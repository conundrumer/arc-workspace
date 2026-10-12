"""The `witness`, `derive`, `store` and `audit` commands: where a solver
and its witness file disagree, and the branches of its stored values."""

import sys
import time
from collections.abc import Callable, Collection, Iterable, Sequence
from pathlib import Path

from checker import Finding, Kind, Runs, fault_findings
from checker.branches.checks import (
    check_color_structure_stored,
    check_stored_or_derived,
    check_two_parameterizations,
)
from checker.branches.witnesses import BuiltBy, unnamed
from checker.derive import Derivation
from checker.render import (
    Section,
    commands,
    exit_code,
    recording,
    render,
)
from checker.render.built import record_lines
from checker.render.derive_block import derive_lines
from checker.render.store_block import store_lines
from checker.render.witness import try_lines
from checker.store.survey import Found
from checker.case_conditions import check_case_conditions
from checker.open_values import check_open_values
from checker.witness import WITNESS_CHECKS
from checker.witness_try import TRY_ID, TryResult, survey_witness_try
from cli import text
from cli.common import (
    LIMITS,
    all_stems,
    command_solver,
    compiles,
    engine,
    failure_lines,
    print_faults,
    written_grids,
)
from cli.witness_file import absent, lined_solver, read_file, target, with_file
from engine import RunFailure, checkout
from solver import witness
from solver.model import DeriveBranch
from solver.names import name as case_name
from solver.form_checks import RecordedForm, recorded_form
from solver.aggregate import Solver
from solver.readers import declaration_of
from solver.problems import OutputForm, VerdictsDisagree, WitnessFileRole
from solver.witness import Entry, Groups, WitnessFile
from souffle import SouffleEngine

# `witness`


def _every_case(runs: Runs, held: Collection[str] | None = None
                ) -> Runs | RunFailure:
    """The runs of the `witness --every-case` form (`Runs.restored`), or,
    with `held`, the names of the cases of the file `--dropped-from`
    names, of its `--dropped-from` form (`Runs.restored_against`): the
    runs themselves where no case is dropped, and the failure of the run
    that enumerates the solver's cases where it fails."""
    restored = runs.restored if held is None \
        else runs.restored_against(held)
    return runs if restored is None else restored


def witness_findings(solver: Solver, runs: Runs, every_case: bool,
                     held: Collection[str] | None = None
                     ) -> list[Finding] | RunFailure:
    """The witness report's findings, for procedure.md under "Witness"
    ("`witness <task_id>` reads the solver against" its witness file): the
    faults, then each witness check, over the runs with `impl_choice` holding every case
    under `every_case` (`_every_case`, with `held`), which adds the case
    conditions.
    Under `every_case`, the failure of the run that enumerates the
    solver's cases, where it fails."""
    if every_case:
        got = _every_case(runs, held)
        if not isinstance(got, Runs):
            return got
        runs = got
    found = fault_findings(solver, runs)
    for check in WITNESS_CHECKS:
        found += check(solver, runs)
    if every_case:
        found += check_case_conditions(solver, runs)
    return found


def _witness_report(eng: SouffleEngine, solver: Solver,
                    given: WitnessFile | None, every_case: bool,
                    runs: Runs | None = None,
                    held: Collection[str] | None = None
                    ) -> tuple[list[str], list[Finding]] | RunFailure:
    """The `@witness` lines, the count of witness grids, and the
    report; the failure of `witness_findings` where it gives one. `runs`
    are the command's runs where it has them already."""
    if runs is None:
        runs = Runs(eng, solver, LIMITS, given=given)
    file = runs.witness_file
    lines = commands.witness_head(
        solver, None if file is None else len(file.entries),
        checkout.shown(witness.path(solver.task_id)))
    findings = witness_findings(solver, runs, every_case, held)
    if not isinstance(findings, list):
        return findings
    return lines + commands.judgment_first(
        commands.indented(solver, Section.WITNESS, findings)), findings


def _held(eng: SouffleEngine, solver: Solver, path: str
          ) -> frozenset[str] | int:
    """The names of the cases of the solver file at `path`
    (`solver.names.name`), as a witness file names them; the exit code,
    with its line, where no solver file of `solver`'s task stands there or
    the run that enumerates its cases fails."""
    other = command_solver(path, eng, task=False)
    if other is None:
        return 2
    if other.task_id != solver.task_id:
        print(text.DROPPED_FROM_TASK.format(task=solver.task_id),
              file=sys.stderr)
        return 2
    if not compiles(eng, other):
        return 1
    got = Runs(eng, other, LIMITS).solver_cases
    if not isinstance(got, tuple):
        print("\n".join(failure_lines(other, got)))
        return 1
    return frozenset(case_name(other, c) for c in got)


def cmd_witness(arg: str | None, file: str | None = None,
                every_case: bool = False,
                witness_file: str | None = None,
                try_path: str | None = None,
                dropped_from: str | None = None) -> int:
    """The witness report of a solver, against the task's witness file,
    `file` in place of it, or `witness_file` read as the task's own; with
    `try_path`, what the grid there would change as a witness; with
    `dropped_from`, the `--every-case` form judging each case the solver
    file there does not hold (`_held`)."""
    if dropped_from is not None and not every_case:
        print(text.DROPPED_FROM_EVERY, file=sys.stderr)
        return 2
    if file is not None and witness_file is not None:
        print(text.BOTH_FILES, file=sys.stderr)
        return 2
    if try_path is not None and (arg is None or file is not None
                                 or every_case):
        print(text.TRY_ALONE, file=sys.stderr)
        return 2
    if arg is None and witness_file is not None:
        print(text.WITNESS_FILE_STEM, file=sys.stderr)
        return 2
    if arg is None and file is None:
        print(text.WITNESS_NEEDS, file=sys.stderr)
        return 2
    if arg is None:
        return _shape_only(Path(str(file)))
    eng = engine()
    solver = command_solver(arg, eng)
    if solver is None:
        return 2
    given: WitnessFile | None = None
    if file is not None:
        path = Path(file)
        if absent(path):
            return 2
        got, problems = read_file(solver, path, WitnessFileRole.GIVEN)
        if got is None or problems:
            print_faults(solver, problems, sys.stdout)
            return 1
        given = got
    elif witness_file is not None:
        lined = lined_solver(solver, Path(witness_file))
        if lined is None:
            return 2
        solver = lined
    if not compiles(eng, solver):
        return 1
    if try_path is not None:
        return _try(eng, solver, try_path)
    held: Collection[str] | None = None
    if dropped_from is not None:
        named = _held(eng, solver, dropped_from)
        if not isinstance(named, frozenset):
            return named
        held = named
    got = _witness_report(eng, solver, given, every_case, held=held)
    if not isinstance(got, tuple):
        print("\n".join(failure_lines(solver, got)))
        return 1
    lines, findings = got
    print("\n".join(lines))
    return exit_code(findings)


def _try(eng: SouffleEngine, solver: Solver, path: str) -> int:
    """`witness --try`: the grid at `path` as a candidate witness
    (`checker.witness_try.survey_witness_try`); nothing is written."""
    grids = written_grids(path, 1, text.TRY_ONE_GRID)
    if grids is None:
        return 2
    got = survey_witness_try(solver, Runs(eng, solver, LIMITS),
                      Entry(TRY_ID, "", grids[0], (), Groups(())))
    if not isinstance(got, TryResult):
        print("\n".join(failure_lines(solver, got)))
        return 1
    print("\n".join(try_lines(solver, got)))
    return 0


def _shape_only(path: Path) -> int:
    """The shape check of a witness file alone, with no solver."""
    if absent(path):
        return 2
    _file, problems = witness.read(path.read_text(), WitnessFileRole.GIVEN)
    if problems:
        eng = engine()
        for p in problems:
            print(commands.shape_problem_line(eng, path, p))
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
    and writes through `witness.put`; None, with its line on stderr, where
    the solver cannot be read or the file is off its shape
    (`with_file`)."""
    solver = command_solver(arg, eng)
    if solver is None:
        return None
    at = target(solver, witness_file)
    if witness_file is None:
        return solver, at
    lined = with_file(solver, at)
    return None if lined is None else (lined, at)


def _unrecorded(found: Iterable[Derivation | Found]
                ) -> list[tuple[Entry, BuiltBy]]:
    """The witnesses a survey built for branches the witness file holds
    no entry for, each with what it was built from."""
    return [(x.built, x.built_by) for x in found
            if x.built is not None and x.built_by is not None
            and not x.entry]


def _built(arg: str, solver: Solver, at: Path,
           built: Sequence[tuple[Entry, BuiltBy]], corpus: bool,
           runs: Runs, kind: Section, writes_lineless: bool) -> int:
    """Each witness a survey built, as `record` prints it, each followed
    by the line that says it was written, after one write of them all;
    over every solver, nothing is written. An entry whose groups hold a
    name that denotes no case of the solver, as where the `store` survey
    built it with a line the solver does not hold, is not written, and its
    line says why. Under `writes_lineless`, as for the `derive` survey,
    the entry built for a branch with no line is written, its names read
    with the line standing, and its line says which line to add. An entry
    whose verdict lines give the judged output (`recorded_form`) is not
    written, since its witness holds that output in place of groups: its
    lines give the `record` command that writes it, on the solver argument
    `arg` of the command, and the input that command reads. The verdict
    lines of a built entry never disagree: its id is a branch's, which
    holds `=`, so no `@witness` line, whose id is a slug, records it, and a
    second line on one branch is a fault that adds no branch."""
    if not built:
        return 0
    if corpus:
        print(commands.CORPUS_READ_ONLY)
    solver_cases = runs.cases_or_none

    def adds_line(by: BuiltBy) -> bool:
        """The survey built the entry with a `@derive` or `@store` line
        the solver does not hold."""
        return any(b not in solver.branches for b in by.solver.branches)

    def lineless(by: BuiltBy) -> bool:
        """The survey built the entry with a line the solver does not hold
        (`adds_line`), and writes it, its names read as the solver will
        read them once the line stands."""
        return writes_lineless and adds_line(by)

    bad = {e.id: unnamed(by.solver, by.cases, e) if lineless(by)
           else unnamed(solver, solver_cases, e) for e, by in built}
    def recorded_of(e: Entry) -> RecordedForm:
        got = recorded_form(solver, e.id)
        if isinstance(got, VerdictsDisagree):
            raise ValueError(f"{solver.stem}: the verdict lines of the built "
                             f"entry `{e.id}` disagree")
        return got

    recorded = {e.id: recorded_of(e) for e, _by in built}

    def writable(e: Entry) -> bool:
        return not bad[e.id] and recorded[e.id].form is OutputForm.GROUPS

    problems = () if corpus else witness.put(
        at, solver.task_id, [e for e, _by in built if writable(e)])
    given = None if at == witness.path(solver.task_id) else at
    for e, by in built:
        of = runs.lined_runs(by.solver).case_count if adds_line(by) \
            else runs.case_count
        lines = ["", *record_lines(e, by.solver, by.cases, of), ""]
        if bad[e.id]:
            lines.append(recording.not_written(
                e.id, bad[e.id], kind,
                adds_line(by)))
        elif recorded[e.id].form is OutputForm.JUDGED:
            lines += recording.judged_unwritten(
                e.id, recorded[e.id].lines, recording.record_command(
                    arg, e, given), e.input)
        elif corpus:
            lines.append(recording.WOULD_RECORD.format(id=e.id))
        elif not problems and lineless(by):
            branch = next(b for b in by.solver.branches
                          if isinstance(b, DeriveBranch)
                          and b not in solver.branches)
            param = solver.params.parameter(branch.parameter)
            if param is None:
                raise ValueError(f"{solver.stem}: a proposed line on no "
                                 f"parameter, `{branch.parameter}`")
            decl = declaration_of(solver.program, param)
            lines.append(recording.wrote_lineless(
                solver.engine, e.id, at, branch.proposer, decl))
        elif not problems:
            lines.append(recording.WROTE.format(id=e.id, path=at))
        print("\n".join(commands.judgment_first(lines)))
    print_faults(solver, problems)
    return 2 if problems else 0


def cmd_derive(arg: str, witness_file: str | None = None,
               corpus: bool = False) -> int:
    """The derivations of the solver's stored parameters, each with its
    witness and the line that records the judgment, then the findings as
    the audit's derive section prints them; each witness it builds is
    written into the witness file as `_built` gives."""
    eng = engine()
    got = _branch_solver(arg, witness_file, eng)
    if got is None:
        return 2
    solver, at = got
    runs = Runs(eng, solver, LIMITS)
    survey = runs.derive_survey
    findings = check_two_parameterizations(solver, runs)
    print("\n".join([
        *commands.judgment_first(derive_lines(solver, survey)), "",
        *commands.judgment_first(commands.indented(solver, Section.DERIVE,
                                                   findings))]))
    return _built(arg, solver, at, _unrecorded(survey.derivations), corpus, runs,
                  Section.DERIVE, True) or exit_code(findings)


def cmd_store(arg: str, witness_file: str | None = None,
              corpus: bool = False) -> int:
    """The relations that hold one value on every input, each with its
    witness and the line that records the judgment; each witness it builds
    is written into the witness file as `_built` gives."""
    eng = engine()
    got = _branch_solver(arg, witness_file, eng)
    if got is None:
        return 2
    solver, at = got
    runs = Runs(eng, solver, LIMITS)
    survey = runs.store_survey
    print("\n".join(store_lines(solver, survey)))
    return _built(arg, solver, at, _unrecorded(f for f in survey.listed
                                          if f.store_branch),
                  corpus, runs, Section.STORE, False)


# `audit`


def cmd_audit(arg: str, witness_file: str | None = None) -> int:
    """The checks of a finished solver: the witness report, the dropped
    cases, the derive and store findings, and the stored facts no input
    exercises (`checker.open_values.check_open_values`), each section
    printed when it completes with the seconds it took on its header
    line; the pass line and the exit code follow those checks. It writes no witness."""
    eng = engine()
    solver = command_solver(arg, eng)
    if solver is None:
        return 2
    if witness_file is not None:
        lined = lined_solver(solver, Path(witness_file))
        if lined is None:
            return 2
        solver = lined
    if not compiles(eng, solver):
        return 1
    runs = Runs(eng, solver, LIMITS)
    first = [True]

    def section[T](name: Section, compute: Callable[[], T],
                   lines: Callable[[T], list[str]]) -> T:
        """Compute one section, then print its header with the seconds it
        took and its lines."""
        began = time.monotonic()
        got = compute()
        body = lines(got)
        head = commands.audit_section(name, time.monotonic() - began)
        print("\n".join(([] if first[0] else [""]) + [head, *body]),
              flush=True)
        first[0] = False
        return got

    def witness_part() -> tuple[list[str], list[Finding]]:
        report = _witness_report(eng, solver, None, False, runs)
        assert isinstance(report, tuple)
        return report

    _lines, found = section(Section.WITNESS, witness_part, lambda r: r[0])

    def unjustified() -> list[Finding] | RunFailure:
        """The dropped cases that fail no case condition, from the runs
        with every case restored."""
        every = _every_case(runs)
        if not isinstance(every, Runs):
            return every
        return [f for f in check_case_conditions(solver, every)
                if f.kind == Kind.DROP_UNJUSTIFIED]

    def dropped_lines(got: list[Finding] | RunFailure) -> list[str]:
        if isinstance(got, list):
            return render(solver, Section.DROPPED_CASES, got)
        return failure_lines(solver, got)

    every = section(Section.DROPPED_CASES, unjustified, dropped_lines)
    dropped = every if isinstance(every, list) else []
    derive = section(
        Section.DERIVE, lambda: check_two_parameterizations(solver, runs),
        lambda fs: commands.indented(solver, Section.DERIVE, fs))
    store = section(
        Section.STORE, lambda: check_stored_or_derived(solver, runs)
        + check_color_structure_stored(solver, runs),
        lambda fs: commands.indented(solver, Section.STORE, fs))
    unexercised = section(
        Section.OPEN_VALUES, lambda: check_open_values(solver, runs),
        lambda fs: commands.indented(solver, Section.OPEN_VALUES, fs))
    return 1 if not isinstance(every, list) \
        else exit_code([*found, *dropped, *derive, *store, *unexercised])
