"""The arclog names of a solver's Souffle relations and cases, which the
stored Souffle outcomes are keyed by (`parity.snapshot`) and a rerun prints
by (`parity.rerun`): the name map `work/arclog/convert.py` writes for each
solver it converts, under `work/arclog/names/`."""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from engine import Engine, RelationName, checkout
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


@dataclass(frozen=True)
class NameMap:
    """One solver's name map: each arclog relation name with each Souffle
    relation it was written from, and each arclog `ALT` name with its
    Souffle `Choice` constructor."""

    relations: Mapping[str, tuple[SouffleRelation, ...]]
    constructors: Mapping[str, str]

    def arclog_at(self, path: str) -> str | None:
        """The arclog name of the relation at `path` from the top level of
        the Souffle program; None where the map gives it none."""
        return next((a for a, ss in self.relations.items()
                     if any(s.path == path for s in ss)), None)

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
    """`work/arclog/names/` of the main worktree."""
    return checkout.work() / "arclog" / "names"


def names_path(stem: str) -> Path:
    """Where the converter writes the name map of the solver `stem`."""
    return names_dir() / f"{stem}.json"


def name_map(stem: str) -> NameMap | None:
    """The name map of the solver `stem`; None where the converter wrote
    none, a solver it did not convert."""
    path = names_path(stem)
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    return NameMap(
        {a: tuple(SouffleRelation(tuple(s["component"]), s["relation"], s["path"]) for s in ss)
         for a, ss in data["relations"].items()},
        dict(data["constructors"]))


def marked(souffle: str) -> str:
    """A Souffle name that no arclog name maps to, under `SOUFFLE_MARK`."""
    return SOUFFLE_MARK + souffle


def relation_name(names: NameMap | None, relation: RelationName) -> str:
    """The arclog name of the Souffle relation `relation`, read from the
    top level, else its Souffle name under `SOUFFLE_MARK`."""
    return _arclog_or_marked(names, lambda n: n.arclog_at(relation.text), relation.text)


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
