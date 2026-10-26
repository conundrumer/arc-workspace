"""The arclog names of a solver's Souffle relations and cases, which the
stored Souffle outcomes are keyed by (`parity.snapshot`) and a rerun prints
by (`parity.rerun`): the name map `arclog_convert.names` makes for each
solver `arclog_convert.convert` converts, under `names/` of `arclog_convert.out`."""

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import arclog_convert
from engine import Engine, RelationName
from solver import names as solver_names
from solver.aggregate import Solver
from solver.model import Branch, Case, DeriveBranch, StoreBranch, StoredAtDerive
from solver.annotations import VerdictWord
from solver.names import ctor_text

PARAMS_COMPONENT = ("Params",)
"""The component path the converter's name map gives a parameter under."""

SOUFFLE_MARK = "souffle:"
"""What leads a Souffle name that no arclog name maps to, where a name of
the map's side is asked for."""


@dataclass(frozen=True)
class SouffleRelation:
    """The Souffle relation an arclog name was written from: the solver
    component path it is declared under, its name there, and its name from
    the top level of the solver's program, None where no top-level instance
    reaches it."""

    component: tuple[str, ...]
    relation: str
    path: str | None

    @property
    def column_key(self) -> str:
        """The key of this relation's entry in the column map of its arclog
        name: its path, and for a relation of `Determine` with no path, its
        name there."""
        return self.relation if self.path is None else self.path


@dataclass(frozen=True)
class NameMap:
    """One solver's name map: each arclog relation name with each Souffle
    relation it was written from, each arclog `ALT` name with its Souffle
    `Choice` constructor, and the names of the arclog relations the
    converted program reads that no Souffle relation was written into."""

    relations: Mapping[str, tuple[SouffleRelation, ...]]
    constructors: Mapping[str, str]
    unmapped: tuple[str, ...]

    @staticmethod
    def of(data: Mapping) -> "NameMap":
        """The name map that `data`, the JSON the converter writes, holds."""
        return NameMap(
            {a: tuple(SouffleRelation(tuple(s["component"]), s["relation"], s["path"]) for s in ss)
             for a, ss in data["relations"].items()},
            dict(data["constructors"]), tuple(data["unmapped"]))

    @property
    def read(self) -> list[str]:
        """The name of each arclog relation with `&` that the converted
        program reads or the map gives a Souffle relation of an instance
        (`relations` and `unmapped`)."""
        return [name for name in (*self.relations, *self.unmapped) if name.startswith("&")]

    def arclog_names_at(self, path: str) -> list[str]:
        """The arclog name of each relation that holds the rows of the
        relation at `path` from the top level of the Souffle program."""
        return [a for a, ss in self.relations.items() if any(s.path == path for s in ss)]

    def arclog_at(self, path: str) -> str | None:
        """The first of `arclog_names_at`; None where the map gives it none."""
        return next(iter(self.arclog_names_at(path)), None)

    def arclog_of(self, component: tuple[str, ...], relation: str) -> str | None:
        """The arclog name of `relation` declared under `component`; None
        where the map gives it none."""
        return next((a for a, ss in self.relations.items()
                     if any(s.component == component and s.relation == relation for s in ss)), None)

    def arclog_constructor(self, ctor: str) -> str | None:
        """The arclog `ALT` name of the Souffle constructor `ctor`; None
        where the map gives it none."""
        return next((a for a, c in self.constructors.items() if c == ctor), None)


def names_dir() -> Path:
    """`names/` of `arclog_convert.out`: `work/arclog/` of the main worktree,
    or the directory `ARCLOG_OUT` names."""
    return arclog_convert.out() / "names"


def columns_path(stem: str) -> Path:
    """Where the converter writes the column map of the solver `stem`, beside
    `names/`: for each arclog relation of the name map, for each of its
    Souffle relations that has a path, one entry per column of the Souffle
    relation, in its order: the arclog column at which each kept leaf of that
    Souffle column is read, empty where no arclog column holds a leaf of it
    (`arclog_convert.names.column_map`)."""
    return names_dir().parent / "columns" / f"{stem}.json"


def names_path(stem: str) -> Path:
    """Where the converter writes the name map of the solver `stem`."""
    return names_dir() / f"{stem}.json"


def name_map(stem: str) -> NameMap | None:
    """The name map of the solver `stem`; None where the converter wrote
    none, a solver it did not convert."""
    path = names_path(stem)
    if not path.is_file():
        return None
    return NameMap.of(json.loads(path.read_text()))


def marked(souffle: str) -> str:
    """A Souffle name that no arclog name maps to, under `SOUFFLE_MARK`."""
    return SOUFFLE_MARK + souffle


def relation_names(names: NameMap | None, relation: RelationName) -> list[str]:
    """The arclog name of each relation that holds the rows of the Souffle
    relation `relation`, read from the top level; its Souffle name under
    `SOUFFLE_MARK` where the map gives none."""
    got = [] if names is None else names.arclog_names_at(relation.text)
    return got or [marked(relation.text)]


def case_name(solver: Solver, case: Case, names: NameMap | None) -> str:
    """The arclog name of `case`: the name `solver.names.name` gives the
    case, with each constructor by its `ALT` name and each parameter or
    relation of a `@derive` or `@store` branch by its arclog name; a part
    the map gives no name, by its Souffle text under `SOUFFLE_MARK`."""
    def ctor(engine: Engine, c: str) -> str:
        return _arclog_or_marked(names, lambda n: n.arclog_constructor(c), ctor_text(engine, c))

    def branch(b: Branch) -> str:
        match b:
            case DeriveBranch(parameter=p, proposer=q):
                return f"{_named(names, p)}={q}"
            case StoreBranch(relation=r, spelled=spelled):
                return f"{_arclog_or_marked(names, lambda n: n.arclog_at(r.text), spelled)}={VerdictWord.STORED}"
            case StoredAtDerive(parameter=p):
                return f"{_named(names, p)}={VerdictWord.STORED}"

    return solver_names.name(solver, case, ctor=ctor, branch=branch)


def _named(names: NameMap | None, parameter: str) -> str:
    """The arclog name of the parameter `parameter`, else its Souffle name
    under `SOUFFLE_MARK`."""
    return _arclog_or_marked(names, lambda n: n.arclog_of(PARAMS_COMPONENT, parameter), parameter)


def _arclog_or_marked(names: NameMap | None, arclog: Callable[[NameMap], str | None], souffle: str) -> str:
    """The name `arclog` gives in `names`, else the Souffle name `souffle`
    under `SOUFFLE_MARK`."""
    got = None if names is None else arclog(names)
    return marked(souffle) if got is None else got


def case_names_digest(data: Mapping | None) -> str | None:
    """The sha256 of what `case_name` can read in the name map `data` (the
    JSON the converter writes; None where it wrote none): every constructor,
    the arclog name of each parameter, and, where the solver has a `@store`
    line (`stores` of the map), the arclog name at each path. A change to
    any other part of the map leaves it as it was."""
    if data is None:
        return None
    names = NameMap.of(data)
    sources = [s for ss in names.relations.values() for s in ss]
    stores = data.get("stores")   # a map of the earlier form has none: its records are stale
    read = {"stores": stores, "constructors": dict(names.constructors),
            "parameters": {s.relation: names.arclog_of(PARAMS_COMPONENT, s.relation)
                           for s in sources if s.component == PARAMS_COMPONENT},
            "stored": {s.path: names.arclog_at(s.path)
                       for s in sources if stores and s.path is not None}}
    return hashlib.sha256(json.dumps(read, sort_keys=True).encode()).hexdigest()
