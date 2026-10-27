"""The check relations of a converted solver: for each Souffle relation whose
clauses the converter folds into other arclog relations, a relation of a name
of its own with a copy of those clauses, which the row-parity check compares
with Souffle's rows of the folded relation.

A folded relation is one that clauses of the solver head and that no arclog
name stands for (`arclog_convert.names.folded`). Its check relation is declared
in the scope of its clauses with the columns of the folded relation, and
nothing reads it, so the converter writes its clauses as it writes those of
any relation it does not fold, and the rest of the converted program is as it
is without it.

A folded relation whose columns are a case's (`Converter.case_types`) and
open values has the same kind of check relation. The converted program keeps
no column of either kind, so the check relation has no column: each clause
stands under the ALT its head's `Choice` fixes, as any clause of the
converter does, and a read of the open value in its body is a read of the
open parameter's `DET`. Where a clause reads no parameter, the relation
holds one row in each case that clause is written for. The column map gives an
empty list for each of its Souffle columns (`arclog_convert.names.check_maps`),
so the row-parity check compares, in each case it runs, whether the relation
has a row. `Converter.open_carriers_dropped` drops the clauses of every
relation of such columns but a check relation.

A check relation is a copy for the row-parity check alone, so one that the
copy cannot hold is left out. Where the converter writes a clause of a check
relation with a `TODO` line, which the reader refuses, the converter leaves
that check relation out of the check copy, and the column map gives the folded
relation's path as untranslated, with a reason that names the `TODO` kinds
(`todo_kinds`, `arclog_convert.names.dropped`). It does so too for a check
relation in whose text the arclog lint (`arclog_convert.lint.Linter`) finds a
violation, which the reader refuses as well, and the reason names the lint
codes (`lint_codes`). The other check relations stay."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from engine.program import Atom, DeclId, Program, RelationDecl, RelationName, Scope, Unit, UnitId
from souffle.parser import parse
from arclog_convert import paths
from arclog_convert.lib import Lib

CHECKED_SCOPES = ((), ("Parse",))
"""The scopes whose clauses get a check relation: the top level and the
solver's own `Parse` component."""


@dataclass(frozen=True)
class Fold:
    """A Souffle relation that clauses of the solver head: the component path
    the clauses stand in, the instance path of their heads (empty for a relation
    declared there), and the relation's name."""

    scope: tuple[str, ...]
    instances: tuple[str, ...]
    name: str

    @property
    def relation(self) -> str:
        """The relation's name in its scope, `<instance>.<name>` for an input
        of an instance."""
        return ".".join((*self.instances, self.name))


def clauses_of(prog: Program) -> dict[Fold, list[Unit]]:
    """The clauses of `prog` of each relation they head, in the scopes of
    `CHECKED_SCOPES`."""
    out: dict[Fold, list[Unit]] = {}
    for u in prog.units:
        if u.scope.components in CHECKED_SCOPES:
            out.setdefault(Fold(u.scope.components, u.head.relation.instances, u.head.relation.name), []).append(u)
    return out


_TODO_KIND = re.compile(r"^\s*;; TODO ([\w-]+):", re.MULTILINE)


def declaration_span(arclog: str, name: str) -> tuple[int, int] | None:
    """The offsets in the arclog `arclog` of the text of the declaration of the
    relation `name`: its comment lines before it, and the lines of its form.
    None where `arclog` declares no such relation."""
    from arclog_convert.lint import DECL_HEADS, L, Sym, read

    def region(forms: list, start: int) -> tuple[int, int] | None:
        before = start
        for f in forms:
            if not isinstance(f, L):
                continue
            if f.head in DECL_HEADS and len(f.items) > 1 and isinstance(f.items[1], Sym) and f.items[1].text == name:
                text = arclog[before:f.end]
                return before + len(text) - len(text.lstrip()), f.end
            if (got := region(f.items, f.start)) is not None:
                return got
            before = f.end
        return None

    return region(read(arclog), 0)


def todo_kinds(arclog: str, name: str) -> list[str]:
    """The kinds of the `TODO` lines in the text of the declaration of the
    relation `name` in the arclog `arclog` (`declaration_span`). Empty where
    `arclog` declares no such relation."""
    span = declaration_span(arclog, name)
    return [] if span is None else sorted(set(_TODO_KIND.findall(arclog[span[0]:span[1]])))


def lint_codes(arclog: str, name: str, violations: Sequence[tuple[int, str, str]]) -> list[str]:
    """The codes of those of `violations` (the `errs` of a `Linter` run over
    `arclog`: line, code, message) whose line falls in the text of the
    declaration of the relation `name` (`declaration_span`). Empty where
    `arclog` declares no such relation."""
    span = declaration_span(arclog, name)
    if span is None:
        return []
    first, last = arclog.count("\n", 0, span[0]) + 1, arclog.count("\n", 0, span[1]) + 1
    return sorted({code for line, code, _ in violations if first <= line <= last})


def check_name(fold: Fold, taken: set[str]) -> str:
    """The name of the check relation of `fold`, which is not in `taken`."""
    base = "_".join(("check", *fold.instances, fold.name))
    name, n = base, 2
    while name in taken:
        name, n = f"{base}{n}", n + 1
    return name


def _columns(prog: Program, lib: Lib, fold: Fold) -> str | None:
    """The columns of the folded relation as a declaration writes them, or
    None where the program and the lib give them no declaration of the
    relation."""
    scope = fold.scope
    if not fold.instances:
        decl = next((r for i in range(len(scope), -1, -1) for r in prog.relations
                     if r.name == fold.name and r.scope.components == scope[:i]), None)
        return None if decl is None else ", ".join(f"{c.name}: {c.type.text}" for c in decl.columns)
    if len(fold.instances) != 1:
        return None
    inst = next((i for k in range(len(scope), -1, -1) for i in prog.instances
                 if i.name == fold.instances[0] and i.scope.components == scope[:k]), None)
    if inst is None or inst.component not in lib.comps:
        return None
    tparams, rels = lib.present(inst.component)
    given = {p: a.text for p, a in zip(tparams, inst.type_args)}
    lr = next((r for r in rels if r.name == fold.name), None)
    return None if lr is None else ", ".join(f"{c.name}: {given.get(c.type, c.type)}" for c in lr.cols)


def with_checks(prog: Program, folds: Sequence[Fold], lib: Lib) -> tuple[Program, dict[Fold, str]]:
    """`prog` with a check relation for each of `folds` that has columns
    (`_columns`) and a clause: its declaration, in the scope of the clauses,
    and a copy of each clause under its name; and each such fold with the
    check relation's name."""
    clauses = clauses_of(prog)
    taken = {d.name for d in (*prog.relations, *prog.instances)}
    declarations = list(prog.relations)
    units = list(prog.units)
    made: dict[Fold, str] = {}
    next_decl = prog.next_decl_index()
    next_unit = prog.next_unit_index()
    for fold in folds:
        columns = _columns(prog, lib, fold)
        if columns is None or fold not in clauses:
            continue
        name = check_name(fold, taken)
        taken.add(name)
        parsed = parse(f".decl {name}({columns})", paths.ROOT / "programs")
        decl: RelationDecl = replace(parsed.relations[0], id=DeclId(next_decl), scope=Scope(fold.scope), span=None)
        next_decl += 1
        declarations.append(decl)
        for u in clauses[fold]:
            units.append(replace(u, id=UnitId(next_unit), span=None,
                                 head=Atom(RelationName((), name), u.head.args, u.head.line)))
            next_unit += 1
        made[fold] = name
    return replace(prog, relations=tuple(declarations), units=tuple(units)), made
