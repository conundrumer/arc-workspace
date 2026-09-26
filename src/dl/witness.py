"""Hand-written grids a solver's cases are pinned to.

A witness file holds grids the author built to tell the solver's branch
models apart, each with the outcome every model is expected to give.
solver-file.md states the file's shape, and `dl.models` reads the names a
group gives.

An entry's `assign` field reassigns a `Params` parameter before the run,
so the entry stands at the assignment its `separates` names rather than
at the stored one.

Every held case fits the task, so only witnesses tell two of them apart:
the file's inputs, and for a `@derive` or `@store` branch with no entry of
its name, the witness `derive` or `store` builds for it. The report names
each pair of held cases no witness separates.
`shape_findings` checks a file's shape alone, with no solver, and the
report runs it first.
"""

import fcntl
import json
import os
import re
import subprocess
from collections.abc import Callable, Iterable, Sequence
from collections.abc import Set as AbstractSet
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from itertools import product
from pathlib import Path
from typing import NoReturn, TypeGuard, overload

from arc.jsonio import format_file
from arc.task import load as load_task
from controlled_markdown import mctx
from dl.annotations import (
    DERIVE,
    STORE,
    STORED,
    Branch,
    Claim,
    derive_param,
    merged_blocks,
    read,
    relaxable,
    resolved_claims,
    store_relation,
    witness_blocks,
)
from dl.dlparse import ParseError, parse
from dl.facts import Candidate
from dl.features import case_branches, declares_held, held_cases
from dl.lint import (
    branch_above,
    concept_case,
    unwitnessed_branches,
    witness_line_branches,
)
from dl.models import (
    NO_CHOICE,
    TERM_RE,
    CaseId,
    Cases,
    NO_CASE,
    NO_LINE,
    Forced,
    Space,
    _adts,
    _split,
    camel,
    case_label,
    case_space,
    enumeration,
    model_label,
)
from dl.paths import PROGRAMS_DIR
from dl.render import _grid_lines
from dl.solve import res_out_stem, run_dl_source, solver_file
from dl.souffle import FIRST_ERROR_RE, _pool_workers
from dl.source import (
    Assign,
    Cell,
    _rect_grid,
    assign_grid,
    assigned_source,
    comp_decls,
    expand_macros,
    param_grid_calls,
    with_held_cases,
)

WITNESS_DIR = PROGRAMS_DIR / "witnesses"

UNDEFINED = "undefined"
"""How a report names the outcome of a case whose cells describe no grid,
and of a case that emits nothing at all. The file writes it as `null` and
the code carries it as None."""

WITNESS_OK = "witness: ok"
"""The pass line, printed when no finding fails the check. When findings
that do not fail it stand, the line carries their count."""

DRIFT = "drift"
UNLISTED = "unlisted"
UNRESOLVED = "unresolved"
ANNOTATION = "annotation"
UNSEPARATED = "unseparated"
SUBSUMED = "subsumed"
TIMEOUT = "timeout"
FAILED = "failed"
ASSIGN = "assign"
CONCEPT = "concept"
NEAREST = "nearest"
SEPARATES = "separates"
DROPPED = "dropped"
TASK_ASSIGN = "task-assign"
FAILING = (DRIFT, UNRESOLVED, ANNOTATION, UNSEPARATED, SUBSUMED, TIMEOUT,
           FAILED, ASSIGN, SEPARATES)
"""The kinds that fail the check."""

type Grid = list[list[int]]
type Outcome = Grid | None
@dataclass
class Entry:
    """One witness grid and what the solver is expected to give on it.

    `output` is a grid per case, where None is an undefined outcome, or one
    bare grid, the judged output that every case must differ from. The file
    writes the per-case form as groups, one grid under the cases that give
    it; `_output` spreads a group over its cases.

    `assign` holds replacement `Params` facts per parameter, each row the
    arguments of one fact in the form solver-file.md (Witness file) gives.
    """

    id: str
    separates: str
    input: list[list[int]]
    output: dict[str, Outcome] | list[list[int]] = field(default_factory=dict)
    assign: Assign = field(default_factory=dict)

    @property
    def rejected_output(self) -> bool:
        return isinstance(self.output, list)


@dataclass(frozen=True)
class TimedOut:
    """The outcome of a case whose run timed out on an input. It equals no
    other case's outcome and is no undefined one, so no finding rests on
    it."""

    case: CaseId


type Got = Outcome | TimedOut
"""What a case gives on one input where its run may have timed out."""


class Timeouts:
    """The runs of held cases that timed out, as TIMEOUT findings, once per
    input and case."""

    def __init__(self) -> None:
        self.findings: list[Drift] = []
        self._seen: set[tuple[str, str]] = set()

    def note(self, where: str, case: str,
             err: subprocess.TimeoutExpired) -> None:
        if (where, case) in self._seen:
            return
        self._seen.add((where, case))
        self.findings.append(Drift(
            entry=where, cases=[case] if case else [], expected=None,
            actual=None, kind=TIMEOUT, note=f"{err.timeout:g}"))

    def merge(self, other: "Timeouts") -> None:
        """Take in the findings `other` noted, as if noted here in turn."""
        for f in other.findings:
            key = (f.entry, f.cases[0] if f.cases else "")
            if key not in self._seen:
                self._seen.add(key)
                self.findings.append(f)

    def run(self, source: str, grid: Grid, path: Path,
            where: str) -> list[Candidate] | None:
        """The run of `source` on `grid`, or None when it timed out."""
        try:
            return run_dl_source(source, grid, solver_path=path)
        except subprocess.TimeoutExpired as err:
            self.note(where, "", err)
            return None


@dataclass
class Witness:
    id: str
    entries: list[Entry] = field(default_factory=list)


@dataclass
class Drift:
    """One finding on one entry. `kind` is DRIFT, UNLISTED, UNRESOLVED,
    ANNOTATION, UNSEPARATED, SUBSUMED, TIMEOUT, FAILED, ASSIGN or SEPARATES,
    each the finding the `witness` help text in `dl.cli` describes, or CONCEPT, which
    `witness --file` gives on an entry of a judged output where the concept
    case gives another grid, holding the judged output in `expected` and
    that grid in `actual`, or NEAREST, which `witness --file` gives on an
    entry where the nearest held cases of a name that denotes no case of
    the solver give a grid other than the group's, naming the name in
    `note`, those cases in `cases`, the group's grid in `expected` and
    theirs in `actual`, or TASK_ASSIGN, which `witness --file` gives on an
    entry whose `assign` holds a name that is no constant of the lib and
    that runs at the `assign` of the task's witness file's entry of its
    id, holding in `note` the lines on those names and that `assign`
    (`_entry_or_failure`); a SEPARATES finding names in `cases` a name the
    entry's `separates` text gives that denotes a held case no group of the
    entry lists (`_separates_findings`); a TIMEOUT finding names
    the input in `entry`, the case in `cases` (empty when the run of every
    case the solver states timed out) and the limit in `note`; a FAILED
    finding names the entry in `entry` and the first line of Souffle's error
    in `note`, and an ASSIGN finding the entry and the line on the `assign`
    string in `note`; an UNRESOLVED finding with a `note` names one constructor,
    and `note` holds the names of the nearest held cases under it; one with
    a `line` names cases that the named `@ignore` line at that line excludes
    (`dl.models.CaseSpace.excluded`); an UNSEPARATED
    finding names the two cases in `cases`, and a SUBSUMED finding either
    the branch and its type's first branch, with the count in `note` and,
    when not every case taking the branch is subsumed, the subsumed ones in
    `subsumed`, or, with no `note`, the subsumed case and then the cases
    that subsume it; a finding of either kind that holds pairs in `pairs`
    stands for a group of them, with in `note` where the two cases of each
    pair differ (`_grouped`). A DROPPED finding, which `witness --every-case` gives,
    names a case `impl_choice` drops in `cases`, followed by the case it
    fails the condition against or that no witness separates it from, and
    in `note` UNSEPARATED, SUBSUMPTION, UNDEFINED or nothing, when it fails
    no case condition, or FIT with the index of the train pair in place of
    that case. `entry` is the entry's
    id, followed by the parameters it reassigns, and it is empty when no
    entry answers the line. `cases` names every case
    the finding holds for, which is the cases that give one outcome where
    another is expected, by the names the entry writes. `expected` stands
    for nothing on an UNLISTED or UNRESOLVED finding. An ANNOTATION finding
    reads as `note`."""

    entry: str
    cases: list[str]
    expected: Outcome | None
    actual: Outcome
    kind: str = DRIFT
    rejected_output: bool = False
    note: str = ""
    subsumed: list[str] = field(default_factory=list)
    pairs: list[tuple[str, str]] = field(default_factory=list)
    line: int = 0


def witness_path(task_id: str) -> Path:
    return WITNESS_DIR / f"{task_id}.wit.json"


def _is_groups(v: object) -> TypeGuard[list[dict]]:
    """A list of groups, which is the per-case form the file writes. An
    empty list is a file that names no case; a rejected output is a list of
    rows, so no list stands for both."""
    return isinstance(v, list) and all(isinstance(g, dict) for g in v)


def _keyed(value: dict) -> dict[str, Outcome]:
    """The object form of an entry's `output`, one grid per case, with the
    one case of a solver without a `Choice` keyed by the name the runner
    prints."""
    return {k or NO_CHOICE: v for k, v in value.items()}


def _output(value: object) -> dict[str, Outcome] | list[list[int]]:
    """An entry's `output` as the code carries it: a grid per case, or the
    bare grid a rejected output holds. A group's grid spreads over the cases
    the group names. An object of one grid per case is read as well, which
    is the form the file held before groups. Either form keys the one case
    of a solver without a `Choice` by the name the runner prints."""
    if isinstance(value, dict):
        return _keyed(value)
    if _is_groups(value):
        return {c or NO_CHOICE: g["grid"] for g in value for c in g["cases"]}
    if _is_grid(value):
        return value
    raise ValueError("output: a group per grid, or one rejected output")


def grouped_output(outcomes: dict[str, Outcome]) -> list[dict]:
    """The per-case outcomes as the file writes them: one group per distinct
    grid, naming the cases that give it. The groups follow the order the
    cases come in, and so do the cases within a group."""
    groups: list[dict] = []
    at: dict[str, int] = {}
    for case, grid in outcomes.items():
        key = json.dumps(grid)
        if key not in at:
            at[key] = len(groups)
            groups.append({"cases": [], "grid": grid})
        groups[at[key]]["cases"].append(case)
    return groups


ENTRY_KEYS = {"id", "separates", "input", "output", "assign"}
REQUIRED_KEYS = {"id", "separates", "input", "output"}


def _is_grid(v: object) -> TypeGuard[list[list[int]]]:
    return (isinstance(v, list) and bool(v)
            and all(isinstance(r, list) and r
                    and all(isinstance(c, int) and 0 <= c <= 9 for c in r)
                    for r in v))


GROUP_KEYS = {"cases", "grid"}


def _check_groups(groups: list, fail: Callable[[str, str], None]) -> None:
    held: set[str] = set()
    for i, g in enumerate(groups):
        if set(g) != GROUP_KEYS:
            fail(f"output/{i}", "the keys are `cases` and `grid`")
        cases = g["cases"]
        if not (isinstance(cases, list) and cases
                and all(isinstance(c, str) for c in cases)):
            fail(f"output/{i}/cases", "a list of case names")
        for c in cases:
            if c in held:
                fail(f"output/{i}/cases", f"case {c} is named by two groups")
            held.add(c)
        if g["grid"] is not None and not _is_grid(g["grid"]):
            fail(f"output/{i}/grid", "a grid or null")


def _check_entry(e: object, fail: Callable[[str, str], None]) -> None:
    if not isinstance(e, dict):
        fail("", "an entry is an object")
        return
    if extra := set(e) - ENTRY_KEYS:
        fail("", f"unknown key {sorted(extra)}")
    if missing := REQUIRED_KEYS - set(e):
        fail("", f"missing key {sorted(missing)}")
    for k in ("id", "separates"):
        if not isinstance(e[k], str):
            fail(k, "a string")
    if not _is_grid(e["input"]):
        fail("input", "a grid")
    out = e["output"]
    if isinstance(out, dict):
        for case, g in out.items():
            if g is not None and not _is_grid(g):
                fail(f"output/{case}", "a grid or null")
    elif _is_groups(out):
        _check_groups(out, fail)
    elif not _is_grid(out):
        fail("output", "a group per grid, or one rejected output")
    assign = e.get("assign", {})
    if not isinstance(assign, dict) or not all(
            isinstance(v, list) and all(isinstance(f, list) for f in v)
            for v in assign.values()):
        fail("assign", "a list of facts per parameter")


def _validate(data: object, path: Path) -> None:
    """Raise a ValueError naming the file, the path of the offending value,
    and what the shape asks of it."""
    def fail(where: str, msg: str) -> NoReturn:
        raise ValueError(f"{path}: {where or '(root)'}: {msg}")
    if not isinstance(data, dict) or set(data) != {"id", "witnesses"}:
        fail("", "the keys are `id` and `witnesses`")
    if not isinstance(data["id"], str):
        fail("id", "a string")
    if not isinstance(data["witnesses"], list):
        fail("witnesses", "a list of entries")
    for i, e in enumerate(data["witnesses"]):
        _check_entry(e, lambda where, msg, i=i: fail(
            f"witnesses/{i}" + (f"/{where}" if where else ""), msg))


WITNESS_FILE_OK = "witness file: ok"
"""The pass line of the shape check."""


def _lib_constants() -> set[str]:
    """The names the lib's `#define` tables give. No solver defines a
    constant of its own."""
    from dl.domains import _lib_defines, _lib_record_defines
    return set(_lib_defines()) | set(_lib_record_defines())


def _strings(value: object) -> list[str]:
    """Every string a fact argument holds, at any depth of a record."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def assign_findings(assign: dict, source: str | None = None) -> list[str]:
    """One line per string of an `assign` value, a fact's argument or a
    grid's cell, that is no constant of the lib; Souffle takes such a name
    for a variable and fails on it. With the solver's `source`, also one
    line per key that is no Params relation of the solver, on which Souffle
    fails as well, and one per parameter whose facts have an arity other
    than its Params relation's, and one per grid that the GRID call storing
    its parameter does not take (`_grid_assign_finding`)."""
    decls = ({} if source is None
             else comp_decls(expand_macros(source), "Params"))
    out: list[str] = []
    for param, rows in assign.items():
        if not (isinstance(rows, list)
                and all(isinstance(f, list) for f in rows)):
            continue
        if source is not None and assign_grid(rows, source, param):
            if line := _grid_assign_finding(source, param, rows):
                out.append(line)
            out += _unknown_names(param, rows)
            continue
        types = decls.get(param)
        if source is not None and types is None:
            out.append(mctx("the `assign` key `{param}` is no relation of "
                            "`Params`")
                       .format(param=param))
            continue
        arities = sorted({len(f) for f in rows})
        if types is not None and arities != [len(types)] and rows:
            out.append(mctx("the `assign` value of `{param}` has facts of "
                            "{got} arguments, and the relation `{param}` "
                            "takes {want}")
                       .format(param=param,
                               got=" and ".join(map(str, arities)),
                               want=len(types)))
            continue
        out += _unknown_names(param, rows)
    return out


def _unknown_names(param: str, rows: list) -> list[str]:
    """One line per string of `param`'s `assign` value, a fact's argument
    or a grid's cell, that is no constant of the lib."""
    strings = _strings(rows)
    known = _lib_constants() if strings else set()
    return [mctx("the `assign` value of `{param}` holds `{value}`, which "
                 "is not a lib constant").format(param=param, value=value)
            for value in strings if value not in known]


def _grid_assign_finding(source: str, param: str,
                         grid: list[list[Cell]]) -> str | None:
    """Why the GRID call that stores `param` takes no `grid` in its place,
    or None when it takes it: `param` has several calls, or the call's form
    gives an anchor or an empty cell, which a grid of colors does not, or
    a mask form meets a cell other than 1 and 0."""
    calls = param_grid_calls(source, param)
    if len(calls) != 1:
        return mctx("the `assign` value of `{param}` is a grid, and "
                    "{count} GRID calls store `{param}`, so no one grid "
                    "replaces them; give `{param}` as `Fact[]`") \
            .format(param=param, count=len(calls))
    macro = calls[0][2]
    if "STAMP_" in macro:
        return mctx("the `assign` value of `{param}` is a grid, and the "
                    "`{macro}` call that stores `{param}` takes an anchor, "
                    "which a grid of colors does not give; give `{param}` "
                    "as `Fact[]`") \
            .format(param=param, macro=macro)
    if "SPARSE_" in macro:
        return mctx("the `assign` value of `{param}` is a grid, and the "
                    "`{macro}` call that stores `{param}` takes empty cells, "
                    "which a grid of colors does not give; give `{param}` "
                    "as `Fact[]`") \
            .format(param=param, macro=macro)
    if "MASK_" in macro and any(c not in (0, 1) for r in grid for c in r):
        return mctx("the `assign` value of `{param}` is a grid for the "
                    "`{macro}` call that stores `{param}`, and holds a cell "
                    "other than 1 (a member cell) and 0 (an empty "
                    "cell)").format(param=param, macro=macro)
    return None


def _entry_shape(e: object) -> list[str]:
    """What stands off the shape in one entry, each without its prefix."""
    if not isinstance(e, dict):
        return ["a witness is an object"]
    out = [mctx("missing field `{key}`").format(key=k)
           for k in ("id", "separates", "input", "output") if k not in e]
    if "input" in e and not _rect_grid(e["input"]):
        out.append(mctx("`input` is no rectangular grid of integers 0 to 9"))
    if "output" in e:
        o = e["output"]
        if _is_groups(o):
            seen: set[str] = set()
            for i, g in enumerate(o):
                cases = g.get("cases")
                if "grid" not in g or not isinstance(cases, list):
                    out.append(mctx("group {i} holds no `cases` list and "
                                    "`grid`").format(i=i))
                    continue
                if g["grid"] is not None and not _rect_grid(g["grid"]):
                    out.append(mctx("the `grid` of group {i} is no "
                                    "rectangular grid of integers 0 to 9")
                               .format(i=i))
                for c in cases:
                    if c in seen:
                        out.append(mctx("`{name}` stands in two groups")
                                   .format(name=c))
                    seen.add(c)
        elif not _rect_grid(o):
            out.append(mctx("`output` is neither a list of groups nor a "
                            "rectangular grid of integers 0 to 9"))
    if "assign" in e:
        a = e["assign"]
        if not isinstance(a, dict):
            out.append(mctx("`assign` is no object"))
        else:
            out += [mctx("the `assign` value of `{param}` is neither a list "
                         "of facts nor a grid").format(param=k)
                    for k, v in a.items()
                    if not (isinstance(v, list)
                            and all(isinstance(f, list) for f in v))]
    return out


def shape_findings(data: object) -> list[str]:
    """What stands off a witness file's shape, one line per finding, each
    prefixed with the id of the witness it holds for. A witness without an
    id is named by its place in `witnesses`."""
    if not isinstance(data, dict):
        return [mctx("the file is no object")]
    out = [mctx("missing field `{key}`").format(key=k)
           for k in ("id", "witnesses") if k not in data]
    entries = data.get("witnesses", [])
    if not isinstance(entries, list):
        return out + [mctx("`witnesses` is no list")]
    seen: set[str] = set()
    for i, e in enumerate(entries):
        wid = e.get("id") if isinstance(e, dict) else None
        name = wid if isinstance(wid, str) else f"witnesses/{i}"
        if isinstance(wid, str):
            if wid in seen:
                out.append(mctx("{id}: the id stands on two witnesses")
                           .format(id=wid))
            seen.add(wid)
        out += [f"{name}: {line}" for line in _entry_shape(e)]
    return out


def file_shape(path: Path) -> list[str]:
    """`shape_findings` of the file at `path`, and a finding for a file
    that holds no JSON."""
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as err:
        return [mctx("the file is no JSON: {err}").format(err=err)]
    return shape_findings(data)


def load_witnesses(task_id: str) -> Witness | None:
    """The task's witness file, or None when it has none. A file off the
    shape solver-file.md (Witness file) gives raises a ValueError."""
    path = witness_path(task_id)
    if not path.exists():
        return None
    return load_witness_file(path)


def read_witness_data(task_id: str, path: Path | None = None) -> dict:
    """The task's witness file as JSON, or the file at `path` in its place,
    checked against the shape. A task with no file yet gets the data an
    empty file holds."""
    path = path or witness_path(task_id)
    if not path.exists():
        return {"id": task_id, "witnesses": []}
    data = json.loads(path.read_text())
    _validate(data, path)
    return data


def _grouped_entry(entry: dict) -> dict:
    """The entry with its per-case outcomes written as groups. An entry that
    holds the object form is converted here, so a file returns to one form
    on any write of it."""
    out = entry.get("output")
    if not isinstance(out, dict):
        return entry
    return {**entry, "output": grouped_output(_keyed(out))}


def write_witness_data(task_id: str, data: dict,
                       path: Path | None = None) -> Path:
    """Write the task's witness file, or the file at `path` in its place,
    after the shape check. Every write of a witness file goes through here,
    so one layout stands over the directory: the file's own conventions,
    groups for the per-case outcomes, and every grid one row per line. The
    text goes to a file beside it that then replaces it, so a write that
    stops part way leaves the file as it was."""
    path = path or witness_path(task_id)
    _validate(data, path)
    data = {**data, "witnesses": [_grouped_entry(e)
                                  for e in data["witnesses"]]}
    path.parent.mkdir(parents=True, exist_ok=True)
    text = format_file(data)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return path


def write_entries(task_id: str, path: Path, entries: list[dict]) -> None:
    """Put `entries` into the witness file at `path` (`put_entry`) and write
    it (`write_witness_data`). The file is read and written under a lock on
    its directory, so runs that write one file at the same time each keep
    their entries. A file off the shape raises ValueError."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = os.open(path.parent, os.O_RDONLY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = read_witness_data(task_id, path)
        for entry in entries:
            put_entry(data, entry)
        write_witness_data(task_id, data, path)
    finally:
        os.close(lock)


def put_entry(data: dict, entry: dict) -> None:
    """Put `entry` into a witness file's data: it replaces the entry of its
    id where one stands, and follows the last entry otherwise."""
    for i, held in enumerate(data["witnesses"]):
        if held.get("id") == entry["id"]:
            data["witnesses"][i] = entry
            return
    data["witnesses"].append(entry)


def load_witness_file(path: Path) -> Witness:
    """A witness file at any path, as `load_witnesses` reads one."""
    data = json.loads(path.read_text())
    _validate(data, path)
    return _witness(data)


def _witness(data: dict) -> Witness:
    return Witness(
        id=data["id"],
        entries=[
            Entry(
                id=e["id"],
                separates=e["separates"],
                input=e["input"],
                output=_output(e["output"]),
                assign={k: list(v) for k, v in e.get("assign", {}).items()},
            )
            for e in data["witnesses"]
        ],
    )


def _outcome(c: Candidate) -> Outcome:
    """What a case's candidate gives: its grid, or None, undefined, where it
    has no grid: `out` holds no fact of the case, or its cells conflict,
    leave a cell unwritten, or describe no grid."""
    return (None if (c.error or c.conflicts or c.missing or not c.grid)
            else c.grid)


def case_outcomes(candidates: list[Candidate],
                  resolution: bool) -> dict[CaseId, Outcome]:
    """What each case gives on one grid, in the order the run emits them. A
    case emitting more than one grid keeps the first."""
    out: dict[CaseId, Outcome] = {}
    for c in candidates:
        name = case_label(c.case, resolution)
        got = _outcome(c)
        if name not in out or got is None:
            out[name] = got
    return out


def model_outcomes(candidates: list[Candidate],
                   resolution: bool) -> dict[CaseId, Outcome]:
    """What each case gives on one grid, keyed as `dl.models` spells a
    case, with each constructor's fields kept. A case emitting more than one
    grid keeps the first, and an undefined one."""
    out: dict[CaseId, Outcome] = {}
    for c in candidates:
        name = model_label(c.case, resolution)
        got = _outcome(c)
        if name not in out or got is None:
            out[name] = got
    return out


def concept_outcome(candidates: list[Candidate], resolution: bool,
                    source: str) -> Outcome:
    """What the concept case of `source` gives on one grid; None when it
    emits nothing. The case is keyed as `dl.models` spells it in full, and
    by the runner's label only where the case space spells no concept."""
    space = case_space(source)
    if isinstance(space, Space) and space.concept is not None:
        return model_outcomes(candidates, resolution).get(space.concept)
    concept = concept_case(source)
    if concept is None:
        return None
    return case_outcomes(candidates, resolution).get(concept)


@overload
def held_outcomes(stem: str, space: Cases, ids: Iterable[CaseId],
                  grid: list[list[int]], source: str, timeouts: None = None,
                  where: str = "") -> dict[CaseId, Outcome]: ...


@overload
def held_outcomes(stem: str, space: Cases, ids: Iterable[CaseId],
                  grid: list[list[int]], source: str, timeouts: "Timeouts",
                  where: str = "") -> dict[CaseId, Got]: ...


def held_outcomes(stem: str, space: Cases, ids: Iterable[CaseId],
                  grid: list[list[int]], source: str,
                  timeouts: "Timeouts | None" = None,
                  where: str = "") -> dict[CaseId, Outcome] | dict[CaseId, Got]:
    """What each case of `ids` that takes a `@derive` or `@store` branch
    (`space.runner`) gives on one grid, by its id, at the assignment
    `source` states. The cases that take the same branches, with the same
    stored values, share one run: `source` with each derived parameter at
    the value its proposer gives on the grid, and each stored relation at
    the value found for it at the stored assignment
    (`dl.store.stored_program`). A case gives what its `Choice` case gives
    in that run, and None where a proposer gives no value on the grid. With
    `timeouts`, a case whose run times out is noted there, as on the input
    `where`, and gives TimedOut; without, the timeout is raised. A failed
    run raises its error."""
    from dl.determination_plan import probe_grid
    from dl.source import swap_facts
    from dl.store import _stored_run, stored_program

    path, _task_id = solver_file(stem)
    resolution = res_out_stem(stem)
    groups: dict[tuple, list[CaseId]] = {}
    for c in ids:
        held = space.runner[c]
        key = (tuple(b for b in held.branches if b.kind == DERIVE),
               tuple(id(v) for v in held.values))
        groups.setdefault(key, []).append(c)
    probe: dict[str, set] | None = None
    out: dict[CaseId, Got] = {}
    for (derived, _values), cases in groups.items():
        text: str | None = source
        for b in derived:
            if probe is None:
                probe = probe_grid(grid)
            value = probe.get(b.reading, set())
            if not value:
                text = None
                break
            text = swap_facts(text, b.target, sorted(value))
        stored = list(space.runner[cases[0]].values)
        try:
            if text is None:
                got = None
            elif stored:
                built = stored_program(text, stored)
                got = None if built is None else _stored_run(built, grid,
                                                             path)
            else:
                got = run_dl_source(text, grid, solver_path=path)
        except subprocess.TimeoutExpired as err:
            if timeouts is None:
                raise
            for c in cases:
                timeouts.note(where, c, err)
                out[c] = TimedOut(c)
            continue
        emitted = {} if got is None else model_outcomes(got, resolution)
        for c in cases:
            base = space.runner[c].base
            out[c] = (None if got is None
                      else emitted.get(base)
                      if isinstance(space, Space) or base != space.concept
                      else concept_outcome(got, resolution, source))
    return {c: out[c] for c in ids}


def branch_diverges(stem: str, space: Cases, branch: Branch,
                    grid: list[list[int]], source: str
                    ) -> tuple[CaseId, CaseId] | None:
    """The first held case that takes `branch` and gives, on `grid` at the
    assignment `source` states, an output other than the held case that
    takes its other branches without `branch`, or is defined where that
    case is not, or the reverse, with that other case. None when no such
    case does."""
    pairs: list[tuple[CaseId, CaseId]] = []
    for case, held in space.runner.items():
        if branch not in held.branches:
            continue
        other = space.case_id(held.base, tuple(
            b for b in held.branches if b != branch))
        if other == held.base or other in space.runner:
            pairs.append((case, other))
    if not pairs:
        return None
    path, _task_id = solver_file(stem)
    ids = list(dict.fromkeys(c for pair in pairs for c in pair))
    timeouts = Timeouts()
    plain = any(c not in space.runner for c in ids)
    got = _held_outcomes(
        stem, space, ids, Entry(id="", separates="", input=grid), source,
        timeouts.run(source, grid, path, "") if plain else [],
        res_out_stem(stem), timeouts, "")
    return next(((a, b) for a, b in pairs
                 if not isinstance(got[a], TimedOut)
                 and not isinstance(got[b], TimedOut)
                 and got[a] != got[b]), None)


def drop_findings(space: Cases, kind: str) -> list[tuple[str, str]]:
    """A finding per `@ignore: derive <name>` line, or per `@ignore:
    store <name>` line for `kind` `store`, that excludes no case the runner
    holds (`dl.models.Drop`), as where it stands and what it says."""
    word = "@derive" if kind == DERIVE else "@store"
    out: list[tuple[str, str]] = []
    for drop in space.drops:
        if drop.ignore.kind != kind or not drop.why:
            continue
        where = f"line {drop.ignore.line}"
        name = drop.ignore.name
        if drop.why == NO_LINE:
            text = (mctx("no `{word}` line stands above this line")
                    if kind == DERIVE else
                    mctx("no `{word}` line stands above the relation under "
                         "this line")).format(word=word)
        elif drop.why == NO_CASE:
            text = mctx("`{name}` denotes no case of the solver").format(
                name=name)
        else:
            text = mctx("this line excludes no case: no case the runner "
                        "holds takes the `{word}` line's branch and every "
                        "branch whose name `{name}` contains").format(
                            word=word, name=name)
        out.append((where, text))
    return out


def listed_models(space: Cases,
                  held: list[CaseId] | None) -> dict[str, CaseId]:
    """The cases a witness entry lists, each by its name: each branch model
    of `space`. `held` holds the cases the solver holds, spelled in full,
    and is None when every case is held. A model whose case is not held
    gives way to the held cases that stand for it (`Space.stand_ins`), each
    by its shortest name (`Space.short_name`)."""
    if held is None or not isinstance(space, Space):
        return space.models()
    out: dict[str, CaseId] = {}
    for name, label, _site in space.model_sites():
        for case in space.stand_ins(label, held):
            out.setdefault(name if case == label else space.short_name(case),
                           case)
    return out


def recorded_models(space: Cases,
                    held: list[CaseId] | None) -> dict[str, CaseId]:
    """The cases `record` writes, each by its name: the ones `listed_models`
    names, then each other case the solver holds, by its shortest name
    (`Space.short_name`). `held` is as `listed_models` takes it."""
    out = listed_models(space, held)
    if not isinstance(space, Space):
        return out
    taken = set(out.values())
    for case in space.cases() if held is None else held:
        if case not in taken:
            out.setdefault(space.short_name(case), case)
            taken.add(case)
    return out


def branch_outcomes(space: Cases, candidates: list[Candidate],
                    resolution: bool,
                    held: list[CaseId] | None = None) -> dict[str, Outcome]:
    """What each case `recorded_models` names gives on one grid, by its
    name; None for a case that emits nothing."""
    got = case_outcomes(candidates, resolution) | model_outcomes(
        candidates, resolution)
    return {name: got.get(label)
            for name, label in recorded_models(space, held).items()}


def _label(entry: Entry) -> str:
    """The entry's id, followed by the parameters it reassigns."""
    if not entry.assign:
        return entry.id
    return f"{entry.id} [{', '.join(entry.assign)}]"


type Mismatch = tuple[str, Outcome, Outcome]


def _merged(label: str, rows: Iterable[Mismatch], kind: str = DRIFT,
            rejected: bool = False) -> list[Drift]:
    """One finding per distinct pair of expected and actual outcome, naming
    the cases that give that pair. The findings follow the order the cases
    come in, and so do the cases within a finding."""
    findings: list[Drift] = []
    at: dict[str, int] = {}
    for case, want, got in rows:
        key = json.dumps([want, got])
        if key not in at:
            at[key] = len(findings)
            findings.append(Drift(entry=label, cases=[], expected=want,
                                  actual=got, kind=kind,
                                  rejected_output=rejected))
        findings[at[key]].cases.append(case)
    return findings


def _entry_findings(entry: Entry, space: Cases,
                    emitted: dict[CaseId, Outcome],
                    actuals: dict[CaseId, Outcome],
                    held: set[CaseId],
                    runner: dict[CaseId, Got],
                    full: list[CaseId] | None = None,
                    file: bool = False,
                    kept: list[CaseId] | None = None) -> list[Drift]:
    """The findings on one entry, given what its input produced. `emitted`
    holds the outcome of each case the run emits, spelled with its fields;
    `actuals` holds those and the runner's labels of them, `held` the names
    of the cases the solver states (`_names`), and `runner` the outcomes of
    the cases the runner holds. An entry whose id is a case the runner holds
    need not list that case. `full` holds the cases `impl_choice` holds,
    spelled in full, and is None when the solver declares no
    `impl_choice`; a name whose case it does not hold denotes no case of the
    solver. The entry lists the cases `listed_models` names. With `file`,
    the entry comes from an Analyze file, which lists no case of the
    solver, so it has no UNLISTED finding; and a name that denotes no case
    of the solver has a NEAREST finding where no held case that takes the
    name gives its group's grid, on each of its nearest held cases that
    gives another grid. `kept` holds the cases the solver's own
    `impl_choice` holds under `--every-case`, and a case it does not hold,
    or one that takes a branch at such a case, has no UNLISTED or
    SEPARATES finding."""

    def outcome(case: CaseId) -> Got:
        return runner[case] if case in runner else actuals.get(case)

    label = _label(entry)
    own = space.resolve(entry.id)
    impl = None if full is None else _names(full)
    listed = listed_models(space, full)
    if isinstance(entry.output, list):
        return _merged(label, [
            (case, entry.output, got)
            for case, got in emitted.items()
            if got == entry.output
        ], rejected=True)
    rows: list[Mismatch] = []
    unresolved: list[str] = []
    named: set[CaseId] = set()
    for name, want in entry.output.items():
        case = space.resolve(name)
        if case is None or (impl is not None and case not in runner
                            and case not in impl):
            unresolved.append(name)
            continue
        named.add(case)
        named |= {m for m in listed.values() if case_label(m) == case}
        got = outcome(case)
        if isinstance(got, TimedOut):
            continue
        if got != want:
            rows.append((name, want, got))
    findings = _merged(label, rows)
    plain: list[str] = []
    by_line: dict[int, list[str]] = {}
    for name in unresolved:
        denoted = space.denoted(name)
        lines = space.excluded.get(denoted, ()) if denoted else ()
        for line in lines:
            by_line.setdefault(line, []).append(name)
        if lines:
            continue
        cases = _nearest_cases(name, space, full)
        if cases:
            findings.append(Drift(
                entry=label, cases=[name], expected=None, actual=None,
                kind=UNRESOLVED,
                note=", ".join(f"`{space.short_name(c)}`" for c in cases)))
            if file and not any(
                    outcome(c) == entry.output[name]
                    for c in _taking_cases(name, space, full)):
                drifts = _merged(label, [
                    (space.short_name(c), entry.output[name], got)
                    for c in cases
                    if not isinstance(got := outcome(c), TimedOut)
                    and got != entry.output[name]
                ], kind=NEAREST)
                for d in drifts:
                    d.note = name
                findings += drifts
        else:
            plain.append(name)
    if plain:
        findings.append(Drift(entry=label, cases=plain, expected=None,
                              actual=None, kind=UNRESOLVED))
    findings += [Drift(entry=label, cases=names, expected=None, actual=None,
                       kind=UNRESOLVED, line=line)
                 for line, names in sorted(by_line.items())]
    if not file:
        findings += _merged(label, [
            (name, None, actuals.get(case))
            for name, case in listed.items()
            if case not in named
            and (case in actuals or case in held)
            and (kept is None or case in kept)
        ] + [
            (case, None, got)
            for case, taken in space.runner.items()
            if case not in named and case != own
            and not isinstance(got := runner.get(case), TimedOut)
            and (kept is None or taken.base in kept)
        ], kind=UNLISTED)
    held_names = held if impl is None else impl
    taking = set(space.runner)
    if kept is not None:
        held_names = held_names & _names(kept)
        taking = {c for c in taking if space.runner[c].base in kept}
    findings += _separates_findings(entry, space, full, held_names | taking)
    return findings


_WORD = r"[\w.]+=\w+|[A-Za-z]\w*(?:-[A-Za-z0-9]+)*"
SEPARATES_NAME_RE = re.compile(rf"(?:{_WORD})(?:\s*&\s*(?:{_WORD}))*")
"""A run of words joined by `&`, which may be a name in one of the forms
solver-file.md (Witness file) gives."""


def _separates_names(text: str) -> list[str]:
    """The runs of words in a `separates` text that may be names. A word in
    lower case with no hyphen and no `=`, other than `concept`, is taken for
    prose, unless it stands in an `A & B` name."""
    out: list[str] = []
    for m in SEPARATES_NAME_RE.finditer(text):
        name = m.group(0)
        if ("&" in name or "=" in name or "-" in name or name == "concept"
                or name[0].isupper()) and name not in out:
            out.append(name)
    return out


def line_branch_witness(separates: str, source: str) -> bool:
    """Whether a witness is one of a `@derive` or `@store` line's branch,
    which takes no `@witness` line: its `separates` text names such a
    branch (`CaseSpace.branch_parts`), and names no branch that takes a
    `@witness` line (`witness_line_branches`). `<param>=stored` of a
    `@derive` parameter is its stored value, which is no line's branch."""
    names = _separates_names(separates)
    space = case_space(source)
    parts = [p.strip() for name in names for p in name.split("&")]
    ctors = witness_line_branches(source)
    return (any((named := space.branch_parts(name)) is not None and named[0]
                for name in names)
            and not any(p in ctors or camel(p) in ctors for p in parts))


def _separates_findings(entry: Entry, space: Cases,
                        full: list[CaseId] | None,
                        held: set[CaseId]) -> list[Drift]:
    """A SEPARATES finding per name in the entry's `separates` text that
    denotes a case in `held` and that no group of the entry lists: no group
    writes the name, and no group's name denotes its case, or the nearest
    held cases of a group's name that denotes no case (`_nearest_cases`)
    hold it. An entry whose id is a case the runner holds lists that case.
    A judged output has no groups, so its entry has no such finding."""
    if isinstance(entry.output, list):
        return []
    groups = set(entry.output)
    listed = {entry.id}
    for name in groups:
        case = space.resolve(name)
        if case is not None:
            listed.add(case)
        listed.update(_nearest_cases(name, space, full))
    labels = {case_label(c) for c in listed}
    out: list[Drift] = []
    for name in _separates_names(entry.separates):
        if name in groups:
            continue
        case = space.resolve(name)
        if case is None or case not in held:
            continue
        if case in listed or case_label(case) in listed or case in labels:
            continue
        out.append(Drift(entry=_label(entry), cases=[name], expected=None,
                         actual=None, kind=SEPARATES))
    return out


def _required(name: str, space: Cases,
              full: list[CaseId] | None) -> Forced | None:
    """For a name that is a constructor, or its slug, or such names joined
    by `&`, whose case the solver does not hold: the nodes a case fixes to
    take every constructor the name gives, at the first choice of places
    at which they agree. None for any other name."""
    if full is None or not isinstance(space, Space):
        return None
    places = [space._sites(n.strip()) for n in name.split("&")]
    if not all(places) or space.resolve(name) in full:
        return None
    for combo in product(*places):
        required: Forced = {}
        if all(required.setdefault(n, k) == k
               for site in combo
               for n, k in space.required(site).items()):
            return required
    return None


def _nearest_cases(name: str, space: Cases,
                   full: list[CaseId] | None) -> list[CaseId]:
    """For a name `_required` reads: the nearest held cases that take every
    constructor it gives (`Space.nearest`). For a name of a case that takes
    a branch the runner does not hold: the held cases that stand for it
    (`CaseSpace.stand_ins`). Empty for any other name."""
    parsed = space.parse(name)
    if parsed is not None and parsed[1]:
        case = space.case_id(*parsed)
        return [] if case in space.runner else space.stand_ins(name, full)
    required = _required(name, space, full)
    if required is None:
        return []
    assert isinstance(space, Space) and full is not None
    return space.nearest(required, full)


def _taking_cases(name: str, space: Cases,
                  full: list[CaseId] | None) -> list[CaseId]:
    """For a name `_required` reads: every held case that takes every
    constructor it gives, at the places `_required` reads. For a name of a
    case that takes a branch the runner does not hold: every held case that
    takes its branches, and the constructors the rest of the name gives.
    Empty for any other name."""
    parsed = space.parse(name)
    test = space.branch_test(name)
    if parsed is not None and parsed[1] and test is not None:
        rest = " & ".join(p.strip() for p in name.split("&")
                          if "=" not in p)
        case = space.resolve(rest) if rest else None
        bases = (None if not rest
                 else {case} if case is not None
                 and (full is None or case in full)
                 else set(_taking_cases(rest, space, full)))
        return [c for c, h in space.runner.items()
                if test(h) and (bases is None or h.base in bases)]
    required = _required(name, space, full)
    if required is None:
        return []
    assert isinstance(space, Space) and full is not None
    return [c for c in full
            if (forced := space.nodes(c)) is not None
            and all(forced.get(n) == k for n, k in required.items())]


# The words of the witness grammar, which is what this check reports on. A
# line off another form of the grammar is the lint's finding.
WITNESS_WORDS = frozenset({"witness", "relaxed", "reassigned"})

FOREIGN = "foreign"
"""The plausibility of a witness the generator never produces."""

ANY = "any"
"""The verdict the generator pairs with any case's output, so no case
departs on it."""

CONCEPT = "concept"
"""The verdict that names the concept case."""

OTHER = "other"
"""The verdict of a judged output, which no case gives, so every case
departs on it."""

DERIVED = "derived"
"""The verdict of a `@derive` line that names the case the line holds.
`STORED` names the case of a `@store` line the same way."""


def _params(names: list[str]) -> str:
    """A parameter list as a finding names it."""
    return ", ".join(f"`{n}`" for n in sorted(names)) or "no parameter"


def verdict_cases(verdict: str, space: Cases, held: list[CaseId] | None,
                  own: dict[str, CaseId] | None = None
                  ) -> list[CaseId] | None:
    """The cases a verdict names: the case it denotes, whether or not
    `impl_choice` holds it, as solver-file.md (Witness file) reads a name.
    A case `impl_choice` does not hold is run on a source that holds it
    (`unheld_verdicts`). A name of a case that takes a `@derive` or
    `@store` branch the runner does not hold, which no source holds, names
    the held cases that stand for it (`_nearest_cases`), and so does a name
    in a `Choice` that no name spells in full. `held` holds the cases
    `impl_choice` holds, spelled in full, and is None when the solver
    declares no `impl_choice`. `own` maps the word `derived` or `stored` to
    the case id of the `@derive` or `@store` line the verdict stands on.
    None for `any` and `other`, which name no one case, and empty for a
    verdict that denotes no case the runs give."""
    if verdict in (ANY, OTHER):
        return None
    if own and verdict in own:
        return [own[verdict]]
    case = space.resolve(verdict)
    if case is not None and (held is None or isinstance(space, Space)
                             or case in space.runner
                             or case in _names(held)):
        return [case]
    return _nearest_cases(verdict, space, held)


def _held_names(source: str, cases: list[CaseId]) -> list[CaseId] | None:
    """The cases `impl_choice` holds, spelled in full, as `verdict_cases`
    takes them: `cases`, the cases the runs on the entries found it
    holding, and None when the solver declares no `impl_choice`."""
    return cases if cases and declares_held(source) else None


type VerdictLine = tuple[int, str, str, dict[str, CaseId] | None]
"""A `@witness`, `@derive` or `@store` line's verdict: the line, the
verdict, the id of the entry it stands on, and the map `verdict_cases`
takes as `own`."""


def _verdict_lines(source: str, space: Cases) -> list[VerdictLine]:
    """The verdict of each `@witness`, `@derive` and `@store` line. A
    `@derive` line stands on the entry of its case id, and a `@store` line
    on the entry of `<rel>=stored`."""
    ann = read(source)
    out: list[VerdictLine] = [(w.line, w.verdict, w.id, None)
                              for w in ann.witnesses]
    derived = {b.name for b in space.lines}
    for d in ann.derives:
        param = derive_param(source, d)
        case = CaseId(f"{param}={d.proposer}")
        out.append((d.line, d.verdict, case,
                    {DERIVED: case} if case in derived else None))
    for st in ann.stores:
        rel = store_relation(source, st)
        stored = CaseId(f"{rel}={STORED}")
        out.append((st.line, st.verdict, stored,
                    {STORED: stored} if rel else None))
    return out


def unheld_verdicts(source: str, space: Cases,
                    held: list[CaseId] | None) -> dict[str, list[CaseId]]:
    """By entry id, the `Choice` cases the verdicts on the entry name
    (`verdict_cases`) that `impl_choice` does not hold. `held` is as
    `verdict_cases` takes it."""
    if held is None or not isinstance(space, Space):
        return {}
    plain = set(space.cases())
    names = _names(held)
    out: dict[str, list[CaseId]] = {}
    for _line, verdict, entry, own in _verdict_lines(source, space):
        for c in verdict_cases(verdict, space, held, own) or []:
            if c in plain and c not in names:
                cases = out.setdefault(entry, [])
                if c not in cases:
                    cases.append(c)
    return out


def _verdict_part(space: Cases, entry: Entry, cases: list[CaseId],
                  source: str, path: Path, resolution: bool
                  ) -> tuple[dict[CaseId, Got], list[Drift], Timeouts]:
    """What each case of `cases` gives on the entry's input at the entry's
    assignment, and a FAILED finding when the run fails. `source` is the
    solver's source with `impl_choice` holding those cases
    (`with_held_cases`), as `--every-case` runs a case the solver does not
    hold. A case whose run times out gives TimedOut."""
    timeouts = Timeouts()
    where = _label(entry)
    try:
        got = run_dl_source(assigned_source(source, entry.assign),
                            entry.input, solver_path=path)
    except subprocess.TimeoutExpired as err:
        for c in cases:
            timeouts.note(where, c, err)
        return {c: TimedOut(c) for c in cases}, [], timeouts
    except RuntimeError as err:
        return {}, [Drift(entry=where, cases=[], expected=None, actual=None,
                          kind=FAILED, note=_souffle_error(err))], timeouts
    out = model_outcomes(got, resolution)
    return {c: out.get(c) for c in cases}, [], timeouts


def _departs(verdict: str, case: CaseId, space: Cases,
             held: list[CaseId] | None, got: dict[CaseId, Got] | None
             ) -> bool:
    """A witness line of this verdict shows `case` departing: the verdict is
    `other`, or the output `case` gives on the witness differs from the
    output of each case the verdict names (`verdict_cases`). `got` holds
    what each case gives on the witness, and is None when the line names no
    entry of the file. A verdict that names a constructor without its
    fields names the runner's label, which stands for every case under that
    constructor, `case` among them when that is its label. Where an output
    is unknown, as a run timed out, `case` departs, and the timeout is a
    finding of its own. The verdict `any` names no case, and neither does a
    verdict that denotes no case the runs give, which is a finding of its
    own."""
    if verdict == OTHER:
        return True
    named = verdict_cases(verdict, space, held) or []
    if not named or {case, case_label(case)} & set(named):
        return False
    if got is None:
        return True
    outs = [got.get(c, TimedOut(c)) for c in [case, *named]]
    if any(isinstance(o, TimedOut) for o in outs):
        return True
    return all(o != outs[0] for o in outs[1:])


def _constructors(case: CaseId) -> set[str]:
    """Every constructor a case spelled in full takes, nested ones
    included."""
    return set(re.findall(r"\w+", case))


def _names(cases: Iterable[CaseId]) -> set[CaseId]:
    """The names that denote the given cases: each case spelled in full,
    and its runner's label, which a name of a constructor written without
    its fields resolves to. A case with a nested constructor is spelled with
    parentheses and a runner's label never is, so two cases that differ in a
    nested constructor stay apart."""
    cases = list(cases)
    return set(cases) | {case_label(c) for c in cases}


def _no_witness_note(c: Claim) -> str:
    return mctx("`@{kind} {slug}` is approximated and has no `@witness` "
                "line under its `@approximated:`").format(kind=c.kind,
                                                          slug=c.slug)


def _annotation_findings(source: str, entries: list[Entry],
                         cases: list[CaseId], space: Cases,
                         outcomes: dict[str, dict[CaseId, Got]] | None = None
                         ) -> list[Drift]:
    """Where a solver's `@witness` lines and the witness file disagree: a
    line off the form of the witness grammar, a line that names no entry of
    the file, a `@relaxed` slug the header's claims do not carry, and a
    block whose `@reassigned` parameters are not the entry's `assign` keys.
    An entry that no line names is no finding here. A `@derive`
    line names the entry of its case id, and the derive report reads that
    entry. The verdict of each `@witness`, `@derive` and `@store` line
    resolves in `space` (`verdict_cases`), and one that denotes no case the
    runs give is a finding. A verdict that names held cases in place of its
    own (`verdict_cases`) reads as those cases, which give the branch
    model's grid wherever it is defined; `outcomes` holds what each held
    case, and each case a verdict names, gives on each entry, by the
    entry's id, and the verdict is a finding when those cases give
    different grids on the line's entry.

    An approximated claim is read against the cases as well. A header
    `@approximated:` runs on every case, so each case stands under a witness
    that shows it departing. A case whose branch carries a `@rule` line of
    the claim's slug restates the claim, so the approximation does not run
    on that case and no witness is asked of it."""
    by_id = {e.id: e for e in entries}
    claims = resolved_claims(source)
    slugs = relaxable(claims)
    kinds = {c.slug: c.kind for c in claims}
    held = _held_names(source, cases)
    findings: list[Drift] = []

    def note(entry: str, case: str, text: str) -> None:
        findings.append(Drift(entry=entry, cases=[case] if case else [],
                              expected=None, actual=None, kind=ANNOTATION,
                              note=text))

    def relaxed_notes(where: str, case: str, relaxed: list[str]) -> None:
        """A `@relaxed` slug the header's `@scene` lines do not carry."""
        for slug in relaxed:
            if slug in slugs:
                continue
            held = kinds.get(slug)
            note(where, case,
                 mctx("`@relaxed {slug}` names the `@{held} {slug}` line; "
                      "`@relaxed` names a `@scene` line")
                 .format(slug=slug, held=held)
                 if held else
                 mctx("`@relaxed {slug}` names no line of the header")
                 .format(slug=slug))

    def verdict_note(line: int, verdict: str, entry: str,
                     own: dict[str, CaseId] | None = None) -> None:
        if verdict in (ANY, OTHER):
            return
        named = verdict_cases(verdict, space, held, own)
        if named and (own and verdict in own
                      or space.resolve(verdict) in named):
            return
        if named:
            got = (outcomes or {}).get(entry, {})
            grids = {json.dumps(got[c]) for c in named
                     if c in got and not isinstance(got[c], TimedOut)}
            if len(grids) > 1:
                note(f"line {line}", "",
                     mctx("the output the verdict `{verdict}` denotes on "
                          "this witness is unknown: the runner does not hold "
                          "its case, and the cases it holds that take "
                          "`{verdict}` and differ least from the concept "
                          "case give different grids: {cases}")
                     .format(verdict=verdict, cases=", ".join(
                         f"`{space.short_name(c)}`" for c in named)))
            return
        note(f"line {line}", "",
             mctx("the output the verdict `{verdict}` denotes on this "
                  "witness is unknown: the runner holds no case that takes "
                  "`{verdict}`")
             .format(verdict=verdict)
             if space.resolve(verdict) is not None else
             mctx("the verdict `{verdict}` denotes no case of the solver")
             .format(verdict=verdict))

    ann = read(source)
    for bad in ann.malformed:
        if bad.word in WITNESS_WORDS:
            note(f"line {bad.line}", "", bad.why)
    for line, verdict, entry, own in _verdict_lines(source, space):
        verdict_note(line, verdict, entry, own)
    for a in merged_blocks(ann.witnesses):
        entry = by_id.get(a.id)
        if entry is None:
            note(f"line {a.line}", a.id,
                 mctx("`@witness {id}` names no witness in the file")
                 .format(id=a.id))
        elif sorted(a.reassigned) != sorted(entry.assign):
            note(a.id, a.id,
                 mctx("`@reassigned` names {named}; the witness's `assign` "
                      "names {holds}").format(
                     named=_params(a.reassigned),
                     holds=_params(list(entry.assign))))
        relaxed_notes(a.id, a.id, a.relaxed)
    for d in ann.derives:
        if param := derive_param(source, d):
            relaxed_notes(f"line {d.line}", f"{param}={d.proposer}", d.relaxed)
    for st in ann.stores:
        if rel := store_relation(source, st):
            relaxed_notes(f"line {st.line}", f"{rel}={STORED}", st.relaxed)

    def approximated(c: Claim, want: list[CaseId]) -> None:
        if not c.witnesses:
            note(f"line {c.line}", "", _no_witness_note(c))
            return
        for w in c.witnesses:
            if w.plausibility == FOREIGN:
                note(f"line {w.line}", "",
                     mctx("`@witness {id}` under `@approximated:` of "
                          "`@{kind} {slug}` is `{plausibility}`").format(
                         id=w.id, kind=c.kind, slug=c.slug,
                         plausibility=FOREIGN))
        for case in want:
            if not any(_departs(w.verdict, case, space, held,
                                (outcomes or {}).get(w.id))
                       for w in c.witnesses):
                note(f"line {c.line}", "",
                     mctx("`@{kind} {slug}` is approximated and no witness "
                          "under its `@approximated:` shows case `{case}` "
                          "giving an output other than the verdict's")
                     .format(
                         kind=c.kind, slug=c.slug, case=case))

    restated: dict[str, set[str]] = {}
    for c in ann.branch_claims:
        if c.kind != "rule":
            continue
        name = branch_above(source, c.line)
        if name:
            restated.setdefault(c.slug, set()).add(name)

    def not_restated(slug: str) -> list[CaseId]:
        """The cases the header's approximation still runs on: the ones no
        branch of theirs restates under that slug."""
        names = restated.get(slug, set())
        return [k for k in cases if not names & _constructors(k)]

    for c in ann.claims:
        if c.approximated:
            approximated(c, not_restated(c.slug))
    return findings


def annotation_lines(source: str) -> list[str]:
    """The features of each `@witness` line, one block per line, and
    `no witness lines` when the solver carries none."""
    lines: list[str] = []
    for a in witness_blocks(source):
        lines.append(f"{a.id}: {a.plausibility} {a.verdict}")
        lines += [f"  relaxed: {slug}" for slug in a.relaxed]
        lines += [f"  reassigned: {param}" for param in a.reassigned]
        if a.approximates:
            lines.append(f"  under @approximated: of {a.approximates}")
    return lines or ["no witness lines"]


def _runner_outcomes(stem: str, entry: Entry, space: Cases, source: str,
                     timeouts: Timeouts) -> dict[CaseId, Got]:
    """What each case that takes a branch gives on the entry's input, at
    the entry's assignment, which `source` states (`held_outcomes`)."""
    if not isinstance(entry.output, dict) or not space.runner:
        return {}
    return held_outcomes(stem, space, list(space.runner), entry.input,
                         source, timeouts, _label(entry))


def _stated(stem: str, source: str, grid: list[list[int]],
            choice: list[CaseId]) -> tuple[list[CaseId], list[CaseId]]:
    """The cases the solver states on `grid`, by the runner's label and
    spelled in full. A solver that declares `impl_choice` states the cases
    a run on `grid` finds it holding. Another states `choice`, the cases of
    its `Choice` as `dl.models.held_choice` spells them, which no grid
    changes."""
    if declares_held(source):
        full = held_cases(parse(source), source, grid, full=True) or []
        return list(dict.fromkeys(case_label(c) for c in full)), full
    return case_branches(stem, source, grid), choice


def _held_outcomes(stem: str, space: Cases, held: list[CaseId],
                   entry: Entry, source: str,
                   candidates: list[Candidate] | None, resolution: bool,
                   timeouts: Timeouts, where: str) -> dict[CaseId, Got]:
    """What each held case gives on the entry's input, None for a case that
    emits nothing there. `source` is the source the entry stands at, and
    `candidates` its run on the entry's input, None when that run timed
    out; a case whose run timed out gives TimedOut, and `timeouts` notes it
    as on the input `where`."""
    runner = [c for c in held if c in space.runner]
    plain = [c for c in held if c not in space.runner]
    if candidates is None:
        out: dict[CaseId, Got] = {c: TimedOut(c) for c in plain}
    else:
        got = case_outcomes(candidates, resolution) | model_outcomes(
            candidates, resolution)
        out = {c: got.get(c) for c in plain}
    if runner:
        out |= held_outcomes(stem, space, runner, entry.input, source,
                             timeouts, where)
    return {c: out[c] for c in held}


def built_witnesses(stem: str, space: Cases, recorded: AbstractSet[str],
                    file: Path | None = None) -> dict[str, Grid]:
    """The input of the witness `derive` or `store` builds for each branch
    some held case takes, by the branch's name: the derive report's swap
    for a `@derive` branch, and the store report's grid for a `@store`
    one. A branch whose name is in `recorded`, the ids of the witness
    file's entries, or that no built grid separates, has none here. `file`
    stands in for the task's witness file."""
    from dl.derive import derive_report
    from dl.store import OWNED, store_report
    wanted = {b for held in space.runner.values() for b in held.branches
              if b.name not in recorded}
    out: dict[str, Grid] = {}
    names = {b.name for b in wanted}
    if any(b.kind == DERIVE for b in wanted):
        for d in derive_report(stem, file).derivations:
            if d.case in names and d.swap is not None:
                out[d.case] = d.swap.input
    if any(b.kind != DERIVE for b in wanted):
        for f in store_report(stem, file).found:
            if (f.kind == OWNED and f.case_id in names
                    and f.move is not None and f.move.input is not None):
                out[f.case_id] = f.move.input
    return out


type Scoped = tuple[dict[CaseId, Got], str | None]
"""What each held case gives on one witness input, and the name of the
branch the witness is built for; None for an entry of the file, which
counts for every pair."""


def _taken(space: Cases, case: CaseId) -> tuple[CaseId, tuple[Branch, ...]]:
    """The `Choice` case a held case takes, and its `@derive` and `@store`
    branches."""
    held = space.runner.get(case)
    return (held.base, held.branches) if held else (case, ())


def _unseparated(held: list[CaseId], outcomes: list[Scoped],
                 space: Cases) -> list[Drift]:
    """A finding per unordered pair of held cases that give one outcome on
    every witness input that counts for the pair (`_counts`). Train inputs
    never tell two held cases apart, as every held case fits the task, so
    the witnesses do. A pair of cases that take the same `@derive` and
    `@store` branches at two `Choice` cases that are themselves
    unseparated has no finding of its own: the pair of those `Choice` cases
    answers for it."""
    pairs = [(a, b) for i, a in enumerate(held) for b in held[i + 1:]
             if all(o.get(a) == o.get(b) for o, built in outcomes
                    if _counts(built, a, b, space))]
    same = {frozenset(p) for p in pairs}
    out: list[Drift] = []
    for a, b in pairs:
        (base_a, taken_a), (base_b, taken_b) = (_taken(space, a),
                                                _taken(space, b))
        if (taken_a and taken_a == taken_b and base_a != base_b
                and frozenset((base_a, base_b)) in same):
            continue
        out.append(Drift(entry="", cases=[a, b], expected=None, actual=None,
                         kind=UNSEPARATED))
    return out


def _counts(built: str | None, a: CaseId, b: CaseId, space: Cases) -> bool:
    """A witness input counts for the pair of held cases: an entry of the
    file counts for every pair, and the witness built for a branch for a
    pair where one case takes that branch."""
    return built is None or any(
        built == br.name for c in (a, b) for br in _taken(space, c)[1])


type Term = tuple[str, list["Term"]]
"""A constructor and the terms of its fields, as a case label writes it."""


def _term(text: str) -> Term:
    m = TERM_RE.match(text.strip())
    if m is None:
        return (text.strip(), [])
    args = m.group(2)
    return (m.group(1), [_term(a) for a in _split(args)]
            if args and args.strip() else [])


def _spelled(t: Term) -> str:
    return f"{t[0]}({', '.join(_spelled(a) for a in t[1])})" if t[1] else t[0]


def _swaps(t: Term, types: dict[str, dict[str, list[str]]],
           owner: dict[str, str]) -> list[tuple[str, str, list[Term]]]:
    """Each constructor of `t` that is not its type's first, with that
    type's first constructor and the terms `t` becomes when that one
    constructor is put in its place: its bare name, and its name applied to
    the first constructor of each field's type, down to where a field's
    type holds no branches."""
    out: list[tuple[str, str, list[Term]]] = []
    ctor, args = t
    if ctor in owner:
        typ = owner[ctor]
        first = next(iter(types[typ]))
        if ctor != first:
            out.append((ctor, first, [(first, []),
                                      _concept_term(typ, types, (typ,))]))
    for i, a in enumerate(args):
        for x, c, subs in _swaps(a, types, owner):
            out.append((x, c, [(ctor, args[:i] + [sub] + args[i + 1:])
                               for sub in subs]))
    return out


def _concept_term(typ: str, types: dict[str, dict[str, list[str]]],
                  chain: tuple[str, ...]) -> Term:
    first = next(iter(types[typ]))
    fts = types[typ][first]
    if not fts or any(ft not in types or ft in chain for ft in fts):
        return (first, [])
    return (first, [_concept_term(ft, types, chain + (ft,)) for ft in fts])


def branch_pairs(held: list[CaseId], source: str, space: Cases
                 ) -> list[tuple[str, str, CaseId, CaseId]]:
    """Each held case A that takes a branch X other than the first at one
    choice point, with the held case B that takes the first branch there
    and A's branches elsewhere, as (X, that first branch, A, B). At the
    choice point of a `@derive` or `@store` line, X is the line's branch
    and the first branch, the stored or the derived value, is written as
    the empty string."""
    try:
        types = _adts(parse(source).items)
    except ParseError:
        types = {}
    owner = {c: t for t, cs in types.items() for c in cs}
    names = set(held)
    out: list[tuple[str, str, CaseId, CaseId]] = []
    for a in held:
        base, taken = _taken(space, a)
        for x in taken:
            b = space.case_id(base, tuple(y for y in taken if y != x))
            if b in names:
                out.append((x.name, "", a, b))
        record = base.startswith("[")
        roots = ([_term(m) for m in _split(base[1:-1])] if record
                 else [_term(base)])
        for i, root in enumerate(roots):
            for x, first, subs in _swaps(root, types, owner):
                for sub in subs:
                    spelled = [_spelled(r) for r in roots[:i] + [sub]
                               + roots[i + 1:]]
                    other = CaseId(f"[{', '.join(spelled)}]" if record
                                   else spelled[0])
                    b = space.case_id(other, taken) if taken else other
                    if b in names:
                        out.append((x, first, a, b))
                        break
    return out


def _subsumes(a: CaseId, b: CaseId, outcomes: list[Scoped],
              space: Cases) -> bool:
    """Case B subsumes case A over the inputs that count for the pair: on
    none is A defined and differing from B, and on some A is undefined
    where B gives a grid, so the two are not equivalent there."""
    counted = [o for o, built in outcomes if _counts(built, a, b, space)]
    return (all(o.get(a) is None or o.get(a) == o.get(b) for o in counted)
            and any(o.get(a) is None and isinstance(o.get(b), list)
                    for o in counted))


def _subsumed(pairs: list[tuple[str, str, CaseId, CaseId]],
              held: list[CaseId], concept: CaseId | None,
              outcomes: list[Scoped], unseparated: list[Drift],
              space: Cases) -> list[Drift]:
    """The held cases that another held case subsumes (`_subsumes`). The
    inputs are the task's pairs, and the witnesses that `_unseparated`
    reads; a pair `unseparated` names is that finding alone.

    A case subsumed by its counterpart in `branch_pairs` is counted under
    the branch X it takes there: one finding per such X, with how many of
    the cases taking X are subsumed by their counterpart, of those that
    have one, and which, when not all are. Each other held case but the
    concept case that other held cases subsume is a finding naming it and
    those cases, less each one that subsumes another of them."""
    same = {frozenset(d.cases) for d in unseparated}
    total: dict[tuple[str, str], int] = {}
    hit: dict[tuple[str, str], list[CaseId]] = {}
    for x, first, a, b in pairs:
        if frozenset((a, b)) in same:
            continue
        total[(x, first)] = total.get((x, first), 0) + 1
        if _subsumes(a, b, outcomes, space):
            hit.setdefault((x, first), []).append(a)
    out = [Drift(entry="", cases=[x, first], expected=None, actual=None,
                 kind=SUBSUMED, note=f"{len(cases)} of {total[(x, first)]}",
                 subsumed=[*cases] if len(cases) < total[(x, first)] else [])
           for (x, first), cases in hit.items()]
    counted = {a for cases in hit.values() for a in cases}
    for a in held:
        if a == concept or a in counted:
            continue
        partners = [b for b in held if b != a
                    and frozenset((a, b)) not in same
                    and _subsumes(a, b, outcomes, space)]
        partners = [b for b in partners
                    if not any(_subsumes(c, b, outcomes, space)
                               for c in partners if c != b)]
        if partners:
            out.append(Drift(entry="", cases=[a, *partners], expected=None,
                             actual=None, kind=SUBSUMED))
    return out


def _held_part(stem: str, space: Cases, held: list[CaseId], entry: Entry,
               source: str, path: Path, resolution: bool,
               where: str) -> tuple[dict[CaseId, Got], Timeouts]:
    """What each held case gives on the entry's input at `source`, and the
    timeouts its runs noted."""
    timeouts = Timeouts()
    return _held_outcomes(
        stem, space, held, entry, source,
        timeouts.run(source, entry.input, path, where), resolution, timeouts,
        where), timeouts


def _pair_outcomes(stem: str, space: Cases, held: list[CaseId],
                   source: str, path: Path, task_id: str, resolution: bool,
                   pool: Executor) -> list[tuple[Scoped, Timeouts]]:
    """What each held case gives on the input of each train and test pair
    of the task, at the stored value, with the timeouts each pair's runs
    noted; none when the task is not materialized."""
    try:
        task = load_task(task_id)
    except FileNotFoundError:
        return []
    pairs = [(f"{kind} {i}", ex) for kind, exs in (("train", task.train),
                                                  ("test", task.test))
             for i, ex in enumerate(exs)]
    runs = [pool.submit(_held_part, stem, space, held,
                        Entry(id="", separates="", input=ex.input), source,
                        path, resolution, where)
            for where, ex in pairs]
    return [((out, None), timeouts)
            for out, timeouts in (r.result() for r in runs)]


def _train_outputs(task_id: str) -> list[list[list[list[int]]]]:
    """The outputs each train pair of the task accepts, in the order
    `_pair_outcomes` runs the pairs: its output, and its alt's grid when it
    has one; none when the task is not materialized."""
    try:
        task = load_task(task_id)
    except FileNotFoundError:
        return []
    return [[ex.output] + ([ex.alt.grid] if ex.alt else [])
            for ex in task.train]


type EntryPart = tuple[Scoped | None, list[CaseId], list[Drift], Timeouts]
"""What one entry adds to the report: its held cases' outcomes, the cases
it states in full, its findings, and the timeouts its runs noted."""


def _entry_part(stem: str, space: Cases, entry: Entry, source: str,
                path: Path, held: list[CaseId], choice: list[CaseId],
                resolution: bool, file: bool = False,
                kept: list[CaseId] | None = None) -> EntryPart:
    """The findings on one entry of the witness file, and what the report
    reads from it besides. Every case runs at the entry's assignment.
    `space` is the solver's case space (`dl.models.enumeration`). With
    `file`, an entry of a judged output on which the concept case gives
    another grid has a CONCEPT finding, and an entry's name that denotes no
    case of the solver a NEAREST finding (`_entry_findings`)."""
    timeouts = Timeouts()
    where = _label(entry)
    run_source = assigned_source(source, entry.assign)
    candidates = timeouts.run(run_source, entry.input, path, where)
    separating: Scoped | None = None
    if held:
        separating = (_held_outcomes(
            stem, space, held, entry, run_source, candidates, resolution,
            timeouts, where), None)
    if candidates is None:
        return separating, [], [], timeouts
    try:
        stated, full = _stated(stem, run_source, entry.input, choice)
    except subprocess.TimeoutExpired as err:
        timeouts.note(where, "", err)
        return separating, [], [], timeouts
    actuals = case_outcomes(candidates, resolution)
    for name in stated:
        actuals.setdefault(name, None)
    emitted = model_outcomes(candidates, resolution)
    names = _names(full)
    findings = _entry_findings(
        entry, space, emitted, actuals | emitted, names | set(actuals),
        _runner_outcomes(stem, entry, space, run_source, timeouts),
        full if declares_held(run_source) else None, file, kept)
    if file and isinstance(entry.output, list):
        got = concept_outcome(candidates, resolution, run_source)
        if got is not None and got != entry.output:
            findings.append(Drift(entry=where, cases=[], expected=entry.output,
                                  actual=got, kind=CONCEPT))
    return separating, full, findings, timeouts


def _souffle_error(err: RuntimeError) -> str:
    """The first line of the error Souffle reported, or the first line of
    the failure when it names no error line."""
    text = str(err)
    m = FIRST_ERROR_RE.search(text)
    if m:
        return text[m.start():].splitlines()[0]
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines[0] if lines else text


def _entry_or_failure(stem: str, space: Cases, entry: Entry, source: str,
                      path: Path, held: list[CaseId], choice: list[CaseId],
                      resolution: bool, file: bool = False,
                      kept: list[CaseId] | None = None,
                      task_entry: Entry | None = None) -> EntryPart:
    """`_entry_part`, and in place of its findings an ASSIGN finding per
    `assign` string that is no constant of the lib, per `assign` key that
    is no Params relation and per `assign` value whose arity does not fit
    its relation, or a FAILED finding
    when a Souffle run on the entry fails. An entry whose `assign` holds a
    name that is no constant of the lib runs at the `assign` of
    `task_entry`, the task's witness file's entry of its id, when that
    `assign` has no fault, and a TASK_ASSIGN finding says so."""
    noted: list[Drift] = []
    names = assign_findings(entry.assign)
    if names and task_entry is not None \
            and not assign_findings(task_entry.assign, source):
        noted = [Drift(
            entry=_label(entry), cases=[], expected=None, actual=None,
            kind=TASK_ASSIGN,
            note=mctx("{names}, so the run takes the `assign` of the "
                      "`{id}` witness in the task's witness file: "
                      "`{assign}`").format(
                names="; ".join(names), id=task_entry.id,
                assign=json.dumps(task_entry.assign)))]
        entry = replace(entry, assign=task_entry.assign)
    if bad := assign_findings(entry.assign, source):
        return None, [], [Drift(entry=_label(entry), cases=[], expected=None,
                                actual=None, kind=ASSIGN, note=line)
                         for line in bad], Timeouts()
    try:
        scoped, full, findings, timeouts = _entry_part(
            stem, space, entry, source, path, held, choice, resolution, file,
            kept)
    except RuntimeError as err:
        return None, [], noted + [Drift(
            entry=_label(entry), cases=[], expected=None, actual=None,
            kind=FAILED, note=_souffle_error(err))], Timeouts()
    return scoped, full, noted + findings, timeouts


SUBSUMPTION = "Subsumption"
FIT = "Fit"


def every_case_source(source: str) -> tuple[str, list[CaseId]]:
    """`source` with `impl_choice` holding every case its `Choice` spells,
    and the cases `impl_choice` holds in `source`, spelled in full. A
    solver that declares no `impl_choice` holds every case already. A
    `Choice` that no name spells raises ValueError."""
    space = case_space(source)
    cases = space.cases() if isinstance(space, Space) else []
    if not cases:
        raise ValueError(mctx("the solver's `Choice` gives no case"))
    if not declares_held(source):
        return source, cases
    kept = held_cases(parse(source), source, full=True) or []
    return with_held_cases(source, cases), kept


def _branches_taken(case: CaseId, space: Cases) -> int:
    """How many non-concept branches `case` takes: the constructors it
    spells that are not their type's first, and its `@derive` and `@store`
    branches."""
    base, taken = _taken(space, case)
    types = space.types if isinstance(space, Space) else {}
    first = {c: next(iter(cs)) for cs in types.values() for c in cs}
    return len(taken) + sum(1 for c in re.findall(r"\w+", base)
                            if first.get(c, c) != c)


def _dropped(held: list[CaseId], kept: list[CaseId], outcomes: list[Scoped],
             unseparated: list[Drift], space: Cases,
             fit: Sequence[tuple[dict[CaseId, Got], list]] = ()
             ) -> list[Drift]:
    """A DROPPED finding per held `Choice` case that `kept` does not hold:
    the case fails Fit, as no run shows it defined, or as at a train pair
    it gives no output the pair accepts; or no witness separates it from a
    case that takes no more non-concept branches (`_branches_taken`); or
    it fails Subsumption against a case that subsumes it (`_subsumes`); or
    no case condition, and then the finding also holds each case no
    witness separates it from. `fit` holds, per train pair, what each case
    gives there and the outputs the pair accepts; a run that timed out
    shows nothing. The case it fails against is one at a kept `Choice`
    case where one serves. The cases that fail no case condition come
    first."""
    same = {frozenset(d.cases) for d in unseparated}
    others = ([c for c in held if _taken(space, c)[0] in kept]
              + [c for c in held if _taken(space, c)[0] not in kept])
    counted = [o for o, built in outcomes if built is None]
    out: list[Drift] = []
    for a in held:
        if a in kept or a in space.runner:
            continue
        note, against = "", []
        at = next((i for i, (o, accepted) in enumerate(fit)
                   if not isinstance(o.get(a), TimedOut)
                   and o.get(a) not in accepted), None)
        if counted and all(o.get(a) is None for o in counted):
            note = UNDEFINED
        elif at is not None:
            note, against = FIT, [str(at)]
        elif b := next((b for b in others
                        if frozenset((a, b)) in same
                        and _branches_taken(b, space)
                        <= _branches_taken(a, space)), None):
            note, against = UNSEPARATED, [b]
        elif b := next((b for b in others if b != a
                        and _subsumes(a, b, outcomes, space)), None):
            note, against = SUBSUMPTION, [b]
        else:
            against = [b for b in others if frozenset((a, b)) in same]
        out.append(Drift(entry="", cases=[a, *against], expected=None,
                         actual=None, kind=DROPPED, note=note))
    return sorted(out, key=lambda d: d.note != "")


def witness_report(stem: str, file: Path | None = None,
                   every_case: bool = False, own: bool = False) -> list[Drift]:
    """The findings of the `witness` command, which its help text in
    `dl.cli` describes. `file` stands in for the task's witness file. Each
    name of a group resolves to a case of the solver's case space
    (`dl.models.enumeration`). Every case runs at an entry's assignment.
    The pairs of held cases (`CaseSpace.held`) are checked over the
    entries and over the witnesses `derive` and `store` build
    (`built_witnesses`), and each held case is checked for the held cases
    that subsume it (`_subsumed`) over those inputs and the task's pairs.
    With `file`, the report holds the entries' findings only: the pair,
    subsumption and `@witness` line findings are the task's own file's, and
    an entry whose `assign` holds a name that is no constant of the lib
    runs at the `assign` of the task's own file's entry of its id
    (`_entry_or_failure`). With `own` as well, `file` is read as the task's
    own file and the report is whole. With `every_case`, the run reads
    `every_case_source` in place of the solver's source, the pair and
    subsumption findings are those of the cases the solver holds and of
    the cases that take a branch at them, and the report ends with the
    findings of `_dropped`."""
    path, task_id = solver_file(stem)
    source = path.read_text()
    kept: list[CaseId] | None = None
    if every_case:
        source, kept = every_case_source(source)
    if file is not None:
        witness: Witness | None = load_witness_file(file)
    else:
        witness = load_witnesses(task_id)
    entries_only = file is not None and not own
    task_entries = {e.id: e for e in (load_witnesses(task_id)
                                      or Witness(id=task_id)).entries} \
        if entries_only else {}
    unwitnessed = [] if witness is None or entries_only else [
        Drift(entry=f"line {at}", cases=[], expected=None, actual=None,
              kind=ANNOTATION, note=text)
        for at, text in unwitnessed_branches(source)]
    space = enumeration(source)
    held = [] if witness is None else space.held()
    choice = list(space.plain) if held else []
    witness = witness or Witness(id=task_id)
    resolution = res_out_stem(stem)
    findings: list[Drift] = []
    cases: list[CaseId] = []
    separating: list[Scoped] = []
    by_entry: dict[str, dict[CaseId, Got]] = {}
    timeouts = Timeouts()
    # Each entry, built witness and pair runs on its own, in a thread: the
    # time goes to Souffle subprocesses. Their parts join in the order a
    # run one after another would give.
    with ThreadPoolExecutor(max_workers=_pool_workers()) as pool:
        built_runs = pool.submit(
            built_witnesses, stem, space,
            {e.id for e in witness.entries}, file) \
            if held and space.runner and not entries_only else None
        entry_runs = [pool.submit(_entry_or_failure, stem, space, entry,
                                  source, path, held, choice, resolution,
                                  entries_only, kept,
                                  task_entries.get(entry.id))
                      for entry in witness.entries]
        pair_runs = _pair_outcomes(
            stem, space, held, source, path, task_id, resolution, pool) \
            if held and not entries_only else []
        for entry, run in zip(witness.entries, entry_runs):
            scoped, full, entry_findings, entry_timeouts = run.result()
            if scoped is not None:
                separating.append(scoped)
                by_entry[entry.id] = scoped[0]
            cases += [c for c in full if c not in cases]
            findings += entry_findings
            timeouts.merge(entry_timeouts)
        # One source holds every case the verdicts name that the solver
        # does not hold, and it runs on each entry a verdict stands on.
        unheld = {} if entries_only else unheld_verdicts(
            source, space, _held_names(source, cases))
        verdict_source = with_held_cases(source, dict.fromkeys(
            c for cs in unheld.values() for c in cs)) if unheld else source
        verdict_runs = [
            (entry.id, pool.submit(_verdict_part, space, entry,
                                   unheld[entry.id], verdict_source, path,
                                   resolution))
            for entry in witness.entries
            if entry.id in unheld and entry.id in by_entry]
        built = built_runs.result() if built_runs else {}
        built_parts = [
            (name, pool.submit(
                _held_part, stem, space, held,
                Entry(id=name, separates="", input=grid), source, path,
                resolution,
                mctx("the witness built for `{name}`").format(name=name)))
            for name, grid in built.items()]
        for entry_id, run in verdict_runs:
            got, verdict_findings, verdict_timeouts = run.result()
            by_entry[entry_id] = by_entry[entry_id] | got
            findings += verdict_findings
            timeouts.merge(verdict_timeouts)
        for name, run in built_parts:
            out, built_timeouts = run.result()
            separating.append((out, name))
            timeouts.merge(built_timeouts)
    if entries_only:
        return _names_once(findings) + timeouts.findings
    unseparated = _unseparated(held, separating, space)
    for _scoped, pair_timeouts in pair_runs:
        timeouts.merge(pair_timeouts)
    shown = held if kept is None else [
        c for c in held if _taken(space, c)[0] in kept]
    shown_unseparated = [d for d in unseparated
                         if all(c in shown for c in d.cases)]
    pairs = branch_pairs(shown, source, space) if shown else []
    subsumed = _subsumed(
        pairs, shown, space.concept,
        separating + [scoped for scoped, _ in pair_runs],
        shown_unseparated, space) if shown else []
    fit = [(out, accepted) for ((out, _b), _t), accepted
           in zip(pair_runs, _train_outputs(task_id), strict=False)]
    dropped = _dropped(
        held, kept, separating + [scoped for scoped, _ in pair_runs],
        unseparated, space, fit) \
        if held and kept is not None else []
    return (findings + unwitnessed
            + _annotation_findings(source, witness.entries, cases, space,
                                   by_entry)
            + _grouped(shown_unseparated, space) + _grouped(subsumed, space)
            + timeouts.findings + dropped)


# A place where two cases differ: a node of the case space, or the choice
# point of a `@derive` or `@store` line, `(POINT, kind, target)`.
type Place = tuple[object, ...]
POINT = "point"

# Where two cases differ: each place, with what the first case and the
# second take there.
type Difference = tuple[tuple[Place, str, str], ...]


def _is_point(place: Place) -> bool:
    return bool(place) and place[0] == POINT


def _choices(space: Space, case: CaseId) -> dict[Place, str] | None:
    """The branch a held case takes at each node of `space`, and at the
    choice point of each `@derive` or `@store` line the name of the branch
    it takes there, or "" for the first branch. None when `space` does not
    spell the case."""
    base, taken = _taken(space, case)
    nodes = space.nodes(base)
    if nodes is None:
        return None
    points: dict[Place, str] = {(POINT, b.kind, b.target): ""
                                for b in space.lines}
    for b in taken:
        points[(POINT, b.kind, b.target)] = b.name
    return {**points, **nodes}


def _difference(space: Space, a: CaseId, b: CaseId) -> Difference | None:
    """The places where `a` and `b` differ, less each node under a node
    where they differ; None when `space` does not spell one of them."""
    ca, cb = _choices(space, a), _choices(space, b)
    if ca is None or cb is None:
        return None
    places = [p for p in {**ca, **cb} if ca.get(p) != cb.get(p)]
    top = [p for p in places
           if _is_point(p) or not any(
               q != p and not _is_point(q) and p[:len(q)] == q
               for q in places)]
    top.sort(key=lambda p: (0, 0, (), str(p)) if _is_point(p)
             else (1, len(p), p, ""))
    return tuple((p, ca.get(p, ""), cb.get(p, "")) for p in top)


def _branch_index(space: Space, place: Place, ctor: str) -> int:
    """Where a branch stands in its type's declaration, or at the choice
    point of a `@derive` or `@store` line, among the lines of the point,
    after the first branch."""
    if _is_point(place):
        lines = [b.name for b in space.lines
                 if (POINT, b.kind, b.target) == place]
        return lines.index(ctor) + 1 if ctor in lines else 0
    site = next((s for s in space.sites.get(ctor, []) if s.node == place),
                None)
    return 0 if site is None else list(space.types[site.type]).index(ctor)


def _first_branch(kind: object) -> str:
    """The first branch of a `@derive` or `@store` line's choice point, as
    a finding names it."""
    return (mctx("the stored value") if kind == DERIVE
            else mctx("the derived value"))


def _place_text(space: Space, place: Place, x: str, y: str,
                branches: bool = True) -> str:
    """One place two cases differ at, where they take `x` and `y`, and
    with `branches`, those two."""
    if _is_point(place):
        text = f"`{place[2]}`"
        if not branches:
            return text
        return text + " ({x}, {y})".format(
            x=f"`{x}`" if x else _first_branch(place[1]),
            y=f"`{y}`" if y else _first_branch(place[1]))
    site = next((s for c in (x, y) for s in space.sites.get(c, [])
                 if s.node == place), None)
    if site is None:
        return f"`{x}`, `{y}`"
    point = f"`{site.type}`"
    if site.above:
        point = mctx("{point} under `{ctor}`").format(
            point=point, ctor=site.above[-1][1])
    return f"{point} (`{x}`, `{y}`)" if branches else point


def _group_text(key: tuple[tuple[Place, str], ...]) -> str:
    """A group's places as its header names them, from the text of each
    (`_place_text`)."""
    points = [t for _p, t in key]
    if len(points) > 1:
        return mctx("choice points {points} and {last}").format(
            points=", ".join(points[:-1]), last=points[-1])
    return mctx("choice point {point}").format(point=points[0])


def _grouped(findings: list[Drift], space: Cases) -> list[Drift]:
    """The UNSEPARATED findings, and the SUBSUMED ones with no `note`,
    grouped by where the two cases of each pair differ (`_difference`):
    a pair that differs at one place by that place and the two branches
    taken there, and a pair that differs at more than one by those places
    alone. One finding per group of more than one pair, holding the pairs in
    `pairs` and the places in `note`. A SUBSUMED finding with several
    cases stands as one pair per case that subsumes the first. The other
    findings, and each pair `space` does not spell, come first; then the
    groups, those that differ at fewer places first, with a group of one
    pair as a finding of its own."""
    if not isinstance(space, Space):
        return findings
    groups: dict[tuple[str, tuple[tuple[Place, str], ...]],
                 list[tuple[str, str]]] = {}
    rest: list[Drift] = []
    for d in findings:
        if d.kind == UNSEPARATED:
            pairs = [(d.cases[0], d.cases[1])]
        elif d.kind == SUBSUMED and not d.note:
            pairs = [(d.cases[0], b) for b in d.cases[1:]]
        else:
            rest.append(d)
            continue
        for a, b in pairs:
            diff = _difference(space, CaseId(a), CaseId(b))
            if diff is None:
                rest.append(Drift(entry="", cases=[a, b], expected=None,
                                  actual=None, kind=d.kind))
                continue
            if d.kind == UNSEPARATED and diff and (
                    _branch_index(space, diff[0][0], diff[0][1])
                    > _branch_index(space, diff[0][0], diff[0][2])):
                a, b = b, a
                diff = tuple((p, y, x) for p, x, y in diff)
            key = tuple((p, _place_text(space, p, x, y, len(diff) == 1))
                        for p, x, y in diff)
            groups.setdefault((d.kind, key), []).append((a, b))
    out: list[Drift] = []
    for (kind, key), pairs in sorted(groups.items(),
                                     key=lambda g: len(g[0][1])):
        if len(pairs) == 1:
            out.append(Drift(entry="", cases=list(pairs[0]), expected=None,
                             actual=None, kind=kind))
        else:
            out.append(Drift(entry="", cases=[], expected=None, actual=None,
                             kind=kind, note=_group_text(key),
                             pairs=pairs))
    return rest + out


def _names_once(findings: list[Drift]) -> list[Drift]:
    """The findings with each UNRESOLVED name taken off its entries and
    stated once, ahead of the rest, with no entry: a witness file other
    than the task's may name, in every entry, cases the solver does not
    hold. A name that has no nearest held cases joins the one finding that
    lists such names, and a name that an `@ignore` line excludes joins the
    one finding on that line."""
    nearest: dict[tuple[str, str], Drift] = {}
    excluded: dict[int, Drift] = {}
    plain: list[str] = []
    rest: list[Drift] = []
    for d in findings:
        if d.kind != UNRESOLVED:
            rest.append(d)
        elif d.line:
            once = excluded.setdefault(d.line, Drift(
                entry="", cases=[], expected=None, actual=None,
                kind=UNRESOLVED, line=d.line))
            once.cases += [n for n in d.cases if n not in once.cases]
        elif d.note:
            nearest.setdefault((d.cases[0], d.note), Drift(
                entry="", cases=[d.cases[0]], expected=None, actual=None,
                kind=UNRESOLVED, note=d.note))
        else:
            plain += [n for n in d.cases if n not in plain]
    once = list(nearest.values()) + list(excluded.values())
    if plain:
        once.append(Drift(entry="", cases=plain, expected=None, actual=None,
                          kind=UNRESOLVED))
    return once + rest


def _side(label: str, value: Outcome) -> list[str]:
    if value is None:
        return [f"  {label}: {UNDEFINED}"]
    return [f"  {label}:", *(f"    {ln}" for ln in _grid_lines(value))]


def _lines_of(d: Drift) -> list[str]:
    """One block for one finding. A finding that holds for several cases
    names them all and draws its grids once."""
    case = ", ".join(d.cases)
    one = len(d.cases) == 1
    if d.kind == ANNOTATION:
        return [f"{d.entry}: {d.note}" if d.entry else d.note]
    if d.pairs:
        pairs = [f"  `{a}` from `{b}`" for a, b in d.pairs]
        if d.kind == UNSEPARATED:
            return [mctx("no witness separates these {count} pairs, which "
                         "differ at {places}:")
                    .format(count=len(d.pairs), places=d.note), *pairs]
        return [mctx("no run shows the first case defined and differing "
                     "from the second in these {count} pairs, which differ "
                     "at {places}:")
                .format(count=len(d.pairs), places=d.note), *pairs]
    if d.kind == UNSEPARATED:
        return [mctx("no witness separates `{a}` from `{b}`")
                .format(a=d.cases[0], b=d.cases[1])]
    if d.kind == TIMEOUT:
        return [mctx("{entry}: case `{case}` timed out after {limit}s, so no "
                     "finding rests on its outcome there")
                .format(entry=d.entry, case=d.cases[0], limit=d.note)
                if d.cases else
                mctx("{entry}: the run of the solver's cases timed out after "
                     "{limit}s, so no finding rests on their outcomes there")
                .format(entry=d.entry, limit=d.note)]
    if d.kind == SUBSUMED and not d.note:
        if len(d.cases) == 2:
            return [mctx("no run shows `{a}` defined and differing from "
                         "`{b}`").format(a=d.cases[0], b=d.cases[1])]
        return [mctx("no run shows `{a}` defined and differing from these "
                     "cases:").format(a=d.cases[0]),
                *(f"  {c}" for c in d.cases[1:])]
    if d.kind == SUBSUMED:
        return [(mctx("no run shows `{a}` defined and differing from `{b}` "
                      "({count} cases)")
                 .format(a=d.cases[0], b=d.cases[1], count=d.note)
                 if d.cases[1] else
                 mctx("no run shows `{a}` defined and differing from "
                      "{first} ({count} cases)")
                 .format(a=d.cases[0], count=d.note,
                         first=_first_branch(
                             STORE if d.cases[0].endswith(f"={STORED}")
                             else DERIVE))),
                *(f"  {c}" for c in d.subsumed)]
    if d.kind == DROPPED:
        a = d.cases[0]
        if d.note == UNDEFINED:
            return [mctx("dropped case `{a}` fails Fit: no run shows it "
                         "defined")
                    .format(a=a)]
        if d.note == FIT:
            return [mctx("dropped case `{a}` fails Fit: at train pair {i} "
                         "it gives no output the pair accepts")
                    .format(a=a, i=d.cases[1])]
        if d.note == UNSEPARATED:
            return [mctx("dropped case `{a}`: no witness separates it from "
                         "`{b}`, a pair that [Witness]"
                         "(docs/handbook/procedure.md#witness) resolves")
                    .format(a=a, b=d.cases[1])]
        if d.note == SUBSUMPTION:
            return [mctx("dropped case `{a}` fails Subsumption against "
                         "`{b}`").format(a=a, b=d.cases[1])]
        if len(d.cases) > 1:
            return [mctx("dropped case `{a}` fails no case condition in the "
                         "`witness --every-case` run; no witness separates "
                         "it from {b}, and [Witness]"
                         "(docs/handbook/procedure.md#witness) resolves each "
                         "such pair")
                    .format(a=a, b=", ".join(f"`{b}`" for b in d.cases[1:]))]
        return [mctx("dropped case `{a}` fails no case condition in the "
                     "`witness --every-case` run")
                .format(a=a)]
    if d.kind == UNLISTED:
        return [mctx("{entry}: case {case} is not listed")
                .format(entry=d.entry, case=case) if one else
                mctx("{entry}: these cases are not listed: {case}")
                .format(entry=d.entry, case=case),
                *_side("the solver's output", d.actual)]
    if d.kind == FAILED:
        return [mctx("the entry `{entry}` failed: {error}")
                .format(entry=d.entry, error=d.note)]
    if d.kind in (ASSIGN, TASK_ASSIGN):
        return [f"{d.entry}: {d.note}"]
    if d.kind == SEPARATES:
        return [mctx("{entry}: the `separates` text has `{name}`, and no "
                     "group lists it").format(entry=d.entry, name=case)]
    if d.kind == NEAREST:
        return [mctx("{entry}: the held case `{case}`, in place of `{name}`, "
                     "gives a grid other than the grid of the group that "
                     "lists `{name}`")
                .format(entry=d.entry, case=case, name=d.note) if one else
                mctx("{entry}: the held cases {case}, in place of `{name}`, "
                     "give a grid other than the grid of the group that "
                     "lists `{name}`")
                .format(entry=d.entry, name=d.note,
                        case=", ".join(f"`{c}`" for c in d.cases)),
                *_side("the witness's output", d.expected),
                *_side("the solver's output", d.actual)]
    if d.kind == CONCEPT:
        return [mctx("{entry}: the concept case gives a grid other than the "
                     "judged output").format(entry=d.entry),
                *_side("the solver's output", d.actual)]
    if d.kind == UNRESOLVED:
        at = f"{d.entry}: " if d.entry else ""
        names = ", ".join(f"`{n}`" for n in d.cases)
        if d.note:
            line = mctx("the name `{name}` denotes no case of the solver; the "
                        "held cases that take `{name}` and differ least from "
                        "the concept case are {cases}").format(name=d.cases[0],
                                                          cases=d.note)
        elif d.line:
            line = (mctx("the name {names} denotes no case of the solver: "
                         "the `@ignore` at line {line} excludes its case")
                    if one else
                    mctx("these names denote no case of the solver, since "
                         "the `@ignore` at line {line} excludes their "
                         "cases: {names}")).format(
                             names=names, line=d.line)
        elif one:
            line = mctx("the name {names} denotes no case of the solver") \
                .format(names=names)
        else:
            line = mctx("these names denote no case of the solver: {names}") \
                .format(names=names)
        return [at + line]
    if d.rejected_output:
        return [mctx("{entry}: case {case} gives the witness's judged output")
                .format(entry=d.entry, case=case) if one else
                mctx("{entry}: these cases give the witness's judged output: "
                     "{case}").format(entry=d.entry, case=case),
                *_side("the judged output", d.actual)]
    return [mctx("{entry}: case {case} gives an output the witness does not "
                 "name").format(entry=d.entry, case=case) if one else
            mctx("{entry}: these cases give an output the witness does not "
                 "name: {case}").format(entry=d.entry, case=case),
            *_side("the witness's output", d.expected),
            *_side("the solver's output", d.actual)]


def finding_lines(findings: list[Drift]) -> list[str]:
    """One block per finding, with no pass line."""
    return [line for d in findings for line in _lines_of(d)]


def passes(findings: list[Drift], file: bool = False) -> bool:
    """No finding fails the check. With `file`, the report reads a file
    other than the task's, which may name cases the solver no longer
    holds, so an UNRESOLVED finding does not fail it."""
    failing = set(FAILING) - {UNRESOLVED} if file else set(FAILING)
    return not any(d.kind in failing for d in findings)


def pass_line(findings: list[Drift]) -> str:
    """`witness: ok`, followed by the count of the findings above it when
    any stand. Every finding of a passing report is one that does not fail
    the check."""
    n = len(findings)
    if not n:
        return WITNESS_OK
    return f"{WITNESS_OK}, {n} non-failing finding{'s' if n != 1 else ''}"

