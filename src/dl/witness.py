"""Hand-written grids a solver's cases are pinned to.

A witness file holds grids the author built to tell the solver's cases
apart, each with the outcome every case is expected to give. style.md
states the file's shape.

An entry's `assign` field reassigns a `Params` parameter before the run,
so the entry stands at the assignment its `hypothesis` names rather than
at the stored one.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from dl.facts import Candidate
from dl.features_run import NO_CHOICE, case_label
from dl.lint import choice_points
from dl.paths import PROGRAMS_DIR
from dl.render import _grid_lines, render_diff
from dl.solve import res_out_stem, run_dl_source, solver_file
from dl.source import swap_facts

WITNESS_DIR = PROGRAMS_DIR / "witnesses"

UNDEFINED = "undefined"
"""How a report names the outcome of a case whose cells describe no grid,
and of a case that emits nothing at all. The file writes it as `null` and
the code carries it as None."""

DRIFT = "drift"
UNLISTED = "unlisted"
DEVIATION = "deviation"

type Outcome = list[list[int]] | None
type Assign = dict[str, list[list[object]]]


@dataclass
class Entry:
    """One witness grid and what the solver is expected to give on it.

    `output` is a grid per case, where None is an undefined outcome, or one
    bare grid, a rejected output that every case must differ from.

    `assign` holds replacement `Params` facts per parameter, each row the
    arguments of one fact as the `.dl` writes them: a number as a number, a
    lib constant such as `AXIS_H` as a string, and a record such as a
    Position as a list of its arguments.

    `violates` names the invariants of the inputs the grid breaks, one
    phrase each, and `rejected` names the rules of the branch the grid
    witnesses whose outcome the concept statement rejects, one phrase each.
    """

    id: str
    hypothesis: str
    input: list[list[int]]
    output: dict[str, Outcome] | list[list[int]] = field(default_factory=dict)
    assign: Assign = field(default_factory=dict)
    violates: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)

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
    the entry's `output` does not name, and DEVIATION when a branch's
    `@deviation` line and its witness disagree. `entry` is the entry's id,
    followed by the parameters it reassigns, and it is empty on a branch
    with no witness. `expected` stands for nothing on an UNLISTED finding.
    A DEVIATION finding names its branch in `case` and reads as `note`."""

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


ENTRY_KEYS = {"id", "hypothesis", "input", "output",
              "assign", "violates", "rejected"}
REQUIRED_KEYS = {"id", "hypothesis", "input", "output"}


def _is_grid(v: object) -> bool:
    return (isinstance(v, list) and bool(v)
            and all(isinstance(r, list) and r
                    and all(isinstance(c, int) and 0 <= c <= 9 for c in r)
                    for r in v))


def _is_strings(v: object) -> bool:
    return isinstance(v, list) and all(isinstance(s, str) for s in v)


def _check_entry(e: object, fail: Callable[[str, str], None]) -> None:
    if not isinstance(e, dict):
        fail("", "an entry is an object")
        return
    if extra := set(e) - ENTRY_KEYS:
        fail("", f"unknown key {sorted(extra)}")
    if missing := REQUIRED_KEYS - set(e):
        fail("", f"missing key {sorted(missing)}")
    for k in ("id", "hypothesis"):
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
    for k in ("violates", "rejected"):
        if not _is_strings(e.get(k, [])):
            fail(k, "a list of strings")


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
                hypothesis=e["hypothesis"],
                input=e["input"],
                output=_output(e["output"]),
                assign={k: list(v) for k, v in e.get("assign", {}).items()},
                violates=list(e.get("violates", [])),
                rejected=list(e.get("rejected", [])),
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


def _case_labels(source: str) -> tuple[str, dict[tuple[int, str], str]] | None:
    """The label of the concept case, and the label of the case that takes
    each other branch with every other choice point left at its concept
    branch.
    None when the source declares no `Choice`, or when a field of a
    record-typed `Choice` names no ADT."""
    points = choice_points(source)
    if not points or any(not p.branches for p in points):
        return None
    record = points[0].field >= 0
    concept = [p.branches[0].name for p in points]

    def label(names: list[str]) -> str:
        return "[" + ", ".join(names) + "]" if record else names[0]

    cases: dict[tuple[int, str], str] = {}
    for p in points:
        for b in p.branches[1:]:
            names = list(concept)
            names[p.field if record else 0] = b.name
            cases[(p.field, b.name)] = label(names)
    return label(concept), cases


def _divergences(entries: list[Entry], case: str, base: str) -> list[Entry]:
    """The divergence witnesses of `case` against `base`: the entries that
    name both and give them different outcomes."""
    return [e for e in entries
            if isinstance(e.output, dict) and case in e.output
            and base in e.output and e.output[case] != e.output[base]]


def _deviation_findings(source: str, entries: list[Entry]) -> list[Drift]:
    """Each other branch's `-` and `~` estimates against the
    `violates` and `rejected` of its divergence witness with the fewest
    violated invariants."""
    labels = _case_labels(source)
    if labels is None:
        return []
    base, cases = labels
    findings: list[Drift] = []
    for p in choice_points(source):
        for b in p.branches[1:]:
            if b.deviation is None:
                continue
            case = cases[(p.field, b.name)]
            found = _divergences(entries, case, base)
            if not found:
                findings.append(Drift(
                    entry="", case=b.name, expected=None, actual=None,
                    kind=DEVIATION,
                    note=f"branch {b.name} carries an `@deviation` line and "
                         "has no divergence witness"))
                continue
            witness = min(found, key=lambda e: len(e.violates))
            relaxed, _added, contradicted = b.deviation
            for mark, stated, got, what in (
                    ("-", relaxed, len(witness.violates),
                     "violates {} invariants of the inputs"),
                    ("~", contradicted, len(witness.rejected),
                     "rejects {} rules")):
                if stated != got:
                    findings.append(Drift(
                        entry=_label(witness), case=b.name, expected=None,
                        actual=None, kind=DEVIATION,
                        note=f"branch {b.name} states `{mark}{stated}`, and "
                             f"its witness {what.format(got)}"))
    return findings


def witness_report(stem: str) -> list[Drift]:
    """Run every witness grid of `stem`'s task through the solver and
    report where the outcomes and the file disagree, then read each
    other branch's `@deviation` estimates against its divergence
    witnesses. An entry carrying `assign` runs the reassigned source. A task
    with no witness file reports nothing."""
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
    return findings + _deviation_findings(source, witness.entries)


def _side(label: str, value: Outcome) -> list[str]:
    if value is None:
        return [f"  {label}: {UNDEFINED}"]
    return [f"  {label}:", *(f"    {ln}" for ln in _grid_lines(value))]


def _lines_of(d: Drift) -> list[str]:
    case = d.case
    if d.kind == DEVIATION:
        return [f"{d.entry}: {d.note}" if d.entry else d.note]
    if d.kind == UNLISTED:
        return [f"{d.entry}: case {case} is not listed",
                *_side("actual", d.actual)]
    if d.rejected_output:
        return [f"{d.entry}: case {case} produces the rejected output",
                *_side("rejected", d.actual)]
    head = f"{d.entry}: case {case} drifted"
    if isinstance(d.expected, list) and isinstance(d.actual, list):
        return [head, *(f"  {ln}" for ln in render_diff(d.expected, d.actual))]
    return [head, *_side("expected", d.expected), *_side("actual", d.actual)]


def render_witness(findings: list[Drift]) -> list[str]:
    """One block per finding, and `no drift` when none of them is a drift or
    a deviation."""
    lines: list[str] = []
    for d in findings:
        lines += _lines_of(d)
    if not any(d.kind in (DRIFT, DEVIATION) for d in findings):
        lines.append("no drift")
    return lines
