"""Model input layer: a generic feature library over a solver's tables. Each feature belongs to one table (its owner); a pair feature also reads an upstream table.

A feature's value is a bool, a number, or a short string (a category). Input features read the tables and the input grid; output features also read
the train output, and exist only where the example has one.

A feature's key holds no name that the program's author chose, and depends on no order the author wrote. A key names a column or another
table by its identity (identity.py): `⟨c:<column>⟩` for a column of the owner, `⟨t:<table>⟩` for another table, and `⟨t:<table>⟩.⟨c:<column>⟩`
for a column of another table. No two columns or tables of a program share an identity, so each feature has a key of its own. For each column
and each other table that a key names, `<token> describe` gives it in given terms: a column by its provenance (provenance.py), with its type,
its frame and the given columns its values come from; another table by how it stands to the owner (`parent`, or `ancestor <k>` for k queries
back) and how it is given (a component's port, a task parameter with its proposer, or a relation). The features are computed on tokens that
stand for the names, and identity_names puts the identities in their place.
"""
from bisect import bisect_left
import hashlib
import itertools
import json
import re
from collections import Counter, OrderedDict

import provenance as PV

OUTPUT_FEATURES = (' vs the changed cells', ' overlap with the changed cells', ' is the set of painted colors', ' within the output colors',
                   ' overlap with the output cells', ' agrees with the output colors, share', ' has the output size',
                   ' vs the output colors', ' vs the output foreground cells', ' is the output foreground box',
                   ' vs the output foreground', ' vs the output cells of its colors', ' color counts agree with the output, share',
                   ' vs the output foreground components')  # the features that read the train output
ORIENT = {'Dir', 'Dir8', 'DiagDir', 'Axis', 'Axis4', 'DiagAxis', 'D4', 'C4', 'Sym', 'Sense'}
NUM = {'Nat', 'Int'}
TYPE_SIZE = {'Dir': 4, 'DiagDir': 4, 'Dir8': 8, 'Axis': 2, 'DiagAxis': 2, 'Axis4': 4, 'D4': 8, 'C4': 4, 'Sense': 2}
AXIS_OF = {'DIR_T': 'V', 'DIR_B': 'V', 'DIR_L': 'H', 'DIR_R': 'H', 'DIAG_TL': 'DG', 'DIAG_BR': 'DG', 'DIAG_TR': 'AD', 'DIAG_BL': 'AD'}
OPPOSITE = {'DIR_T': 'DIR_B', 'DIR_B': 'DIR_T', 'DIR_L': 'DIR_R', 'DIR_R': 'DIR_L', 'DIAG_TL': 'DIAG_BR', 'DIAG_BR': 'DIAG_TL', 'DIAG_TR': 'DIAG_BL',
            'DIAG_BL': 'DIAG_TR'}
TURNS = {'D4_ID', 'D4_CW', 'D4_HT', 'D4_CC'}
D4_MAPS = (lambda r, c: (r, c), lambda r, c: (c, -r), lambda r, c: (-r, -c), lambda r, c: (-c, r),
           lambda r, c: (r, -c), lambda r, c: (-r, c), lambda r, c: (c, r), lambda r, c: (-c, -r))


def cell(p):
    return (p[0], p[2])


def comps(cs, diag=True):
    cs, n, seen = set(cs), 0, set()
    steps = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0) and (diag or a == 0 or b == 0)]
    for c in cs:
        if c in seen:
            continue
        n += 1
        todo = [c]
        while todo:
            x = todo.pop()
            if x in seen:
                continue
            seen.add(x)
            todo += [(x[0] + a, x[1] + b) for a, b in steps if (x[0] + a, x[1] + b) in cs]
    return n


def normalized(S):
    """A nonempty cell set moved so that its bounding box starts at (0, 0)."""
    r0, c0 = min(c[0] for c in S), min(c[1] for c in S)
    return frozenset((r - r0, c - c0) for r, c in S)


def images(S):
    """The eight images of a cell set under the symmetries of the square, each normalized."""
    return [normalized({m(r, c) for r, c in S}) for m in D4_MAPS]


def symmetry_count(S):
    """The number of the eight symmetries of the square that map a nonempty cell set onto itself, up to a move."""
    n = normalized(S)
    return sum(i == n for i in images(n))


def canon(S):
    """One form for each class of cell sets equal up to a move, a rotation or a reflection."""
    return min(tuple(sorted(i)) for i in images(S))


def enclosed_regions(S):
    """The number of 4-connected regions of cells outside a nonempty cell set that the set encloses."""
    rs, ks = [c[0] for c in S], [c[1] for c in S]
    free = {(r, k) for r in range(min(rs) - 1, max(rs) + 2) for k in range(min(ks) - 1, max(ks) + 2)} - set(S)
    return comps(free, diag=False) - 1  # the ring around the bounding box is one region, and it is not enclosed


def fills_box(S):
    rs, ks = [c[0] for c in S], [c[1] for c in S]
    return len(S) == (max(rs) - min(rs) + 1) * (max(ks) - min(ks) + 1)


def outlines_box(S):
    rs, ks = [c[0] for c in S], [c[1] for c in S]
    r0, r1, k0, k1 = min(rs), max(rs), min(ks), max(ks)
    return r1 - r0 >= 2 and k1 - k0 >= 2 and set(S) == {(r, k) for r in range(r0, r1 + 1) for k in range(k0, k1 + 1) if r in (r0, r1) or k in (k0, k1)}


def grouped(cols, rows, pi):
    """{group: set of cells} of the Position column at index pi, by the table's Ident, Color and key columns; None where it has none."""
    gcols = [j for j, (m, ty, _) in enumerate(cols) if ty in ('Ident', 'Color') or m.startswith('key.')]
    if not gcols:
        return None
    groups = {}
    for r in rows:
        groups.setdefault(tuple(str(r[j]) for j in gcols), set()).add(cell(r[pi]))
    return groups


def colored_symmetry_count(M):
    """The number of the eight symmetries of the square that map a nonempty colored cell set ({cell: color}) onto itself, up to a move."""
    def norm(m):
        r0, c0 = min(c[0] for c in m), min(c[1] for c in m)
        return frozenset(((r - r0, c - c0), x) for (r, c), x in m.items())
    n = norm(M)
    return sum(norm({mp(r, c): x for (r, c), x in M.items()}) == n for mp in D4_MAPS)


def least_period(M):
    """The least move along a row or a column, at most half the box's extent along it, that maps every cell of a colored cell set that fills
    its bounding box onto a cell of the same color, wherever both cells lie in the box; None where no such move exists."""
    rs, ks = [c[0] for c in M], [c[1] for c in M]
    r0, r1, k0, k1 = min(rs), max(rs), min(ks), max(ks)
    best = None
    for dr, dc, n in ((0, 1, k1 - k0 + 1), (1, 0, r1 - r0 + 1)):
        for k in range(1, n // 2 + 1):
            if best is not None and k >= best:
                break
            if all(M.get((r + dr * k, c + dc * k), x) == x for (r, c), x in M.items()):
                best = k
                break
    return best


def graph_shape(edges):
    """(connected components, greatest degree) of the undirected graph whose edges are the given pairs of values."""
    parent, nbrs = {}, {}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in edges:
        for x in (a, b):
            parent.setdefault(x, x)
        if a != b:
            nbrs.setdefault(a, set()).add(b)
            nbrs.setdefault(b, set()).add(a)
        parent[root(a)] = root(b)
    return len({root(x) for x in parent}), max((len(v) for v in nbrs.values()), default=0)


def full_lines(S, H, W):
    """The number of whole rows and whole columns of an H by W frame that a cell set holds."""
    rows, cols = Counter(c[0] for c in S if 0 <= c[1] < W), Counter(c[1] for c in S if 0 <= c[0] < H)
    return sum(n == W for n in rows.values()) + sum(n == H for n in cols.values())


def holes(S):
    """The cells outside a nonempty cell set that the set encloses: those that no walk of 4 steps outside the set leads to from beyond its
    bounding box."""
    rs, ks = [c[0] for c in S], [c[1] for c in S]
    r0, r1, k0, k1 = min(rs) - 1, max(rs) + 1, min(ks) - 1, max(ks) + 1
    free = {(r, k) for r in range(r0, r1 + 1) for k in range(k0, k1 + 1)} - set(S)
    todo = [c for c in free if c[0] in (r0, r1) or c[1] in (k0, k1)]
    seen = set(todo)
    while todo:
        x = todo.pop()
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            y = (x[0] + a, x[1] + b)
            if y in free and y not in seen:
                seen.add(y)
                todo.append(y)
    return free - seen


def box_cells(S):
    """The cells of the bounding box of a nonempty cell set."""
    rs, ks = [c[0] for c in S], [c[1] for c in S]
    return {(r, k) for r in range(min(rs), max(rs) + 1) for k in range(min(ks), max(ks) + 1)}


def fixes(a, b):
    """Whether, over the keys of a, equal values of a always go with equal values of b."""
    seen = {}
    return all(seen.setdefault(a[k], b[k]) == b[k] for k in a)


def setrel2(a, b):
    """How two sets of values stand to each other, with no universe."""
    if a == b:
        return 'equal'
    if not a & b:
        return 'disjoint'
    return 'subset' if a < b else 'superset' if a > b else 'overlap'


def components(cs):
    """The 8-connected components of a cell set, as sets."""
    cs, out, seen = set(cs), [], set()
    for c in cs:
        if c in seen:
            continue
        part, todo = set(), [c]
        while todo:
            x = todo.pop()
            if x in seen:
                continue
            seen.add(x)
            part.add(x)
            todo += [(x[0] + a, x[1] + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (x[0] + a, x[1] + b) in cs]
        out.append(part)
    return out


def straight(S):
    """The cells lie on one row, one column or one diagonal."""
    return len({c[0] for c in S}) == 1 or len({c[1] for c in S}) == 1 or len({c[0] - c[1] for c in S}) == 1 or len({c[0] + c[1] for c in S}) == 1


def top2(values):
    v = sorted(values, reverse=True)
    return round(v[0] / v[1], 3) if len(v) >= 2 and v[1] > 0 else None


def setrel(a, b, grid):
    if a == b:
        return 'equal'
    if not a & b:
        return 'complement' if a | b == grid else 'disjoint'
    if a < b:
        return 'subset'
    if a > b:
        return 'superset'
    return 'overlap'


def set_distance(S, U):
    """The least Chebyshev distance between a cell of S and a cell of U: 0 where they share a cell; None where one is empty, or the distance
    is above 60. Each cell of the smaller set looks at the rows of the other set in the order of their distance from it, and stops at a row
    that is no nearer than the best distance so far."""
    if len(S) > len(U):
        S, U = U, S
    if not S:
        return None
    U = set(U)
    if any(c in U for c in S):
        return 0
    rows = {}
    for r, c in U:
        rows.setdefault(r, []).append(c)
    for v in rows.values():
        v.sort()
    keys = sorted(rows)
    best = None
    for r0, c0 in S:
        i = bisect_left(keys, r0)
        lo, hi = i - 1, i
        while lo >= 0 or hi < len(keys):
            dl = r0 - keys[lo] if lo >= 0 else None
            dh = keys[hi] - r0 if hi < len(keys) else None
            if dh is None or (dl is not None and dl <= dh):
                d_row, r = dl, keys[lo]
                lo -= 1
            else:
                d_row, r = dh, keys[hi]
                hi += 1
            if best is not None and d_row >= best:
                break
            cs = rows[r]
            j = bisect_left(cs, c0)
            d = max(d_row, min(abs(cs[k] - c0) for k in (j - 1, j) if 0 <= k < len(cs)))
            if best is None or d < best:
                best = d
                if best == 1:
                    return 1
    return None if best > 60 else best


def group_distances(groups, each=False, cap=True):
    """The least Chebyshev distance between cells of two different groups ({group: set of cells}), or, with each, {group: the least distance
    from its cells to a cell of another group}: 0 where a cell is in two groups; None for fewer than two groups, and, with cap, for a
    distance above 60.
    One search from every cell at once, over the bounding box of the cells: an edge between cells nearest to different groups gives the
    distance between those groups through it, and the search stops once no edge it has not yet looked at can give less."""
    if len(groups) < 2:
        return None
    owner, near = {}, {g: None for g in groups}
    for g, cs in groups.items():
        for c in cs:
            h = owner.setdefault(c, g)
            if h != g:
                near[g] = near[h] = 0
    if not owner:
        return {g: None for g in groups} if each else None
    rs, ks = [c[0] for c in owner], [c[1] for c in owner]
    r0, r1, k0, k1 = min(rs), max(rs), min(ks), max(ks)
    dist, frontier, layer = dict.fromkeys(owner, 0), list(owner), 0
    steps = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
    while frontier:
        nxt = []
        for x in frontier:
            gx = owner[x]
            for a, b in steps:
                y = (x[0] + a, x[1] + b)
                if not (r0 <= y[0] <= r1 and k0 <= y[1] <= k1):
                    continue
                if y in dist:
                    gy = owner[y]
                    if gy != gx:
                        v = layer + dist[y] + 1
                        if near[gx] is None or v < near[gx]:
                            near[gx] = v
                        if near[gy] is None or v < near[gy]:
                            near[gy] = v
                else:
                    dist[y], owner[y] = layer + 1, gx
                    nxt.append(y)
        # an edge not yet looked at joins two cells at least layer + 1 from every group, so it gives at least 2 * layer + 3
        vals = [v for v in near.values() if v is not None]
        if each:
            if len(vals) == len(near) and max(vals) <= 2 * layer + 3:
                break
        elif vals and min(vals) <= 2 * layer + 3:
            break
        frontier, layer = nxt, layer + 1
    limit = (lambda v: None if v is None or v > 60 else v) if cap else (lambda v: v)
    if each:
        return {g: limit(v) for g, v in near.items()}
    vals = [v for v in near.values() if v is not None]
    return limit(min(vals)) if vals else None


def least_distance(groups):
    """The least Chebyshev distance between cells of two different groups ({group: set of cells}): 0 where a cell is in two; None for one group,
    and for a distance above 60."""
    if len(groups) == 2:
        return set_distance(*groups.values())
    return group_distances(groups)


def box_features(B, H, W):
    """{feature: value} of a set of boxes in an H by W grid, each box as its margins (top, bottom, left, right)."""
    f = {'distinct': len(B)}
    sides = [(H - t - b, W - l - r) for t, b, l, r in B if H - t - b > 0 and W - l - r > 0]
    if B:
        f['least margin'] = min(min(x) for x in B)
        f['edges touched max'] = max(sum(m == 0 for m in x) for x in B)
        f['edges touched min'] = min(sum(m == 0 for m in x) for x in B)
        f['centered axes max'] = max((t == b) + (l == r) for t, b, l, r in B)
    if len(B) > 1:
        f['aligned'] = len({(t, b) for t, b, l, r in B}) == 1 or len({(l, r) for t, b, l, r in B}) == 1
        f['boxes of one size'] = len(set(sides)) == 1
        spans = [(t, H - 1 - b, l, W - 1 - r) for t, b, l, r in B if t <= H - 1 - b and l <= W - 1 - r]
        if len(spans) <= 200:
            pairs = [(x, y) for x in spans for y in spans if x != y]
            f['some boxes overlap'] = any(x[0] <= y[1] and y[0] <= x[1] and x[2] <= y[3] and y[2] <= x[3] for x, y in pairs)
            f['nested boxes'] = any(y[0] <= x[0] and x[1] <= y[1] and y[2] <= x[2] and x[3] <= y[3] for x, y in pairs)
            if H * W <= 900:
                f['boxes cover the grid'] = len({(r, c) for x in spans for r in range(max(x[0], 0), min(x[1], H - 1) + 1)
                                                 for c in range(max(x[2], 0), min(x[3], W - 1) + 1)}) == H * W
        if len(spans) >= 3:
            even = False
            for lo, hi in ((0, 1), (2, 3)):
                iv = sorted({(x[lo], x[hi]) for x in spans})
                if len(iv) >= 3 and all(a[1] < b[0] for a, b in zip(iv, iv[1:])):
                    even = even or len({b[0] - a[1] for a, b in zip(iv, iv[1:])}) == 1
            f['evenly spaced along an axis'] = even
    if sides:
        f['shorter side min'] = min(min(x) for x in sides)
        f['longer side max'] = max(max(x) for x in sides)
        f['every box is square'] = all(h == w for h, w in sides)
    if len(B) == 1:
        t, b, l, r = next(iter(B))
        h, w = H - t - b, W - l - r
        f['share of the grid'] = round(h * w / (H * W), 3) if h > 0 and w > 0 else 0.0
        f['more than one cell along each axis'] = h > 1 and w > 1
        f['is the whole grid'] = (t, b, l, r) == (0, 0, 0, 0)
    return f


def bounding_box(S, H, W):
    rs, ks = [c[0] for c in S], [c[1] for c in S]
    return (min(rs), H - 1 - max(rs), min(ks), W - 1 - max(ks))


def rows_at(tab, ex):
    r = tab['rows']
    return r.get(ex, r.get('task'))


def frame_of(fr, vals, frame_size):
    """The grid frame of a Position column: its declared frame, or else the one grid whose extents every value's margins add up to."""
    if fr in frame_size:
        return fr
    for f, (H, W) in frame_size.items():
        if vals and all(v[0] + v[1] + 1 == H and v[2] + v[3] + 1 == W for v in vals):
            return f
    return None


def cellsets(tab, rows, frame_size):
    """{column: (frame, set of cells)} for the Position columns of a table in a grid frame, and for the Position and Box columns whose values
    are the cells of one frame of their own: a frame that the values imply, each value as a cell. Such a frame enters frame_size under the
    column's declared frame, or under the column's name where none is declared."""
    out = {}
    for i, (n, ty, fr) in enumerate(tab['columns']):
        vals = [r[i] for r in rows]
        f = frame_of(fr, vals, frame_size) if ty == 'Position' else None
        if f is None and ty in ('Position', 'Box') and not (ty == 'Box' and fr in frame_size) and vals:
            implied = {(v[0] + v[1] + 1, v[2] + v[3] + 1) for v in vals}
            if len(implied) == 1 and all(min(v) >= 0 for v in vals):
                f = fr or 'own frame of ' + n
                frame_size.setdefault(f, next(iter(implied)))
                if frame_size[f] != next(iter(implied)):
                    f = None
        if f:
            out[n] = (f, {cell(r[i]) for r in rows})
    return out


def boxes(tab, rows, frame_size):
    out = {}
    for i, (n, ty, fr) in enumerate(tab['columns']):
        if ty == 'Box' and fr in frame_size:
            out[n] = (fr, {tuple(r[i]) for r in rows})
    return out


def table_features(name, tab, ex, sizes, up_tabs, grids, shared=None, cache=None, dig=None):
    """{feature: value} owned by table `name` at example ex. sizes: {frame: (H, W)}; up_tabs: {upstream name: table}; grids: (input, output or None).
    shared: a cache of what the pair features compute from a table, which the tables of one example share. cache: a FeatureCache, which keeps
    the features that read no grid across examples, under dig: {table: rows_digest of its rows at ex}."""
    rows = rows_at(tab, ex)
    if rows is None:
        return {}
    key = None
    if cache is not None:
        key = (name, dig.get(name), tuple(dig.get(u) for u in up_tabs), frozenset(sizes.items()))
        hit = cache.get(key)
        if hit is not None:
            core, cs, sizes_after = hit
            f = dict(core)
            f.update(grid_features(tab, rows, cs, sizes_after, grids))
            return f
    f = {'rows': len(rows), 'empty': len(rows) == 0, 'one row': len(rows) == 1}
    cols = tab['columns']
    sizes = dict(sizes)
    cs = cellsets(tab, rows, sizes)
    for i, (n, ty, fr) in enumerate(cols):
        vals = [r[i] for r in rows]
        if ty == 'Color':
            f[n + ' distinct'] = len(set(vals))
            if cs:
                per = Counter(vals)
                f[n + ' top-two count ratio'] = top2(per.values())
        elif ty in NUM:
            f[n + ' distinct'] = len(set(vals))
            if vals:
                f[n + ' max'] = max(vals)
                f[n + ' min'] = min(vals)
                f[n + ' top-two ratio'] = top2(vals)
                f[n + ' forms a run'] = max(vals) - min(vals) + 1 == len(set(vals))
                dv = sorted(set(vals))
                if len(dv) >= 3:
                    f[n + ' in equal steps'] = len({b - a for a, b in zip(dv, dv[1:])}) == 1
                per = Counter(vals)
                f[n + ' rows per value max'] = max(per.values())
                f[n + ' rows per value min'] = min(per.values())
                if len(per) > 1:
                    f[n + ' rows per value all distinct'] = len(set(per.values())) == len(per)
        elif ty in ORIENT or ty == 'Ident':
            f[n + ' distinct'] = len(set(map(str, vals)))
            if ty in TYPE_SIZE:
                f[n + ' covers its type'] = len(set(vals)) == TYPE_SIZE[ty]
            if vals and ty in ('Dir', 'Dir8', 'DiagDir'):
                f[n + ' on one axis'] = len({AXIS_OF[v] for v in vals}) == 1
                f[n + ' includes an opposite pair'] = any(OPPOSITE[v] in set(vals) for v in vals)
            if vals and ty in ('D4', 'C4'):
                f[n + ' all turns'] = set(vals) <= TURNS
                f[n + ' includes the identity'] = 'D4_ID' in vals
            if vals and ty == 'Ident':
                per = Counter(map(str, vals))
                f['rows per %s min' % n] = min(per.values())
                f['rows per %s max' % n] = max(per.values())
                if len(per) > 1:
                    f['rows per %s all distinct' % n] = len(set(per.values())) == len(per)
                for j, (cn, cty, _) in enumerate(cols):
                    if cty == 'Color':
                        sets = {}
                        for r in rows:
                            sets.setdefault(str(r[i]), set()).add(r[j])
                        f['%s values per %s max' % (cn, n)] = max(len(x) for x in sets.values())
                        f['%s value sets per %s distinct' % (cn, n)] = len({frozenset(x) for x in sets.values()})
        elif ty == 'Offset':
            moves = {(v[0], v[2]) for v in vals}
            f[n + ' distinct'] = len(moves)
            if moves:
                lens = {max(abs(a), abs(b)) for a, b in moves}
                f[n + ' includes no move'] = (0, 0) in moves
                f[n + ' along rows or columns'] = all(a == 0 or b == 0 for a, b in moves)
                f[n + ' longest move'] = max(lens)
                f[n + ' moves of one length'] = len(lens) == 1
    for n, (fr, S) in cs.items():
        H, W = sizes[fr]
        grid = {(r, c) for r in range(H) for c in range(W)}
        f[n + ' cells'] = len(S)
        f[n + ' covers the grid'] = len(S) == H * W
        f[n + ' components'] = comps(S)
        f[n + ' on one line'] = len({c[0] for c in S}) <= 1 or len({c[1] for c in S}) <= 1
        f[n + ' touches the grid edge'] = any(c[0] in (0, H - 1) or c[1] in (0, W - 1) for c in S)
        f[n + ' outside is one region'] = comps(grid - S, diag=False) == 1
        if fr != 'input' and 'input' in sizes:
            f[n + ' frame is the input size'] = (H, W) == sizes['input']
            f[n + ' frame is square'] = H == W
            f[n + ' frame share of the input'] = round(H * W / (sizes['input'][0] * sizes['input'][1]), 3)
            Hi_, Wi_ = sizes['input']
            f[n + ' frame is a multiple of the input size'] = (H, W) != (Hi_, Wi_) and H % Hi_ == 0 and W % Wi_ == 0
            f[n + ' frame divides the input size'] = (H, W) != (Hi_, Wi_) and Hi_ % H == 0 and Wi_ % W == 0
        if S:
            f[n + ' 4-connected components'] = comps(S, diag=False)
            f[n + ' every component is a straight line'] = all(straight(p) for p in components(S))
            f[n + ' full lines'] = full_lines(S, H, W)
            f[n + ' cells per line max'] = max(max(Counter(c[0] for c in S).values()), max(Counter(c[1] for c in S).values()))
            f[n + ' fills its bounding box'] = fills_box(S)
            f[n + ' is the outline of its bounding box'] = outlines_box(S)
            f[n + ' symmetry count'] = symmetry_count(S)
            f[n + ' enclosed regions'] = enclosed_regions(S)
            rs, ks = [c[0] for c in S], [c[1] for c in S]
            f[n + ' box share of the grid'] = round((max(rs) - min(rs) + 1) * (max(ks) - min(ks) + 1) / (H * W), 3)
            for k, v in box_features({bounding_box(S, H, W)}, H, W).items():
                f['%s bounding box %s' % (n, k)] = v
        gcols = [j for j, (m, ty, _) in enumerate(cols) if ty in ('Ident', 'Color') or m.startswith('key.')]
        if gcols:
            pi = [j for j, c in enumerate(cols) if c[0] == n][0]
            groups = {}
            for r in rows:
                groups.setdefault(tuple(str(r[j]) for j in gcols), set()).add(cell(r[pi]))
            gname = 'its Ident, Color and key columns'
            f['%s least distance between groups of %s' % (n, gname)] = least_distance(groups)
            for k, v in box_features({bounding_box(g, H, W) for g in groups.values()}, H, W).items():
                f['%s bounding box per group of %s %s' % (n, gname, k)] = v
            if groups:
                sizes_ = [len(g) for g in groups.values()]
                parts = [comps(g) for g in groups.values()]
                f['%s cells per group of %s min' % (n, gname)] = min(sizes_)
                f['%s cells per group of %s max' % (n, gname)] = max(sizes_)
                if len(sizes_) > 1:
                    f['%s largest group of %s is unique' % (n, gname)] = sizes_.count(max(sizes_)) == 1
                    f['%s smallest group of %s is unique' % (n, gname)] = sizes_.count(min(sizes_)) == 1
                    if len(groups) <= 30 and sum(sizes_) <= 300:
                        f['%s distance to the nearest other group of %s, max' % (n, gname)] = max(group_distances(groups, each=True, cap=False).values())
                f['%s components per group of %s max' % (n, gname)] = max(parts)
                f['%s components per group of %s total' % (n, gname)] = sum(parts)
                gs = [g for g in groups.values() if g]
                f['%s distinct shapes per group of %s' % (n, gname)] = len({normalized(g) for g in gs})
                f['%s distinct shapes per group of %s up to rotation and reflection' % (n, gname)] = len({canon(g) for g in gs})
                f['%s fills its bounding box per group of %s' % (n, gname)] = all(fills_box(g) for g in gs)
                f['%s symmetry count per group of %s min' % (n, gname)] = min(symmetry_count(g) for g in gs)
                f['%s enclosed regions per group of %s max' % (n, gname)] = max(enclosed_regions(g) for g in gs)
                f['%s full lines per group of %s max' % (n, gname)] = max(full_lines(g, H, W) for g in gs)
                if len(gs) > 1 and sum(len(g) for g in gs) <= 900:
                    owner = {}
                    for gi_, g in enumerate(gs):
                        for c in g:
                            owner.setdefault(c, set()).add(gi_)

                    def rests(gi_, g, d):
                        return any(not (0 <= c[0] + d[0] < H and 0 <= c[1] + d[1] < W) or owner.get((c[0] + d[0], c[1] + d[1]), {gi_}) - {gi_} for c in g)
                    f['%s every group of %s rests toward one side' % (n, gname)] = any(all(rests(gi_, g, d) for gi_, g in enumerate(gs))
                                                                                      for d in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    for n, (fr, B) in boxes(tab, rows, sizes).items():
        H, W = sizes[fr]
        for k, v in box_features(B, H, W).items():
            f['%s %s' % (n, k)] = v
    # a column whose value differs from row to row
    if len(rows) > 1:
        for i, (a_, _, _) in enumerate(cols):
            f['%s is unique' % a_] = len({str(r[i]) for r in rows}) == len(rows)
    # two columns of one row: the order of two numbers, the move between two cells, a cell in a box
    if rows:
        for i, (a_, ta, fa) in enumerate(cols):
            for j, (b_, tb, fb) in enumerate(cols):
                if j <= i and not (ta == 'Position' and tb == 'Box'):
                    continue
                if ta in NUM and tb in NUM:
                    signs = {(r[i] > r[j]) - (r[i] < r[j]) for r in rows}
                    f['%s vs %s in every row' % (a_, b_)] = {frozenset({-1}): '<', frozenset({-1, 0}): '<=', frozenset({0}): '=', frozenset({0, 1}): '>=',
                                                             frozenset({1}): '>'}.get(frozenset(signs), 'mixed')
                if ta in NUM and tb in NUM and len({r[i] for r in rows}) > 1 and len({r[j] for r in rows}) > 1:
                    pairs = sorted({(r[i], r[j]) for r in rows})
                    up_ = all(p[1] <= q[1] for p, q in zip(pairs, pairs[1:]) if p[0] < q[0]) and all(p[1] == q[1] for p, q in zip(pairs, pairs[1:]) if p[0] == q[0])
                    down = all(p[1] >= q[1] for p, q in zip(pairs, pairs[1:]) if p[0] < q[0]) and all(p[1] == q[1] for p, q in zip(pairs, pairs[1:]) if p[0] == q[0])
                    f['%s as %s rises' % (b_, a_)] = 'rises' if up_ else 'falls' if down else 'neither'
                if ta == tb and (ta in ORIENT or ta in ('Ident', 'Color')):
                    eq = {str(r[i]) == str(r[j]) for r in rows}
                    f['%s equals %s' % (a_, b_)] = 'in every row' if eq == {True} else 'in no row' if eq == {False} else 'in some rows'
                if ta == tb and ta in ('Ident', 'Position', 'Color', 'Nat', 'Int'):
                    comps_, degree = graph_shape([(str(r[i]), str(r[j])) for r in rows])
                    f['%s-%s graph components' % (a_, b_)] = comps_
                    f['%s-%s graph greatest degree' % (a_, b_)] = degree
                if ta == 'Position' and tb == 'Position' and a_ in cs and b_ in cs and cs[a_][0] == cs[b_][0]:
                    moves = {(r[j][0] - r[i][0], r[j][2] - r[i][2]) for r in rows}
                    dist = [max(abs(x), abs(y)) for x, y in moves]
                    f['%s to %s moves distinct' % (a_, b_)] = len(moves)
                    f['%s to %s distance max' % (a_, b_)] = max(dist)
                    f['%s to %s distance min' % (a_, b_)] = min(dist)
                    f['%s to %s along rows or columns' % (a_, b_)] = all(x == 0 or y == 0 for x, y in moves)
                    f['%s to %s along diagonals' % (a_, b_)] = all(abs(x) == abs(y) for x, y in moves)
                if ta == 'Position' and tb == 'Position' and a_ in cs and b_ in cs and cs[a_][0] != cs[b_][0]:
                    f['%s to %s offsets distinct, across frames' % (a_, b_)] = len({(r[j][0] - r[i][0], r[j][2] - r[i][2]) for r in rows})
                elif ta == 'Position' and tb == 'Box' and a_ in cs and fb == cs[a_][0]:
                    f['%s inside %s in every row' % (a_, b_)] = all(r[i][0] >= r[j][0] and r[i][1] >= r[j][1] and r[i][2] >= r[j][2] and r[i][3] >= r[j][3]
                                                                  for r in rows)
    # the key columns fix the rest of the row: one row per key
    keys = [i for i, (a, _, _) in enumerate(cols) if a.startswith('key.')]
    if rows and keys and len(keys) < len(cols):
        seen = {}
        f['key fixes the row'] = all(seen.setdefault(tuple(str(r[i]) for i in keys), tuple(str(x) for x in r)) == tuple(str(x) for x in r) for r in rows)
    # functional dependencies: within the table's rows, one column's value fixes another's
    if rows and len(cols) > 1:
        for i, (a, _, _) in enumerate(cols):
            for j, (b, _, _) in enumerate(cols):
                if i != j:
                    seen = {}
                    f['%s fixes %s' % (a, b)] = all(seen.setdefault(str(r[i]), str(r[j])) == str(r[j]) for r in rows)
    # colored cell sets: a Position column with a Color column, where the column's cells hold one color each
    for i, (cn, ty, _) in enumerate(cols):
        if ty != 'Color' or not rows:
            continue
        per = Counter(r[i] for r in rows)
        f[cn + ' rows per value all equal'] = len(set(per.values())) == 1
        if len(per) > 1:
            f[cn + ' rows per value all distinct'] = len(set(per.values())) == len(per)
        for j, (pn, pty, _) in enumerate(cols):
            if pn in cs:
                M = {}
                for r in rows:
                    M.setdefault(cell(r[j]), set()).add(r[i])
                if all(len(x) == 1 for x in M.values()):
                    M = {c: next(iter(x)) for c, x in M.items()}
                    f['%s,%s symmetry count' % (pn, cn)] = colored_symmetry_count(M)
                    by = {}
                    for c, v in M.items():
                        by.setdefault(v, set()).add(c)
                    if 1 < len(by) <= 10:
                        hl = {v: holes(x) for v, x in by.items()}
                        f['%s,%s a color lies in the holes of another' % (pn, cn)] = any(hl[a] and by[b] <= hl[a] for a in by for b in by if a != b)
                        touch = {frozenset((M[c], M[(c[0] + a, c[1] + b)])) for c in M for a, b in ((1, 0), (0, 1))
                                 if (c[0] + a, c[1] + b) in M and M[(c[0] + a, c[1] + b)] != M[c]}
                        f['%s,%s touching color pairs' % (pn, cn)] = len(touch)
                    if fills_box(set(M)):
                        f['%s,%s least period' % (pn, cn)] = least_period(M)
        for j, (pn, pty, _) in enumerate(cols):
            if pn not in cs:
                continue
            for g, (gn, gty, _) in enumerate(cols):
                if g in (i, j) or not (gty == 'Ident' or gn.startswith('key.')):
                    continue
                cells_g, colors_g = {}, {}
                for r in rows:
                    cells_g.setdefault(str(r[g]), set()).add(cell(r[j]))
                    colors_g.setdefault(str(r[g]), set()).add(r[i])
                if len(cells_g) > 1:
                    shape = {k: normalized(v) for k, v in cells_g.items()}
                    col = {k: frozenset(v) for k, v in colors_g.items()}
                    f['%s,%s same shape, same colors, per %s' % (pn, cn, gn)] = fixes(shape, col)
                    f['%s,%s same colors, same shape, per %s' % (pn, cn, gn)] = fixes(col, shape)
    # pair features with upstream tables
    memo = shared if shared is not None else {}

    def framed(kind, un, fn):
        """fn(), which reads and may add to sizes, once for each state of sizes; the frames it adds are added again where the cache holds it."""
        key = (kind, un, frozenset(sizes.items()))
        if key not in memo:
            before = set(sizes)
            got = fn()
            memo[key] = (got, {k: v for k, v in sizes.items() if k not in before})
        got, added = memo[key]
        for k, v in added.items():
            sizes.setdefault(k, v)
        return got

    def groups_of(tname, tcols, trows, col):
        key = ('grouped', tname, col)
        if key not in memo:
            memo[key] = grouped(tcols, trows, [j for j, c in enumerate(tcols) if c[0] == col][0])
        return memo[key]

    def form(key, S, fn):
        if (key, fn) not in memo:
            memo[key, fn] = fn(S)
        return memo[key, fn]

    for un, ut in up_tabs.items():
        urows = rows_at(ut, ex)
        if urows is None:
            continue
        f['rows vs %s' % un] = '<' if len(rows) < len(urows) else '=' if len(rows) == len(urows) else '>'
        for a, (an, aty, _) in enumerate(cols):
            if aty != 'Ident' or not rows:
                continue
            mine_by = {}
            for r in rows:
                mine_by.setdefault(str(r[a]), []).append(r)
            for b, (bn, bty, _) in enumerate(ut['columns']):
                if bty != 'Ident':
                    continue
                theirs_by = {}
                for r in urows:
                    theirs_by.setdefault(str(r[b]), []).append(r)
                if set(mine_by) != set(theirs_by):
                    continue
                for c, (cn2, cty, _) in enumerate(cols):
                    if c == a or not (cty == 'Color' or cty in NUM or cty in ORIENT):
                        continue
                    for d, (dn, dty, _) in enumerate(ut['columns']):
                        if d == b or dty != cty:
                            continue
                        agree = [{str(r[c]) for r in mine_by[k]} == {str(r[d]) for r in theirs_by[k]} for k in mine_by]
                        f['%s agrees with %s.%s by %s' % (cn2, un, dn, an)] = 'for every one' if all(agree) else 'for none' if not any(agree) else 'for some'
        for i, (cn, ty, _) in enumerate(cols):
            if ty == 'Color' or ty in NUM:
                for j, (ucn, uty, _) in enumerate(ut['columns']):
                    if (uty == 'Color') == (ty == 'Color') and (uty in NUM) == (ty in NUM):
                        f['%s vs %s.%s' % (cn, un, ucn)] = setrel2({r[i] for r in rows}, {r[j] for r in urows})
            if ty in ORIENT:
                for j, (ucn, uty, _) in enumerate(ut['columns']):
                    if uty == ty:
                        f['%s orientations vs %s.%s' % (cn, un, ucn)] = setrel2({str(r[i]) for r in rows}, {str(r[j]) for r in urows})
            if ty in NUM and rows:
                top = max(r[i] for r in rows)
                f['%s max vs rows of %s' % (cn, un)] = '<' if top < len(urows) else '=' if top == len(urows) else '>'
        ucs = framed('cellsets', un, lambda: cellsets(ut, urows, sizes))
        ucols = ut['columns']
        for i, (cn, ty, _) in enumerate(cols):
            if ty in NUM and rows:
                top_ = max(r[i] for r in rows)
                for un2 in ucs:
                    theirs = groups_of(un, ucols, urows, un2)
                    if theirs:
                        f['%s max vs groups of %s.%s' % (cn, un, un2)] = '<' if top_ < len(theirs) else '=' if top_ == len(theirs) else '>'
        for j, (pn, _, _) in enumerate(cols):
            if pn not in cs:
                continue
            for i, (cn, cty, _) in enumerate(cols):
                if cty != 'Color':
                    continue
                mine_m = {}
                for r in rows:
                    mine_m.setdefault(cell(r[j]), set()).add(r[i])
                for pj, (pu, _, _) in enumerate(ucols):
                    if pu not in ucs or ucs[pu][0] != cs[pn][0]:
                        continue
                    for ci, (cu, cuty, _) in enumerate(ucols):
                        if cuty != 'Color':
                            continue
                        theirs_m = {}
                        for r in urows:
                            theirs_m.setdefault(cell(r[pj]), set()).add(r[ci])
                        shared = set(mine_m) & set(theirs_m)
                        if shared:
                            agree = [mine_m[c] == theirs_m[c] for c in shared]
                            f['%s,%s agrees with %s.%s,%s at shared cells' % (pn, cn, un, pu, cu)] = 'at every one' if all(agree) else 'at none' if not any(agree) else 'at some'
        mine_b, theirs_b = boxes(tab, rows, sizes), framed('boxes', un, lambda: boxes(ut, urows, sizes))
        for n, (fr, B) in mine_b.items():
            for un2, (ufr, UB) in theirs_b.items():
                if ufr == fr:
                    f['%s boxes vs %s.%s boxes' % (n, un, un2)] = setrel2(B, UB)
        for n, (fr, S) in cs.items():
            mine = groups_of(name, cols, rows, n)
            if not mine:
                continue
            for un2, (ufr, U) in ucs.items():
                theirs = groups_of(un, ut['columns'], urows, un2)
                if not theirs:
                    continue
                if ufr == fr:
                    f['%s groups vs %s.%s groups' % (n, un, un2)] = setrel2({frozenset(g) for g in mine.values()}, {frozenset(g) for g in theirs.values()})
                f['%s group count vs %s.%s groups' % (n, un, un2)] = '<' if len(mine) < len(theirs) else '=' if len(mine) == len(theirs) else '>'
                f['%s group shapes vs %s.%s group shapes' % (n, un, un2)] = setrel2({normalized(g) for g in mine.values() if g}, {normalized(g) for g in theirs.values() if g})
        for n, (fr, S) in cs.items():
            for un2, (ufr, U) in ucs.items():
                if S and U:
                    alike = len(S) == len(U)
                    f['%s same shape as %s.%s' % (n, un, un2)] = alike and form((name, n), S, normalized) == form((un, un2), U, normalized)
                    f['%s same shape up to rotation and reflection as %s.%s' % (n, un, un2)] = alike and form((name, n), S, canon) == form((un, un2), U, canon)
        for n, (fr, S) in cs.items():
            H, W = sizes[fr]
            grid = {(r, c) for r in range(H) for c in range(W)}
            for un2, (ufr, U) in ucs.items():
                if ufr == fr:
                    f['%s vs %s.%s' % (n, un, un2)] = setrel(S, U, grid)
                    f['%s cells vs %s.%s cells' % (n, un, un2)] = '<' if len(S) < len(U) else '=' if len(S) == len(U) else '>'
                    if U:
                        f['%s vs the holes of %s.%s' % (n, un, un2)] = setrel(S, form((un, un2), U, holes), grid)
                        f['%s vs the box of %s.%s' % (n, un, un2)] = setrel(S, form((un, un2), U, box_cells), grid)
                    if S and U:
                        rs, ks, urs, uks = {c[0] for c in S}, {c[1] for c in S}, {c[0] for c in U}, {c[1] for c in U}
                        f['%s shares rows or columns with %s.%s' % (n, un, un2)] = (min(rs) <= max(urs) and min(urs) <= max(rs)) or (min(ks) <= max(uks) and min(uks) <= max(ks))
                        if len(S) <= 300 and len(U) <= 300:
                            f['%s least distance to %s.%s' % (n, un, un2)] = least_distance({0: S, 1: U})
                    if S and S <= U:
                        rim = [c for c in S if any((c[0] + a, c[1] + b) not in U for a, b in ((-1, 0), (1, 0), (0, -1), (0, 1)))]
                        f['%s on the boundary of %s.%s, share' % (n, un, un2)] = round(len(rim) / len(S), 3)
                    if S:
                        nb = sum((c[0] + a, c[1] + b) in U for c in S for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0))
                        f['%s neighbors in %s.%s, mean' % (n, un, un2)] = round(nb / len(S), 3)
            for un2, (ufr, B) in boxes(ut, urows, sizes).items():
                if ufr == fr and len(B) > 1 and S:
                    spans = [(t, H - 1 - b, l, W - 1 - r) for t, b, l, r in B]
                    f['%s inside the boxes of %s.%s' % (n, un, un2)] = all(any(r0 <= c[0] <= r1 and c0 <= c[1] <= c1 for r0, r1, c0, c1 in spans) for c in S)
                if ufr != fr or len(B) != 1:
                    continue
                t, b, l, r = next(iter(B))
                r0, r1, c0, c1 = t, H - 1 - b, l, W - 1 - r
                inside = [c for c in S if r0 <= c[0] <= r1 and c0 <= c[1] <= c1]
                f['%s inside %s.%s' % (n, un, un2)] = len(inside) == len(S)
                edge = [c for c in S if c in inside and (c[0] in (r0, r1) or c[1] in (c0, c1))]
                f['%s on the border of %s.%s, share' % (n, un, un2)] = round(len(edge) / len(S), 3) if S else None
                if len(S) == 1:
                    (x, y), = S
                    offs = []
                    if y in (c0, c1) and r0 <= x <= r1:
                        offs.append(abs(x - (r0 + r1) / 2))
                    if x in (r0, r1) and c0 <= y <= c1:
                        offs.append(abs(y - (c0 + c1) / 2))
                    f['%s distance from the middle of an edge of %s.%s' % (n, un, un2)] = min(offs) if offs else None
    if key is not None:
        cache.put(key, (dict(f), cs, dict(sizes)))
    f.update(grid_features(tab, rows, cs, sizes, grids))
    return f


def grid_features(tab, rows, cs, sizes, grids):
    """{feature: value} of a table's rows at an example that read the example's grids: the input grid, and the train output where there is one.
    cs and sizes: the table's cell sets and frames, as table_features gives them."""
    f = {}
    cols = tab['columns']
    gi = grids[0]
    incount = Counter(x for row in gi for x in row) if gi is not None else Counter()
    if gi is not None:
        for n, (fr, S) in cs.items():
            if S and fr == 'input':
                H, W = sizes[fr]
                under = Counter(gi[c[0]][c[1]] for c in S if 0 <= c[0] < H and 0 <= c[1] < W)
                f[n + ' input colors distinct'] = len(under)
                f[n + ' is a union of input colors'] = all(incount[k] == m for k, m in under.items())
    # colors against the input grid
    if gi is not None and incount:
        top, low = max(incount.values()), min(incount.values())
        Hi, Wi = len(gi), len(gi[0])
        for i, (cn, ty, _) in enumerate(cols):
            if ty != 'Color':
                continue
            colors = {r[i] for r in rows}
            f[cn + ' within the input colors'] = colors <= set(incount)
            f[cn + ' vs the input colors'] = setrel2(colors, set(incount))
            f[cn + ' includes the commonest input color'] = any(incount[k] == top for k in colors)
            f[cn + ' includes the rarest input color'] = any(incount[k] == low for k in colors)
            for j, (pn, pty, _) in enumerate(cols):
                if pn in cs and sizes.get(cs[pn][0]) == (Hi, Wi) and rows:
                    agree = sum(0 <= r[j][0] < Hi and 0 <= r[j][2] < Wi and gi[r[j][0]][r[j][2]] == r[i] for r in rows)
                    f['%s,%s agrees with the input colors, share' % (pn, cn)] = round(agree / len(rows), 3)
    if gi is not None and incount:
        itops = [k for k, m in incount.items() if m == max(incount.values())]
        if len(itops) == 1:
            Hi, Wi = len(gi), len(gi[0])
            ifg = {(r, c) for r in range(Hi) for c in range(Wi) if gi[r][c] != itops[0]}
            for n, (fr, S) in cs.items():
                if fr == 'input':
                    f[n + ' vs the input foreground'] = setrel(S, ifg, {(r, c) for r in range(Hi) for c in range(Wi)})
    if gi is not None:
        longer, shorter = max(len(gi), len(gi[0])), min(len(gi), len(gi[0]))
        cmp = lambda x, y: '<' if x < y else '=' if x == y else '>'
        for i, (n, ty, _) in enumerate(cols):
            if ty in NUM and rows:
                top = max(r[i] for r in rows)
                f[n + ' max vs the longer side of the input'] = cmp(top, longer)
                f[n + ' max vs the shorter side of the input'] = cmp(top, shorter)
                f[n + ' max vs the input color count'] = cmp(top, len(incount))
    # output features
    gi, go = grids
    if go is not None:
        same = len(gi) == len(go) and len(gi[0]) == len(go[0])
        ch = {(r, c) for r in range(len(go)) for c in range(len(go[0])) if same and gi[r][c] != go[r][c]}
        painted = {go[r][c] for r, c in ch}
        outcells = {(r, c): go[r][c] for r in range(len(go)) for c in range(len(go[0]))}
        for n, (fr, S) in cs.items():
            if fr == 'input' and same:
                f[n + ' vs the changed cells'] = setrel(S, ch, {(r, c) for r in range(len(gi)) for c in range(len(gi[0]))})
                f[n + ' overlap with the changed cells'] = round(len(S & ch) / len(S | ch), 3) if S | ch else 1.0
        Ho, Wo = len(go), len(go[0])
        ocount = Counter(v for row in go for v in row)
        tops = [c for c, m in ocount.items() if m == max(ocount.values())]
        if len(tops) == 1:
            fg = {(r, c) for r in range(Ho) for c in range(Wo) if go[r][c] != tops[0]}
            fg_parts = comps(fg) if fg else 0
            for n, (fr, S) in cs.items():
                f[n + ' cells vs the output foreground cells'] = '<' if len(S) < len(fg) else '=' if len(S) == len(fg) else '>'
                if S and fg and (fr == 'output' or (fr == 'input' and same)):
                    f[n + ' bounding box is the output foreground box'] = bounding_box(S, Ho, Wo) == bounding_box(fg, Ho, Wo)
                if fr == 'output' or (fr == 'input' and same):
                    f[n + ' vs the output foreground'] = setrel(S, fg, {(r, c) for r in range(Ho) for c in range(Wo)})
                pi = [j for j, c in enumerate(cols) if c[0] == n][0]
                groups = grouped(cols, rows, pi)
                if groups:
                    gname = 'its Ident, Color and key columns'
                    f['%s groups of %s vs the output foreground components' % (n, gname)] = '<' if len(groups) < fg_parts else '=' if len(groups) == fg_parts else '>'
        for n, (fr, S) in cs.items():
            if S and fr in sizes:
                rs, ks = [c[0] for c in S], [c[1] for c in S]
                f[n + ' bounding box has the output size'] = (max(rs) - min(rs) + 1, max(ks) - min(ks) + 1) == (Ho, Wo)
        for n, (fr, B) in boxes(tab, rows, sizes).items():
            H, W = sizes[fr]
            f[n + ' some box has the output size'] = any((H - t - b, W - l - r) == (Ho, Wo) for t, b, l, r in B)
        ci = [i for i, (n, ty, fr) in enumerate(cols) if ty == 'Color']
        for i in ci:
            cn = cols[i][0]
            for n, (fr, S) in cs.items():
                if rows and (fr == 'output' or (fr == 'input' and same)):
                    pi = [j for j, c in enumerate(cols) if c[0] == n][0]
                    agree = sum(0 <= r[pi][0] < Ho and 0 <= r[pi][2] < Wo and go[r[pi][0]][r[pi][2]] == r[i] for r in rows)
                    f['%s,%s agrees with the output colors, share' % (n, cn)] = round(agree / len(rows), 3)
            colors = {r[i] for r in rows}
            for n, (fr, S) in cs.items():
                if rows and (fr == 'output' or (fr == 'input' and same)):
                    pi = [j for j, c in enumerate(cols) if c[0] == n][0]
                    grid_o = {(r, c) for r in range(Ho) for c in range(Wo)}
                    f['%s,%s vs the output cells of its colors' % (n, cn)] = setrel(S, {x for x in grid_o if go[x[0]][x[1]] in colors}, grid_o)
                    per = Counter(v for _, v in {(cell(r[pi]), r[i]) for r in rows})
                    f['%s,%s color counts agree with the output, share' % (n, cn)] = round(sum(per[v] == ocount[v] for v in per) / len(per), 3)
            if ch:
                f[cn + ' is the set of painted colors'] = colors == painted
            f[cn + ' within the output colors'] = colors <= set(outcells.values())
            f[cn + ' vs the output colors'] = setrel2(colors, set(outcells.values()))
            for n, (fr, S) in cs.items():
                if fr == 'output' or (fr == 'input' and not same):
                    pi = [j for j, c in enumerate(cols) if c[0] == n][0]
                    pairs = {(cell(r[pi]), r[i]) for r in rows}
                    want = set(outcells.items())
                    f['%s,%s overlap with the output cells' % (n, cn)] = round(len(pairs & want) / len(pairs | want), 3) if pairs | want else 1.0
    return f


MAX_MATCHES = 5000  # column matches tried per pair of tables
STRUCTURE = ('duplicate of a relation it reads', 'projection of a relation it reads', 'functional extension of a relation it reads',
             'Cartesian product', 'degenerate', 'selectivity')  # the features of structure_features


def row_set(rows):
    return {tuple(json.dumps(v) for v in r) for r in rows}


def column_matches(cand):
    """The injective choices of one candidate per position, at most MAX_MATCHES of them."""
    n = 0
    for m in itertools.product(*cand):
        if len(set(m)) == len(m):
            yield m
            n += 1
            if n >= MAX_MATCHES:
                return


def cartesian(R, k):
    """Whether the k columns of rows R split into two groups, each with two or more distinct rows, whose product R is."""
    if not 2 <= k <= 10:
        return False
    for a in range(1, 2 ** (k - 1)):
        A = [i for i in range(k) if a >> i & 1]
        B = [i for i in range(k) if not a >> i & 1]
        pa, pb = {tuple(r[i] for i in A) for r in R}, {tuple(r[i] for i in B) for r in R}
        if len(pa) >= 2 and len(pb) >= 2 and len(pa) * len(pb) == len(R):
            return True
    return False


def restructuring(R, k, U, ku):
    """How rows R of k columns stand to rows U of ku columns, under a match of columns with equal sets of values: 'duplicate' (the same
    rows), 'projection' (U's rows on some of its columns), 'functional extension' (each row of U extends to exactly one row of R), or None."""
    vt = [{r[i] for r in R} for i in range(k)]
    vu = [{u[j] for u in U} for j in range(ku)]
    if k <= ku:
        cand = [[j for j in range(ku) if vu[j] == vt[i]] for i in range(k)]
        if all(cand) and any({tuple(u[j] for j in m) for u in U} == R for m in column_matches(cand)):
            return 'duplicate' if k == ku else 'projection'
    elif len(R) == len(U):
        cand = [[i for i in range(k) if vt[i] == vu[j]] for j in range(ku)]
        if all(cand) and any({tuple(r[i] for i in m) for r in R} == U for m in column_matches(cand)):
            return 'functional extension'
    return None


def structure_features(R, k, upstream, parents):
    """{feature: value} of how rows R of k columns stand to the relations upstream of them. upstream: [(rows, columns)] of every relation
    upstream of the table, and of the input grid; parents: [rows] of each relation the table's form reads directly, the input grid
    included where the form reads it."""
    kinds = set()
    if R:
        for U, ku in upstream:
            if U:
                x = restructuring(R, k, U, ku)
                if x:
                    kinds.add(x)
    f = {'duplicate of a relation it reads': 'duplicate' in kinds, 'projection of a relation it reads': 'projection' in kinds,
         'functional extension of a relation it reads': 'functional extension' in kinds, 'Cartesian product': bool(R) and cartesian(R, k)}
    f['degenerate'] = not R or f['duplicate of a relation it reads'] or f['projection of a relation it reads'] or f['Cartesian product']
    largest = max(parents, default=0)
    f['selectivity'] = round(len(R) / largest, 3) if largest else None
    return f


def rows_digest(rows):
    """A digest of a table's rows at an example, as they stand, for FeatureCache keys."""
    return None if rows is None else hashlib.blake2b(json.dumps(rows).encode(), digest_size=16).digest()


class FeatureCache:
    """The features of a table that read no grid, under the state of its rows, its upstream tables' rows and the frames, so that a variant that
    leaves a table and every table upstream of it as they were takes them from here. Holds the most recently used `size` states."""

    def __init__(self, size=1000):
        self.size, self.held, self.hits, self.misses = size, OrderedDict(), 0, 0

    def get(self, key):
        v = self.held.get(key)
        if v is None:
            self.misses += 1
        else:
            self.hits += 1
            self.held.move_to_end(key)
        return v

    def put(self, key, value):
        self.held[key] = value
        if len(self.held) > self.size:
            self.held.popitem(last=False)


TABLE_TOKEN = re.compile('\u27e6T([^\u27e7]*)\u27e7')
COLUMN_TOKEN = re.compile('\u27e6C([^\u27e7#]*)#(\\d+)\u27e7')


def table_token(name):
    return '\u27e6T%s\u27e7' % name


def column_token(name, i, col):
    """The token of column i of table `name`; a key column keeps its `key.` prefix, which the features read."""
    return ('key.' if col.startswith('key.') else '') + '\u27e6C%s#%d\u27e7' % (name, i)


def tokened(name, tab):
    """The table with each column named by its token."""
    return dict(tab, columns=[(column_token(name, i, n), ty, fr) for i, (n, ty, fr) in enumerate(tab['columns'])])


def hops(graph, owner, other):
    """The number of queries from the owner back to the other table, or None where it is not upstream."""
    node = lambda x: x.split('.')[0] if x.startswith('&') else x
    a, b = node(owner), node(other)
    seen, layer, d = {a}, {a}, 0
    while layer:
        d += 1
        layer = {y for x in layer for y in graph.get(x, ()) if y not in seen}
        if b in layer:
            return d
        seen |= layer
    return None


KEY_COLUMN_TOKEN = re.compile('(?:key\\.)?' + COLUMN_TOKEN.pattern)  # a column token with the `key.` that column_token puts before it


class SharedIdentity(ValueError):
    """Two tables of one program with one identity, which give one key two values."""


def column_description(name, i, T, prov):
    """The column's name in given terms: its provenance's, or its type and frame where prov gives none."""
    p = prov.get(name)
    if p and i < len(p['describe']):
        return p['describe'][i]
    _, ty, fr = T[name]['columns'][i]
    ft = PV.frame_text(fr)
    return '{%s%s}' % (ty, ' ' + ft if ft else '')


def table_description(owner, other, graph, prov):
    """(queries back, how the table stands to the owner and how it is given), as the module's docstring gives."""
    d = hops(graph, owner, other)
    where = 'parent' if d == 1 else 'ancestor %d' % d if d else 'table'
    return d, '[%s %s]' % (where, prov.get(other, {}).get('given', 'relation'))


def identity_names(feats, owner, T, graph, prov):
    """feats with each token in its key replaced by its identity, with `<token> describe` for each column of the owner and each table and
    column that a key names, as the module's docstring gives; prov: provenance.provenance of the program. A key that two tables of one
    identity give two values raises SharedIdentity."""
    ids, memo = prov.ids, prov.memo
    out, tables, columns = {}, {}, {}
    for k, v in feats.items():
        hit = memo.get((owner, k))
        if hit is None:
            named = [m[1] for m in TABLE_TOKEN.finditer(k)], [(m[1], int(m[2])) for m in COLUMN_TOKEN.finditer(k)]
            nk = KEY_COLUMN_TOKEN.sub(lambda m: ids.column_token(m[1], int(m[2])), TABLE_TOKEN.sub(lambda m: ids.table_token(m[1]), k))
            hit = memo[owner, k] = (nk, named)
        nk, (ts, cs) = hit
        if nk in out and repr(out[nk]) != repr(v):
            raise SharedIdentity('%s: %s holds %r and %r' % (owner, nk, out[nk], v))
        out[nk] = v
        for t in ts:
            tables.setdefault(t, None)
        for c in cs:
            columns.setdefault(c, None)
    for i in range(len(T[owner]['columns'])):
        columns.setdefault((owner, i), None)
    for (name, i) in columns:
        tok = ids.column_token(name, i)
        if name != owner:
            tok = '%s.%s' % (ids.table_token(name), tok)
            tables.setdefault(name, None)
        out[tok + ' describe'] = column_description(name, i, T, prov)
    nearest = {}
    for name in tables:
        d, text = table_description(owner, name, graph, prov)
        tok = ids.table_token(name)
        if tok not in nearest or (d or 10 ** 9) < (nearest[tok][0] or 10 ** 9):
            nearest[tok] = (d, text)
    for tok, (_, text) in nearest.items():
        out[tok + ' describe'] = text
    return out


def all_features(T, ex, task_json, graph, upstream, grids_of, cache=None, reads=None, prov=None):
    """{(owner, feature): value} at example ex, for every table of T. cache: a FeatureCache that the calls of one task share. reads:
    engine.table_reads of the program, for the relations each form reads directly; without it, selectivity reads every table of each
    relation or instance that the graph gives, and not the input grid. prov: the Solver's provenance, which gives the identities and the
    descriptions of the tables and the columns."""
    if prov is None:
        raise ValueError('all_features needs the provenance of the program, which gives the identities of its tables and columns')
    gi, go = grids_of(task_json, ex)
    sizes = {'input': (len(gi), len(gi[0]))}
    if go is not None:
        sizes['output'] = (len(go), len(go[0]))
    out, shared, sets, toks = {}, {}, {}, {}
    dig = {n: rows_digest(rows_at(t, ex)) for n, t in T.items() if n not in ('ex_input', 'ex_output')} if cache is not None else None
    dig_t = None if dig is None else {table_token(n): d for n, d in dig.items()}
    tok = lambda n: toks[n] if n in toks else toks.setdefault(n, tokened(n, T[n]))
    for name, tab in T.items():
        if name in ('ex_input', 'ex_output'):
            continue
        ups = upstream(graph, name)
        up_tabs = {u: t for u, t in T.items() if u.split('.')[0] in ups}
        feats = table_features(table_token(name), tok(name), ex, sizes, {table_token(u): tok(u) for u in up_tabs}, (gi, go), shared, cache, dig_t)
        feats.update(structure_of(name, tab, ex, T, graph, up_tabs, gi, reads, sets, cache, dig))
        p = prov.get(name)
        if p:
            for i, cf in enumerate(p['columns']):
                ct = column_token(name, i, tab['columns'][i][0])
                for k, v in cf.items():
                    feats['%s %s' % (ct, k)] = v
            for i, j, k, v in p.get('pairs', ()):
                feats['%s %s %s' % (column_token(name, i, tab['columns'][i][0]), k, column_token(name, j, tab['columns'][j][0]))] = v
            feats.update(p['table'])
        for k, v in identity_names(feats, name, T, graph, prov).items():
            out[(name, k)] = v
    return out


def base_features(task_json, ex, grids_of):
    """{(base table, feature): value} at example ex: the features of the input grid, and where the example has a train output, of the output
    grid and of the changed cells (the output's cells whose color differs from the input's at that place, where the two have one size). Each
    is a table of a Position and a Color column, which keep the lib's names (input's `P` and `Col`), so the keys name no program's table.
    The input grid's features include those that read the train output, where there is one."""
    gi, go = grids_of(task_json, ex)
    hi, wi = len(gi), len(gi[0])

    def table(g, frame, keep=lambda p, c: True):
        H, W = len(g), len(g[0])
        rows = [[[r, H - 1 - r, c, W - 1 - c], g[r][c]] for r in range(H) for c in range(W) if keep((r, c), g[r][c])]
        return {'columns': [[COLUMN_P, 'Position', frame], [COLUMN_COL, 'Color', frame]], 'rows': {ex: rows}}

    sizes = {'input': (hi, wi)}
    if go is not None:
        sizes['output'] = (len(go), len(go[0]))
    out = {('input', k): v for k, v in table_features('input', table(gi, 'input'), ex, dict(sizes), {}, (gi, go)).items()}
    if go is not None:
        out.update({('output', k): v for k, v in table_features('output', table(go, 'output'), ex, dict(sizes), {}, (gi, go)).items()})
        if (len(go), len(go[0])) == (hi, wi):
            ch = table(go, 'output', lambda p, c: gi[p[0]][p[1]] != c)
            out.update({('changed', k): v for k, v in table_features('changed', ch, ex, dict(sizes), {}, (gi, go)).items()})
    return out


COLUMN_P, COLUMN_COL = '⟨c:P⟩', '⟨c:Col⟩'


def structure_of(name, tab, ex, T, graph, up_tabs, gi, reads, sets, cache, dig):
    """structure_features of table `name` at ex, through the cache where one is given. sets: {table: row_set at ex}, which the tables of one
    example share."""
    rows = rows_at(tab, ex)
    if rows is None:
        return {}
    node = name.split('.')[0]
    if reads is not None:
        direct = reads.get(node, set())
        par = [u for u in T if u in direct and u != name] + (['input'] if 'input' in direct else [])
    else:
        direct = graph.get(node, set())
        par = [u for u in T if u.split('.')[0] in direct and u != name]
    up = [u for u in up_tabs if u != name] + ['input']
    key = None
    if cache is not None:
        key = ('structure', name, dig.get(name), tuple((u, dig.get(u)) for u in up), tuple((u, dig.get(u)) for u in par))
        hit = cache.get(key)
        if hit is not None:
            return dict(hit)

    def set_of(u):
        if u not in sets:
            if u == 'input':
                H, W = len(gi), len(gi[0])
                sets[u] = (row_set([[[r, H - 1 - r, c, W - 1 - c], gi[r][c]] for r in range(H) for c in range(W)]), 2)
            else:
                ur = rows_at(T[u], ex)
                sets[u] = (None if ur is None else row_set(ur), len(T[u]['columns']))
        return sets[u]
    R, k = set_of(name)
    f = structure_features(R, k, [set_of(u) for u in up if set_of(u)[0] is not None],
                           [len(gi) * len(gi[0]) if u == 'input' else len(set_of(u)[0]) for u in par if set_of(u)[0] is not None])
    if key is not None:
        cache.put(key, dict(f))
    return f
