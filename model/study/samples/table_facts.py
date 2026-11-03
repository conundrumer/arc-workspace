"""The per-table facts of set T (work/lm/data-study/features-worker/results/features-node-score-refit-loop/features_node_feats.py), over a TableAt.

Changes from set T:
- No DET worlds. A TableAt is one table at one assignment, so the facts that read across assignments (`tb_worlds`, `tb_alt`) are not here.
- Several Rows per example. Each per-example fact is computed for each Rows of the example and averaged over them; a feature then combines
  over the examples as before (the mean over examples, the least over examples, the greatest over column choices).
- No Form shape, no depth, no kind: these belong to the function (FunctionVector).
- Columns are chosen by content, so no fact reads a column order (`top_cols`).
- Every fact is a function of the column types, the cells, the rows grouped on the Example column and the train grids.

  table_features(tab, ctx) -> dict name -> float, over FACT_NAMES
"""
import math
import zlib

import numpy as np
from scipy import ndimage  # pyright: ignore[reportMissingImports]

from table_read import EIGHT, Rw, TableAt, TaskCtx, fsum, obj_shapes

NAN = float('nan')
TYPES = ['Position', 'Box', 'Offset', 'Color', 'Ident', 'Nat', 'Int', 'Axis', 'Dir', 'Dir8', 'DiagDir', 'DiagAxis', 'Axis4', 'D4', 'C4', 'Sym', 'Sense', 'Pose']


def canon_type(x: str) -> str:
    return x if x in TYPES else ('Pose' if x.startswith('Pose') else 'other')


PAIR_FACTS = ['pr_cover', 'pr_in_fg', 'pr_out_fg', 'pr_prec_ch', 'pr_rec_ch', 'pr_iou_ch', 'pr_unchanged', 'pr_iou_ofg', 'pr_rec_ofg', 'pr_iou_ifg', 'pr_rec_ifg',
              'pr_class_in', 'pr_class_out', 'pr_one_color_out', 'pr_parts', 'pr_shape_in', 'pr_shape_out', 'pr_shape_moved', 'pr_oob',
              'pr_paint_gain', 'pr_paint_exact', 'pr_paint_rec', 'pr_paint_prec', 'pr_paint_broke', 'pr_paint_stale', 'pr_paint_wrong', 'pr_paint_oob', 'pr_paint_conflict',
              'pr_fill_gain', 'pr_fill_rec', 'pr_fill_one',
              'tb_logrows', 'tb_empty', 'tb_onerow', 'tb_const', 'tb_distinct_mean', 'tb_distinct_max', 'tb_pos_key', 'tb_pos_det_color', 'tb_ident_classes', 'tb_ident_maxshare',
              'oc_hist_out', 'oc_hist_changed', 'oc_fits_out', 'oc_rows_eq_changed', 'oc_rows_eq_ofg', 'oc_ratio_changed', 'oc_ratio_ofg', 'oc_box_eq_out', 'oc_box_eq_in', 'oc_nat_in_dims',
              'oc_color_in_out', 'oc_color_new', 'oc_color_obg', 'oc_nat_dims_out',
              'rows_per_area', 'color_one']  # the last two are new: the hand model's rows_per_area and color_one
SCALARS = ['tb_n_cols', 'tb_empty_any', 'tb_empty_all', 'tb_rows_equal',
           'pr_paint_best_pair', 'pr_paint_worst_pair', 'pr_paint_pairs_exact', 'pr_paint_remap',
           'ti_logrows', 'ti_rows_per_area_in_range', 'ti_empty_with_train_rows', 'ti_colors_inside', 'ti_oob', 'ti_fg_share_delta', 'ti_class', 'ti_shape_in']
FACT_NAMES = sorted(set(['tb_t_' + t for t in TYPES + ['other']] + SCALARS + [f + s for f in PAIR_FACTS for s in ('_mean', '_min')]))
TYPE_NAMES = ['tb_t_' + t for t in TYPES + ['other']] + ['tb_n_cols']  # computed from the column types alone


class Acc:
    """Facts by name, column choice and example, each a list over the example's Rows. `emit` gives name_mean (the mean over examples of the mean over
    Rows) and name_min (the least over examples), each as the greatest over column choices."""

    def __init__(self):
        self.v: dict[str, dict] = {}

    def add(self, key, e: int, name: str, v: float) -> None:
        if v == v:
            self.v.setdefault(name, {}).setdefault(key, {}).setdefault(e, []).append(float(v))

    def per_example(self, name: str) -> dict:
        """key -> list over examples of the mean over Rows."""
        return {k: [fsum(v) / len(v) for _, v in sorted(per.items())] for k, per in self.v.get(name, {}).items()}

    def emit(self, d: dict) -> None:
        for name in self.v:
            ms, mn = [], []
            for means in self.per_example(name).values():
                ms.append(fsum(means) / len(means))
                mn.append(min(means))
            d[name + '_mean'] = max(ms)
            d[name + '_min'] = max(mn)


def colkey(a: np.ndarray, c: tuple[str, int, int]) -> np.ndarray:
    """One int64 per row for the cells of column c (type, start, width)."""
    k = a[:, c[1]].astype(np.int64) + 2048
    for j in range(1, c[2]):
        k = k * 4096 + a[:, c[1] + j] + 2048
    return k


def pos_cells(a: np.ndarray, s: int) -> tuple[np.ndarray, np.ndarray]:
    r, c = a[:, s].astype(np.int64), a[:, s + 2].astype(np.int64)
    code = np.unique(r * 4096 + c + 2048)
    return code // 4096, code % 4096 - 2048


def hit(mask: np.ndarray, r: np.ndarray, c: np.ndarray) -> tuple[int, int]:
    """Cells (r, c) that lie in mask's grid and are set in mask, and the count of those in the grid."""
    h, w = mask.shape
    inb = (r >= 0) & (r < h) & (c >= 0) & (c < w)
    return int(mask[r[inb], c[inb]].sum()), int(inb.sum())


def cell_mask(r: np.ndarray, c: np.ndarray, h: int, w: int) -> np.ndarray:
    m = np.zeros((h, w), bool)
    inb = (r >= 0) & (r < h) & (c >= 0) & (c < w)
    m[r[inb], c[inb]] = True
    return m


def paint(ex, r: np.ndarray, c: np.ndarray, col: np.ndarray) -> tuple[int, int, int, int, int, tuple]:
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
    cw = np.unique(f[~single])
    wasc = ex.base.ravel()[cw] == ex.b.ravel()[cw]
    brokec, stalec = int(wasc.sum()), int((~wasc).sum())
    bad_s = single & (v != want)
    broke = int((bad_s & was).sum()) + brokec
    stale = int((bad_s & ~was).sum()) + stalec
    cm = tuple(zip(v[single].tolist(), want[single].tolist()))
    return fixed, broke, stale, oob, conflict, cm


def canon_rows(a: np.ndarray, cols: list[tuple[str, int, int]]) -> bytes:
    """Bytes of the rows of `a` that don't depend on the order of rows or of same-type columns (Ident cells left out)."""
    if len(a) == 0:
        return b''
    by: dict[str, list] = {}
    for c in cols:
        if c[0] != 'Ident':
            by.setdefault(c[0], []).append(colkey(a, c))
    if not by:
        return b'x' * len(a)
    m = np.concatenate([np.sort(np.stack(by[t], 1), axis=1) for t in sorted(by)], axis=1)
    return m[np.lexsort(m.T[::-1])].tobytes()


def _mix(x: np.ndarray) -> np.ndarray:
    """A 64-bit mix (splitmix64's finalizer) of each element."""
    x = x.astype(np.uint64)
    with np.errstate(over='ignore'):
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return x ^ (x >> np.uint64(31))


def top_cols(tab: TableAt, idxs: list[int], cap: int = 4) -> list[int]:
    """At most cap of the columns idxs, chosen by their content so that the choice depends on no order of columns, rows or Rows. A column's
    signature is the set of its cells joined with the rest of the row, where the rest of the row is the sum over the other columns of a mix of
    their type and cells."""
    if len(idxs) <= cap:
        return idxs
    tid = {t: i + 1 for i, t in enumerate(sorted({c[0] for c in tab.cols}))}

    def sig(i: int) -> int:
        h = 0
        for e in sorted(tab.per_example):
            ds = []
            for rw in tab.per_example[e]:
                a = rw.body
                if not len(a):
                    ds.append(0)
                    continue
                keys = [colkey(a, c) for c in tab.cols]
                hs = [_mix(k + np.int64(tid[c[0]]) * np.int64(1 << 40)) for k, c in zip(keys, tab.cols)]
                rest = sum(hs[j] for j in range(len(hs)) if j != i) if len(hs) > 1 else np.zeros(len(a), np.uint64)
                with np.errstate(over='ignore'):
                    pair = _mix(_mix(keys[i]) + rest * np.uint64(0x9E3779B97F4A7C15))
                ds.append(zlib.crc32(np.sort(pair).tobytes()))
            for d in sorted(ds):
                h = zlib.crc32(int(d).to_bytes(8, 'little'), h)
        return h
    return sorted(idxs, key=sig)[:cap]


def table_features(tab: TableAt, ctx: TaskCtx) -> dict[str, float]:
    d: dict[str, float] = {}
    ntr, nte = ctx.n_train, ctx.n_test
    cols = tab.cols
    for t in tab.types:
        k = 'tb_t_' + canon_type(t)
        d[k] = d.get(k, 0) + 1
    d['tb_n_cols'] = len(tab.types)
    A = Acc()
    pos = top_cols(tab, [i for i, c in enumerate(cols) if c[0] == 'Position'])
    colr = top_cols(tab, [i for i, c in enumerate(cols) if c[0] == 'Color'])
    natc = top_cols(tab, [i for i, c in enumerate(cols) if c[0] == 'Nat'])
    boxc = [i for i, c in enumerate(cols) if c[0] == 'Box']
    idc = [i for i, c in enumerate(cols) if c[0] == 'Ident']
    fgtr: dict[int, dict[int, list[float]]] = {}
    if ntr:
        share_empty = [fsum([float(r.n == 0) for r in tab.rows_of(e)]) / len(tab.rows_of(e)) for e in range(ntr)]
        d['tb_empty_any'], d['tb_empty_all'] = max(share_empty), min(share_empty)
        sets = [tuple(sorted(canon_rows(r.body, cols) for r in tab.per_example[e])) for e in range(ntr) if e in tab.per_example]
        d['tb_rows_equal'] = float(len(sets) == ntr and len(set(sets)) == 1)
    for e in range(ntr):
        ex = ctx.train[e]
        for rw in tab.rows_of(e):
            a, n, k = rw.body, rw.n, len(rw.body)
            A.add(0, e, 'tb_logrows', math.log1p(n))
            A.add(0, e, 'tb_empty', float(n == 0))
            A.add(0, e, 'tb_onerow', float(n == 1))
            A.add(0, e, 'rows_per_area', n / ex.area)
            if not k:
                continue
            nd = [len(np.unique(colkey(a, c))) for c in cols if c[0] != 'Ident']
            if nd:
                A.add(0, e, 'tb_const', sum(x == 1 for x in nd) / len(nd))
                A.add(0, e, 'tb_distinct_mean', fsum([x / k for x in nd]) / len(nd))
                A.add(0, e, 'tb_distinct_max', max(nd) / k)
            for i in idc:
                sz = np.unique(a[:, cols[i][1]], return_counts=True)[1]
                A.add(i, e, 'tb_ident_classes', len(sz))
                A.add(i, e, 'tb_ident_maxshare', sz.max() / k)
            for i in natc:
                dims = {ex.ho, ex.wo, len(ex.ocolors), ex.h, ex.w}
                dims2 = {ex.ho, ex.wo, len(ex.ocolors), len(ex.out_objs())}
                vals = np.unique(a[:, cols[i][1]])
                A.add(i, e, 'oc_nat_in_dims', float(np.mean([int(v) in dims for v in vals])))
                A.add(i, e, 'oc_nat_dims_out', float(np.mean([int(v) in dims2 for v in vals])))
            for j in colr:
                cvals = a[:, cols[j][1]]
                cs = set(int(v) for v in np.unique(cvals))
                A.add(j, e, 'color_one', float(len(cs) == 1))
                A.add(j, e, 'oc_color_in_out', len(cs & ex.ocolors) / len(cs))
                A.add(j, e, 'oc_color_new', float(bool(cs & ex.newcolors)))
                A.add(j, e, 'oc_color_obg', float(ex.obg in cs))
                hist = np.bincount(cvals.clip(0, 9), minlength=10)[:10]
                hist = hist / hist.sum()
                A.add(j, e, 'oc_hist_out', float(np.minimum(hist, ex.ohist).sum()))
                if ex.chist is not None:
                    A.add(j, e, 'oc_hist_changed', float(np.minimum(hist, ex.chist).sum()))
            A.add(0, e, 'oc_rows_eq_ofg', float(n == ex.nofg))
            A.add(0, e, 'oc_ratio_ofg', n / max(ex.nofg, 1))
            if ex.same:
                A.add(0, e, 'oc_rows_eq_changed', float(n == ex.nchanged))
                A.add(0, e, 'oc_ratio_changed', n / max(ex.nchanged, 1))
            if boxc and rw.boxes is not None:
                for q in range(len(boxc)):
                    bh, bw = rw.boxes[:, q, 0], rw.boxes[:, q, 1]
                    ok = ~np.isnan(bh)
                    if ok.any():
                        A.add(('b', q), e, 'oc_box_eq_out', float(((bh[ok] == ex.ho) & (bw[ok] == ex.wo)).all()))
                        A.add(('b', q), e, 'oc_box_eq_in', float(((bh[ok] == ex.h) & (bw[ok] == ex.w)).all()))
            for i in pos:
                r, c = pos_cells(a, cols[i][1])
                ns = len(r)
                A.add(i, e, 'tb_pos_key', float(ns == k))
                for j in colr:
                    key = colkey(a, cols[i])
                    u = np.unique(key * 16 + a[:, cols[j][1]])
                    A.add((i, j), e, 'tb_pos_det_color', float(len(u) == len(np.unique(u // 16))))
                A.add(i, e, 'pr_cover', ns / ex.area)
                fi, _ = hit(ex.fg, r, c)
                fgtr.setdefault(i, {}).setdefault(e, []).append(fi / ns)
                fo, ino = hit(ex.ofg, r, c)
                A.add(i, e, 'pr_in_fg', fi / ns)
                A.add(i, e, 'pr_out_fg', fo / ns)
                A.add(i, e, 'pr_oob', 1 - ino / ns)
                A.add(i, e, 'pr_rec_ofg', fo / max(ex.nofg, 1))
                A.add(i, e, 'pr_iou_ofg', fo / (ns + ex.nofg - fo))
                nfg = int(ex.fg.sum())
                A.add(i, e, 'pr_rec_ifg', fi / max(nfg, 1))
                A.add(i, e, 'pr_iou_ifg', fi / (ns + nfg - fi))
                if ex.changed is not None:
                    hc, _ = hit(ex.changed, r, c)
                    A.add(i, e, 'pr_prec_ch', hc / ns)
                    A.add(i, e, 'pr_rec_ch', hc / max(ex.nchanged, 1))
                    A.add(i, e, 'pr_iou_ch', hc / (ns + ex.nchanged - hc))
                    A.add(i, e, 'pr_unchanged', 1 - hc / ns)
                m_in = cell_mask(r, c, ex.h, ex.w)
                m_out = cell_mask(r, c, ex.ho, ex.wo)
                A.add(i, e, 'pr_class_in', float(m_in.tobytes() + bytes(m_in.shape) in ex.incls))
                A.add(i, e, 'pr_class_out', float(m_out.tobytes() + bytes(m_out.shape) in ex.oincls))
                if m_out.any():
                    A.add(i, e, 'pr_one_color_out', float(len(np.unique(ex.b[m_out])) == 1))
                if ns <= 4000:
                    _, nc = ndimage.label(m_in, EIGHT)
                    A.add(i, e, 'pr_parts', nc / ns)
                    sh = obj_shapes(m_in, ex.area)
                    so = sh & ex.out_objs()
                    A.add(i, e, 'pr_shape_in', float(bool(sh & ex.in_objs())))
                    A.add(i, e, 'pr_shape_out', float(bool(so)))
                    A.add(i, e, 'pr_shape_moved', float(bool(so - ex.in_objs())))
                A.add(i, e, 'oc_fits_out', float((r.max() - r.min() + 1 <= ex.ho) and (c.max() - c.min() + 1 <= ex.wo)))
                if m_out.any():
                    vals = ex.b[m_out]
                    cnt = np.bincount(vals, minlength=10)
                    v = int(cnt.argmax())
                    cellb = ex.base[m_out]
                    got = int(((vals == v) & (cellb != v)).sum())
                    own = int(((vals != v) & (cellb == vals)).sum())
                    A.add(i, e, 'pr_fill_gain', (got - own) / max(ex.base_err, 1))
                    A.add(i, e, 'pr_fill_rec', got / max(ex.base_err, 1))
                    A.add(i, e, 'pr_fill_one', cnt[v] / cnt.sum())
    paint_facts(tab, ctx, pos, colr, A, d)
    A.emit(d)
    if nte and tab.per_example:
        test_input_facts(tab, ctx, pos, colr, fgtr, d)
    out = dict.fromkeys(FACT_NAMES, NAN)
    for k, v in d.items():
        if k not in out:
            raise KeyError('undeclared feature ' + k)
        out[k] = float(v)
    for t in TYPES + ['other']:
        if out['tb_t_' + t] != out['tb_t_' + t]:
            out['tb_t_' + t] = 0.0
    return out


def paint_facts(tab: TableAt, ctx: TaskCtx, pos: list[int], colr: list[int], A: Acc, d: dict) -> None:
    """Paint of a Position column with a Color column onto the train inputs, over all train examples. Per example the counts are the mean over
    its Rows; the pair of columns with the least error is kept."""
    ntr, cols = ctx.n_train, tab.cols
    best = None
    for i in pos:
        for j in colr:
            tf = tb = ts = to = tc = 0.0
            per, remap, rok = [], {}, True
            for e in range(ntr):
                ex = ctx.train[e]
                rs = tab.rows_of(e)
                sums = np.zeros(5)
                pe = []
                for rw in rs:
                    a = rw.body
                    if len(a) == 0:
                        f = b_ = s_ = o_ = c_ = 0
                        cm: tuple = ()
                    else:
                        f, b_, s_, o_, c_, cm = paint(ex, a[:, cols[i][1]].astype(np.int64), a[:, cols[i][1] + 2].astype(np.int64),
                                                      a[:, cols[j][1]].astype(np.int64).clip(0, 15))
                    sums += (f, b_, s_, o_, c_)
                    be = ex.base_err
                    pe.append((be - f + b_) / be if be else float(b_ > 0))
                    for kk, v in cm:
                        if remap.setdefault(kk, v) != v:
                            rok = False
                tf += sums[0] / len(rs)
                tb += sums[1] / len(rs)
                ts += sums[2] / len(rs)
                to += sums[3] / len(rs)
                tc += sums[4] / len(rs)
                per.append(fsum(pe) / len(pe))
            base = sum(ctx.train[e].base_err for e in range(ntr)) or 1
            err = base - tf + tb
            rmp = rok and any(kk != v for kk, v in remap.items()) and not tf
            rec = (err / base, -tf, tb, ts, to, tc, tuple(sorted(per)), rmp, base)
            if best is None or rec < best:
                best = rec
    if best is None:
        return
    e_, ntf, tb, ts, to, tc, per, rmp, base = best
    tf = -ntf
    n_ = tf + tb + ts
    for name, v in (('pr_paint_gain', 1 - e_), ('pr_paint_exact', float(e_ == 0 and to == 0)), ('pr_paint_rec', tf / base),
                    ('pr_paint_prec', tf / n_ if n_ else 0.0), ('pr_paint_broke', tb / base), ('pr_paint_stale', ts / base),
                    ('pr_paint_wrong', e_), ('pr_paint_oob', float(to > 0)), ('pr_paint_conflict', float(tc > 0))):
        d[name + '_mean'] = d[name + '_min'] = v
    d['pr_paint_best_pair'] = 1 - min(per)
    d['pr_paint_worst_pair'] = 1 - max(per)
    d['pr_paint_pairs_exact'] = sum(x == 0 for x in per) / len(per)
    d['pr_paint_remap'] = float(rmp)


def test_input_facts(tab: TableAt, ctx: TaskCtx, pos: list[int], colr: list[int], fgtr: dict[int, dict[int, list[float]]], d: dict) -> None:
    """The test input group: per test input, the facts of each of its Rows averaged; then the greatest (or least) over test inputs and columns."""
    ntr, nte, cols = ctx.n_train, ctx.n_test, tab.cols
    trn = [fsum([r.n for r in tab.rows_of(e)]) / len(tab.rows_of(e)) for e in range(ntr)]
    area = [ctx.train[e].area for e in range(ntr)]
    ratio = [n / a for n, a in zip(trn, area)]
    lo, hi = (min(ratio), max(ratio)) if ratio else (0.0, 0.0)
    maxtr = max(trn or [0.0])
    T = Acc()
    train_fg = {i: fsum([fsum(v) / len(v) for v in per.values()]) / len(per) for i, per in fgtr.items()}
    for t in range(nte):
        e, ex = ntr + t, ctx.test[t]
        for rw in tab.rows_of(e):
            n, a = rw.n, rw.body
            T.add(0, t, 'lr', math.log1p(n))
            T.add(0, t, 'rpa', float(lo <= n / ex.area <= hi))
            T.add(0, t, 'ewt', float(n == 0 and maxtr > 0))
            if not len(a):
                continue
            for j in colr:
                cv = set(int(v) for v in np.unique(a[:, cols[j][1]]))
                T.add(('c', j), t, 'cin', len(cv & ex.colors) / len(cv))
            for i in pos:
                r, c = pos_cells(a, cols[i][1])
                fi, ino = hit(ex.fg, r, c)
                T.add(('p', i), t, 'oob', 1 - ino / len(r))
                if i in train_fg:
                    T.add(('p', i), t, 'fgd', fi / len(r) - train_fg[i])
                m_in = cell_mask(r, c, ex.h, ex.w)
                T.add(('p', i), t, 'cls', float(m_in.tobytes() + bytes(m_in.shape) in ex.incls))
                if len(r) <= 4000:
                    T.add(('p', i), t, 'shp', float(bool(obj_shapes(m_in, ex.area) & ex.in_objs())))

    def over(name: str, how) -> float | None:
        v = [x for means in T.per_example(name).values() for x in means]
        return how(v) if v else None

    for out, name, how in (('ti_logrows', 'lr', max), ('ti_rows_per_area_in_range', 'rpa', min), ('ti_empty_with_train_rows', 'ewt', max),
                           ('ti_colors_inside', 'cin', min), ('ti_oob', 'oob', max), ('ti_fg_share_delta', 'fgd', max), ('ti_class', 'cls', max),
                           ('ti_shape_in', 'shp', max)):
        v = over(name, how)
        if v is not None:
            d[out] = v


def empty_rows(tab: TableAt) -> Rw:
    return tab.empty
