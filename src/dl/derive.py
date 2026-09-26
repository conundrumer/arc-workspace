"""Derived readings of stored parameters: the branches a proposer states.

A proposer of `programs/proposers.dl` that gives a parameter's stored value
on every input, each input read alone, states a model that derives the value
from the input. That model's reading is a branch of a choice point on the
parameter: the solver carries one `// @derive` line above the parameter's
`.decl`, and no constructor. `dl.models.enumeration` holds the cases that
take the branch.

The witness tells the cases that take the branch from the same cases at
the stored value. The tool builds one by swapping the stored color with a
color the input does not hold: the proposer follows the swap, the stored
fact does not, and some case that takes the branch gives an output other
than the same case at the stored value, or one of the two is defined
alone. The witness's id is the branch's name, `<param>=<Proposer>`; an
entry of that id in the witness file is kept, and a parameter no swap
separates takes one built by hand.

A `// @ignore: derive` line stands above the parameter's `.decl` when the
session judges a derivation no branch, in place of its `@derive` line;
`// @ignore: derive <name>` under a `@derive` line excludes every held
case that takes the line's branch and every branch whose name `<name>`
contains.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from arc.task import load as load_task
from controlled_markdown import mctx
from dl.annotations import (
    DERIVE,
    Branch,
    Derive,
    derive_blocks,
    derive_param,
    ignore_lines,
)
from dl.determination_plan import (
    fact_params,
    per_grid_matches,
    proposer_decls,
)
from dl.domains import _lib_defines
from dl.models import CaseId, Cases, enumeration
from dl.store import case_reads
from dl.paths import PROPOSERS_SRC
from dl.solve import solver_file
from dl.source import (
    _render_arg,
    assigned_source,
    expand_macros,
    with_line_above,
)
from dl.witness import (
    Entry,
    Witness,
    assign_findings,
    branch_diverges,
    drop_findings,
    load_witness_file,
    load_witnesses,
)

DERIVE_OK = "derive: ok"
"""The pass line, printed when no finding stands."""

OTHER = "other"
"""The verdict that takes a judged output, which only an entry holds."""

COMP_RE = re.compile(r"^\.comp\s+(\w+)")


@dataclass
class Swap:
    """The witness the tool builds: on the input `grid` names, the color
    `free` stands in for the color `stored` holds, and `input` is the
    swapped grid. `case` is the first case that takes the branch and gives
    there an output other than `other`, the case that takes the stored
    value there and the same branches elsewhere, by its shortest name."""

    grid: str
    stored: int
    free: int
    input: list[list[int]]
    case: CaseId
    other: str


@dataclass
class Derivation:
    """One parameter read off the input by one proposer. `line` is the
    solver's `@derive` line where one stands, `entry` the witness file's
    entry of the branch's name, and `swap` the witness the tool builds, with
    `reason` in its place where it builds none. `source` is the solver's
    source with the `@derive` line standing, as the witness is recorded
    on it."""

    param: str
    proposer: str
    comment: str
    line: Derive | None = None
    entry: str = ""
    swap: Swap | None = None
    reason: str = ""
    read: bool = True
    """Some held case reads the parameter. Where none does, no case takes
    the branch."""
    ignored: bool = False
    """A bare `@ignore: derive` line stands in place of the `@derive`
    line."""
    excluded: bool = False
    """The `@ignore: derive <name>` lines under the `@derive` line exclude
    every case that takes the branch."""
    source: str = ""

    @property
    def case(self) -> CaseId:
        return CaseId(f"{self.param}={self.proposer}")


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


NO_COLOR = mctx("the parameter is not one color")
NO_FREE_COLOR = mctx("no train input has a free color")
ONE_OUTPUT = mctx("on every swap, each case that takes the branch gives the "
                  "output of the case that takes the stored value there and "
                  "the same branches elsewhere")


def swap_witness(stem: str, space: Cases, branch: Branch, source: str,
                 types: list[str], stored: set[tuple]
                 ) -> tuple[Swap | None, str]:
    """The swap that tells the cases that take `branch` from the same cases
    at the stored value (`dl.witness.branch_diverges`), and the reason in
    its place where no swap tells them apart. The first train input whose
    swapped grid shows it is the witness. `space` and `source` are the
    solver's with the branch's line standing."""
    if types != ["Color"] or len(stored) != 1:
        return None, NO_COLOR
    color = next(iter(stored))[0]
    _path, task_id = solver_file(stem)
    task = load_task(task_id)
    held = _stored_colors(expand_macros(source), _lib_defines())
    free_seen = False
    for i, ex in enumerate(task.train):
        used = held | {c for row in ex.input for c in row}
        free = [c for c in range(10) if c not in used]
        if not free:
            continue
        free_seen = True
        grid = _swap_grid(ex.input, color, free[0])
        pair = branch_diverges(stem, space, branch, grid, source)
        if pair is not None:
            return Swap(f"train {i}", color, free[0], grid, pair[0],
                        space.name_of(pair[1])), ""
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


def entry_witness(stem: str, space: Cases, branch: Branch, source: str,
                  entry: Entry) -> list[str]:
    """Where the witness file's entry of the branch's name fails to witness
    it: its `assign` holds a fault `assign_findings` finds, or at its
    assignment no case that takes the branch gives an output other than
    the same case at the stored value (`dl.witness.branch_diverges`).
    `space` and `source` are the solver's with the branch's line
    standing."""
    if bad := assign_findings(entry.assign, source):
        return bad
    if branch_diverges(stem, space, branch, entry.input,
                       assigned_source(source, entry.assign)) is not None:
        return []
    return [mctx("at the witness's assignment, each case that takes "
                 "`{case}` gives the output of the case that takes the stored "
                 "value there and the same branches elsewhere").format(
                     case=branch.name)]


def _lined(source: str, param: str, proposer: str) -> str | None:
    """`source` with a `@derive` line of `proposer` above the parameter's
    `.decl` in `Params`, as the session writes it. None when no `.decl`
    stands there."""
    return with_line_above(
        source, rf"^\s*\.decl\s+{re.escape(param)}\b",
        f"// @derive {proposer}: <plausibility> <verdict>", "Params")


def derive_report(stem: str, witness_file: Path | None = None) -> Report:
    """Every derivation of the solver's stored parameters, each with its
    witness and its `@derive` line, and the findings that stand on them.
    A derivation with no `@derive` line is judged with its line standing.
    `witness_file` stands in for the task's witness file."""
    path, task_id = solver_file(stem)
    source = path.read_text()
    params = fact_params(expand_macros(source), _lib_defines())
    labels, matches = per_grid_matches(stem)
    comments = proposer_comments()
    proposers = proposer_decls()
    witness = load_witnesses(task_id) if witness_file is None \
        else load_witness_file(witness_file) if witness_file.exists() \
        else None
    entries = {e.id: e for e in (witness or Witness(task_id)).entries}
    space = enumeration(source)
    reads = set().union(*(params for _read, params in case_reads(
        source, space, space.plain).values()))
    lines = {b.line: b for b in space.lines if b.kind == DERIVE}
    taken = {b for held in space.runner.values() for b in held.branches}
    dismissed = {i.site for i in ignore_lines(source)
                 if i.kind == DERIVE and not i.name}
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
                "`@derive` stands above a parameter no held case reads")))
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
                "the verdict `{verdict}` needs a witness whose id is "
                "`{case}`").format(verdict=OTHER, case=case)))
    findings += [Finding(where, text)
                 for where, text in drop_findings(space, DERIVE)]
    derivations: list[Derivation] = []
    for param, per_proposer in matches.items():
        for proposer, per in per_proposer.items():
            if not all(per):
                continue
            line = annotated.get(f"{param}={proposer}")
            d = Derivation(param, proposer, comments.get(proposer, ""), line,
                           read=param in reads,
                           ignored=line is None and param in dismissed)
            if not d.read or d.ignored:
                derivations.append(d)
                continue
            if line is not None:
                d.source, lined = source, space
                branch = lines.get(line.line)
                d.excluded = branch is None or branch not in taken
            else:
                d.source = _lined(source, param, proposer) or ""
                lined = enumeration(d.source) if d.source else space
                branch = next((b for b in lined.lines
                               if b.name == d.case), None)
            if d.excluded or branch is None:
                derivations.append(d)
                continue
            entry = entries.get(d.case)
            if entry is not None:
                d.entry = d.case
                findings += [
                    Finding(d.case, text)
                    for text in entry_witness(stem, lined, branch, d.source,
                                              entry)
                ]
            else:
                types, stored = params.get(param, ([], set()))
                d.swap, d.reason = swap_witness(stem, lined, branch,
                                                d.source, types, stored)
            if d.line is None and (d.entry or d.swap is not None):
                findings.append(Finding(param, mctx(
                    "`{proposer}` derives the stored value on every input "
                    "and has no `@derive` or `@ignore: derive` line").format(
                        proposer=proposer)))
            derivations.append(d)
    return Report(derivations, findings)


def _witness_line(swap: Swap) -> str:
    return mctx("witness: {grid} with {stored} and {free} swapped; there "
                "`{case}` differs from `{other}`"
                ).format(grid=swap.grid, stored=swap.stored, free=swap.free,
                         case=swap.case, other=swap.other)


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
                "no case takes the branch: `@ignore: derive` stands in place "
                "of its `@derive` line"))
            continue
        if not d.read:
            lines.append("  " + mctx(
                "no branch: no held case reads the parameter"))
            continue
        if d.excluded:
            lines.append("  " + mctx(
                "no case takes the branch: the `@ignore: derive <name>` "
                "lines under its `@derive` line exclude every case that "
                "would"))
            continue
        # The witness the line's plausibility and verdict judge, shown
        # whether or not the line stands yet.
        if d.entry:
            lines.append("  " + mctx("witness: `{case}` in the witness file"
                                     ).format(case=d.case))
        elif d.swap is not None:
            lines.append("  " + _witness_line(d.swap))
        else:
            lines.append("  " + mctx("no witness: {reason}").format(
                reason=d.reason))
            lines.append("  " + mctx(
                "a `@derive` line needs a witness whose id is `{case}`"
                ).format(case=d.case))
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
