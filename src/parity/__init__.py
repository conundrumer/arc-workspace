"""The arclog names of a solver's Souffle relations and cases, which the
stored Souffle outcomes are keyed by (`parity.snapshot`) and a rerun prints
by (`parity.rerun`): the name map `work/arclog/convert.py` writes for each
solver it converts, under `work/arclog/names/`."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from engine import RelationName, checkout
from solver.aggregate import Solver
from solver.model import (
    Case,
    DeriveBranch,
    StoreBranch,
    StoredAtDerive,
    constructors_taken,
    is_concept_branch,
)
from solver.annotations import VerdictWord
from solver.names import SEPARATOR, ctor_text

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
    """One solver's name map: each arclog relation name with its Souffle
    relation, and each arclog `ALT` name with its Souffle `Choice`
    constructor."""

    relations: Mapping[str, SouffleRelation]
    constructors: Mapping[str, str]

    def arclog_at(self, path: str) -> str | None:
        """The arclog name of the relation at `path` from the top level of
        the Souffle program; None where the map gives it none."""
        return next((a for a, s in self.relations.items() if s.path == path), None)

    def arclog_of(self, component: tuple[str, ...], relation: str) -> str | None:
        """The arclog name of `relation` declared under `component`; None
        where the map gives it none."""
        return next((a for a, s in self.relations.items()
                     if s.component == component and s.relation == relation), None)

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
        {a: SouffleRelation(tuple(s["component"]), s["relation"], s["path"])
         for a, s in data["relations"].items()},
        dict(data["constructors"]))


def marked(souffle: str) -> str:
    """A Souffle name that no arclog name maps to, under `SOUFFLE_MARK`."""
    return SOUFFLE_MARK + souffle


def relation_name(names: NameMap | None, relation: RelationName) -> str:
    """The arclog name of the Souffle relation `relation`, read from the
    top level, else its Souffle name under `SOUFFLE_MARK`."""
    got = None if names is None else names.arclog_at(relation.text)
    return marked(relation.text) if got is None else got


def case_name(solver: Solver, case: Case, names: NameMap | None) -> str:
    """The arclog name of `case`: the parts `solver.names.name` gives the
    case, in its order and joined as it joins them, each constructor by its
    `ALT` name and each parameter or relation of a `@derive` or `@store`
    branch by its arclog name; a part the map gives no name, by its Souffle
    text under `SOUFFLE_MARK`."""
    parts: list[str] = []
    choice = solver.choice
    if choice is not None and case.base is not None:
        for point, ctor in constructors_taken(choice, case.base):
            text = ctor_text(solver.engine, ctor)
            got = None if names is None else names.arclog_constructor(ctor)
            part = marked(text) if got is None else got
            if not is_concept_branch(point, ctor) and part not in parts:
                parts.append(part)
    ordered = [b for b in solver.branches if b in case.branches] + \
        [b for b in case.branches
         if b not in solver.branches and not isinstance(b, StoredAtDerive)]
    for b in ordered:
        match b:
            case DeriveBranch(parameter=p, proposer=q):
                parts.append(f"{_named(names, PARAMS_COMPONENT, p)}={q}")
            case StoreBranch(spelled=r):
                parts.append(f"{_named(names, (), r)}={VerdictWord.STORED}")
            case StoredAtDerive(parameter=p):
                parts.append(f"{_named(names, PARAMS_COMPONENT, p)}={VerdictWord.STORED}")
    return SEPARATOR.join(parts) or VerdictWord.CONCEPT.value


def _named(names: NameMap | None, component: tuple[str, ...], relation: str) -> str:
    """The arclog name of `relation` under `component`, else its Souffle
    name under `SOUFFLE_MARK`."""
    got = None if names is None else names.arclog_of(component, relation)
    return marked(relation) if got is None else got
