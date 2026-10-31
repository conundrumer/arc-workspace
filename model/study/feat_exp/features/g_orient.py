"""G16 Orientation by a Dir column.

Replaces `r4l.l1_dir_orient`, `r4l.l3_toward_side`, `r1.e3_binary_relation.oriented` and `r7s.s1_dir_beam` (`blocked_*`).
`r3d.d4_order_orientation` is None on every pair and is left out. The beams of S1 read train grids and are left out.
"""
import collections as C
import itertools

from featlib import feature

GRID = ('Position', 'Box')


def _dir(v):
    return v if isinstance(v, int) and 0 <= v <= 3 else None


@feature
def g16_orient(p):
    """G16 Orientation by a Dir column. Pair keys, over pairs of Position (or Box) columns of one non-empty frame tag
    with each Dir column: `strict_cols` (the (pair, Dir) combinations where the first column's margin at the Dir value is
    smaller in every row, or larger in every row), `best` (the largest one-sided share) and `tie` (the tie share of that
    combination). Cell keys, over each Position column with each Dir column: `near`, `far`, `tie_cell` (the shares of
    rows where the margin at the Dir value is smaller than, larger than or equal to the margin at the opposite side,
    for the combination with the most one-sided share). Beam keys, over each Position or Box column with each Dir
    column: `blocked_max` (the largest share of distinct values that touch their frame at the Dir side) and
    `blocked_all` (the combinations blocked in every value). None without a Dir column or without a Position or Box column.

    Needs: partial. Monotone: partly (`strict_cols` and `blocked_all` stay under a filter; the shares do not).
    """
    x = p.x
    cols = x.columns()
    dirs = [c for c in cols if c.type == 'Dir']
    cells = [c for c in cols if c.type in GRID]
    if not dirs or not cells:
        return None
    pairs = [(a.index, b.index) for a, b in itertools.combinations(cells, 2)
             if a.type == b.type and a.frame and a.frame == b.frame]
    rows = [r for models in x.examples(tests=True).values() for m in models for r in m]
    n = C.Counter()
    lt = C.Counter()
    gt = C.Counter()
    cn = C.Counter()
    near = C.Counter()
    far = C.Counter()
    seen = C.defaultdict(set)
    for r in rows:
        for dc in dirs:
            d = _dir(r[dc.index])
            if d is None:
                continue
            for i, j in pairs:
                a, b = r[i], r[j]
                if not hasattr(a, 'margins') or not hasattr(b, 'margins'):
                    continue
                a, b = a.margins, b.margins
                n[i, j, dc.index] += 1
                lt[i, j, dc.index] += a[d] < b[d]
                gt[i, j, dc.index] += a[d] > b[d]
            for c in cells:
                v = r[c.index]
                if not hasattr(v, 'margins'):
                    continue
                m = v.margins
                seen[c.index, dc.index].add((m, d))
                if c.type == 'Position':
                    cn[c.index, dc.index] += 1
                    near[c.index, dc.index] += m[d] < m[d ^ 1]
                    far[c.index, dc.index] += m[d] > m[d ^ 1]
    out = {}
    if n:
        strict = 0
        best = (-1.0, 0.0)
        for key, total in n.items():
            s = max(lt[key], gt[key]) / total
            strict += s == 1.0
            tie = 1.0 - (lt[key] + gt[key]) / total
            if (s, -tie) > (best[0], -best[1]):
                best = (s, tie)
        out.update({'strict_cols': strict, 'best': best[0], 'tie': best[1]})
    if cn:
        key = max(cn, key=lambda c: (max(near[c], far[c]) / cn[c], near[c] / cn[c], far[c] / cn[c]))
        t = cn[key]
        out.update({'near': near[key] / t, 'far': far[key] / t, 'tie_cell': 1.0 - (near[key] + far[key]) / t})
    if seen:
        shares = [sum(m[d] == 0 for m, d in vals) / len(vals) for vals in seen.values()]
        out.update({'blocked_max': max(shares), 'blocked_all': sum(s == 1.0 for s in shares)})
    return out or None
