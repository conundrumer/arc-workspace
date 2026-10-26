"""One Souffle case run again on one pair with every relation of its
program written out, each by its arclog name, so that a mismatch report can
give the first relation whose rows differ, on a program from which each
clause of a branch the case does not take is dropped (`taken_program`), so
that the rows are the case's own; the JSON form of that rerun; and
the kept JSON of a rerun that gave rows, which stands while each input of
the rerun is unchanged (`kept_json`); and the rows of the cases the row
parity check runs on each pair, projected onto the columns the converter
maps, with the relations the check leaves out (`case_rows`).

The check (`arclog_convert.row_parity`) runs the concept case and, for each
`Choice` constructor (an ALT) that no case run before takes, the first case
of `Loaded.every` that takes it (`cases_to_run`), so that each ALT's
relations are compared on a case that has them; `Loaded.every` holds no case
that an `exclude` form leaves out. Each relation of the program that a run
outputs (`every_relation`) is compared, or has a line of its own, by the
first of these that holds (`classify`):

- `skip`, "an input of the Souffle program": a top-level lib relation
  marked `// @input`.
- `skip`, "a lib relation that no clause of the solver writes and no arclog
  relation stands for": the lib declares it, at the top level or in a
  component of the lib, so it holds rows the lib derives; no clause of the
  solver heads it (it is no input port of an instance that the solver
  writes); and no `&` name of the name map stands for it.
- `skip`, "its rows are facts alone and no arclog relation stands for it":
  no clause with a body heads it.
- compared, where the column map has an entry for it; a relation whose entry
  holds no column to compare is compared as present or absent.
- `uncompared`, "no entry in the column map".

Each arclog relation of the name map (`relations` and `unmapped`) that no
relation of the run maps to (`relation_name`) is `uncompared`, "no Souffle
relation of the run stands for it". `arclog-cli row-parity` gives the rest
of the verdicts, and `uncompared` "no case's program has a relation of that
name" for a relation that no case it runs has. An `equal` line proves that
the relation's rows in each case that derives it, at the stored parameters,
are these rows over the columns the converter maps
(`engine/arclog-cli/src/row_parity.rs` gives the rest)."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from arc.task import Example
from cli.common import LIMITS, engine, solver_path
from engine import (AdtValue, Engine, Program, RecordValue, RelationName, Rows,
                    RunFailure, Scope, TypeName)
from engine.memo import hash_files, read_or_make
from engine.program import (AtomLiteral, BodyLiteral, Comparison, ComparisonOperator,
                            ConstructorTerm, Disjunction, Qualifier, Term, Unit, Value, as_grid,
                            own, subterms)
from parity import NameMap, case_name, columns_path, name_map, names_path, relation_name, snapshot
from parity.idents import Ambiguous, Minted, NoMembers, Source, Unresolved, Writer, ident_sources, kind_of, leaves
from solver.aggregate import Solver
from solver.cases import cases as cases_of
from solver.graph import Graph
from solver.load import load
from solver.model import Base, Case, Lib, concept_branch
from solver.outcome import Assignment
from solver.pair_runs import examples
from solver.solve import relations_at
from solver.undefined import Undefined
from solver.vocabulary import OPEN_VALUE


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

    def pair(self, pair: str) -> Example:
        """The example of the pair whose name is `pair`. Raises `NoSuchPair`."""
        ex = next((ex for p, ex in examples(self.solver.given_task) if p.text == pair), None)
        if ex is None:
            raise NoSuchPair(pair)
        return ex

    def taking(self, chosen: Case) -> Solver:
        """The solver with the program of `taken_program` for `chosen`, to
        run `chosen` on each pair (`run`); the program is built once, so that
        the caches keyed by it serve every pair."""
        return replace(self.solver, program=taken_program(self.solver, chosen.base))

    def run(self, taken: Solver, chosen: Case, ex: Example, rels: list[RelationName]
            ) -> Mapping[RelationName, Rows] | Undefined | RunFailure:
        """The rows of `rels` of the case `chosen` run on the input of `ex`
        on `taken`, which `taking(chosen)` gave, so that they are the case's
        own."""
        return relations_at(self.eng, taken, chosen, as_grid(ex.input), rels, Assignment(()), LIMITS)


def load_once(stem: str, solver_file: Path) -> Loaded | Undefined | RunFailure:
    """The solver of `stem` read from `solver_file`, with its name map and
    its cases; the cases' undefined outcome or failure where they give none."""
    eng = engine()
    solver = load(stem, eng, solver_file)
    every = cases_of(solver, eng, LIMITS)
    if not isinstance(every, tuple):
        return every
    return Loaded(eng, solver, name_map(stem), every)


def relations(stem: str, case: str, pair: str
              ) -> Mapping[str, Rows] | Undefined | RunFailure:
    """The rows of each relation of the program of the case of `stem` whose
    arclog name is `case` (`parity.case_name`), run on the input of the
    pair whose name is `pair` (`arc.task.pair_name`), each keyed by its arclog name
    (`parity.relation_name`), the rows of a run of the program of
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
    return {relation_name(loaded.names, r): rows for r, rows in got.items()}


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
    NO_ENTRY = "no entry in the column map"
    NO_RELATION = "no Souffle relation of the run stands for it"

    @property
    def verdict(self) -> LeftOut:
        """`skip` where the relation holds no row the solver derives,
        else `uncompared`."""
        return LeftOut.UNCOMPARED if self in (Reason.NO_ENTRY, Reason.NO_RELATION) else LeftOut.SKIP


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


def read_by_converted(stem: str) -> list[str]:
    """The name of each arclog relation the converted program reads, as the
    name map gives them (`relations` and `unmapped`); none where the
    converter wrote no name map."""
    path = names_path(stem)
    if not path.is_file():
        return []
    data = json.loads(path.read_text())
    return [*data["relations"], *data["unmapped"]]


def classify(loaded: Loaded, columns: Mapping[str, Any], read: Sequence[str]
             ) -> tuple[dict[RelationName, str], list[dict[str, str]]]:
    """The relations of the run that the check compares, each with its arclog
    name, and a `{"name", "verdict", "reason"}` for each relation it does not
    compare, by the rules in the module docstring: one for each relation of
    the run, then one for each arclog relation in `read`, the names the
    converted program reads (`read_by_converted`), that no relation of the
    run maps to."""
    program = loaded.eng.expand(loaded.solver.program)
    graph = Graph(program, loaded.eng)
    marks = lib_inputs(program)
    written = {graph.place(at, u.head.relation) for u in program.units if u.span is None or own(u.span)
               for at in graph.paths_of(u)}
    mapped: dict[RelationName, str] = {}
    left: dict[str, Reason] = {}
    run = every_relation(loaded.eng, loaded.solver.program)
    for r in run:
        name = relation_name(loaded.names, r)
        found = graph.decl((), r)
        if found is None:
            raise ValueError(f"`{r.text}` of the run has no declaration")
        span = found[0].span
        stands = name.startswith("&")
        if not r.instances and (span.file, span.first) in marks:
            left[name] = Reason.INPUT
        elif not own(span) and r not in written and not stands:
            left[name] = Reason.LIB
        elif all(u.body is None for u, _ in graph.feeding(r)) and not stands:
            left[name] = Reason.FACTS
        elif name in columns:
            mapped[r] = name
        else:
            left[name] = Reason.NO_ENTRY
    stood = {relation_name(loaded.names, r) for r in run}
    left.update((n, Reason.NO_RELATION) for n in read if n not in stood)
    return mapped, [{"name": n, "verdict": why.verdict.value, "reason": why.value} for n, why in left.items()]


def case_rows(stem: str, solver_file: Path) -> dict[str, Any] | Undefined | RunFailure:
    """The rows of the cases `cases_to_run` gives for the solver of `stem`,
    read from `solver_file`, each on every train and test pair, for each
    relation `classify` compares, each row projected onto the columns the
    column map (`columns_path`) gives it, which leave out each Example leaf:
    for each, the leaves of the value at its `leaf` in its Souffle column. A
    relation's rows are a set. The form: `{"orientation_constants": {...},
    "cases": [{"case": <arclog name>, "pairs": [{"pair": "train 0",
    "relations": [{"name": "&x", "columns": [[label, field], ...],
    "idents": [kind, ...], "unread": [[label, field], ...],
    "unresolved": [[label, field, reason], ...], "rows": [[[leaves of column 1], ...], ...],
    "by_open": [rows, ...], "fault": text}]}]}], "not_compared": [{"name",
    "verdict", "reason"}]}`; a case whose run gives no rows has `"failure":
    text` in place of `pairs`. A relation whose entry has no column to
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
    arclog column, holds the rows of each distinct value of that column
    (each a list as `rows` is), whose union is `rows`. The concept case's undefined outcome or a run's failure
    where it gives no rows. Raises `NoSuchCase` where the solver has no concept case,
    and `FileNotFoundError` where the column map is missing."""
    loaded = load_once(stem, solver_file)
    if not isinstance(loaded, Loaded):
        return loaded
    chosen = cases_to_run(loaded)
    columns: dict[str, list[list[dict[str, Any]]]] = json.loads(columns_path(stem).read_text())
    mapped, not_compared = classify(loaded, columns, read_by_converted(stem))
    entries = []
    for i, case in enumerate(chosen):
        name = case_name(loaded.solver, case, loaded.names)
        got = case_entry(loaded, case, columns, mapped)
        if isinstance(got, list):
            entries.append({"case": name, "pairs": got})
        elif i == 0:
            return got
        else:
            entries.append({"case": name, "failure": str(got)})
    return {"orientation_constants": orientation_constants(loaded.solver.lib), "cases": entries,
            "not_compared": not_compared}


def case_entry(loaded: Loaded, chosen: Case, columns: Mapping[str, list[list[dict[str, Any]]]],
               mapped: Mapping[RelationName, str]) -> list[dict[str, Any]] | Undefined | RunFailure:
    """The `pairs` of the entry of `chosen` in `case_rows`' form, or the
    case's undefined outcome or a run's failure."""
    taken = loaded.taking(chosen)
    sources = ident_sources(loaded.eng, taken.program)
    graph = sources.graph
    leaves_of = {r: [MappedLeaf(j, e["label"], e["field"], tuple(e["leaf"]), sources.of(r, j, tuple(e["leaf"])))
                     for j, column in enumerate(columns[name]) for e in column if not e["example"]]
                 for r, name in mapped.items()}
    opens = {r: [j for j, column in enumerate(columns[name]) if not any(not e["example"] for e in column)
                 and open_valued(graph, r, j)]
             for r, name in mapped.items()}
    asked = list(dict.fromkeys([*mapped, *(m for ls in leaves_of.values() for leaf in ls
                                           if isinstance(leaf.source, Minted) for m in sources.minting(leaf.source))]))
    runs = []
    for p, ex in examples(loaded.solver.given_task):
        got = loaded.run(taken, chosen, ex, asked)
        if not isinstance(got, Mapping):
            return got
        runs.append((p.text, got))
    unread = {r: [leaf for leaf in ls if any(leaves_at(row[leaf.column], leaf.path) is None
                                             for _, got in runs for row in got[r])]
              for r, ls in leaves_of.items()}
    return [{"pair": pair, "relations": [relation_entry(name, got[r], leaves_of[r], unread[r], opens[r],
                                                        Writer(sources, got))
                                         for r, name in mapped.items()]}
            for pair, got in runs]


def open_valued(graph: Graph, relation: RelationName, column: int) -> bool:
    """Whether column `column` of `relation` is of type `OpenValue`."""
    found = graph.decl((), relation)
    return found is not None and found[0].columns[column].type == TypeName((), OPEN_VALUE)


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


def relation_entry(name: str, rows: Rows, mapped: list[MappedLeaf], unread: list[MappedLeaf],
                   opens: list[int], writer: Writer) -> dict[str, Any]:
    """The entry of the relation `name` for one pair in `case_rows`' form,
    from its `rows` on the pair, its `mapped` leaves, those of them that are
    `unread`, the columns of type `OpenValue` that it holds (`opens`), and
    the `writer` of the minted ids."""
    unresolved = {leaf: leaf.source.reason for leaf in mapped
                  if leaf not in unread and isinstance(leaf.source, Unresolved)}
    read = [leaf for leaf in mapped if leaf not in unread and leaf not in unresolved]
    table: list[tuple[str, list[list[int | float | str]]]] = []
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
        table.append((json.dumps([leaf for j in opens for leaf in leaves(row[j])]), cell))
    kept = [i for i in range(len(read)) if i not in ambiguous]
    unresolved.update((read[i], reason) for i, reason in ambiguous.items())
    fault = [text for i, text in faults if i in kept]

    def distinct(cells: list[list[list[int | float | str]]]) -> list[Any]:
        return [json.loads(cell) for cell in sorted({json.dumps([c[i] for i in kept]) for c in cells})]

    entry: dict[str, Any] = {
        "name": name, "columns": [[read[i].label, read[i].field] for i in kept],
        "idents": [kind_of(read[i].source) for i in kept],
        "unread": [[leaf.label, leaf.field] for leaf in unread],
        "unresolved": [[leaf.label, leaf.field, unresolved[leaf]] for leaf in mapped if leaf in unresolved],
        "rows": distinct([cell for _, cell in table])}
    if opens:
        groups = sorted({value for value, _ in table})
        entry["by_open"] = [distinct([cell for value, cell in table if value == group]) for group in groups]
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


def taken_program(solver: Solver, base: Base | None) -> Program:
    """The program of `solver` with each clause of a branch the case of `base`
    does not take (`untaken`) dropped. A clause is of such a branch where one of
    its constructors stands in its head, or in a positive atom or a `=`
    comparison of its body, outside a negation and an aggregate: a disjunct of the
    body that holds one is dropped from its disjunction, and the clause with
    it where no disjunct is left. A fact is dropped by its head alone."""
    names = untaken(solver, base)
    if not names:
        return solver.program
    units = tuple(u for u in (_taken_unit(u, names) for u in solver.program.units) if u is not None)
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
