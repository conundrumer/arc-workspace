"""G17 A column with one value in every example.

Replaces `r4j.j3_dead_derived`, `r6p.p4_dead_number`, `r2a.a1_degenerate_cols.const_number`,
`r3c.c5_example_constant`, `r6p.p7_mode_share.flat_other` and `r2b.b3_zero_relative`.
"""
import collections as C

from featlib import BOX_TYPES, feature

LIBRARY_KINDS = ('relation', 'macro')
NOMINAL = ('Color', 'Dir', 'Dir8', 'DiagDir', 'Axis', 'C4', 'D4', 'Sense', 'Sym')


def _made(scope):
    """{(OR path, label)}: the labels that a starred site inside an OR makes and every other branch of that OR names."""
    named = C.defaultdict(lambda: C.defaultdict(set))
    for a in scope.arguments:
        if a.label is None:
            continue
        for orp, b in a.atom.branch:
            named[orp, a.label][b].add(a.binds)
    out = set()
    for (orp, label), branches in named.items():
        siblings = {b for (o, _), by in named.items() if o == orp for b in by}
        if any(True in flags for flags in branches.values()) and set(branches) >= siblings:
            out.add((orp, label))
    return out


def _origin(p, v):
    """The Variable that stands for the label v where it is made (an INIT port reads the key's labels, which the key
    clause makes)."""
    key = p.clause.key
    if key is not None and v.scope is not key and v.label in key.key_order() and not v.binders:
        return key.variables.get(v.label, v)
    return v


def _makers(p, v):
    """The sites that make the label of the Variable v."""
    v = _origin(p, v)
    made = _made(v.scope)
    return [a for a in v.occurrences if a.atom is not None and (
        a.binds or any((orp, v.label) in made for orp, _ in a.atom.branch))]


def _computed_geometry(p):
    """{index: Variable} of the X columns of type Position, Box or Offset that hold a label which a library atom makes
    at a site of such a type."""
    if p.clause is None:
        return {}
    out = {}
    for v in p.clause.x_columns.values():
        if v is None or v.column is None or v.column.index is None or v.column.type not in BOX_TYPES:
            continue
        if any(a.atom.kind in LIBRARY_KINDS and a.column_type in BOX_TYPES for a in _makers(p, v)):
            out[v.column.index] = v
    return dict(sorted(out.items()))


def _collapses(p, v, constant):
    """Whether the constant computed column that holds the Variable v collapses varying inputs, and so loses
    information. It does where a library atom that makes it takes the literal 0, or a label that is not held by a
    constant X column (`constant` says whether an X column index is one). A column whose makers take only constant
    columns is constant by construction. An Offset made from two or more different varying labels, none repeated, is
    a law (the translation between two cells that move together), not a collapse."""
    held = {w.label: w.column.index for w in p.clause.x_columns.values()
            if w is not None and w.column is not None and w.column.index is not None}
    for site in _makers(p, v):
        atom = site.atom
        if atom.kind not in LIBRARY_KINDS or site.column_type not in BOX_TYPES:
            continue
        inputs = [b for b in atom.arguments if b is not site and not b.binds]
        if any(b.label is None for b in inputs):
            return True
        varying = {b.label for b in inputs if b.label not in held or not constant(held[b.label])}
        labels = [b.label for b in inputs]
        if varying and not (v.column.type == 'Offset' and len(varying) >= 2 and len(set(labels)) == len(labels)):
            return True
    return False


@feature
def g17_constant(p):
    """G17 A column with one value in every example. A context is an example's rows in the first model. `dead_number`,
    `dead_geom`, `dead_nominal`: the Number columns, the library-computed Position, Box or Offset columns, and the
    Color, Dir and Axis columns that hold one value in every context of 2 or more rows, when there are 2 such contexts
    (a computed column counts only where it collapses varying inputs: not where every input of its makers is a
    constant column, nor for an Offset between two different varying cells, see `_collapses`);
    `dead` their sum; `share` it over the columns of those three kinds; `flat` the share of (Number or nominal column,
    context) pairs with one value; `const_share` the share of columns (not Example) that hold one value in every
    non-empty context; `single` 1 when every non-empty context has one row; `zero_offset` the share of Offset cells that
    are the zero vector. None without a non-empty context.

    Needs: partial. Monotone: partly (`dead*` yes: a constant column stays constant under a filter or an added atom;
    `share`, `flat`, `const_share`, `single`, `zero_offset` no).
    """
    x = p.x
    ctxs = [ms[0] for ms in x.examples(tests=True).values() if ms and ms[0]]
    if not ctxs:
        return None
    cols = x.columns()
    out = {}
    multi = [rows for rows in ctxs if len(rows) >= 2]
    number = [c.index for c in cols if c.type == 'Number']
    nominal = [c.index for c in cols if c.type in NOMINAL]
    geom = _computed_geometry(p)

    def one(k, rows):
        return len({r[k] for r in rows}) == 1

    def dead(idx):
        return sum(all(one(k, rows) for rows in multi) for k in idx) if len(multi) >= 2 else 0

    dn, dm = dead(number), dead(nominal)
    dg = sum(all(one(k, rows) for rows in multi) and _collapses(p, v, lambda q: all(one(q, rows) for rows in multi))
             for k, v in geom.items()) if len(multi) >= 2 else 0
    out.update({'dead_number': dn, 'dead_geom': dg, 'dead_nominal': dm, 'dead': dn + dg + dm})
    considered = len(number) + len(geom) + len(nominal)
    if considered:
        out['share'] = (dn + dg + dm) / considered
    graded = number + nominal
    if graded and multi:
        out['flat'] = sum(one(k, rows) for k in graded for rows in multi) / (len(graded) * len(multi))
    plain = [c.index for c in cols if c.type != 'Example']
    if plain:
        out['const_share'] = sum(all(one(k, rows) for rows in ctxs) for k in plain) / len(plain)
    out['single'] = float(all(len(rows) == 1 for rows in ctxs))
    offs = [c.index for c in cols if c.type == 'Offset']
    cells = [r[k] for rows in ctxs for r in rows for k in offs if hasattr(r[k], 'is_zero')]
    if cells:
        out['zero_offset'] = sum(c.is_zero() for c in cells) / len(cells)
    return out
