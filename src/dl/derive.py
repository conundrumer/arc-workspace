"""Derived readings of stored parameters: the cases a proposer states.

A proposer of `programs/proposers.dl` that gives a parameter's stored value
on every input, each input read alone, states a model that derives the value
from the input. That model is a case of the solver, and the runner owns it:
the solver carries one `// @derive` line above the parameter's `.decl`, and
no branch.

The witness tells the derived case from the stored reading. The tool builds
one by swapping the stored color with a color the input does not hold: the
proposer follows the swap, the stored fact does not, and the concept case
gives different outputs at the two values, or is defined at one alone. A
parameter no swap separates takes a hand-built entry of the witness file,
under the id `<param>=<Proposer>`.

The runner holds a case only where the concept case reads the parameter.
A parameter that only another branch reads, through clauses whose head
carries that branch's constructor, has the concept case as its derived
reading, so no case stands apart from it. A
`// @ignore: derive` line above the parameter's `.decl` dismisses the case
the session judges no case.
"""

import re
from dataclasses import dataclass

from arc.task import load as load_task
from controlled_markdown import mctx
from dl.annotations import (
    Derive,
    derive_blocks,
    derive_ignored,
    derive_param,
)
from dl.determination_plan import (
    fact_params,
    per_grid_matches,
    probe_grid,
    proposer_decls,
)
from dl.domains import _lib_defines
from dl.lint import concept_case
from dl.models import case_space
from dl.store import concept_reads
from dl.paths import PROPOSERS_SRC
from dl.solve import res_out_stem, run_dl_source, solver_file
from dl.source import _render_arg, expand_macros, swap_facts
from dl.witness import (
    Entry,
    Outcome,
    Witness,
    _rows,
    assigned_source,
    case_outcomes,
    load_witnesses,
    model_outcomes,
)

DERIVE_OK = "derive: ok"
"""The pass line, printed when no finding stands."""

OTHER = "other"
"""The verdict that takes a judged output, which only an entry holds."""

COMP_RE = re.compile(r"^\.comp\s+(\w+)")

"""The directive that dismisses this check. It stands above the
parameter's `.decl`, and names the parameter declared under it."""


@dataclass
class Swap:
    """The witness the tool builds: on the input `grid` names, the color
    `free` stands in for the color `stored` holds, and `input` is the
    swapped grid. `at_stored` and `at_derived` are what the concept case
    gives on it at the stored value and at the derived value, each None
    where the case is undefined, as a Group's null grid."""

    grid: str
    stored: int
    free: int
    input: list[list[int]]
    at_stored: Outcome
    at_derived: Outcome

    @property
    def identity(self) -> bool:
        """The concept case gives the input unchanged at the stored
        value."""
        return self.at_stored == self.input


@dataclass
class Derivation:
    """One parameter read off the input by one proposer. `line` is the
    solver's `@derive` line where one stands, `entry` the witness file's
    entry of the case's id, and `swap` the witness the tool builds, with
    `reason` in its place where it builds none."""

    param: str
    proposer: str
    comment: str
    line: Derive | None = None
    entry: str = ""
    swap: Swap | None = None
    reason: str = ""
    read: bool = True
    """The concept case reads the parameter. Where it does not, the
    derived reading is the concept case, and the runner holds no case."""
    ignored: bool = False
    """An `@ignore: derive` line dismisses the case."""

    @property
    def case(self) -> str:
        return f"{self.param}={self.proposer}"


@dataclass
class Finding:
    """One finding of the derive report: where it stands, and what it
    says."""

    where: str
    text: str


@dataclass
class Report:
    derivations: list[Derivation]
    findings: list[Finding]


def proposer_comments() -> dict[str, str]:
    """Each proposer's comment, as a phrase: the `//` lines above its
    `.comp` line."""
    lines = PROPOSERS_SRC.read_text().splitlines()
    out: dict[str, str] = {}
    for i, line in enumerate(lines):
        m = COMP_RE.match(line)
        if m is None:
            continue
        block: list[str] = []
        j = i - 1
        while j >= 0 and lines[j].startswith("//"):
            block.insert(0, lines[j][2:].strip())
            j -= 1
        text = " ".join(w for w in block if w).rstrip(".")
        out[m[1]] = text[:1].lower() + text[1:]
    return out


def _swap_grid(grid: list[list[int]], a: int, b: int) -> list[list[int]]:
    return [[b if c == a else a if c == b else c for c in row]
            for row in grid]


def _stored_colors(source: str, defines: dict[str, int]) -> set[int]:
    """Every color a `Params` fact names."""
    return {
        v
        for types, stored in fact_params(source, defines).values()
        for row in stored
        for v, t in zip(row, types) if t == "Color"
    }


def _concept_outcome(source: str, grid: list[list[int]], path,
                     concept: str, resolution: bool) -> Outcome:
    outcomes = case_outcomes(
        run_dl_source(source, grid, solver_path=path), resolution)
    return outcomes.get(concept)


def derived_outcome(stem: str, case_id: str, grid: list[list[int]],
                    source: str | None = None) -> Outcome:
    """What the derived case `case_id`, `<param>=<Proposer>`, gives on one
    grid: the concept case of `source`, the solver's file when omitted, at
    the value the proposer gives on the grid. None when the proposer gives
    no value there."""
    param, _sep, proposer = case_id.partition("=")
    path, _task_id = solver_file(stem)
    if source is None:
        source = path.read_text()
    value = probe_grid(grid).get(proposer, set())
    if not value:
        return None
    resolution = res_out_stem(stem)
    candidates = run_dl_source(swap_facts(source, param, sorted(value)),
                               grid, solver_path=path)
    concept = case_space(source).concept
    fine = model_outcomes(candidates, resolution)
    if concept in fine:
        return fine[concept]
    return case_outcomes(candidates, resolution).get(concept_case(source))


NO_COLOR = mctx("the parameter is not one color")
NO_FREE_COLOR = mctx("no train input has a free color")
ONE_OUTPUT = mctx("the concept case gives one output at both values, or is "
                  "undefined at both, on every swap")


def swap_witness(stem: str, param: str, proposer: str, types: list[str],
                 stored: set[tuple]) -> tuple[Swap | None, str]:
    """The swap that tells the derived case from the stored reading, and
    the reason in its place where no swap tells them apart. The first train
    input on whose swapped grid the concept case gives different outputs at
    the stored value and at the value the proposer gives, or is defined at
    one value alone, is the witness."""
    if types != ["Color"] or len(stored) != 1:
        return None, NO_COLOR
    color = next(iter(stored))[0]
    path, task_id = solver_file(stem)
    source = path.read_text()
    task = load_task(task_id)
    concept = concept_case(source)
    resolution = res_out_stem(stem)
    held = _stored_colors(expand_macros(source), _lib_defines())
    free_seen = False
    for i, ex in enumerate(task.train):
        used = held | {c for row in ex.input for c in row}
        free = [c for c in range(10) if c not in used]
        if not free:
            continue
        free_seen = True
        grid = _swap_grid(ex.input, color, free[0])
        cand = probe_grid(grid).get(proposer, set())
        if not cand:
            continue
        got = _concept_outcome(source, grid, path, concept, resolution)
        at_derived = _concept_outcome(
            swap_facts(source, param, sorted(cand)), grid, path, concept,
            resolution)
        if at_derived == got:
            continue
        return Swap(f"train {i}", color, free[0], grid, got, at_derived), ""
    if not free_seen:
        return None, NO_FREE_COLOR
    return None, ONE_OUTPUT


def _show(rows) -> str:
    """A parameter's value as a finding names it."""
    return ", ".join(
        _render_arg(row[0]) if len(row) == 1
        else "(" + ", ".join(_render_arg(v) for v in row) + ")"
        for row in sorted(rows)
    ) or "nothing"


def _names(params) -> str:
    return ", ".join(f"`{n}`" for n in sorted(params)) or "no parameter"


def entry_witness(stem: str, param: str, proposer: str,
                  entry: Entry) -> list[str]:
    """Where a witness file entry fails to witness the derived case: its
    `assign` names another parameter, the proposer gives another value on
    its input, or the concept case gives one output at both values or is
    undefined at both."""
    out: list[str] = []
    if sorted(entry.assign) != [param]:
        out.append(mctx("`assign` names {named}; a derive entry's `assign` "
                        "names `{param}` alone").format(
            named=_names(entry.assign), param=param))
        return out
    want = set(_rows(entry.assign[param]))
    got = probe_grid(entry.input).get(proposer, set())
    if got != want:
        out.append(mctx("`{proposer}` gives {got} on the input; `assign` "
                        "gives {want}").format(
            proposer=proposer, got=_show(got), want=_show(want)))
    path, _task_id = solver_file(stem)
    source = path.read_text()
    concept = concept_case(source)
    resolution = res_out_stem(stem)
    at_stored = _concept_outcome(source, entry.input, path, concept,
                                 resolution)
    at_assigned = _concept_outcome(
        assigned_source(source, entry.assign), entry.input, path, concept,
        resolution)
    if at_stored is None and at_assigned is None:
        out.append(mctx("the concept case is undefined at the stored and at "
                        "the assigned value"))
    elif at_stored == at_assigned:
        out.append(mctx("the concept case gives one output at the stored and "
                        "at the assigned value"))
    return out


def derive_report(stem: str) -> Report:
    """Every derivation of the solver's stored parameters, each with its
    witness and its `@derive` line, and the findings that stand on them."""
    path, task_id = solver_file(stem)
    source = path.read_text()
    params = fact_params(expand_macros(source), _lib_defines())
    labels, matches = per_grid_matches(stem)
    comments = proposer_comments()
    proposers = proposer_decls()
    entries = {e.id: e
               for e in (load_witnesses(task_id) or Witness(task_id)).entries}
    reads = concept_reads(source)
    dismissed = derive_ignored(source)
    findings: list[Finding] = []
    annotated: dict[str, Derive] = {}
    for block in derive_blocks(source):
        param = derive_param(source, block)
        where = f"line {block.line}"
        if not param:
            findings.append(Finding(
                where, mctx("`@derive` stands above no `.decl`")))
            continue
        if block.proposer not in proposers:
            findings.append(Finding(where, mctx(
                "`{proposer}` is no proposer of programs/proposers.dl")
                .format(proposer=block.proposer)))
            continue
        if param not in reads:
            findings.append(Finding(where, mctx(
                "`@derive` stands above a parameter the concept case does "
                "not read")))
            continue
        per = matches.get(param, {}).get(block.proposer)
        if per is None or not all(per):
            grid = labels[per.index(False)] if per else labels[0]
            findings.append(Finding(where, mctx(
                "`{proposer}` does not derive `{param}`'s stored value on "
                "{grid}").format(proposer=block.proposer, param=param,
                                 grid=grid)))
            continue
        case = f"{param}={block.proposer}"
        annotated[case] = block
        if block.verdict == OTHER and case not in entries:
            findings.append(Finding(where, mctx(
                "the verdict `{verdict}` needs an entry `{case}`").format(
                    verdict=OTHER, case=case)))
    derivations: list[Derivation] = []
    for param, per_proposer in matches.items():
        for proposer, per in per_proposer.items():
            if not all(per):
                continue
            d = Derivation(param, proposer, comments.get(proposer, ""),
                           annotated.get(f"{param}={proposer}"),
                           read=param in reads,
                           ignored=param in dismissed)
            if not d.read or d.ignored:
                derivations.append(d)
                continue
            entry = entries.get(d.case)
            if entry is not None:
                d.entry = d.case
                findings += [
                    Finding(d.case, text)
                    for text in entry_witness(stem, param, proposer, entry)
                ]
            else:
                types, stored = params.get(param, ([], set()))
                d.swap, d.reason = swap_witness(stem, param, proposer, types,
                                                stored)
            if d.line is None and (d.entry or d.swap is not None):
                findings.append(Finding(param, mctx(
                    "`{proposer}` derives the stored value on every input "
                    "and has no `@derive` or `@ignore: derive` line").format(
                        proposer=proposer)))
            derivations.append(d)
    return Report(derivations, findings)


def _witness_line(swap: Swap) -> str:
    line = mctx("witness: {grid} with {stored} and {free} swapped").format(
        grid=swap.grid, stored=swap.stored, free=swap.free)
    if swap.at_stored is None:
        line += mctx("; the concept case is undefined at the stored value")
    elif swap.identity:
        line += mctx("; the concept case gives the input unchanged")
    else:
        line += mctx("; the concept case gives another grid")
    if swap.at_derived is None:
        line += mctx("; the derived case is undefined")
    return line


def render_derive(report: Report) -> list[str]:
    """The `derive` command's output: one block per derivation."""
    if not report.derivations:
        return [mctx("no built-in derivation fits")]
    lines: list[str] = []
    for d in report.derivations:
        lines.append(mctx("{param}: {proposer} — {comment}").format(
            param=d.param, proposer=d.proposer, comment=d.comment))
        if d.ignored:
            lines.append("  " + mctx(
                "no case: the `@ignore: derive` line above the declaration "
                "dismisses it"))
            continue
        if not d.read:
            lines.append("  " + mctx(
                "no case: the concept case does not read the parameter"))
            continue
        # The witness the line's plausibility and verdict judge, shown
        # whether or not the line stands yet.
        if d.entry:
            lines.append("  " + mctx("witness: entry {case}").format(
                case=d.case))
        elif d.swap is not None:
            lines.append("  " + _witness_line(d.swap))
        else:
            lines.append("  " + mctx("no witness: {reason}").format(
                reason=d.reason))
            if d.line is None:
                lines.append("  " + mctx(
                    "the case needs an entry `{case}`, its `assign` holding "
                    "`{param}` at the value `{proposer}` gives on the "
                    "entry's input, or an `@ignore: derive` line when no "
                    "input separates them").format(case=d.case, param=d.param,
                                             proposer=d.proposer))
                continue
        if d.line is not None:
            lines.append("  " + mctx(
                "line {line}: @derive {proposer}: {plausibility} {verdict}")
                .format(line=d.line.line, proposer=d.proposer,
                        plausibility=d.line.plausibility,
                        verdict=d.line.verdict))
            continue
        lines.append("  " + derive_hint(d.proposer))
        lines.append("  " + ignore_hint())
    return lines


def derive_hint(proposer: str) -> str:
    """The line the session adds above the parameter's `.decl`."""
    return f"add: // @derive {proposer}: <plausibility> <verdict>"


def ignore_hint() -> str:
    """The line the session adds instead when it judges the derived model
    no case, at the same site."""
    return "or:  // @ignore: derive — <reason>"


def render_findings(report: Report) -> list[str]:
    """The audit's section: one line per finding, and `derive: ok` when
    none stands."""
    return [f"{f.where}: {f.text}" for f in report.findings] or [DERIVE_OK]
