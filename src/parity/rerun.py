"""One Souffle case run again on one pair with every relation of its
program written out, each by its arclog name, so that a mismatch report can
give the first relation whose rows differ; the JSON form of that rerun; and
the kept JSON of a rerun that gave rows, which stands while each input of
the rerun is unchanged (`kept_json`); and the rows of the concept case on
each pair projected onto the columns the converter maps (`concept_rows`)."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arc.task import Example
from cli.common import LIMITS, engine, solver_path
from engine import (AdtValue, Engine, NilValue, Program, RecordValue, RelationName, Rows,
                    RunFailure, Scope)
from engine.memo import hash_files, read_or_make
from engine.program import Qualifier, Value, as_grid
from parity import NameMap, case_name, columns_path, name_map, relation_name, snapshot
from solver.aggregate import Solver
from solver.cases import cases as cases_of
from solver.load import load
from solver.model import Case, Lib
from solver.outcome import Assignment
from solver.pair_runs import examples
from solver.solve import relations_at
from solver.undefined import Undefined


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

    def run(self, chosen: Case, ex: Example, rels: list[RelationName]
            ) -> Mapping[RelationName, Rows] | Undefined | RunFailure:
        """The rows of `rels` of the case `chosen` run on the input of `ex`,
        with the rows that `case_rows` cuts left out."""
        got = relations_at(self.eng, self.solver, chosen, as_grid(ex.input), rels, Assignment(()), LIMITS)
        if not isinstance(got, Mapping):
            return got
        foreign = {c for case in self.every for c in constructors(case.base)} - constructors(chosen.base)
        return {r: case_rows(rows, foreign) for r, rows in got.items()}


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
    (`parity.relation_name`), with the rows that `case_rows` cuts left out;
    the case's undefined outcome or the run's
    failure where it gives no rows. Raises `NoSuchCase` and `NoSuchPair`."""
    loaded = load_once(stem, solver_path(stem))
    if not isinstance(loaded, Loaded):
        return loaded
    chosen = next((c for c in loaded.every if case_name(loaded.solver, c, loaded.names) == case), None)
    if chosen is None:
        raise NoSuchCase(case)
    ex = loaded.pair(pair)
    got = loaded.run(chosen, ex, every_relation(loaded.eng, loaded.solver.program))
    if not isinstance(got, Mapping):
        return got
    return {relation_name(loaded.names, r): rows for r, rows in got.items()}


def leaves_at(value: Value, path: list[int]) -> list[int | float | str] | None:
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


def concept_rows(stem: str, solver_file: Path) -> dict[str, Any] | Undefined | RunFailure:
    """The rows of the concept case of the solver of `stem`, read from
    `solver_file`, on each train and test pair, for each relation the
    column map (`columns_path`) gives a column to compare, each row
    projected onto those columns, which leave out each Example leaf: for each, the leaves of the value at its
    `leaf` in its Souffle column. A relation's rows are a set. The form:
    `{"orientation_constants": {...}, "pairs": [{"pair": "train 0",
    "relations": [{"name": "&x", "columns": [[label, field], ...],
    "unread": [[label, field], ...], "rows": [[[leaves of column 1], ...], ...]}]}], "skipped": [{"name",
    "reason"}]}`. A column of `unread` is a mapped column whose leaf some row
    lacks, which every list of `columns` and `rows` leaves out. The case's undefined outcome or a run's failure where one
    gives no rows. Raises `NoSuchCase` where the solver has no concept case,
    and `FileNotFoundError` where the column map is missing."""
    loaded = load_once(stem, solver_file)
    if not isinstance(loaded, Loaded):
        return loaded
    chosen = next((c for c in loaded.every if case_name(loaded.solver, c, loaded.names) == "concept"), None)
    if chosen is None:
        raise NoSuchCase("concept")
    columns: dict[str, list[list[dict[str, Any]]]] = json.loads(columns_path(stem).read_text())
    mapped: dict[RelationName, str] = {}
    skipped: list[dict[str, str]] = []
    for r in every_relation(loaded.eng, loaded.solver.program):
        name = relation_name(loaded.names, r)
        if name not in columns:
            skipped.append({"name": name, "reason": "no entry in the column map"})
        elif not any(not e["example"] for column in columns[name] for e in column):
            skipped.append({"name": name, "reason": "no column to compare: every leaf is a case, a drop or an Example leaf"})
        else:
            mapped[r] = name
    runs = []
    for p, ex in examples(loaded.solver.given_task):
        got = loaded.run(chosen, ex, list(mapped))
        if not isinstance(got, Mapping):
            return got
        runs.append((p.text, got))
    entries = {name: [(j, e) for j, column in enumerate(columns[name]) for e in column if not e["example"]]
               for name in mapped.values()}
    unread = {name: [(j, e) for j, e in es if any(leaves_at(row[j], e["leaf"]) is None
                                                  for _, got in runs for row in got[r])]
              for r, name in mapped.items() for es in [entries[name]]}
    pairs = []
    for pair, got in runs:
        out = []
        for r, name in mapped.items():
            read = [(j, e) for j, e in entries[name] if (j, e) not in unread[name]]
            rows = {json.dumps([leaves_at(row[j], e["leaf"]) for j, e in read]) for row in got[r]}
            out.append({"name": name, "columns": [[e["label"], e["field"]] for _, e in read],
                        "unread": [[e["label"], e["field"]] for _, e in unread[name]],
                        "rows": [json.loads(row) for row in sorted(rows)]})
        pairs.append({"pair": pair, "relations": out})
    return {"orientation_constants": orientation_constants(loaded.solver.lib), "pairs": pairs,
            "skipped": skipped}


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


def case_rows(rows: Rows, foreign: set[str]) -> Rows:
    """The rows of one relation that hold, at no depth of a record or ADT
    value, an `AdtValue` whose constructor is in `foreign`, the
    constructors that some case's base holds and the chosen case's base
    does not. Souffle's program derives the rows of every branch of a
    `Choice` for each relation, and a row of another branch is no row of the
    case."""
    return tuple(row for row in rows if not any(constructors(v) & foreign for v in row))


def leaves(value: Value) -> list[int | float | str]:
    """The leaves of `value`, as `rerun --json` writes a row's values."""
    match value:
        case RecordValue(fields=fields) | AdtValue(args=fields):
            return [leaf for field in fields for leaf in leaves(field)]
        case NilValue():
            return []
        case _:
            return [value]


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
