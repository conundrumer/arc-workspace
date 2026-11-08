"""Model input layer: pairs of cells in one row, pairs of objects named by the values of one row, and the colored cells of a table against the output. No opaque id is read as a number. An
object's description comes from every upstream column of the same type whose values cover the observed keys, and each description keeps its own name, so there is no best match and no search
for an alignment. The features of an ordered pair are given for both orders, and an order is pooled over the axes and over reversal, so that it keeps its value under D4.
"""
from collections import defaultdict
import json

from grammar import ABSENT, Var, operator
from vocabulary import GRID_STAGE, TABLE_STAGE, columns

n, x, a, b, va, vb = (Var(v) for v in 'n x a b va vb'.split())
POOLS = (('min', min), ('max', max), ('mean', lambda held: round(sum(held) / len(held), 3)))


def freeze(y):
    return json.dumps(y, sort_keys=True)


def object_key(tab, ty, value):
    """A key shared between tables, where equality of the objects is known: colors are shared, and an Ident stands for its object."""
    if ty == 'Ident':
        raw = tab.get('ident_values', {}).get(str(value))
        return None if raw is None else ('Ident', raw)
    return ('Color', freeze(value))


def bounds(s):
    return min(r for r, c in s), min(c for r, c in s), max(r for r, c in s), max(c for r, c in s)


def norm(s):
    r0, c0, _, _ = bounds(s)
    return frozenset((r - r0, c - c0) for r, c in s)


# ---- two cells of one row

def cell_columns(c, e):
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[1] == 'Position' and col[0] in c.cs] if c.rows else ()


def cell_columns_in_frame_of(v):
    def dom(c, e):
        fr = c.cs[c.cols[e[v]][0]][0]
        return [(i, col[0]) for i, col in enumerate(c.cols) if i != e[v] and col[1] == 'Position' and col[0] in c.cs and c.cs[col[0]][0] == fr]
    return dom


def displacements(c, e, v, w):
    key = ('displacements', e[v], e[w])
    held = c.memo.get(key)
    if held is None:
        held = c.memo[key] = [(y[0] - p[0], y[2] - p[2]) for p, y in {(tuple(r[e[v]]), tuple(r[e[w]])) for r in c.rows}]
    return held


@operator
def manhattan_distance(c, e, v, w, pool):
    return pool[1]([abs(p) + abs(q) for p, q in displacements(c, e, v, w)])


@operator
def shared_axes(c, e, v, w, pool):
    return pool[1]([int(p == 0) + int(q == 0) for p, q in displacements(c, e, v, w)])


@operator
def axes_with_one_sign(c, e, v, w):
    moves = displacements(c, e, v, w)
    signs = [{(m[k] > 0) - (m[k] < 0) for m in moves} for k in (0, 1)]
    return sum(len(s) == 1 and 0 not in s for s in signs)


# ---- two objects of one row

def catalogs(un, tab, ex):
    """Every (key, cells) description of a table's objects, each with a frame of its own. A Box value counts only where it gives cells in one nonnegative frame per key, as a crop does."""
    rows = tab['rows'].get(ex, tab['rows'].get('task'))
    if not rows:
        return []
    out = []
    for i, (kn, kt, _) in enumerate(tab['columns']):
        if kt not in ('Ident', 'Color'):
            continue
        for j, (pn, pt, fr) in enumerate(tab['columns']):
            if pt not in ('Position', 'Box') or (pt == 'Box' and fr in ('input', 'output')):
                continue
            groups, extents = defaultdict(set), defaultdict(set)
            for r in rows:
                v, k = r[j], object_key(tab, kt, r[i])
                if k is None:
                    break
                if min(v) < 0:
                    break
                groups[k].add((v[0], v[2]))
                extents[k].add((v[0] + v[1] + 1, v[2] + v[3] + 1))
            else:
                if all(len(v) == 1 for v in extents.values()):
                    frames = set.union(*extents.values())
                    frame = (fr, next(iter(frames))) if fr and len(frames) == 1 else None
                    out.append((kt, '%s.%s via %s.%s' % (un, pn, un, kn), groups, frame))
    return out


def all_catalogs(c):
    held = c.memo.get('catalogs')
    if held is None:
        held = []
        for un, tab in c.up_tabs.items():
            key = ('correspondence catalogs', un)
            if key not in c.shared:
                c.shared[key] = catalogs(un, tab, c.ex)
            held.extend(c.shared[key])
        c.memo['catalogs'] = held
    return held


@operator(memo=True)
def object_pairs(c, e, v, w):
    """The pairs of objects that two columns of the rows name, or None where the table does not say which object a value stands for."""
    ta, tb = c.cols[e[v]][1], c.cols[e[w]][1]
    pairs = {(object_key(c.tab, ta, r[e[v]]), object_key(c.tab, tb, r[e[w]])) for r in c.rows}
    if not pairs or any(p is None or q is None for p, q in pairs):
        return None
    return pairs


def object_columns(c, e):
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[1] in ('Ident', 'Color')]


def other_object_columns(c, e):
    return [(i, tok) for i, tok in object_columns(c, e) if i != e[a]]


def catalogs_of_first(c, e):
    pairs = object_pairs(a, b)(c, e)
    if pairs is None:
        return ()
    ty = c.cols[e[a]][1]
    keys = {p for p, _ in pairs}
    return [(i, v[1]) for i, v in enumerate(all_catalogs(c)) if v[0] == ty and keys <= v[2].keys()]


def catalogs_of_second(c, e):
    pairs = object_pairs(a, b)(c, e)
    ty = c.cols[e[b]][1]
    keys = {q for _, q in pairs}
    return [(i, v[1]) for i, v in enumerate(all_catalogs(c)) if v[0] == ty and keys <= v[2].keys()]


def footprints(c, e, v, w, p, q):
    pairs = object_pairs(v, w)(c, e)
    held = all_catalogs(c)
    return [held[e[p]][2][k] for k, _ in pairs], [held[e[q]][2][k] for _, k in pairs]


@operator
def same_footprint(c, e, v, w, p, q):
    sa, sb = footprints(c, e, v, w, p, q)
    return round(sum(norm(y) == norm(z) for y, z in zip(sa, sb)) / len(sa), 3)


@operator
def size_ratio(c, e, v, w, p, q, pool):
    sa, sb = footprints(c, e, v, w, p, q)
    return pool[1]([len(y) / len(z) for y, z in zip(sa, sb)])


@operator
def size_product(c, e, v, w, p, q, pool):
    sa, sb = footprints(c, e, v, w, p, q)
    return pool[1]([len(y) * len(z) for y, z in zip(sa, sb)])


def one_frame(c, e, p, q):
    held = all_catalogs(c)
    fa, fb = held[e[p]][3], held[e[q]][3]
    return fa is not None and fa == fb


@operator
def box_separation(c, e, v, w, p, q, pool):
    if not one_frame(c, e, p, q):
        return ABSENT
    sa, sb = footprints(c, e, v, w, p, q)
    gaps = []
    for y, z in zip(sa, sb):
        r0, c0, r1, c1 = bounds(y)
        s0, d0, s1, d1 = bounds(z)
        gaps.append(max(0, r0 - s1, s0 - r1) + max(0, c0 - d1, d0 - c1))
    return pool[1](gaps)


@operator
def distinct_center_displacements(c, e, v, w, p, q):
    if not one_frame(c, e, p, q):
        return ABSENT
    sa, sb = footprints(c, e, v, w, p, q)
    moves = set()
    for y, z in zip(sa, sb):
        r0, c0, r1, c1 = bounds(y)
        s0, d0, s1, d1 = bounds(z)
        moves.add((s0 + s1 - r0 - r1, d0 + d1 - c0 - c1))
    return len(moves)


# ---- colored cells against the output

def expand(pairs, h, w, target_h, target_w):
    """Uniform integer scaling up to the target's extents, or None where the extents are not a whole multiple. Scaling down keeps all the colors in each block, so conflicting colors cannot vanish by sampling a cell."""
    if target_h % h == 0 and target_w % w == 0 and target_h // h == target_w // w:
        k = target_h // h
        return {((r * k + dr, c * k + dc), v) for (r, c), v in pairs for dr in range(k) for dc in range(k)}
    return None


def aligned(pairs, want):
    """The Jaccard index of two colored cell sets, after each is translated to its bounding box and the smaller is scaled up. No translation, rotation, color map or scale is chosen by its agreement with the output."""
    if not pairs or not want:
        return None

    def anchor(ps):
        r0, c0, r1, c1 = bounds({p for p, v in ps})
        return {((r - r0, c - c0), v) for (r, c), v in ps}, r1 - r0 + 1, c1 - c0 + 1
    p, h, w = anchor(pairs)
    q, th, tw = anchor(want)
    if th * tw >= h * w:
        p = expand(p, h, w, th, tw)
    else:
        q = expand(q, th, tw, h, w)
    if p is None or q is None:
        return None
    return round(len(p & q) / len(p | q), 3)


def colored_pairs(c, e, v, w):
    return {((r[e[v]][0], r[e[v]][2]), r[e[w]]) for r in c.rows}


def output_pairs(c):
    return {((r, k), y) for r, row in enumerate(c.go) for k, y in enumerate(row)}


@operator(reads=('output',))
def jaccard_in_frame(c, e, v, w):
    if c.sizes[c.cs[c.cols[e[v]][0]][0]] != (len(c.go), len(c.go[0])):
        return ABSENT
    pairs, want = colored_pairs(c, e, v, w), output_pairs(c)
    return round(len(pairs & want) / len(pairs | want), 3)


@operator(reads=('output',))
def jaccard_of_scaled_boxes(c, e, v, w, colors_only):
    want = output_pairs(c)
    if colors_only:
        colors = {r[e[w]] for r in c.rows}
        want = {(p, y) for p, y in want if y in colors}
    score = aligned(colored_pairs(c, e, v, w), want)
    return ABSENT if score is None else score


def any_cell_column(c, e):
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.cs] if c.rows else ()


def declare_relations():
    from vocabulary import UPSTREAM_STAGE
    for name, pool in POOLS:
        UPSTREAM_STAGE.define('{a} paired with {b} Manhattan distance ' + name, manhattan_distance(a, b, _Pool(name, pool)), a=cell_columns, b=cell_columns_in_frame_of(a))
        UPSTREAM_STAGE.define('{a} paired with {b} shared axes ' + name, shared_axes(a, b, _Pool(name, pool)), a=cell_columns, b=cell_columns_in_frame_of(a))
    UPSTREAM_STAGE.define('{a} paired with {b} axes with one strict direction', axes_with_one_sign(a, b), a=cell_columns, b=cell_columns_in_frame_of(a))
    binders = dict(a=object_columns, b=other_object_columns, va=catalogs_of_first, vb=catalogs_of_second)
    lead = '{a} paired with {b} using {va} and {vb} '
    UPSTREAM_STAGE.define(lead + 'same shape, proportion', same_footprint(a, b, va, vb), **binders)
    UPSTREAM_STAGE.define(lead + 'box center displacements distinct', distinct_center_displacements(a, b, va, vb), **binders)
    for name, pool in POOLS:
        UPSTREAM_STAGE.define(lead + 'size ratio ' + name, size_ratio(a, b, va, vb, _Pool(name, pool)), **binders)
        UPSTREAM_STAGE.define(lead + 'size product ' + name, size_product(a, b, va, vb, _Pool(name, pool)), **binders)
        UPSTREAM_STAGE.define(lead + 'box separation ' + name, box_separation(a, b, va, vb, _Pool(name, pool)), **binders)
    GRID_STAGE.define('{n},{x} Jaccard index with the output cells in the frame', jaccard_in_frame(n, x), n=any_cell_column, x=columns(('Color',)))
    GRID_STAGE.define('{n},{x} Jaccard index with the output cells after bounding box scaling', jaccard_of_scaled_boxes(n, x, False), n=any_cell_column, x=columns(('Color',)))
    GRID_STAGE.define('{n},{x} color Jaccard index with the output cells after bounding box scaling', jaccard_of_scaled_boxes(n, x, True), n=any_cell_column, x=columns(('Color',)))


class _Pool(tuple):
    """A pooling function in a term, with its name."""

    def __new__(cls, name, fn):
        return super().__new__(cls, (name, fn))

    def __hash__(self):
        return hash(self[0])

    def __eq__(self, other):
        return isinstance(other, _Pool) and self[0] == other[0]

    def __repr__(self):
        return self[0]


declare_relations()
OBJECT_PAIR_SCHEMAS = [r for r in __import__('vocabulary').UPSTREAM_STAGE.rules if ' using ' in r.pattern]


def object_pair_features(tab, rows, up_tabs, ex):
    """{feature: value} of the pairs of objects in the rows of a table at example ex, with no other feature of the table."""
    from vocabulary import Context
    c = Context(tab, rows, ex, None, None, {}, {}, up_tabs=up_tabs)
    out = {}
    for r in OBJECT_PAIR_SCHEMAS:
        r.run(c, out)
    return out
