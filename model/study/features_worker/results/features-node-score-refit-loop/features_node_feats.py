"""Per-instance features of a node: table facts against the task's pairs, test input facts, depth, form shape.
See design.md, "Feature groups". Groups by name prefix: tb_ (Table), pr_ (Pairs), oc_ (Output cells), ti_ (Test input), dp_ (Depth),
sh_ and ce_ (Form shape). Feature set T is every group but sh_ and ce_; TS is all.

  ctx = TaskCtx(task_json)              # train pairs and test inputs; test outputs are dropped here
  d = node_features(types, x_rows, clause, kind, form_depth, form_reads, ctx)   # dict name -> float, NaN where empty
"""
import math, sys, os, zlib

import numpy as np
from scipy import ndimage

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop')
import features_node_read as RD
import features_node_shape as SH

NAN = float('nan')
EIGHT = np.ones((3, 3), int)
TYPES = ['Position', 'Box', 'Offset', 'Color', 'Example', 'Ident', 'Nat', 'Int', 'Axis', 'Dir', 'Dir8', 'DiagDir', 'DiagAxis', 'Axis4', 'D4', 'C4', 'Sym', 'Sense', 'Pose']
KINDS = {'DET': 0, 'RULE': 1, 'INIT': 2}


def canon_type(x):
    return x if x in TYPES else ('Pose' if x.startswith('Pose') else 'other')


def obj_shapes(mask, area, lo=3, hi=.6):
    """Set of shapes (height, width, packed cells) of the 8-connected parts of mask with 3 or more cells and at most hi of the area."""
    if not mask.any():
        return set()
    lab, n = ndimage.label(mask, EIGHT)
    out = set()
    for i, sl in enumerate(ndimage.find_objects(lab)):
        m = lab[sl] == i + 1
        c = int(m.sum())
        if c >= lo and c <= hi * area:
            out.add((m.shape[0], m.shape[1], np.packbits(m).tobytes()))
    return out


class Ex:
    """One grid pair (train) or one test input."""

    def __init__(self, a, b=None):
        self.a = np.asarray(a, np.int16)
        self.h, self.w = self.a.shape
        self.area = self.h * self.w
        cnt = np.bincount(self.a.ravel(), minlength=10)
        self.bg = int(cnt.argmax())
        self.fg = self.a != self.bg
        self.colors = frozenset(int(c) for c in np.nonzero(cnt)[0])
        self.cmasks = [self.a == c for c in self.colors]
        self.incls = {m.tobytes() + bytes(m.shape) for m in self.cmasks}
        self.fgshare = float(self.fg.mean())
        self.iobj = None
        self.b = None
        if b is not None:
            self.b = np.asarray(b, np.int16)
            self.ho, self.wo = self.b.shape
            self.oarea = self.ho * self.wo
            oc = np.bincount(self.b.ravel(), minlength=10)
            self.obg = int(oc.argmax())
            self.ofg = self.b != self.obg
            self.ocolors = frozenset(int(c) for c in np.nonzero(oc)[0])
            self.ohist = oc / oc.sum()
            self.same = (self.ho, self.wo) == (self.h, self.w)
            self.changed = (self.a != self.b) if self.same else None
            self.nchanged = int(self.changed.sum()) if self.same else 0
            self.nofg = int(self.ofg.sum())
            self.ocmasks = [self.b == c for c in self.ocolors]
            self.oincls = {m.tobytes() + bytes(m.shape) for m in self.ocmasks}
            self.newcolors = self.ocolors - self.colors
            self.base = self.a if self.same else np.full((self.ho, self.wo), self.obg, np.int16)
            self.base_err = self.nchanged if self.same else self.nofg
            self.chist = None
            if self.same and self.nchanged:
                ch = np.bincount(self.b[self.changed], minlength=10)
                self.chist = ch / ch.sum()
            self.oobj = None
            self.nobj_out = None

    def in_objs(self):
        if self.iobj is None:
            s = set()
            for c in self.colors:
                s |= obj_shapes((self.a == c) & self.fg, self.area)
            self.iobj = s
        return self.iobj

    def out_objs(self):
        if self.oobj is None:
            s = set()
            for c in self.ocolors:
                s |= obj_shapes((self.b == c) & self.ofg, self.oarea)
            self.oobj = s
            self.nobj_out = len(s)
        return self.oobj


class TaskCtx:
    """Train pairs and test inputs. A test item's output is dropped here, so no feature code can receive it."""

    def __init__(self, task):
        self.train = [Ex(p['input'], p['output']) for p in task['train']]
        self.test = [Ex(x['input']) for x in task['test']]
        self.n_train, self.n_test = len(self.train), len(self.test)
        self.exs = self.train + self.test


def _fsum(v):
    return math.fsum(sorted(v))


class Acc:
    """Facts per world and example. out: name_mean (mean over train examples) and name_min, as the greatest over worlds."""

    def __init__(self):
        self.w = {}

    def add(self, wi, name, v):
        if v == v:
            self.w.setdefault(name, {}).setdefault(wi, []).append(float(v))

    def emit(self, d):
        for name, ws in self.w.items():
            ms = [_fsum(v) / len(v) for v in ws.values()]
            mn = [min(v) for v in ws.values()]
            d[name + '_mean'] = max(ms)
            d[name + '_min'] = max(mn)


PAIR_FACTS = ['pr_cover', 'pr_in_fg', 'pr_out_fg', 'pr_prec_ch', 'pr_rec_ch', 'pr_iou_ch', 'pr_unchanged', 'pr_iou_ofg', 'pr_rec_ofg', 'pr_iou_ifg', 'pr_rec_ifg',
              'pr_class_in', 'pr_class_out', 'pr_one_color_out', 'pr_parts', 'pr_shape_in', 'pr_shape_out', 'pr_shape_moved', 'pr_oob',
              'pr_paint_gain', 'pr_paint_exact', 'pr_paint_rec', 'pr_paint_prec', 'pr_paint_broke', 'pr_paint_stale', 'pr_paint_wrong', 'pr_paint_oob', 'pr_paint_conflict',
              'pr_fill_gain', 'pr_fill_rec', 'pr_fill_one',
              'tb_logrows', 'tb_empty', 'tb_onerow', 'tb_const', 'tb_distinct_mean', 'tb_distinct_max', 'tb_pos_key', 'tb_pos_det_color', 'tb_ident_classes', 'tb_ident_maxshare',
              'oc_hist_out', 'oc_hist_changed', 'oc_fits_out', 'oc_rows_eq_changed', 'oc_rows_eq_ofg', 'oc_ratio_changed', 'oc_ratio_ofg', 'oc_box_eq_out', 'oc_box_eq_in', 'oc_nat_in_dims',
              'oc_color_in_out', 'oc_color_new', 'oc_color_obg', 'oc_nat_dims_out']
SCALARS = ['tb_n_cols', 'tb_worlds', 'tb_alt', 'tb_capped', 'tb_empty_any', 'tb_empty_all', 'tb_rows_equal', 'tb_has_example',
           'pr_paint_best_pair', 'pr_paint_worst_pair', 'pr_paint_pairs_exact', 'pr_paint_remap',
           'ti_logrows', 'ti_rows_per_area_in_range', 'ti_empty_with_train_rows', 'ti_colors_inside', 'ti_oob', 'ti_fg_share_delta', 'ti_class', 'ti_shape_in',
           'dp_form_depth', 'dp_form_reads', 'dp_kind']
NAMES = ['tb_t_' + t for t in TYPES + ['other']] + SCALARS + [f + s for f in PAIR_FACTS for s in ('_mean', '_min')] + SH.shape_names()
NAMES = sorted(set(NAMES))
GROUPS = {'tb_': 'Table', 'pr_': 'Pairs', 'oc_': 'Output cells', 'ti_': 'Test input', 'dp_': 'Depth', 'sh_': 'Form shape', 'ce_': 'Form shape'}


def group_of(name):
    return GROUPS[name[:3]]


def names_T():
    return [n for n in NAMES if group_of(n) != 'Form shape']


def names_depth():
    return [n for n in NAMES if group_of(n) == 'Depth']


def colkey(a, c):
    """One int64 per row for the cells of column c (type, start, width)."""
    k = a[:, c[1]].astype(np.int64) + 2048
    for j in range(1, c[2]):
        k = k * 4096 + a[:, c[1] + j] + 2048
    return k


def pos_cells(a, s):
    r, c = a[:, s].astype(np.int64), a[:, s + 2].astype(np.int64)
    code = np.unique(r * 4096 + c + 2048)
    return code // 4096, code % 4096 - 2048


def hit(mask, r, c):
    """Cells (r, c) that lie in mask's grid and are set in mask, and the count of those in the grid."""
    h, w = mask.shape
    inb = (r >= 0) & (r < h) & (c >= 0) & (c < w)
    rr, cc = r[inb], c[inb]
    return int(mask[rr, cc].sum()), int(inb.sum())


def cell_mask(r, c, h, w):
    m = np.zeros((h, w), bool)
    inb = (r >= 0) & (r < h) & (c >= 0) & (c < w)
    m[r[inb], c[inb]] = True
    return m


def paint(ex, r, c, col):
    """One Position column painted with one Color column on the train example. Returns (fixed, broke, stale, oob, conflict, colormap pairs)."""
    H, W = ex.ho, ex.wo
    inb = (r >= 0) & (r < H) & (c >= 0) & (c < W)
    oob = int((~inb).sum())
    r, c, col = r[inb], c[inb], col[inb]
    if len(r) == 0:
        return 0, 0, 0, oob, 0, ()
    flat = r * W + c
    code = np.unique(flat * 16 + col)
    f, v = code // 16, code % 16
    uf, cnt = np.unique(f, return_counts=True)
    conflict = int((cnt > 1).sum())
    single = cnt[np.searchsorted(uf, f)] == 1
    want = ex.b.ravel()[f]
    was = ex.base.ravel()[f] == want
    ok = single & (v == want)
    fixed = int((ok & ~was).sum())
    # a conflicted cell counts once, as wrong, if it was right before (broke) or not (stale)
    fw = f[~single]
    cw = np.unique(fw)
    wasc = ex.base.ravel()[cw] == ex.b.ravel()[cw]
    brokec, stalec = int(wasc.sum()), int((~wasc).sum())
    bad_s = single & (v != want)
    broke = int((bad_s & was).sum()) + brokec
    stale = int((bad_s & ~was).sum()) + stalec
    cm = tuple(zip(v[single].tolist(), want[single].tolist()))
    return fixed, broke, stale, oob, conflict, cm


def canon_rows(a, cols):
    """Bytes of the rows of `a` that don't depend on the order of rows or of same-type columns (Ident cells left out)."""
    if len(a) == 0:
        return b''
    by = {}
    for c in cols:
        if c[0] != 'Ident':
            by.setdefault(c[0], []).append(colkey(a, c))
    if not by:
        return b'x' * len(a)
    m = np.concatenate([np.sort(np.stack(by[t], 1), axis=1) for t in sorted(by)], axis=1)
    return m[np.lexsort(m.T[::-1])].tobytes()


def top_cols(T, idxs, cap=4):
    """At most cap of the columns idxs, chosen by their content so that the choice doesn't depend on column order."""
    if len(idxs) <= cap:
        return idxs
    def sig(i):
        c = T.cols[i]
        h = 0
        for wd in T.worlds:
            for e in sorted(wd):
                if len(wd[e]):
                    h = zlib.crc32(np.sort(colkey(wd[e], c)).tobytes(), h)
        return h
    return sorted(idxs, key=sig)[:cap]


def node_features(types, x_rows, clause, kind, form_depth, form_reads, ctx, with_shape=True):
    d = {}
    ntr, nte = ctx.n_train, ctx.n_test
    T = RD.read_table(types, x_rows, ntr, nte)
    cols = T.cols
    for t in types:
        k = 'tb_t_' + canon_type(t)
        d[k] = d.get(k, 0) + 1
    d['tb_n_cols'] = len(types)
    d['tb_worlds'] = math.log1p(T.n_worlds)
    d['tb_capped'] = float(T.capped)
    d['tb_has_example'] = float(T.has_example)
    d['dp_form_depth'], d['dp_form_reads'], d['dp_kind'] = form_depth, form_reads, KINDS.get(kind, 3)
    A = Acc()
    pos = top_cols(T, [i for i, c in enumerate(cols) if c[0] == 'Position'])
    colr = top_cols(T, [i for i, c in enumerate(cols) if c[0] == 'Color'])
    natc = top_cols(T, [i for i, c in enumerate(cols) if c[0] == 'Nat'])
    boxc = [i for i, c in enumerate(cols) if c[0] == 'Box']
    idc = [i for i, c in enumerate(cols) if c[0] == 'Ident']
    empty_any = empty_all = rows_eq = 0.0
    alt = []
    fgtr = {}
    paint_all = {}
    for wi, world in enumerate(T.worlds):
        nrows = [len(world[e]) if e in world else 0 for e in range(ntr)]
        if ntr:
            empty_any = max(empty_any, float(min(nrows) == 0))
            empty_all = max(empty_all, float(max(nrows) == 0))
            sets = [canon_rows(world[e], cols) for e in range(ntr) if e in world]
            rows_eq = max(rows_eq, float(len(sets) == ntr and len(set(sets)) == 1))
        alt.append(tuple(sorted(canon_rows(world[e], cols) for e in range(ntr) if e in world)))
        bd = T.boxdims[wi]
        for e in range(ntr):
            ex = ctx.train[e]
            a = world.get(e)
            if a is None:
                a = np.zeros((0, T.width), np.int32)
            n = len(a)
            A.add(wi, 'tb_logrows', math.log1p(n))
            A.add(wi, 'tb_empty', float(n == 0))
            A.add(wi, 'tb_onerow', float(n == 1))
            if n:
                nd = [len(np.unique(colkey(a, c))) for c in cols if c[0] != 'Ident']
                if nd:
                    A.add(wi, 'tb_const', sum(x == 1 for x in nd) / len(nd))
                    A.add(wi, 'tb_distinct_mean', _fsum([x / n for x in nd]) / len(nd))
                    A.add(wi, 'tb_distinct_max', max(nd) / n)
                for i in idc:
                    sz = RD.ident_classes(a, cols[i][1])
                    A.add((wi, i), 'tb_ident_classes', len(sz))
                    A.add((wi, i), 'tb_ident_maxshare', sz.max() / n)
                for i in natc:
                    dims = {ex.ho, ex.wo, len(ex.ocolors), ex.h, ex.w}
                    dims2 = {ex.ho, ex.wo, len(ex.ocolors), len(ex.out_objs())}
                    vals = np.unique(a[:, cols[i][1]])
                    A.add((wi, i), 'oc_nat_in_dims', float(np.mean([int(v) in dims for v in vals])))
                    A.add((wi, i), 'oc_nat_dims_out', float(np.mean([int(v) in dims2 for v in vals])))
                for j in colr:
                    cvals = a[:, cols[j][1]]
                    cs = set(int(v) for v in np.unique(cvals))
                    kk = (wi, j)
                    A.add(kk, 'oc_color_in_out', len(cs & ex.ocolors) / len(cs))
                    A.add(kk, 'oc_color_new', float(bool(cs & ex.newcolors)))
                    A.add(kk, 'oc_color_obg', float(ex.obg in cs))
                    hist = np.bincount(cvals.clip(0, 9), minlength=10)[:10]
                    hist = hist / hist.sum()
                    A.add(kk, 'oc_hist_out', float(np.minimum(hist, ex.ohist).sum()))
                    if ex.chist is not None:
                        A.add(kk, 'oc_hist_changed', float(np.minimum(hist, ex.chist).sum()))
                A.add(wi, 'oc_rows_eq_ofg', float(n == ex.nofg))
                A.add(wi, 'oc_ratio_ofg', n / max(ex.nofg, 1))
                if ex.same:
                    A.add(wi, 'oc_rows_eq_changed', float(n == ex.nchanged))
                    A.add(wi, 'oc_ratio_changed', n / max(ex.nchanged, 1))
                if boxc and e in bd:
                    for q in range(len(boxc)):
                        bh, bw = bd[e][:, q, 0], bd[e][:, q, 1]
                        ok = ~np.isnan(bh)
                        if ok.any():
                            A.add((wi, 'b', q), 'oc_box_eq_out', float(((bh[ok] == ex.ho) & (bw[ok] == ex.wo)).all()))
                            A.add((wi, 'b', q), 'oc_box_eq_in', float(((bh[ok] == ex.h) & (bw[ok] == ex.w)).all()))
                for i in pos:
                    r, c = pos_cells(a, cols[i][1])
                    kk = (wi, i)
                    ns = len(r)
                    A.add(kk, 'tb_pos_key', float(ns == n))
                    for j in colr:
                        key = colkey(a, cols[i])
                        u = np.unique(key * 16 + a[:, cols[j][1]])
                        A.add((wi, i, j), 'tb_pos_det_color', float(len(u) == len(np.unique(u // 16))))
                    A.add(kk, 'pr_cover', ns / ex.area)
                    fi, _ = hit(ex.fg, r, c)
                    fgtr.setdefault(kk, []).append(fi / ns)
                    fo, ino = hit(ex.ofg, r, c)
                    A.add(kk, 'pr_in_fg', fi / ns)
                    A.add(kk, 'pr_out_fg', fo / ns)
                    A.add(kk, 'pr_oob', 1 - ino / ns)
                    A.add(kk, 'pr_rec_ofg', fo / max(ex.nofg, 1))
                    A.add(kk, 'pr_iou_ofg', fo / (ns + ex.nofg - fo))
                    nfg = int(ex.fg.sum())
                    A.add(kk, 'pr_rec_ifg', fi / max(nfg, 1))
                    A.add(kk, 'pr_iou_ifg', fi / (ns + nfg - fi))
                    if ex.same:
                        hc, _ = hit(ex.changed, r, c)
                        A.add(kk, 'pr_prec_ch', hc / ns)
                        A.add(kk, 'pr_rec_ch', hc / max(ex.nchanged, 1))
                        A.add(kk, 'pr_iou_ch', hc / (ns + ex.nchanged - hc))
                        A.add(kk, 'pr_unchanged', 1 - hc / ns)
                    m_in = cell_mask(r, c, ex.h, ex.w)
                    m_out = cell_mask(r, c, ex.ho, ex.wo)
                    A.add(kk, 'pr_class_in', float(m_in.tobytes() + bytes(m_in.shape) in ex.incls))
                    A.add(kk, 'pr_class_out', float(m_out.tobytes() + bytes(m_out.shape) in ex.oincls))
                    if m_out.any():
                        A.add(kk, 'pr_one_color_out', float(len(np.unique(ex.b[m_out])) == 1))
                    if ns <= 4000:
                        lab, nc = ndimage.label(m_in, EIGHT)
                        A.add(kk, 'pr_parts', nc / ns)
                        sh = obj_shapes(m_in, ex.area)
                        so = sh & ex.out_objs()
                        A.add(kk, 'pr_shape_in', float(bool(sh & ex.in_objs())))
                        A.add(kk, 'pr_shape_out', float(bool(so)))
                        A.add(kk, 'pr_shape_moved', float(bool(so - ex.in_objs())))
                    A.add(kk, 'oc_fits_out', float((r.max() - r.min() + 1 <= ex.ho) and (c.max() - c.min() + 1 <= ex.wo)))
                    if m_out.any():
                        vals = ex.b[m_out]
                        cnt = np.bincount(vals, minlength=10)
                        v = int(cnt.argmax())
                        cellb = ex.base[m_out]
                        got = int(((vals == v) & (cellb != v)).sum())
                        own = int(((vals != v) & (cellb == vals)).sum())
                        A.add(kk, 'pr_fill_gain', (got - own) / max(ex.base_err, 1))
                        A.add(kk, 'pr_fill_rec', got / max(ex.base_err, 1))
                        A.add(kk, 'pr_fill_one', cnt[v] / cnt.sum())
        # paint of a Position column with a Color column, over all train examples
        for i in pos:
            for j in colr:
                tf = tb = ts = to = tc = 0
                per, remap, rok = [], {}, True
                for e in range(ntr):
                    ex = ctx.train[e]
                    a = world.get(e)
                    if a is None or len(a) == 0:
                        f = b_ = s_ = o_ = c_ = 0
                        cm = ()
                    else:
                        f, b_, s_, o_, c_, cm = paint(ex, a[:, cols[i][1]].astype(np.int64), a[:, cols[i][1] + 2].astype(np.int64), a[:, cols[j][1]].astype(np.int64).clip(0, 15))
                    tf += f; tb += b_; ts += s_; to += o_; tc += c_
                    be = ex.base_err
                    per.append((be - f + b_) / be if be else float(b_ > 0))
                    for k, v in cm:
                        if remap.setdefault(k, v) != v:
                            rok = False
                base = sum(ctx.train[e].base_err for e in range(ntr)) or 1
                err = base - tf + tb
                rmp = rok and any(k != v for k, v in remap.items()) and not tf
                rec = (err / base, -tf, tb, ts, to, tc, tuple(sorted(per)), rmp, base)
                if wi not in paint_all or rec < paint_all[wi]:
                    paint_all[wi] = rec
    best_pair = worst_pair = pairs_exact = remap_ok = None
    for wi, (e_, ntf, tb, ts, to, tc, per, rmp, base) in paint_all.items():
        tf = -ntf
        n_ = tf + tb + ts
        A.add(wi, 'pr_paint_gain', 1 - e_)
        A.add(wi, 'pr_paint_exact', float(e_ == 0 and to == 0))
        A.add(wi, 'pr_paint_rec', tf / base)
        A.add(wi, 'pr_paint_prec', tf / n_ if n_ else 0.0)
        A.add(wi, 'pr_paint_broke', tb / base)
        A.add(wi, 'pr_paint_stale', ts / base)
        A.add(wi, 'pr_paint_wrong', e_)
        A.add(wi, 'pr_paint_oob', float(to > 0))
        A.add(wi, 'pr_paint_conflict', float(tc > 0))
        bp, wp = 1 - min(per), 1 - max(per)
        best_pair = bp if best_pair is None else max(best_pair, bp)
        worst_pair = wp if worst_pair is None else max(worst_pair, wp)
        pe = sum(x == 0 for x in per) / len(per)
        pairs_exact = pe if pairs_exact is None else max(pairs_exact, pe)
        remap_ok = float(rmp) if remap_ok is None else max(remap_ok, float(rmp))
    A.emit(d)
    d['tb_empty_any'], d['tb_empty_all'], d['tb_rows_equal'] = empty_any, empty_all, rows_eq
    d['tb_alt'] = float(len(set(alt)))
    d['pr_paint_best_pair'] = NAN if best_pair is None else best_pair
    d['pr_paint_worst_pair'] = NAN if worst_pair is None else worst_pair
    d['pr_paint_pairs_exact'] = NAN if pairs_exact is None else pairs_exact
    d['pr_paint_remap'] = NAN if remap_ok is None else remap_ok
    # test input group
    if nte and T.worlds:
        lr, rpa, ewt, cin, oob, fgd, cls, shp = [], [], [], [], [], [], [], []
        for wi, world in enumerate(T.worlds):
            trn = [len(world[e]) / ctx.train[e].area if e in world else 0.0 for e in range(ntr)]
            lo, hi = (min(trn), max(trn)) if trn else (0.0, 0.0)
            trows = [len(world[e]) if e in world else 0 for e in range(ntr)]
            for t in range(nte):
                e = ntr + t
                ex = ctx.test[t]
                a = world.get(e)
                n = 0 if a is None else len(a)
                lr.append(math.log1p(n))
                rpa.append(float(lo <= n / ex.area <= hi))
                ewt.append(float(n == 0 and max(trows or [0]) > 0))
                if n:
                    for j in colr:
                        cv = set(int(v) for v in np.unique(a[:, cols[j][1]]))
                        cin.append(len(cv & ex.colors) / len(cv))
                    for i in pos:
                        r, c = pos_cells(a, cols[i][1])
                        fi, ino = hit(ex.fg, r, c)
                        oob.append(1 - ino / len(r))
                        trfs = fgtr.get((wi, i), [])
                        if trfs:
                            fgd.append(fi / len(r) - _fsum(trfs) / len(trfs))
                        m_in = cell_mask(r, c, ex.h, ex.w)
                        cls.append(float(m_in.tobytes() + bytes(m_in.shape) in ex.incls))
                        if len(r) <= 4000:
                            shp.append(float(bool(obj_shapes(m_in, ex.area) & ex.in_objs())))
        d['ti_logrows'] = max(lr)
        d['ti_rows_per_area_in_range'] = min(rpa)
        d['ti_empty_with_train_rows'] = max(ewt)
        if cin: d['ti_colors_inside'] = min(cin)
        if oob: d['ti_oob'] = max(oob)
        if fgd: d['ti_fg_share_delta'] = max(fgd)
        if cls: d['ti_class'] = max(cls)
        if shp: d['ti_shape_in'] = max(shp)
    if with_shape:
        d.update(SH.shape_features(clause, len(types)))
    out = dict.fromkeys(NAMES, NAN)
    for k, v in d.items():
        if k not in out:
            raise KeyError('undeclared feature ' + k)
        out[k] = float(v)
    for t in TYPES + ['other']:
        if out['tb_t_' + t] != out['tb_t_' + t]:
            out['tb_t_' + t] = 0.0
    if not with_shape:
        for k in out:
            if group_of(k) == 'Form shape':
                out[k] = NAN
    return out


def plain_sig(types, x_rows, n_train, n_test):
    """Signature of the plain form of a table: Example, Ident, constant and repeated columns dropped, rows and same-type columns unordered.
    Equal signatures mean one plain form. Computed over the (at most 8) worlds."""
    T = RD.read_table(types, x_rows, n_train, n_test)
    sigs = []
    for world in T.worlds:
        exs = sorted(world)
        keep = []
        seen = set()
        for c in T.cols:
            if c[0] == 'Ident':
                continue
            arrs = [colkey(world[e], c) for e in exs if len(world[e])]
            if not arrs:
                continue
            allv = np.concatenate(arrs)
            if len(np.unique(allv)) <= 1:
                continue
            s = (c[0], zlib.crc32(np.concatenate([np.int64([e]) if False else a for e, a in zip(exs, arrs)]).tobytes()))
            if s in seen:
                continue
            seen.add(s)
            keep.append(c)
        h = zlib.crc32(','.join(sorted(c[0] for c in keep)).encode())
        for e in exs:
            h = zlib.crc32(canon_rows(world[e], keep), zlib.crc32(np.int64(e).tobytes(), h)) if len(world[e]) else zlib.crc32(np.int64(-e - 1).tobytes(), h)
        sigs.append(h)
    return zlib.crc32(np.array(sorted(sigs), np.int64).tobytes()) if sigs else 0
