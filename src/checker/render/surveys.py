"""The surveys' text: one render function per survey result type. A
result's timed-out and failed runs print here, through the finding lines
every command prints them with."""

import math
from collections.abc import Callable, Sequence
from pathlib import Path

import controlled_markdown as nm
from checker.domains import (
    MAGNITUDE_TYPES,
    ColumnDomain,
    column_domain,
    row_key,
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
    ProbeFails,
    Settled,
    Subject,
    Superset,
    Verdict,
    classify,
    covering,
)
from checker.drop_one import DroppedFact, DropOneResult, Fact, TrainFails
from checker.deletions import (
    BaselineFails,
    ColumnName,
    DeletionKind,
    DeletionReport,
    DeletionResult,
    DeletionRow,
    Quote,
    Quoted,
    TypeName,
)
from checker.render import (
    atom_text,
    case_name,
    failure_text,
    finding_lines,
    literal_text,
    marker_text,
    solver_name,
    value_text,
)
from checker.sweep import (
    CaseSets,
    Cut,
    Extras,
    Gaps,
    Near,
    NoCaseMarker,
    NotSwept,
    RunFailed,
    SetSweep,
    Skipped,
    SweepEntry,
    SweepReport,
    ValueSweep,
)
from checker.variants import OnTest, TimedOut
from controlled_markdown import mctx
from engine import AdtValue, RecordValue, Row, Value, checkout
from solver.model import Lib, Solver, has_determine
from solver.vocabulary import NUMBER


def deletion_doc() -> Path:
    """The deletion report's prose, one section per group."""
    return checkout.prompts() / "run_dl.md"


# Deletions


def _head_text(q: Quoted) -> str:
    """A clause's head, with `<= <atom>` for a subsumptive clause."""
    if q.dominating is None:
        return atom_text(q.head)
    return f"{atom_text(q.head)} <= {atom_text(q.dominating)}"


def quote_text(q: Quote) -> str:
    """What a deletion row quotes between backticks: a removed part and
    its clause's head read as two quoted fragments."""
    match q:
        case Quoted(part=None):
            return _head_text(q)
        case Quoted(part=part):
            return (", ".join(literal_text(x) for x in part or ())
                    + f"` in `{_head_text(q)}")
        case ColumnName(relation=r, column=c):
            return f"{r}.{c}"
        case TypeName(name=n):
            return n


def _section(name: str, pad: str = "", **values: object) -> list[str]:
    """One section of the deletion report's prose, each line under
    `pad`."""
    registry = nm.Registry(checkout.ROOT)
    document = registry.load(deletion_doc())
    body = nm.Node(nm.DOCUMENT, source=document.source)
    body.children = list(registry.ids[document.source][name].children)
    text = nm.render(body, registry, values).strip()
    return [pad + line for line in text.split("\n")]


ROW = " " * 4
DETERMINED_CLAUSE = " " + mctx("and no determined value")
"""The `noop` note's clause for a solver with a Determine comp."""
NO_DETERMINE = mctx("the solver has no Determine comp, so no deletion's "
                    "effect on a determined value was checked")


def render_deletions(solver: Solver, result: DeletionResult) -> list[str]:
    """The deletion section, as the audit and `deletions` print it: each
    group's statement, its note and its rows under it, then the rows
    whose run timed out, each with its timeout line; each list in line
    order."""
    if isinstance(result, BaselineFails):
        return _section("baseline-fails")
    if isinstance(result, TimedOut):
        return finding_lines(solver, result.finding)
    report: DeletionReport = result
    judged = report.judged
    name = solver_name(solver)
    rows = sorted(report.rows,
                  key=lambda r: (r.line, r.label, quote_text(r.quote)))

    def entries(group: list[DeletionRow]) -> list[str]:
        return [f"{ROW}- {name}:{r.line}: {r.label} `{quote_text(r.quote)}`"
                for r in group]

    apart = (DeletionKind.UNPROBED_CASE, DeletionKind.UNGROUNDED,
             DeletionKind.UNEXERCISED_CASES, DeletionKind.BOUND_ENUMERATOR)
    noop = [r for r in rows if r.kind not in apart]
    enumerators = [r for r in rows
                   if r.kind == DeletionKind.BOUND_ENUMERATOR]
    unprobed = [r for r in rows if r.kind == DeletionKind.UNPROBED_CASE]
    ungrounded = [r for r in rows if r.kind == DeletionKind.UNGROUNDED]
    unexercised = [r for r in rows
                   if r.kind == DeletionKind.UNEXERCISED_CASES]
    lines: list[str] = []
    if noop:
        lines += _section("noop", count=len(noop), judged=judged,
                          determined=DETERMINED_CLAUSE
                          if has_determine(solver) else "")
        if any(r.kind == DeletionKind.CASE_COLUMN for r in noop):
            lines += _section("case", pad=ROW)
        lines += entries(noop)
    elif not enumerators:
        lines += _section("none", judged=judged)
    if enumerators:
        if lines:
            lines.append("")
        lines += _section("enumerator", count=len(enumerators),
                          judged=judged)
        lines += entries(enumerators)
    if unprobed:
        lines.append("")
        lines += _section(
            "unprobed", count=len(unprobed),
            noun="case column" if len(unprobed) == 1 else "case columns")
        lines += entries(unprobed)
    if ungrounded:
        lines.append("")
        lines += _section(
            "ungrounded", count=len(ungrounded),
            noun="deletion" if len(ungrounded) == 1 else "deletions")
    if unexercised:
        lines.append("")
        lines += _section("unexercised")
        lines += entries(unexercised)
    if report.no_determine:
        lines += ["", NO_DETERMINE]
    if report.timed_out:
        lines.append("")
        lines += _section("timed-out")
        lines += [f"{ROW}- {name}:{t.line}: {t.kind} "
                  f"`{quote_text(t.quote)}`: "
                  f"{' '.join(finding_lines(solver, t.finding))}"
                  for t in sorted(report.timed_out, key=lambda t: (
                      t.line, str(t.kind), quote_text(t.quote)))]
    return lines


# Values as the sweep, drop-one and the determination plan print them


def arg_text(value: Value, type_name: str, lib: Lib) -> str:
    """One column's value: an orientation member by the constant that
    names it, any other value as the solver writes it."""
    if column_domain(type_name, lib) == ColumnDomain.ORIENTATION:
        for member in lib.orientation_types.get(type_name, ()):
            if lib.constants.get(member) == value:
                return member
    return value_text(value)


def row_text(row: Row, types: Sequence[str], lib: Lib) -> str:
    """A row of a parameter, as `(<value>, ...)`."""
    return "(" + ", ".join(arg_text(v, t, lib)
                           for v, t in zip(row, types, strict=True)) + ")"


# Drop-one


SWEEP_NOTE = mctx("an enumerable parameter, so `sweep` can report the same "
                  "drop")


def _fact_text(solver: Solver, f: Fact) -> str:
    return f"{f.parameter}{row_text(f.row, f.types, solver.lib)}"


def render_drop_one(solver: Solver, result: DropOneResult) -> list[str]:
    """The drop-one report: the facts no pair needs, the facts the train
    pairs do not need and the test pairs do, the facts no test pair can
    judge, and each fact whose run timed out."""
    if isinstance(result, TrainFails):
        return [mctx("drop-one baseline fails: stored source does not pass "
                     "train")]
    if isinstance(result, TimedOut):
        return finding_lines(solver, result.finding)
    if not result.tested:
        return [mctx("{solver}: no parameter holds more than one stored "
                     "fact").format(solver=solver_name(solver))]

    def entries(group: list[DroppedFact]) -> list[str]:
        return [f"  {_fact_text(solver, d.fact)}"
                + (f"  — {SWEEP_NOTE}" if d.enumerable else "")
                for d in group]

    noun = "parameter" if result.parameters == 1 else "parameters"
    lines = [mctx("{tested} stored facts across {params} multi-fact "
                  "{noun}").format(tested=result.tested,
                                   params=result.parameters, noun=noun)]
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


def printed(value: Value) -> str:
    """A value as a run prints it: a constructor with no arguments as
    `$Name`."""
    match value:
        case AdtValue(constructor=name, args=()):
            return f"${name}"
        case AdtValue(constructor=name, args=args):
            return f"${name}({', '.join(printed(a) for a in args)})"
        case RecordValue(fields=fields):
            return f"[{', '.join(printed(f) for f in fields)}]"
        case _:
            return value_text(value)


def render_derived_constant(solver: Solver, result: ConstantResult
                            ) -> list[str]:
    """The derived-constant report."""
    name = solver_name(solver)
    match result:
        case NoCandidate():
            return [mctx("{solver}: no relation both reads `in` and feeds "
                         "`out`").format(solver=name)]
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
                        key=lambda c: [p.text for p in c.paths]):
            texts = sorted("\t".join(printed(v) for v in row)
                           for row in c.rows)
            shown = ", ".join(t.replace("\t", ", ")
                              for t in texts[:SHOWN_TUPLES])
            more = "" if len(texts) <= SHOWN_TUPLES else ", …"
            lines.append(f"  {', '.join(p.text for p in c.paths)}: "
                         f"{len(texts)} tuple(s) — {shown}{more}")
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


def _subject_text(subject: Subject) -> str:
    if isinstance(subject, KeyedTable):
        return f"{subject.child}+{subject.parent}"
    return subject


def _settled_note(settled: Settled, shown: Callable[[Row], str]) -> str:
    """What a covered line says of a parameter's values in the joint
    enumeration: `pairs-exact` where the train pairs leave one value,
    `pairs-ambiguous(n)` where they leave n, and no verdict where a value
    is unjudged."""
    surviving = ", ".join(shown(r) for r in settled.surviving)
    if not settled.unjudged:
        verdict = ("pairs-exact" if len(settled.surviving) == 1
                   else f"pairs-ambiguous({len(settled.surviving)})")
        return f"{verdict}: {surviving}"
    unjudged = ", ".join(shown(r) for r in settled.unjudged)
    if not settled.surviving:
        return mctx("unjudged, since a run timed out: {unjudged}").format(
            unjudged=unjudged)
    return mctx("surviving: {values}; unjudged, since a run timed out: "
                "{unjudged}").format(values=surviving, unjudged=unjudged)


def render_determination_plan(solver: Solver, result: PlanResult,
                              verdicts: bool = False) -> list[str]:
    """The plan's sections; with `verdicts`, each proposer's verdict on
    each parameter after them."""
    if isinstance(result, ProbeFails):
        return [mctx("the proposer probe gives no result: {error}").format(
            error=failure_text(result.failure))]
    lib = solver.lib
    types = dict(result.types)

    def shown_of(param: str) -> Callable[[Row], str]:
        return lambda r: row_text(r, types[param], lib)

    joint = result.joint
    baseline = joint if isinstance(joint, TimedOut) else None
    enumerated = joint if isinstance(joint, Joint) else None
    surviving = dict(enumerated.values) if enumerated else {}
    determine, settle, done, exact = classify(result.results,
                                              result.determined)
    product = math.prod(v.count for _, v in settle)
    over = product > ENUMERATION_LIMIT
    covered = sorted(exact + ([] if over else [p for p, _ in settle]))
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

    def covered_line(param: str) -> str:
        best = covering(by_subject[param])
        if best is None:
            for r in result.results:
                t = r.subject
                if isinstance(t, KeyedTable) and param in (t.child, t.parent):
                    best = covering(r)
        if best is None:
            return param
        note = f"{best[0]} {verdict_text(best[1])}"
        if param in surviving:
            note += f", {_settled_note(surviving[param], shown_of(param))}"
        return f"{param} ({note})"

    open_valued = [p for p in sorted(surviving)
                   if not surviving[p].unjudged
                   and len(surviving[p].surviving) > 1]
    unjudged = baseline is not None or any(
        s.unjudged for s in surviving.values())
    if (not determine and not over and not result.embedded
            and not open_valued and not unjudged):
        lines.append(mctx("no actions"))
    section(mctx("write a determination relation"), determine)
    section(mctx("the train pairs leave several values, so record the "
                 "surviving values as the parameter's open values"),
            [f"{p} ({', '.join(shown_of(p)(r) for r in surviving[p].surviving)})"
             for p in open_valued])
    if over:
        section(mctx("over the enumeration limit ({joint} > {limit})").format(
            joint=product, limit=ENUMERATION_LIMIT),
            [f"{p}({v.count})" for p, v in settle])
        if any(isinstance(v, Enumerable) and v.position for _, v in settle):
            lines.append("  " + mctx(
                "A Position parameter's candidates are the cells of the "
                "frame its stored value implies, so its count follows the "
                "frame the parse produces. A Box or Offset parameter's count "
                "follows the largest height or width of the task's grids."))
    section(mctx("determined"), done)
    section(mctx("the value is covered on this task's examples, so no "
                 "determination relation is needed"),
            [covered_line(p) for p in covered])
    if surviving and enumerated is not None:
        lines.append(mctx("{survived} of {tried} joint assignments of the "
                          "enumerated parameters reproduce every train "
                          "pair").format(survived=enumerated.survived,
                                         tried=enumerated.tried))
    if enumerated is not None and enumerated.timed_out:
        lines.append(mctx("{count} joint assignment(s) whose run timed "
                          "out:").format(count=len(enumerated.timed_out)))
        lines += [
            "  " + ", ".join(f"{n}={shown_of(n)(r)}" for n, r in a)
            + f": {' '.join(finding_lines(solver, t.finding))}"
            for a, t in enumerated.timed_out]
    if baseline is not None:
        lines += finding_lines(solver, baseline.finding)
    section(mctx("move data from clauses to fact parameters"),
            list(result.embedded))
    if verdicts:
        detail = [f"{_subject_text(r.subject)}: " + ", ".join(
            f"{name} {verdict_text(v)}" for name, v in entries)
            for r in result.results if (entries := r.entries())]
        if detail:
            lines += ["", mctx("each proposer's verdict on each parameter:")]
            lines += [f"  {d}" for d in detail]
    return lines


# The sweep


UNIQUE = mctx("{param}: unique = {shown}{mark}{scope}")
UNIQUE_SET = mctx("{param}: unique as a set = {shown}{mark} (facts fit only "
                  "together; {scope})")
REFUTES = mctx("test refutes {shown} — {note}")
DETERMINED = mctx("the determination picks the stored value")
UNDETERMINED = mctx("a determination from train alone could pick it")
PASSING = mctx("{shown} reproduce the stored outputs on test too")
UNJUDGED = mctx("{shown} did not run on test — the solver fails a test pair "
                "at its stored assignment")
IN_KIND = mctx("[{shown}] and stored are open values, differing in a nominal "
               "argument")
BELOW = mctx("[{shown}] fit and are smaller than stored")
CASES = mctx("{param}: the cases admit different values")
WHOLE_DOMAIN = mctx("{label} admit{s} the whole domain [{shown}], so {label} "
                    "never read{s} {param} — move {param} under the marker "
                    "of the cases that read it")
UNEXERCISED = mctx("{label} admit{s} [{shown}], so the pairs do not exercise "
                   "{param} under {label}")
UNMARKED = mctx("line {line}: {params} {verb} under the marker `{marker}`, "
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


def _test_clauses[V](extras: Extras[V], undetermined: bool,
                     shown: Callable[[list[V]], str]) -> list[str]:
    parts: list[str] = []
    if refuted := extras.group(OnTest.REFUTED):
        parts.append(REFUTES.format(
            shown=shown(refuted),
            note=UNDETERMINED if undetermined else DETERMINED))
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


def _value_line(solver: Solver, r: ValueSweep, undetermined: bool) -> str:
    types, lib = r.types, solver.lib
    match r.scope:
        case Near(swept=swept, whole=whole):
            scope = " " + mctx("(swept single-column changes; {swept} of "
                               "{whole} values)").format(swept=swept,
                                                         whole=whole)
        case Cut(ran=ran, whole=whole):
            scope = " " + mctx("(cut by the time limit; {run} of {whole} "
                               "values)").format(run=ran, whole=whole)
        case None:
            scope = ""

    def one(v: Row) -> str:
        return row_text(v, types, lib)

    def shown(vs: Sequence[Row]) -> str:
        return ", ".join(one(v) for v in vs)

    gap_parts = (_gap_clauses(r.gaps, lambda vs: f"[{shown(vs)}]")
                 + _timed_clauses(solver, [*r.timed, *r.extras.timed], one))
    if r.admits_stored_alone():
        mark = " ✓" if r.settles() else ""
        if len(set(r.stored)) == 1:
            head = UNIQUE.format(param=r.parameter, shown=shown(r.stored),
                                 mark=mark, scope=scope)
        else:
            head = mctx("{param}: set of {count} = [{shown}]{mark}{scope}"
                        ).format(param=r.parameter, count=len(set(r.stored)),
                                 shown=shown(r.stored), mark=mark,
                                 scope=scope)
        return "; ".join([head] + gap_parts)
    parts = [mctx("stored {shown}").format(shown=shown(r.stored)),
             mctx("train also admits [{shown}]").format(
                 shown=shown(r.extras.values)),
             *_test_clauses(r.extras, undetermined,
                            lambda vs: f"[{shown(vs)}]")]
    passing = r.extras.group(OnTest.PASSED)
    if kind := [e for e in passing
                if not any(_peer(e, s, types) for s in r.stored)]:
        parts.append(IN_KIND.format(shown=shown(kind)))
    if below := [e for e in passing
                 if any(_below(e, s, types) for s in r.stored)]:
        parts.append(BELOW.format(shown=shown(below)))
    return f"{r.parameter}: " + "; ".join(parts + gap_parts) + scope


def _set_line(solver: Solver, r: SetSweep, undetermined: bool) -> str:
    types, lib = r.types, solver.lib
    match r.scope:
        case Near(swept=swept, whole=whole):
            scope = mctx("swept single-row changes; {swept} of {whole} "
                         "sets").format(swept=swept, whole=whole)
        case Cut(ran=ran, whole=whole):
            scope = mctx("cut by the time limit; {run} of {whole} "
                         "sets").format(run=ran, whole=whole)
        case None:
            scope = mctx("swept whole")

    def one(v: frozenset[Row]) -> str:
        return "{" + ", ".join(row_text(x, types, lib)
                               for x in sorted(v, key=row_key)) + "}"

    def many(vs: Sequence[frozenset[Row]]) -> str:
        return "[" + ", ".join(one(v) for v in vs) + "]"

    shown_s = one(frozenset(r.stored))
    gap_parts = (_gap_clauses(r.gaps, many)
                 + _timed_clauses(solver, [*r.timed, *r.extras.timed], one))
    if r.admits_stored_alone():
        mark = " ✓" if r.settles() else ""
        return "; ".join([UNIQUE_SET.format(param=r.parameter, shown=shown_s,
                                            mark=mark, scope=scope)]
                         + gap_parts)
    parts = [mctx("stored {shown} ({scope})").format(shown=shown_s,
                                                     scope=scope),
             mctx("train also admits sets {shown}").format(
                 shown=many(r.extras.values)),
             *_test_clauses(r.extras, undetermined, many)]
    return f"{r.parameter}: " + "; ".join(parts + gap_parts)


def _cases_line(solver: Solver, r: CaseSets) -> str:
    groups: dict[frozenset[Row], list[str]] = {}
    for label, values in sorted((case_name(solver, c), v)
                                for c, v in r.per_case):
        groups.setdefault(values, []).append(label)
    order = sorted(groups.items(), key=lambda g: (len(g[0]), sorted(g[1])))
    least = order[0][0]
    parts = [CASES.format(param=r.parameter)]
    for values, cases in order:
        label = ", ".join(cases)
        s = "" if len(cases) > 1 else "s"
        shown = ", ".join(row_text(v, r.types, solver.lib)
                          for v in sorted(values, key=row_key))
        if values == r.domain:
            parts.append(WHOLE_DOMAIN.format(label=label, s=s, shown=shown,
                                             param=r.parameter))
        elif values != least:
            parts.append(UNEXERCISED.format(label=label, s=s, shown=shown,
                                            param=r.parameter))
        else:
            parts.append(mctx("{label} admit{s} [{shown}]").format(
                label=label, s=s, shown=shown))
    return "; ".join(parts)


def _skip_text(solver: Solver, r: Skipped) -> str:
    match r.reason:
        case NotSwept.NON_ENUMERABLE:
            return f"non-enumerable ({', '.join(r.types)})"
        case NotSwept():
            return r.reason.value
        case RunFailed(failure=failure):
            return mctx("the run failed: {error}").format(
                error=failure_text(failure))
        case TimedOut(finding=finding):
            return " ".join(finding_lines(solver, finding))


def sweep_line(solver: Solver, entry: SweepEntry,
               determined: frozenset[str]) -> str:
    """One entry's line: a parameter's, ` ✓` where the sweep settles it,
    or a marker's that lists no case."""
    match entry:
        case ValueSweep():
            return _value_line(solver, entry,
                               entry.parameter not in determined)
        case SetSweep():
            return _set_line(solver, entry, entry.parameter not in determined)
        case CaseSets():
            return _cases_line(solver, entry)
        case Skipped():
            return mctx("{param}: not swept — {detail}").format(
                param=entry.parameter, detail=_skip_text(solver, entry))
        case NoCaseMarker(marker=m, parameters=params):
            return UNMARKED.format(
                line=m.line, marker=marker_text(m),
                params=", ".join(f"`{p}`" for p in params),
                verb="are" if len(params) > 1 else "is")


def render_sweep(solver: Solver, report: SweepReport) -> list[str]:
    """One line per entry, in declaration order, then the time limit and
    the seconds the sweep took."""
    return [sweep_line(solver, e, report.determined)
            for e in report.entries] + [
        mctx("time limit {limit:.0f}s; elapsed {elapsed:.0f}s").format(
            limit=report.time_limit, elapsed=report.elapsed)]
