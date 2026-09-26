"""The rows a solver derives in named relations on one grid."""

import re
from dataclasses import dataclass
from pathlib import Path

from dl.dlparse import TOP, EXTERN, Index, ParseError, parse
from dl.facts import grid_to_facts
from dl.models import Cases, Space, case_label, model_label
from dl.souffle import _run_source
from dl.source import build_source

CASE_TYPE = "Choice"
"""The type of a column that holds a case."""

UNDEFINED_RE = re.compile(
    r"Undefined relation (\S+) in file \S+ at line \d+\n\.output ")
BLOCK_RE = re.compile(r"^-+\n(\S+)\n(.*?)\n=+\n(.*?)=+\n", re.M | re.S)


class MissingRelations(Exception):
    """The names of the relations the program does not declare."""

    def __init__(self, names: list[str]) -> None:
        super().__init__(", ".join(names))
        self.names = names


@dataclass
class Relation:
    """One relation's attribute names, and its rows as Souffle prints them,
    one list of column texts per fact."""

    columns: list[str]
    rows: list[list[str]]


def relation_rows(source: str, names: list[str], grid: list[list[int]],
                  space: Cases, solver_path: Path | None = None
                  ) -> dict[str, Relation]:
    """Run `source` on `grid` with an `.output` directive for each of
    `names`, and read each one's rows. A column of the case type holds each
    case by its name in `space`. Raises MissingRelations naming the ones
    the program does not declare, and RuntimeError on any other failure of
    the run."""
    built = build_source(source) + "".join(
        f".output {name}(IO=stdout)\n" for name in names)
    try:
        stdout = _run_source(built, grid_to_facts(grid),
                             solver_path=solver_path)
    except RuntimeError as e:
        missing = UNDEFINED_RE.findall(str(e))
        if missing:
            raise MissingRelations(
                [n for n in dict.fromkeys(missing) if n in names]
                or missing) from None
        raise
    blocks = {m[1]: (m[2], m[3]) for m in BLOCK_RE.finditer(stdout)}
    types = _column_types(source)
    out: dict[str, Relation] = {}
    for name in names:
        head, body = blocks.get(name, ("", ""))
        rows = [line.split("\t") for line in body.splitlines() if line]
        cases = [i for i, t in enumerate(types.get(name, []))
                 if t == CASE_TYPE]
        for row in rows:
            for i in cases:
                if i < len(row):
                    row[i] = _case_name(space, row[i])
        out[name] = Relation(head.split("\t") if head else [], rows)
    return out


def _column_types(source: str) -> dict[str, list[str]]:
    """The column types of each relation the solver declares, by the name
    a directive gives it: top-level relations, and those of an instance of
    a component the solver declares."""
    try:
        index = Index(parse(source))
    except ParseError:
        return {}
    out: dict[str, list[str]] = {}
    for name, decl in index.decls.get(TOP, {}).items():
        out[name] = [f.type for f in decl.fields]
    for inst in index.inits.get(TOP, {}):
        for scope in index.chain(index.inits[TOP][inst].comp):
            for name, decl in index.decls.get(scope, {}).items():
                out.setdefault(f"{inst}.{name}",
                               [f.type for f in decl.fields])
    out.pop(EXTERN, None)
    return out


def _case_name(space: Cases, value: str) -> str:
    """A case as Souffle prints it, by its shortest name in `space`."""
    if isinstance(space, Space):
        return space.short_name(model_label(value))
    return case_label(value)
