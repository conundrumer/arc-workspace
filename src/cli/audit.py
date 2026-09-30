"""The `witness`, `derive`, `store` and `audit` commands: where a solver
and its witness file disagree, and the branches of its stored values."""

import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from checker import Finding, Kind, Runs, check_faults
from checker.branches import (
    BuiltBy,
    check_color_structure_stored,
    check_stored_or_derived,
    check_two_parameterizations,
)
from checker.deletions import DeletionReport, survey_deletions
from checker.readable import finding_of
from checker.render import (
    Section,
    commands,
    exit_code,
    failure_text,
    finding_lines,
    pass_line,
    render,
)
from checker.render.branches import derive_lines, record_lines, store_lines
from checker.render.surveys import render_deletions, render_sweep
from checker.sweep import MAX_CANDIDATES, TIME_LIMIT_SECONDS, survey_sweep
from checker.witness import WITNESS_CHECKS, check_case_conditions
from cli import text
from cli.common import (
    LIMITS,
    all_stems,
    compile_failure,
    failed_lines,
    engine,
    load_solver,
    missing,
    no_task,
    shown_path,
)
from cli.record import absent, read_file, target, with_file
from solver import witness
from engine import RunFailure
from solver.model import Solver
from solver.witness import Entry, WitnessFile
from souffle import SouffleEngine

# `witness`


def witness_findings(solver: Solver, runs: Runs, every_case: bool
                     ) -> list[Finding] | RunFailure:
    """The witness report's findings: the faults, then each
    witness check, over the runs with `impl_choice` holding every case
    under `every_case`, which adds the case conditions. Under
    `every_case`, the failure of the run that enumerates the solver's cases,
    where it fails."""
    if every_case:
        restored = runs.restored
        if isinstance(restored, Runs):
            runs = restored
        elif restored is not None:
            return restored
    found = check_faults(solver, runs)
    for check in WITNESS_CHECKS:
        found += check(solver, runs)
    if every_case:
        found += check_case_conditions(solver, runs)
    return found


def _witness_report(eng: SouffleEngine, solver: Solver,
                    given: WitnessFile | None, every_case: bool
                    ) -> tuple[list[str], list[Finding]] | RunFailure:
    """The `@witness` lines, the count of witness grids, and the
    report; the failure of `witness_findings` where it gives one."""
    file = given or solver.witness_file
    lines = commands.witness_head(
        solver, None if file is None else len(file.entries),
        shown_path(witness.path(solver.task_id)))
    runs = Runs(eng, solver, LIMITS, given=given)
    findings = witness_findings(solver, runs, every_case)
    if not isinstance(findings, list):
        return findings
    return lines + commands.indented(solver, Section.WITNESS, findings), findings


def cmd_witness(arg: str | None, file: str | None = None,
                every_case: bool = False,
                witness_file: str | None = None) -> int:
    """The witness report of a solver, against the task's witness file,
    `file` in place of it, or `witness_file` read as the task's own."""
    if file is not None and witness_file is not None:
        print(text.BOTH_FILES, file=sys.stderr)
        return 2
    if arg is None and witness_file is not None:
        print(text.WITNESS_FILE_STEM, file=sys.stderr)
        return 2
    if arg is None and file is None:
        print(text.WITNESS_NEEDS, file=sys.stderr)
        return 2
    if arg is None:
        return _shape_only(Path(str(file)))
    if missing(arg):
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    if no_task(solver):
        return 2
    given: WitnessFile | None = None
    if file is not None:
        path = Path(file)
        if absent(path, creates=False):
            return 2
        got, problems = read_file(solver, path)
        if got is None or problems:
            for p in problems:
                print("\n".join(finding_lines(solver, finding_of(p))))
            return 1
        given = got
    elif witness_file is not None:
        path = Path(witness_file)
        if absent(path, creates=False):
            return 2
        lined = with_file(solver, path)
        if lined is None:
            return 1
        solver = lined
    failure = compile_failure(eng, solver)
    if failure is not None:
        print("\n".join(failed_lines(solver, failure)))
        return 1
    got = _witness_report(eng, solver, given, every_case)
    if not isinstance(got, tuple):
        print(commands.RUN_FAILED.format(error=failure_text(got)))
        return 1
    lines, findings = got
    print("\n".join(lines))
    return 0 if pass_line(Section.WITNESS, findings) is not None else 1


def _shape_only(path: Path) -> int:
    """The shape check of a witness file alone, with no solver."""
    if absent(path, creates=False):
        return 2
    _file, problems = witness.read(path.read_text())
    if problems:
        for p in problems:
            print(commands.shape_problem_line(path, p))
        return 1
    print(commands.WITNESS_FILE_OK)
    return 0


# `derive` and `store`


def derive_or_store(run: Callable[..., int], args) -> int:
    """`derive` or `store` over one solver, or over every solver, where
    the command writes nothing."""
    if args.stem is not None:
        return run(args.stem, args.witness_file)
    if args.witness_file is not None:
        print(text.WITNESS_FILE_NEEDS_STEM, file=sys.stderr)
        return 2
    code = 0
    for s in all_stems():
        print(commands.stem_head(s))
        try:
            code = run(s, corpus=True) or code
        except Exception as e:
            print(commands.UNCAUGHT.format(kind=type(e).__name__, error=e),
                  file=sys.stderr)
            code = 1
        print()
    return code


def _branch_solver(arg: str, witness_file: str | None,
                   eng: SouffleEngine) -> tuple[Solver, Path] | None:
    """The solver of `derive` or `store`, with the witness file it reads
    and writes."""
    if missing(arg):
        return None
    solver = load_solver(arg, eng)
    if no_task(solver):
        return None
    at = target(solver, witness_file)
    if witness_file is not None and absent(at, creates=True):
        return None
    lined = with_file(solver, at) if witness_file is not None else solver
    if lined is None:
        return None
    return lined, at


def _built(solver: Solver, at: Path,
           built: Sequence[tuple[Entry, BuiltBy]], corpus: bool) -> int:
    """Each witness a survey built, as `record` prints it, each followed
    by the line that says it was written, after one write of them all;
    over every solver, nothing is written."""
    if not built:
        return 0
    if corpus:
        print(commands.CORPUS_READ_ONLY)
    problems = () if corpus \
        else witness.put(at, solver.task_id, [e for e, _by in built])
    for e, by in built:
        print("\n".join(record_lines(e, by.solver, by.cases)))
        print()
        if corpus:
            print(commands.WOULD_RECORD.format(id=e.id))
        elif not problems:
            print(commands.WROTE.format(id=e.id, path=at))
    for p in problems:
        print("\n".join(finding_lines(solver, finding_of(p))),
              file=sys.stderr)
    return 2 if problems else 0


def cmd_derive(arg: str, witness_file: str | None = None,
               corpus: bool = False) -> int:
    """The derivations of the solver's stored parameters, each with its
    witness and the line that records the judgment; each witness it builds
    is written into the witness file."""
    eng = engine()
    got = _branch_solver(arg, witness_file, eng)
    if got is None:
        return 2
    solver, at = got
    survey = Runs(eng, solver, LIMITS).derive_survey
    print("\n".join(derive_lines(solver, survey)))
    built = [(d.built, d.built_by) for d in survey.derivations
             if d.built is not None and d.built_by is not None
             and not d.entry]
    return _built(solver, at, built, corpus)


def cmd_store(arg: str, witness_file: str | None = None,
              corpus: bool = False) -> int:
    """The relations that hold one value on every input, each with its
    witness and the line that records the judgment; each witness it builds
    is written into the witness file."""
    eng = engine()
    got = _branch_solver(arg, witness_file, eng)
    if got is None:
        return 2
    solver, at = got
    survey = Runs(eng, solver, LIMITS).store_survey
    print("\n".join(store_lines(solver, survey)))
    built = [(f.built, f.built_by) for f in survey.listed
             if f.built is not None and f.built_by is not None
             and f.store_branch and not f.entry]
    return _built(solver, at, built, corpus)


# `audit`


def cmd_audit(arg: str, time_limit: float = TIME_LIMIT_SECONDS,
              witness_file: str | None = None) -> int:
    """The evidence audits of a finished solver: the sweep, the
    deletions, the witness report, the dropped cases, and the derive and
    store findings. It writes no witness."""
    if missing(arg):
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    if no_task(solver):
        return 2
    if witness_file is not None:
        path = Path(witness_file)
        if absent(path, creates=False):
            return 2
        lined = with_file(solver, path)
        if lined is None:
            return 2
        solver = lined
    failure = compile_failure(eng, solver)
    if failure is not None:
        print("\n".join(failed_lines(solver, failure)))
        return 1
    runs = Runs(eng, solver, LIMITS)
    out: list[str] = [commands.AUDIT_SECTION.format(name="sweep")]
    out += render_sweep(solver, survey_sweep(solver, runs, MAX_CANDIDATES,
                                             time_limit))
    out += ["", commands.AUDIT_SECTION.format(name="deletions")]
    deletions = survey_deletions(solver, runs)
    out += render_deletions(solver, deletions)
    out += ["", commands.AUDIT_SECTION.format(name="witness")]
    report = _witness_report(eng, solver, None, False)
    assert isinstance(report, tuple)
    lines, found = report
    out += lines
    every = witness_findings(solver, runs, True)
    out += ["", commands.AUDIT_SECTION.format(name="dropped cases")]
    if isinstance(every, list):
        dropped = [f for f in every if f.kind == Kind.DROP_UNJUSTIFIED]
        out += render(solver, Section.DROPPED_CASES, dropped)
    else:
        dropped = []
        out.append(commands.RUN_FAILED.format(error=failure_text(every)))
    derive = check_two_parameterizations(solver, runs)
    store = check_stored_or_derived(solver, runs) \
        + check_color_structure_stored(solver, runs)
    out += ["", commands.AUDIT_SECTION.format(name="derive")]
    out += commands.indented(solver, Section.DERIVE, derive)
    out += ["", commands.AUDIT_SECTION.format(name="store")]
    out += commands.indented(solver, Section.STORE, store)
    print("\n".join(out))
    return 1 if not isinstance(deletions, DeletionReport) \
        or not isinstance(every, list) else exit_code([*found, *dropped, *derive, *store])
