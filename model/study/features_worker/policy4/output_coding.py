"""Features of a table that point toward the task's output (explorer a).

Reading of the rows. A row is flat: Position, Box and Offset take 4 ints (Position is row, rows below, column, columns right of it), every other type takes 1. A
table has one entry per example and per assignment of the free DET values it reads (the entries of one example are the table's variants); an entry with
example [0, 0] is one table for all examples, split by its Example column when it has one. The extents of an entry give the grid that each Position, Box or
Offset column lives in.

ha_code: the bits that a table's cells save when the output color of each cell is coded with the input color and the table (a Dirichlet 1/2 code length
over the train cells, so a split that only fits noise costs bits and the gain is negative). It is taken for the best variant, for the table's cells alone and
beyond the cells of the gold prefix, and for the table's other columns as the cell's attribute (a recolor by a Color, Nat or Ident column).
ha_var: how much the free DET values of a table matter: the number of variants and the spread of ha_code over them.
ha_frame: the grid that the table's columns live in against the output's size, and sizes in the table (box dimensions) against the output's.
ha_geo: whether the changed cells that the table does not cover lie next to the table's cells, or in a row or column of them.
"""
import math
import numpy as np
from scipy.special import gammaln

WIDE = ('Position', 'Box', 'Offset')
K = 10
LN2 = math.log(2)
MAX_VARIANTS = 10
MAX_ATTR_DISTINCT = 16
_CACHE = [None, None]
import os
DEBUG = bool(os.environ.get('HA_DEBUG'))


def widths(types):
    return [4 if t in WIDE else 1 for t in types]


def kt_bits(code, y):
    """Dirichlet 1/2 code length in bits of y (colors 0..9) given the block codes, both int arrays."""
    if len(code) == 0:
        return 0.0
    m = int(code.max()) + 1
    cnt = np.bincount(code * K + y, minlength=m * K).reshape(m, K)
    n = cnt.sum(1)
    ll = gammaln(cnt + .5).sum() - gammaln(n + K / 2).sum() + m * (gammaln(K / 2) - K * gammaln(.5))
    return float(-ll / LN2)


def compress(code):
    return np.unique(code, return_inverse=True)[1].ravel()


class Task:
    """Cells of the train examples in the output's frame. Where input and output differ in size, a cell has input color 0."""

    def __init__(self, ctx):
        tr = ctx['train']
        self.n = len(tr)
        self.same, self.odims, self.idims, self.off = [], [], [], []
        xs, ys, cs, es = [], [], [], []
        o = 0
        for e, p in enumerate(tr):
            a = np.asarray(p['input'], dtype=np.int64)
            b = np.asarray(p['output'], dtype=np.int64)
            self.idims.append(a.shape)
            self.odims.append(b.shape)
            s = a.shape == b.shape
            self.same.append(s)
            self.off.append(o)
            xs.append(a.ravel() if s else np.zeros(b.size, np.int64))
            ys.append(b.ravel())
            cs.append(a.ravel() != b.ravel() if s else np.zeros(b.size, bool))
            es.append(np.full(b.size, e))
            o += b.size
        self.N = o
        self.x = np.concatenate(xs) if xs else np.zeros(0, np.int64)
        self.y = np.concatenate(ys) if ys else np.zeros(0, np.int64)
        self.changed = np.concatenate(cs) if cs else np.zeros(0, bool)
        self.ex = np.concatenate(es) if es else np.zeros(0, np.int64)
        self.dd = [not s for s in self.same]
        self.base_code = compress(self.x)
        self.L0 = kt_bits(self.base_code, self.y)
        self.avail = None
        self.code_av = None
        self.Lav = None
        self.code_av2 = None
        self.Lav2 = None

    def accept(self, e, ext):
        """Whether a column of extent ext (None or [h, w]) is a view of example e's output cells."""
        if self.same[e]:
            return True
        return ext is not None and tuple(ext) == tuple(self.odims[e])


_NODE = [None, None]


def parse(node, T):
    """(types, variants). A variant is {e: (array of rows, extents of the rows)} over the train examples."""
    if _NODE[0] is node:
        return _NODE[1]
    got = parse_(node, T)
    _NODE[0], _NODE[1] = node, got
    return got


def parse_(node, T):
    types = node.get('table_types') or node['types']
    w = widths(types)
    tot = sum(w)
    ex_col = None
    if 'Example' in types:
        ex_col = sum(w[:types.index('Example')])
    per, glob = {}, []
    for ent in node.get('x_rows') or []:
        (a, e), rows = ent[0], ent[1]
        if a == 2 or not rows:
            if a == 1 and e < T.n and not rows:
                per.setdefault(e, []).append((np.zeros((0, tot), np.int64), []))
            continue
        if len(rows[0]) != tot:
            return types, None
        arr = np.asarray(rows, dtype=np.int64)
        ext = ent[5] if len(ent) > 5 else None
        if a == 0:
            glob.append((arr, ext))
        elif e < T.n:
            per.setdefault(e, []).append((arr, ext))
    variants = []
    if per:
        for k in range(min(MAX_VARIANTS, max(len(v) for v in per.values()))):
            variants.append({e: v[k] for e, v in per.items() if k < len(v)})
    for arr, ext in glob[:MAX_VARIANTS]:
        v = {}
        if ex_col is not None:
            for e in range(T.n):
                sel = arr[:, ex_col] == e
                if sel.any():
                    if not ext:
                        sub = None
                    elif any(T.dd):
                        sub = [ext[i] for i in np.flatnonzero(sel)]
                    else:
                        sub = [ext[int(np.argmax(sel))]]
                    v[e] = (arr[sel], sub)
        else:
            for e in range(T.n):
                v[e] = (arr, ext)
        variants.append(v)
    return types, variants


def col_layout(types):
    """Per column: (type, start offset in the flat row, index among the wide columns or None)."""
    out, o, k = [], 0, 0
    for t in types:
        if t in WIDE:
            out.append((t, o, k)); o += 4; k += 1
        else:
            out.append((t, o, None)); o += 1
    return out


def ext_ok(T, e, ext, k):
    """Whether wide column k, from the extents of an entry's rows, lives in example e's output grid (the first row says: a column has one frame per example)."""
    if not ext:
        return False
    try:
        x = ext[0]
        return x is not None and len(x) > k and x[k] is not None and tuple(x[k]) == tuple(T.odims[e])
    except Exception:
        return False


def view_specs(types):
    """The cell views of a table: ('P', i) each Position column, ('B', i) the union of each Box column's rectangles, ('S', i, j) the first Position column
    i moved by Offset column j (at most two)."""
    specs = []
    offs = [i for i, t in enumerate(types) if t == 'Offset']
    pos = [i for i, t in enumerate(types) if t == 'Position']
    for i in pos:
        specs.append(('P', i))
    for i, t in enumerate(types):
        if t == 'Box':
            specs.append(('B', i))
    if pos:
        for j in offs[:2]:
            specs.append(('S', pos[0], j))
    return specs


def rect_union(arr, o, h, w):
    """Cells (flat ids in an h x w grid) in the union of the rectangles of a Box column that starts at offset o of the rows: rows [top, h - bottom), columns [left, w - right)."""
    r0, r1 = arr[:, o], h - arr[:, o + 1]
    c0, c1 = arr[:, o + 2], w - arr[:, o + 3]
    ok = (r0 >= 0) & (c0 >= 0) & (r0 < r1) & (c0 < c1) & (r1 <= h) & (c1 <= w)
    if not ok.any():
        return None
    r0, r1, c0, c1 = r0[ok], r1[ok], c0[ok], c1[ok]
    diff = np.zeros((h + 1, w + 1), np.int64)
    np.add.at(diff, (r0, c0), 1)
    np.add.at(diff, (r0, c1), -1)
    np.add.at(diff, (r1, c0), -1)
    np.add.at(diff, (r1, c1), 1)
    return (diff.cumsum(0).cumsum(1)[:h, :w] > 0).ravel()


def cell_vectors(T, types, variant, spec, attrs):
    """For a view spec of a variant: (membership bool array over T's cells, {attr column: int array, 0 = not in the table, v + 1 = value v}). Attributes
    come from Position and moved views only."""
    lay = col_layout(types)
    m = np.zeros(T.N, bool)
    av = {j: np.zeros(T.N, np.int64) for j in attrs} if spec[0] != 'B' else {}
    for e, (arr, ext) in variant.items():
        if e >= T.n or len(arr) == 0:
            continue
        h, w = T.odims[e]
        _, po, pk = lay[spec[1]]
        if not ext_ok(T, e, ext, pk):
            continue
        if spec[0] == 'B':
            f = rect_union(arr, po, h, w)
            if f is not None:
                m[T.off[e]:T.off[e] + h * w] |= f
            continue
        r, c = arr[:, po], arr[:, po + 2]
        if spec[0] == 'S':
            oo = lay[spec[2]][1]
            r, c = r + arr[:, oo], c + arr[:, oo + 2]
        ok = (r >= 0) & (r < h) & (c >= 0) & (c < w)
        if not ok.any():
            continue
        ids = T.off[e] + r[ok] * w + c[ok]
        m[ids] = True
        for j in attrs:
            av[j][ids] = arr[ok, lay[j][1]] + 1
    return m, av


def attr_columns(types, variants):
    """Single-cell columns that can be a cell's attribute: not wide, not Example, and few distinct values."""
    cols = []
    for j, t in enumerate(types):
        if t in WIDE or t == 'Example':
            continue
        cols.append(j)
    return cols


def prepare(ctx):
    if _CACHE[0] is ctx:
        return _CACHE[1]
    T = Task(ctx)
    bits = []
    for n in ctx.get('available') or []:
        try:
            types, vs = parse(n, T)
            if not vs:
                continue
            m = np.zeros(T.N, bool)
            for v in vs:
                for sp in view_specs(types):
                    m |= cell_vectors(T, types, v, sp, [])[0]
            if m.any():
                bits.append(m)
        except Exception:
            continue
    code = T.base_code
    for m in bits:
        code = compress(code * 2 + m)
    # the same, with the first few-valued column of each available table as the cell's attribute in place of its membership
    code2 = T.base_code
    n2 = 0
    for n in ctx.get('available') or []:
        try:
            types, vs = parse(n, T)
            if not vs:
                continue
            pos = [sp for sp in view_specs(types) if sp[0] == 'P']
            attrs = attr_columns(types, vs)
            if not pos:
                continue
            m, av = cell_vectors(T, types, vs[0], pos[0], attrs)
            a = m.astype(np.int64)
            for j, vv in av.items():
                if len(np.unique(vv)) <= MAX_ATTR_DISTINCT + 1:
                    a = vv; break
            if a.any():
                code2 = compress(code2 * 64 + np.minimum(a, 63)); n2 += 1
        except Exception:
            continue
    T.avail = bits
    T.code_av = code
    T.Lav = kt_bits(code, T.y)
    T.code_av2 = code2
    T.Lav2 = kt_bits(code2, T.y)
    _CACHE[0], _CACHE[1] = ctx, T
    return T


def code_features(node, T, d):
    types, vs = parse(node, T)
    if not vs:
        return
    d['ha_n_variants'] = float(len(vs))
    pos = view_specs(types)
    if not pos or T.N == 0 or T.L0 <= 0:
        return
    attrs = attr_columns(types, vs)
    per_var, per_var_inc, per_var_attr, per_var_attr_inc, per_var_extra, per_var_inc2 = [], [], [], [], [], []
    cover = 0.0
    for v in vs:
        gb = gi = ga = gai = gx = gi2 = -1e9
        for pi in pos:
            m, av = cell_vectors(T, types, v, pi, attrs)
            if not m.any():
                gb, gi, gi2 = max(gb, 0.0), max(gi, 0.0), max(gi2, 0.0)
                continue
            cm = T.base_code * 2 + m
            lm = kt_bits(compress(cm), T.y)
            if T.L0 - lm > gb:
                cover = float(m.mean())
            gb = max(gb, T.L0 - lm)
            gi = max(gi, T.Lav - kt_bits(compress(T.code_av * 2 + m), T.y))
            gi2 = max(gi2, T.Lav2 - kt_bits(compress(T.code_av2 * 2 + m), T.y))
            for j, a in av.items():
                if len(np.unique(a)) > MAX_ATTR_DISTINCT + 1:
                    continue
                la = kt_bits(compress(T.base_code * 64 + np.minimum(a, 63)), T.y)
                ga = max(ga, T.L0 - la)
                gx = max(gx, lm - la)
                gai = max(gai, T.Lav - kt_bits(compress(T.code_av * 64 + np.minimum(a, 63)), T.y))
                gi2 = max(gi2, T.Lav2 - kt_bits(compress(T.code_av2 * 64 + np.minimum(a, 63)), T.y))
        per_var.append(gb); per_var_inc.append(gi); per_var_inc2.append(gi2)
        if ga > -1e9:
            per_var_attr.append(ga); per_var_attr_inc.append(gai); per_var_extra.append(gx)
    pv = np.array(per_var)
    d['ha_gain_best'] = float(pv.max())
    d['ha_gain_best_frac'] = float(pv.max() / T.L0)
    d['ha_gain_worst'] = float(pv.min())
    d['ha_gain_mean'] = float(pv.mean())
    d['ha_gain_inc_best'] = float(max(per_var_inc))
    d['ha_gain_inc_frac'] = float(max(per_var_inc) / max(T.Lav, 1.0))
    d['ha_gain_inc2_best'] = float(max(per_var_inc2))
    d['ha_gain_inc2_frac'] = float(max(per_var_inc2) / max(T.Lav2, 1.0))
    d['ha_lav2_frac'] = float(T.Lav2 / T.L0)
    d['ha_var_spread'] = float((pv.max() - pv.min()) / T.L0)
    d['ha_var_std'] = float(pv.std() / T.L0)
    if per_var_attr:
        d['ha_attr_gain_best'] = float(max(per_var_attr))
        d['ha_attr_gain_frac'] = float(max(per_var_attr) / T.L0)
        d['ha_attr_gain_inc'] = float(max(per_var_attr_inc))
        d['ha_attr_extra'] = float(max(per_var_extra))
        d['ha_attr_extra_frac'] = float(max(per_var_extra) / T.L0)
    d['ha_cover_best'] = cover
    d['ha_lav_frac'] = float(T.Lav / T.L0)
    d['ha_L0_per_cell'] = float(T.L0 / max(T.N, 1))


def frame_features(node, T, d):
    """The grid that the wide columns live in against the output's size. Only where some train example's output differs in size from its input."""
    types, vs = parse(node, T)
    wide = [t for t in types if t in WIDE]
    dd = [e for e in range(T.n) if T.dd[e]]
    d['ha_dims_differ'] = float(len(dd) / max(T.n, 1))
    if not vs or not wide:
        return
    cnt = {'out': 0, 'in': 0, 'sub': 0, 'none': 0, 'big': 0}
    out_ex = set()
    div = box_eq = box_div = box_n = 0
    tot = 0
    tile_div = tile_n = 0
    for v in vs[:3]:
        for e, (arr, ext) in v.items():
            if e >= T.n or not ext:
                continue
            oh, ow = T.odims[e]
            ih, iw = T.idims[e]
            x0 = ext[0]
            for k in range(len(x0)):
                tot += 1
                x = x0[k]
                if x is None:
                    cnt['none'] += 1; continue
                h, w = x
                if (h, w) == (oh, ow) and (oh, ow) != (ih, iw):
                    cnt['out'] += 1
                    out_ex.add(e)
                elif (h, w) == (ih, iw):
                    cnt['in'] += 1
                elif h <= oh and w <= ow and h * w < oh * ow:
                    cnt['sub'] += 1
                    tile_n += 1
                    tile_div += int(oh % h == 0 and ow % w == 0)
                else:
                    cnt['big'] += 1
            # box dimensions: a Box column is (top, bottom, left, right) margins inside its frame
            lay = col_layout(types)
            for t, o, k in lay:
                if t != 'Box' or k is None or k >= len(x0) or x0[k] is None:
                    continue
                fh, fw = x0[k]
                bh = fh - arr[:, o] - arr[:, o + 1]
                bw = fw - arr[:, o + 2] - arr[:, o + 3]
                if len(bh) == 0:
                    continue
                box_n += 1
                hb, wb = int(np.median(bh)), int(np.median(bw))
                box_eq += (hb, wb) == (oh, ow) and (oh, ow) != (ih, iw)
                box_div += hb > 0 and wb > 0 and (hb, wb) != (oh, ow) and oh % hb == 0 and ow % wb == 0
    if tot:
        for k in ('out', 'in', 'sub', 'none', 'big'):
            d['ha_frame_' + k] = cnt[k] / tot
    if any(T.dd):
        d['ha_frame_out_dd'] = d.get('ha_frame_out', 0.0)
        d['ha_frame_out_all'] = float(all(e in out_ex for e in dd))
    if tile_n:
        d['ha_frame_sub_divides'] = tile_div / tile_n
    if box_n:
        d['ha_box_eq_out'] = box_eq / box_n
        d['ha_box_div_out'] = box_div / box_n


def geo_features(node, T, d):
    """Changed cells that the table does not cover, against the table's cells: next to them, or in a row or column of them. Lift over the share of all
    uncovered cells that lie so. Only same-size train examples."""
    types, vs = parse(node, T)
    pos = view_specs(types)
    if not vs or not pos or not any(T.same) or not T.changed.any():
        return
    best = None
    for v in vs[:4]:
        for pi in pos:
            m, _ = cell_vectors(T, types, v, pi, [])
            if not m.any():
                continue
            ring_hit = ring_all = line_hit = line_all = rest_n = rest_d = 0
            for e in range(T.n):
                if not T.same[e]:
                    continue
                h, w = T.odims[e]
                sl = slice(T.off[e], T.off[e] + h * w)
                S = m[sl].reshape(h, w)
                D = T.changed[sl].reshape(h, w)
                if not S.any():
                    continue
                P = np.pad(S, 1)
                ring = (P[:-2, 1:-1] | P[2:, 1:-1] | P[1:-1, :-2] | P[1:-1, 2:] | P[:-2, :-2] | P[:-2, 2:] | P[2:, :-2] | P[2:, 2:]) & ~S
                lines = (S.any(1)[:, None] | S.any(0)[None, :]) & ~S
                rest = ~S
                ring_all += int(ring.sum()); line_all += int(lines.sum()); rest_n += int(rest.sum())
                Dr = D & rest
                rest_d += int(Dr.sum()); ring_hit += int((Dr & ring).sum()); line_hit += int((Dr & lines).sum())
            if rest_d == 0 or rest_n == 0:
                continue
            ring_lift = (ring_hit / rest_d) / max(ring_all / rest_n, 1e-9)
            line_lift = (line_hit / rest_d) / max(line_all / rest_n, 1e-9)
            cand = (ring_hit / rest_d, ring_lift, line_hit / rest_d, line_lift, rest_d / max(int(T.changed.sum()), 1))
            if best is None or cand[1] > best[1]:
                best = cand
    if best:
        d['ha_ring_share'], d['ha_ring_lift'], d['ha_line_share'], d['ha_line_lift'] = [float(x) for x in best[:4]]


def ha(node, ctx):
    """Output-pointing features of a table: code length saved (ha_gain_*, ha_attr_*), DET-variant spread (ha_var_*), frame and size reach (ha_frame_*, ha_box_*), changed cells next to the table (ha_ring_*, ha_line_*)."""
    d = {}
    try:
        T = prepare(ctx)
    except Exception:
        if DEBUG:
            raise
        return d
    for f in (code_features, frame_features, geo_features):
        try:
            f(node, T, d)
        except Exception:
            if DEBUG:
                raise
    return d


FEATURE_FUNCS = {'ha': ha}
