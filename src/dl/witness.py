"""Hand-written grids a solver's cases are pinned to.

A witness file holds grids the author built to tell the solver's branch
models apart, each with the outcome every model is expected to give.
solver-file.md states the file's shape, and `dl.models` reads the names a
group gives.

An entry's `assign` field reassigns a `Params` parameter before the run,
so the entry stands at the assignment its `separates` names rather than
at the stored one.

Every held case fits the task, so only witnesses tell two of them apart:
the file's inputs, and for a case the runner holds, the witness the runner
builds for it. The report names each pair of held cases no witness
separates.
`shape_findings` checks a file's shape alone, with no solver, and the
report runs it first.
"""

import json
import re
import subprocess
from collections.abc import Callable, Iterable
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from arc.jsonio import format_file
from arc.task import load as load_task
from controlled_markdown import mctx
from dl.annotations import (
    STORED,
    Claim,
    derive_ids,
    derive_param,
    merged_blocks,
    read,
    relaxable,
    resolved_claims,
    store_ids,
    store_relation,
    witness_blocks,
)
from dl.dlparse import ParseError, parse
from dl.facts import Candidate
from dl.features import case_branches, declares_held, held_cases
from dl.features_run import NO_CHOICE, _split, case_label
from dl.lint import branch_above, concept_case, unwitnessed_branches
from dl.models import (
    TERM_RE,
    Cases,
    Coarse,
    Space,
    _adts,
    case_space,
    model_label,
)
from dl.paths import PROGRAMS_DIR
from dl.render import _grid_lines
from dl.solve import res_out_stem, run_dl_source, solver_file
from dl.souffle import FIRST_ERROR_RE, _pool_workers
from dl.source import swap_facts

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
FAILING = (DRIFT, UNRESOLVED, ANNOTATION, UNSEPARATED, SUBSUMED, TIMEOUT,
           FAILED, ASSIGN)
"""The kinds that fail the check."""

type Grid = list[list[int]]
type Outcome = Grid | None
type Assign = dict[str, list[list[object]]]


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

    case: str


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
    ANNOTATION, UNSEPARATED, SUBSUMED, TIMEOUT, FAILED or ASSIGN, each the finding
    the `witness` help text in `dl.cli` describes; a TIMEOUT finding names
    the input in `entry`, the case in `cases` (empty when the run of every
    case the solver states timed out) and the limit in `note`; a FAILED
    finding names the entry in `entry` and the first line of Souffle's error
    in `note`, and an ASSIGN finding the entry and the line on the `assign`
    string in `note`; an UNRESOLVED finding with a `note` names one constructor,
    and `note` holds the names of the nearest held cases under it; an UNSEPARATED
    finding names the two cases in `cases`, and a SUBSUMED finding either
    the branch and its type's first branch, with the count in `note` and,
    when not every case taking the branch is subsumed, the subsumed ones in
    `subsumed`, or, with no `note`, the subsumed case and then the cases
    that subsume it. `entry` is the entry's
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


def witness_path(task_id: str) -> Path:
    return WITNESS_DIR / f"{task_id}.wit.json"


def _is_groups(v: object) -> bool:
    """A list of groups, which is the per-case form the file writes. An
    empty list is a file that names no case; a rejected output is a list of
    rows, so no list stands for both."""
    return isinstance(v, list) and all(isinstance(g, dict) for g in v)


def _output(value: object) -> dict[str, Outcome] | list[list[int]]:
    """An entry's `output` as the code carries it: a grid per case, or the
    bare grid a rejected output holds. A group's grid spreads over the cases
    the group names. An object of one grid per case is read as well, which
    is the form the file held before groups. Either form keys the one case
    of a solver without a `Choice` by the name the runner prints."""
    if isinstance(value, dict):
        return {k or NO_CHOICE: v for k, v in value.items()}
    if _is_groups(value):
        return {c or NO_CHOICE: g["grid"] for g in value for c in g["cases"]}
    return value


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


def _is_grid(v: object) -> bool:
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
    def fail(where: str, msg: str) -> None:
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


def _rect_grid(v: object) -> bool:
    """A grid of at least one cell, each row as long as the first, each
    cell an integer from 0 to 9."""
    return (isinstance(v, list) and bool(v)
            and all(isinstance(r, list) and r and len(r) == len(v[0])
                    for r in v)
            and all(type(c) is int and 0 <= c <= 9 for r in v for c in r))


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


def assign_findings(assign: dict) -> list[str]:
    """One line per string argument of an `assign` fact that is no constant
    of the lib; Souffle takes such a name for a variable and fails on the
    fact."""
    known: set[str] | None = None
    out: list[str] = []
    for param, rows in assign.items():
        if not (isinstance(rows, list)
                and all(isinstance(f, list) for f in rows)):
            continue
        for value in _strings(rows):
            if known is None:
                known = _lib_constants()
            if value not in known:
                out.append(mctx("the `assign` value of `{param}` holds "
                                "`{value}`, which is no constant of the lib")
                           .format(param=param, value=value))
    return out


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


def read_witness_data(task_id: str) -> dict:
    """The task's witness file as JSON, checked against the shape. A task
    with no file yet gets the data an empty file holds."""
    path = witness_path(task_id)
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
    return {**entry, "output": grouped_output(_output(out))}


def write_witness_data(task_id: str, data: dict) -> Path:
    """Write a witness file, after the shape check. Every write of a witness
    file goes through here, so one layout stands over the directory: the
    file's own conventions, groups for the per-case outcomes, and every grid
    one row per line."""
    path = witness_path(task_id)
    _validate(data, path)
    data = {**data, "witnesses": [_grouped_entry(e)
                                  for e in data["witnesses"]]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_file(data))
    return path


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
    return None if (c.error or c.conflicts or c.missing) else c.grid


def case_outcomes(candidates: list[Candidate],
                  resolution: bool) -> dict[str, Outcome]:
    """What each case gives on one grid, in the order the run emits them. A
    case emitting more than one grid keeps the first."""
    out: dict[str, Outcome] = {}
    for c in candidates:
        name = case_label(c.case, resolution)
        got = _outcome(c)
        if name not in out or got is None:
            out[name] = got
    return out


def model_outcomes(candidates: list[Candidate],
                   resolution: bool) -> dict[str, Outcome]:
    """What each case gives on one grid, keyed as `dl.models` spells a
    case, with each constructor's fields kept. A case emitting more than one
    grid keeps the first, and an undefined one."""
    out: dict[str, Outcome] = {}
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
    return case_outcomes(candidates, resolution).get(concept_case(source))


def runner_outcomes(stem: str, ids: Iterable[str], grid: list[list[int]],
                    source: str, timeouts: Timeouts | None = None,
                    where: str = "") -> dict[str, Outcome]:
    """What each case the runner holds gives on one grid, by its id. A
    derived case runs `source`, and a stored case the solver's file. With
    `timeouts`, a case whose run times out is noted there, as on the input
    `where`, and gives TimedOut; without, the timeout is raised."""
    from dl.derive import derived_outcome
    from dl.store import store_outcome
    out: dict[str, Outcome] = {}
    for c in ids:
        try:
            out[c] = (store_outcome(stem, c, grid)
                      if c.endswith(f"={STORED}")
                      else derived_outcome(stem, c, grid, source))
        except subprocess.TimeoutExpired as err:
            if timeouts is None:
                raise
            timeouts.note(where, c, err)
            out[c] = TimedOut(c)  # type: ignore[assignment]
    return out


def listed_models(space: Cases, held: list[str] | None) -> dict[str, str]:
    """The cases a witness entry lists, each by its name: each branch model
    of `space`. `held` holds the cases the solver holds, spelled in full,
    and is None when every case is held. A model whose case is not held
    gives way to the nearest held cases under its constructor
    (`Space.nearest`), each by its shortest name (`Space.short_name`)."""
    if held is None or not isinstance(space, Space):
        return space.models()
    kept = set(held)
    out: dict[str, str] = {}
    for name, label, site in space.model_sites():
        if site is None or label in kept:
            out.setdefault(name, label)
            continue
        for case in space.nearest(space.required(site), held):
            out.setdefault(space.short_name(case), case)
    return out


def branch_outcomes(space: Cases, candidates: list[Candidate],
                    resolution: bool,
                    held: list[str] | None = None) -> dict[str, Outcome]:
    """What each case `listed_models` names gives on one grid, by its name;
    None for a case that emits nothing."""
    got = case_outcomes(candidates, resolution) | model_outcomes(
        candidates, resolution)
    return {name: got.get(label)
            for name, label in listed_models(space, held).items()}


def _rows(rows: list[list[object]]) -> list[tuple]:
    """A parameter's replacement facts as `swap_facts` takes them: one tuple
    per fact, and a list argument a record."""
    return [
        tuple(tuple(a) if isinstance(a, list) else a for a in row)
        for row in rows
    ]


def assigned_source(source: str, assign: Assign) -> str:
    """The solver source with the reassignments applied."""
    for param, rows in assign.items():
        source = swap_facts(source, param, _rows(rows))
    return source


def _label(entry: Entry) -> str:
    """The entry's id, followed by the parameters it reassigns."""
    if not entry.assign:
        return entry.id
    return f"{entry.id} [{', '.join(entry.assign)}]"


type Mismatch = tuple[str, Outcome, Outcome]


def _merged(label: str, rows: list[Mismatch], kind: str = DRIFT,
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
                    emitted: dict[str, Outcome], actuals: dict[str, Outcome],
                    held: set[str],
                    runner: dict[str, Outcome],
                    full: list[str] | None = None) -> list[Drift]:
    """The findings on one entry, given what its input produced. `emitted`
    holds the outcome of each case the run emits, spelled with its fields;
    `actuals` holds those and the runner's labels of them, `held` the names
    of the cases the solver states (`_names`), and `runner` the outcomes of
    the cases the runner holds. An entry whose id is a case the runner holds
    need not list that case. `full` holds the cases `impl_choice` holds,
    spelled in full, and is None when the solver declares no
    `impl_choice`; a name whose case it does not hold denotes no case of the
    solver. The entry lists the cases `listed_models` names."""
    label = _label(entry)
    impl = None if full is None else _names(full)
    listed = listed_models(space, full)
    if entry.rejected_output:
        return _merged(label, [
            (case, entry.output, got)
            for case, got in emitted.items()
            if got == entry.output
        ], rejected=True)
    rows: list[Mismatch] = []
    unresolved: list[str] = []
    named: set[str] = set()
    for name, want in entry.output.items():
        case = space.resolve(name)
        if case is None or (impl is not None and case not in runner
                            and case not in impl):
            unresolved.append(name)
            continue
        named.add(case)
        named |= {m for m in listed.values() if case_label(m) == case}
        got = runner.get(case) if case in runner else actuals.get(case)
        if isinstance(got, TimedOut):
            continue
        if got != want:
            rows.append((name, want, got))
    findings = _merged(label, rows)
    plain: list[str] = []
    for name in unresolved:
        nearest = _nearest_names(name, space, full)
        if nearest:
            findings.append(Drift(entry=label, cases=[name], expected=None,
                                  actual=None, kind=UNRESOLVED,
                                  note=", ".join(f"`{n}`" for n in nearest)))
        else:
            plain.append(name)
    if plain:
        findings.append(Drift(entry=label, cases=plain, expected=None,
                              actual=None, kind=UNRESOLVED))
    findings += _merged(label, [
        (name, None, actuals.get(case))
        for name, case in listed.items()
        if case not in named
        and (case in actuals or case in held)
    ] + [
        (case, None, runner.get(case))
        for case in sorted(space.runner)
        if case not in named and case != entry.id
        and not isinstance(runner.get(case), TimedOut)
    ], kind=UNLISTED)
    return findings


def _nearest_names(name: str, space: Cases,
                   full: list[str] | None) -> list[str]:
    """For a name that is a constructor, or its slug, whose case the solver
    does not hold: the names of the nearest held cases under that
    constructor (`Space.nearest`). Empty for any other name."""
    if full is None or not isinstance(space, Space) or "&" in name:
        return []
    sites = space._sites(name.strip())
    if not sites or space.resolve(name) in full:
        return []
    return [space.short_name(c)
            for c in space.nearest(space.required(sites[0]), full)]


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


def verdict_case(verdict: str, space: Cases,
                 own: dict[str, str] | None = None) -> str | None:
    """The case a verdict names, read as a name of a witness group is
    (`dl.models`). `own` maps the word
    `derived` or `stored` to the case id of the `@derive` or `@store` line
    the verdict stands on. None for `any` and `other`, which name no one
    case, and for a verdict that denotes no case."""
    if verdict in (ANY, OTHER):
        return None
    if own and verdict in own:
        return own[verdict]
    return space.resolve(verdict)


def _departs(verdict: str, case: str, space: Cases) -> bool:
    """A witness line of this verdict shows `case` departing: the verdict is
    `other`, or it names a case other than `case`. A verdict that names a
    constructor without its fields names the runner's label, which stands
    for every case under that constructor, `case` among them when that is
    its label. The verdict `any` names no case, and neither does a verdict
    that denotes no case, which is a finding of its own."""
    if verdict == OTHER:
        return True
    named = verdict_case(verdict, space)
    return named is not None and named not in (case, case_label(case))


def _constructors(case: str) -> set[str]:
    """Every constructor a case spelled in full takes, nested ones
    included."""
    return set(re.findall(r"\w+", case))


def _names(cases: Iterable[str]) -> set[str]:
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
                         cases: list[str], space: Cases) -> list[Drift]:
    """Where a solver's `@witness` lines and the witness file disagree: a
    line off the form of the witness grammar, a line that names no entry of
    the file, a `@relaxed` slug the header's claims do not carry, and a
    block whose `@reassigned` parameters are not the entry's `assign` keys.
    An entry that no line names is no finding here. A `@derive`
    line names the entry of its case id, and the derive report reads that
    entry. The verdict of each `@witness`, `@derive` and `@store` line
    resolves in `space` (`verdict_case`), and one that denotes no case of
    the solver is a finding.

    An approximated claim is read against the cases as well. A header
    `@approximated:` runs on every case, so each case stands under a witness
    that shows it departing. A case whose branch carries a `@rule` line of
    the claim's slug restates the claim, so the approximation does not run
    on that case and no witness is asked of it."""
    by_id = {e.id: e for e in entries}
    claims = resolved_claims(source)
    slugs = relaxable(claims)
    kinds = {c.slug: c.kind for c in claims}
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

    def verdict_note(line: int, verdict: str,
                     own: dict[str, str] | None = None) -> None:
        if verdict in (ANY, OTHER) or verdict_case(verdict, space, own):
            return
        note(f"line {line}", "",
             mctx("the verdict `{verdict}` denotes no case of the solver")
             .format(verdict=verdict))

    ann = read(source)
    for bad in ann.malformed:
        if bad.word in WITNESS_WORDS:
            note(f"line {bad.line}", "", bad.why)
    for w in ann.witnesses:
        verdict_note(w.line, w.verdict)
    derived = derive_ids(source)
    for d in ann.derives:
        param = derive_param(source, d)
        case = f"{param}={d.proposer}"
        verdict_note(d.line, d.verdict,
                     {DERIVED: case} if case in derived else None)
    for st in ann.stores:
        rel = store_relation(source, st)
        verdict_note(st.line, st.verdict,
                     {STORED: f"{rel}={STORED}"} if rel else None)
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

    def approximated(c: Claim, want: list[str]) -> None:
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
            if not any(_departs(w.verdict, case, space)
                       for w in c.witnesses):
                note(f"line {c.line}", "",
                     mctx("`@{kind} {slug}` is approximated and no witness "
                          "under its `@approximated:` shows case `{case}` "
                          "departing").format(
                         kind=c.kind, slug=c.slug, case=case))

    restated: dict[str, set[str]] = {}
    for c in ann.branch_claims:
        if c.kind != "rule":
            continue
        name = branch_above(source, c.line)
        if name:
            restated.setdefault(c.slug, set()).add(name)

    def not_restated(slug: str) -> list[str]:
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
                     timeouts: Timeouts) -> dict[str, Outcome]:
    """What each case the runner holds gives on the entry's input. A stored
    case is the runner's own, so no `assign` states it; a derived case runs
    `source`, the reassigned one."""
    if not isinstance(entry.output, dict):
        return {}
    ids = sorted(space.runner)
    return runner_outcomes(stem, ids, entry.input, source, timeouts,
                           _label(entry)) if ids else {}


def held_case_labels(source: str) -> list[str]:
    """The cases the solver holds, spelled as the run's FAIL list spells
    them: the cases `impl_choice` holds, or every case the `Choice` spells
    when the solver declares no `impl_choice`, then the cases the runner
    holds under `@derive` and `@store`."""
    try:
        held = held_cases(parse(source), source, full=True)
    except ParseError:
        held = None
    if held is None:
        space = case_space(source)
        if isinstance(space, Space):
            held = space.cases()
        elif isinstance(space, Coarse):
            held = case_branches("", source)
        else:
            held = [space.concept]
    runner = derive_ids(source) | store_ids(source)
    return list(held) + sorted(runner)


def _stated(stem: str, source: str, grid: list[list[int]],
            choice: list[str]) -> tuple[list[str], list[str]]:
    """The cases the solver states on `grid`, by the runner's label and
    spelled in full. A solver that declares `impl_choice` states the cases
    a run on `grid` finds it holding. Another states `choice`, the cases of
    its `Choice` as `held_case_labels` spells them, which no grid
    changes."""
    if declares_held(source):
        full = held_cases(parse(source), source, grid, full=True) or []
        return list(dict.fromkeys(case_label(c) for c in full)), full
    return case_branches(stem, source, grid), choice


def _held_outcomes(stem: str, held: list[str], entry: Entry, source: str,
                   candidates: list[Candidate] | None, resolution: bool,
                   timeouts: Timeouts, where: str) -> dict[str, Outcome]:
    """What each held case gives on the entry's input, None for a case that
    emits nothing there. `source` is the source the entry stands at, and
    `candidates` its run on the entry's input, None when that run timed
    out; a case whose run timed out gives TimedOut, and `timeouts` notes it
    as on the input `where`."""
    runner = [c for c in held if "=" in c]
    if candidates is None:
        out: dict[str, Outcome] = {
            c: TimedOut(c) for c in held if "=" not in c}  # type: ignore[misc]
    else:
        got = case_outcomes(candidates, resolution) | model_outcomes(
            candidates, resolution)
        out = {c: got.get(c) for c in held if "=" not in c}
    if runner:
        out |= runner_outcomes(stem, runner, entry.input, source, timeouts,
                               where)
    return out


def built_witnesses(stem: str, runner: list[str]) -> dict[str, Grid]:
    """The input of the witness the runner builds for each of its cases:
    the derive report's swap for a derived case, and the store report's
    grid for a stored one. A case whose witness is an entry of the file,
    or that no built grid separates, has none here."""
    from dl.derive import derive_report
    from dl.store import OWNED, store_report
    out: dict[str, Grid] = {}
    if any(not c.endswith(f"={STORED}") for c in runner):
        for d in derive_report(stem).derivations:
            if d.case in runner and d.swap is not None:
                out[d.case] = d.swap.input
    if any(c.endswith(f"={STORED}") for c in runner):
        for f in store_report(stem).found:
            if (f.kind == OWNED and f.case_id in runner
                    and f.move is not None and f.move.input is not None):
                out[f.case_id] = f.move.input
    return out


type Scoped = tuple[dict[str, Outcome], str | None]
"""What each held case gives on one witness input, and the runner's case
the witness is built for; None for an entry of the file, which counts for
every pair."""


def _unseparated(held: list[str], outcomes: list[Scoped]) -> list[Drift]:
    """A finding per unordered pair of held cases that give one outcome on
    every witness input that counts for the pair. Train inputs never tell
    two held cases apart, as every held case fits the task, so the
    witnesses do: each entry of the file, and for a pair with a case the
    runner holds, the witness the runner builds for that case."""
    return [
        Drift(entry="", cases=[a, b], expected=None, actual=None,
              kind=UNSEPARATED)
        for i, a in enumerate(held) for b in held[i + 1:]
        if all(o.get(a) == o.get(b) for o, built in outcomes
               if built is None or built in (a, b))
    ]


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


def branch_pairs(held: list[str], source: str,
                 concept: str | None) -> list[tuple[str, str, str, str]]:
    """Each held case A that takes a branch X other than its type's first at
    one choice point, with the held case B that takes that type's first
    branch there and A's branches elsewhere, as (X, that first branch, A,
    B). A case the runner holds stands as X against the concept case, its
    stored counterpart; there the first branch is the concept case."""
    try:
        types = _adts(parse(source).items)
    except ParseError:
        types = {}
    owner = {c: t for t, cs in types.items() for c in cs}
    names = set(held)
    out: list[tuple[str, str, str, str]] = []
    for a in held:
        if "=" in a:
            if concept in names:
                out.append((a, concept, a, concept))
            continue
        record = a.startswith("[")
        roots = [_term(m) for m in _split(a[1:-1])] if record else [_term(a)]
        for i, root in enumerate(roots):
            for x, first, subs in _swaps(root, types, owner):
                for sub in subs:
                    spelled = [_spelled(r) for r in roots[:i] + [sub]
                               + roots[i + 1:]]
                    b = f"[{', '.join(spelled)}]" if record else spelled[0]
                    if b in names:
                        out.append((x, first, a, b))
                        break
    return out


def _subsumes(a: str, b: str, outcomes: list[Scoped]) -> bool:
    """Case B subsumes case A over the inputs that count for the pair: on
    none is A defined and differing from B, and on some A is undefined
    where B gives a grid, so the two are not equivalent there."""
    counted = [o for o, built in outcomes if built is None or built in (a, b)]
    return (all(o.get(a) is None or o.get(a) == o.get(b) for o in counted)
            and any(o.get(a) is None and isinstance(o.get(b), list)
                    for o in counted))


def _subsumed(pairs: list[tuple[str, str, str, str]], held: list[str],
              concept: str | None, outcomes: list[Scoped],
              unseparated: list[Drift]) -> list[Drift]:
    """The held cases that another held case subsumes (`_subsumes`). The
    inputs are the task's pairs, and the witnesses that `_unseparated`
    reads; a pair `unseparated` names is that finding alone.

    A case subsumed by its counterpart in `branch_pairs` is counted under
    the branch X it takes there: one finding per such X, with how many of
    the cases taking X are subsumed by their counterpart, of those that
    have one, and which, when not all are. Each other held case but the
    concept case that cases the solver's `Choice` spells subsume is a
    finding naming it and those cases, less each one that subsumes
    another of them. A case the runner holds stands against the concept
    case alone."""
    same = {frozenset(d.cases) for d in unseparated}
    total: dict[tuple[str, str], int] = {}
    hit: dict[tuple[str, str], list[str]] = {}
    for x, first, a, b in pairs:
        if frozenset((a, b)) in same:
            continue
        total[(x, first)] = total.get((x, first), 0) + 1
        if _subsumes(a, b, outcomes):
            hit.setdefault((x, first), []).append(a)
    out = [Drift(entry="", cases=[x, first], expected=None, actual=None,
                 kind=SUBSUMED, note=f"{len(cases)} of {total[(x, first)]}",
                 subsumed=cases if len(cases) < total[(x, first)] else [])
           for (x, first), cases in hit.items()]
    counted = {a for cases in hit.values() for a in cases}
    spelled = [c for c in held if "=" not in c]
    for a in spelled:
        if a == concept or a in counted:
            continue
        partners = [b for b in spelled if b != a
                    and frozenset((a, b)) not in same
                    and _subsumes(a, b, outcomes)]
        partners = [b for b in partners
                    if not any(_subsumes(c, b, outcomes)
                               for c in partners if c != b)]
        if partners:
            out.append(Drift(entry="", cases=[a, *partners], expected=None,
                             actual=None, kind=SUBSUMED))
    return out


def _held_part(stem: str, held: list[str], entry: Entry, source: str,
               path: Path, resolution: bool,
               where: str) -> tuple[dict[str, Outcome], Timeouts]:
    """What each held case gives on the entry's input at `source`, and the
    timeouts its runs noted."""
    timeouts = Timeouts()
    return _held_outcomes(
        stem, held, entry, source,
        timeouts.run(source, entry.input, path, where), resolution, timeouts,
        where), timeouts


def _pair_outcomes(stem: str, held: list[str], source: str, path: Path,
                   task_id: str, resolution: bool,
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
    runs = [pool.submit(_held_part, stem, held,
                        Entry(id="", separates="", input=ex.input), source,
                        path, resolution, where)
            for where, ex in pairs]
    return [((out, None), timeouts)
            for out, timeouts in (r.result() for r in runs)]


type EntryPart = tuple[Scoped | None, list[str], list[Drift], Timeouts]
"""What one entry adds to the report: its held cases' outcomes, the cases
it states in full, its findings, and the timeouts its runs noted."""


def _entry_part(stem: str, entry: Entry, source: str, path: Path,
                held: list[str], choice: list[str],
                resolution: bool) -> EntryPart:
    """The findings on one entry of the witness file, and what the report
    reads from it besides."""
    timeouts = Timeouts()
    where = _label(entry)
    run_source = assigned_source(source, entry.assign)
    candidates = timeouts.run(run_source, entry.input, path, where)
    separating: Scoped | None = None
    # An entry of a derived case's id holds the derived value in its
    # `assign`, so the held cases stand at the stored value, as the
    # derive report reads that entry; the derived case sets its own
    # parameter.
    if held and entry.assign and entry.id in derive_ids(source):
        separating = (_held_outcomes(
            stem, held, entry, source,
            timeouts.run(source, entry.input, path, where),
            resolution, timeouts, where), None)
    elif held:
        separating = (_held_outcomes(
            stem, held, entry, run_source, candidates, resolution,
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
    space = case_space(run_source, stated)
    names = _names(full)
    findings = _entry_findings(
        entry, space, emitted, actuals | emitted, names | set(actuals),
        _runner_outcomes(stem, entry, space, run_source, timeouts),
        full if declares_held(run_source) else None)
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


def _entry_or_failure(stem: str, entry: Entry, source: str, path: Path,
                      held: list[str], choice: list[str],
                      resolution: bool) -> EntryPart:
    """`_entry_part`, and in place of its findings an ASSIGN finding per
    `assign` string that is no constant of the lib, or a FAILED finding
    when a Souffle run on the entry fails."""
    if bad := assign_findings(entry.assign):
        return None, [], [Drift(entry=_label(entry), cases=[], expected=None,
                                actual=None, kind=ASSIGN, note=line)
                         for line in bad], Timeouts()
    try:
        return _entry_part(stem, entry, source, path, held, choice,
                           resolution)
    except RuntimeError as err:
        return None, [], [Drift(entry=_label(entry), cases=[],
                                expected=None, actual=None, kind=FAILED,
                                note=_souffle_error(err))], Timeouts()


def witness_report(stem: str, file: Path | None = None) -> list[Drift]:
    """The findings of the `witness` command, which its help text in
    `dl.cli` describes. `file` stands in for the task's witness file. Each
    name of a group resolves to a case, which `dl.models` states. An entry
    carrying `assign` runs the reassigned source, and an entry of a derived
    case's id runs the held cases at the stored value, as the derive report
    reads it. The pairs of held cases (`held_case_labels`) are checked over
    the entries and over the witnesses the runner builds
    (`built_witnesses`), with every held case run at the stored value, and
    each held case is checked for the held cases that subsume it
    (`_subsumed`) over those inputs and the task's pairs. With `file`, the
    report holds the entries' findings only: the pair, subsumption and
    `@witness` line findings are the task's own file's."""
    path, task_id = solver_file(stem)
    source = path.read_text()
    if file is not None:
        witness: Witness | None = load_witness_file(file)
    else:
        witness = load_witnesses(task_id)
    entries_only = file is not None
    unwitnessed = [] if witness is None or entries_only else [
        Drift(entry=f"line {at}", cases=[], expected=None, actual=None,
              kind=ANNOTATION, note=text)
        for at, text in unwitnessed_branches(source)]
    held = [] if witness is None else held_case_labels(source)
    choice = [c for c in held if "=" not in c]
    witness = witness or Witness(id=task_id)
    resolution = res_out_stem(stem)
    findings: list[Drift] = []
    cases: list[str] = []
    separating: list[Scoped] = []
    timeouts = Timeouts()
    runner = [c for c in held if "=" in c]
    # Each entry, built witness and pair runs on its own, in a thread: the
    # time goes to Souffle subprocesses. Their parts join in the order a
    # run one after another would give.
    with ThreadPoolExecutor(max_workers=_pool_workers()) as pool:
        built_runs = pool.submit(built_witnesses, stem, runner) \
            if runner and not entries_only else None
        entry_runs = [pool.submit(_entry_or_failure, stem, entry, source,
                                  path, held, choice, resolution)
                      for entry in witness.entries]
        pair_runs = _pair_outcomes(
            stem, held, source, path, task_id, resolution, pool) \
            if held and not entries_only else []
        for run in entry_runs:
            scoped, full, entry_findings, entry_timeouts = run.result()
            if scoped is not None:
                separating.append(scoped)
            cases += [c for c in full if c not in cases]
            findings += entry_findings
            timeouts.merge(entry_timeouts)
        built = built_runs.result() if built_runs else {}
        built_parts = [
            (case, pool.submit(
                _held_part, stem, held, Entry(id=case, separates="", input=grid),
                source, path, resolution,
                mctx("the witness built for `{case}`").format(case=case)))
            for case, grid in built.items()]
        for case, run in built_parts:
            out, built_timeouts = run.result()
            separating.append((out, case))
            timeouts.merge(built_timeouts)
    if entries_only:
        return findings + timeouts.findings
    space = case_space(source, case_branches(stem, source))
    unseparated = _unseparated(held, separating)
    for _scoped, pair_timeouts in pair_runs:
        timeouts.merge(pair_timeouts)
    subsumed = _subsumed(
        branch_pairs(held, source, space.concept), held, space.concept,
        separating + [scoped for scoped, _ in pair_runs],
        unseparated) if held else []
    return (findings + unwitnessed
            + _annotation_findings(source, witness.entries, cases, space)
            + unseparated + subsumed + timeouts.findings)


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
        return [mctx("no run shows `{a}` defined and differing from `{b}` "
                     "({count} cases)")
                .format(a=d.cases[0], b=d.cases[1], count=d.note),
                *(f"  {c}" for c in d.subsumed)]
    if d.kind == UNLISTED:
        return [mctx("{entry}: case {case} is not listed")
                .format(entry=d.entry, case=case) if one else
                mctx("{entry}: these cases are not listed: {case}")
                .format(entry=d.entry, case=case),
                *_side("the solver's output", d.actual)]
    if d.kind == FAILED:
        return [mctx("{entry}: the run failed: {error}")
                .format(entry=d.entry, error=d.note)]
    if d.kind == ASSIGN:
        return [f"{d.entry}: {d.note}"]
    if d.kind == UNRESOLVED and d.note:
        return [mctx("{entry}: the name `{name}` denotes no case of the "
                     "solver; the held cases that take `{name}` and differ "
                     "least from the concept are {cases}")
                .format(entry=d.entry, name=d.cases[0], cases=d.note)]
    if d.kind == UNRESOLVED:
        names = ", ".join(f"`{n}`" for n in d.cases)
        return [mctx("{entry}: the name {names} denotes no case of the solver")
                .format(entry=d.entry, names=names) if one else
                mctx("{entry}: these names denote no case of the solver: "
                     "{names}").format(entry=d.entry, names=names)]
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

