"""The rules that class the values of one column of a relation by the
relation's rows at each (`engine.Engine.classify`)."""

from dataclasses import replace
from pathlib import Path

from engine.engine import Classed
from engine.memo import ByIdentity
from engine.program import DeclId, Program, RelationName, Scope, UnitId
from engine.text import columns
from souffle import parser
from souffle.index import tree_of
from souffle.layout import next_decl, next_unit

ROWS = "_cls_out"
"""The classified relation's rows at each class's representative."""
CLASSES = "_cls_class"
"""Each value of the column with its class's representative."""

_CLASSING = """\
.type _cls_row = [{fields}]
.decl _cls_case(ch: {case})
_cls_case(Ch) :- {rel}({blank}).
.decl _cls_rec(ch: {case}, r: _cls_row)
_cls_rec(Ch, [{others}]) :- {rel}({args}).
.decl _cls_rows(ch: {case}, o: number)
_cls_rows(Ch, ord(R)) :- _cls_rec(Ch, R).
.decl _cls_fp(ch: {case}, n: number, s: number, t: number)
_cls_fp(Ch, N, S, T) :- _cls_case(Ch), N = count : {{ _cls_rows(Ch, _) }}, \
S = sum O : {{ _cls_rows(Ch, O) }}, T = sum O * O : {{ _cls_rows(Ch, O) }}.
.decl _cls_ord(ch: {case}, o: number)
_cls_ord(Ch, ord(Ch)) :- _cls_case(Ch).
.decl _cls_first(ch: {case}, o: number)
_cls_first(Ch, M) :- _cls_fp(Ch, N, S, T), \
M = min O : {{ _cls_fp(C2, N, S, T), _cls_ord(C2, O) }}.
.decl _cls_repc(ch: {case}, r: {case})
_cls_repc(Ch, R) :- _cls_first(Ch, O), _cls_ord(R, O).
.decl _cls_diff(ch: {case})
_cls_diff(Ch) :- _cls_repc(Ch, R), Ch != R, {rel}({args}), !{rel}({args_r}).
_cls_diff(Ch) :- _cls_repc(Ch, R), Ch != R, {rel}({args_r}), !{rel}({args}).
.decl {classes}(ch: {case}, r: {case})
{classes}(Ch, R) :- _cls_repc(Ch, R), !_cls_diff(Ch).
{classes}(Ch, Ch) :- _cls_diff(Ch).
.decl {rows}({columns})
{rows}({args}) :- {rel}({args}), {classes}(Ch, Ch).
"""
"""The rules: a fingerprint of each value's rows (their count, and the sum
and the sum of squares of each row's record number) proposes the least
value of equal fingerprint as its representative, and a value whose rows
differ from that value's in any row is its own representative. `{{` and
`}}` are braces."""

_CLASSED: ByIdentity[Program, dict[tuple[RelationName, int], Classed]] \
    = ByIdentity()
"""`classify`'s results for each program while it lives."""


def classify(program: Program, relation: RelationName, column: int) -> Classed:
    """`program` with the rules of `_CLASSING` over `relation`'s `column`
    (`engine.Engine.classify`). The parts the rules add are written parts,
    after every part of `program`."""
    return _CLASSED.keyed(program, (relation, column),
                          lambda: _classify(program, relation, column))


def _classify(program: Program, relation: RelationName, column: int
              ) -> Classed:
    """`classify`, computed."""
    hit = None if relation.instances \
        else tree_of(program).resolve(relation, Scope(()))
    if hit is None:
        raise ValueError(f"no top-level relation {relation.text}")
    cols = hit.decl.columns
    names = [f"Y{i}" if i != column else "Ch" for i in range(len(cols))]
    others = [i for i in range(len(cols)) if i != column]
    text = _CLASSING.format(
        rel=relation.name, rows=ROWS, classes=CLASSES,
        fields=", ".join(f"f{i}: {cols[i].type.text}" for i in others),
        case=cols[column].type.text,
        blank=", ".join("Ch" if i == column else "_"
                        for i in range(len(cols))),
        others=", ".join(names[i] for i in others),
        args=", ".join(names),
        args_r=", ".join("R" if i == column else names[i]
                         for i in range(len(cols))),
        columns=columns(cols))
    parsed = parser.parse(text, Path("."))
    if not isinstance(parsed, Program):
        raise ValueError(f"the classing rules do not parse: {parsed}")
    decls = next_decl(program)
    units = next_unit(program)
    classed = replace(
        program,
        types=(*program.types, *(
            replace(t, id=DeclId(decls + i))
            for i, t in enumerate(parsed.types))),
        relations=(*program.relations, *(
            replace(r, id=DeclId(decls + len(parsed.types) + i))
            for i, r in enumerate(parsed.relations))),
        units=(*program.units, *(
            replace(u, id=UnitId(units + i), span=None)
            for i, u in enumerate(parsed.units))))
    return Classed(classed, RelationName((), ROWS), RelationName((), CLASSES))
