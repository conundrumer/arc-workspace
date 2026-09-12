"""Checks over the lib's sources, for the tests: the `@input` marks agree
with the rules, no file reads a name a later file defines, and every doc
comment documents something.

Each check returns its findings as messages that name files, units, and
relations; an empty list is a pass.
"""

from __future__ import annotations

from pathlib import Path

from dl.context import (DOCUMENTED, FILE_DOC, INPUT_MARK_RE, ITEM_DOC,
                        LIB_SRC, _doc_blocks, _documented, lib_sources)
from dl.dlparse import (Comp, Decl, Define, Functor, Item, Rule, TypeDecl,
                        _lex, parse)


def _marked(decl: Decl, lines: list[str]) -> bool:
    return any(INPUT_MARK_RE.search(lines[ln - 1])
               for ln in range(decl.line, decl.end_line + 1))


def input_marks(path: Path, text: str) -> list[str]:
    """Inside a comp, a decl is `@input` iff no rule in that comp derives
    it; facts under it are its default either way. A top-level `@input`
    has no rule."""
    lines = text.splitlines()
    out: list[str] = []

    def walk(items: list[Item], scope: str) -> None:
        derived = {it.head.name for it in items
                   if isinstance(it, Rule) and it.body is not None}
        for it in items:
            if isinstance(it, Comp):
                walk(it.items, it.name)
            elif isinstance(it, Decl):
                where = f"{scope}.{it.name}" if scope else it.name
                marked = _marked(it, lines)
                if marked and it.name in derived:
                    out.append(f"`{where}` has a rule and an `@input` mark")
                elif scope and not marked and it.name not in derived:
                    out.append(f"`{where}` has no rule and no `@input` mark")

    walk(parse(text).items, "")
    return [f"{path.name}: {m}" for m in out]


def _defined(items: list[Item]) -> set[str]:
    """The names a file defines at its top level: relations, comps, types,
    macros, and functors."""
    return {it.name for it in items
            if isinstance(it, (Decl, Comp, TypeDecl, Define, Functor))}


def module_order(sources: list[tuple[Path, str]]) -> list[str]:
    """No file reads a name that a later file defines, so the include
    order is a dependency order."""
    parsed = [(path, parse(text).items, text) for path, text in sources]
    per_file: list[list[str]] = []
    later: dict[str, Path] = {}   # each name and the latest file defining it
    for path, items, text in reversed(parsed):
        own = _defined(items)
        reads = {t.text for t in _lex(text)[0] if t.kind == "ident"}
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
    for end, (start, _) in sorted(_doc_blocks(program, FILE_DOC).items()):
        if first is not None and start > first:
            out.append(f"{path.name}:{start}: a `//!` block is not at the file's top")
    return out


def check(root: Path = LIB_SRC) -> list[str]:
    """Every check over the lib rooted at `root`."""
    sources = lib_sources(root)
    out: list[str] = []
    for path, text in sources:
        out.extend(input_marks(path, text))
        out.extend(doc_adjacency(path, text))
    out.extend(module_order(sources))
    return out
