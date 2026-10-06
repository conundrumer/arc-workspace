"""The sentences of the witness kinds, from their payloads' parts."""

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

from checker.finding import AtEntry, AtLine, Finding, Kind
from checker.payloads.witness import (
    AnnotationPayload,
    ApproximatedWithoutWitness,
    ApproximationUnwitnessed,
    BranchRef,
    BranchUnwitnessed,
    CaseSet,
    ConceptPayload,
    ConceptUnenumeratedPayload,
    Condition,
    DriftPayload,
    DroppedPayload,
    ForeignUnderApproximated,
    NoDivergence,
    PointBranch,
    ReassignedMismatch,
    RelaxedNoClaim,
    RelaxedNotScene,
    SeparatesPayload,
    StandsElsewhere,
    SubsumedPayload,
    TaskAssignPayload,
    ListsNoCasePayload,
    UnjustifiedDropPayload,
    UnlistedPayload,
    UnseparatedPayload,
    VerdictOutputUnknown,
    WitnessEntryMissing,
)
from checker.render import (
    NO_ASSIGN_VALUE,
    _no_sentence,
    _ticked,
    names_text,
    resolution_lines,
    where_text,
)
from checker.render.grids import grid_lines, shifted
from solver.names import name as case_name
from controlled_markdown import mctx
from solver import names
from solver.annotations import Slot, comment_text, verdict_text, witness_text
from solver.aggregate import Solver
from solver.outcome import Grids, Outcome
from solver.solve import PairId
from solver.witness import (
    AssignValue,
    GroupGrid,
    RejectedOutput,
    Resolutions,
    Undefined,
    assign_json,
)

if TYPE_CHECKING:
    from checker.witness import TryResult

WITNESS_KINDS = frozenset({
    Kind.DRIFT, Kind.UNLISTED, Kind.ANNOTATION, Kind.UNSEPARATED,
    Kind.SUBSUMED, Kind.CONCEPT, Kind.SEPARATES, Kind.LISTS_NO_CASE,
    Kind.DROPPED, Kind.DROP_UNJUSTIFIED, Kind.TASK_ASSIGN,
    Kind.CONCEPT_UNENUMERATED,
})
"""The kinds this module states."""

_WITNESSES = "([Witnesses](docs/handbook/principles.md#witnesses))"


# Parts


def outcome_lines(solver: Solver,
                  value: Outcome | GroupGrid | RejectedOutput) -> list[str]:
    """An outcome drawn: each grid one row per line, a blank line between
    the grids of an outcome of more than one, a `Resolutions` output's
    grids each under its resolution value (`resolution_lines`); nothing
    for an undefined outcome."""
    match value:
        case Resolutions():
            return resolution_lines(solver, value)
        case Grids(grids=gs):
            grids = gs
        case RejectedOutput(grid=g):
            grids = (g,)
        case Undefined():
            return []
        case tuple():
            grids = (value,)
        case _:
            from checker.render import failure_text
            return [failure_text(value)]
    lines: list[str] = []
    for i, grid in enumerate(grids):
        lines += ([""] if i else []) + grid_lines(grid)
    return lines


def _side(solver: Solver, label: str,
          value: Outcome | GroupGrid | RejectedOutput) -> list[str]:
    if isinstance(value, Undefined):
        return [f"  {label}: " + mctx("undefined")]
    return [f"  {label}:", *(shifted(ln, "    ") if ln else ""
                             for ln in outcome_lines(solver, value))]


def _cases(cases: CaseSet) -> str:
    """A set of cases by the names that print it (`CaseSet`)."""
    return names_text(cases.names)


def _params(names: Sequence[str]) -> str:
    """A parameter list as a finding writes it."""
    return _ticked(sorted(names)) or mctx("no parameter")


def _ref_name(ref: BranchRef) -> str:
    """A branch in the one name form (`solver.names.part_text`)."""
    return names.part_text(ref)


def _branches_text(parts: Sequence[PointBranch]) -> str:
    """One side of a branch difference as one name: the branch it takes
    at each point where the two sides differ, joined as a name
    (`solver.names.part_name`)."""
    return f"`{names.part_name(parts)}`"


def _assign_text(assign: Sequence[tuple[str, AssignValue]]) -> str:
    """An `assign` value as the witness file writes it
    (`solver.witness.assign_json`)."""
    return json.dumps(assign_json(assign))


# Sentences


def _annotation_text(solver: Solver, p: AnnotationPayload) -> str:
    match p:
        case ApproximatedWithoutWitness(kind=kind, slug=slug):
            return mctx("`@{kind} {slug}` is approximated and has no "
                        "`@witness` line under its `@approximated:`").format(
                kind=kind.value, slug=slug)
        case ApproximationUnwitnessed(kind=kind, slug=slug, case=case):
            return mctx("`@{kind} {slug}` is approximated and no witness "
                        "under its `@approximated:` shows case `{case}` "
                        "giving an output other than the verdict's").format(
                kind=kind.value, slug=slug, case=case_name(solver, case))
        case ForeignUnderApproximated(witness=w, kind=kind, slug=slug):
            return mctx("`@witness {id}` under `@approximated:` of "
                        "`@{kind} {slug}` is `foreign`").format(
                id=w, kind=kind.value, slug=slug)
        case RelaxedNotScene(slug=slug, denotes=kind):
            return mctx("`@relaxed {slug}` denotes a `@{kind}` claim"
                        ).format(slug=slug, kind=kind.value)
        case RelaxedNoClaim(slug=slug):
            return mctx("`@relaxed {slug}` denotes no claim in the header"
                        ).format(slug=slug)
        case VerdictOutputUnknown(verdict=v):
            return mctx("the output the verdict `{verdict}` denotes on this "
                        "witness is unknown: no witnessed case takes "
                        "`{verdict}`").format(verdict=verdict_text(v))
        case WitnessEntryMissing(witness=w):
            return mctx("the witness file holds no witness `{id}`").format(
                id=w)
        case BranchUnwitnessed(constructor=c):
            return mctx("`{name}` is no concept branch and has no "
                        "`@witness` line; add `{line}`").format(
                name=c, line=comment_text(witness_text(
                    Slot.ID, Slot.PLAUSIBILITY, Slot.VERDICT)))
        case ReassignedMismatch(reassigned=r, assigned=a):
            return mctx("the `@reassigned` lines give {named}; the "
                        "witness's `assign` changes {holds}").format(
                named=_params(r), holds=_params(a))
        case StandsElsewhere(witness=w, changed=changed):
            return (mctx("`{id}` stands at the stored assignment, and its "
                         "`assign` changes {changed} ").format(
                id=w, changed=_params(changed)) + _WITNESSES)
        case NoDivergence(witness=w, model=m, first=first, branch=b):
            return (mctx("on `{id}`, `{model}` and `{first}` give the same "
                         "output or neither is defined, so `{id}` is no "
                         "witness of `{branch}` ").format(
                id=w, model=case_name(solver, m),
                first=case_name(solver, first), branch=_ref_name(b))
                + _WITNESSES)


def _pairs_lines(solver: Solver, p: UnseparatedPayload | SubsumedPayload
                 ) -> list[str]:
    """A branch difference and the pairs it holds: how many of the pairs
    that differ by it alone, and the names of the branches both cases of
    each such pair take elsewhere."""
    a, b = _branches_text(p.a), _branches_text(p.b)
    n, of = len(p.contexts.cases), p.of
    if isinstance(p, UnseparatedPayload):
        head = mctx("no witness separates {a} from {b}").format(a=a, b=b)
    else:
        head = mctx("no run shows {a} defined and differing from {b}"
                    ).format(a=a, b=b)
    if not p.contexts.names:
        return [head + " " + (
            mctx("in the one pair of cases that differs by these branches "
                 "alone, of which one is `{case}`").format(
                case=case_name(solver, p.contexts.cases[0]))
            if of == 1 and p.contexts.cases else
            mctx("in any of the {of} pairs of cases that differ by these "
                 "branches alone").format(of=of))]
    return [head + " " + mctx(
        "in {n} of the {of} pairs of cases that differ by these branches "
        "alone; both cases of each such pair take one of:").format(
            n=n, of=of),
        *(f"  `{name}`" for name in p.contexts.names)]


def _dropped_line(solver: Solver, p: DroppedPayload) -> str:
    a = case_name(solver, p.case)
    against = "" if p.against is None else (
        p.against.text
        if isinstance(p.against, PairId) else case_name(solver, p.against))
    match p.condition:
        case Condition.UNDEFINED:
            return mctx("dropped case `{a}` fails Fit: no run shows it "
                        "defined").format(a=a)
        case Condition.NOT_RUN:
            return mctx("dropped case `{a}` is not judged: no run with it "
                        "restored gives a cell at it").format(a=a)
        case Condition.ENTRY_NOT_RUN:
            return mctx("dropped case `{a}` is not judged: it is not run on "
                        "a witness entry whose `assign` the model cannot "
                        "place").format(a=a)
        case Condition.FIT:
            return mctx("dropped case `{a}` fails Fit: at `{pair}` it "
                        "gives no output the pair accepts").format(
                a=a, pair=against)
        case Condition.EQUIVALENCE:
            return mctx("dropped case `{a}`: no witness separates it from "
                        "`{b}`, a pair that [Witness]"
                        "(docs/handbook/procedure.md#witness) resolves"
                        ).format(a=a, b=against)
        case Condition.SUBSUMPTION:
            return mctx("dropped case `{a}` fails Subsumption against "
                        "`{b}`").format(a=a, b=against)


def _unjustified_line(solver: Solver, p: UnjustifiedDropPayload) -> str:
    a = case_name(solver, p.case)
    if p.unseparated.cases:
        return mctx("dropped case `{a}` fails no case condition in the "
                    "`witness --every-case` run; no witness separates it "
                    "from {b}, and [Witness]"
                    "(docs/handbook/procedure.md#witness) resolves each "
                    "such pair").format(a=a, b=_ticked(p.unseparated.names))
    return mctx("dropped case `{a}` fails no case condition in the "
                "`witness --every-case` run").format(a=a)


def witness_lines(solver: Solver, f: Finding) -> list[str]:
    """The lines of one finding of a witness kind: one block per
    finding."""
    p = f.payload
    at = where_text(solver, f.where)
    match p:
        case DriftPayload(cases=cases, expected=expected,
                                      actual=actual):
            case = _cases(cases)
            one = len(cases.cases) == 1
            if isinstance(expected, RejectedOutput):
                return [mctx("{entry}: case {case} gives the witness's "
                             "judged output").format(entry=at, case=case)
                        if one else
                        mctx("{entry}: these cases give the witness's judged "
                             "output: {case}").format(entry=at, case=case),
                        *_side(solver, mctx("the judged output"), actual)]
            return [mctx("{entry}: case {case} gives an output the witness "
                         "does not name").format(entry=at, case=case)
                    if one else
                    mctx("{entry}: these cases give an output the witness "
                         "does not name: {case}").format(entry=at, case=case),
                    *_side(solver, mctx("the witness's output"), expected),
                    *_side(solver, mctx("the solver's output"), actual)]
        case UnlistedPayload(cases=cases, actual=actual):
            case = _cases(cases)
            return [mctx("{entry}: case {case} is not listed").format(
                entry=at, case=case) if len(cases.cases) == 1 else
                mctx("{entry}: these cases are not listed: {case}").format(
                    entry=at, case=case),
                *_side(solver, mctx("the solver's output"), actual)]
        case UnseparatedPayload() | SubsumedPayload():
            return _pairs_lines(solver, p)
        case ConceptPayload(concept=concept):
            return [mctx("{entry}: the concept case gives a grid other than "
                         "the judged output").format(entry=at),
                    *_side(solver, mctx("the solver's output"), concept)]
        case SeparatesPayload(name=name):
            return [mctx("{entry}: the `separates` text has `{name}`, and no "
                         "group lists it").format(entry=at, name=name)]
        case ListsNoCasePayload(names=names):
            return [f"{at}: " + (
                mctx("{names} denotes no case of the solver, so "
                     "the grid of the group that lists it is not checked")
                if len(names) == 1 else
                mctx("these names denote no case of the solver, "
                     "so the grids of the groups that list them are not "
                     "checked: {names}")).format(names=_ticked(names))]
        case DroppedPayload():
            return [_dropped_line(solver, p)]
        case UnjustifiedDropPayload():
            return [_unjustified_line(solver, p)]
        case ConceptUnenumeratedPayload(concept=concept):
            return [mctx("the concept case `{a}` is not among the cases "
                         "`impl_choice` enumerates, so no check reads it "
                         "as a case of the solver; see "
                         "[Cases](docs/handbook/solver-file.md#cases)"
                         ).format(a=case_name(solver, concept))]
        case TaskAssignPayload(values=values,
                                                 task_entry=task_entry,
                                                 assign=assign):
            names = "; ".join(
                mctx("the `assign` value of `{param}` holds `{value}`, "
                     "which is {unknown}").format(
                         param=k, value=v, unknown=NO_ASSIGN_VALUE)
                for k, v in values)
            return [mctx("{entry}: {names}, so the run takes the `assign` of "
                         "the `{id}` witness in the task's witness file: "
                         "`{assign}`").format(
                entry=at, names=names, id=task_entry,
                assign=_assign_text(assign))]
        case (
                ApproximatedWithoutWitness() | ApproximationUnwitnessed()
                | ForeignUnderApproximated() | RelaxedNotScene()
                | RelaxedNoClaim() | VerdictOutputUnknown()
                | WitnessEntryMissing() | ReassignedMismatch()
                | StandsElsewhere() | NoDivergence()
                | BranchUnwitnessed()):
            line = _annotation_text(solver, p)
            return [f"{at}: {line}" if isinstance(f.where, AtLine | AtEntry)
                    else line]
        case _:
            _no_sentence(f)


def try_lines(solver: Solver, result: "TryResult") -> list[str]:
    """The `witness --try` report: the candidate's groups as `record`
    prints them, the unseparated branch differences whose pairs it
    separates, and the subsumed ones whose pairs it shows defined and
    differing; it writes nothing."""
    from checker.render.branch_blocks import record_lines

    lines = record_lines(result.entry, solver, result.cases,
                         result.of) + [""]

    def counted(n: int, left: int) -> str:
        return mctx("all {n} of its pairs").format(n=n) if not left \
            else mctx("{k} of its {n} pairs, {left} left").format(
                k=n - left, n=n, left=left)

    if result.unseparated:
        lines.append(mctx("unseparated branch differences it separates:"))
        for x in result.unseparated:
            p = x.finding.payload
            assert isinstance(p, UnseparatedPayload)
            lines.append("  " + mctx("{a} from {b}: {count}").format(
                a=_branches_text(p.a), b=_branches_text(p.b),
                count=counted(len(p.contexts.cases), x.left)))
    if result.subsumed:
        lines.append(mctx("subsumed branch differences it shows defined and "
                          "differing:"))
        for x in result.subsumed:
            p = x.finding.payload
            assert isinstance(p, SubsumedPayload)
            lines.append("  " + mctx(
                "{a} defined and differing from {b}: {count}").format(
                a=_branches_text(p.a), b=_branches_text(p.b),
                count=counted(len(p.contexts.cases), x.left)))
    if not result.unseparated and not result.subsumed:
        lines.append(mctx("it separates no unseparated pair and shows no "
                          "subsumed case defined and differing"))
    lines.append(mctx("wrote nothing"))
    return lines
