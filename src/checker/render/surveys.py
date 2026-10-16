"""The surveys' text: one render function per survey result type. A
result's timed-out and failed runs print here, through the finding lines
every command prints them with."""

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Annotated
from pathlib import Path

import controlled_markdown as nm
from checker.deletions import (
    BaselineFails,
    ColumnName,
    DeletionKind,
    DeletionReport,
    DeletionResult,
    DeletionRow,
    Quote,
    Quoted,
)
from checker.derived_constant import (
    ConstantReport,
    ConstantResult,
    ExampleFails,
    NoCandidate,
    NoConstant,
)
from checker.determination_plan import (
    ENUMERATION_LIMIT,
    AtCase,
    Candidates,
    Covering,
    Empty,
    Enumerable,
    Exact,
    Joint,
    KeyedTable,
    Missed,
    Narrowed,
    Open,
    Partial,
    PlanResult,
    PlanValue,
    ProbeFails,
    Settled,
    Subject,
    Superset,
    Verdict,
    by_parameter,
    classify,
    covering,
    parameter_of,
    value_order,
)
from checker.domains import (
    MAGNITUDE_TYPES,
)
from checker.drop_one import DropOneResult, DroppedFact
from checker.payloads.open_values import Fact, TrainFails, UnexercisedPayload
from checker.render import finding_lines, noun, verb_s
from checker.render.cases import names_text, under_case
from checker.render.lint import marker_text
from checker.render.locations import file_line, line_text, solver_name
from checker.render.no_result import CASES_RUN_FAILED, run_failed, cases_run_failed, failure_text
from checker.render.values import arg_text
from checker.render.branches import NOT_BETWEEN
from checker.runs import NoCases
from checker.sweep import (
    CaseSets,
    Cut,
    Extras,
    Gaps,
    GivingValues,
    Near,
    NoCaseMarker,
    NotSwept,
    RunFailed,
    SetCases,
    Uncompared,
    SetSweep,
    SetValue,
    Skipped,
    SweepEntry,
    SweepReport,
    ValueSweep,
    set_rows,
)
from checker.variants import OnTest, TimedOut
from controlled_markdown import mctx
from engine import Engine, RecordValue, Row, RunFailure, checkout
from engine.quotes import quotes
from solver.model import Case
from solver.aggregate import Solver, has_determine
from solver.determine import rigid_charts
from solver.names import cover
from solver.names import name as case_name
from solver.value_order import row_key
from solver.vocabulary import NUMBER


def deletion_doc() -> Path:
    """The deletion report's prose, one section per group."""
    return checkout.prompts() / "run_dl.md"


# Deletions


def _head_text(engine: Engine, q: Quoted) -> str:
    """A clause's head, with `<= <atom>` for a subsumptive clause."""
    if q.dominating is None:
        return engine.text(q.head)
    return f"{engine.text(q.head)} <= {engine.text(q.dominating)}"


_KIND_ORDER = {k: i for i, k in enumerate(DeletionKind)}
"""The order of the deletion kinds as `DeletionKind` declares them. Rows
of one line and kind keep the order `deletions` gives them, the order of
their parts in the clause."""


def _label(r: DeletionRow) -> str:
    """A row's kind as the report prints it."""
    return f"determination {r.kind}" if r.determination else str(r.kind)


def quote_text(engine: Engine, q: Quote) -> str:
    """What a deletion row quotes between backticks: a removed part and
    its clause's head read as two quoted fragments."""
    match q:
        case Quoted(part=None):
            return _head_text(engine, q)
        case Quoted(part=part):
            return (", ".join(engine.text(x) for x in part or ())
                    + f"` in `{_head_text(engine, q)}")
        case ColumnName(relation=r, column=c):
            return f"{r}.{c}"


def _section(name: str, **values: object) -> list[str]:
    """One section of the deletion report's prose."""
    registry = nm.Registry(checkout.ROOT)
    document = registry.load(deletion_doc())
    body = nm.Node(nm.DOCUMENT, source=document.source)
    body.children = list(registry.ids[document.source][name].children)
    text = nm.render(body, registry, values).strip()
    return text.split("\n")


ROW = " " * 4
DETERMINED_CLAUSE = " " + mctx("and no determined value")
"""The `noop` note's clause for a solver with a Determine comp."""
NO_DETERMINE = mctx("the solver has no Determine comp, so no deletion's "
                    "effect on a determined value was checked")


def render_deletions(solver: Solver, result: DeletionResult) -> list[str]:
    """The deletion section, as `deletions` prints it: each
    group's statement, its note and its rows under it, then the rows
    whose run timed out, each with its timeout line; each list in line
    order."""
    if isinstance(result, BaselineFails):
        return _section("baseline-fails")
    if isinstance(result, TimedOut):
        return finding_lines(solver, result.finding)
    report: DeletionReport = result
    judged = report.judged
    rows = sorted(report.rows, key=lambda r: (
        r.line, r.determination, _KIND_ORDER[r.kind]))

    def entries(group: list[DeletionRow]) -> list[str]:
        return [f"{ROW}- {file_line(solver.stem, r.line)}: {_label(r)} "
                f"`{quote_text(solver.engine, r.quote)}`"
                for r in group]

    apart = (DeletionKind.UNGROUNDED, DeletionKind.BOUND_ENUMERATOR)
    noop = [r for r in rows if r.kind not in apart]
    enumerators = [r for r in rows
                   if r.kind == DeletionKind.BOUND_ENUMERATOR]
    ungrounded = [r for r in rows if r.kind == DeletionKind.UNGROUNDED]
    lines: list[str] = []
    if noop:
        lines += _section("noop", count=len(noop), judged=judged,
                          determined=DETERMINED_CLAUSE
                          if has_determine(solver) else "")
        lines += entries(noop)
    elif not enumerators:
        lines += _section("none", judged=judged)
    if enumerators:
        if lines:
            lines.append("")
        lines += _section("enumerator", count=len(enumerators),
                          judged=judged)
        lines += entries(enumerators)
    if ungrounded:
        lines.append("")
        lines += _section(
            "ungrounded", count=len(ungrounded),
            noun=noun(len(ungrounded), "deletion"))
    if report.no_determine:
        lines += ["", NO_DETERMINE]
    if report.timed_out:
        lines.append("")
        lines += _section("timed-out")
        lines += [f"{ROW}- {file_line(solver.stem, t.line)}: {t.kind} "
                  f"`{quote_text(solver.engine, t.quote)}`: "
                  f"{' '.join(finding_lines(solver, t.finding))}"
                  for t in sorted(report.timed_out, key=lambda t: (
                      t.line, _KIND_ORDER[t.kind]))]
    return lines


# Values as the sweep, drop-one and the determination plan print them


def row_text(row: Row, types: Sequence[str], solver: Solver) -> str:
    """A row of a parameter, as `(<value>, ...)`."""
    return "(" + ", ".join(arg_text(v, t, solver)
                           for v, t in zip(row, types, strict=True)) + ")"


def rows_text(rows: Iterable[Row], types: Sequence[str], solver: Solver
              ) -> str:
    """Rows of a parameter (`row_text`) in the order given, separated by
    commas."""
    return ", ".join(row_text(r, types, solver) for r in rows)


def rows_list(rows: Iterable[Row], types: Sequence[str], solver: Solver
              ) -> str:
    """A list of rows of a parameter (`rows_text`), in brackets."""
    return f"[{rows_text(rows, types, solver)}]"


# Drop-one


def _fact_text(solver: Solver, f: Fact) -> str:
    return f"{f.parameter}{row_text(f.row, f.types, solver)}"


def unexercised_line(solver: Solver, at: str, p: UnexercisedPayload) -> str:
    """The line of an `unexercised` finding at `at`."""
    return mctx("{at}: removing `{fact}` changes no output on any input of "
                "the task or of the witness file").format(
                    at=at, fact=_fact_text(solver, p.fact))


def train_fails(check: str) -> str:
    """The line of the check `check`, which the stored program's failure on
    a train pair keeps from running."""
    return mctx("{check} not checked: the stored program fails a train "
                "pair").format(check=check)


def render_drop_one(solver: Solver, result: DropOneResult) -> list[str]:
    """The drop-one report: the facts no pair needs, the facts the train
    pairs do not need and the test pairs do, the facts no test pair can
    judge, and each fact whose run timed out."""
    if isinstance(result, TrainFails):
        return [train_fails("drop-one")]
    if isinstance(result, TimedOut):
        return finding_lines(solver, result.finding)
    if not result.tested:
        return [mctx("{solver}: no parameter holds more than one stored "
                     "fact").format(solver=solver_name(solver))]

    def entries(group: list[DroppedFact]) -> list[str]:
        return [f"  {_fact_text(solver, d.fact)}" for d in group]

    parameters = noun(result.parameters, "parameter")
    lines = [mctx("{tested} stored facts across {params} multi-fact "
                  "{noun}").format(tested=result.tested,
                                   params=result.parameters,
                                   noun=parameters)]
    hits = list(result.dropped)
    both = [d for d in hits if d.on_test == OnTest.PASSED]
    train_only = [d for d in hits if d.on_test == OnTest.REFUTED]
    unjudged = [d for d in hits if d.on_test == OnTest.UNJUDGED]
    if not hits and not result.timed_out:
        lines.append(mctx("every fact changes a train pair"))
        return lines
    if both:
        lines += ["", mctx("{count} fact(s) no pair needs:").format(
            count=len(both))]
        lines += entries(both)
    if train_only:
        lines += ["", mctx("{count} fact(s) the train pairs do not need, and "
                           "the test pairs do:").format(count=len(train_only))]
        lines += entries(train_only)
    if unjudged:
        lines += ["", mctx("the solver fails a test pair at its stored "
                           "assignment, so no test pair judges a drop"),
                  mctx("{count} fact(s) the train pairs do not need:").format(
                      count=len(unjudged))]
        lines += entries(unjudged)
    if result.timed_out:
        lines += ["", mctx("{count} fact(s) whose run timed out:").format(
            count=len(result.timed_out))]
        lines += [f"  {_fact_text(solver, f)}: "
                  f"{' '.join(finding_lines(solver, t))}"
                  for f, t in result.timed_out]
    return lines


# Derived constants


SHOWN_TUPLES = 4
"""How many tuples a constant's line shows."""


def render_derived_constant(solver: Solver, result: ConstantResult
                            ) -> list[str]:
    """The derived-constant report."""
    name = solver_name(solver)
    match result:
        case NoCandidate():
            return [mctx("{solver}: {why}").format(solver=name,
                                                    why=NOT_BETWEEN)]
        case NoConstant(tested=tested):
            return [mctx("{solver}: no constant relation among the {tested} "
                         "that read `in`").format(solver=name,
                                                  tested=tested)]
        case ExampleFails():
            return [mctx("{solver}: the stored source fails an "
                         "example").format(solver=name)]
        case TimedOut(finding=finding):
            return [f"{name}: {' '.join(finding_lines(solver, finding))}"]
        case ConstantReport():
            pass
    lines = [mctx("{tested} relations read `in` and feed `out`").format(
        tested=result.tested)]
    if not result.constants:
        lines.append(mctx("no relation reads the input and holds the same "
                          "tuples on every example"))
    else:
        lines += ["", mctx("{count} relation(s) hold the same tuples on "
                           "every train and test example:").format(
            count=len(result.constants))]
        for c in sorted(result.constants,
                        key=lambda c: [(p.instances, p.name)
                                       for p in c.paths]):
            rows = sorted(c.rows, key=row_key)
            shown = ", ".join(", ".join(solver.engine.text(v) for v in row)
                              for row in rows[:SHOWN_TUPLES])
            more = "" if len(rows) <= SHOWN_TUPLES else ", …"
            lines.append(f"  {', '.join(p.text for p in c.paths)}: "
                         f"{len(rows)} tuple(s) — {shown}{more}")
    if result.dropped:
        lines += ["", mctx("{count} relation(s) hold their tuples on the "
                           "control grids too, so they do not read the "
                           "input").format(count=result.dropped)]
    if result.unrun:
        lines += ["", mctx("the runs on these control grids give no result, "
                           "so the control grids leave no relation out:")]
        lines += ["  " + mctx("control grid {i}: {error}").format(
            i=u.index, error=failure_text(u.failure)) for u in result.unrun]
    return lines


# The determination plan


def verdict_text(v: Verdict | Enumerable) -> str:
    """A proposer's verdict, or a domain, as the plan prints it."""
    match v:
        case Exact():
            return "exact"
        case Narrowed(count=n):
            return f"narrowed({n})"
        case Open():
            return "open"
        case Missed():
            return "missed"
        case Empty():
            return "empty"
        case Superset(extra=n):
            return f"superset(+{n})"
        case Partial():
            return "partial"
        case Enumerable(count=n):
            return f"enumerable({n})"


type Printed = Callable[[str], str]
"""The name a plan line prints for a parameter (`printed_name`)."""


def printed_name(solver: Solver) -> Printed:
    """A RIGID chart's placed relation, the name a `Determine` relation
    mirrors, for the chart, and its own name for any other parameter."""
    placed = {chart: n for n, chart in rigid_charts(solver).items()}
    return lambda name: placed.get(name, name)


def _subject_text(subject: Subject, printed: Printed) -> str:
    if isinstance(subject, KeyedTable):
        return (f"{_value_text(subject.child, printed)}+"
                f"{_value_text(subject.parent, printed)}")
    return _value_text(subject, printed)


def _value_text(v: PlanValue, printed: Printed) -> str:
    """A parameter's printed name, and for its value at a case, the
    case's."""
    if isinstance(v, str):
        return printed(v)
    return under_case(printed(v.parameter), v.name)


def _settled_note(settled: Settled, types: Sequence[str], solver: Solver
                  ) -> str:
    """What a covered line says of a parameter's values in the joint
    enumeration, rows of `types`: `pairs-exact` with the value where the
    train pairs leave one value, `pairs-ambiguous(n)` where they leave n,
    whose values the `JUDGE_FREE` section lists, and no verdict where a
    value is unjudged."""
    surviving = rows_text(settled.surviving, types, solver)
    if not settled.unjudged:
        if len(settled.surviving) == 1:
            return f"pairs-exact: {surviving}"
        return f"pairs-ambiguous({len(settled.surviving)})"
    unjudged = rows_text(settled.unjudged, types, solver)
    if not settled.surviving:
        return mctx("unjudged, since a run timed out: {unjudged}").format(
            unjudged=unjudged)
    return mctx("surviving: {values}; unjudged, since a run timed out: "
                "{unjudged}").format(values=surviving, unjudged=unjudged)


def _by_parameter(values: Sequence[PlanValue],
                  note: Callable[[PlanValue], str], form: str,
                  printed: Printed) -> list[str]:
    """One item per parameter among `values` (`by_parameter`): a parameter's
    one value with its `note`, and a parameter that stores a value per
    case in `form`, with each case's name and its value's `note`."""
    def noted(name: str, v: PlanValue) -> str:
        return " ".join(x for x in (name, note(v)) if x)

    return [noted(printed(p), p) if vs is None else form.format(
        param=printed(p),
        cases=", ".join(noted(v.name, v) for v in vs))
        for p, vs in by_parameter(values).items()]


def _over_lines(settle: Sequence[tuple[PlanValue, Candidates]],
                printed: Printed) -> list[str]:
    """One item per parameter over the enumeration limit, with its
    candidate count (`by_parameter`); a parameter that stores a value per case
    with the product of its cases' counts and each case's count."""
    counts = {p: c.count for p, c in settle}
    return [f"{printed(p)}({counts[p]})" if vs is None else
            f"{printed(p)}({math.prod(counts[v] for v in vs)}: "
            + ", ".join(f"{v.name} {counts[v]}" for v in vs) + ")"
            for p, vs in by_parameter(p for p, _c in settle).items()]


def _make_run(failure: RunFailure) -> str:
    """The action that closes a plan sentence on a run that gave no
    result, with the run's failure."""
    return mctx("; make the run give a result: {error}").format(
        error=failure_text(failure))


JUDGE_FREE: Annotated[str, quotes(
    "procedure.md", "Determine",
    "store a value it reports for a parameter beyond the stored values only "
    "where the concept leaves that parameter's value free")] \
    = mctx("judge whether the concept leaves the value free")

PLAN_HELP = mctx("""
    - Each entry under `write a determination relation:` is a value that needs a determination relation, with the rows each case needs, and the note beside it gives why.
    - `<n> of <m> joint assignments of the enumerated parameters reproduce every train pair`: of the `m` joint assignments of the parameters that their own domain settles, `n` give every train pair's output.
    - The verdicts, which a covered line gives for its best proposer and `--verdicts` appends for each proposer:
        - `exact`: the proposal is the stored value.
        - `narrowed(<n>)`: a one-column proposal that holds the stored value and is smaller than the column's domain, of `n` candidates, the non-empty subsets of the proposal for a multi-fact value.
        - `open`: a one-column proposal that holds the stored value and is no smaller than the domain.
        - `missed`: a proposal that leaves out part of the stored value, or a table proposal none of whose rows is stored.
        - `empty`: a table proposal that holds no row.
        - `superset(+<n>)`: a table proposal that holds every stored row and `n` more.
        - `partial`: a table proposal that holds some stored rows and leaves out others.
        - `enumerable(<n>)`: a single-fact parameter's own value domain, of `n` values.
    - A covered line gives, after the verdict, for an enumerated parameter, what the train pairs leave of its values:
        - `pairs-exact`: one value, which follows.
        - `pairs-ambiguous(<n>)`: `n` values, which the `{judge_free}:` section lists.
    """).format(judge_free=JUDGE_FREE)
"""The `determination-plan` command's help: what the plan's lines and
verdict words mean, kept beside the code that prints them."""


def render_determination_plan(solver: Solver, result: PlanResult,
                              verdicts: bool = False) -> list[str]:
    """The plan's sections; with `verdicts`, each proposer's verdict on
    each parameter after them."""
    if isinstance(result, ProbeFails):
        return [mctx("the proposer probe gives no result: {error}").format(
            error=failure_text(result.failure))]
    if isinstance(result, NoCases):
        return [mctx("no value a parameter stores per case is read, and "
                     "this plan is not made, since {failed}").format(
                         failed=CASES_RUN_FAILED)
                + _make_run(result.failure)]
    types = dict(result.types)
    printed = printed_name(solver)

    def shown_of(param: PlanValue) -> Callable[[Row], str]:
        return lambda r: row_text(r, types[param], solver)

    joint = result.joint
    baseline = joint if isinstance(joint, TimedOut) else None
    enumerated = joint if isinstance(joint, Joint) else None
    surviving = dict(enumerated.values) if enumerated else {}
    differing = result.differing
    classes = classify(result.results, result.determined, differing)
    determine, settle, exact = classes.determine, classes.settle, \
        classes.exact
    product = math.prod(v.count for _, v in settle)
    over = product > ENUMERATION_LIMIT
    covered = sorted(exact + ([] if over else [p for p, _ in settle]),
                     key=value_order)
    by_subject = {r.subject: r for r in result.results}
    lines: list[str] = []

    def section(header: str, items: list[str], note: str = "") -> None:
        if not items:
            return
        if lines:
            lines.append("")
        lines.append(f"{header}:")
        if note:
            lines.append(note)
        lines.extend(f"  {i}" for i in items)

    def best_of(param: PlanValue) -> tuple[str, Covering] | None:
        best = covering(by_subject[param])
        if best is None:
            for r in result.results:
                t = r.subject
                if isinstance(t, KeyedTable) and param in (t.child, t.parent):
                    best = covering(r)
        return best

    def covered_note(param: PlanValue) -> str:
        best = best_of(param)
        if best is None:
            return ""
        note = f"{best[0]} {verdict_text(best[1])}"
        if param in surviving:
            settled = _settled_note(surviving[param], types[param], solver)
            note += f", {settled}"
        return f"({note})"

    def state(param: PlanValue) -> str:
        """A value's state in a relation to write: where its parameter is
        determined, whether the relation gives it; else its cover, which
        a parameter's one value, listed there for want of one, omits."""
        if parameter_of(param) in result.determined:
            return (mctx("differs from its stored rows")
                    if isinstance(differing, frozenset)
                    and param in differing else mctx("determined"))
        note = covered_note(param)
        if note:
            return mctx("covered {note}").format(note=note)
        return mctx("covered by no proposer") \
            if isinstance(param, AtCase) else ""

    open_valued = [p for p in sorted(surviving, key=value_order)
                   if not surviving[p].unjudged and surviving[p].extras()]
    unjudged = baseline is not None \
        or not isinstance(differing, frozenset) \
        or any(s.unjudged for s in surviving.values())
    moved = result.moved
    if (not determine and not over and not result.embedded
            and not open_valued and not unjudged and not moved
            and not covered):
        lines.append(mctx("no actions"))
    section(mctx("write a determination relation"),
            _by_parameter(determine, state, mctx(
                "{param}, giving the rows of each case: {cases}"), printed))
    if isinstance(moved, tuple):
        section(MOVED, [mctx("{param} at witness `{witness}`").format(
            param=printed(m.parameter), witness=m.witness) for m in moved])
    else:
        lines += [""] if lines else []
        lines.append(MOVED_UNKNOWN + _make_run(moved))
    section(JUDGE_FREE,
            [f"{_value_text(p, printed)}: " + _also_admits(
                surviving[p].stored, surviving[p].extras(), types[p], solver)
             for p in open_valued])
    if over:
        section(mctx("over the enumeration limit ({joint} > {limit}); "
                     "determine the parameters simplest to determine until "
                     "the product of the remaining candidate counts goes "
                     "under the limit").format(
            joint=product, limit=ENUMERATION_LIMIT),
            _over_lines(settle, printed))
    section(mctx("determined"), [printed(p)
                                 for p in by_parameter(classes.done)])
    if not isinstance(differing, frozenset):
        section(mctx("the determination run gives no result, so whether "
                     "these determination relations give the stored values "
                     "is not known") + _make_run(differing),
                [printed(p) for p in by_parameter(classes.unknown)])
    section(mctx("the value is covered on this task's examples; write a "
                 "determination relation for each value here that a "
                 "proposer derives from a fact other than the one the "
                 "concept derives it from"),
            _by_parameter(covered, covered_note, "{param}: {cases}",
                          printed))
    if surviving and enumerated is not None:
        lines.append(mctx("{survived} of {tried} joint assignments of the "
                          "enumerated parameters reproduce every train "
                          "pair").format(survived=enumerated.survived,
                                         tried=enumerated.tried))
    if enumerated is not None and enumerated.timed_out:
        lines.append(mctx("{count} joint assignment(s) whose run timed "
                          "out:").format(count=len(enumerated.timed_out)))
        lines += [
            "  " + ", ".join(f"{_value_text(n, printed)}={shown_of(n)(r)}"
                             for n, r in a)
            + f": {' '.join(finding_lines(solver, t.finding))}"
            for a, t in enumerated.timed_out]
    if baseline is not None:
        lines += finding_lines(solver, baseline.finding)
    section(mctx("move data from clauses to fact parameters"),
            list(result.embedded))
    if verdicts:
        detail = [f"{_subject_text(r.subject, printed)}: " + ", ".join(
            f"{name} {verdict_text(v)}" for name, v in entries)
            for r in result.results if (entries := r.entries())]
        if detail:
            lines += ["", mctx("each proposer's verdict on each parameter:")]
            lines += [f"  {d}" for d in detail]
    return lines


# The form of the clauses restates Principles' determination: Create
# a6c6527b222939b7c and Refine a87e305652de9cb00 met this action with a test
# that reads `ex_in` and `ex_out` together.
MOVED = mctx("change the determination relation so that it reads its value "
             "from the evidence, or keeps each value at which a fact of the "
             "inputs alone, or of the outputs alone, holds, and gives the "
             "stored value with the pair of the witness added to the train "
             "pairs, where it now gives another: the witness stands at the "
             "stored assignment, and its output is the one the concept case "
             "gives there")
MOVED_UNKNOWN = mctx("the determination run with the witnesses' pairs added "
                     "gives no result, so whether they move a determined "
                     "value is not known")


# The sweep


UNIQUE = mctx("{param}: unique = {shown}{mark}{scope}")
SET_SCOPE: Annotated[str, quotes(
    "solver-file.md", "Params",
    "Of a parameter whose value is a set of rows, a case stores one set.")] \
    = mctx("its value is a set of rows, and a case stores one set; {scope}")
UNIQUE_SET = mctx("{param}: unique as a set = {shown}{mark} ({set_scope})")
STORED_SET = mctx("{param}: stored {shown} ({set_scope})")
NOT_PINNED = mctx("the train pairs do not pin {what}")
UNPINNED = mctx("{not_pinned}: single-row changes of it that give every "
                "train output: {count}")
UNCOMPARED = mctx("the cases that read it were not compared, since the time "
                  "limit cut the sweep")
REFUTES = mctx("test refutes {shown}")
NOTED = mctx("{clause} — {note}")
DETERMINED = mctx("the determination picks the stored value")
NARROWER = mctx("the determination keeps fewer values than those at which "
                "the model fits every train pair, the other parameters at "
                "their stored values, whatever the test pairs give")
UNDETERMINED = mctx("a determination from train alone could pick it")
PASSING = mctx("{shown} reproduce the stored outputs on test too")
UNJUDGED = mctx("{shown} did not run on test — the solver fails a test pair "
                "at its stored assignment")
IN_KIND = mctx("{shown} differ from stored in a nominal argument")
BELOW = mctx("{shown} fit and are smaller than stored")
CASES = mctx("{param}: the cases admit different values")
SET_CASES = mctx("the cases differ in which single-row changes of the "
                 "stored set give their train outputs")
NEVER_READS = mctx("{label} never read{s} {param} — move {param} under the "
                   "marker of the cases that read it")
ADMITS = mctx("{label} admit{s} {shown}")
SO = mctx("{clause}, so {then}")
WHOLE_DOMAIN = mctx("the whole domain {shown}")
UNDER = mctx("{param} under {label}")
UNEXERCISED = mctx("the pairs do not exercise {under}")
COMMON = mctx("{shown} serve{s} every case, so {param} needs no case column")
NO_COMMON: Annotated[str, quotes(
    "solver-file.md", "Params",
    "**Case column.** Where the cases that read a relation in Params store "
    "different values of it, the relation takes a case column in the form "
    "of `out`'s, and each fact's case column is the `Choice` value of the "
    "case that stores the fact.")] \
    = mctx("no value is admitted by every case, so each group stores what "
           "it admits under a case column")
UNMARKED = mctx("{line}: {params} {verb} under the marker `{marker}`, "
                "which lists no case; see "
                "[Cases](docs/handbook/solver-file.md#cases)")

MAGNITUDE = frozenset({NUMBER}) | MAGNITUDE_TYPES


def _mag(row: Row, types: Sequence[str]) -> list[int]:
    out: list[int] = []
    for v, t in zip(row, types):
        if t == NUMBER and isinstance(v, int):
            out.append(v)
        elif t in MAGNITUDE_TYPES and isinstance(v, RecordValue):
            out += [abs(x) for x in v.fields if isinstance(x, int)]
    return out


def _peer(e: Row, s: Row, types: Sequence[str]) -> bool:
    """`e` differs from `s` in magnitude arguments alone."""
    return all(e[i] == s[i] for i, t in enumerate(types) if t not in MAGNITUDE)


def _below(e: Row, s: Row, types: Sequence[str]) -> bool:
    em, sm = _mag(e, types), _mag(s, types)
    return (_peer(e, s, types) and all(a <= b for a, b in zip(em, sm))
            and any(a < b for a, b in zip(em, sm)))


def _test_clauses[V](extras: Extras[V], note: str | None,
                     shown: Callable[[list[V]], str]) -> list[str]:
    """The extras' test verdicts, the refuted ones with `note` where it is
    given."""
    parts: list[str] = []
    if refuted := extras.group(OnTest.REFUTED):
        clause = REFUTES.format(shown=shown(refuted))
        parts.append(clause if note is None
                     else NOTED.format(clause=clause, note=note))
    if passing := extras.group(OnTest.PASSED):
        parts.append(PASSING.format(shown=shown(passing)))
    if unjudged := extras.group(OnTest.UNJUDGED):
        parts.append(UNJUDGED.format(shown=shown(unjudged)))
    return parts


def _gap_clauses[V](gaps: Gaps[V] | None, shown: Callable[[list[V]], str]
                    ) -> list[str]:
    if gaps is None:
        return []
    label = ", ".join(f"`{n}`" for n in sorted(p.name
                                                for p in gaps.marker.parts))
    nothing = [v for v, empty in gaps.undefined if empty]
    partial = [v for v, empty in gaps.undefined if not empty]
    parts: list[str] = []
    if nothing:
        parts.append(mctx("the {label} cases are undefined on every train "
                          "pair at {shown}").format(label=label,
                                                    shown=shown(nothing)))
    if partial:
        parts.append(mctx("no {label} case is defined on every train pair "
                          "at {shown}").format(label=label,
                                               shown=shown(partial)))
    return parts


def _timed_clauses[V](solver: Solver, timed: Sequence[tuple[V, TimedOut]],
                      shown: Callable[[V], str]) -> list[str]:
    return [mctx("at {shown}, {timeout}").format(
        shown=shown(v), timeout=" ".join(finding_lines(solver, t.finding)))
        for v, t in timed]


def _swept(solver: Solver, r: ValueSweep | SetSweep | Skipped) -> str:
    """The parameter a sweep line is about: its name, and for a parameter
    that stores a value per case, the case whose value the line gives."""
    if r.case is None:
        return r.parameter
    return under_case(r.parameter, case_name(solver, r.case))


def _scope_clause(r: ValueSweep | SetSweep) -> str | None:
    """How many of a sweep's candidates ran, the values of a value sweep
    or the single-row changes of a set sweep: those nearest the stored
    value (`Near`), or those the time limit left (`Cut`); None where every
    candidate ran."""
    match r.scope:
        case None:
            return None
        case Near(swept=ran, whole=whole):
            cut = ""
        case Cut(ran=ran, whole=whole):
            cut = mctx("cut by the time limit; ")
    swept = mctx("values") if isinstance(r, ValueSweep) \
        else mctx("single-row changes")
    return cut + mctx("{ran} of {whole} {swept} swept").format(
        ran=ran, whole=whole, swept=swept)


def _also_admits(stored: Sequence[Row], extras: Sequence[Row],
                 types: Sequence[str], solver: Solver) -> str:
    """A parameter's stored rows and the values beyond them that the
    train pairs also admit."""
    return mctx("stored {stored}; {not_pinned}: they also admit {shown}"
                ).format(stored=rows_text(stored, types, solver),
                         not_pinned=NOT_PINNED.format(what=mctx("the value")),
                         shown=rows_list(extras, types, solver))


def _value_line(solver: Solver, r: ValueSweep, determined: bool) -> str:
    types = r.types
    clause = _scope_clause(r)
    scope = "" if clause is None else f" ({clause})"

    def one(v: Row) -> str:
        return row_text(v, types, solver)

    def shown(vs: Sequence[Row]) -> str:
        return rows_text(vs, types, solver)

    def listed(vs: Sequence[Row]) -> str:
        return rows_list(vs, types, solver)

    gap_parts = (_gap_clauses(r.gaps, listed)
                 + _timed_clauses(solver, [*r.timed, *r.extras.timed], one))
    if r.admits_stored_alone():
        mark = " ✓" if r.settles() else ""
        if len(set(r.stored)) == 1:
            head = UNIQUE.format(param=_swept(solver, r), shown=shown(r.stored),
                                 mark=mark, scope=scope)
        else:
            head = mctx("{param}: set of {count} = {shown}{mark}{scope}"
                        ).format(param=_swept(solver, r), count=len(set(r.stored)),
                                 shown=listed(r.stored), mark=mark,
                                 scope=scope)
        return "; ".join([head] + gap_parts)
    # A sweep that ran the whole domain holds every value the fit keeps.
    narrower = determined and r.scope is None and bool(r.extras.values)
    note = None if narrower else DETERMINED if determined else UNDETERMINED
    parts = [_also_admits(r.stored, r.extras.values, types, solver),
             *([NARROWER] if narrower else []),
             *_test_clauses(r.extras, note, listed)]
    passing = r.extras.group(OnTest.PASSED)
    if kind := [e for e in passing
                if not any(_peer(e, s, types) for s in r.stored)]:
        parts.append(IN_KIND.format(shown=listed(kind)))
    if below := [e for e in passing
                 if any(_below(e, s, types) for s in r.stored)]:
        parts.append(BELOW.format(shown=listed(below)))
    return f"{_swept(solver, r)}: " + "; ".join(parts + gap_parts) + scope


def _set_text(v: SetValue, types: Sequence[str], solver: Solver) -> str:
    """A set value: its rows (`row_text`) in order (`set_rows`), in
    braces."""
    return "{" + rows_text(set_rows(v), types, solver) + "}"


def _set_line(solver: Solver, r: SetSweep) -> str:
    types = r.types
    scope = _scope_clause(r) or mctx("every single-row change swept")

    def one(v: frozenset[Row]) -> str:
        return _set_text(v, types, solver)

    def many(vs: Sequence[frozenset[Row]]) -> str:
        return "[" + ", ".join(one(v) for v in vs) + "]"

    shown_s = one(frozenset(r.stored))
    gap_parts = (_gap_clauses(r.gaps, many)
                 + _timed_clauses(solver, r.timed, one))
    set_scope = SET_SCOPE.format(scope=scope)
    if r.admits_stored_alone() and not r.cases_differ:
        mark = " ✓" if r.settles() else ""
        return "; ".join([UNIQUE_SET.format(
            param=_swept(solver, r), shown=shown_s, mark=mark,
            set_scope=set_scope)] + gap_parts)
    head = STORED_SET.format(param=_swept(solver, r), shown=shown_s,
                             set_scope=set_scope)
    match r.per_case:
        case SetCases():
            told = _set_cases_parts(solver, r.parameter, r.per_case)
        case Uncompared():
            told = [UNCOMPARED]
        case None:
            told = [UNPINNED.format(
                not_pinned=NOT_PINNED.format(what=mctx("the set")),
                count=r.unpinned)]
    return "; ".join([head, *told] + gap_parts)


@dataclass(frozen=True)
class _CaseGroup:
    """The cases of a per-case line that share a key: the fewest names
    that cover them (`cover`), as printed, and the verb ending that
    agrees with those names."""

    cases: tuple[Case, ...]
    names: tuple[str, ...]

    @property
    def label(self) -> str:
        return names_text(self.names)

    @property
    def s(self) -> str:
        return verb_s(len(self.names))


def _case_groups[K](solver: Solver, keyed: Sequence[tuple[Case, K]]
                    ) -> dict[K, _CaseGroup]:
    """The cases of `keyed` grouped by their key, each group named by its
    cover among all of them."""
    groups: dict[K, list[Case]] = {}
    for c, k in keyed:
        groups.setdefault(k, []).append(c)
    every = [c for c, _k in keyed]
    return {k: _CaseGroup(tuple(cs), tuple(cover(solver, cs, every)))
            for k, cs in groups.items()}


def _group_order[K](groups: dict[K, _CaseGroup], size: Callable[[K], int]
                    ) -> list[K]:
    """The keys of `groups` in the order their parts print: by `size`,
    and then by the names of the group."""
    return sorted(groups, key=lambda k: (size(k), sorted(groups[k].names)))


def _sorted_list(values: Iterable[Row], r: CaseSets[Row],
                 solver: Solver) -> str:
    """A set of a parameter's rows, in order (`row_key`), as a list
    (`rows_list`)."""
    return rows_list(sorted(values, key=row_key), r.types, solver)


def _cases_line(solver: Solver, r: CaseSets[Row]) -> str:
    """Each group of cases with the values it admits (`ADMITS`), and then
    `COMMON` or `NO_COMMON`. A group that admits the whole domain says so
    (`WHOLE_DOMAIN`) where a clause follows its values (`SO`): its
    cases never read the parameter, or the train pairs do not pin the
    parameter under it. Where some value is common, a group that admits more
    than the common values, short of the whole domain, is one the pairs
    do not exercise (`UNEXERCISED`)."""
    groups = _case_groups(solver, r.per_case)
    common = r.common
    parts = [CASES.format(param=r.parameter)]
    for values in _group_order(groups, len):
        g = groups[values]
        label, s = g.label, g.s
        under = UNDER.format(param=r.parameter, label=label)
        if values == r.domain and set(g.cases) <= r.never_read:
            then = NEVER_READS.format(label=label, s=s, param=r.parameter)
        elif common and values == r.domain:
            then = NOT_PINNED.format(what=under)
        elif common and values != common:
            then = UNEXERCISED.format(under=under)
        else:
            then = None
        shown = _sorted_list(values, r, solver)
        if then is not None and values == r.domain:
            shown = WHOLE_DOMAIN.format(shown=shown)
        admits = ADMITS.format(label=label, s=s, shown=shown)
        parts.append(admits if then is None
                     else SO.format(clause=admits, then=then))
    if common:
        parts.append(COMMON.format(shown=_sorted_list(common, r, solver),
                                   s=verb_s(len(common)), param=r.parameter))
    else:
        parts.append(NO_COMMON)
    return "; ".join(parts)


def _set_cases_parts(solver: Solver, parameter: str, r: SetCases
                     ) -> list[str]:
    """Per group of cases that admit as many single-row changes of the
    stored set, that count, the groups by count and then by name."""
    groups = _case_groups(
        solver, [(c, (count, c in r.unread)) for c, count in r.per_case])
    parts = [SET_CASES]
    for key in _group_order(groups, lambda k: k[0]):
        (count, unread), g = key, groups[key]
        part = mctx("under {label}, single-row changes that give the train "
                    "outputs: {count} of {swept}").format(
                        label=g.label, count=count, swept=r.swept)
        if unread:
            part = SO.format(clause=part, then=NEVER_READS.format(
                label=g.label, s=g.s, param=parameter))
        parts.append(part)
    return parts


def giving_text(solver: Solver, g: GivingValues) -> str:
    """The rows a parameter holds at a case that gives no output on a
    train pair, those under which alone the case gives its train outputs,
    the guidance to keep only those at the case unless the parameter's
    value is a set of rows, a judgment the reader makes, and each row
    whose run failed."""
    def one(v: Row) -> str:
        return row_text(v, g.types, solver)

    def listed(vs: Sequence[Row]) -> str:
        return rows_list(vs, g.types, solver)

    case = case_name(solver, g.case)
    parts = [mctx("{param} holds the rows {held} at {case}").format(
        param=g.parameter, held=listed(g.held), case=case)]
    match g.giving:
        case (only,):
            parts.append(mctx(
                "{case} gives its train outputs under {giving} alone; "
                "unless the value of {param} is a set of rows, keep only "
                "that row at {case}").format(
                    giving=one(only), case=case, param=g.parameter))
        case ():
            parts.append(mctx(
                "{case} gives its train outputs under no one of the rows "
                "that ran").format(case=case))
        case _:
            parts.append(mctx(
                "{case} gives its train outputs under each of {giving} "
                "alone; unless the value of {param} is a set of rows, keep "
                "only those rows at {case}").format(
                    giving=listed(g.giving), case=case, param=g.parameter))
    parts += [run_failed(f, mctx("run at {value}").format(value=one(v)))
              for v, f in g.failed]
    return "; ".join(parts)


def _skip_text(solver: Solver, r: Skipped) -> str:
    match r.reason:
        case NotSwept.DERIVED:
            return "derived"
        case NotSwept.NO_FACTS:
            return "0 facts"
        case NotSwept.NON_ENUMERABLE:
            return f"non-enumerable ({', '.join(r.types)})"
        case NotSwept.TIME_LIMIT:
            return "time limit"
        case NotSwept.FAILS_TRAIN:
            return "; ".join(["stored value fails train",
                              *(giving_text(solver, g) for g in r.giving)])
        case RunFailed(failure=failure):
            return run_failed(failure)
        case NoCases(failure=failure):
            return cases_run_failed(failure)
        case TimedOut(finding=finding):
            return " ".join(finding_lines(solver, finding))


def sweep_lines(solver: Solver, entry: SweepEntry,
                determined: frozenset[str]) -> list[str]:
    """One entry's lines: a parameter's, ` ✓` where the sweep settles it,
    and for a value sweep whose bases admit different values, the line of
    each base's values under it; or a marker's that lists no case."""
    match entry:
        case ValueSweep(per_case=per_case):
            return [_value_line(solver, entry,
                                entry.parameter in determined),
                    *([] if per_case is None
                      else [_cases_line(solver, per_case)])]
        case SetSweep():
            return [_set_line(solver, entry)]
        case Skipped():
            return [mctx("{param}: not swept — {detail}").format(
                param=_swept(solver, entry),
                detail=_skip_text(solver, entry))]
        case NoCaseMarker(marker=m, parameters=params):
            return [UNMARKED.format(
                line=line_text(m.line), marker=marker_text(m),
                params=", ".join(f"`{p}`" for p in params),
                verb="are" if len(params) > 1 else "is")]


def render_sweep(solver: Solver, report: SweepReport) -> list[str]:
    """Each entry's lines (`sweep_lines`), in declaration order, then the
    time limit and the seconds the sweep took."""
    return [ln for e in report.entries
            for ln in sweep_lines(solver, e, report.determined)] + [
        mctx("time limit {limit:.0f}s; elapsed {elapsed:.0f}s").format(
            limit=report.time_limit, elapsed=report.elapsed)]
