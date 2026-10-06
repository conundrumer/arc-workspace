"""The Python module of the lib's component wrappers, as text: for each
public top-level component of the lib, a function that runs it through
`lib_components.call.call`."""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from engine.program import Primitive, Qualifier
from handbook.items import Comp, Decl, TypeDecl
from handbook.lib import LIB_SRC, _hidden, lib_sources, parse
from handbook.paths import repo_label

def _upper_snake(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).upper()


@dataclass(frozen=True)
class _WrappedDecl:
    """A relation of a component as its wrapper passes it: its name,
    whether it is an input, whether it is declared `inline`, and its
    column names and types, each type
    written in the component's own type parameters."""

    name: str
    input: bool
    inline: bool
    column_names: tuple[str, ...]
    column_types: tuple[str, ...]


def _comp_decls(comp: Comp, comps: dict[str, tuple[Comp, list[str]]]
                ) -> list[_WrappedDecl]:
    """The public relations a component declares or inherits from its
    base, its own before its base's."""
    out = [_WrappedDecl(it.name, it.input,
                        Qualifier.INLINE in it.qualifiers,
                        tuple(c.name for c in it.columns),
                        tuple(c.type for c in it.columns))
           for it in comp.items if isinstance(it, Decl) and not _hidden(it)]
    if comp.base is not None:
        if comp.base not in comps:
            raise SystemExit(f"`{comp.name}` extends `{comp.base}`, which no "
                             f"lib file declares")
        base = comps[comp.base][0]
        given = dict(zip(base.type_params, comp.base_type_args, strict=True))
        names = {d.name for d in out}
        out += [_WrappedDecl(d.name, d.input, d.inline, d.column_names,
                             tuple(given.get(t, t) for t in d.column_types))
                for d in _comp_decls(base, comps) if d.name not in names]
    return out


def _type_expr(t: str, comp: Comp, types: list[str]) -> str | None:
    """The Python expression of the column type `t` in a wrapper of
    `comp`: its type parameter, or the member of `Primitive` or `LibType`
    that names it. None for a type the calling program declares, which
    no Python call can declare."""
    if t in comp.type_params:
        return t
    if (prim := Primitive.named(t)) is not None:
        return f"Primitive.{prim.name}"
    if t in types:
        return f"LibType.{_upper_snake(t)}"
    return None


def wrappers_text(lib: Path = LIB_SRC) -> str:
    """The Python module of the lib's wrappers: the lib's types as an enum,
    and for each public top-level component whose columns are of the
    lib's types a function that runs it through `lib_components.call.call`
    over the relations it does not declare `inline`, with a tuple type of
    its output relations. A component that declares every relation
    `inline` gets no function."""
    types: list[str] = []
    comps: dict[str, tuple[Comp, list[str]]] = {}
    order: list[tuple[Path, Comp]] = []
    for path, text in lib_sources(lib):
        program = parse(text)
        for it in program.items:
            if isinstance(it, TypeDecl) and not _hidden(it):
                types.append(it.name)
            elif isinstance(it, Comp) and not _hidden(it):
                comps[it.name] = (it, text.splitlines())
                order.append((path, it))
    out = [mctx("\"\"\"Generated from the lib by scripts/context.py.\"\"\""), "",
           "from collections.abc import Iterable, Mapping",
           "from enum import StrEnum",
           "from typing import NamedTuple", "",
           "from engine.program import Primitive",
           "from lib_components.call import (Columns, GridTypes, PyRow, PyValue, Relation, Size,",
           "                                  call)",
           "", "",
           "class LibType(StrEnum):",
           '    """The types the lib declares, by name."""', ""]
    out += [f'    {_upper_snake(t)} = "{t}"' for t in types]
    out += ["", "", "type TypeArg = Primitive | LibType"]
    for path, comp in order:
        decls = [d for d in _comp_decls(comp, comps) if not d.inline]
        if not decls:
            continue
        exprs = {d.name: [_type_expr(t, comp, types) for t in d.column_types]
                 for d in decls}
        if any(None in e for e in exprs.values()):
            continue
        for d in decls:
            if keyword.iskeyword(d.name):
                raise SystemExit(f"`{comp.name}.{d.name}` is a Python keyword")
        ins = [d.name for d in decls if d.input]
        outs = [d.name for d in decls if not d.input]
        rows = f"{comp.name}Rows"
        out += ["", "", f"class {rows}(NamedTuple):",
                f'    """The output relations of `{comp.name}` '
                f'({repo_label(path)})."""', ""]
        out += [f"    {o}: Relation" for o in outs] or ["    pass"]
        params = [f"{t}: TypeArg" for t in comp.type_params]
        params += ["*", "sizes: Mapping[PyValue, Size] | None = None"]
        params += [f"{i}: Iterable[PyRow] | None = None" for i in ins]
        columns = ", ".join(
            f"{d.name!r}: Columns(("
            + "".join(f"{e}, " for e in exprs[d.name])
            + f"), {d.column_names[:1] == ('key',)})" for d in decls)
        out += ["", "", f"def {comp.name}({', '.join(params)}) -> {rows}:",
                f'    """Runs `{comp.name}` ({repo_label(path)}) over the rows '
                f'given, a cell of each `Position` column in the grid of '
                f'`sizes` for its key, or in the one grid of `sizes` where '
                f'the relation has no key, and each `Offset` column as a '
                f'(row, column) displacement."""',
                f"    got = call({comp.name!r}, [{', '.join(comp.type_params)}],",
                "               GridTypes(LibType.POSITION, LibType.OFFSET),",
                "               {" + columns + "},",
                "               {" + ", ".join(f"{i!r}: {i}" for i in ins) + "},",
                f"               {outs!r}, sizes)",
                f"    return {rows}(" + ", ".join(f"got[{o!r}]" for o in outs) + ")"]
    return "\n".join(out) + "\n"
