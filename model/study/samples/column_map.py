"""The columns of a graph query's output, and the rewrite of a reference from the columns of one table to those of another.

A table is a leaf list: one leaf for each column the engine exports, in the engine's order, without Example. The leaves of an INIT's output are the fields of its key record, then the output's own columns:
- a field of the key record is named `key.<Label>`, with <Label> the label that a `^` marks in the key clause (a key of one label is a record of one field);
- another column is named `:<column>`, as the registry gives the output's columns (a column of a type parameter that holds a record of several columns is `:<column>.<j>`).
The leaves of a RULE or a DET are its columns `:<label>`, or, where the form is a bare proposer, the proposer's columns.

A reference to a table writes its sites on those leaves: `(:key (:F label))` for a field of the key record, `(:C label)` for a column. `rewrite` writes the sites of a reference that reads one table again over another table of the same column types. It pairs the leaves by type; where several leaves have one type it pairs them by origin (the column that a RULE's column came from), then by name, then by place.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
import re
from collections import Counter
from dataclasses import dataclass

import canon_text
from canon_text import Tree

KEY = 'key.'
MARK = re.compile(r'^[*^]?([A-Z][A-Za-z0-9_]*)$')
CARET = re.compile(r'^\^([A-Z][A-Za-z0-9_]*)$')


@dataclass(frozen=True)
class Leaf:
    type: str
    name: str
    origin: str


def key_labels(tree: list[Tree]) -> list[str]:
    """The labels that a `^` marks in the key clause of an INIT, in order of appearance."""
    got: dict[str, None] = {}

    def go(x: Tree) -> None:
        if isinstance(x, str):
            m = CARET.match(x)
            if m:
                got.setdefault(m[1])
        else:
            for y in x:
                go(y)
    for c in tree[3:]:
        if isinstance(c, list) and c[:1] == ['key'] and len(c) > 1 and isinstance(c[1], list):
            go(c[1])
    return list(got)


def port_names(fields: list[str], labels: list[str], sizes: dict[str, int] | None = None, heads: dict[str, list[str]] | None = None) -> list[str] | None:
    """The names of an output's columns after its key, from the registry's fields and the row store's labels of those columns; None where they do not fit. A field of a type parameter (lowercase) holds a record of as many columns as the form gives it in `sizes` (a head's `(:observed Key Key2)` is two), else as many as the types leave, shared by the parameters. A parameter of one column is a plain column; of several, its columns are `:<field>.<label>`, the label the name of the record's field: the one that the form's head gives in `heads` where it gives as many as the record has columns, else the row store's, which names the field as the first graph query of the QueryHash does."""
    count = len(labels)
    if len(fields) == count:
        return fields
    params = [i for i, f in enumerate(fields) if f[1:2].islower()]
    spare = count - (len(fields) - len(params))
    if not params or spare < len(params):
        return None
    sized = [(sizes or {}).get(fields[i]) for i in params]
    if all(x is not None for x in sized) and sum(x or 0 for x in sized) == spare:
        width = {i: x or 0 for i, x in zip(params, sized)}
    elif spare % len(params) == 0:
        width = {i: spare // len(params) for i in params}
    else:
        return None
    names: list[str] = []
    for i, f in enumerate(fields):
        if i in width and width[i] != 1:
            at = len(names)
            head = (heads or {}).get(f, [])
            names += [f'{f}.{head[j] if len(head) == width[i] else labels[at + j] or j}' for j in range(width[i])]
        else:
            names.append(f)
    return names


def leaves(kind: str, tree: list[Tree], cols: dict[str, str], out: str, types: list[str], labels: list[str], example: str = '') -> list[Leaf] | None:
    """The leaves of the output `out` of a form of this kind, given the column types and labels that the row store holds, and `example`, the name that a site gives the table's Example column ('' where it has none); None where the names do not fit the types. The Example column is a leaf of the type Example, named as a site names it."""
    got = columns(kind, tree, cols, out, types, labels, example)
    return got + [Leaf('Example', example, example)] if got is not None and example else got


def columns(kind: str, tree: list[Tree], cols: dict[str, str], out: str, types: list[str], labels: list[str], example: str) -> list[Leaf] | None:
    """The leaves but the Example column. A key field that the Example column is (the key group writes `^Key` for it, and the store's label for that column is `Key`) is no leaf of the key."""
    if kind == 'INIT':
        port = canon_text.port_registry().get((str(tree[2]), out))
        if port is None:
            return None
        keys = key_labels(tree) if port[0] else []
        places = {k: i for i, k in enumerate(keys)}
        keys = [k for k in keys if ':' + k != example]
        fields = port[1]
        if len(keys) > len(types):
            return None
        names = port_names(fields, labels[len(keys):len(types)], head_sizes(tree), head_labels(tree))
        if names is None:
            # an output has the fields that the form's ports give: a field that no port head of the form names is no column
            named = head_fields(tree)
            fields = [f for f in fields if f in named]
            names = port_names(fields, labels[len(keys):len(types)], head_sizes(tree), head_labels(tree))
        if names is None:
            return None
        got = [Leaf(types[i], KEY + k, f'key#{places[k]}') for i, k in enumerate(keys)]
        for j, name in enumerate(names):
            got.append(Leaf(types[len(keys) + j], name, canon_text.out_field(fields.index(name.partition('.')[0]))))
        return got
    bare = tree[2] if len(tree) == 3 and isinstance(tree[2], str) else None
    names = canon_text.proposer_columns().get(bare, []) if bare else [':' + x if x else '' for x in labels]
    if len(names) != len(types) or not all(names):
        return None
    return [Leaf(t, n, cols.get(n, n)) for t, n in zip(types, names)]


def port_clauses(tree: list[Tree]) -> list[list[Tree]]:
    """The port clauses of an INIT: its own, and those inside its key clause."""
    out: list[list[Tree]] = []
    for c in tree[3:]:
        if isinstance(c, list) and c[:1] == ['key']:
            out += [p for p in c[2:] if isinstance(p, list)]
        elif isinstance(c, list):
            out.append(c)
    return out


def head_fields(tree: list[Tree]) -> set[str]:
    """The fields `:name` that the heads of the input ports of an INIT name, as in `(source_distance ((:K K)) ...)`."""
    got: set[str] = set()
    for c in port_clauses(tree):
        if len(c) > 1 and isinstance(c[1], list):
            for f in c[1]:
                if isinstance(f, list) and f and isinstance(f[0], str) and f[0].startswith(':'):
                    got.add(f[0])
    return got


def head_sizes(tree: list[Tree]) -> dict[str, int]:
    """{field `:name`: the count of labels it has in the heads of the INIT's input ports}, as `(:observed Key Key2)` has two; a field with other counts in two heads is left out."""
    got: dict[str, int] = {}
    bad: set[str] = set()
    for c in port_clauses(tree):
        if len(c) > 1 and isinstance(c[1], list):
            for f in c[1]:
                if isinstance(f, list) and f and isinstance(f[0], str) and f[0].startswith(':') and all(isinstance(x, str) for x in f[1:]):
                    if got.setdefault(f[0], len(f) - 1) != len(f) - 1:
                        bad.add(f[0])
    return {k: v for k, v in got.items() if k not in bad}


def head_labels(tree: list[Tree]) -> dict[str, list[str]]:
    """{field `:name`: its labels in the heads of the INIT's input ports}, as `(:observed Key Key2)` has Key and Key2; a field with other labels in two heads is left out."""
    got: dict[str, list[str]] = {}
    bad: set[str] = set()
    for c in port_clauses(tree):
        if len(c) > 1 and isinstance(c[1], list):
            for f in c[1]:
                if isinstance(f, list) and f and isinstance(f[0], str) and f[0].startswith(':') and all(isinstance(x, str) for x in f[1:]):
                    labels = [x for x in f[1:] if isinstance(x, str)]
                    if got.setdefault(f[0], labels) != labels:
                        bad.add(f[0])
    return {k: v for k, v in got.items() if k not in bad}


def pair(a: list[Leaf], b: list[Leaf]) -> tuple[dict[str, str], int] | None:
    """({name of a leaf of a: name of the leaf of b it pairs with}, the count of types with several leaves); None where the types differ."""
    if Counter(x.type for x in a) != Counter(x.type for x in b):
        return None
    out: dict[str, str] = {}
    ties = 0
    for t in sorted({x.type for x in a}):
        la, lb = [x for x in a if x.type == t], [x for x in b if x.type == t]
        if len(la) > 1:
            ties += 1
        for key in (lambda x: x.origin, lambda x: x.name):
            for x in list(la):
                same_a, same_b = [y for y in la if key(y) == key(x)], [y for y in lb if key(y) == key(x)]
                if len(same_a) == 1 and len(same_b) == 1:
                    out[x.name] = same_b[0].name
                    la.remove(x)
                    lb.remove(same_b[0])
        for x, y in zip(la, lb):
            out[x.name] = y.name
    return out, ties


def pair_cols(old: dict[str, str], new: dict[str, str]) -> dict[str, str] | None:
    """The pairing of the columns of two RULEs or DETs (column -> origin) that the row store lacks: the only column where each has one, else the columns of the same origin where every origin is one column's in each; else, where that fails, `pair_rest`; None otherwise."""
    if len(old) == len(new):
        if len(old) == 1:
            return {next(iter(old)): next(iter(new))}
        out: dict[str, str] = {}
        for n, o in old.items():
            same_old, same_new = [x for x, y in old.items() if y == o], [x for x, y in new.items() if y == o]
            if len(same_old) != 1 or len(same_new) != 1:
                break
            out[n] = same_new[0]
        else:
            return out
    return pair_rest(old, new)


def pair_rest(old: dict[str, str], new: dict[str, str]) -> dict[str, str] | None:
    """A column of the same name and origin pairs with its namesake. A column of either side that has the origin of one so paired is that column again (a variable of one branch of an OR that names the column of another), so it has no pair. The columns left pair where each side has one."""
    out = {n: n for n, o in old.items() if new.get(n) == o}
    same = {old[n] for n in out}
    left_old = [n for n, o in old.items() if n not in out and o not in same]
    left_new = [n for n, o in new.items() if n not in out.values() and o not in same]
    if len(left_old) != len(left_new) or len(left_old) > 1:
        return None
    return out | dict(zip(left_old, left_new))


def sites(atom: list[Tree], records: set[str]) -> list[tuple[str, list[Tree]]] | None:
    """(the leaf each site of the atom is on, the site's labels); None where a site is not one this module reads. `:key` and each head in `records` are records: a site on one has a site on each field in it, and a field is a leaf."""
    got: list[tuple[str, list[Tree]]] = []
    for s in atom[1:]:
        if not (isinstance(s, list) and s and isinstance(s[0], str) and s[0].startswith(':')):
            return None
        if s[0] != ':key' and s[0] not in records:
            got.append((s[0], s[1:]))
            continue
        prefix = KEY if s[0] == ':key' else s[0] + '.'
        for f in s[1:]:
            if isinstance(f, list) and f and isinstance(f[0], str) and f[0].startswith(':'):
                got.append((prefix + f[0][1:], f[1:]))
            elif isinstance(f, str) and MARK.match(f):
                got.append((prefix + f.lstrip('*^'), [f]))
            else:
                return None
    return got


def records_of(a: list[Leaf]) -> set[str]:
    """The heads of the columns of a table that are records of several columns (a type parameter's)."""
    return {x.name.partition('.')[0] for x in a if '.' in x.name and not x.name.startswith(KEY)}


def rewrite(atom: list[Tree], head: str, onto: dict[str, str], records: set[str]) -> list[Tree] | None:
    """The atom with `head` as its relation, its sites moved by `onto` (leaf name -> leaf name); None where a site is on a leaf that `onto` lacks."""
    ss = sites(atom, records)
    if ss is None:
        return None
    nested: dict[str, list[Tree]] = {}
    plain: list[Tree] = []
    for name, rest in ss:
        new = onto.get(name)
        if new is None:
            return None
        if new.startswith(KEY):
            nested.setdefault(':key', []).append([':' + new[len(KEY):], *rest])
        elif '.' in new:
            at, _, field = new.partition('.')
            nested.setdefault(at, []).append([':' + field, *rest])
        else:
            plain.append([new, *rest])
    return [head, *([[at, *fs] for at, fs in nested.items()]), *plain]


COMPARISONS = ('=', '!=', '<', '<=', '>', '>=')


def held_atom(tree: list[Tree], port: str) -> str | None:
    """The relation of the one positive atom in the body of the input `port` of an INIT, where that body is that atom and NOT atoms only (the engine exports no table for such an input); None otherwise, and for a port that is no input of the INIT."""
    body: list[Tree] | None = None
    for c in tree[3:]:
        if not isinstance(c, list) or not c:
            continue
        groups = [p for p in c[2:] if isinstance(p, list)] if c[0] == 'key' else [c]
        for p in groups:
            if p[:1] == [port] and port != 'key':
                body = p[2:]
    if body is None:
        return None
    positive: list[str] = []
    for item in body:
        if not (isinstance(item, list) and item and isinstance(item[0], str)):
            return None
        if item[0] == 'NOT':
            if not all(isinstance(a, list) and a and isinstance(a[0], str) and a[0] not in ('OR', 'IF', 'ALL', 'NOT', *COMPARISONS) for a in item[1:]):
                return None
        elif item[0] in ('OR', 'IF', 'ALL', *COMPARISONS):
            return None
        else:
            positive.append(item[0])
    return positive[0] if len(positive) == 1 else None
