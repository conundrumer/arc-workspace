"""Row shapes of a table, on one example.

geom_shape: the geometric shape of a set of cells in an H by W grid.
rel_shape: the relational shape of a table's rows, each row a tuple of column values.

A class is a string. The classes are mutually exclusive, and each function tests them in the order written.
"""
from collections import Counter


def components(points):
    """The 4-connected components of a set of (r, c), as lists."""
    todo = set(points)
    out = []
    while todo:
        p = todo.pop()
        comp = [p]
        stack = [p]
        while stack:
            r, c = stack.pop()
            for q in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if q in todo:
                    todo.remove(q)
                    comp.append(q)
                    stack.append(q)
        out.append(comp)
    return out


def _bbox(pts):
    rs = [p[0] for p in pts]
    cs = [p[1] for p in pts]
    return min(rs), max(rs), min(cs), max(cs)


def geom_shape(points, H, W):
    """empty, single cell, whole grid, h line, v line, h gapped, v gapped, diagonal, grid border, full rows, full cols, rectangle, ring,
    blob, blocks, lines, lattice, dots, scatter."""
    pts = set(points)
    n = len(pts)
    if n == 0:
        return 'empty'
    if n == 1:
        return 'single cell'
    if H and W and n == H * W:
        return 'whole grid'
    r0, r1, c0, c1 = _bbox(pts)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    rows = {p[0] for p in pts}
    cols = {p[1] for p in pts}
    if len(rows) == 1:
        return 'h line' if n == w else 'h gapped'
    if len(cols) == 1:
        return 'v line' if n == h else 'v gapped'
    if len({r - c for r, c in pts}) == 1 or len({r + c for r, c in pts}) == 1:
        return 'diagonal'
    if H and W:
        if n == 2 * (H + W) - 4 and all(r in (0, H - 1) or c in (0, W - 1) for r, c in pts):
            return 'grid border'
        if n == len(rows) * W:
            return 'full rows'
        if n == len(cols) * H:
            return 'full cols'
    if n == h * w:
        return 'rectangle'
    if h >= 3 and w >= 3 and n == 2 * (h + w) - 4 and all(r in (r0, r1) or c in (c0, c1) for r, c in pts):
        return 'ring'
    comps = components(pts)
    if len(comps) == 1:
        return 'blob'
    if n == len(rows) * len(cols) and len(rows) >= 2 and len(cols) >= 2 and all(len(x) == 1 for x in comps):
        return 'lattice'
    if all(len(x) == 1 for x in comps):
        return 'dots'
    filled = True
    lines = True
    for x in comps:
        a, b, e, f = _bbox(x)
        hh, ww = b - a + 1, f - e + 1
        if len(x) != hh * ww:
            filled = False
        if hh != 1 and ww != 1:
            lines = False
    if lines:
        return 'lines'
    if filled:
        return 'blocks'
    return 'scatter'


def rel_shape(rows, types):
    """rows: tuples of column values, types: a column's type per column. empty, one row, set, cross product, equivalence, symmetric, order,
    permutation, chain, one to one, function, keyed, many to many."""
    rows = list(set(rows))
    n = len(rows)
    if n == 0:
        return 'empty'
    if n == 1:
        return 'one row'
    k = len(rows[0])
    keep = [i for i in range(k) if len({r[i] for r in rows}) > 1]
    m = len(keep)
    if m <= 1:
        return 'set'
    vals = [[r[i] for r in rows] for i in keep]
    d = [len(set(v)) for v in vals]
    prod = 1
    for x in d:
        prod *= x
    if prod == n:
        return 'cross product'
    if m == 2 and str(types[keep[0]]) == str(types[keep[1]]):
        pairs = set(zip(vals[0], vals[1]))
        dom = set(vals[0]) | set(vals[1])
        sym = all((b, a) in pairs for a, b in pairs)
        refl = all((a, a) in pairs for a in dom)
        anti = all((b, a) not in pairs or a == b for a, b in pairs)
        trans = None
        if n <= 4000:
            out = {}
            for a, b in pairs:
                out.setdefault(a, set()).add(b)
            trans = all(c in out.get(a, ()) for a, b in pairs for c in out.get(b, ()))
        if refl and sym and trans:
            return 'equivalence'
        if sym and not refl:
            return 'symmetric'
        if anti and trans and any(a != b for a, b in pairs):
            mid = sum(1 for a, b in pairs if a != b)
            nv = len(dom)
            if mid * 2 >= nv * (nv - 1) and nv >= 3:
                return 'order'
        if d[0] == n and d[1] == n:
            if set(vals[0]) == set(vals[1]):
                return 'permutation'
            if set(vals[0]) & set(vals[1]):
                return 'chain'
            return 'one to one'
    nkeys = sum(1 for x in d if x == n)
    if nkeys == m:
        return 'one to one'
    if nkeys >= 2:
        return 'keyed'
    if nkeys == 1:
        return 'function'
    if m == 2:
        return 'many to many'
    for i in range(m):
        for j in range(i + 1, m):
            if len(set(zip(vals[i], vals[j]))) == n:
                return 'function'
    return 'many to many'


def modal(xs):
    """The most common class of a list, ties to the first written; None on an empty list."""
    if not xs:
        return None
    c = Counter(xs)
    best = max(c.values())
    return next(x for x in xs if c[x] == best)
