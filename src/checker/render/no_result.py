"""The text of runs that gave no result: what a failed run reports, and
the line of a run that timed out or failed."""


from checker.finding import AtEntry, Finding, Kind, NoResultPayload, RunKind
from checker.judged import is_timeout
from checker.render.locations import LineForm, line_text, where_text
from checker.render.values import _ticked
from controlled_markdown import mctx
from engine import (
    CompileError,
    CpuLimit,
    Exited,
    RunFailure,
    UndefinedOutput,
    UngroundedVariable,
    WallLimit,
)
from solver import names
from solver.aggregate import Solver
from solver.variant_limits import (
    VARIANT_CPU_FACTOR,
    VARIANT_CPU_FLOOR_SECONDS,
    VariantBound,
)


def failure_text(failure: RunFailure) -> str:
    """What a failed run reports, in one line."""
    match failure:
        case CompileError(line=line, message=message):
            at = "" if line is None else f"{line_text(line)}: "
            return at + message
        case UngroundedVariable(variable=v, line=line):
            at = "" if line is None else " " + mctx(
                "at {line}").format(line=line_text(line))
            return mctx("the variable `{v}` is ungrounded{at}").format(
                v=v, at=at)
        case CpuLimit(seconds=s) | WallLimit(seconds=s):
            return mctx("the run reached its limit of {s:g}s").format(s=s)
        case UndefinedOutput(relations=rels):
            return mctx("the program declares no {rels}").format(
                rels=_ticked([r.text for r in rels]))
        case Exited(code=code, message=message):
            return mctx("the run exits with {code}: {message}").format(
                code=code, message=message)


RUN = mctx("run")
"""A run that `run_failed` names by no kind."""


def run_failed(failure: RunFailure, run: str = RUN) -> str:
    """That the run `run` names failed, with what it reports
    (`failure_text`)."""
    return mctx("the {run} failed: {error}").format(
        run=run, error=failure_text(failure))


CASES_RUN_FAILED = mctx("the run that enumerates the solver's cases failed")


def cases_run_failed(failure: RunFailure) -> str:
    """That the run that enumerates the solver's cases failed
    (`CASES_RUN_FAILED`), with what it reports (`failure_text`)."""
    return f"{CASES_RUN_FAILED}: {failure_text(failure)}"


def _limit(p: NoResultPayload) -> str:
    """The limit a run reached, which a `TIMEOUT` finding's failure
    holds: a variant's CPU limit by the rule that set it, so that the
    same inputs print the same limit."""
    if not is_timeout(p.failure):
        raise ValueError("a run that reached no limit has no limit's seconds")
    match p.bound:
        case VariantBound.MULTIPLE:
            return mctx("{n} times the CPU time of the solver's own "
                        "run").format(n=VARIANT_CPU_FACTOR)
        case VariantBound.FLOOR:
            return f"{VARIANT_CPU_FLOOR_SECONDS:g}s"
        case None:
            return f"{p.failure.seconds:g}s"


def no_result_lines(solver: Solver, f: Finding, p: NoResultPayload,
                     form: LineForm) -> list[str]:
    """The line of a run that gave no result: a timeout, which every
    command prints for a run a limit ended, or a failure."""
    at = where_text(solver, f.where, form)
    if f.kind == Kind.TIMEOUT:
        limit = _limit(p)
        if p.run not in (RunKind.CASE, RunKind.PAIR, RunKind.WITNESS):
            return [mctx("{entry}: the {run} run timed out after {limit}, "
                         "so no finding rests on its outcome").format(
                entry=at, run=p.run.value, limit=limit)]
        if p.case is not None:
            return [mctx("{entry}: case `{case}` timed out after {limit}, "
                         "so no finding rests on its outcome there").format(
                entry=at, case=names.name(solver, p.case), limit=limit)]
        return [mctx("{entry}: the run of the solver's cases timed out "
                     "after {limit}, so no finding rests on their outcomes "
                     "there").format(entry=at, limit=limit)]
    error = failure_text(p.failure)
    kind_run = mctx("{kind} run").format(kind=p.run.value)
    if p.run == RunKind.DROPPED_CASE:
        return [f"{at}: {run_failed(p.failure, kind_run)}"]
    if isinstance(f.where, AtEntry):
        return [mctx("the entry `{entry}` failed: {error}").format(
            entry=at, error=error)]
    if p.case is not None:
        return [mctx("{at}: case `{case}` failed: {error}").format(
            at=at, case=names.name(solver, p.case), error=error)]
    if p.run == RunKind.CASE:
        return [f"{at}: {cases_run_failed(p.failure)}"]
    return [f"{at}: {run_failed(p.failure, kind_run)}"]
