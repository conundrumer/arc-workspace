"""The determination plan: which Params parameters need determination
relations, from the proposer probe.

In conventional terms, the values consistent with the examples are a
parameter's version space. A proposer restricts the space that settling
searches: an exact parameter is point-identified by its proposer, a narrowed
parameter set-identified, and settling enumerates the rest under the
enumeration limit.
"""

import itertools
import math
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from arc.task import load as load_task
from controlled_markdown import mctx
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
from dl.lint import NUMERIC_LITERAL_RE, SINGLETON_AXIS_MARKER, exempt_literal
from dl.paths import PROPOSERS_SRC
from dl.solve import _profile, solver_file
from dl.souffle import _pool_workers, _run_source
from dl.source import (
    COMP_HEADER_RE,
    _comp_span,
    _param_facts,
    _render_arg,
    _split_args,
    comp_decls,
    determined_params,
    expand_macros,
    public_param,
    swap_fact,
)
from dl.sweep import param_domains, stored_rows


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
# parameters by verification; over it, parameters must move under
# determination — the session's choice which — until the rest go under.
ENUMERATION_LIMIT = 100

# Every sentence the plan prints, keyed by the part it heads. A slot,
# `{name}`, is filled by the render.
MESSAGES = mctx({
        "none": "no actions",
        "determine": "write a determination relation",
        "open": "the train pairs leave several values, so record the surviving "
                "values as the parameter's open values",
        "over": "over the enumeration limit ({joint} > {limit})",
        # Printed once under the over-the-limit section when some listed count is
        # a Position parameter's enumerable domain.
        "position-domain": "  A Position parameter's candidates are the cells of "
                           "the frame its stored value implies, so its count "
                           "follows the frame the parse produces.",
        "determined": "determined",
        "covered": "the value is covered on this task's examples, so no "
                   "determination relation is needed",
        "joint": "{survived} of {tried} joint assignments of the enumerated "
                 "parameters reproduce every train pair",
        "embedded": "move data from clauses to fact parameters",
        "verdicts": "each proposer's verdict on each parameter:",
})


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
    path, task_id = solver_file(stem)
    source = expand_macros(path.read_text())
    task = load_task(task_id)
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
                not exempt_literal(m.group(0), singleton_axis)
                for text, singleton_axis in rules
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
    `SINGLETON_AXIS_MARKER`); empty for fact parameters."""
    rules = []
    cur: list[str] = []
    singleton_axis = False
    in_rule = False
    for line in params_text.splitlines():
        code, _, comment = line.partition("//")
        if not in_rule and re.search(rf"\b{param}\s*\([^)]*\)\s*:-", code):
            in_rule = True
        if in_rule:
            cur.append(code)
            singleton_axis = singleton_axis or SINGLETON_AXIS_MARKER in comment
            if code.rstrip().endswith("."):
                rules.append(("\n".join(cur), singleton_axis))
                cur, singleton_axis, in_rule = [], False, False
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


type Survivors = tuple[int, int, dict[str, list[str]]]

# A covering verdict and the size of the candidate set it leaves.
COUNT_RE = re.compile(r"(?:narrowed|enumerable)\((\d+)\)")


def covering_verdict(verdicts: dict[str, str]) -> tuple[str, str] | None:
    """The verdict that covers the parameter's value, as (key, verdict): the
    proposer that reads it exactly, or the smallest candidate set. None when
    no verdict covers the value."""
    best: tuple[int, str, str] | None = None
    for key, verdict in verdicts.items():
        if verdict == "exact":
            rank = 0
        elif m := COUNT_RE.fullmatch(verdict):
            rank = int(m.group(1))
        else:
            continue
        if best is None or rank < best[0]:
            best = (rank, key, verdict)
    return None if best is None else best[1:]


def survivor_verdict(values: list[str]) -> str:
    """The verdict a settling parameter's surviving values carry:
    'pairs-exact' when the train pairs leave one value, 'pairs-ambiguous(n)'
    when they leave n."""
    return ("pairs-exact" if len(values) == 1
            else f"pairs-ambiguous({len(values)})")


def settle_survivors(
    stem: str,
    report: tuple[list[tuple[str, dict[str, str]]], list[str], set[str]],
) -> Survivors | None:
    """Enumerate the settling parameters jointly and keep the assignments
    that reproduce every train pair, as a produce run does.

    A parameter whose covering verdict is its own value domain carries a
    candidate set the plan knows, so the enumeration ranges over those
    parameters; a parameter a proposer narrows holds its stored value,
    since the plan keeps the narrowed set's size rather than the set.

    Returns (assignments, surviving, values): the assignments run, how many
    of them reproduce every train pair, and each enumerated parameter's
    surviving values, rendered. None when no parameter settles, when the
    joint product is over ENUMERATION_LIMIT, or when the stored values fail
    the
    train pairs.
    """
    results, _embedded, determined = report
    _determine, settle, _done, _exact = determination_plan(results, determined)
    if not settle or math.prod(n for _, n in settle) > ENUMERATION_LIMIT:
        return None
    verdicts_by_param = dict(results)
    path, task_id = solver_file(stem)
    source = expand_macros(path.read_text())
    task = load_task(task_id)
    defines = _lib_defines()
    names = {v: k for k, v in defines.items()}
    settling = {param for param, _ in settle}

    enumerated: list[tuple[str, list[str], list[tuple]]] = []
    for param, types in comp_decls(source, "Params").items():
        public = public_param(param)
        if public not in settling:
            continue
        covering = covering_verdict(verdicts_by_param.get(public, {}))
        if covering is None or covering[0] not in ("domain", "position-domain"):
            continue
        stored = stored_rows(_param_facts(source, param), types, defines)
        domains = param_domains(types, stored, task, defines)
        candidates = sorted(set(itertools.product(*domains)) | set(stored))
        enumerated.append((param, types, candidates))
    if not enumerated:
        return None

    assignments = list(itertools.product(*(c for _, _, c in enumerated)))
    if len(assignments) > ENUMERATION_LIMIT:
        return None
    reference = _profile(source, task.train)
    if reference is None:
        return None

    def test(assignment: tuple) -> bool:
        mod = source
        for (param, _types, _cands), vals in zip(enumerated, assignment):
            mod = swap_fact(mod, param, vals)
        return _profile(mod, task.train) == reference

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        fits = list(executor.map(test, assignments))
    surviving = [a for a, ok in zip(assignments, fits) if ok]

    def show(vals: tuple, types: list[str]) -> str:
        return "(" + ", ".join(
            names.get(v, str(v)) if t in ENUM_TYPES else _render_arg(v)
            for v, t in zip(vals, types)
        ) + ")"

    values = {
        public_param(param): [
            show(v, types) for v in sorted({a[i] for a in surviving})
        ]
        for i, (param, types, _cands) in enumerate(enumerated)
    }
    return len(assignments), len(surviving), values


def determination_plan(
    results: list[tuple[str, dict[str, str]]],
    determined: set[str] = frozenset(),
) -> tuple[list[str], list[tuple[str, int]], list[str], list[str]]:
    """Classify parameters: (determine, settle, done, exact).

    A parameter is exact when some proposer reads it off exactly; it settles
    when a candidate set — a proposer's narrowed set or the parameter's own
    value domain — gives a produce run something to enumerate; it needs a
    determination relation when it has neither. Settling is bounded: when the
    joint product of the candidate counts is over ENUMERATION_LIMIT, some
    parameters must move under determination — which ones is the session's
    choice — until the rest go under. Parameters in `determined` already carry a determination
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
            if (m := COUNT_RE.fullmatch(v))
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
    survivors: Survivors | None = None,
    verdicts: bool = False,
) -> list[str]:
    """The plan's sections. `survivors` is the joint enumeration of the
    settling parameters (see settle_survivors); it puts each enumerated
    parameter's verdict on its covered line, under a line stating how many
    assignments the train pairs admit. `verdicts` appends each proposer's
    verdict on each parameter."""
    results, embedded, determined = report
    tried, survived, surviving = survivors or (0, 0, {})
    determine, settle, done, exact = determination_plan(results, determined)
    joint = math.prod(n for _, n in settle)
    over = joint > ENUMERATION_LIMIT
    covered = sorted(exact + ([] if over else [param for param, _ in settle]))
    verdicts_by_param = dict(results)
    lines: list[str] = []

    def section(header: str, params: list[str], note: str = "") -> None:
        if not params:
            return
        if lines:
            lines.append("")
        lines.append(f"{header}:")
        if note:
            lines.append(note)
        lines.extend(f"  {param}" for param in params)

    def covered_line(param: str) -> str:
        """The parameter with the verdict that covers its value: the
        proposer that reads it exactly, or the smallest candidate set."""
        best = covering_verdict(verdicts_by_param.get(param, {}))
        if best is None:
            # A paired-table row carries the verdict of each of its parts.
            for row, vs in results:
                if "+" in row and param in row.split("+"):
                    for name, verdict in vs.items():
                        if verdict == "exact":
                            best = (name, verdict)
        if best is None:
            return param
        note = f"{best[0]} {best[1]}"
        if param in surviving:
            values = surviving[param]
            note += f", {survivor_verdict(values)}: {', '.join(values)}"
        return f"{param} ({note})"

    open_valued = [param for param in sorted(surviving)
                   if len(surviving[param]) > 1]
    if not determine and not over and not embedded and not open_valued:
        lines.append(MESSAGES["none"])
    section(MESSAGES["determine"], determine)
    section(
        MESSAGES["open"],
        [f"{param} ({', '.join(surviving[param])})" for param in open_valued],
    )
    if over:
        section(
            MESSAGES["over"].format(joint=joint, limit=ENUMERATION_LIMIT),
            [f"{param}({n})" for param, n in settle],
        )
        position_domain = {
            param: vs.get("position-domain") for param, vs in results
        }
        if any(position_domain.get(p) == f"enumerable({n})" for p, n in settle):
            lines.append(MESSAGES["position-domain"])
    section(MESSAGES["determined"], done)
    section(MESSAGES["covered"], [covered_line(param) for param in covered])
    if surviving:
        lines.append(
            MESSAGES["joint"].format(survived=survived, tried=tried))
    section(MESSAGES["embedded"], embedded)

    if verdicts:
        detail = [
            f"{param}: " + ", ".join(f"{n} {v}" for n, v in vs.items())
            for param, vs in results
            if vs
        ]
        if detail:
            lines += ["", MESSAGES["verdicts"]]
            lines += [f"  {line}" for line in detail]
    return lines
