"""Hand-written grids a solver's cases are pinned to.

A witness file holds grids the author built to tell the solver's cases
apart, each with the outcome every case is expected to give.
procedure.md states the file's shape.

An entry's `assign` field reassigns a `Params` parameter before the run,
so the entry stands at the assignment its `separates` names rather than
at the stored one.
"""

import json
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from pathlib import Path

from arc.jsonio import format_file
from controlled_markdown import mctx
from dl.annotations import (
    Claim,
    merged_blocks,
    read,
    relaxable,
    resolved_claims,
    witness_blocks,
)
from dl.facts import Candidate
from dl.features_run import NO_CHOICE, case_label, case_members
from dl.lint import branch_above, concept_case
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
UNDEFINED_CONCEPT = "undefined-concept"

FAILING = (DRIFT, ANNOTATION, UNDEFINED_CONCEPT)
"""The kinds that fail the check."""

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
    the entry's `output` does not name, UNDEFINED_CONCEPT when the run
    leaves the concept case's outcome undefined, and ANNOTATION when a
    `@witness` line of the solver and the witness file disagree — over the
    line's form, the entry it names, a `@relaxed` slug, the `@reassigned`
    parameters, or an entry no line names. `entry` is the entry's id,
    followed by the parameters it reassigns, and it is empty when no entry
    answers the line. `expected` stands for nothing on an UNLISTED finding,
    and neither `expected` nor `actual` stands for anything on an
    UNDEFINED_CONCEPT one. An ANNOTATION finding reads as `note`."""

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
    shape procedure.md states raises a ValueError."""
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


def read_witness_data(task_id: str) -> dict:
    """The task's witness file as JSON, checked against the shape. A task
    with no file yet gets the data an empty file holds."""
    path = witness_path(task_id)
    if not path.exists():
        return {"id": task_id, "witnesses": []}
    data = json.loads(path.read_text())
    _validate(data, path)
    return data


def write_witness_data(task_id: str, data: dict) -> Path:
    """Write a witness file, after the shape check. Every write of a witness
    file goes through here, so one layout stands over the directory: the
    file's own conventions, and every grid one row per line."""
    path = witness_path(task_id)
    _validate(data, path)
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


def undefined_concept(label: str, concept: str,
                      outcomes: dict[str, Outcome],
                      named: Collection[str] = ()) -> list[Drift]:
    """The finding on an entry whose concept case the run leaves undefined.
    `outcomes` carries an undefined case as None, and a case that emitted
    nothing has no row there. `named` supplies the case names the entry
    lists. The finding stands on a concept case that `outcomes` or `named`
    holds; a concept case the solver leaves unspelled gets none."""
    if not concept or concept not in set(outcomes) | set(named):
        return []
    if outcomes.get(concept) is not None:
        return []
    return [Drift(entry=label, case=concept, expected=None, actual=None,
                  kind=UNDEFINED_CONCEPT)]


def _entry_findings(entry: Entry, actuals: dict[str, Outcome],
                    concept: str) -> list[Drift]:
    """The findings on one entry, given what its input produced."""
    findings = undefined_concept(
        _label(entry), concept, actuals,
        () if entry.rejected_output else entry.output)
    if entry.rejected_output:
        return findings + [
            Drift(entry=_label(entry), case=case, expected=entry.output,
                  actual=got, rejected_output=True)
            for case, got in actuals.items()
            if got == entry.output
        ]
    findings += [
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

FOREIGN = "foreign"
"""The plausibility of a witness the generator never produces."""

ANY = "any"
"""The verdict the generator pairs with any case's output, so no case
departs on it."""

CONCEPT = "concept"
"""The verdict that names the concept case."""


def _params(names: list[str]) -> str:
    """A parameter list as a finding names it."""
    return ", ".join(f"`{n}`" for n in sorted(names)) or "no parameter"


def _departs(verdict: str, case: str, concept: str) -> bool:
    """A witness line of this verdict shows `case` departing: the verdict is
    not `any`, and it names some other case. A verdict of `concept` names
    the concept case."""
    if verdict == ANY:
        return False
    named = concept if verdict == CONCEPT else verdict
    return named != case and named not in case_members(case)


def _no_witness_note(c: Claim) -> str:
    return mctx("`@{kind} {slug}` is approximated and has no `@witness` "
                "line under its `@approximated:`").format(kind=c.kind,
                                                          slug=c.slug)


def _annotation_findings(source: str, entries: list[Entry],
                         cases: list[str]) -> list[Drift]:
    """Where a solver's `@witness` lines and the witness file disagree: a
    line off the form of the witness grammar, a line that names no entry of
    the file, a `@relaxed` slug the header's claims do not carry, a block
    whose `@reassigned` parameters are not the entry's `assign` keys, an
    entry whose `assign` is empty, and an entry no line names.

    An approximated claim is read against the cases as well. A header
    `@approximated:` runs on every case, and a branch one on the cases its
    branch holds, so each of those cases stands under a witness that shows
    it departing. A case whose branch carries a `@rule` line of the claim's
    slug restates the claim, so the header's approximation does not run on
    that case and no witness is asked of it."""
    by_id = {e.id: e for e in entries}
    claims = resolved_claims(source)
    slugs = relaxable(claims)
    kinds = {c.slug: c.kind for c in claims}
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
                 mctx("`@witness {id}` names no witness in the file")
                 .format(id=a.id))
        elif sorted(a.reassigned) != sorted(entry.assign):
            note(a.id, a.id,
                 mctx("`@reassigned` names {named}; the witness's `assign` "
                      "names {holds}").format(
                     named=_params(a.reassigned),
                     holds=_params(list(entry.assign))))
        for slug in a.relaxed:
            if slug in slugs:
                continue
            held = kinds.get(slug)
            note(a.id, a.id,
                 mctx("`@relaxed {slug}` names the `@{held} {slug}` line; "
                      "`@relaxed` names a `@scene` line")
                 .format(slug=slug, held=held)
                 if held else
                 mctx("`@relaxed {slug}` names no line of the header")
                 .format(slug=slug))
    concept = concept_case(source)

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
            if not any(_departs(w.verdict, case, concept) for w in c.witnesses):
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
        return [k for k in cases if not names & set(case_members(k))]

    for c in ann.claims:
        if c.approximated:
            approximated(c, not_restated(c.slug))
    for c in ann.branch_claims:
        if not c.approximated:
            continue
        name = branch_above(source, c.line)
        approximated(c, [k for k in cases if name in case_members(k)]
                     if name else [])
    for e in entries:
        if e.empty_assign:
            note(e.id, e.id, mctx("`assign` is empty; omit the key"))
        if e.id not in named:
            note("", e.id,
                 mctx("witness `{id}` of the file is named by no `@witness` "
                      "line").format(id=e.id))
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


def witness_report(stem: str) -> list[Drift]:
    """Run every witness grid of `stem`'s task through the solver and
    report where the outcomes and the file disagree, then pair each
    `@witness` line of the solver to an entry of the file. An entry
    carrying `assign` runs the reassigned source. A task with no witness
    file runs no grid, and every `@witness` line of the solver names no
    entry."""
    path, task_id = solver_file(stem)
    source = path.read_text()
    witness = load_witnesses(task_id) or Witness(id=task_id)
    resolution = res_out_stem(stem)
    concept = concept_case(source)
    findings: list[Drift] = []
    cases: list[str] = []
    for entry in witness.entries:
        candidates = run_dl_source(
            assigned_source(source, entry.assign), entry.input,
            solver_path=path)
        actuals = case_outcomes(candidates, resolution)
        cases += [c for c in actuals if c not in cases]
        findings += _entry_findings(entry, actuals, concept)
    return findings + _annotation_findings(source, witness.entries, cases)


def _side(label: str, value: Outcome) -> list[str]:
    if value is None:
        return [f"  {label}: {UNDEFINED}"]
    return [f"  {label}:", *(f"    {ln}" for ln in _grid_lines(value))]


def _lines_of(d: Drift) -> list[str]:
    case = d.case
    if d.kind == ANNOTATION:
        return [f"{d.entry}: {d.note}" if d.entry else d.note]
    if d.kind == UNDEFINED_CONCEPT:
        return [mctx("{entry}: the concept case {case} is {undefined}; take "
                     "another input, or drop the peer with the statement that "
                     "no witness exists").format(
            entry=d.entry, case=case, undefined=UNDEFINED)]
    if d.kind == UNLISTED:
        return [mctx("{entry}: case {case} is not listed")
                .format(entry=d.entry, case=case),
                *_side("the solver's output", d.actual)]
    if d.rejected_output:
        return [mctx("{entry}: case {case} gives the witness's judged output")
                .format(entry=d.entry, case=case),
                *_side("the judged output", d.actual)]
    return [mctx("{entry}: case {case} gives an output the witness does not "
                 "name").format(entry=d.entry, case=case),
            *_side("the witness's output", d.expected),
            *_side("the solver's output", d.actual)]


def finding_lines(findings: list[Drift]) -> list[str]:
    """One block per finding, with no pass line."""
    return [line for d in findings for line in _lines_of(d)]


def render_witness(findings: list[Drift]) -> list[str]:
    """One block per finding, and `witness: ok` when no finding fails the
    check."""
    lines = finding_lines(findings)
    if not any(d.kind in FAILING for d in findings):
        lines.append(WITNESS_OK)
    return lines
