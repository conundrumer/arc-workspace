"""The `run --pairs` command: the reading of a pairs file, and the run of
one solver over its pairs."""

import json
from enum import Enum
import sys
from pathlib import Path

from arc.materialize import DESCRIPTION_KEYS
from arc.task import (
    LIST_SECTION,
    PAIR_SECTIONS,
    Example,
    PairFormError,
    PairSection,
    Probe,
    pair_name,
    read_pair,
    spelled,
)
from checker import Runs
from checker.render import run_pairs
from cli import text
from cli.common import (
    LIMITS,
    compiles,
    engine,
    load_solver,
    missing,
)
from engine.program import as_grid
from solver.model import Case
from solver.outcome import Assignment, Outcome
from solver.solve import outcomes
from solver.pair_runs import CaseOnPair, TaskSection, candidates, matching


class PairsFault(Enum):
    """How a pairs file is off its form, or that it holds no pair."""

    NOT_JSON = "not json"
    BAD_KEY = "bad key"
    NO_FORM = "no form"
    NO_LIST = "no list"
    NONE = "none"
    LIST_OUTPUT = "list output"


class PairsFileError(Exception):
    """A pairs file off its form: the fault and its parts, which
    `_pairs_text` writes."""

    def __init__(self, fault: PairsFault, **parts: object) -> None:
        super().__init__(fault.value)
        self.fault = fault
        self.parts = parts


PAIRS_TEXT = {
    PairsFault.NOT_JSON: text.PAIRS_NOT_JSON,
    PairsFault.BAD_KEY: text.PAIRS_BAD_KEY,
    PairsFault.NO_FORM: text.PAIRS_NO_FORM,
    PairsFault.NO_LIST: text.PAIRS_NO_LIST,
    PairsFault.NONE: text.PAIRS_NONE,
    PairsFault.LIST_OUTPUT: text.PAIRS_LIST_OUTPUT,
}
"""The sentence of each pairs-file fault, from its parts."""


def _pairs_text(e: PairsFileError) -> str:
    return PAIRS_TEXT[e.fault].format(**e.parts)


def _pairs_file(path: Path) -> list[tuple[PairSection, list[Example | Probe]]]:
    """The pairs of a pairs file, per section, each read as a task file's
    pair is (`arc.task.read_pair`): a bare list of pairs is the one
    section `arc.task.LIST_SECTION`, and an object holds the sections a
    task file holds, beside which it may hold the keys that describe a
    task, unread. A pair of the bare list that holds an output is the fault
    `PairsFault.LIST_OUTPUT`: an output is judged against a train or a test
    pair's candidates (`solver.pair_runs.matching`)."""
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise PairsFileError(PairsFault.NOT_JSON, error=e) from None
    if isinstance(data, list):
        found: list[tuple[PairSection, object]] = [(LIST_SECTION, data)]
    elif isinstance(data, dict):
        for key in data:
            if key not in PAIR_SECTIONS and key not in DESCRIPTION_KEYS:
                raise PairsFileError(PairsFault.BAD_KEY, key=key,
                                     sections=spelled(PAIR_SECTIONS))
        found = [(k, data[k]) for k in PAIR_SECTIONS if k in data]
    else:
        raise PairsFileError(PairsFault.NO_FORM,
                             sections=spelled(PAIR_SECTIONS))
    out: list[tuple[PairSection, list[Example | Probe]]] = []
    for section, pairs in found:
        if not isinstance(pairs, list):
            raise PairsFileError(PairsFault.NO_LIST, section=section)
        read = [read_pair(section, i, e) for i, e in enumerate(pairs)]
        if section == LIST_SECTION and any(isinstance(e, Example)
                                           for e in read):
            raise PairsFileError(PairsFault.LIST_OUTPUT,
                                 sections=spelled(PAIR_SECTIONS))
        out.append((section, read))
    if not any(pairs for _, pairs in out):
        raise PairsFileError(PairsFault.NONE)
    return out


def cmd_pairs(arg: str, path: str) -> int:
    """One solver against the pairs of a JSON file in place of the task's.
    A pair without an output prints what each case gives on its input."""
    if missing(arg):
        return 2
    p = Path(path)
    if not p.exists():
        print(text.NO_PAIRS_FILE.format(path=p), file=sys.stderr)
        return 2
    try:
        sections = _pairs_file(p)
    except PairsFileError as e:
        print(f"{p}: {_pairs_text(e)}", file=sys.stderr)
        return 2
    except PairFormError as e:
        print(f"{p}: {e}", file=sys.stderr)
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    if not compiles(eng, solver):
        return 1
    runs = Runs(eng, solver, LIMITS)
    solver_cases = runs.cases
    if not isinstance(solver_cases, tuple):
        print("\n".join(run_pairs.enumeration_failed_lines(
            [pair_name(kind, idx) for kind, pairs in sections
             for idx in range(len(pairs))], solver_cases)))
        return 1 if any(isinstance(e, Example)
                        for _kind, pairs in sections for e in pairs) else 0
    failed = False
    for kind, pairs in sections:
        for idx, e in enumerate(pairs):
            name = pair_name(kind, idx)
            got = outcomes(eng, solver, solver_cases, as_grid(e.input),
                           Assignment(()), LIMITS)
            if isinstance(e, Probe):
                print("\n".join(run_pairs.probe_lines(
                    solver, name, [(c, got[c]) for c in solver_cases])))
                continue
            cases = tuple(_on_pair(c, got[c], TaskSection(kind), e)
                          for c in solver_cases)
            if not run_pairs.passed(cases):
                failed = True
            print("\n".join(run_pairs.pair_lines(solver, name, cases, e)))
    return 1 if failed else 0


def _on_pair(case: Case, o: Outcome, section: TaskSection, ex: Example
             ) -> CaseOnPair:
    """What `case` gives on a pair of `section`, and the candidates its
    grids match, as `solver.pair_runs.pairs` judges a case of the
    solver."""
    return CaseOnPair(case, o, matching(candidates(section, ex), o))
