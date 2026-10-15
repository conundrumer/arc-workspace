"""The rules that class the keys of a relation, the values of some of its
columns, by the relation's rows at each (`engine.Engine.classify`)."""

from dataclasses import replace
from pathlib import Path

from engine.engine import Classed
from engine.memo import ByIdentity
from engine.program import DeclId, Program, RelationName, Scope, UnitId
from souffle import parser
from souffle.index import tree_of
from souffle.layout import next_decl, next_unit
from souffle.text import columns, declared

ROWS = "_cls_out"
"""The classified relation's rows at each class's representative."""
CLASSES = "_cls_class"
"""Each value of the column with its class's representative."""

KEY = "_cls_key"
"""The record type of a key of more than one column."""

_CLASSING = """\
{key_type}.type _cls_row = [{fields}]
.decl _cls_case(ch: {case})
_cls_case({key}) :- {rel}({blank}).
.decl _cls_rec(ch: {case}, r: _cls_row)
_cls_rec({key}, [{others}]) :- {rel}({args}).
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
_cls_diff(Ch) :- _cls_repc(Ch, R), Ch != R{bind}, {rel}({args}), !{rel}({args_r}).
_cls_diff(Ch) :- _cls_repc(Ch, R), Ch != R{bind}, {rel}({args_r}), !{rel}({args}).
.decl {classes}(ch: {case}, r: {case})
{classes}(Ch, R) :- _cls_repc(Ch, R), !_cls_diff(Ch).
{classes}(Ch, Ch) :- _cls_diff(Ch).
.decl {rows}({columns})
{rows}({args}) :- {rows_body}.
"""
"""The rules: a fingerprint of each value's rows (their count, and the sum
and the sum of squares of each row's record number) proposes the least
value of equal fingerprint as its representative, and a value whose rows
differ from that value's in any row is its own representative. A key of
one column is that column's value, `Ch` in the relation's atoms; a key of
more is a `KEY` record of the columns' values, `K<i>` in the atoms, and
`R<i>` at the representative, and the rule of the representatives' rows
takes each representative before its rows, since Souffle looks a key
record built from each row of the relation up in the classes slowly. `{{`
and `}}` are braces."""

_CLASSED: ByIdentity[Program,
                     dict[tuple[RelationName, tuple[int, ...]], Classed]] \
    = ByIdentity()
"""`classify`'s results for each program while it lives."""


def classify(program: Program, relation: RelationName,
             key: tuple[int, ...]) -> Classed:
    """`program` with the rules of `_CLASSING` over `relation`'s columns
    `key` (`engine.Engine.classify`). The parts the rules add are written parts,
    after every part of `program`."""
    return _CLASSED.keyed(program, (relation, key),
                          lambda: _classify(program, relation, key))


def _classify(program: Program, relation: RelationName, key: tuple[int, ...]
              ) -> Classed:
    """`classify`, computed."""
    hit = None if relation.instances \
        else tree_of(program).resolve(relation, Scope(()))
    if hit is None:
        raise ValueError(f"no top-level relation {relation.text}")
    cols = hit.decl.columns
    if not key or len(set(key)) != len(key):
        raise ValueError(f"no key of distinct columns: {key}")
    one = len(key) == 1
    at = {c: "Ch" if one else f"K{j}" for j, c in enumerate(key)}
    at_r = {c: "R" if one else f"R{j}" for j, c in enumerate(key)}
    names = [at.get(i, f"Y{i}") for i in range(len(cols))]
    others = [i for i in range(len(cols)) if i not in at]
    text = _CLASSING.format(
        rel=relation.name, rows=ROWS, classes=CLASSES,
        key_type="" if one else (
            f".type {KEY} = ["
            f"{declared((f'k{j}', cols[c].type) for j, c in enumerate(key))}]\n"),
        key="Ch" if one else f"[{', '.join(at[c] for c in key)}]",
        rows_body=(f"{relation.name}({', '.join(names)}), {CLASSES}(Ch, Ch)"
                   if one else
                   f"{CLASSES}(Ch, Ch), Ch = [{', '.join(at[c] for c in key)}]"
                   f", {relation.name}({', '.join(names)})"),
        bind="" if one else (
            f", Ch = [{', '.join(at[c] for c in key)}]"
            f", R = [{', '.join(at_r[c] for c in key)}]"),
        fields=declared((f"f{i}", cols[i].type) for i in others),
        case=cols[key[0]].type.text if one else KEY,
        blank=", ".join(at.get(i, "_") for i in range(len(cols))),
        others=", ".join(names[i] for i in others),
        args=", ".join(names),
        args_r=", ".join(at_r.get(i, names[i]) for i in range(len(cols))),
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
