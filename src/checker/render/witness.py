"""The sentences of the witness kinds, from their payloads' parts."""

import json
from collections.abc import Sequence

from checker.finding import AtEntry, AtLine, Finding, Kind
from checker.payloads.witness import (
    AnnotationPayload,
    ApproximatedWithoutWitness,
    ApproximationUnwitnessed,
    BranchUnwitnessed,
    AssignPayload,
    BranchRef,
    CaseSet,
    ConceptPayload,
    Condition,
    DriftPayload,
    ConceptUnenumeratedPayload,
    DroppedPayload,
    ForeignUnderApproximated,
    NoDivergence,
    ReassignedMismatch,
    RelaxedNoClaim,
    RelaxedNotScene,
    SeparatesPayload,
    StandsElsewhere,
    SubsumedPayload,
    Taking,
    TaskAssignPayload,
    UnheldPayload,
    UnjustifiedDropPayload,
    UnlistedPayload,
    UnseparatedPayload,
    VerdictOutputUnknown,
    WitnessEntryMissing,
)
from checker.render import (
    _no_sentence,
    _ticked,
    branch_name,
    case_name,
    grid_lines,
    joined,
    verdict_text,
    where_text,
)
from controlled_markdown import mctx
from solver import names
from solver.model import (
    Case,
    ConstructorBranch,
    DeriveBranch,
    Solver,
    StoreBranch,
    StoredAtDerive,
)
from solver.solve import Grids, Outcome, PairId
from solver.witness import (
    AssignArg,
    AssignRows,
    AssignValue,
    GroupGrid,
    RejectedOutput,
    Resolutions,
    Undefined,
)

WITNESS_KINDS = frozenset({
    Kind.DRIFT, Kind.UNLISTED, Kind.ANNOTATION, Kind.UNSEPARATED,
    Kind.SUBSUMED, Kind.CONCEPT, Kind.SEPARATES, Kind.UNHELD, Kind.DROPPED,
    Kind.DROP_UNJUSTIFIED, Kind.ASSIGN, Kind.TASK_ASSIGN,
    Kind.CONCEPT_UNENUMERATED,
})
"""The kinds this module states."""

_WITNESSES = "([Witnesses](docs/handbook/principles.md#witnesses))"


# Parts


def location(solver: Solver, f: Finding) -> str:
    """Where a witness finding stands, as the `witness` report writes it:
    `line <n>` for a line of the solver, else `where_text`."""
    if isinstance(f.where, AtLine):
        return mctx("line {n}").format(n=f.where.line)
    return where_text(solver, f.where)


def outcome_lines(value: Outcome | GroupGrid | RejectedOutput) -> list[str]:
    """An outcome drawn: each grid one row per line, a blank line between
    the grids of an outcome of more than one; nothing for an undefined
    outcome."""
    match value:
        case Grids(grids=gs) | Resolutions(grids=gs):
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


def _side(label: str, value: Outcome | GroupGrid | RejectedOutput
          ) -> list[str]:
    if isinstance(value, Undefined):
        return [f"  {label}: " + mctx("undefined")]
    return [f"  {label}:", *(f"    {ln}" if ln else ""
                             for ln in outcome_lines(value))]


def _cases(cases: CaseSet) -> str:
    """A set of cases by the names that print it (`CaseSet`)."""
    return ", ".join(cases.names)


def _params(names: Sequence[str]) -> str:
    """A parameter list as a finding writes it."""
    return _ticked(sorted(names)) or mctx("no parameter")


def _ref_name(ref: BranchRef) -> str:
    """A branch in the one name form: a constructor with Souffle's `$`
    prefix, a `@derive` or `@store` branch as `branch_name` gives it."""
    if isinstance(ref, ConstructorBranch):
        return names.ctor_text(ref.name)
    return branch_name(ref)


def _taking_text(solver: Solver, t: Taking) -> str:
    """A side or a shared part by its name: the base and the branches the
    part holds, named as a model (`solver.names.name`), branches alone
    joined by ` & `."""
    if t.base is None:
        return joined([branch_name(b) for b in t.branches])
    return names.name(solver, Case(t.base, t.branches))


def _side_text(solver: Solver, side: Taking, other: Taking) -> str:
    """One side of an unseparated pair as one name: its own, and for a
    side that holds nothing, the first branch at each point where the
    other side takes a branch, `<param>=stored` at a `@derive` point,
    joined as one name (`joined`). A `@store` point's first branch, the
    derived value, has no name, and is stated after the name."""
    if side.base is not None or side.branches:
        return f"`{_taking_text(solver, side)}`"
    named = [names.branch_text(StoredAtDerive(b.parameter))
             for b in other.branches
             if isinstance(b, DeriveBranch | StoredAtDerive)]
    derived = [mctx("the derived value of `{r}`").format(r=b.spelled)
               for b in other.branches if isinstance(b, StoreBranch)]
    parts = ([f"`{joined(named)}`"] if named else []) + derived
    if len(parts) == 1:
        return parts[0]
    return mctx("{firsts} and {last}").format(firsts=", ".join(parts[:-1]),
                                              last=parts[-1])


def _arg_text(arg: AssignArg) -> object:
    return [_arg_text(a) for a in arg] if isinstance(arg, tuple) else arg


def _assign_json(assign: Sequence[tuple[str, AssignValue]]) -> str:
    return json.dumps({
        k: [[_arg_text(a) for a in row] for row in v.rows]
        if isinstance(v, AssignRows) else [list(r) for r in v]
        for k, v in assign})


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
                        "witness is unknown: the runner holds no case that "
                        "takes `{verdict}`").format(verdict=verdict_text(v))
        case WitnessEntryMissing(witness=w):
            return mctx("the witness file holds no witness `{id}`").format(
                id=w)
        case BranchUnwitnessed(constructor=c):
            return mctx("`{name}` is no concept branch and has no "
                        "`@witness` line; add "
                        "`// @witness <id>: <plausibility> <verdict>`"
                        ).format(name=c)
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


def _unseparated_lines(solver: Solver, p: UnseparatedPayload) -> list[str]:
    neither = (mctx("neither takes another `@derive` or `@store` branch")
               if p.a.branches or p.b.branches
               else mctx("neither takes a `@derive` or `@store` branch"))
    return [mctx("no witness separates {a} from {b}").format(
        a=_side_text(solver, p.a, p.b), b=_side_text(solver, p.b, p.a)),
        *(f"  {neither}" if part.base is None and not part.branches
          else "  " + mctx("both take `{name}`").format(
              name=_taking_text(solver, part))
          for part in p.under)]


def _dropped_line(solver: Solver, p: DroppedPayload) -> str:
    a = case_name(solver, p.case)
    against = "" if p.against is None else (
        f"{p.against.section} {p.against.index}"
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
    at = location(solver, f)
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
                        *_side(mctx("the judged output"), actual)]
            return [mctx("{entry}: case {case} gives an output the witness "
                         "does not name").format(entry=at, case=case)
                    if one else
                    mctx("{entry}: these cases give an output the witness "
                         "does not name: {case}").format(entry=at, case=case),
                    *_side(mctx("the witness's output"), expected),
                    *_side(mctx("the solver's output"), actual)]
        case UnlistedPayload(cases=cases, actual=actual):
            case = _cases(cases)
            return [mctx("{entry}: case {case} is not listed").format(
                entry=at, case=case) if len(cases.cases) == 1 else
                mctx("{entry}: these cases are not listed: {case}").format(
                    entry=at, case=case),
                *_side(mctx("the solver's output"), actual)]
        case UnseparatedPayload():
            return _unseparated_lines(solver, p)
        case SubsumedPayload(subsumed=a, by=by):
            if len(by.names) == 1:
                return [mctx("no run shows `{a}` defined and differing from "
                             "`{b}`").format(a=case_name(solver, a),
                                             b=by.names[0])]
            return [mctx("no run shows `{a}` defined and differing from "
                         "these cases:").format(a=case_name(solver, a)),
                    *(f"  {n}" for n in by.names)]
        case ConceptPayload(concept=concept):
            return [mctx("{entry}: the concept case gives a grid other than "
                         "the judged output").format(entry=at),
                    *_side(mctx("the solver's output"), concept)]
        case SeparatesPayload(name=name):
            return [mctx("{entry}: the `separates` text has `{name}`, and no "
                         "group lists it").format(entry=at, name=name)]
        case UnheldPayload(names=names):
            return [f"{at}: " + (
                mctx("the runner does not hold the case {names} denotes, so "
                     "the grid of the group that lists it is not checked")
                if len(names) == 1 else
                mctx("the runner does not hold the cases these names denote, "
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
        case AssignPayload(name=name, arities=arities,
                                        columns=columns):
            return [mctx("{entry}: the `assign` value of `{param}` has facts "
                         "of {got} arguments, and the relation `{param}` "
                         "takes {want}").format(
                entry=at, param=name, want=columns,
                got=" and ".join(str(n) for n in arities))]
        case TaskAssignPayload(values=values,
                                                 task_entry=task_entry,
                                                 assign=assign):
            names = "; ".join(
                mctx("the `assign` value of `{param}` holds `{value}`, "
                     "which is not a lib constant").format(param=k, value=v)
                for k, v in values)
            return [mctx("{entry}: {names}, so the run takes the `assign` of "
                         "the `{id}` witness in the task's witness file: "
                         "`{assign}`").format(
                entry=at, names=names, id=task_entry,
                assign=_assign_json(assign))]
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
