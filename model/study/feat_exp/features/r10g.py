"""Round 10, explorer g: tables that the grids do not shape.

G1 reads the column types of X: a table with no Position, Box, Offset, Ident or Color column holds no cell, object or color of
the task; its values come from the library's enumerations and numbers.
G2 reads the columns of enumerated library types (Dir, Dir8, DiagDir, Axis, Axis4, D4, C4, Sense): one that takes every value of
its domain in every example is a loop over the domain.
"""
from featlib import BOX_TYPES, feature

GRID_TYPES = BOX_TYPES | {'Ident', 'Color'}
# Number of values of each enumerated library type (the library's domains).
DOMAIN = {'Dir': 4, 'DiagDir': 4, 'Dir8': 8, 'Axis': 2, 'DiagAxis': 2, 'Axis4': 4, 'C4': 4, 'D4': 8, 'Sense': 2}


def _contexts(x):
    """{(assignment, example): set of rows} of X, the rows of every model pooled, contexts with no row left out."""
    return {k: {r for m in models for r in m} for k, models in x.examples().items() if any(models)}


@feature
def g1_grid_free(p):
    """G1 Grid free: `free` (1 when X has no Position, Box, Offset, Ident or Color column), `cellfree` (no Position, Box or
    Offset column), `scalar` (cellfree and at most one row in every example), `uniform` (the same rows in every example,
    over at least two examples).

    Needs: partial. Monotone: no (a new column can make the table grid bound). None at a Det point, where the library's
    own domains (a D4 or divisor table) are gold's tables.
    """
    if p.kind == 'Det':
        return None
    cols = [c for c in p.x.columns() if c.type != 'Example']
    if not cols:
        return None
    ctx = _contexts(p.x)
    types = {c.type for c in cols}
    cellfree = not (types & BOX_TYPES)
    sets = list(ctx.values())
    return {'free': int(not (types & GRID_TYPES)),
            'cellfree': int(cellfree),
            'scalar': int(cellfree and bool(sets) and all(len(s) <= 1 for s in sets)),
            'uniform': int(len(sets) >= 2 and all(s == sets[0] for s in sets))}


@feature
def g2_enum_full(p):
    """G2 Enumerated column over its whole domain: `full` (columns of an enumerated library type that take every value of
    their domain in every example), `enum` (columns of such a type), `share` (full over enum).

    Needs: partial. Monotone: no.
    """
    if p.kind == 'Det':
        return None
    cols = p.x.columns()
    enum = [(j, c) for j, c in enumerate(cols) if c.type in DOMAIN]
    if not enum:
        return {'full': 0, 'enum': 0, 'share': None}
    ctx = _contexts(p.x)
    if not ctx:
        return None
    full = 0
    for j, c in enum:
        if all(len({r[j] for r in rows}) == DOMAIN[c.type] for rows in ctx.values()):
            full += 1
    return {'full': full, 'enum': len(enum), 'share': full / len(enum)}
