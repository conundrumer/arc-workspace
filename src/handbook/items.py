"""One lib file as the handbook's readers read it: its top-level items in
file order, each component with its own items, and its comments, from the
engine's parse of that file alone. Parts of the files it includes are not
its items."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from engine import ParseFailure
from engine import Program as Parsed
from engine.program import (
    AdtType,
    AliasType,
    Column,
    Qualifier,
    RecordType,
    Scope,
    SubtypeType,
    UnionType,
    own,
)
from solver.annotations import input_mark_lines, input_marked
from souffle import SouffleEngine


@dataclass(frozen=True)
class SubtypeForm:
    """`.type A <: B`: the base."""

    base: str


@dataclass(frozen=True)
class OtherForm:
    """Any type form but a subtype."""


@dataclass
class Include:
    path: str
    line: int


@dataclass
class Define:
    name: str
    line: int


@dataclass
class TypeDecl:
    name: str
    line: int
    end_line: int
    form: SubtypeForm | OtherForm


@dataclass
class Decl:
    name: str
    line: int
    end_line: int
    columns: tuple[Column, ...]
    qualifiers: tuple[Qualifier, ...]
    choice_domain: tuple[str, ...]
    input: bool
    """The declaration bears the lib's `// @input` mark."""


@dataclass
class Init:
    inst: str
    line: int
    end_line: int


@dataclass
class Head:
    name: str


@dataclass
class Rule:
    head: Head
    body: object | None
    line: int
    end_line: int


@dataclass
class Functor:
    name: str
    line: int
    end_line: int


@dataclass
class Comp:
    name: str
    line: int
    end_line: int
    type_params: tuple[str, ...]
    base: str | None
    """The component it extends; None where it extends none."""
    base_type_args: tuple[str, ...]
    items: list[Item] = field(default_factory=list)


type Item = Include | Define | TypeDecl | Decl | Init | Rule | Functor | Comp


@dataclass(frozen=True)
class Comment:
    """A comment with its delimiters, as the file writes it."""

    line: int
    text: str
    own_line: bool


@dataclass
class Program:
    items: list[Item]
    comments: list[Comment]


class ParseError(ValueError):
    """The file leaves the grammar."""


def parse(text: str, base_dir: Path = Path(".")) -> Program:
    """The items and comments of one lib file, each `#include` in it
    resolved against `base_dir` and its parts left out. Raises
    `ParseError` where the text leaves the grammar."""
    parsed = SouffleEngine(functor_dir=None, cache_dir=None).parse(
        text, base_dir)
    if isinstance(parsed, ParseFailure):
        raise ParseError(f"{parsed.line}:{parsed.column}: {parsed.message}")
    return _view(parsed)


def _view(p: Parsed) -> Program:
    placed: list[tuple[int, Scope, Item]] = []

    comps: dict[tuple[str, ...], Comp] = {}
    for c in p.components:
        if c.span is None or not own(c.span):
            continue
        comp = Comp(c.name, c.span.first, c.span.last, c.type_params,
                    c.base, tuple(a.text for a in c.base_type_args))
        comps[(*c.scope.components, c.name)] = comp
        placed.append((c.span.first, c.scope, comp))
    for t in p.types:
        if not own(t.span):
            continue
        form: SubtypeForm | OtherForm = SubtypeForm(t.base.text) \
            if isinstance(t, SubtypeType) else OtherForm()
        assert isinstance(t, AdtType | RecordType | AliasType | SubtypeType
                          | UnionType)
        placed.append((t.span.first, t.scope,
                       TypeDecl(t.name, t.span.first, t.span.last, form)))
    marks = input_mark_lines(p.comments)
    for r in p.relations:
        if own(r.span):
            placed.append((r.span.first, r.scope,
                           Decl(r.name, r.span.first, r.span.last,
                                r.columns, r.qualifiers, r.choice_domain,
                                input_marked(r.span, marks))))
    for i in p.instances:
        if i.span is not None and own(i.span):
            placed.append((i.span.first, i.scope,
                           Init(i.name, i.span.first, i.span.last)))
    for f in p.functors:
        if own(f.span):
            placed.append((f.span.first, Scope(()),
                           Functor(f.name, f.span.first, f.span.last)))
    seen: set[tuple[int, int, str]] = set()
    for u in p.units:
        if u.span is None or not own(u.span):
            continue
        key = (u.span.first, u.span.last, "/".join(u.scope.components))
        if key in seen:
            continue
        seen.add(key)
        placed.append((u.span.first, u.scope,
                       Rule(Head(u.head.relation.name), u.body, u.span.first,
                            u.span.last)))
    for inc in p.includes:
        if own(inc):
            placed.append((inc.line, Scope(()), Include(inc.path, inc.line)))
    for d in p.defines:
        if own(d):
            placed.append((d.line, Scope(()), Define(d.name, d.line)))
    top: list[Item] = []
    for _line, scope, item in sorted(placed, key=lambda x: x[0]):
        holder = comps.get(scope.components)
        (holder.items if holder is not None else top).append(item)
    comments = [Comment(c.line, ("/*" + c.text + "*/") if c.block
                        else "//" + c.text, c.own_line)
                for c in p.comments if own(c)]
    return Program(top, comments)
