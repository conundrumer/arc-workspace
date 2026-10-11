"""Checks over the lib's sources, run before the handbook's reader files are
written: the `@input` marks agree with the rules, no file reads a name a
later file defines, and every doc comment documents something.

Each check returns its findings as messages that name files, units, and
relations; an empty list is a pass.
"""

from __future__ import annotations

from pathlib import Path

from engine import ParseFailure, checkout
from engine.program import own
from handbook.lib import (FILE_DOC, ITEM_DOC, _doc_blocks, _documented,
                          lib_sources, parse)
from handbook.items import Comp, Decl, Define, Functor, Item, TypeDecl
from solver.annotations import input_mark_lines, input_marked
from souffle import SouffleEngine
from souffle.lexer import lex


def input_marks(path: Path, text: str) -> list[str]:
    """Inside a component, a relation no rule of that component derives is
    `@input`; an `@input` may also have rules of that component, which are
    its default, as the facts under it are. A top-level `@input` has no
    rule."""
    program = SouffleEngine(functor_dir=None, cache_dir=None).parse(
        text, checkout.programs())
    if isinstance(program, ParseFailure):
        return [f"{path.name}:{program.line}: {program.message}"]
    marks = input_mark_lines(program.comments)
    # A rule through an instance (`inst.rel(...) :- ...`) is not its scope's.
    derived = {(u.scope.components, u.head.relation.name)
               for u in program.units
               if own(u.span)
               and u.body is not None and not u.head.relation.instances}
    out: list[str] = []
    for r in program.relations:
        if not own(r.span):
            continue
        scope = r.scope.components
        where = ".".join((*scope, r.name))
        marked = input_marked(r.span, marks)
        rule = (scope, r.name) in derived
        if marked and rule and not scope:
            out.append(f"{path.name}:{r.span.first}: `{where}` has a rule "
                       f"and an `@input` mark")
        elif scope and not marked and not rule:
            out.append(f"{path.name}:{r.span.first}: `{where}` has no rule "
                       f"and no `@input` mark")
    return out


def _defined(items: list[Item]) -> set[str]:
    """The names a file defines at its top level: relations, components,
    types, macros, and functors."""
    return {it.name for it in items
            if isinstance(it, (Decl, Comp, TypeDecl, Define, Functor))}


def module_order(sources: list[tuple[Path, str]]) -> list[str]:
    """No file reads a name that a later file defines, so the include
    order is a dependency order."""
    per_file: list[list[str]] = []
    later: dict[str, Path] = {}   # each name and the latest file defining it
    for path, text in reversed(sources):
        own = _defined(parse(text).items)
        reads = {t.text for t in lex(text)[0] if t.kind == "ident"}
        per_file.append([
            f"`{path.name}` reads `{name}`, defined in `{later[name].name}`, "
            f"which is included later"
            for name in sorted(reads & set(later) - own)])
        for name in own:
            later[name] = path
    return [m for file in reversed(per_file) for m in file]


def doc_adjacency(path: Path, text: str) -> list[str]:
    """Every `///` block stands over a declaration, and every `//!` block
    stands at the file's top."""
    program = parse(text)
    attached = {it.line - 1 for it in _documented(program.items)}
    out: list[str] = []
    for end, (start, _) in sorted(_doc_blocks(program, ITEM_DOC).items()):
        if end not in attached:
            out.append(f"{path.name}:{start}: a `///` block stands over no declaration")
    first = min((it.line for it in program.items), default=None)
    for _, (start, _) in sorted(_doc_blocks(program, FILE_DOC).items()):
        if first is not None and start > first:
            out.append(f"{path.name}:{start}: a `//!` block is not at the file's top")
    return out


def check(root: Path | None = None) -> list[str]:
    """Every check over the lib rooted at `root`, the lib the runner reads
    where none is given."""
    sources = lib_sources(root)
    out: list[str] = []
    for path, text in sources:
        out.extend(input_marks(path, text))
        out.extend(doc_adjacency(path, text))
    out.extend(module_order(sources))
    return out
