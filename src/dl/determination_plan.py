"""The determination plan: which Params parameters need determination
relations, from the proposer probe.

In conventional terms, the values consistent with the examples are a
parameter's version space. A proposer restricts the space that settling
searches: an exact parameter is point-identified by its proposer, a narrowed
parameter set-identified, and settling enumerates the rest under the budget.
"""

import math
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
    _position_domain,
)
from dl.facts import _parse_relations, _parse_value, example_facts
from dl.lint import NUMERIC_LITERAL_RE, UNIT_MARKER, exempt_literal
from dl.paths import PROPOSERS_SRC, SOLVERS_DIR
from dl.solve import task_id_of
from dl.souffle import _run_source
from dl.source import (
    COMP_HEADER_RE,
    _comp_span,
    _param_facts,
    _split_args,
    comp_decls,
    determined_params,
    expand_macros,
    public_param,
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
             ".input ex_in", ".input ex_out"]
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


def run_probe(task) -> dict[str, set[tuple]]:
    """Run the probe on a task's examples: proposer -> candidate set."""
    with tempfile.TemporaryDirectory() as facts_dir:
        for name, text in example_facts(task).items():
            (Path(facts_dir) / name).write_text(text)
        stdout = _run_source(build_probe_source(), "", ["-F", facts_dir])
    return {
        name.removeprefix("propose_"): {
            tuple(_parse_value(x) for x in row.split("\t")) for row in rows
        }
        for name, rows in _parse_relations(stdout).items()
    }


# Joint candidate product a produce run may enumerate to settle narrowed
# parameters by verification; over it, settling parameters must move under
# determination — the session's choice which — until the rest go under.
JOINT_BUDGET = 100

# Printed once under the over-budget section when some listed count is a
# Position parameter's enumerable domain.
POSITION_DOMAIN_NOTE = (
    "A Position parameter's candidates are the cells of the frame its stored "
    "value implies, so its count follows the frame the parse produces."
)


def probe_report(
    stem: str,
) -> tuple[list[tuple[str, dict[str, str]]], list[str], set[str]]:
    """Compare each fact parameter's stored value with each proposer of the
    parameter's value type. Parameters outside the probe's types carry no
    verdicts.

    Returns (results, embedded, determined). determined names the parameters
    whose determination relation already exists. results is
    (parameter, {proposer: verdict}):
    'exact' — candidate set equals the stored set; 'narrowed(n)' — stored
    inside a set smaller than the enumeration domain, n its candidate
    count (for a multi-fact parameter, the non-empty subsets, since a set
    value applies whole); 'open' — stored inside a set no smaller than the
    domain; 'missed' — stored outside the set. A single-fact parameter also carries a 'domain' entry, 'enumerable(n)':
    the size of its value domain, a proposer-free candidate set. A parameter
    with a Position column carries that entry under 'position-domain'. embedded
    lists rule-derived Params relations whose rules carry literals that
    `exempt_literal` does not exempt.
    """
    source = expand_macros((SOLVERS_DIR / f"{stem}.dl").read_text())
    task = load_task(task_id_of(stem))
    defines = _lib_defines()
    s, e = _comp_span(source, "Params")
    params_text = "\n".join(source.splitlines()[s:e])
    nums = _number_domain(task)
    domains = {
        "Color": len(_color_domain(task)),
        "number": len(nums),
        **{t: len(_enum_domain(t, defines)) for t in ENUM_TYPES},
    }
    ptypes = proposer_decls()
    proposals = run_probe(task)

    def stored_value(a: str, t: str):
        if t in POSITION_TYPES:
            return tuple(int(x) for x in _split_args(a[1:-1]))
        return int(a) if a.lstrip("-").isdigit() else defines[a]

    supported = set(ENUM_TYPES) | POSITION_TYPES | {"Color", "number"}
    results = []
    embedded = []
    for param, types in comp_decls(source, "Params").items():
        if not types:
            continue
        rules = _rules(params_text, param)
        if rules:
            if any(
                not exempt_literal(m.group(0), unit)
                for text, unit in rules
                for m in NUMERIC_LITERAL_RE.finditer(text)
            ):
                embedded.append(param)
            continue
        if not _param_facts(source, param):
            continue
        if any(t not in supported for t in types):
            results.append((public_param(param), {}))
            continue
        stored = {
            tuple(stored_value(a, t) for a, t in zip(args, types))
            for args in _param_facts(source, param)
        }
        verdicts = {}
        for name, cand in sorted(proposals.items()):
            if ptypes[name] != types:
                continue
            if len(types) == 1:
                # Single-column: cand is a set of peer candidates.
                if not stored <= cand:
                    verdicts[name] = "missed"
                elif cand == stored:
                    verdicts[name] = "exact"
                elif len(cand) < domains[types[0]]:
                    # A multi-fact value is a subset of cand applied whole,
                    # so its enumeration ranges over the subsets.
                    n = (len(cand) if len(stored) == 1
                         else 2 ** len(cand) - 1)
                    verdicts[name] = f"narrowed({n})"
                else:
                    verdicts[name] = "open"
            else:
                verdicts[name] = _table_verdict(cand, stored)
        if len(stored) == 1:
            n = 1
            for i, t in enumerate(types):
                if t in POSITION_TYPES:
                    n *= len(_position_domain(t, [s[i] for s in stored], nums))
                else:
                    n *= domains[t]
            key = "position-domain" if "Position" in types else "domain"
            verdicts[key] = f"enumerable({n})"
        results.append((public_param(param), verdicts))

    combo = _combine_triples(source)
    if combo is not None and "PanelCombine" in proposals:
        results.append((
            "combine_member+combine_out",
            {"PanelCombine": _table_verdict(proposals["PanelCombine"], combo)},
        ))
    return results, sorted(embedded), set(determined_params(source) or {})


def _rules(params_text: str, param: str) -> list[tuple[str, bool]]:
    """The parameter's rules, each as (comment-stripped text, carries
    `UNIT_MARKER`); empty for fact parameters."""
    rules = []
    cur: list[str] = []
    unit = False
    in_rule = False
    for line in params_text.splitlines():
        code, _, comment = line.partition("//")
        if not in_rule and re.search(rf"\b{param}\s*\([^)]*\)\s*:-", code):
            in_rule = True
        if in_rule:
            cur.append(code)
            unit = unit or UNIT_MARKER in comment
            if code.rstrip().endswith("."):
                rules.append(("\n".join(cur), unit))
                cur, unit, in_rule = [], False, False
    return rules


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
    members = _param_facts(source, "combine_member")
    outs = {a[0]: int(a[1]) for a in _param_facts(source, "combine_out")}
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


def determination_plan(
    results: list[tuple[str, dict[str, str]]],
    determined: set[str] = frozenset(),
) -> tuple[list[str], list[tuple[str, int]], list[str], list[str]]:
    """Classify parameters: (determine, settle, done, exact).

    A parameter is exact when some proposer reads it off exactly; it settles
    when a candidate set — a proposer's narrowed set or the parameter's own
    value domain — gives a produce run something to enumerate; it needs a
    determination relation when it has neither. Settling is bounded: when the
    settling parameters' joint product is over JOINT_BUDGET, some must move
    under determination — which ones is the session's choice — until the rest
    go under. Parameters in `determined` already carry a determination
    relation; they are done and leave the product. A paired-table row ('a+b')
    makes both parameters exact.
    """
    determine, settle, done, exact = [], [], [], []
    for param, verdicts in results:
        if "+" in param:
            continue
        if param in determined:
            done.append(param)
            continue
        vals = set(verdicts.values())
        if "exact" in vals:
            exact.append(param)
            continue
        ns = [
            int(m.group(1))
            for v in vals
            if (m := re.fullmatch(r"(?:narrowed|enumerable)\((\d+)\)", v))
        ]
        if ns:
            settle.append((param, min(ns)))
        else:
            determine.append(param)
    for param, verdicts in results:
        if "+" in param and set(verdicts.values()) == {"exact"}:
            for part in param.split("+"):
                if part in determine:
                    determine.remove(part)
                    exact.append(part)

    settle.sort(key=lambda sn: (-sn[1], sn[0]))
    return sorted(determine), settle, sorted(done), sorted(exact)


def render_determination_plan(
    report: tuple[list[tuple[str, dict[str, str]]], list[str], set[str]],
) -> list[str]:
    results, embedded, determined = report
    determine, settle, done, exact = determination_plan(results, determined)
    joint = math.prod(n for _, n in settle)
    over = joint > JOINT_BUDGET
    covered = sorted(exact + ([] if over else [param for param, _ in settle]))
    verdicts_by_param = dict(results)
    lines: list[str] = []

    def section(header: str, params: list[str]) -> None:
        if not params:
            return
        if lines:
            lines.append("")
        lines.append(f"{header}:")
        lines.extend(f"  {param}" for param in params)

    def covered_line(param: str) -> str:
        """The parameter with the verdict that covers its value: the
        proposer that reads it exactly, or the smallest candidate set."""
        best: tuple[int, str] | None = None
        for name, verdict in verdicts_by_param.get(param, {}).items():
            if verdict == "exact":
                rank = 0
            elif m := re.fullmatch(r"(?:narrowed|enumerable)\((\d+)\)", verdict):
                rank = int(m.group(1))
            else:
                continue
            if best is None or rank < best[0]:
                best = (rank, f"{name} {verdict}")
        if best is None:
            # A paired-table row carries the verdict of each of its parts.
            for row, verdicts in results:
                if "+" in row and param in row.split("+"):
                    for name, verdict in verdicts.items():
                        if verdict == "exact":
                            best = (0, f"{name} {verdict}")
        return f"{param} ({best[1]})" if best else param

    if not determine and not over and not embedded:
        lines.append("no actions")
    section("write a determination relation", determine)
    if over:
        section(
            f"over the settle budget ({joint} > {JOINT_BUDGET}) — "
            "choose determination relations until the rest go under",
            [f"{param}({n})" for param, n in settle],
        )
        position_domain = {
            param: verdicts.get("position-domain") for param, verdicts in results
        }
        if any(position_domain.get(p) == f"enumerable({n})" for p, n in settle):
            lines.append(POSITION_DOMAIN_NOTE)
    section("determined", done)
    section(
        "a proposer or the parameter's value domain covers the value on "
        "this task's examples — no determination relation needed",
        [covered_line(param) for param in covered],
    )
    section("move data from rules to fact parameters", embedded)

    detail = [
        f"{param}: " + ", ".join(f"{n} {v}" for n, v in verdicts.items())
        for param, verdicts in results
        if verdicts
    ]
    if detail:
        lines += [""] + detail
    return lines
