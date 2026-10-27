"""One Souffle case run again on one pair with every relation of its
program written out, each by its arclog name, so that a mismatch report can
give the first relation whose rows differ, on a program from which each
clause of a branch the case does not take is dropped (`taken_program`), so
that the rows are the case's own; the JSON form of that rerun; and
the kept JSON of a rerun that gave rows, which stands while each input of
the rerun is unchanged (`kept_json`); and the rows of the cases the row
parity check runs on each pair, projected onto the columns the converter
maps, with the relations the check leaves out (`case_rows`); and, for each of
those cases, the rows of the relations of `Determine` at the run of its
component over the task's examples, on the program from which each clause of a
branch that neither that case nor the concept case takes is dropped
(`determination_entry`).

`case_rows` writes those rows to a file (`write_json`) as each relation's entry
is made, so that it holds at once the runs of one case and the entry of one
relation, whose rows are held as their JSON texts (`JsonText`).

The check (`arclog_convert.row_parity`) runs the concept case and, for each
`Choice` constructor (an ALT) that no case run before takes, the first case
of `Loaded.every` that takes it (`cases_to_run`); `Loaded.every` holds no case
that an `exclude` form leaves out. Each relation of the program that a run
outputs (`every_relation`) is compared, or has a line of its own, by the
first of these that holds (`classify`):

- `skip`, "an input of the Souffle program": a top-level lib relation
  marked `// @input`.
- `skip`, "a relation of the converter's Souffle text that no arclog relation
  stands for": the converter writes, beside the name map, the Souffle text
  that derives the rows of the relations it adds (`parity.text_path`,
  `arclog_convert.parity_text`), and `load_once` adds it, with the components
  it instantiates, to the solver's program; the relations and instances the
  text declares are in `Loaded.added`. The converter writes as well the text
  of the relations it adds inside `Determine` (`parity.determination_text_path`),
  which `load_once` adds to the program of the determination run alone
  (`Loaded.determination`).
- `skip`, "a lib relation that no clause of the solver writes and no arclog
  relation stands for": the lib declares it, at the top level or in a
  component of the lib, so it holds rows the lib derives; no clause of the
  solver heads it (it is no input port of an instance that the solver
  writes); and no `&` name of the name map stands for it.
- `skip`, "its rows are facts alone and no arclog relation stands for it":
  no clause with a body heads it.
- compared, where the column map has an entry for it; a relation whose entry
  holds no column to compare is compared as present or absent. A relation
  with an entry for each of several writings is compared in each case on the
  columns of the writing the case takes (`parity.column_entry`). Two Souffle
  columns that the entry gives one label hold the engine's one column twice, so
  that a Souffle row whose two columns differ is a row of Souffle's side alone.
- `uncompared`, "no entry in the column map", or, for a relation that the
  converter folds and made no check relation of, the converter's reason
  (`NameMap.untranslated`).

A Souffle relation that the converter folds into other arclog relations, such
as an input of an instance that its shape reads inline or a relation written
as a quantifier, has a check relation in the corpus (`arclog_convert.checks`):
the converter's translation of the relation's own clauses, under an arclog
name of its own that no relation reads. The name map gives that name with the
Souffle relation, so the relation is compared like any other. An `equal` line
of such a relation proves that the converter's translation of the relation's
clauses derives Souffle's rows of it; the fold of those clauses into the
relations that read them is checked by those relations' own lines.

Each arclog relation with `&` of the name map (`relations` and `unmapped`)
that no relation of the run maps to (`relation_names`), and that is no relation of
`Determine` the check compares (`determined_relations`), is `skip`, "each Souffle
relation it stands for is inline, with no rows of its own", where it has
Souffle relations and each is declared `inline`, and `uncompared`, "no Souffle
relation of the run stands for it", otherwise. A relation of the run that
several arclog relations hold, and an arclog relation that holds several
relations of the run, are compared once for each pair. `arclog-cli row-parity` gives the rest
of the verdicts, and `uncompared` "no case's program has a relation of that
name" for a relation that no case it runs has, and "no case the check runs
reads it from `&output`" for one that a case has and no case's `&output`
reads, at any depth. In a case the check compares a relation only where the
case's `&output` reads it or is it, or where it is a check relation
(`NameMap.checks`), which the case counts as read though nothing reads it
(`case_rows` writes their names as `check_relations`). An `equal` line proves that
the relation's rows in each case that derives it and whose `&output` reads
it, or that is a check relation, at the stored parameters, are these rows over the columns the converter maps
(`engine/arclog-cli/src/row_parity.rs` gives the rest). Where the relation is
one of the converter's Souffle text, the rows are those the text's clauses
derive with the solver's program, which says nothing on whether those clauses
hold what the solver means; that rests on the lines of the solver's relations
that read them.

A relation of `Determine` that the name map gives an arclog name and the
column map an entry is compared as well with Souffle's rows of it at the run
of the `Determine` component over the task's examples, once for the task
(`determination_entry`), as `solver.determine.determine` makes it, on the
program of `solver.determine.run_program` over `Loaded.determination` from which
each clause of a branch that neither that case nor the concept case takes is
dropped (`taken_program`), for each case the check runs (Souffle's one
`Determine` run reads the concept case's rows where a clause names a
constructor of the concept): a relation with an Example leaf in its column map
per train pair, and any other once for the task. The check compares a relation at the first case it
runs whose program has a relation of that name, with the rows of that case's
entry (a `DET` inside an `ALT` is in the program of the cases that take the
branch). So is a relation of the converter's text of the
determination run: the name map gives it the component `Determine` and its path
from the top level of that program, and any other relation of `Determine` its
path under the instance of `Determine`."""

import hashlib
import json
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any, TextIO

from arc.task import Example
from cli.common import LIMITS, engine, solver_path
from engine import (AdtValue, Engine, NilValue, ParseFailure, Program, RecordValue, RelationName, Rows,
                    RunFailure, Scope, Tuples, TypeName, checkout)
from engine.memo import hash_files, read_or_make
from engine.program import (AtomLiteral, BodyLiteral, Comparison, ComparisonOperator,
                            ConstructorTerm, Disjunction, Qualifier, Term, Unit, Value, as_grid,
                            own, subterms)
from arclog_convert.parity_text import FORMS
from parity import (PARAMS_COMPONENT, Entry, NameMap, case_name, column_entry, columns_path,
                    determination_text_path, name_map, relation_names, snapshot, text_path)
from parity.idents import (Ambiguous, IdentSources, Minted, NoMembers, Source, Unresolved, Writer, ident_sources,
                           kind_of, leaves)
from solver.aggregate import Solver
from solver.cases import cases as cases_of
from solver.determine import RunProgram, run_program
from solver.graph import Graph
from solver.load import load
from solver.model import Base, Case, Lib, concept_branch
from solver.open_values import FieldOff, field_readings
from solver.outcome import Assignment
from solver.per_case import parameter_reading
from solver.pair_runs import examples
from solver.probe import example_inputs
from solver.solve import output_rows, relations_at
from solver.undefined import Undefined
from solver.variant_limits import over_examples
from solver.vocabulary import DETERMINE_SCOPE, INPUT, OPEN_VALUE
from souffle.parser import relation_name as relation_at


class NoSuchCase(LookupError):
    """No case of the solver has the arclog name asked for."""


class NoSuchPair(LookupError):
    """The solver's task has no pair of the name asked for."""


def every_relation(eng: Engine, program: Program) -> list[RelationName]:
    """Each relation of `program` a run can output, by its name from the
    top level: those declared there, then those each instance reaches, in
    declaration order; an `inline` relation has no rows of its own, and no
    run outputs it."""
    index = eng.index(program)
    kept = [r for r in program.relations if Qualifier.INLINE not in r.qualifiers]
    out = [RelationName((), r.name) for r in kept if not r.scope.components]

    def walk(scope: tuple[str, ...], prefix: tuple[str, ...], depth: int) -> None:
        if depth > len(program.components):
            return
        for inst in program.instances:
            if inst.scope.components != scope:
                continue
            comp = index.component(inst.component, Scope(scope))
            if comp is None:
                continue
            for c in index.chain(comp):
                inner = (*c.scope.components, c.name)
                out.extend(RelationName((*prefix, inst.name), r.name)
                           for r in kept if r.scope.components == inner)
                walk(inner, (*prefix, inst.name), depth + 1)

    walk((), (), 0)
    return list(dict.fromkeys(out))


@dataclass(frozen=True)
class Loaded:
    """A solver loaded once, with its name map and its cases, for the runs
    of one or more of its cases on its pairs."""

    eng: Engine
    solver: Solver
    names: NameMap | None
    every: tuple[Case, ...]
    determination: Solver
    """The solver's file with the converter's Souffle text of the determination
    run (`determination_text_path`), in place of the text of the cases, whose
    program the determination runs (`run_program`)."""
    added: frozenset[str] = frozenset()
    """The relations and instances at the top level that the converter's Souffle
    text (`load_once`) declares and the solver's file does not."""

    def pair(self, pair: str) -> Example:
        """The example of the pair whose name is `pair`. Raises `NoSuchPair`."""
        ex = next((ex for p, ex in examples(self.solver.given_task) if p.text == pair), None)
        if ex is None:
            raise NoSuchPair(pair)
        return ex

    def taking(self, chosen: Case) -> Solver:
        """The solver with the program of `taken_program` that drops the
        constructors `chosen` does not take (`untaken`), to run `chosen` on
        each pair (`run`); the program is built once, so that the caches keyed
        by it serve every pair."""
        return taking(self.solver, untaken(self.solver, chosen.base))

    def run(self, taken: Solver, chosen: Case, ex: Example, rels: list[RelationName]
            ) -> Mapping[RelationName, Rows] | Undefined | RunFailure:
        """The rows of `rels` of the case `chosen` run on the input of `ex`
        on `taken`, which `taking(chosen)` gave, so that they are the case's
        own."""
        return relations_at(self.eng, taken, chosen, as_grid(ex.input), rels, Assignment(()), LIMITS)


def taking(solver: Solver, dropped: frozenset[str]) -> Solver:
    """`solver` with the program of `taken_program` for `dropped`."""
    return replace(solver, program=taken_program(solver, dropped))


def with_text(eng: Engine, solver: Solver, text: str) -> Solver:
    """`solver` with its program followed by `text`, a Souffle text of the
    converter (`parity_text`) that reads the program's relations, and the
    components it instantiates (`FORMS`); `solver` where `text` is empty.
    Raises `ValueError` where the program with the text does not parse."""
    if not text:
        return solver
    program = "\n".join(line.text for line in eng.render(solver.program).lines)
    got = eng.parse(f"{program}\n{FORMS.read_text()}\n{text}", checkout.programs())
    if isinstance(got, ParseFailure):
        raise ValueError(f"the converter's Souffle text of {solver.stem} does not parse: {got}")
    return replace(solver, program=got)


def load_once(stem: str, solver_file: Path) -> Loaded | Undefined | RunFailure:
    """The solver of `stem` read from `solver_file`, with its name map and
    its cases; the cases' undefined outcome or failure where they give none.
    The program that `Loaded.solver` holds ends with the converter's Souffle
    text (`text_path`), where the converter wrote one, and that of
    `Loaded.determination` with its text of the determination run
    (`determination_text_path`)."""
    eng = engine()
    solver = load(stem, eng, solver_file)
    every = cases_of(solver, eng, LIMITS)
    if not isinstance(every, tuple):
        return every
    joined = with_text(eng, solver, _text_of(text_path(stem)))
    determination = with_text(eng, solver, _text_of(determination_text_path(stem)))
    return Loaded(eng, joined, name_map(stem), every, determination,
                  top_level(joined.program) - top_level(solver.program))


def _text_of(path: Path) -> str:
    """What the Souffle text at `path` holds; nothing where the converter wrote none."""
    return path.read_text() if path.is_file() else ""


def top_level(program: Program) -> frozenset[str]:
    """The name of each relation and instance that `program` declares at the top level."""
    return frozenset(d.name for d in (*program.relations, *program.instances) if not d.scope.components)


def relations(stem: str, case: str, pair: str
              ) -> Mapping[str, Rows] | Undefined | RunFailure:
    """The rows of each relation of the program of the case of `stem` whose
    arclog name is `case` (`parity.case_name`), run on the input of the
    pair whose name is `pair` (`arc.task.pair_name`), each keyed by its arclog name
    (`parity.relation_names`), the rows of a run of the program of
    `taken_program`; the case's undefined outcome or the run's
    failure where it gives no rows. Raises `NoSuchCase` and `NoSuchPair`."""
    loaded = load_once(stem, solver_path(stem))
    if not isinstance(loaded, Loaded):
        return loaded
    chosen = next((c for c in loaded.every if case_name(loaded.solver, c, loaded.names) == case), None)
    if chosen is None:
        raise NoSuchCase(case)
    ex = loaded.pair(pair)
    got = loaded.run(loaded.taking(chosen), chosen, ex, every_relation(loaded.eng, loaded.solver.program))
    if not isinstance(got, Mapping):
        return got
    return {name: rows for r, rows in got.items() for name in relation_names(loaded.names, r)}


def leaves_at(value: Value, path: Sequence[int]) -> list[int | float | str] | None:
    """The leaves (`leaves`) of the part of `value` at `path`, the index of a
    field of a record or an ADT value at each step; None where `value` has no part there, as where
    the type of the column is a type argument that the run binds to a type
    with fewer fields than the converter's leaf."""
    for index in path:
        match value:
            case RecordValue(fields=fields) | AdtValue(args=fields) if index < len(fields):
                value = fields[index]
            case _:
                return None
    return leaves(value)


class LeftOut(StrEnum):
    """The verdict of a relation that the row parity check does not
    compare."""

    SKIP = "skip"
    UNCOMPARED = "uncompared"


class Reason(StrEnum):
    """Why the row parity check does not compare a relation of the run, or
    an arclog relation, and the verdict that gives."""

    INPUT = "an input of the Souffle program"
    LIB = "a lib relation that no clause of the solver writes and no arclog relation stands for"
    FACTS = "its rows are facts alone and no arclog relation stands for it"
    INLINE = "each Souffle relation it stands for is inline, with no rows of its own"
    TEXT = "a relation of the converter's Souffle text that no arclog relation stands for"
    NO_ENTRY = "no entry in the column map"
    NO_RELATION = "no Souffle relation of the run stands for it"

    @property
    def verdict(self) -> LeftOut:
        """`skip` where the relation holds no row the solver derives,
        else `uncompared`."""
        return LeftOut.UNCOMPARED if self in (Reason.NO_ENTRY, Reason.NO_RELATION) else LeftOut.SKIP


@dataclass(frozen=True)
class Untranslated:
    """The converter's reason for no check relation of a relation it folds
    (`NameMap.untranslated`), which stands in place of `Reason.NO_ENTRY`."""

    value: str

    @property
    def verdict(self) -> LeftOut:
        return LeftOut.UNCOMPARED


def lib_inputs(program: Program) -> frozenset[tuple[str | None, int]]:
    """The file and line of each `// @input` comment that follows a
    declaration on its line, in the lib the program includes."""
    return frozenset((c.file, c.line) for c in program.comments if not c.own_line and "@input" in c.text)


def cases_to_run(loaded: Loaded) -> list[Case]:
    """The concept case, then, in the order of `loaded.every`, each case that
    takes a `Choice` constructor (an ALT) that no case before it takes.
    Raises `NoSuchCase` where the solver has no concept case."""
    concept = next((c for c in loaded.every if case_name(loaded.solver, c, loaded.names) == "concept"), None)
    if concept is None:
        raise NoSuchCase("concept")
    choice = loaded.solver.choice
    every = frozenset() if choice is None else frozenset(c.name for p in choice.points for c in p.constructors)

    def takes(case: Case) -> frozenset[str]:
        return every - untaken(loaded.solver, case.base)

    covered = takes(concept)
    out = [concept]
    for case in loaded.every:
        if case is not concept and takes(case) - covered:
            out.append(case)
            covered |= takes(case)
    return out


@dataclass(frozen=True)
class Pairing:
    """A relation of the Souffle run, the arclog relation that holds its
    rows, and the key of the relation's entry in the column map of that
    arclog relation (`SouffleRelation.column_key`)."""

    relation: RelationName
    name: str
    key: str


def classify(loaded: Loaded, columns: Mapping[str, Mapping[str, Any]], read: Sequence[str]
             ) -> tuple[list[Pairing], list[dict[str, str]]]:
    """The relations of the run that the check compares, each with each arclog
    name that holds its rows, and a `{"name", "verdict", "reason"}` for each
    relation it does not compare, by the rules in the module docstring: one for
    each relation of the run, then one for each arclog relation in `read`, the
    names the converted program reads (`NameMap.read`), that no relation of
    the run maps to. An arclog relation that some relation of the run is
    compared with has no such line."""
    program = loaded.eng.expand(loaded.solver.program)
    graph = Graph(program, loaded.eng)
    marks = lib_inputs(program)
    written = {graph.place(at, u.head.relation) for u in program.units if u.span is None or own(u.span)
               for at in graph.paths_of(u)}
    mapped: list[Pairing] = []
    left: dict[str, Reason | Untranslated] = {}
    run = every_relation(loaded.eng, loaded.solver.program)
    for r in run:
        found = graph.decl((), r)
        if found is None:
            raise ValueError(f"`{r.text}` of the run has no declaration")
        span = found[0].span
        for name in relation_names(loaded.names, r):
            stands = name.startswith("&")
            if not r.instances and (span.file, span.first) in marks:
                left[name] = Reason.INPUT
            elif (r.instances[0] if r.instances else r.name) in loaded.added and not stands:
                left[name] = Reason.TEXT
            elif not own(span) and r not in written and not stands:
                left[name] = Reason.LIB
            elif all(u.body is None for u, _ in graph.feeding(r)) and not stands:
                left[name] = Reason.FACTS
            elif r.text in columns.get(name, {}):
                mapped.append(Pairing(r, name, r.text))
            else:
                left[name] = Untranslated(loaded.names.untranslated[r.text]) \
                    if loaded.names is not None and r.text in loaded.names.untranslated else Reason.NO_ENTRY
    stood = {name for r in run for name in relation_names(loaded.names, r)}
    left.update((n, Reason.INLINE if inline(loaded.names, graph, n) else Reason.NO_RELATION)
                for n in read if n not in stood)
    for at in mapped:
        left.pop(at.name, None)
    return mapped, [{"name": n, "verdict": why.verdict.value, "reason": why.value} for n, why in left.items()]


def inline(names: NameMap | None, graph: Graph, name: str) -> bool:
    """Whether the arclog relation `name` stands for some Souffle relation
    of the name map `names`, and each is declared `inline`."""
    if names is None:
        return False
    found = [graph.decl((), relation_at(s.path)) for s in names.relations.get(name, ()) if s.path is not None]
    return bool(found) and all(f is not None and Qualifier.INLINE in f[0].qualifiers for f in found)


def case_rows(stem: str, solver_file: Path, path: Path) -> Undefined | RunFailure | None:
    """Write to the file `path` the rows of the cases `cases_to_run` give for
    the solver of `stem`, read from `solver_file`, each on every train and
    test pair, for each relation `classify` compares, each row projected onto the columns the
    column map (`columns_path`) gives it, which leave out each Example leaf:
    for each, the leaves of the value at its `leaf` in its Souffle column. A
    relation's rows are a set. The form: `{"orientation_constants": {...},
    "check_relations": [<arclog name>, ...], "cases": [{"case": <arclog name>, "pairs": [{"pair": "train 0",
    "relations": [{"name": "&x", "columns": [[label, field], ...],
    "idents": [kind, ...], "unread": [[label, field], ...],
    "unresolved": [[label, field, reason], ...], "rows": [[[leaves of column 1], ...], ...],
    "by_open": {...}, "fault": text}]}]}], "not_compared": [{"name",
    "verdict", "reason"}]}`, with the keys in that order, which `arclog-cli row-parity`
    reads one relation at a time; a case whose run gives no rows has `"failure":
    text` in place of `pairs`. A case's entry has as well `"determination":
    {"pairs": [{"pair": "train 0" or "task", "relations": [...]}]}`, where the
    check compares a relation of `Determine`, with `"failure": text` in place of
    `pairs` where its run gives no rows; the entries of its
    relations are a case's. It holds the rows of the run of the case's
    program of `Loaded.determination` from which each clause of a branch that
    neither the case nor the concept case takes is dropped (`taken_program`),
    so that the check compares a relation at the first case whose engine
    program has it, with that case's rows; a relation with an Example leaf in
    its column map has an entry for each train pair, with the rows of that example, and any other relation
    one under the pair `task`, with the rows of the run. A relation whose entry has no column to
    compare has an empty `columns`, and its rows are `[]` where it has a row.
    A column of
    `unread` is a mapped column whose leaf some row lacks, which every list
    of `columns` and `rows` leaves out; so is a column of `unresolved`, a
    leaf of type `Ident` that has no one source (`parity.idents`), with its
    reason; a leaf whose minted id has two member sets at the keys that
    agree with the row's, for that reason, is one on that pair alone. The
    kind of a column in `idents` is `"minted"`, where the leaf is an id a lib relation mints, and its leaf is the text of the set of
    the id's members (`parity.idents.Writer`); `"stored"`, where it is a
    number a clause writes; and `null` for any other leaf. `fault`, which a
    relation's entry holds only where it applies, is the text of a minted
    id that the minting relation's rows on the pair do not hold at the
    row's key. `by_open`, which an entry holds only where the Souffle
    relation has a column of type `OpenValue` that the column map gives no
    arclog column, is `{"picks": {<arclog name of an open parameter>:
    [[label, field], ...]}, "values": [{"rows": rows, "picks": {<name>:
    [[leaves of column 1], ...]}}]}`: for each distinct value of that column,
    the relation's rows under it (a list as `rows` is, the union of them all
    being `rows`) and, for each open parameter whose field of that value is
    not `nil`, the rows of the parameter's arclog relation that the value
    gives, over the columns that `picks` lists for it. The file holds that
    form as `json.dumps` writes it with its default separators, written
    (`write_json`) as each relation's entry (`relation_entry`) is made, so that
    the function holds at once the runs of one case (`case_entry`) and the entry
    of one relation, and no entry it has written. It gives None, or the concept
    case's undefined outcome or a run's failure where it gives no rows; where
    it gives one or raises, no file stays at `path`. Raises `NoSuchCase` where
    the solver has no concept case, and `FileNotFoundError` where the column
    map is missing."""
    path.unlink(missing_ok=True)
    loaded = load_once(stem, solver_file)
    if not isinstance(loaded, Loaded):
        return loaded
    chosen = cases_to_run(loaded)
    columns: dict[str, dict[str, Entry | dict[str, Any]]] = json.loads(columns_path(stem).read_text())
    concept_untaken = untaken(loaded.determination, chosen[0].base)
    concept_run = run_program(taking(loaded.determination, concept_untaken))
    determined = determined_relations(loaded, columns, concept_run)
    read = [] if loaded.names is None else loaded.names.read
    mapped, not_compared = classify(loaded, columns, [n for n in read if n not in {at.name for at in determined}])
    first = case_entry(loaded, chosen[0], columns, mapped)
    if not isinstance(first, Iterator):
        return first

    def cases() -> Iterator[dict[str, Any]]:
        for i, case in enumerate(chosen):
            got = first if i == 0 else case_entry(loaded, case, columns, mapped)
            entry: dict[str, Any] = {"case": case_name(loaded.solver, case, loaded.names)}
            if isinstance(got, Iterator):
                entry["pairs"] = got
            else:
                entry["failure"] = str(got)
            if determined:
                run = concept_run if i == 0 else run_program(
                    taking(loaded.determination, untaken(loaded.determination, case.base) & concept_untaken))
                entry["determination"] = determination_entry(loaded, run, columns, determined)
            yield entry

    try:
        with path.open("w") as handle:
            write_json(handle, {"orientation_constants": orientation_constants(loaded.solver.lib),
                                "check_relations": [] if loaded.names is None else list(loaded.names.checks),
                                "cases": cases(), "not_compared": not_compared})
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return None


def case_entry(loaded: Loaded, chosen: Case, columns: Mapping[str, Mapping[str, Any]],
               mapped: Sequence[Pairing]) -> Iterator[dict[str, Any]] | Undefined | RunFailure:
    """The case's undefined outcome or a run's failure, or, once each run of
    `chosen` gives rows, its `pairs` in `case_rows`' form as an iterator, which
    makes each relation's entry (`relation_entry`) when it is consumed and
    holds the case's runs until it ends. A relation of the run that
    several arclog relations hold has an entry for each. Each relation's
    columns are those of the writing the case takes (`column_entry`)."""
    taken = loaded.taking(chosen)
    projection = Projection.of(ident_sources(loaded.eng, taken.program), columns, mapped, constructors(chosen.base),
                               open_picks(loaded, columns))
    runs = []
    for p, ex in examples(loaded.solver.given_task):
        got = loaded.run(taken, chosen, ex, projection.asked)
        if not isinstance(got, Mapping):
            return got
        runs.append((p.text, got))
    unread = projection.unread([got for _, got in runs])

    def pairs() -> Iterator[dict[str, Any]]:
        for pair, got in runs:
            yield {"pair": pair, "relations": projection.entries([(at, got[at.relation]) for at in mapped], got, unread)}
    return pairs()


def determined_relations(loaded: Loaded, columns: Mapping[str, Mapping[str, Any]], run: RunProgram
                         ) -> list[Pairing]:
    """Each relation of `Determine` that the name map gives an arclog name
    and the column map an entry, with that name, by its path under the
    instance of `Determine` in the program of `run` (`run_program`), if the
    program outputs it."""
    if run.determine is None or loaded.names is None:
        return []
    declared = set(every_relation(loaded.eng, run.program))
    found = []
    for arc, souffle in loaded.names.relations.items():
        for source in souffle:
            if source.column_key in columns.get(arc, {}) and source.component == DETERMINE_SCOPE.components:
                *chain, name = source.relation.split(".")
                relation = relation_at(source.path) if source.path is not None \
                    else RelationName((run.determine.name, *chain), name)
                if relation in declared:
                    found.append(Pairing(relation, arc, source.column_key))
    return found


def determination_entry(loaded: Loaded, run: RunProgram, columns: Mapping[str, Mapping[str, Any]],
                        mapped: Sequence[Pairing]) -> dict[str, Any]:
    """The `determination` entry of a case in `case_rows`' form, its `pairs` an
    iterator that makes each relation's entry when it is consumed, for the relations
    `mapped`: the program of `run`, which `case_rows` gives the cut of the
    branches that neither the case nor the concept case takes
    (`taken_program`), over the task's examples, as
    `solver.determine.determine` runs it, once, each relation projected
    as in a case's `pairs`. A relation with an Example leaf in its column
    map has its rows of each train example under the pair `train <i>`, those
    of a test example left out, and any other relation all its rows under the
    pair `task`.
    `{"failure": text}` where the run fails."""
    task = loaded.solver.given_task
    projection = Projection.of(ident_sources(loaded.eng, run.program), columns, mapped, frozenset())
    got = loaded.eng.run(run.program, {INPUT: (), **example_inputs(task)}, projection.asked,
                         over_examples(LIMITS, task))
    if not isinstance(got, Tuples):
        return {"failure": str(got)}
    rows = output_rows(got, projection.asked)
    unread = projection.unread([rows])
    per_input = {p: leaf for p in mapped
                 if (leaf := _example_leaf(column_entry(columns[p.name][p.key], frozenset()))) is not None}
    alone = [p for p in mapped if p not in per_input]

    def pairs() -> Iterator[dict[str, Any]]:
        for i in range(len(task.train) if per_input else 0):
            yield {"pair": f"train {i}", "relations": projection.entries(
                [(p, _of_example(rows[p.relation], leaf, i)) for p, leaf in per_input.items()], rows, unread)}
        if alone:
            yield {"pair": "task", "relations": projection.entries([(p, rows[p.relation]) for p in alone], rows, unread)}
    return {"pairs": pairs()}


def _example_leaf(column_map: list[list[dict[str, Any]]]) -> tuple[int, tuple[int, ...]] | None:
    """The Souffle column and the path in it of the first Example leaf in
    `column_map`, the entry of a relation; None where it has none."""
    return next(((j, tuple(e["leaf"])) for j, column in enumerate(column_map) for e in column if e["example"]), None)


def _of_example(rows: Rows, at: tuple[int, tuple[int, ...]], example: int) -> Rows:
    """The rows of `rows` whose Example leaf at `at` is `example`."""
    column, path = at
    return tuple(row for row in rows if leaves_at(row[column], path) == [example])


def open_valued(graph: Graph, relation: RelationName, column: int) -> bool:
    """Whether column `column` of `relation` is of type `OpenValue`."""
    found = graph.decl((), relation)
    return found is not None and found[0].columns[column].type == TypeName((), OPEN_VALUE)


@dataclass(frozen=True)
class OpenPick:
    """An open parameter whose arclog relation `name` the converter maps, at
    field `field` of `OpenValue`: the parameter's stored `values` (rows of
    the columns outside its case part), the `places` among them of the
    columns the field's record names, and the leaves of its columns that the
    column map gives an arclog column, each as the arclog column's `label`
    and `field`, the column's place and the leaf's path in that column."""

    field: int
    name: str
    values: Rows
    places: tuple[int, ...]
    leaves: tuple[tuple[str, str | None, int, tuple[int, ...]], ...]

    def rows_of(self, field: Value) -> list[list[list[int | float | str]]]:
        """The rows of the parameter's arclog relation that `field`, the
        value of the field of `OpenValue`, gives: each stored row whose columns
        at the record's places are `field`, as the leaves at each leaf of the
        pick, each once, in order by their text; a row with a leaf its columns
        lack is left out."""
        rows = {}
        for stored in self.values:
            if RecordValue(tuple(stored[i] for i in self.places)) != field:
                continue
            got = [leaves_at(stored[c], path) for _, _, c, path in self.leaves]
            if None not in got:
                rows[json.dumps(got)] = got
        return [rows[key] for key in sorted(rows)]


def open_picks(loaded: Loaded, columns: Mapping[str, Mapping[str, Any]]) -> list[OpenPick]:
    """The `OpenPick` of each field of the solver's `OpenValue` whose
    parameter the name map maps to an arclog relation with a column map entry
    and whose rows the program stores. Raises ValueError where a field is off
    its form, which the lint reports (`checker.lint.form.open_value_fields`)."""
    picks = []
    for index, reading in enumerate(field_readings(loaded.solver)):
        if isinstance(reading, FieldOff):
            raise ValueError(f"the `{OPEN_VALUE}` field `{reading.field}` is off its form: {reading.fault.value}")
        parameter = reading.parameter
        if loaded.names is None or not isinstance(parameter.stored, tuple):
            continue
        found = next(((arc, s) for arc, ss in loaded.names.relations.items() for s in ss
                      if s.component == PARAMS_COMPONENT and s.relation == parameter.name), None)
        if found is None or found[1].column_key not in columns.get(found[0], {}):
            continue
        name, entry = found[0], column_entry(columns[found[0]][found[1].column_key], frozenset())
        pc = parameter_reading(loaded.solver, parameter.name)
        leaves = tuple((e["label"], e["field"], place, tuple(e["leaf"]))
                       for place, column in enumerate(pc.given) for e in entry[column]
                       if not e["example"])
        if leaves:
            picks.append(OpenPick(index, name, pc.values(parameter.stored), reading.places, leaves))
    return picks


def pick_rows(values: Sequence[Value], picks: Sequence[OpenPick]) -> dict[str, list[list[list[int | float | str]]]]:
    """For each of `picks` whose field some value of `values`, the values of
    `OpenValue` of a row, holds other than `nil`, the rows of the parameter's
    arclog relation that the field's value gives (`OpenPick.rows_of`); the
    first such value gives them."""
    out: dict[str, list[list[list[int | float | str]]]] = {}
    for value in values:
        if not isinstance(value, RecordValue):
            continue
        for pick in picks:
            field = value.fields[pick.field]
            if pick.name not in out and not isinstance(field, NilValue):
                if rows := pick.rows_of(field):
                    out[pick.name] = rows
    return out


@dataclass(frozen=True)
class MappedLeaf:
    """A leaf of a Souffle column that the column map gives an arclog column
    (`label`, and `field` where the column is a record's field): the Souffle
    column, the path of the leaf into its value, and the source of the leaf
    where it is an Ident (`parity.idents`)."""

    column: int
    label: str
    field: str | None
    path: tuple[int, ...]
    source: Source | None


@dataclass(frozen=True)
class Projection:
    """The pairings `mapped` of one program, each with its mapped leaves
    (`MappedLeaf`) and the columns of type `OpenValue` that it holds, for
    their rows to be written out as `relation_entry` does, with the open
    parameters `picks` that the open values of a relation name."""

    sources: IdentSources
    leaves_of: Mapping[Pairing, list[MappedLeaf]]
    opens: Mapping[Pairing, list[int]]
    picks: Sequence[OpenPick]

    @staticmethod
    def of(sources: IdentSources, columns: Mapping[str, Mapping[str, Any]],
           mapped: Sequence[Pairing], taken: Collection[str], picks: Sequence[OpenPick] = ()) -> "Projection":
        """The projection of `mapped` onto the columns of the writing that a
        case taking the `ALT` constructors `taken` reads (`column_entry`)."""
        entries = {at: column_entry(columns[at.name][at.key], taken) for at in mapped}
        leaves_of = {at: [MappedLeaf(j, e["label"], e["field"], tuple(e["leaf"]), sources.of(at.relation, j, tuple(e["leaf"])))
                          for j, column in enumerate(entry) for e in column if not e["example"]]
                     for at, entry in entries.items()}
        opens = {at: [j for j, column in enumerate(entry) if not any(not e["example"] for e in column)
                      and open_valued(sources.graph, at.relation, j)]
                 for at, entry in entries.items()}
        return Projection(sources, leaves_of, opens, picks)

    @property
    def asked(self) -> list[RelationName]:
        """The relations a run outputs for the entries: the mapped ones, and
        those that mint the ids of their leaves."""
        return list(dict.fromkeys([*(at.relation for at in self.leaves_of),
                                   *(m for ls in self.leaves_of.values() for leaf in ls
                                     if isinstance(leaf.source, Minted)
                                     for m in self.sources.minting(leaf.source))]))

    def unread(self, runs: Sequence[Mapping[RelationName, Rows]]) -> dict[Pairing, list[MappedLeaf]]:
        """The leaves of each pairing that some row of some run in `runs`
        lacks."""
        return {at: [leaf for leaf in ls if any(leaves_at(row[leaf.column], leaf.path) is None
                                                for got in runs for row in got[at.relation])]
                for at, ls in self.leaves_of.items()}

    def entries(self, held: Sequence[tuple[Pairing, Rows]], got: Mapping[RelationName, Rows],
                unread: Mapping[Pairing, list[MappedLeaf]]) -> Iterator[dict[str, Any]]:
        """The entry (`relation_entry`) of each pairing of `held`, from its
        rows, with the rows `got` of a run for the minted ids; each is made when
        it is consumed."""
        for at, rows in held:
            yield relation_entry(at.name, rows, self.leaves_of[at], unread[at], self.opens[at],
                                 self.picks, Writer(self.sources, got))


@dataclass(frozen=True, slots=True)
class JsonText:
    """A value in its JSON text, which `write_json` writes as it stands."""

    text: str


def write_json(handle: TextIO, value: Any) -> None:
    """Write `value` to `handle` as `json.dumps` writes it, with its default
    separators: a dict (its keys strings) and a list or other iterable piece by
    piece, an iterable consumed once, and a `JsonText` as it stands."""
    if isinstance(value, JsonText):
        handle.write(value.text)
    elif isinstance(value, Mapping):
        handle.write("{")
        for i, (key, item) in enumerate(value.items()):
            if not isinstance(key, str):
                raise TypeError(f"the key {key!r} is no string")
            handle.write(f"{', ' if i else ''}{json.dumps(key)}: ")
            write_json(handle, item)
        handle.write("}")
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        handle.write("[")
        for i, item in enumerate(value):
            if i:
                handle.write(", ")
            write_json(handle, item)
        handle.write("]")
    else:
        handle.write(json.dumps(value))


def relation_entry(name: str, rows: Rows, mapped: list[MappedLeaf], unread: list[MappedLeaf],
                   opens: list[int], picks: Sequence[OpenPick], writer: Writer) -> dict[str, Any]:
    """The entry of the relation `name` for one pair in `case_rows`' form,
    from its `rows` on the pair, its `mapped` leaves, those of them that are
    `unread`, the columns of type `OpenValue` that it holds (`opens`), the
    open `picks` of the solver, and the `writer` of the minted ids. The `rows`
    of the entry, and of each `by_open` value, are the sorted JSON texts
    (`JsonText`) of the distinct rows over the columns it keeps."""
    unresolved = {leaf: leaf.source.reason for leaf in mapped
                  if leaf not in unread and isinstance(leaf.source, Unresolved)}
    read = [leaf for leaf in mapped if leaf not in unread and leaf not in unresolved]
    table: list[tuple[str, tuple[Value, ...], list[list[int | float | str]]]] = []
    faults: list[tuple[int, str]] = []
    ambiguous: dict[int, str] = {}
    for row in rows:
        cell = []
        for i, leaf in enumerate(read):
            value = leaves_at(row[leaf.column], leaf.path)
            assert value is not None
            if isinstance(leaf.source, Minted):
                try:
                    value = [writer.text(leaf.source, value[0], row)]
                except NoMembers as no:
                    faults.append((i, str(no)))
                except Ambiguous as other:
                    ambiguous[i] = min(ambiguous.get(i, str(other)), str(other))
            cell.append(value)
        table.append((json.dumps([leaf for j in opens for leaf in leaves(row[j])]),
                      tuple(row[j] for j in opens), cell))
    kept = [i for i in range(len(read)) if i not in ambiguous]
    unresolved.update((read[i], reason) for i, reason in ambiguous.items())
    fault = [text for i, text in faults if i in kept]

    def distinct(cells: list[list[list[int | float | str]]]) -> list[JsonText]:
        return [JsonText(cell) for cell in sorted({json.dumps([c[i] for i in kept]) for c in cells})]

    entry: dict[str, Any] = {
        "name": name, "columns": [[read[i].label, read[i].field] for i in kept],
        "idents": [kind_of(read[i].source) for i in kept],
        "unread": [[leaf.label, leaf.field] for leaf in unread],
        "unresolved": [[leaf.label, leaf.field, unresolved[leaf]] for leaf in mapped if leaf in unresolved],
        "rows": distinct([cell for _, _, cell in table])}
    if opens:
        held = {key: values for key, values, _ in table}
        values = [{"rows": distinct([cell for k, _, cell in table if k == key]),
                   "picks": pick_rows(held[key], picks)} for key in sorted(held)]
        given = {pick_name for value in values for pick_name in value["picks"]}
        entry["by_open"] = {"picks": {pick.name: [[label, field] for label, field, _, _ in pick.leaves]
                                      for pick in picks if pick.name in given},
                            "values": values}
    if fault:
        entry["fault"] = min(fault)
    return entry


def orientation_constants(lib: Lib) -> dict[str, Any]:
    """The number of each orientation constant of `lib`."""
    members = {name for names in lib.orientation_types.values() for name in names}
    return {name: value for name, value in lib.constants.items() if name in members}


def constructors(value: Value | None) -> set[str]:
    """The constructor of each `AdtValue` at any depth of `value`."""
    match value:
        case AdtValue(constructor=name, args=fields):
            return {name}.union(*(constructors(f) for f in fields))
        case RecordValue(fields=fields):
            return set().union(*(constructors(f) for f in fields))
        case _:
            return set()


def untaken(solver: Solver, base: Base | None) -> frozenset[str]:
    """The constructors of the branches the case of `base` does not take: those of
    each choice point of `solver` other than the constructors `base` holds,
    and, at a point none of whose constructors `base` holds, other than the
    point's concept branch (`concept_branch`). None are, for a solver with one
    case."""
    choice = solver.choice
    if choice is None:
        return frozenset()
    held = constructors(base)
    taken = held.union(concept_branch(p).name for p in choice.points
                       if not held.intersection(c.name for c in p.constructors))
    return frozenset(c.name for p in choice.points for c in p.constructors) - taken


def taken_program(solver: Solver, dropped: frozenset[str]) -> Program:
    """The program of `solver` with each clause of a branch whose constructor
    is in `dropped` dropped: the constructors a case does not take
    (`untaken`), or, for a determination run, those that neither the case nor
    the concept case takes. A clause is of such a branch where one of its
    constructors stands in its head, or in a positive atom or a `=`
    comparison of its body, outside a negation and an aggregate: a disjunct of the
    body that holds one is dropped from its disjunction, and the clause with
    it where no disjunct is left. A fact is dropped by its head alone."""
    if not dropped:
        return solver.program
    units = tuple(u for u in (_taken_unit(u, dropped) for u in solver.program.units) if u is not None)
    return replace(solver.program, units=units)


def _taken_unit(unit: Unit, names: frozenset[str]) -> Unit | None:
    """`unit` without the disjuncts of branches in `names`; None where the
    unit is of such a branch."""
    if any(_holds(t, names) for t in unit.head.args):
        return None
    if unit.body is None:
        return unit
    body = _taken_body(unit.body, names)
    return None if body is None else replace(unit, body=body)


def _taken_body(body: tuple[BodyLiteral, ...], names: frozenset[str]
                ) -> tuple[BodyLiteral, ...] | None:
    """`body` without the disjuncts of branches in `names`; None where a
    literal is of such a branch, or a disjunction has no disjunct left."""
    out: list[BodyLiteral] = []
    for lit in body:
        if isinstance(lit, AtomLiteral) and not lit.negated and any(_holds(t, names) for t in lit.atom.args):
            return None
        if isinstance(lit, Comparison) and lit.op == ComparisonOperator.EQ \
                and any(_holds(t, names) for t in (lit.lhs, lit.rhs)):
            return None
        if isinstance(lit, Disjunction):
            kept = [b for branch in lit.branches if (b := _taken_body(branch, names)) is not None]
            if not kept:
                return None
            if len(kept) == 1:
                out.extend(kept[0])
            else:
                out.append(replace(lit, branches=tuple(kept)))
        else:
            out.append(lit)
    return tuple(out)


def _holds(term: Term, names: frozenset[str]) -> bool:
    """Whether a constructor named in `names` stands in `term`, outside an
    aggregate."""
    return (isinstance(term, ConstructorTerm) and term.name in names) \
        or any(_holds(t, names) for t in subterms(term))


def rerun_json(stem: str, got: Mapping[str, Rows]) -> str:
    """The JSON object `rerun --json` prints for the rows `got` of a case
    of `stem`."""
    lib = load(stem, engine(), solver_path(stem)).lib
    return json.dumps({
        "relations": [[name, [[leaf for value in row for leaf in leaves(value)] for row in rows]]
                      for name, rows in got.items()],
        "orientation_constants": orientation_constants(lib),
    })


def code_digest() -> str:
    """The sha256 of the files of this package, which `cli.common.stamp`
    leaves out."""
    h = hashlib.sha256()
    hash_files(h, ((path.name, path) for path in sorted(Path(__file__).parent.glob("*.py"))))
    return h.hexdigest()


def kept_path(stem: str, case: str, pair: str) -> Path:
    """Where the kept JSON of the rerun of `case` of `stem` on `pair`
    stands: a file per solver, case and pair under `reruns/` of
    `snapshot.parity_dir`."""
    digest = hashlib.sha256(f"{case}\0{pair}".encode()).hexdigest()[:16]
    return snapshot.parity_dir() / "reruns" / stem / f"{digest}.json"


def kept_json(stem: str, case: str, pair: str) -> str | Undefined | RunFailure:
    """The JSON `rerun --json` prints for the rerun of `case` of `stem` on
    `pair`: the kept JSON of a rerun that gave rows, while the key it was
    made under is the current one; otherwise the JSON of a rerun now, kept
    where it gives rows, or the case's undefined outcome or the run's
    failure, which nothing keeps. The key is `snapshot.record_key`, the
    case, the pair and the digest of this package's files. Raises
    `NoSuchCase` and `NoSuchPair`."""
    key: dict[str, Any] = {**snapshot.record_key(stem), "case": case, "pair": pair,
                           "parity": code_digest()}

    def decode(data: bytes) -> str | None:
        try:
            held = json.loads(data)
        except ValueError:
            return None
        return held["output"] if held.get("key") == key else None

    def make() -> tuple[str | Undefined | RunFailure, bool]:
        got = relations(stem, case, pair)
        if isinstance(got, Mapping):
            return rerun_json(stem, got), True
        return got, False

    def encode(output: str | Undefined | RunFailure) -> bytes:
        return json.dumps({"key": key, "output": output}).encode()

    return read_or_make(kept_path(stem, case, pair), decode, encode, make)
