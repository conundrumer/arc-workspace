"""Hand-written grids a solver's cases are pinned to.

A witness file holds grids the author built to tell the solver's cases
apart, each with the outcome every case is expected to give.
solver-file.md states the file's shape.

An entry's `assign` field reassigns a `Params` parameter before the run,
so the entry stands at the assignment its `separates` names rather than
at the stored one.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from arc.jsonio import format_file
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
FAILING = (DRIFT, ANNOTATION)
"""The kinds that fail the check."""

type Outcome = list[list[int]] | None
type Assign = dict[str, list[list[object]]]


@dataclass
class Entry:
    """One witness grid and what the solver is expected to give on it.

    `output` is a grid per case, where None is an undefined outcome, or one
    bare grid, the judged output that every case must differ from. The file
    writes the per-case form as groups, one grid under the cases that give
    it; `_output` spreads a group over its cases.

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
    the entry's `output` does not name, and ANNOTATION when a
    `@witness` line of the solver and the witness file disagree — over the
    line's form, the entry it names, a `@relaxed` slug, the `@reassigned`
    parameters, or an entry no line names. `entry` is the entry's id,
    followed by the parameters it reassigns, and it is empty when no entry
    answers the line. `cases` names every case the finding holds for, which
    is the cases that give one outcome where another is expected.
    `expected` stands for nothing on an UNLISTED finding. An ANNOTATION
    finding reads as `note`."""

    entry: str
    cases: list[str]
    expected: Outcome | None
    actual: Outcome
    kind: str = DRIFT
    rejected_output: bool = False
    note: str = ""


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


def _entry_findings(entry: Entry,
                    actuals: dict[str, Outcome]) -> list[Drift]:
    """The findings on one entry, given what its input produced."""
    label = _label(entry)
    if entry.rejected_output:
        return _merged(label, [
            (case, entry.output, got)
            for case, got in actuals.items()
            if got == entry.output
        ], rejected=True)
    findings = _merged(label, [
        (case, want, actuals.get(case))
        for case, want in entry.output.items()
        if actuals.get(case) != want
    ])
    findings += _merged(label, [
        (case, None, got)
        for case, got in actuals.items()
        if case not in entry.output
    ], kind=UNLISTED)
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
    entry whose `assign` is empty, and an entry no line names. A `@derive`
    line names the entry of its case id, and the derive report reads that
    entry.

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
        relaxed_notes(a.id, a.id, a.relaxed)
    for d in ann.derives:
        if param := derive_param(source, d):
            relaxed_notes(f"line {d.line}", f"{param}={d.proposer}", d.relaxed)
    for st in ann.stores:
        if rel := store_relation(source, st):
            relaxed_notes(f"line {st.line}", f"{rel}={STORED}", st.relaxed)
    named |= derive_ids(source) | store_ids(source)
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


def _store_outcomes(stem: str, entry: Entry) -> dict[str, Outcome]:
    """What the stored case of each `<rel>=stored` key of the entry gives on
    the entry's input. The runner owns that case, so no `assign` states
    it."""
    if not isinstance(entry.output, dict):
        return {}
    ids = [c for c in entry.output if c.endswith(f"={STORED}")]
    if not ids:
        return {}
    from dl.store import store_outcome
    return {c: store_outcome(stem, c, entry.input) for c in ids}


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
    findings: list[Drift] = []
    cases: list[str] = []
    for entry in witness.entries:
        candidates = run_dl_source(
            assigned_source(source, entry.assign), entry.input,
            solver_path=path)
        actuals = case_outcomes(candidates, resolution)
        cases += [c for c in actuals if c not in cases]
        actuals |= _store_outcomes(stem, entry)
        findings += _entry_findings(entry, actuals)
    return findings + _annotation_findings(source, witness.entries, cases)


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
    if d.kind == UNLISTED:
        return [mctx("{entry}: case {case} is not listed")
                .format(entry=d.entry, case=case) if one else
                mctx("{entry}: these cases are not listed: {case}")
                .format(entry=d.entry, case=case),
                *_side("the solver's output", d.actual)]
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


def render_witness(findings: list[Drift]) -> list[str]:
    """One block per finding, and `witness: ok` when no finding fails the
    check."""
    lines = finding_lines(findings)
    if not any(d.kind in FAILING for d in findings):
        lines.append(WITNESS_OK)
    return lines
