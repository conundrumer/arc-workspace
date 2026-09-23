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
from collections.abc import Callable, Iterable
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
from dl.dlparse import ParseError, parse
from dl.facts import Candidate
from dl.features import case_branches, declares_held, held_cases
from dl.features_run import NO_CHOICE, case_label, case_members
from dl.lint import branch_above, unwitnessed_branches
from dl.models import Cases, Coarse, Space, case_space, model_label
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
UNRESOLVED = "unresolved"
ANNOTATION = "annotation"
UNSEPARATED = "unseparated"
FAILING = (DRIFT, UNRESOLVED, ANNOTATION, UNSEPARATED)
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
    """One finding on one entry. `kind` is DRIFT, UNLISTED, UNRESOLVED,
    ANNOTATION or UNSEPARATED, each the finding the `witness` help text in
    `dl.cli` describes; an UNSEPARATED finding names the two cases in
    `cases`. `entry` is the entry's id, followed by the parameters it reassigns, and
    it is empty when no entry answers the line. `cases` names every case
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
                empty_assign="assign" in e and not e["assign"],
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


def runner_outcomes(stem: str, ids: Iterable[str], grid: list[list[int]],
                    source: str) -> dict[str, Outcome]:
    """What each case the runner holds gives on one grid, by its id. A
    derived case runs `source`, and a stored case the solver's file."""
    from dl.derive import derived_outcome
    from dl.store import store_outcome
    return {c: store_outcome(stem, c, grid) if c.endswith(f"={STORED}")
            else derived_outcome(stem, c, grid, source)
            for c in ids}


def branch_outcomes(space: Cases, candidates: list[Candidate],
                    resolution: bool) -> dict[str, Outcome]:
    """What each branch model of `space` gives on one grid, by the model's
    name; None for a model that emits nothing."""
    got = case_outcomes(candidates, resolution) | model_outcomes(
        candidates, resolution)
    return {name: got.get(label) for name, label in space.models().items()}


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
                    impl: set[str] | None = None) -> list[Drift]:
    """The findings on one entry, given what its input produced. `emitted`
    holds the outcome of each case the run emits, spelled with its fields;
    `actuals` holds those and the runner's labels of them, `held` the cases
    the solver states, and `runner` the outcomes of the cases the runner
    holds that the entry names. `impl` holds the cases `impl_choice` holds,
    and is None when the solver declares no `impl_choice`; a name whose case
    it does not hold denotes no case of the solver."""
    label = _label(entry)
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
                            and case not in impl
                            and case_label(case) not in impl):
            unresolved.append(name)
            continue
        named.add(case)
        named |= {m for m in space.models().values()
                  if case_label(m) == case}
        got = runner.get(case) if case in runner else actuals.get(case)
        if got != want:
            rows.append((name, want, got))
    findings = _merged(label, rows)
    if unresolved:
        findings.append(Drift(entry=label, cases=unresolved, expected=None,
                              actual=None, kind=UNRESOLVED))
    findings += _merged(label, [
        (name, None, actuals.get(case))
        for name, case in space.models().items()
        if case not in named
        and (case in actuals or case_label(case) in held)
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
    `other`, or it names a case of another label than `case`. The verdict
    `any` names no case, and neither does a verdict that denotes no case,
    which is a finding of its own."""
    if verdict == OTHER:
        return True
    named = verdict_case(verdict, space)
    return (named is not None and named != case
            and case_label(named) != case_label(case))


def _no_witness_note(c: Claim) -> str:
    return mctx("`@{kind} {slug}` is approximated and has no `@witness` "
                "line under its `@approximated:`").format(kind=c.kind,
                                                          slug=c.slug)


def _annotation_findings(source: str, entries: list[Entry],
                         cases: list[str], space: Cases) -> list[Drift]:
    """Where a solver's `@witness` lines and the witness file disagree: a
    line off the form of the witness grammar, a line that names no entry of
    the file, a `@relaxed` slug the header's claims do not carry, a block
    whose `@reassigned` parameters are not the entry's `assign` keys, an
    entry whose `assign` is empty, and an entry no line names. A `@derive`
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


def _runner_outcomes(stem: str, entry: Entry, space: Cases,
                     source: str) -> dict[str, Outcome]:
    """What each case the runner holds and the entry names gives on the
    entry's input. A stored case is the runner's own, so no `assign` states
    it; a derived case runs `source`, the reassigned one."""
    if not isinstance(entry.output, dict):
        return {}
    ids = [c for c in entry.output if c in space.runner]
    return runner_outcomes(stem, ids, entry.input, source) if ids else {}


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


def _held_outcomes(stem: str, held: list[str], entry: Entry, source: str,
                   candidates: list[Candidate],
                   resolution: bool) -> dict[str, Outcome]:
    """What each held case gives on the entry's input, None for a case that
    emits nothing there. `source` is the source the entry stands at, and
    `candidates` its run on the entry's input."""
    got = case_outcomes(candidates, resolution) | model_outcomes(
        candidates, resolution)
    runner = [c for c in held if "=" in c]
    out = {c: got.get(c) for c in held if "=" not in c}
    if runner:
        out |= runner_outcomes(stem, runner, entry.input, source)
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


def witness_report(stem: str, file: Path | None = None) -> list[Drift]:
    """The findings of the `witness` command, which its help text in
    `dl.cli` describes. `file` stands in for the task's witness file. Each
    name of a group resolves to a case, which `dl.models` states. An entry
    carrying `assign` runs the reassigned source, and an entry of a derived
    case's id runs the held cases at the stored value, as the derive report
    reads it. The pairs of held cases (`held_case_labels`) are checked over
    the entries and over the witnesses the runner builds
    (`built_witnesses`), with every held case run at the stored value."""
    path, task_id = solver_file(stem)
    source = path.read_text()
    if file is not None:
        witness: Witness | None = load_witness_file(file)
    else:
        witness = load_witnesses(task_id)
    unwitnessed = [] if witness is None else [
        Drift(entry=f"line {at}", cases=[], expected=None, actual=None,
              kind=ANNOTATION, note=text)
        for at, text in unwitnessed_branches(source)]
    held = [] if witness is None else held_case_labels(source)
    witness = witness or Witness(id=task_id)
    resolution = res_out_stem(stem)
    findings: list[Drift] = []
    cases: list[str] = []
    separating: list[Scoped] = []
    for entry in witness.entries:
        run_source = assigned_source(source, entry.assign)
        candidates = run_dl_source(run_source, entry.input, solver_path=path)
        # An entry of a derived case's id holds the derived value in its
        # `assign`, so the held cases stand at the stored value, as the
        # derive report reads that entry; the derived case sets its own
        # parameter.
        if held and entry.assign and entry.id in derive_ids(source):
            separating.append((_held_outcomes(
                stem, held, entry, source,
                run_dl_source(source, entry.input, solver_path=path),
                resolution), None))
        elif held:
            separating.append((_held_outcomes(stem, held, entry, run_source,
                                              candidates, resolution), None))
        actuals = case_outcomes(candidates, resolution)
        stated = case_branches(stem, run_source, entry.input)
        for name in stated:
            actuals.setdefault(name, None)
        cases += [c for c in actuals if c not in cases]
        emitted = model_outcomes(candidates, resolution)
        space = case_space(run_source, stated)
        findings += _entry_findings(
            entry, space, emitted, actuals | emitted,
            set(stated) | set(actuals),
            _runner_outcomes(stem, entry, space, run_source),
            set(stated) if declares_held(run_source) else None)
    runner = [c for c in held if "=" in c]
    for case, grid in (built_witnesses(stem, runner) if runner else {}).items():
        built = Entry(id=case, separates="", input=grid)
        separating.append((_held_outcomes(
            stem, held, built, source,
            run_dl_source(source, grid, solver_path=path), resolution), case))
    return (findings + unwitnessed
            + _annotation_findings(source, witness.entries, cases,
                                   case_space(source,
                                              case_branches(stem, source)))
            + _unseparated(held, separating))


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
    if d.kind == UNLISTED:
        return [mctx("{entry}: case {case} is not listed")
                .format(entry=d.entry, case=case) if one else
                mctx("{entry}: these cases are not listed: {case}")
                .format(entry=d.entry, case=case),
                *_side("the solver's output", d.actual)]
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


def render_witness(findings: list[Drift]) -> list[str]:
    """One block per finding, and `witness: ok` when no finding fails the
    check."""
    lines = finding_lines(findings)
    if not any(d.kind in FAILING for d in findings):
        lines.append(WITNESS_OK)
    return lines
