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

import across as AX
import assignments as AS
import inputs as IN
import vocabulary as LB
import dependencies  # noqa: F401
import outputs  # noqa: F401
import tables  # noqa: F401
import upstream  # noqa: F401
from grammar import SCHEMAS, VERSION, tails
if VERSION > 1:
    import typed  # noqa: F401
import maps as MP
import progress as PR
import provenance as PV
import relations as RL
import roles as RO
import values as VL

OUTPUT_FEATURES = tails(SCHEMAS, lambda reads: 'output' in reads) + PR.WITH_OUTPUT + PR.WITH_BOTH  # the features that read the train output
INPUT_CLAIMS = tails(LB.OWN_STAGE.rules + LB.BASE_STAGE.rules, lambda reads: reads == {'input'})  # the claims about the input grid that a table may be the first to hold
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
        f['proportion of the grid'] = round(h * w / (H * W), 3) if h > 0 and w > 0 else 0.0
        f['more than one cell along each axis'] = h > 1 and w > 1
        f['is the whole grid'] = (t, b, l, r) == (0, 0, 0, 0)
    return f


def bounding_box(S, H, W):
    rs, ks = [c[0] for c in S], [c[1] for c in S]
    return (min(rs), H - 1 - max(rs), min(ks), W - 1 - max(ks))


def rows_at(tab, ex):
    r = tab['rows']
    return r.get(ex, r.get('task'))


def view_at(tab, ex):
    """(row count, [(columns, rows)]) of a table whose rows at ex are a product of parts over the engine's projection cap, or None."""
    counts = tab.get('counts', {})
    at = ex if ex in counts else 'task' if 'task' in counts else None
    return None if at is None else (counts[at], tab['views'][at])


def columns_at(tab, ex, columns):
    """The rows of the columns at the given places of a table at ex: from its rows, or the product of what its parts give of them. None where the
    table gives neither."""
    rows = rows_at(tab, ex)
    if rows is not None:
        return [[r[c] for c in columns] for r in rows]
    held = view_at(tab, ex)
    if held is None:
        return None
    out = [{}]
    for cols, part in held[1]:
        here = [c for c in columns if c in cols]
        if here:
            at = [cols.index(c) for c in here]
            values = {json.dumps([r[a] for a in at]): [r[a] for a in at] for r in part}.values()
            out = [dict(row, **dict(zip(here, value))) for row in out for value in values]
    return [[row[c] for c in columns] for row in out] if all(c in out[0] for c in columns) else []


# What a feature reads of a whole table beside one part's columns: the rows that repeat a value, and the grouping by all of its Ident, Color and
# key columns. A part's rows answer a feature that is a function of the set of its columns' values, and no other.
WHOLE_TABLE = ('rows', 'empty', 'one row', 'key determines the row')
WHOLE_TABLE_ENDS = (' top-two count ratio', ' top-two ratio', ' rows per value max', ' rows per value min', ' rows per value all distinct',
                    ' rows per value all equal', ' is unique', ' agrees with the input colors, proportion', ' agrees with the output colors, proportion',
                    ' rows per value agree with the output color counts, proportion')
WHOLE_TABLE_STARTS = ('rows per ', 'rows vs ')
WHOLE_TABLE_HOLDS = ('its Ident, Color and key columns', ' groups vs ', ' group count vs ', ' group shapes vs ')


def whole_table(key):
    return key in WHOLE_TABLE or key.endswith(WHOLE_TABLE_ENDS) or key.startswith(WHOLE_TABLE_STARTS) or any(x in key for x in WHOLE_TABLE_HOLDS)


def row_count(tab, ex):
    """The count of a table's rows at ex, or None where it gives neither its rows nor their count."""
    rows = rows_at(tab, ex)
    if rows is not None:
        return len(rows)
    held = view_at(tab, ex)
    return None if held is None else held[0]


def view_features(name, tab, ex, sizes, up_tabs, grids):
    """{feature: value} of a table whose rows at ex are a product of parts: its row count, and the features of each part's rows with the other
    columns absent, without those that read the whole table."""
    held = view_at(tab, ex)
    if held is None:
        return {}
    count, views = held
    f = {'rows': count, 'empty': count == 0, 'one row': count == 1}
    for columns, rows in views:
        part = dict(tab, columns=[tab['columns'][c] for c in columns], rows={ex: rows})
        del part['counts'], part['views']
        f.update({k: v for k, v in table_features(name, part, ex, sizes, up_tabs, grids).items() if not whole_table(k)})
    for un, ut in up_tabs.items():
        theirs = row_count(ut, ex)
        if theirs is not None:
            f['rows vs %s' % un] = '<' if count < theirs else '=' if count == theirs else '>'
    return f


def frame_of(fr, vals, frame_size):
    """The grid frame of a Position column: its declared frame where every value is a cell of it, or else the one grid whose extents every value's
    margins add up to. A column of values of several extents, such as the rows and the columns of a grid, is a cell set of no frame."""
    fits = lambda H, W: all(v[0] + v[1] + 1 == H and v[2] + v[3] + 1 == W for v in vals)
    if fr in frame_size and fits(*frame_size[fr]):
        return fr
    for f, (H, W) in frame_size.items():
        if vals and fits(H, W):
            return f
    return None


def cellsets(tab, rows, frame_size):
    """{column: (frame, set of cells)} for the Position columns of a table in a grid frame, and for the Position and Box columns whose values
    are the cells of one frame of their own: a frame that the values imply, each value as a cell. Such a frame enters frame_size under the
    column's declared frame, or under the column's name where none is declared."""
    out = {}
    columns = list(enumerate(tab['columns']))
    # A frame that no grid gives takes its extents from the first column that declares it, so the columns go in an order of their own values.
    if sum(ty in ('Position', 'Box') and fr not in frame_size for _, (_, ty, fr) in columns) > 1:
        rank = {'Position': 0, 'Box': 1}
        columns.sort(key=lambda c: (rank.get(c[1][1], 2), sorted(tuple(r[c[0]]) for r in rows) if c[1][1] in rank else []))
    for i, (n, ty, fr) in columns:
        vals = [r[i] for r in rows]
        f = frame_of(fr, vals, frame_size) if ty == 'Position' else None
        if f is None and ty in ('Position', 'Box') and not (ty == 'Box' and fr in frame_size) and vals:
            implied = {(v[0] + v[1] + 1, v[2] + v[3] + 1) for v in vals}
            if len(implied) == 1 and all(min(v) >= 0 for v in vals):
                f = 'own frame of ' + n if not fr or fr in frame_size else fr
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
        return view_features(name, tab, ex, sizes, up_tabs, grids)
    key = None
    if cache is not None:
        aliases = tuple(json.dumps(t.get('ident_values', {}), sort_keys=True) for t in [tab, *up_tabs.values()])
        key = (name, dig.get(name), tuple(dig.get(u) for u in up_tabs), frozenset(sizes.items()), aliases)
        hit = cache.get(key)
        if hit is not None:
            core, cs, sizes_after = hit
            f = dict(core)
            f.update(grid_features(tab, rows, cs, sizes_after, grids))
            return f
    cols = tab['columns']
    sizes = dict(sizes)
    cs = cellsets(tab, rows, sizes)
    f = LB.TABLE_STAGE.run(LB.Context(tab, rows, ex, None, None, sizes, cs))
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

    c = LB.Context(tab, rows, ex, None, None, sizes, cs, up_tabs=up_tabs)
    c.shared, c.name = memo, name
    for un, ut in up_tabs.items():
        urows = rows_at(ut, ex)
        if urows is None:
            c.views.append(LB.View(un, ut, None, row_count(ut, ex), None, None, None))
            continue
        ucs = framed('cellsets', un, lambda: cellsets(ut, urows, sizes))
        c.views.append(LB.View(un, ut, urows, row_count(ut, ex), ucs, framed('boxes', un, lambda: boxes(ut, urows, sizes)), boxes(tab, rows, sizes)))
    LB.UPSTREAM_STAGE.run(c, f)
    if key is not None:
        cache.put(key, (dict(f), cs, dict(sizes)))
    f.update(grid_features(tab, rows, cs, sizes, grids))
    return f


def grid_features(tab, rows, cs, sizes, grids):
    """{feature: value} of a table's rows at an example that read the example's grids: the input grid, and the train output where there is one.
    cs and sizes: the table's cell sets and frames, as table_features gives them."""
    cols = tab['columns']
    gi, go = grids
    c = LB.Context(tab, rows, None, gi, go, sizes, cs)
    f = LB.INPUT_GRID_STAGE.run(c)
    if go is not None:
        LB.GRID_STAGE.run(c, f)
    return f


MAX_MATCHES = 5000  # column matches tried per pair of tables
STRUCTURE = ('duplicate of a relation it reads', 'projection of a relation it reads', 'functional extension of a relation it reads',
             'Cartesian product', 'degenerate', 'selectivity')  # the features of structure_features


def row_set(rows, types, idents=None):
    """The rows as a set, a color kept apart from a number of the same value. idents: {Ident label: the object it stands for}, since a label holds
    only within its table."""
    idents = idents or {}

    def value(v, ty):
        if ty == 'Color':
            return 'color %s' % v
        if ty == 'Ident':
            return 'ident %s' % idents.get(str(v), v)
        return json.dumps(v)
    return {tuple(value(v, ty) for v, ty in zip(r, types)) for r in rows}


def column_matches(cand):
    """The injective choices of one candidate per position, or none where they number more than MAX_MATCHES, so that the answer depends on no
    order of the columns."""
    out, chosen = [], []

    def walk(at):
        if at == len(cand):
            out.append(tuple(chosen))
            return
        for j in cand[at]:
            if len(out) > MAX_MATCHES:
                return
            if j not in chosen:
                chosen.append(j)
                walk(at + 1)
                chosen.pop()
    walk(0)
    return out if len(out) <= MAX_MATCHES else []


def cartesian(R, k):
    """Whether the k columns of rows R split into two groups, each with two or more distinct rows, whose product R is. Two columns on opposite sides
    of such a split are independent: each pair of their values occurs. So only the splits between groups of columns that depend on each other are
    tried, and a column of one value stands on neither side, since it changes no count."""
    if not 2 <= k <= 10:
        return False
    values = [{r[i] for r in R} for i in range(k)]
    varying = [i for i in range(k) if len(values[i]) >= 2]
    group = {i: i for i in varying}

    def root(i):
        while group[i] != i:
            i = group[i]
        return i
    for at, i in enumerate(varying):
        for j in varying[at + 1:]:
            if root(i) != root(j) and len({(r[i], r[j]) for r in R}) < len(values[i]) * len(values[j]):
                group[root(i)] = root(j)
    groups = [[i for i in varying if root(i) == g] for g in sorted({root(i) for i in varying})]
    for a in range(1, 2 ** max(len(groups) - 1, 0)):
        A = [i for g, held in enumerate(groups) if a >> g & 1 for i in held]
        B = [i for g, held in enumerate(groups) if not a >> g & 1 for i in held]
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


def all_features(T, ex, task_json, graph, upstream, grids_of, cache=None, reads=None, prov=None, own=True, others=None):
    """{(owner, feature): value} at example ex, for every table of T. cache: a FeatureCache that the calls of one task share. reads:
    engine.table_reads of the program, for the relations each form reads directly; without it, selectivity reads every table of each
    relation or instance that the graph gives, and not the input grid. prov: the Solver's provenance, which gives the identities and the
    descriptions of the tables and the columns. Cross-table Ident observations additionally need the auxiliary ident_values maps that
    observations.Solver supplies; legacy tables without them contribute no such observations. The maps are read only for equality. own: whether
    ex is one of the task's own examples; a variant of a task takes neither the features across its examples nor the input claims. others: the
    tables at each other retained assignment, for the features across assignments."""
    if prov is None:
        raise ValueError('all_features needs the provenance of the program, which gives the identities of its tables and columns')
    gi, go = grids_of(task_json, ex)
    sizes = {'input': (len(gi), len(gi[0]))}
    if go is not None:
        sizes['output'] = (len(go), len(go[0]))
    out, shared, sets, toks, earlier = {}, {}, {}, {}, {}
    dig = {n: rows_digest(rows_at(t, ex) if rows_at(t, ex) is not None else view_at(t, ex)) for n, t in T.items() if n not in ('ex_input', 'ex_output')} if cache is not None else None
    dig_t = None if dig is None else {table_token(n): d for n, d in dig.items()}
    if dig is not None:
        dig['input'] = rows_digest(gi)  # structure_of compares a table with the input grid, which T does not hold
    tok = lambda n: toks[n] if n in toks else toks.setdefault(n, tokened(n, T[n]))
    for name, tab in T.items():
        if name in ('ex_input', 'ex_output'):
            continue
        ups = upstream(graph, name)
        up_tabs = {u: t for u, t in T.items() if u.split('.')[0] in ups}
        earlier[name] = [u for u in up_tabs if u.split('.')[0] != name.split('.')[0] and u not in ('ex_input', 'ex_output')]
        feats = table_features(table_token(name), tok(name), ex, sizes, {table_token(u): tok(u) for u in up_tabs}, (gi, go), shared, cache, dig_t)
        if own:
            feats.update(IN.claims(tok(name), ex, sizes, gi))
            feats.update(AX.claims(tok(name), ex, task_json, grids_of))
            feats['assignments of its table'] = tab.get('assignments', 1)
            LB.own(tok(name), ex, sizes, gi, go, feats, {table_token(u): tok(u) for u in up_tabs})
            if ex.startswith('train/'):
                LB.TRAIN_EXAMPLES_STAGE.run(LB.Context(tok(name), rows_at(tok(name), ex), ex, gi, go, task=task_json, grids_of=grids_of), feats)
            if others:
                feats.update(AS.claims(name, tok(name), ex, others, sizes, gi))
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
    if own:
        out.update(PR.claims(out, T, ex, earlier, sizes, gi, go, OUTPUT_FEATURES, INPUT_CLAIMS))
        memo = {}
        for name, before in earlier.items():
            for k, v in PR.static_claims(name, graph, before, memo).items():
                out[(name, k)] = v
    return out


def base_features(task_json, ex, grids_of, own=True):
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

    def whole(names, side, frame):
        """The table of one grid of each of the named examples: its input (side 0) or its train output (side 1)."""
        rows = {}
        for e in names:
            g = grids_of(task_json, e)[side]
            H, W = len(g), len(g[0])
            rows[e] = [[[r, H - 1 - r, c, W - 1 - c], g[r][c]] for r in range(H) for c in range(W)]
        return {'columns': [[COLUMN_P, 'Position', frame], [COLUMN_COL, 'Color', frame]], 'rows': rows}

    sizes = {'input': (hi, wi)}
    if go is not None:
        sizes['output'] = (len(go), len(go[0]))
    out = {('input', k): v for k, v in table_features('input', table(gi, 'input'), ex, dict(sizes), {}, (gi, go)).items()}
    if own:
        out.update({('input', k): v for k, v in IN.claims(table(gi, 'input'), ex, sizes, gi).items()})
        names = ['train/%d' % i for i in range(len(task_json['train']))] + ['test/%d' % i for i in range(len(task_json['test']))]
        out.update({('input', k): v for k, v in AX.table_claims(whole(names, 0, 'input')).items()})
    if go is not None:
        out.update({('output', k): v for k, v in table_features('output', table(go, 'output'), ex, dict(sizes), {}, (gi, go)).items()})
        if own:
            out.update({('output', k): v for k, v in AX.table_claims(whole(names[:len(task_json['train'])], 1, 'output')).items()})
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
        held = view_at(tab, ex)
        if held is None:
            return {}
        # Two parts of two rows or more are what `cartesian` finds, up to its limit on the columns.
        cross = len(tab['columns']) <= 10 and sum(len(part) >= 2 for _, part in held[1]) >= 2
        return {'Cartesian product': cross, 'degenerate': cross or held[0] == 0}
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
        aliases = tuple(json.dumps(T[u].get('ident_values', {}), sort_keys=True) for u in [name, *up] if u in T)
        key = ('structure', name, dig.get(name), tuple((u, dig.get(u)) for u in up), tuple((u, dig.get(u)) for u in par), aliases)
        hit = cache.get(key)
        if hit is not None:
            return dict(hit)

    def set_of(u):
        if u not in sets:
            if u == 'input':
                H, W = len(gi), len(gi[0])
                sets[u] = (row_set([[[r, H - 1 - r, c, W - 1 - c], gi[r][c]] for r in range(H) for c in range(W)], ('Position', 'Color')), 2)
            else:
                ur = rows_at(T[u], ex)
                sets[u] = (None if ur is None else row_set(ur, [c[1] for c in T[u]['columns']], T[u].get('ident_values')), len(T[u]['columns']))
        return sets[u]
    R, k = set_of(name)
    f = structure_features(R, k, [set_of(u) for u in up if set_of(u)[0] is not None],
                           [len(gi) * len(gi[0]) if u == 'input' else row_count(T[u], ex) for u in par if u == 'input' or row_count(T[u], ex) is not None])
    if key is not None:
        cache.put(key, dict(f))
    return f
