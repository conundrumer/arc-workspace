"""Builders of hand-made programs and grids, for the solver tests."""

from collections.abc import Sequence

from engine import (
    Comment,
    DeclId,
    Grid,
    Program,
    Scope,
    Span,
    Unit,
    UnitId,
)
from engine.program import (
    TypeName,
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
        Column(n, TypeName((), t)) for n, t in columns), (), (),
        span(line, file=file))


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


def grid(*rows: str) -> Grid:
    """A grid drawn as a grid: one row per string, cells separated by
    spaces."""
    return tuple(tuple(int(c) for c in r.split()) for r in rows)
