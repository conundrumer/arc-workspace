"""One Souffle case run again on one pair with every relation of its
program written out, each by its arclog name, so that a mismatch report can
give the first relation whose rows differ; the JSON form of that rerun; and
the kept JSON of a rerun that gave rows, which stands while each input of
the rerun is unchanged (`kept_json`)."""

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cli.common import LIMITS, engine, solver_path
from engine import (AdtValue, Engine, NilValue, Program, RecordValue, RelationName, Rows,
                    RunFailure, Scope)
from engine.memo import hash_files, read_or_make
from engine.program import Qualifier, Value, as_grid
from parity import case_name, name_map, relation_name, snapshot
from solver.cases import cases as cases_of
from solver.load import load
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


def relations(stem: str, case: str, pair: str
              ) -> Mapping[str, Rows] | Undefined | RunFailure:
    """The rows of each relation of the program of the case of `stem` whose
    arclog name is `case` (`parity.case_name`), run on the input of the
    pair whose name is `pair` (`arc.task.pair_name`), each keyed by its arclog name
    (`parity.relation_name`); the case's undefined outcome or the run's
    failure where it gives no rows. Raises `NoSuchCase` and `NoSuchPair`."""
    eng = engine()
    solver = load(stem, eng, solver_path(stem))
    names = name_map(stem)
    every = cases_of(solver, eng, LIMITS)
    if not isinstance(every, tuple):
        return every
    chosen = next((c for c in every if case_name(solver, c, names) == case), None)
    if chosen is None:
        raise NoSuchCase(case)
    ex = next((ex for p, ex in examples(solver.given_task) if p.text == pair), None)
    if ex is None:
        raise NoSuchPair(pair)
    rels = every_relation(eng, solver.program)
    got = relations_at(eng, solver, chosen, as_grid(ex.input), rels, Assignment(()), LIMITS)
    if not isinstance(got, Mapping):
        return got
    return {relation_name(names, r): rows for r, rows in got.items()}


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
    members = {name for names in lib.orientation_types.values() for name in names}
    return json.dumps({
        "relations": [[name, [[leaf for value in row for leaf in leaves(value)] for row in rows]]
                      for name, rows in got.items()],
        "orientation_constants": {name: value for name, value in lib.constants.items()
                                  if name in members},
    })


def _code_digest() -> str:
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
                           "parity": _code_digest()}

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
