"""A fake engine and builders of hand-made programs, for the solver tests:
the `souffle` engine is not what these tests are about."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from engine import (
    Atom,
    BodyLiteral,
    Comment,
    DeclId,
    Grid,
    GridLayout,
    GridValue,
    Index,
    InputValue,
    Limits,
    ParseFailure,
    Program,
    RelationName,
    RelationValue,
    RemovalTarget,
    Rendered,
    RunResult,
    Scope,
    Span,
    Term,
    Unit,
    UnitId,
)
from engine.engine import Classed, GridMisfit
from souffle.index import index_of
from engine.program import (
    AdtType,
    Column,
    Component,
    ConstructorDecl,
    Include,
    Instance,
    RelationDecl,
    TypeDecl,
)

def span(first: int, last: int | None = None, file: str | None = None) -> Span:
    return Span(first, first if last is None else last, file=file, width=40)


def comment(line: int, text: str, above: UnitId | DeclId | None = None,
            own_line: bool = True, column: int = 0) -> Comment:
    """A `//` comment, `text` as the line writes it; the comment's text is
    what follows the `//`."""
    return Comment(line, column, text.removeprefix("//"), own_line, above,
                   file=None, block=False)


def adt(id: int, name: str, line: int,
        ctors: Sequence[tuple[str, int]]) -> AdtType:
    """An ADT of the solver's own text: each constructor with its line."""
    last = max((ln for _n, ln in ctors), default=line)
    return AdtType(DeclId(id), name, Scope(()), tuple(
        ConstructorDecl(n, (), span(ln), True) for n, ln in ctors),
        span(line, last))


def relation(id: int, name: str, line: int, scope: tuple[str, ...] = (),
             columns: Sequence[tuple[str, str]] = (),
             file: str | None = None) -> RelationDecl:
    return RelationDecl(DeclId(id), name, Scope(scope), tuple(
        Column(n, t) for n, t in columns), (), (), span(line, file=file))


def component(id: int, name: str, first: int, last: int,
              file: str | None = None) -> Component:
    return Component(DeclId(id), name, Scope(()), (), None, (),
                     span(first, last, file))


def instance(id: int, name: str, comp: str, line: int) -> Instance:
    return Instance(DeclId(id), name, Scope(()), comp, (), span(line))


def atom(line: int, relation: str, *args: Term) -> Atom:
    """An atom on `relation`, written as a clause reads it:
    `params.bg`."""
    path, _dot, name = relation.rpartition(".")
    return Atom(RelationName(tuple(path.split(".")) if path else (), name),
                args, line)


def unit(id: int, line: int, head: Atom,
         body: Sequence[BodyLiteral] | None = None,
         scope: tuple[str, ...] = ()) -> Unit:
    """A clause of the solver's own text; a fact where `body` is None."""
    return Unit(UnitId(id), Scope(scope), head,
                None if body is None else tuple(body), None, span(line))


def program(*, types: Sequence[TypeDecl] = (),
            relations: Sequence[RelationDecl] = (),
            components: Sequence[Component] = (),
            instances: Sequence[Instance] = (),
            units: Sequence[Unit] = (),
            comments: Sequence[Comment] = ()) -> Program:
    """A program that includes the lib."""
    return Program(tuple(types), tuple(relations), tuple(components),
                   tuple(instances), (), tuple(units), (), tuple(comments),
                   (Include("../lib.dl", 1, file=None),), ())


@dataclass
class FakeEngine:
    """An engine whose parse gives one program and whose runs a function
    scripts; the rewrites record themselves and change nothing."""

    parsed: Program | ParseFailure
    runs: Callable[[Program, Mapping[RelationName, InputValue],
                    Sequence[RelationName]], RunResult]
    fixed: list[tuple[RelationName, RelationValue]] = field(
        default_factory=list[tuple[RelationName, RelationValue]])

    def parse(self, text: str, base_dir: Path) -> Program | ParseFailure:
        return self.parsed

    def parse_including(self, text: str, included: str,
                        base_dir: Path) -> Program | ParseFailure:
        return self.parsed

    def index(self, program: Program) -> Index:
        return index_of(program)

    def fix_relation(self, program: Program, relation: RelationName,
                     value: RelationValue) -> Program:
        self.fixed.append((relation, value))
        return program

    def place_grid(self, layout: GridLayout, mark: tuple[int, int] | None,
                   value: GridValue) -> GridValue | GridMisfit:
        raise NotImplementedError

    def remove(self, program: Program, target: RemovalTarget) -> Program:
        return program

    def instantiate(self, program: Program, component: str,
                    name: str) -> Program:
        return program

    def run(self, program: Program, inputs: Mapping[RelationName, InputValue],
            outputs: Sequence[RelationName], limits: Limits,
            caps: Mapping[RelationName, int] | None = None) -> RunResult:
        return self.runs(program, inputs, outputs)

    def classify(self, program: Program, relation: RelationName,
                 column: int) -> Classed:
        raise NotImplementedError

    def expand(self, program: Program) -> Program:
        return program

    def render(self, program: Program) -> Rendered:
        return Rendered(())


def grid(*rows: str) -> Grid:
    """A grid drawn as a grid: one row per string, cells separated by
    spaces."""
    return tuple(tuple(int(c) for c in r.split()) for r in rows)
