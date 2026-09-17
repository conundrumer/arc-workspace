"""Hand-written grids a solver's cases are pinned to.

A witness file holds grids the author built to tell the solver's cases
apart, each with the outcome every case is expected to give. style.md
states the file's shape.

An entry's `assign` field reassigns a `Params` parameter before the run,
so the entry stands at the assignment its `separates` names rather than
at the stored one.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from dl.annotations import (
    merged_blocks,
    read,
    relaxable,
    resolved_claims,
    witness_blocks,
)
from dl.facts import Candidate
from dl.features_run import NO_CHOICE, case_label
from dl.paths import PROGRAMS_DIR
from dl.render import _grid_lines
from dl.solve import res_out_stem, run_dl_source, solver_file
from dl.source import swap_facts

WITNESS_DIR = PROGRAMS_DIR / "witnesses"

UNDEFINED = "undefined"
"""How a report names the outcome of a case whose cells describe no grid,
and of a case that emits nothing at all. The file writes it as `null` and
the code carries it as None."""

WITNESS_OK = "witness: ok"
"""The pass line, printed when no finding stands."""

DRIFT = "drift"
UNLISTED = "unlisted"
ANNOTATION = "annotation"

type Outcome = list[list[int]] | None
type Assign = dict[str, list[list[object]]]


@dataclass
class Entry:
    """One witness grid and what the solver is expected to give on it.

    `output` is a grid per case, where None is an undefined outcome, or one
    bare grid, the judged output that every case must differ from.

    `assign` holds replacement `Params` facts per parameter, each row the
    arguments of one fact as the `.dl` writes them: a number as a number, a
    lib constant such as `AXIS_H` as a string, and a record such as a
    Position as a list of its arguments.
    """

    id: str
    separates: str
    input: list[list[int]]
    output: dict[str, Outcome] | list[list[int]] = field(default_factory=dict)
    assign: Assign = field(default_factory=dict)
    empty_assign: bool = False
    """The file writes an `assign` key that holds nothing."""

    @property
    def rejected_output(self) -> bool:
        return isinstance(self.output, list)


@dataclass
class Witness:
    id: str
    entries: list[Entry] = field(default_factory=list)


@dataclass
class Drift:
    """One finding on one entry. `kind` is DRIFT when a case gives an
    outcome the entry does not name, UNLISTED when the solver has a case
    the entry's `output` does not name, and ANNOTATION when a `@witness`
    line of the solver and the witness file disagree — over the line's
    form, the entry it names, a `@relaxed` slug, the `@reassigned`
    parameters, or an entry no line names. `entry` is the entry's id,
    followed by the parameters it reassigns, and it is empty when no entry
    answers the line. `expected` stands for nothing on an UNLISTED finding.
    An ANNOTATION finding reads as `note`."""

    entry: str
    case: str
    expected: Outcome | None
    actual: Outcome
    kind: str = DRIFT
    rejected_output: bool = False
    note: str = ""


def witness_path(task_id: str) -> Path:
    return WITNESS_DIR / f"{task_id}.wit.json"


def _output(value: object) -> dict[str, Outcome] | list[list[int]]:
    """An entry's `output` as the code carries it. A bare grid stays a grid;
    a per-case object keys the one case of a solver without a `Choice` by
    the name the runner prints."""
    if isinstance(value, dict):
        return {k or NO_CHOICE: v for k, v in value.items()}
    return value


ENTRY_KEYS = {"id", "separates", "input", "output", "assign"}
REQUIRED_KEYS = {"id", "separates", "input", "output"}


def _is_grid(v: object) -> bool:
    return (isinstance(v, list) and bool(v)
            and all(isinstance(r, list) and r
                    and all(isinstance(c, int) and 0 <= c <= 9 for c in r)
                    for r in v))


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
    elif not _is_grid(out):
        fail("output", "a grid per case, or one rejected output")
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


def load_witnesses(task_id: str) -> Witness | None:
    """The task's witness file, or None when it has none. A file off the
    shape style.md states raises a ValueError."""
    path = witness_path(task_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    _validate(data, path)
    return Witness(
        id=data["id"],
        entries=[
            Entry(
                id=e["id"],
                separates=e["separates"],
                input=e["input"],
                output=_output(e["output"]),
                assign={k: list(v) for k, v in e.get("assign", {}).items()},
                empty_assign="assign" in e and not e["assign"],
            )
            for e in data["witnesses"]
        ],
    )


def _outcome(c: Candidate) -> Outcome:
    return None if (c.error or c.conflicts or c.missing) else c.grid


def _actuals(candidates: list[Candidate], resolution: bool) -> dict[str, Outcome]:
    """What each case gives on one grid, in the order the run emits them. A
    case emitting more than one grid keeps the first."""
    out: dict[str, Outcome] = {}
    for c in candidates:
        name = case_label(c.variant, resolution)
        got = _outcome(c)
        if name not in out or got is None:
            out[name] = got
    return out


def _rows(rows: list[list[object]]) -> list[tuple]:
    """A parameter's replacement facts as `swap_facts` takes them: one tuple
    per fact, and a list argument a record."""
    return [
        tuple(tuple(a) if isinstance(a, list) else a for a in row)
        for row in rows
    ]


def _assigned(source: str, entry: Entry) -> str:
    """The solver source with the entry's reassignments applied."""
    for param, rows in entry.assign.items():
        source = swap_facts(source, param, _rows(rows))
    return source


def _label(entry: Entry) -> str:
    """The entry's id, followed by the parameters it reassigns."""
    if not entry.assign:
        return entry.id
    return f"{entry.id} [{', '.join(entry.assign)}]"


def _entry_findings(entry: Entry, actuals: dict[str, Outcome]) -> list[Drift]:
    """The findings on one entry, given what its input produced."""
    if entry.rejected_output:
        return [
            Drift(entry=_label(entry), case=case, expected=entry.output,
                  actual=got, rejected_output=True)
            for case, got in actuals.items()
            if got == entry.output
        ]
    findings = [
        Drift(entry=_label(entry), case=case, expected=want,
              actual=actuals.get(case))
        for case, want in entry.output.items()
        if actuals.get(case) != want
    ]
    findings += [
        Drift(entry=_label(entry), case=case, expected=None, actual=got,
              kind=UNLISTED)
        for case, got in actuals.items()
        if case not in entry.output
    ]
    return findings


# The words of the witness grammar, which is what this check reports on. A
# line off another form of the grammar is the lint's finding.
WITNESS_WORDS = frozenset({"witness", "relaxed", "reassigned"})


def _params(names: list[str]) -> str:
    """A parameter list as a finding names it."""
    return ", ".join(f"`{n}`" for n in sorted(names)) or "no parameter"


def _annotation_findings(source: str, entries: list[Entry]) -> list[Drift]:
    """Where a solver's `@witness` lines and the witness file disagree: a
    line off the form of the witness grammar, a line that names no entry of
    the file, a `@relaxed` slug the header's claims do not carry, a block
    whose `@reassigned` parameters are not the entry's `assign` keys, an
    entry whose `assign` is empty, and an entry no line names."""
    by_id = {e.id: e for e in entries}
    slugs = relaxable(resolved_claims(source))
    findings: list[Drift] = []

    def note(entry: str, case: str, text: str) -> None:
        findings.append(Drift(entry=entry, case=case, expected=None,
                              actual=None, kind=ANNOTATION, note=text))

    ann = read(source)
    for bad in ann.malformed:
        if bad.word in WITNESS_WORDS:
            note(f"line {bad.line}", "", bad.why)
    named = set()
    for a in merged_blocks(ann.witnesses):
        named.add(a.id)
        entry = by_id.get(a.id)
        if entry is None:
            note(f"line {a.line}", a.id,
                 f"`@witness {a.id}` names no entry of the witness file")
        elif sorted(a.reassigned) != sorted(entry.assign):
            note(a.id, a.id,
                 f"`@reassigned` names {_params(a.reassigned)}; the entry's "
                 f"`assign` names {_params(list(entry.assign))}")
        for slug in a.relaxed:
            if slug not in slugs:
                note(a.id, a.id,
                     f"`@relaxed {slug}` names no `@scene` line of the header "
                     "and no claim the header approximates")
    for e in entries:
        if e.empty_assign:
            note(e.id, e.id, "`assign` is empty; omit the key")
        if e.id not in named:
            note("", e.id, f"entry `{e.id}` of the witness file is named by "
                           "no `@witness` line")
    return findings


def annotation_lines(source: str) -> list[str]:
    """The features of each `@witness` line, one block per line, and
    `no witness lines` when the solver carries none."""
    lines: list[str] = []
    for a in witness_blocks(source):
        lines.append(f"{a.id}: {a.plausibility} {a.verdict}")
        lines += [f"  relaxed: {slug}" for slug in a.relaxed]
        lines += [f"  reassigned: {param}" for param in a.reassigned]
    return lines or ["no witness lines"]


def witness_report(stem: str) -> list[Drift]:
    """Run every witness grid of `stem`'s task through the solver and
    report where the outcomes and the file disagree, then pair each
    `@witness` line of the solver to an entry of the file. An entry
    carrying `assign` runs the reassigned source. A task with no witness
    file reports nothing."""
    path, task_id = solver_file(stem)
    witness = load_witnesses(task_id)
    if witness is None:
        return []
    source = path.read_text()
    resolution = res_out_stem(stem)
    findings: list[Drift] = []
    for entry in witness.entries:
        candidates = run_dl_source(
            _assigned(source, entry), entry.input, solver_path=path)
        findings += _entry_findings(entry, _actuals(candidates, resolution))
    return findings + _annotation_findings(source, witness.entries)


def _side(label: str, value: Outcome) -> list[str]:
    if value is None:
        return [f"  {label}: {UNDEFINED}"]
    return [f"  {label}:", *(f"    {ln}" for ln in _grid_lines(value))]


def _lines_of(d: Drift) -> list[str]:
    case = d.case
    if d.kind == ANNOTATION:
        return [f"{d.entry}: {d.note}" if d.entry else d.note]
    if d.kind == UNLISTED:
        return [f"{d.entry}: case {case} is not listed",
                *_side("the solver's output", d.actual)]
    if d.rejected_output:
        return [f"{d.entry}: case {case} gives the entry's judged output",
                *_side("the judged output", d.actual)]
    return [f"{d.entry}: case {case} gives an output the entry does not name",
            *_side("the entry's output", d.expected),
            *_side("the solver's output", d.actual)]


def render_witness(findings: list[Drift]) -> list[str]:
    """One block per finding, and `witness: ok` when no finding states a
    differing output or an annotation."""
    lines: list[str] = []
    for d in findings:
        lines += _lines_of(d)
    if not any(d.kind in (DRIFT, ANNOTATION) for d in findings):
        lines.append(WITNESS_OK)
    return lines
