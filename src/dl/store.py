"""Program relations that hold one value on every input: the cases a
stored value states.

A relation between `in` and `out` whose projection onto some of its columns
is the same on every input of the task, train and test, states a model that
stores that value rather than reading it off the grid. That model is a case
of the solver, and the runner owns it: the solver carries one `// @store`
line above the relation's declaration, and no branch.

The witness tells the stored case from the derivation. The tool builds one
by turning or mirroring a train input, or by swapping a stored color with a
free one: the derivation follows the grid, the stored value does not, and
the two cases give different outputs, or one is defined and the other is
not. A relation no such grid separates takes
a hand-built entry of the witness file, under the id `<rel>=stored`.
"""

import itertools
import random
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache

from arc.task import load as load_task
from controlled_markdown import mctx
from dl.annotations import (
    DECL_RE,
    INIT_RE,
    STORED,
    Store,
    store_blocks,
    store_relation,
)
from dl.derived_constant import (
    SKIP,
    _build,
    _controls,
    _edges,
    _index,
    _instances,
    _reachable,
    _tuple_sets,
)
from dl.determination_plan import fact_params
from dl.dlparse import (
    TOP,
    Comp,
    Index,
    ParseError,
    TypeDecl,
    marker_cases,
    parse,
)
from dl.domains import _lib_defines
from dl.facts import grid_to_facts
from dl.lint import choice_points, concept_case
from dl.solve import (
    parse_output,
    res_out_stem,
    run_dl_source,
    solver_file,
)
from dl.souffle import _pool_workers, _run_source
from dl.source import SOLVE_DIRECTIVES, expand_macros
from dl.witness import Witness, case_outcomes, load_witnesses

STORE_OK = "store: ok"
"""The pass line, printed when no finding stands."""

OTHER = "other"
"""The verdict that takes a judged output, which only an entry holds."""

IGNORE_RE = re.compile(r"//\s*@ignore(?:\s+([\w.]+))?:\s*store\b")
"""The directive that dismisses this check. Above a `.decl` it names the
relation declared under it; above a `.init` the bare form dismisses the
whole instance and the named form one relation of it."""

POS_TYPES = frozenset({"Position", "Box"})
"""Types whose value is a cell of the frame."""

OFFSET_TYPE = "Offset"

COLOR_TYPE = "Color"

UNIT_TYPE = "Unit"

IDENT_TYPE = "Ident"

NO_COLUMN_TYPES = frozenset({UNIT_TYPE, IDENT_TYPE})
"""Types that label a row rather than hold a value. A column of one of
these, and a case column, is no column of the value the report names."""

FULL = {"Dir": 4, "Axis": 2, "DiagDir": 4, "DiagAxis": 2, "D4": 8, "C4": 4,
        "Sym": 10, "Sense": 2, "Dir8": 8, "Axis4": 4}
"""Each orientation type and how many elements it holds. A column that
ranges over all of them states the type, not a value."""

DATA_TYPES = POS_TYPES | {OFFSET_TYPE, "number", COLOR_TYPE} | set(FULL)
"""The column types a stored value can hold."""

MAX_COLS = 6
"""Relations wider than this take too many column subsets to test."""

ROW_CAP = 20000
"""Rows above which a relation is not checked. The cap stands well past the
largest stored picture of the corpus, so a relation over it is a structure
over the frame, not a value a solver would store."""

SWAP_SEED = 11

SHOWN_MEMBERS = 8
"""How many members of a value that draws no picture the report spells out.
A larger value goes under its member count."""

DRAW_CAP = 30
"""How far a picture reaches along each axis. A value whose cells spread
further goes under its member count."""

OWNED = "owned"
CONSTANT = "constant"
TRANSLATED = "translated"

# The D4 elements, each named as the report names it.
D4_NAMES = {
    "CW": "turned a quarter turn clockwise",
    "HT": "turned a half turn",
    "CC": "turned a quarter turn counterclockwise",
    "LR": "mirrored left-right",
    "TB": "mirrored top-bottom",
    "DG": "mirrored across the main diagonal",
    "AD": "mirrored across the anti-diagonal",
}

@lru_cache(maxsize=1)
def _orientation() -> tuple[dict[str, str], list[frozenset[str]]]:
    """Each orientation value under the lib's name for it, and the whole
    value set of each orientation type. The lib numbers the types apart, so
    a value names one element of one type."""
    names: dict[str, str] = {}
    groups: dict[str, set[str]] = {}
    for name, value in _lib_defines().items():
        prefix = name.split("_")[0]
        if prefix not in _ORIENTATION_PREFIXES:
            continue
        names[str(value)] = name
        groups.setdefault(prefix, set()).add(str(value))
    return names, [frozenset(g) for g in groups.values()]


_ORIENTATION_PREFIXES = frozenset(
    {"DIR", "AXIS", "DIAG", "DAXIS", "D4", "SENSE", "SYM"})


TWIN = "_store_twin"
VALUES = "_store_values"


@dataclass
class Move:
    """The grid on which a relation's value differs: the train input it
    comes from, and the transformation that made it. `identity` says the
    concept case gives that grid unchanged."""

    grid: str
    change: str
    identity: bool = False


@dataclass
class Found:
    """One column subset of one relation whose projected value repeats.

    `rel` is the relation's path, `cols` the names of the columns the value
    lives in, `sub` whether those are fewer than the relation's columns,
    and `keys` the names of the other columns. `kind` is `owned` for one
    value on every input, `constant` for one family of values, and
    `translated` for one value once each set is shifted to its own corner.
    `ref` is that value, as the run prints it.
    """

    rel: str
    cols: list[str]
    keys: list[str]
    types: list[str]
    sub: bool
    kind: str
    case: str
    concept: bool
    read: bool
    ref: frozenset
    rect: str = ""
    line: Store | None = None
    entry: str = ""
    move: Move | None = None
    facts: tuple = ()
    """The relation's whole rows, where no key column stands. The stored
    case puts these in place of the clauses that derive the relation."""
    used_in: str = ""
    """The cases whose markers hold the reads and the feeds."""
    under: list[str] = field(default_factory=list)
    """The relations that fold under this one, downstream of it."""
    folded: bool = False
    """The relation stands downstream of another the report names, so that
    one answers for it."""

    @property
    def case_id(self) -> str:
        return f"{self.rel}={STORED}"

    @property
    def colors(self) -> bool:
        return bool(self.types) and all(t == COLOR_TYPE for t in self.types)


@dataclass
class Finding:
    """One finding of the store report: where it stands, and what it
    says."""

    where: str
    text: str


@dataclass
class Report:
    found: list[Found] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    error: str = ""


# --- candidates -------------------------------------------------------

def _solver_scopes(source: str) -> set[str]:
    """The top level and the comps the solver declares as program code."""
    return {TOP} | {c for c in parse(source).comps()
                    if c not in ("Params", "Determine", "ParamsHelpers")}


def _candidates(ix: Index, scopes: set[str]) -> dict[str, tuple]:
    """Path -> (key, decl) for the relations between `in` and `out` that a
    clause of a solver scope reads or writes."""
    forward, backward = _edges(ix)
    wanted = (_reachable(forward, (TOP, "in"))
              & _reachable(backward, (TOP, "out")))
    out: dict[str, tuple] = {}

    def add(name: str, key: tuple, decl) -> None:
        if key not in wanted or "inline" in decl.qualifiers or name in out:
            return
        if not any(r.scope in scopes for r in ix.refs_of(key)):
            return
        out[name] = (key, decl)

    for name, decl in ix.decls.get(TOP, {}).items():
        if name not in SKIP:
            add(name, (TOP, name), decl)
    for path, comp in _instances(ix):
        for scope in ix.chain(comp):
            for name, decl in ix.decls.get(scope, {}).items():
                add(f"{path}.{name}", (scope, name), decl)
    return out


def _uses(ix: Index, key: tuple, scopes: set[str], branches: set[str],
          concept: set[str]) -> tuple[bool, set[str]]:
    """Whether the concept case reads or feeds the relation, and the cases
    whose markers hold the uses. A feed counts: an instance's input is what
    the program puts into it. A clause under no marker runs on every case,
    so the concept case runs it."""
    cases: set[str] = set()
    by_concept = False
    for r in ix.refs_of(key):
        if r.scope not in scopes:
            continue
        section = ix.rules[r.rule].section
        marked = ({c.lstrip("$") for c in marker_cases(section)} & branches
                  if section else set())
        cases |= marked
        if not marked or marked & concept:
            by_concept = True
    return by_concept, cases


# --- cases ------------------------------------------------------------

def _case_types(ix: Index) -> set[str]:
    """`Choice` and every other ADT the program declares, bar the tiebreak
    resolution and the unit key. A column of one of these types carries the
    case."""
    out = {"Choice"}
    for it in ix.program.items:
        if (isinstance(it, TypeDecl) and it.branches
                and it.name not in ("TiebreakResolution", UNIT_TYPE)):
            out.add(it.name)
    return out


def _branch_names(source: str, ix: Index,
                  casetypes: set[str]) -> tuple[set[str], set[str], list]:
    """Every branch name, the concept branch names, and the branches of
    each choice type. A type declares its concept branch first."""
    every: set[str] = set()
    concept: set[str] = set()
    universes: list[frozenset[str]] = []
    for point in choice_points(source):
        for b in point.branches:
            every.add(b.name)
            if b.is_concept:
                concept.add(b.name)
    for it in ix.program.items:
        if not (isinstance(it, TypeDecl) and it.name in casetypes
                and it.branches):
            continue
        universes.append(frozenset(it.branches))
        every |= set(it.branches)
        concept.add(it.branches[0])
    return every, concept, universes


def _section_cases(ix: Index, key: tuple, branches: set[str]) -> set[str]:
    """The cases the section markers of the defining clauses name."""
    out: set[str] = set()
    for r in ix.refs_of(key):
        if r.scope != TOP or r.role != "head":
            continue
        section = ix.rules[r.rule].section
        if section:
            out |= {c.lstrip("$") for c in marker_cases(section)} & branches
    return out


def _ctor_names(value: str) -> set[str]:
    """The constructor names a printed case value holds: `$A` gives `A`,
    and `[$A, $B(1)]` gives `A` and `B`."""
    out = set()
    flat = value.replace("[", " ").replace("]", " ").replace(",", " ")
    for part in flat.split():
        if part.startswith("$"):
            out.add(part[1:].split("(", 1)[0])
    return out


def _spread(family: frozenset, subset: tuple, types: list[str]) -> bool:
    """Whether every set of the family holds two cells or more. One cell is
    the same up to translation whatever the other columns hold."""
    cells = [j for j, i in enumerate(subset) if types[i] in POS_TYPES]
    return all(len({tuple(m[j] for j in cells) for m in g}) >= 2
               for g in family)


def _full_set(family: frozenset) -> bool:
    """Whether every set of the family is the whole element set of one
    orientation type. Such a column states the type, not a value."""
    groups = _orientation()[1]
    return all(any(frozenset(m[0] for m in g) == whole for whole in groups)
               for g in family)


def _split_cases(rows: list[list[str]],
                 case_cols: list[int]) -> dict[str, list[list[str]]]:
    """The rows per case value, under one empty key where no column carries
    the case."""
    if not case_cols:
        return {"": rows}
    out: dict[str, list[list[str]]] = {}
    for row in rows:
        out.setdefault(", ".join(row[i] for i in case_cols), []).append(row)
    return out


# --- families ---------------------------------------------------------

def _point(text: str) -> tuple[int, int]:
    """The top and the left of a printed Box record."""
    t, _b, l, _r = (int(x) for x in text[1:-1].split(","))
    return t, l


def _normalize(members: set[tuple], pos_idx: list[int]) -> frozenset:
    """One set with its cells shifted to its own corner."""
    ps = [_point(m[j]) for m in members for j in pos_idx]
    t0 = min(p[0] for p in ps)
    l0 = min(p[1] for p in ps)
    return frozenset(
        tuple((_point(x)[0] - t0, _point(x)[1] - l0) if j in pos_idx else x
              for j, x in enumerate(m))
        for m in members)


def _families(rows: list[list[str]], types: list[str], cols: list[int],
              subsets=None) -> dict:
    """Subset -> (family, translated family). A family holds one projection
    per value of the other columns."""
    n = len(types)
    if subsets is None:
        subsets = [s for k in range(1, len(cols) + 1)
                   for s in itertools.combinations(cols, k)]
    out = {}
    for s in subsets:
        rest = [i for i in range(n) if i not in s]
        groups: dict[tuple, set] = {}
        for row in rows:
            groups.setdefault(tuple(row[i] for i in rest), set()).add(
                tuple(row[i] for i in s))
        fam = frozenset(frozenset(g) for g in groups.values())
        pos_idx = [j for j, i in enumerate(s) if types[i] in POS_TYPES]
        tfam = (frozenset(_normalize(g, pos_idx) for g in groups.values())
                if pos_idx else None)
        out[s] = (fam, tfam)
    return out


def _analyze(per_grid: list[dict], names: list[str], cands: dict,
             casetypes: set[str], resolved: dict[str, list[str]],
             skipped: list[str]) -> dict:
    """(path, case) -> (types, {subset: kind}, families of the first
    input)."""
    found: dict = {}
    for name in names:
        types = resolved[name]
        if not types or len(types) > MAX_COLS:
            continue
        if any(not g[name] for g in per_grid):
            continue
        rows_per = [[r.split("\t") for r in g[name]] for g in per_grid]
        if max(len(r) for r in rows_per) > ROW_CAP:
            skipped.append(name)
            continue
        case_cols = [i for i in range(len(types)) if types[i] in casetypes]
        by_case = [_split_cases(rows, case_cols) for rows in rows_per]
        cases = set(by_case[0])
        if any(set(b) != cases for b in by_case):
            continue
        data_cols = [i for i in range(len(types)) if types[i] in DATA_TYPES]
        for case in sorted(cases):
            crow = [b[case] for b in by_case]
            # A subset is the same on every input only when each of its
            # columns holds the same values on every input. A cell column
            # may still enter a translated subset.
            colsets = [[{r[i] for r in rows} for i in range(len(types))]
                       for rows in crow]
            cols = [i for i in data_cols
                    if all(cs[i] == colsets[0][i] for cs in colsets)
                    or types[i] in POS_TYPES]
            if not cols:
                continue
            fams = [_families(rows, types, cols) for rows in crow]
            hits: dict[tuple, str] = {}
            for s in fams[0]:
                fam0, tfam0 = fams[0][s]
                if len(s) == 1 and types[s[0]] in FULL and _full_set(fam0):
                    continue
                if all(f[s][0] == fam0 for f in fams):
                    hits[s] = OWNED if len(fam0) == 1 else CONSTANT
                elif (tfam0 is not None and _spread(tfam0, s, types)
                      and all(f[s][1] == tfam0 for f in fams)):
                    hits[s] = TRANSLATED
            keep = {
                s: k for s, k in hits.items()
                if not any(set(s) < set(s2)
                           and hits[s2] in (k, OWNED)
                           for s2 in hits)
            }
            if keep:
                found[(name, case)] = (types, keep, fams[0], crow[0])
    return found


# --- filters ----------------------------------------------------------

def _rect(points: set[tuple[int, int]]) -> str:
    """`HxW` when the cells fill their bounding rectangle, and empty
    otherwise."""
    if not points:
        return ""
    ts = [p[0] for p in points]
    ls = [p[1] for p in points]
    h, w = max(ts) - min(ts) + 1, max(ls) - min(ls) + 1
    return f"{h}x{w}" if h * w == len(points) else ""


def _is_frame(rect: str, grids: list[list[list[int]]]) -> bool:
    """Whether a filled rectangle covers the whole extent of every input."""
    height, width = (int(x) for x in rect.split("x"))
    return all(len(g) == height and len(g[0]) == width for g in grids)


def _value(text: str):
    if text.startswith("["):
        return tuple(int(x) for x in text[1:-1].split(","))
    return int(text) if text.lstrip("-").isdigit() else text


def _stored_sets(source: str, defines: dict[str, int]) -> dict:
    """Each stored fact parameter's value, exact and shifted to its own
    corner."""
    out = {}
    for param, (types, stored) in fact_params(source, defines).items():
        pos_idx = [i for i, t in enumerate(types) if t in POS_TYPES]
        trans = None
        if pos_idx and stored:
            t0 = min(row[i][0] for row in stored for i in pos_idx)
            l0 = min(row[i][2] for row in stored for i in pos_idx)
            trans = frozenset(
                tuple((v[0] - t0, v[2] - l0) if i in pos_idx else v
                      for i, v in enumerate(row))
                for row in stored)
        out[param] = (frozenset(stored), trans)
    return out


def _restates(kind: str, ref: frozenset, stored: dict) -> bool:
    """Whether the one set the finding holds is a stored parameter's
    value."""
    if len(ref) != 1:
        return False
    members = next(iter(ref))
    if kind == TRANSLATED:
        value = frozenset(
            tuple(_value(x) if isinstance(x, str) else x for x in m)
            for m in members)
        return any(trans is not None and trans == value
                   for _exact, trans in stored.values())
    value = frozenset(tuple(_value(x) for x in m) for m in members)
    return any(exact == value for exact, _trans in stored.values())


# --- grids ------------------------------------------------------------

def _count_source(source: str, cands: dict,
                  names: list[str]) -> tuple[str, dict[str, str]]:
    """The solve-mode program whose outputs are one row count per relation,
    and the count relation's name per relation.

    The counts and the tuples come from the same expanded source, so a count
    names the rows the base run would print.
    """
    parts: list[str] = []
    of_count: dict[str, str] = {}
    for i, name in enumerate(names):
        arity = len(cands[name][1].fields)
        if not arity:
            continue
        cname = f"_store_n{i}"
        of_count[cname] = name
        args = ", ".join("_" for _ in range(arity))
        parts.append(f".decl {cname}(n: number)\n"
                     f"{cname}(N) :- N = count : {{ {name}({args}) }}.\n"
                     f".output {cname}(IO=stdout)\n")
    return (f"{expand_macros(source)}\n{SOLVE_DIRECTIVES}" + "".join(parts),
            of_count)


def _d4_images(grid: list[list[int]]) -> dict[str, list[list[int]]]:
    """The seven other images of a grid under D4."""
    h, w = len(grid), len(grid[0])
    rot = [[grid[h - 1 - r][c] for r in range(h)] for c in range(w)]

    def lr(g):
        return [row[::-1] for row in g]

    def tb(g):
        return g[::-1]

    def tr(g):
        return [list(x) for x in zip(*g)]

    return {"CW": rot, "HT": tb(lr(grid)), "CC": tb(lr(rot)),
            "LR": lr(grid), "TB": tb(grid), "DG": tr(grid),
            "AD": tb(lr(tr(grid)))}


def _swap_grid(grid: list[list[int]], a: int, b: int) -> list[list[int]]:
    return [[b if c == a else a if c == b else c for c in row]
            for row in grid]


def _swaps(grids: list[list[list[int]]],
           held: set[int]) -> list[tuple[str, str, list[list[int]]]]:
    """One color swap per train input: a stored color the grid holds
    against a color no grid holds."""
    rng = random.Random(SWAP_SEED)
    out = []
    for i, grid in enumerate(grids):
        used = {c for row in grid for c in row}
        stored = sorted(held & used)
        free = [c for c in range(10) if c not in used | held]
        if not stored or not free:
            continue
        a = stored[0]
        b = free[rng.randrange(len(free))]
        out.append((f"train {i}",
                    mctx("with {a} and {b} swapped").format(a=a, b=b),
                    _swap_grid(grid, a, b)))
    return out


# --- the stored case --------------------------------------------------

def _top_level_lines(source: str) -> list[int]:
    """The indices of the source lines that stand outside every comp."""
    depth = 0
    out = []
    for i, raw in enumerate(source.splitlines()):
        code = raw.split("//")[0]
        opens = code.count("{")
        closes = code.count("}")
        if depth == 0 and not code.lstrip().startswith(".comp"):
            out.append(i)
        depth += opens - closes
        depth = max(depth, 0)
    return out


def _rename_reads(source: str, rel: str, twin: str) -> str:
    """The source with the top-level clause bodies reading `twin` where
    they read `rel`."""
    pattern = re.compile(r"(?<![\w.])" + re.escape(rel) + r"\s*\(")
    lines = source.splitlines()
    top = set(_top_level_lines(source))
    in_body = False
    for i, raw in enumerate(lines):
        if i not in top:
            continue
        code, sep, comment = raw.partition("//")
        if in_body:
            code = pattern.sub(twin + "(", code)
        elif ":-" in code:
            head, arrow, body = code.partition(":-")
            code = head + arrow + pattern.sub(twin + "(", body)
            in_body = True
        if code.rstrip().endswith("."):
            in_body = False
        lines[i] = code + sep + comment
    return "\n".join(lines) + "\n"


def _comp_params(ix: Index) -> dict[str, list[str]]:
    """Each comp's type parameters, by comp name."""
    out: dict[str, list[str]] = {}

    def walk(items) -> None:
        for it in items:
            if isinstance(it, Comp):
                out[it.name] = it.params
                walk(it.items)

    walk(ix.program.items)
    return out


def _type_args(ix: Index, path: str) -> dict[str, str]:
    """The type each parameter of the instance's comp stands for, read down
    the instance path."""
    params = _comp_params(ix)
    scope = TOP
    subst: dict[str, str] = {}
    for part in path.split("."):
        scopes = [TOP] if scope == TOP else list(ix.chain(scope))
        init = next((i for s in scopes
                     if (i := ix.inits.get(s, {}).get(part)) is not None),
                    None)
        if init is None:
            return subst
        args = [subst.get(a, a) for a in init.targs]
        subst = dict(zip(params.get(init.comp, []), args))
        scope = init.comp
    return subst


def _twin_text(rel: str, decl, cols: list[int], ref: frozenset,
               subst: dict[str, str]) -> str:
    """The twin relation: the keys of the derivation against the stored
    value set."""

    def type_of(f) -> str:
        return subst.get(f.type, f.type)

    fields = ", ".join(f"{f.name}: {type_of(f)}" for f in decl.fields)
    values = sorted(next(iter(ref)))
    value_fields = ", ".join(
        f"{decl.fields[i].name}: {type_of(decl.fields[i])}" for i in cols)
    head, body = [], []
    for i in range(len(decl.fields)):
        if i in cols:
            head.append(f"V{i}")
            body.append("_")
        else:
            head.append(f"K{i}")
            body.append(f"K{i}")
    take = ", ".join(f"V{i}" for i in cols)
    facts = "".join(f"{VALUES}({', '.join(row)}).\n" for row in values)
    return (f"\n.decl {VALUES}({value_fields})\n{facts}"
            f".decl {TWIN}({fields})\n"
            f"{TWIN}({', '.join(head)}) :- "
            f"{rel}({', '.join(body)}), {VALUES}({take}).\n")


def _fact_arg(text: str) -> str:
    """One printed argument as a fact writes it. The runner prints a
    constructor without its parentheses."""
    return f"{text}()" if text.startswith("$") and "(" not in text else text


def _stored_facts(rel: str, facts: tuple) -> str:
    """The relation's rows as facts, under the instance path."""
    return "".join(
        f"{rel}({', '.join(_fact_arg(a) for a in row)}).\n" for row in facts)


def _head_rules(ix: Index, rel: str) -> list:
    """The rules of the program whose head is the relation, each as its
    first and last line."""
    prefixes: dict[str, list[str]] = {TOP: [""]}
    for path, comp in _instances(ix):
        prefixes.setdefault(comp, []).append(path)
    out = []
    for r in ix.refs:
        if r.role != "head":
            continue
        for prefix in prefixes.get(r.scope, []):
            name = ".".join(x for x in (prefix, r.atom.qual or "",
                                        r.atom.name) if x)
            if name == rel:
                rule = ix.rules[r.rule].rule
                out.append((rule.line, rule.end_line))
    return out


def _replace_clauses(expanded: str, ix: Index, found: Found) -> str:
    """The program with the clauses that derive the relation taken out and
    the stored facts put in their place."""
    lines = expanded.splitlines()
    for start, end in _head_rules(ix, found.rel):
        for i in range(start - 1, min(end, len(lines))):
            lines[i] = ""
    return ("\n".join(lines) + "\n"
            + _stored_facts(found.rel, found.facts))


def store_case_program(expanded: str, ix: Index, found: Found, decl,
                       subst: dict[str, str]) -> str:
    """The solve-mode program running the stored case. A relation with no
    key column takes the stored facts in place of its clauses; one with key
    columns keeps its keys and takes its values from the stored set."""
    if not found.keys:
        text = _replace_clauses(expanded, ix, found)
    else:
        cols = [i for i, f in enumerate(decl.fields) if f.name in found.cols]
        text = (_rename_reads(expanded, found.rel, TWIN)
                + _twin_text(found.rel, decl, cols, found.ref, subst))
    return f"{text}\n{SOLVE_DIRECTIVES}"


def store_outcome(stem: str, case_id: str, grid: list[list[int]]):
    """What the stored case named by `case_id` gives on one grid, and None
    when the runner holds no such case."""
    report = store_report(stem)
    for f in report.found:
        if f.kind == OWNED and f.case_id == case_id:
            path, _task_id = solver_file(stem)
            source = path.read_text()
            built = _case_program(source, f)
            if built is None:
                return None
            return _case_outcome(built, grid, path, concept_case(source),
                                 res_out_stem(stem))
    return None


def _case_program(source: str, found: Found) -> str | None:
    """The stored case's program, built off the solver's expanded source."""
    expanded = expand_macros(source)
    try:
        ix = _index(expanded)
    except ParseError:
        return None
    hit = _candidates(ix, _solver_scopes(expanded)).get(found.rel)
    if hit is None:
        return None
    subst = _type_args(ix, found.rel.rpartition(".")[0])
    return store_case_program(expanded, ix, found, hit[1], subst)


def _decl_of(source: str, rel: str):
    """The declaration of a relation named by its instance path, and the
    type each parameter of its comp stands for."""
    expanded = expand_macros(source)
    try:
        ix = _index(expanded)
    except ParseError:
        return None, {}
    hit = _candidates(ix, _solver_scopes(expanded)).get(rel)
    if hit is None:
        return None, {}
    return hit[1], _type_args(ix, rel.rpartition(".")[0])


def _concept_outcome(source: str, grid: list[list[int]], path, concept: str,
                     resolution: bool):
    outcomes = case_outcomes(
        run_dl_source(source, grid, solver_path=path), resolution)
    return outcomes.get(concept)


def _case_outcome(built: str, grid: list[list[int]], path, concept: str,
                  resolution: bool):
    """What the concept case gives on one grid, under a program already
    assembled for the run."""
    try:
        got = parse_output(_run_source(built, grid_to_facts(grid),
                                       solver_path=path))
    except Exception:
        return None
    return case_outcomes(got, resolution).get(concept)


# --- the report -------------------------------------------------------

def _ignore_sites(source: str) -> set[str]:
    """The relations an `@ignore: store` line dismisses: the one a `.decl`
    under the line names, the one an instance's `.init` and the line's own
    relation name give, and, where the line names none, every relation of
    the instance."""
    out: set[str] = set()
    lines = source.splitlines()
    for i, raw in enumerate(lines):
        mark = IGNORE_RE.match(raw.strip())
        if mark is None:
            continue
        for below in lines[i + 1:]:
            text = below.strip()
            if not text or text.startswith("//"):
                continue
            if (m := DECL_RE.match(below)) and not mark[1]:
                out.add(m[1])
            elif m := INIT_RE.match(below):
                out.add(f"{m[1]}.{mark[1]}" if mark[1] else m[1] + ".")
            break
    return out


def _names(spelled: str, rel: str) -> bool:
    """Whether a directive's relation names this one. A site inside a comp
    spells the path from that comp, so a suffix of the instance path
    answers for it."""
    return rel == spelled or rel.endswith("." + spelled)


def _ignored(sites: set[str], rel: str) -> bool:
    """Whether an `@ignore: store` line dismisses this relation."""
    return any(_names(s, rel) if not s.endswith(".")
               else _names(s + rel.rpartition(".")[2], rel)
               for s in sites)


def _run_all(built: str, grids: list[list[list[int]]],
             names: list[str]) -> list[dict] | None:
    got = _run_each(built, grids, names)
    return None if any(g is None for g in got) else got


def _run_each(built: str, grids: list[list[list[int]]],
              names: list[str]) -> list[dict | None]:
    """Each grid's tuples, with None where the run fails. A grid the solver
    refuses says nothing, and it leaves the other grids standing."""
    with ThreadPoolExecutor(max_workers=_pool_workers()) as pool:
        return list(pool.map(lambda g: _tuple_sets(built, g, names), grids))


def store_report(stem: str) -> Report:
    """Every column subset of the solver's program relations that holds one
    value on every input, with its witness and its `@store` line, and the
    findings that stand on them."""
    path, task_id = solver_file(stem)
    source = path.read_text()
    expanded = expand_macros(source)
    try:
        ix = _index(expanded)
    except ParseError as e:
        return Report(error=f"source does not parse: {e}")
    scopes = _solver_scopes(expanded)
    cands = _candidates(ix, scopes)
    names = list(cands)
    if not names:
        return Report(error="no relation both reads `in` and feeds `out`")
    casetypes = _case_types(ix)
    resolved = {
        name: [subst.get(f.type, f.type) for f in decl.fields]
        for name, (_k, decl) in cands.items()
        for subst in [_type_args(ix, name.rpartition(".")[0])]
    }
    branches, concept_branches, universes = _branch_names(
        source, ix, casetypes)
    stored = _stored_sets(expanded, _lib_defines())
    task = load_task(task_id)
    grids = [ex.input for ex in task.train] + [ex.input for ex in task.test]

    # Size pre-pass: count each relation's rows before any run prints them,
    # so a relation over the cap costs one count and no print.
    pre, of_count = _count_source(source, cands, names)
    per_count = _run_all(pre, grids, list(of_count))
    if per_count is None:
        return Report(error="the stored source fails an example")
    skipped: list[str] = []
    over: set[str] = set()
    for cname, name in of_count.items():
        got = [next(iter(g[cname]), None) for g in per_count]
        if any(x is None for x in got):
            continue
        rows = [int(x) for x in got]
        if max(rows) <= ROW_CAP:
            continue
        over.add(name)
        types = resolved[name]
        if types and len(types) <= MAX_COLS and min(rows) > 0:
            skipped.append(name)

    run_names = [n for n in names if n not in over]
    per_grid = _run_all(_build(source, run_names), grids, run_names)
    if per_grid is None:
        return Report(error="the stored source fails an example")
    labels = ([f"train {i}" for i in range(len(task.train))]
              + [f"test {i}" for i in range(len(task.test))])
    differs = {
        n: next((labels[i] for i, g in enumerate(per_grid)
                 if g[n] != per_grid[0][n]), "")
        for n in run_names
    }
    raw = _analyze(per_grid, run_names, cands, casetypes, resolved, skipped)
    if not raw:
        return Report(skipped=sorted(skipped),
                      findings=_findings(source, stem, [], cands, differs))

    flagged = sorted({name for name, _case in raw})
    probe = _build(source, flagged)
    # Two controls: the first palette redraw and the changed extent.
    controls = _controls(grids)
    ctrl = _run_each(probe, [controls[0], controls[-1]], flagged)

    cache: dict[tuple, dict] = {}

    def projection(g, name, case, subset, kind, types, case_cols):
        """The relation's value on one probe grid, and None when the
        relation is empty there."""
        if g is None or not g[name]:
            return None
        k = (id(g), name, case)
        if k not in cache:
            rows = _split_cases([r.split("\t") for r in g[name]],
                                case_cols).get(case, [])
            needed = [s2 for (n2, _c2), (_t, keep, _f, _r) in raw.items()
                      if n2 == name for s2 in keep]
            cache[k] = _families(rows, types, [], needed) if rows else {}
        fam = cache[k].get(subset)
        if fam is None:
            return None
        return fam[1] if kind == TRANSLATED else fam[0]

    # The case the input reading is taken on. A branch of its own may
    # derive what it reads, and that derivation is the branch's reading,
    # not the relation's, so the concept branch answers for the relation.
    concept_key: dict[str, str] = {}
    for name, case in raw:
        members = _ctor_names(case)
        if members and members <= concept_branches:
            concept_key[name] = case

    found: list[Found] = []
    pending: list[tuple] = []
    reading: set[str] = set()
    """The relations the controls left standing, whatever filter took them
    afterwards. A relation derived from one of these inherits its value
    from it."""
    sites = _ignore_sites(source)
    for (name, case), (types, keep, fam0, rows) in sorted(raw.items()):
        key, decl = cands[name]
        if _ignored(sites, name):
            continue
        case_cols = [i for i in range(len(types)) if types[i] in casetypes]
        members = (_ctor_names(case) if case
                   else _section_cases(ix, key, branches))
        label = ", ".join(sorted(members)) if members else "shared"
        is_concept = (not members) or bool(members & concept_branches)
        reads, use_cases = _uses(ix, key, scopes, branches,
                                 concept_branches)
        for subset, kind in keep.items():
            ref = fam0[subset][1] if kind == TRANSLATED else fam0[subset][0]
            args = (name, case, subset, kind, types, case_cols)
            read_case = concept_key.get(name, case)
            base = ref
            if read_case != case:
                base = projection(per_grid[0], name, read_case, subset, kind,
                                  types, case_cols)
                if base is None:
                    base, read_case = ref, case
            read_args = (name, read_case, subset, kind, types, case_cols)
            # A control grid gives evidence only where the relation stands
            # nonempty on it. A grid the solver leaves it empty on says
            # nothing, and the controls then hold the finding back on
            # nothing.
            palette, extent = (projection(g, *read_args) for g in ctrl)
            evidence = [r for r in (palette, extent) if r is not None]
            if evidence and all(r == base for r in evidence):
                continue  # the value does not read the input
            reading.add(name)
            sizes = sorted(len(s) for s in ref)
            if (len(subset) == 1 and len(ref) > 1
                    and all(n == 1 for n in sizes)):
                continue  # the column is a function of the key
            rect = ""
            if (len(subset) == 1 and types[subset[0]] == "Position"
                    and len(ref) == 1):
                one = next(iter(ref))
                points = ({m[0] for m in one} if kind == TRANSLATED
                          else {_point(m[0]) for m in one})
                rect = _rect(points)
            extent_only = (palette is not None and palette == base
                           and extent is not None and extent != base)
            if rect and _is_frame(rect, grids):
                continue  # the frame of every input
            positional = any(types[i] in POS_TYPES | {OFFSET_TYPE}
                             for i in subset)
            if extent_only and (rect or positional):
                continue  # the frame, a panel, a tile, or layout over them
            dir_cols = [i for i in subset if types[i] in FULL]
            pos_cols = [i for i in subset if types[i] in POS_TYPES]
            if (len(subset) == 2 and len(dir_cols) == 1 and len(pos_cols) == 1
                    and all(n == FULL[types[dir_cols[0]]] for n in sizes)):
                continue  # a neighborhood generated around a point
            if _restates(kind, ref, stored):
                continue  # a stored parameter's value under another name
            keys = [i for i in range(len(types)) if i not in subset
                    and types[i] not in casetypes | {UNIT_TYPE}]
            if kind == CONSTANT and not (
                    keys and all(types[i] == IDENT_TYPE for i in keys)):
                continue  # the owned relation over all its columns
            columns = [i for i in range(len(types))
                       if types[i] not in casetypes | NO_COLUMN_TYPES]
            facts = tuple(sorted(tuple(r) for r in rows)) if not keys else ()
            found.append(Found(
                rel=name,
                cols=[decl.fields[i].name for i in subset],
                keys=[decl.fields[i].name for i in keys],
                types=[types[i] for i in subset],
                sub=len(subset) < len(columns),
                kind=kind, case=label, concept=is_concept, read=reads,
                ref=ref, rect=rect, facts=facts,
                used_in=", ".join(sorted(use_cases))))
            pending.append((found[-1], args))

    bodies = _body_map(ix, scopes)
    kept = {id(f) for f in _inherited(bodies, ix, found, reading)}
    pending = [p for p in pending if id(p[0]) in kept]
    kept = {id(f) for f in _merge([f for f in found if id(f) in kept])}
    pending = [p for p in pending if id(p[0]) in kept]
    found = [p[0] for p in pending]
    _fold(found, _body_map(ix, scopes, deep=True),
          universes)
    _attach_witnesses(stem, source, path, task, cands, pending, projection)
    _attach_lines(source, found)
    return Report(found=found, skipped=sorted(skipped),
                  findings=_findings(source, stem, found, cands, differs))


def _relation_keys(ix: Index) -> list[tuple[str, tuple]]:
    """Every relation of the program under its instance path."""
    out = [(name, (TOP, name)) for name in ix.decls.get(TOP, {})]
    for path, comp in _instances(ix):
        for scope in ix.chain(comp):
            out += [(f"{path}.{name}", (scope, name))
                    for name in ix.decls.get(scope, {})]
    return out


def _body_map(ix: Index, scopes: set[str],
              deep: bool = False,
              rules: set[int] | None = None) -> dict[str, set[str]]:
    """Each relation's body relations, by instance path. A relation derived
    inside a lib comp takes the relations fed to its instance, and, where
    `deep` stands, the relations of that instance it derives from. Where
    `rules` stands, only the rules it names give edges."""
    by_rule: dict[int, list] = {}
    for r in ix.refs:
        by_rule.setdefault(r.rule, []).append(r)
    prefixes: dict[str, list[str]] = {TOP: [""]}
    comp_of: dict[str, str] = {}
    for path, comp in _instances(ix):
        prefixes.setdefault(comp, []).append(path)
        comp_of[path] = comp
    backward = _edges(ix)[1]

    def full(prefix: str, atom) -> str:
        return ".".join(x for x in (prefix, atom.qual or "", atom.name) if x)

    keys = dict(_relation_keys(ix))

    def bodies(rel: str) -> set[str]:
        key = keys.get(rel)
        if key is None:
            return set()
        out: set[str] = set()
        seen = False
        for r in ix.refs_of(key):
            if r.role != "head" or r.scope not in scopes:
                continue
            if rules is not None and r.rule not in rules:
                continue
            for prefix in prefixes.get(r.scope, []):
                if full(prefix, r.atom) != rel:
                    continue
                seen = True
                out |= {full(prefix, b.atom) for b in by_rule[r.rule]
                        if b.role != "head"}
        if seen:
            return out
        # Derived inside a lib comp. The instance holds what the top level
        # feeds it, so the feeds answer for every relation of it.
        inst = rel.rpartition(".")[0]
        for r in ix.refs:
            if r.role != "head" or r.scope not in scopes:
                continue
            if rules is not None and r.rule not in rules:
                continue
            for prefix in prefixes.get(r.scope, []):
                if not full(prefix, r.atom).startswith(inst + "."):
                    continue
                out |= {full(prefix, b.atom) for b in by_rule[r.rule]
                        if b.role != "head"}
        if out and not deep:
            return out
        chain = set(ix.chain(comp_of[inst])) if inst in comp_of else set()
        for k in backward.get(key, set()):
            if k[0] in chain:
                out.add(f"{inst}.{k[1]}")
                continue
            subs = [p for p, c in comp_of.items()
                    if p.startswith(inst + ".") and k[0] in set(ix.chain(c))]
            out |= {f"{p}.{k[1]}" for p in subs} or {k[1]}
        return out

    return {rel: bodies(rel) for rel in keys}


def _inherited(bodies: dict[str, set[str]], ix: Index, found: list[Found],
               reading: set[str]) -> list[Found]:
    """The findings left once the ones that inherit their constancy are
    out: a relation every body relation of which is constant states
    nothing of its own. A Params relation counts as constant, an inline lib
    relation is neutral, and `in` is not constant."""

    def body_constant(name: str) -> bool | None:
        if name == "in":
            return False
        if name.startswith("params.") or name in reading:
            return True
        decl = ix.decls.get(TOP, {}).get(name) if "." not in name else None
        if decl is not None and "inline" in decl.qualifiers:
            return None
        return False

    return [f for f in found
            if any(body_constant(n) is False
                   for n in bodies.get(f.rel, {"in"}))]


def _case_members(label: str) -> set[str]:
    return set(label.split(", "))


def _shares_case(a: set[str], b: set[str], universes: list) -> bool:
    """Whether two findings can stand in one case: no choice type has them
    on different branches. A finding under no marker runs on every case."""
    for whole in universes:
        pa, pb = a & whole, b & whole
        if pa and pb and not pa & pb:
            return False
    return True


def _ancestors(rel: str, bodies: dict[str, set[str]]) -> set[str]:
    """Every relation the relation derives from, `in` aside. The walk goes
    through a relation the report does not name, so a chain holds across
    one."""
    seen: set[str] = set()
    work = list(bodies.get(rel, ()))
    while work:
        name = work.pop()
        if name in seen or name == "in" or name == rel:
            continue
        seen.add(name)
        work += list(bodies.get(name, ()))
    return seen


def _concept_rules(ix: Index, branches: set[str],
                   concept: set[str]) -> set[int]:
    """The rules the concept case runs: the ones under no branch marker,
    and the ones under a marker of a concept branch."""
    out: set[int] = set()
    for i, info in enumerate(ix.rules):
        marked = ({c.lstrip("$") for c in marker_cases(info.section)}
                  & branches if info.section else set())
        if not marked or marked & concept:
            out.add(i)
    return out


def concept_reads(source: str) -> set[str]:
    """The Params parameters the concept case reads: the ones a rule it
    runs reads, and the ones a relation it reads derives from. A solver
    with no choice point runs one case, which reads every parameter."""
    expanded = expand_macros(source)
    params = set(fact_params(expanded, _lib_defines()))
    try:
        ix = _index(expanded)
    except ParseError:
        return params
    branches, concept, _universes = _branch_names(
        source, ix, _case_types(ix))
    if not branches:
        return params
    bodies = _body_map(ix, _solver_scopes(expanded), deep=True,
                       rules=_concept_rules(ix, branches, concept))
    read = _ancestors("out", bodies)
    holder = next((name for name, init in ix.inits.get(TOP, {}).items()
                   if init.comp == "Params"), "params")
    return {p for p in params if f"{holder}.{p}" in read or p in read}


def _fold(found: list[Found], bodies: dict[str, set[str]],
          universes: list) -> None:
    """Fold each shown relation that stands downstream of another shown one
    under it. The upstream relation states the value; the rest restate it
    one step along."""
    cases: dict[str, set[str]] = {}
    for f in found:
        cases.setdefault(f.rel, set()).update(_case_members(f.case))
    shown = set(cases)
    above = {
        rel: sorted(a for a in _ancestors(rel, bodies) & shown
                    if _shares_case(cases[rel], cases[a], universes))
        for rel in shown
    }
    sources = {rel for rel, ups in above.items() if not ups}
    weight = {rel: sum(rel in ups for ups in above.values()) for rel in shown}
    under: dict[str, list[str]] = {}
    for rel, ups in sorted(above.items()):
        if not ups:
            continue
        roots = sorted((a for a in ups if a in sources),
                       key=lambda a: (-weight[a], a))
        src = roots[0] if roots else None
        if src is None:      # a cycle: its members answer for one another
            src = sorted({*ups, rel})[0]
            if src == rel:
                sources.add(rel)
                continue
        under.setdefault(src, []).append(rel)
    for f in found:
        f.folded = f.rel not in sources
    for src, rels in under.items():
        first = next((f for f in found if f.rel == src), None)
        if first is not None:
            first.under = sorted(set(rels))


def _merge(found: list[Found]) -> list[Found]:
    """One entry per finding, with the cases that give the same value on one
    line."""
    out: list[Found] = []
    by_sig: dict[tuple, Found] = {}
    for f in found:
        sig = (f.rel, tuple(f.cols), f.kind, f.ref)
        held = by_sig.get(sig)
        if held is None:
            by_sig[sig] = f
            out.append(f)
            continue
        cases = set(held.case.split(", ")) | set(f.case.split(", "))
        held.case = ", ".join(sorted(cases))
        held.concept = held.concept or f.concept
    return out


def _attach_witnesses(stem, source, path, task, cands, pending,
                      projection) -> None:
    """Give each owned finding the first grid on which its value differs:
    a D4 image of a train input, then a color swap of one. A grid the
    relation stands empty on holds no value, and it is the witness where
    the concept case and the stored case give different outputs there, or
    one of them is defined and the other is not."""
    wanted = [(f, args) for f, args in pending if f.kind == OWNED
              and not f.colors and f.read and not f.folded]
    if not wanted:
        return
    names = sorted({f.rel for f, _ in wanted})
    built = _build(source, names)
    held = _stored_colors(expand_macros(source), _lib_defines())
    trains = [ex.input for ex in task.train]
    batches: list[list[tuple[str, str, list[list[int]]]]] = []
    for i, grid in enumerate(trains):
        batches.append([(f"train {i}", D4_NAMES[d], g)
                        for d, g in _d4_images(grid).items()])
    batches.append(_swaps(trains, held))
    concept = concept_case(source)
    resolution = res_out_stem(stem)
    outcomes: dict[int, object] = {}
    programs: dict[int, str | None] = {}

    def at_concept(grid):
        key = id(grid)
        if key not in outcomes:
            outcomes[key] = _concept_outcome(source, grid, path, concept,
                                             resolution)
        return outcomes[key]

    def diverges(f, grid) -> bool:
        """The concept case and the stored case give different outputs on
        the grid, or one of them is defined and the other is not."""
        if id(f) not in programs:
            programs[id(f)] = _case_program(source, f)
        stored = programs[id(f)]
        if stored is None:
            return False
        return at_concept(grid) != _case_outcome(stored, grid, path, concept,
                                                 resolution)

    for batch in batches:
        left = [(f, args) for f, args in wanted if f.move is None]
        if not left:
            return
        if not batch:
            continue
        got = _run_all(built, [g for _l, _c, g in batch], names)
        if got is None:
            continue
        for (label, change, grid), g in zip(batch, got):
            for f, args in left:
                if f.move is not None:
                    continue
                value = projection(g, *args)
                if value == f.ref:
                    continue
                if value is None and not diverges(f, grid):
                    continue
                f.move = Move(label, change, at_concept(grid) == grid)


def _stored_colors(source: str, defines: dict[str, int]) -> set[int]:
    """Every color a Params fact names."""
    return {
        v
        for types, stored in fact_params(source, defines).values()
        for row in stored
        for v, t in zip(row, types) if t == COLOR_TYPE
    }


def _attach_lines(source: str, found: list[Found]) -> None:
    """Give each finding the `@store` line that stands on its relation."""
    spelled = [(rel, block) for block in store_blocks(source)
               if (rel := store_relation(source, block))]
    for f in found:
        f.line = next((b for rel, b in spelled if _names(rel, f.rel)), None)


def _findings(source: str, stem: str, found: list[Found], cands: dict,
              differs: dict[str, str]) -> list[Finding]:
    """The findings the audit prints."""
    _path, task_id = solver_file(stem)
    ids = {e.id for e in (load_witnesses(task_id) or Witness(task_id)).entries}
    out: list[Finding] = []
    owned = {f.rel: f for f in found if f.kind == OWNED and f.read}
    unread = {f.rel for f in found if f.kind == OWNED and not f.read}
    held_back = {f.rel: f for f in found if f.kind != OWNED}
    for block in store_blocks(source):
        rel = store_relation(source, block)
        where = f"line {block.line}"
        if not rel:
            out.append(Finding(where, mctx(
                "`@store` stands above no `.decl` or `.init`")))
            continue
        f = next((v for k, v in owned.items() if _names(rel, k)), None)
        if f is None:
            out.append(Finding(where, _no_finding(rel, cands, unread,
                                                  held_back, differs)))
            continue
        needs = (block.verdict == OTHER
                 or (f.move is None and f.case_id not in ids))
        if needs and f.case_id not in ids:
            out.append(Finding(where, mctx(
                "the case needs an entry `{case}`").format(case=f.case_id)))
    for f in found:
        if (f.kind == OWNED and f.read and f.concept and not f.colors
                and f.line is None and not f.folded):
            out.append(Finding(f.rel, mctx(
                "one value on every input and no `@store` or "
                "`@ignore: store` line")))
        if f.case_id in ids:
            f.entry = f.case_id
    return out


def _no_finding(rel: str, cands: dict, unread: set[str],
                held_back: dict[str, Found],
                differs: dict[str, str]) -> str:
    """What the audit says of a `@store` line that stands on no owned
    finding of a relation the concept case reads."""
    if rel not in cands:
        return mctx("`{rel}` is no program relation between `in` and `out`"
                    ).format(rel=rel)
    if rel in unread:
        return mctx("`{rel}` is no relation the concept case reads").format(
            rel=rel)
    f = next((v for k, v in held_back.items() if _names(rel, k)), None)
    if f is not None:
        return mctx("`{rel}` {why}").format(rel=rel, why=_no_case(f))
    grid = differs.get(rel, "")
    if grid:
        return mctx("`{rel}` gives another value on {grid}").format(
            rel=rel, grid=grid)
    return mctx("`{rel}` gives no value the runner can store").format(
        rel=rel)


# --- rendering --------------------------------------------------------

def _enum_name(type_: str, value: str) -> str:
    """An orientation value under the name the lib gives it."""
    if type_ not in FULL:
        return value
    return _orientation()[0].get(value, value)


def _cells(f: Found) -> list[tuple[int, int]] | None:
    """The cells the value draws, and None when it draws no picture."""
    if len(f.cols) != 1 or f.types[0] not in POS_TYPES or len(f.ref) != 1:
        return None
    one = next(iter(f.ref))
    if f.kind == TRANSLATED:
        return sorted(m[0] for m in one)
    return sorted(_point(m[0]) for m in one)


def _colored(f: Found) -> dict[tuple[int, int], int] | None:
    """The colored cells the value draws, and None when it draws none."""
    if len(f.cols) != 2 or len(f.ref) != 1:
        return None
    pos = [i for i, t in enumerate(f.types) if t in POS_TYPES]
    col = [i for i, t in enumerate(f.types) if t == COLOR_TYPE]
    if len(pos) != 1 or len(col) != 1:
        return None
    one = next(iter(f.ref))
    if f.kind == TRANSLATED:
        return {m[pos[0]]: int(m[col[0]]) for m in one}
    return {_point(m[pos[0]]): int(m[col[0]]) for m in one}


def _offsets(f: Found) -> list[tuple[int, int]] | None:
    """The offsets the value stamps, and None when it stamps none."""
    if len(f.cols) != 1 or f.types[0] != OFFSET_TYPE or len(f.ref) != 1:
        return None
    return sorted(_point(m[0]) for m in next(iter(f.ref)))


def _picture(marks: dict[tuple[int, int], str]) -> list[str]:
    """A cell map drawn as a grid, one row per line. A map of one cell, and
    one that reaches past the draw cap along either axis, draws nothing: a
    record standing alone is a value, not a picture."""
    if len(marks) < 2:
        return []
    ts = [t for t, _l in marks]
    ls = [l for _t, l in marks]
    if (max(ts) - min(ts) >= DRAW_CAP) or (max(ls) - min(ls) >= DRAW_CAP):
        return []
    return [" ".join(marks.get((t, l), ".")
                     for l in range(min(ls), max(ls) + 1))
            for t in range(min(ts), max(ts) + 1)]


def _drawn(f: Found) -> list[str]:
    """The value's picture, and no line where it draws none."""
    if f.rect:
        return [mctx("{rect} rectangle").format(rect=f.rect)]
    cells = _cells(f)
    if cells is not None:
        return _picture({p: "#" for p in cells})
    colored = _colored(f)
    if colored is not None:
        return _picture({p: str(c) for p, c in colored.items()})
    offsets = _offsets(f)
    if offsets is not None:
        marks = {p: "#" for p in offsets}
        marks[(0, 0)] = "@"
        return _picture(marks)
    return []


def _inline(f: Found) -> str:
    """The value as one phrase, for a value that draws no picture."""
    one = next(iter(f.ref))
    return ", ".join(
        _enum_name(f.types[0], m[0]) if len(m) == 1
        else "(" + ", ".join(_enum_name(f.types[i], v)
                             for i, v in enumerate(m)) + ")"
        for m in sorted(one))


def _noun(f: Found) -> str:
    if _cells(f) is not None or _colored(f) is not None or f.rect:
        return mctx("cell set")
    if _offsets(f) is not None:
        return mctx("offset set")
    return mctx("value")


def _headline(f: Found) -> str:
    """The finding's first line."""
    name = f"{f.rel}[{', '.join(f.cols)}]" if f.sub else f.rel
    if f.line is not None and f.kind == OWNED:
        return mctx("{name}: @store at line {line}").format(
            name=name, line=f.line.line)
    if f.kind == CONSTANT:
        keys = ", ".join(f"`{k}`" for k in f.keys) or mctx("the key")
        return mctx("{name}: {n} {noun}s, one per {keys}").format(
            name=name, n=len(f.ref), noun=_noun(f), keys=keys)
    if f.kind == TRANSLATED:
        return mctx("{name}: one {noun} up to translation on every input"
                    ).format(name=name, noun=_noun(f))
    if f.colors:
        value = _inline(f)
        return mctx("{name}: one color on every input: {value}; store it in "
                    "Params").format(name=name, value=value)
    if _drawn(f):
        return (mctx("{name}: one {noun} on every input").format(
            name=name, noun=_noun(f)) + _in_case(f))
    members = len(next(iter(f.ref)))
    if members > SHOWN_MEMBERS:
        return (mctx("{name}: one value set of {n} members on every input"
                     ).format(name=name, n=members) + _in_case(f))
    return (mctx("{name}: one value on every input: {value}").format(
        name=name, value=_inline(f)) + _in_case(f))


def _in_case(f: Found) -> str:
    """The case a relation the concept case neither reads nor feeds stands
    under."""
    if f.read or not f.used_in:
        return ""
    return mctx("; in case `{case}`").format(case=f.used_in)


def _witness_line(f: Found) -> str:
    if f.entry:
        return mctx("witness: entry {case}").format(case=f.case_id)
    if f.move is None:
        return mctx("no witness: every D4 element and every swap keeps the "
                    "value; the case needs an entry `{case}`").format(
            case=f.case_id)
    line = mctx("witness: {grid} {change}").format(grid=f.move.grid,
                                                   change=f.move.change)
    if f.move.identity:
        line += mctx("; the concept case gives the input unchanged")
    return line


def _named(rel: str) -> str:
    """The name a directive above the instance's `.init` gives the relation:
    its path inside the instance, and nothing for a top-level relation."""
    _root, _dot, path = rel.partition(".")
    return f" {path}" if path else ""


def store_hint(rel: str) -> str:
    """The line the session adds at the relation's site: the bare form above
    a top-level `.decl`, and the named form above an instance's `.init`."""
    return f"add: // @store{_named(rel)}: <plausibility> <verdict>"


def _no_case(f: Found) -> str:
    """Why the runner holds no case for a value that is not the same on
    every input: it stores a value as it stands, with no anchor to place
    it by and no id to key it by."""
    if f.kind == TRANSLATED:
        return mctx("stands at another place on each input, and the runner "
                    "picks no anchor")
    keys = ", ".join(f"`{k}`" for k in f.keys)
    return mctx("varies by {keys}, an id the runner stores nothing under"
                ).format(keys=keys)


def ignore_hint(rel: str) -> str:
    """The line the session adds instead when it judges the stored model
    no case, at the same site and in the same two forms."""
    return f"or:  // @ignore{_named(rel)}: store — <reason>"


def _rank(f: Found) -> tuple:
    return (not f.concept, not f.read, f.kind != OWNED, f.rel, tuple(f.cols))


def render_store(report: Report) -> list[str]:
    """The `store` command's output: one block per finding."""
    if report.error:
        return [report.error]
    lines: list[str] = []
    for f in sorted([f for f in report.found if not f.folded], key=_rank):
        lines.append(_headline(f))
        if (f.kind == OWNED and f.line is None and not f.colors and f.read):
            lines += ["  " + ln for ln in _drawn(f)]
            lines.append("  " + _witness_line(f))
            lines.append("  " + store_hint(f.rel))
            lines.append("  " + ignore_hint(f.rel))
        elif f.kind == OWNED and f.line is not None and f.read:
            # The witness the line's plausibility and verdict judge.
            lines.append("  " + _witness_line(f))
        elif f.kind != OWNED:
            lines += ["  " + ln for ln in _drawn(f)]
            lines.append("  " + mctx("no case: the value {why}").format(
                why=_no_case(f)))
        if f.under:
            lines.append("  " + mctx("with it: {rels}").format(
                rels=", ".join(f.under)))
    if report.skipped:
        lines.append(mctx("not checked: {rels}").format(
            rels=", ".join(f"`{n}`" for n in report.skipped)))
    return lines or [mctx("no findings")]


def render_findings(report: Report) -> list[str]:
    """The audit's section: one line per finding, and `store: ok` when none
    stands."""
    if report.error:
        return [report.error]
    return [f"{f.where}: {f.text}" for f in report.findings] or [STORE_OK]
