"""Derived constants: program relations that read `in` and hold the same
tuples on every example."""

import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from arc.task import load as load_task
from dl.dlparse import TOP, Index, ParseError, Program, parse
from dl.facts import _parse_relations, grid_to_facts
from dl.lint import _lib_items, _lib_source
from dl.paths import SOLVERS_DIR
from dl.souffle import _pool_workers, _run_source
from dl.source import SOLVE_DIRECTIVES, expand_macros

# Relations the probe never outputs: the IO relations of the run modes.
SKIP = {"in", "out", "ex_in", "ex_out", "determination_diff"}

# How deep the walk over comp instances goes. A lib comp instantiates its
# own helpers, and the corpus nests no deeper than this.
MAX_DEPTH = 4

# The seed of the control grids, so a rerun reports the same relations.
CONTROL_SEED = 7

# How many tuples one report line shows.
SHOWN_TUPLES = 4


@dataclass
class Constant:
    """One constant relation, under every instance path that carries it."""

    paths: list[str]
    tuples: list[str]


def _index(source: str) -> Index:
    """The reference index of a solver's expanded source, with lib.dl's
    items merged in.

    A solver reaches its relations through lib comp instances, so the index
    resolves those instances only when lib's comps are in the same program.
    """
    program = parse(source)
    return Index(Program(program.items + _lib_items(_lib_source()),
                         program.comments))


def _edges(ix: Index) -> tuple[dict, dict]:
    """Body-to-head and head-to-body edges over the index's rules."""
    by_rule: dict[int, list] = {}
    for ref in ix.refs:
        by_rule.setdefault(ref.rule, []).append(ref)
    forward: dict[tuple, set] = {}
    backward: dict[tuple, set] = {}
    for idx in range(len(ix.rules)):
        refs = by_rule.get(idx, ())
        head = next((r for r in refs if r.role == "head"), None)
        if head is None:
            continue
        for ref in refs:
            if ref.role == "head":
                continue
            forward.setdefault(ref.key, set()).add(head.key)
            backward.setdefault(head.key, set()).add(ref.key)
    return forward, backward


def _reachable(edges: dict, start: tuple) -> set:
    seen = {start}
    work = [start]
    while work:
        for nxt in edges.get(work.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                work.append(nxt)
    return seen


def _instances(ix: Index) -> list[tuple[str, str]]:
    """(dotted path, comp name) for every comp instance reachable from the
    top level."""
    out: list[tuple[str, str]] = []

    def walk(path: str, comp: str, depth: int, stack: frozenset) -> None:
        if depth > MAX_DEPTH or comp in stack:
            return
        out.append((path, comp))
        for scope in ix.chain(comp):
            for init in ix.inits.get(scope, {}).values():
                walk(f"{path}.{init.inst}", init.comp, depth + 1,
                     stack | {comp})

    for init in ix.inits.get(TOP, {}).values():
        walk(init.inst, init.comp, 1, frozenset())
    return out


def _candidates(ix: Index) -> list[str]:
    """The output names of the relations that read `in` by forward dataflow
    and feed `out` by backward dataflow.

    A relation off either path says nothing about a derivation the output
    rests on: one that never reads `in` is stored, and one `out` never
    reaches is dead.
    """
    forward, backward = _edges(ix)
    reads = _reachable(forward, (TOP, "in"))
    feeds = _reachable(backward, (TOP, "out"))
    wanted = reads & feeds
    names: list[str] = []
    seen: set[str] = set()

    def add(name: str, key: tuple, decl) -> None:
        if key not in wanted or "inline" in decl.qualifiers or name in seen:
            return
        seen.add(name)
        names.append(name)

    for name, decl in ix.decls.get(TOP, {}).items():
        if name not in SKIP:
            add(name, (TOP, name), decl)
    for path, comp in _instances(ix):
        for scope in ix.chain(comp):
            for name, decl in ix.decls.get(scope, {}).items():
                add(f"{path}.{name}", (scope, name), decl)
    return names


def _build(source: str, names: list[str]) -> str:
    """The solve-mode program with an `.output` on each named relation."""
    outputs = "".join(f".output {n}(IO=stdout)\n" for n in names)
    return f"{expand_macros(source)}\n{SOLVE_DIRECTIVES}{outputs}"


def _tuple_sets(built: str, grid: list[list[int]],
                names: list[str]) -> dict[str, frozenset[str]] | None:
    """Each named relation's tuples on one grid, or None when the run fails."""
    try:
        relations = _parse_relations(_run_source(built, grid_to_facts(grid)))
    except Exception:
        return None
    return {n: frozenset(relations.get(n, ())) for n in names}


def _controls(grids: list[list[list[int]]]) -> list[list[list[int]]]:
    """Control grids: each example's extent with its cells redrawn from its
    own palette, plus one grid of a changed extent.

    A relation that reads the input moves when the input does. One that
    holds its tuples over these grids reads something else — the palette,
    the dimensions, a stored fact — so its constancy across the examples
    says nothing.
    """
    rng = random.Random(CONTROL_SEED)
    out = []
    for grid in grids[:3]:
        palette = sorted({c for row in grid for c in row}) or [0]
        out.append([[rng.choice(palette) for _ in row] for row in grid])
    first = grids[0]
    palette = sorted({c for row in first for c in row}) or [0]
    height, width = len(first), len(first[0])
    out.append([[rng.choice(palette) for _ in range(max(1, width - 1))]
                for _ in range(max(1, height + 1))])
    return out


def _collapse(constants: dict[str, frozenset[str]]) -> list[Constant]:
    """One entry per constant, with the sibling instance paths that carry the
    same relation under the same tuples on one line.

    A comp instantiated twice gives each copy its own path, and the copies
    are one finding.
    """
    groups: dict[tuple[str, frozenset[str]], list[str]] = {}
    for name, tuples in constants.items():
        groups.setdefault((name.split(".")[-1], tuples), []).append(name)
    return [
        Constant(paths=sorted(paths), tuples=sorted(tuples))
        for (_, tuples), paths in groups.items()
    ]


def derived_constant_report(
    stem: str,
) -> tuple[list[Constant], int, int] | str:
    """The relations whose tuples are identical on every train and test
    example.

    Such a relation derives from the input yet takes one value over the
    task, so what it holds is stored in the program rather than read off the
    grid. A relation empty everywhere is out: it derives nothing. A relation
    that keeps its tuples on the control grids (see `_controls`) is out too,
    since it does not really read the input.

    Returns (constants, relations tested, relations the controls dropped),
    or a message naming what stopped the probe.
    """
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    try:
        ix = _index(expand_macros(source))
    except ParseError as e:
        return f"source does not parse: {e}"
    names = _candidates(ix)
    if not names:
        return "no relation both reads `in` and feeds `out`"
    built = _build(source, names)
    task = load_task(stem.split("_", 1)[0])
    grids = [ex.input for ex in task.train] + [ex.input for ex in task.test]

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        per_grid = list(executor.map(
            lambda g: _tuple_sets(built, g, names), grids))
    if any(g is None for g in per_grid):
        return "the stored source fails an example"

    constant = {
        n: per_grid[0][n]
        for n in names
        if per_grid[0][n] and all(g[n] == per_grid[0][n] for g in per_grid)
    }
    if not constant:
        return _empty_verdict(len(names))

    flagged = sorted(constant)
    control_built = _build(source, flagged)
    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        controls = list(executor.map(
            lambda g: _tuple_sets(control_built, g, flagged),
            _controls(grids)))
    moved: set[str] = set()
    for got in controls:
        if got is not None:
            moved |= {n for n in flagged if got[n] != constant[n]}
    dropped = len(flagged) - len(moved)
    kept = {n: constant[n] for n in flagged if n in moved}
    return (_collapse(kept), len(names), dropped)


def _empty_verdict(tested: int) -> str:
    return f"no constant relation among the {tested} that read `in`"


def render_derived_constant(
    stem: str, report: tuple[list[Constant], int, int] | str
) -> list[str]:
    """The derived-constant report, as printable lines."""
    if isinstance(report, str):
        return [f"{stem}.dl: {report}"]
    constants, tested, dropped = report
    lines = [f"{tested} relations read `in` and feed `out`"]
    if not constants:
        lines.append("no relation reads the input and holds the same tuples "
                     "on every example")
    else:
        lines.append("")
        lines.append(f"{len(constants)} relation(s) hold the same tuples on "
                     "every train and test example:")
        for c in sorted(constants, key=lambda c: c.paths):
            shown = ", ".join(t.replace("\t", ", ")
                              for t in c.tuples[:SHOWN_TUPLES])
            more = "" if len(c.tuples) <= SHOWN_TUPLES else ", …"
            lines.append(f"  {', '.join(c.paths)}: "
                         f"{len(c.tuples)} tuple(s) — {shown}{more}")
    if dropped:
        lines.append("")
        lines.append(f"{dropped} relation(s) hold their tuples on the control "
                     "grids too, so they do not read the input")
    return lines
