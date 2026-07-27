"""Probe the proposers against a solver's stored fills."""

import re
import tempfile
from pathlib import Path

from arc.task import load as load_task
from dl.domains import (
    ENUM_TYPES,
    POSITION_TYPES,
    _color_domain,
    _enum_domain,
    _lib_defines,
    _number_domain,
)
from dl.facts import _parse_relations, _parse_value, train_facts
from dl.paths import PROPOSERS_SRC, SOLVERS_DIR
from dl.souffle import _run_source
from dl.source import (
    COMP_HEADER_RE,
    _comp_span,
    _slot_facts,
    _split_args,
    comp_decls,
    expand_grid_macros,
)


def proposer_decls() -> dict[str, list[str]]:
    """Map proposer comp name -> propose argument types.

    A comp without a propose relation is a helper, not a proposer.
    """
    source = PROPOSERS_SRC.read_text()
    names = [
        m.group(1)
        for line in source.splitlines()
        if (m := COMP_HEADER_RE.search(line.split("//")[0]))
    ]
    decls = {n: comp_decls(source, n) for n in names}
    return {n: d["propose"] for n, d in decls.items() if "propose" in d}


def build_probe_source() -> str:
    """Assemble the proposer probe: every proposer inited, propose relayed."""
    lines = ['#include "../lib.dl"', '#include "../proposers.dl"',
             ".input train_in", ".input train_out"]
    for name, types in sorted(proposer_decls().items()):
        inst = name.lower()
        args = ", ".join(f"A{i}" for i in range(len(types)))
        typed = ", ".join(f"a{i}: {t}" for i, t in enumerate(types))
        lines += [
            f".init {inst} = {name}",
            f".decl propose_{name}({typed})",
            f"propose_{name}({args}) :- {inst}.propose({args}).",
            f".output propose_{name}(IO=stdout)",
        ]
    return "\n".join(lines) + "\n"


def run_propose(task) -> dict[str, set[tuple]]:
    """Run the probe on a task's train pairs: proposer -> candidate set."""
    with tempfile.TemporaryDirectory() as facts_dir:
        for name, text in train_facts(task).items():
            (Path(facts_dir) / name).write_text(text)
        stdout = _run_source(build_probe_source(), "", ["-F", facts_dir])
    return {
        name.removeprefix("propose_"): {
            tuple(_parse_value(x) for x in row.split("\t")) for row in rows
        }
        for name, rows in _parse_relations(stdout).items()
    }


def propose_report(stem: str) -> list[tuple[str, dict[str, str]]]:
    """Compare each Color/number slot's stored fill with each proposer of
    the slot's value type.

    Returns (slot, {proposer: verdict}): 'pinned' — candidate set equals
    the stored set; 'narrowed(n)' — stored inside a set of n smaller than
    the enumeration domain; 'open' — stored inside a set no smaller than
    the domain; 'missed' — stored outside the set.
    """
    source = expand_grid_macros((SOLVERS_DIR / f"{stem}.dl").read_text())
    task = load_task(stem.split("_", 1)[0])
    defines = _lib_defines()
    s, e = _comp_span(source, "Consts")
    consts_text = "\n".join(source.splitlines()[s:e])
    domains = {
        "Color": len(_color_domain(task)),
        "number": len(_number_domain(task)),
        **{t: len(_enum_domain(t, defines)) for t in ENUM_TYPES},
    }
    ptypes = proposer_decls()
    proposals = run_propose(task)

    def stored_value(a: str, t: str):
        if t in POSITION_TYPES:
            return tuple(int(x) for x in _split_args(a[1:-1]))
        return int(a) if a.lstrip("-").isdigit() else defines[a]

    supported = set(ENUM_TYPES) | POSITION_TYPES | {"Color", "number"}
    results = []
    for slot, types in comp_decls(source, "Consts").items():
        if not types or any(t not in supported for t in types):
            continue
        if re.search(rf"\b{slot}\s*\([^)]*\)\s*:-", consts_text):
            continue
        stored = {
            tuple(stored_value(a, t) for a, t in zip(args, types))
            for args in _slot_facts(source, slot)
        }
        if not stored:
            continue
        verdicts = {}
        for name, cand in sorted(proposals.items()):
            if ptypes[name] != types:
                continue
            if len(types) == 1:
                # Single-column: cand is a set of rival candidates.
                if not stored <= cand:
                    verdicts[name] = "missed"
                elif cand == stored:
                    verdicts[name] = "pinned"
                elif len(cand) < domains[types[0]]:
                    verdicts[name] = f"narrowed({len(cand)})"
                else:
                    verdicts[name] = "open"
            else:
                verdicts[name] = _table_verdict(cand, stored)
        results.append((slot, verdicts))

    combo = _combine_triples(source)
    if combo is not None and "PanelCombine" in proposals:
        results.append((
            "combine_member+combine_out",
            {"PanelCombine": _table_verdict(proposals["PanelCombine"], combo)},
        ))
    return results


def _table_verdict(cand: set, stored: set) -> str:
    """A multi-column proposal is one table, compared whole."""
    if cand == stored:
        return "exact"
    if not cand:
        return "empty"
    if stored < cand:
        return f"superset(+{len(cand - stored)})"
    if cand & stored:
        return "partial"
    return "missed"


def _combine_triples(source: str) -> set[tuple] | None:
    """The 2-panel combine table as (c_first, c_second, c_out) triples,
    id-invariant; None when the solver has no such table."""
    members = _slot_facts(source, "combine_member")
    outs = {a[0]: int(a[1]) for a in _slot_facts(source, "combine_out")}
    if not members or not outs:
        return None
    by_id: dict[str, list] = {}
    for id_, pos, col in members:
        t, _, l, _ = (int(x) for x in _split_args(pos[1:-1]))
        by_id.setdefault(id_, []).append(((t, l), int(col)))
    triples = set()
    for id_, cells in by_id.items():
        if id_ not in outs or len(cells) != 2:
            return None
        cells.sort()
        triples.add((cells[0][1], cells[1][1], outs[id_]))
    return triples


def render_propose(results: list[tuple[str, dict[str, str]]]) -> list[str]:
    lines = []
    for slot, verdicts in results:
        marks = ", ".join(f"{n} {v}" for n, v in verdicts.items())
        lines.append(f"{slot}: {marks}")
    return lines
