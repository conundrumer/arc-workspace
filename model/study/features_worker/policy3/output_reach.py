"""Features of a table that point toward the task's output (explorer b).

A table is read as cell views: each Position column is a set of cells, each Box column is a set of rectangles (margins: top, bottom, left, right), and each Ident
column resolves, through an available table that pairs Idents with Positions or Boxes, to cells. Rows with an Example column are split by it. All of this reads
rows and the task's train grids, never the answer.

hb1 reach: output changes sit where a table's cells can reach. The share of changed cells (or of connected changed regions) that a view of the table touches by
    8-neighbour dilation, by sharing a row or column, or by sharing a diagonal, minus the share of the grid that the same reach covers. Seeds and generators of a
    change score high at any depth, where cell-for-cell overlap with the change scores zero.
hb2 attr: the attributes of a table's cells (Dir, Nat, Int, Axis, Color, Sym, D4, Offset, and the displacement to a second Position column) predict what the cell
    turns into (kept, or the output color). Leave-one-out majority accuracy per attribute value, minus the accuracy without the attribute.
hb3 paint: the colors that the output paints on changed cells (the output colors of the output's non-background cells, where sizes differ) against the values
    of the table's Color columns, by recall, by exact set equality per example, and by the same set at every example.
hb4 extent: the bounding box of a view against the box of the changed cells (same size), and the size of a view's connected regions or boxes against the size of
    the output (crop and tile tasks).
hb5 residual: reach of a view onto the changed cells that no earlier, small table of the point reaches. Tables that the clause already reads and tables of the
    prefix mark the cells they cover; a new table that reaches what they leave out scores high.
"""
import collections

import numpy as np
from scipy import ndimage

WIDE = {'Position': 4, 'Box': 4, 'Offset': 4}
ATTR_TYPES = ('Dir', 'Dir8', 'Nat', 'Int', 'Axis', 'Color', 'Sym', 'D4')
EIGHT = np.ones((3, 3), dtype=int)
MAXCELLS = 4000


def _prep(ctx):
    """Per-point facts, kept in ctx['_hb']."""
    if '_hb' in ctx:
        return ctx['_hb']
    ex = []
    for p in ctx['train']:
        a, b = np.array(p['input']), np.array(p['output'])
        same = a.shape == b.shape
        d = dict(a=a, b=b, same=same, H=a.shape[0], W=a.shape[1])
        if same:
            ch = a != b
            lab, n = ndimage.label(ch, structure=EIGHT)
            d.update(ch=ch, lab=lab, ncomp=n, nch=int(ch.sum()))
        else:
            bg = collections.Counter(b.ravel().tolist()).most_common(1)[0][0]
            d.update(ofg=b != bg, obg=bg)
        ex.append(d)
    st = dict(ex=ex, ident=None, small=None)
    ctx['_hb'] = st
    return st


_IDX = {}


def _idx(shape):
    """(row - col, row + col) index grids of a shape."""
    if shape not in _IDX:
        rr, cc = np.indices(shape)
        _IDX[shape] = (rr - cc, rr + cc)
    return _IDX[shape]


def _widths(types, rowlen):
    for off in (4, 1):
        w = [off if t == 'Offset' else WIDE.get(t, 1) for t in types]
        if sum(w) == rowlen:
            return w
    return None


def _split(node, ctx, nt):
    """(types, widths, offsets, {example: ndarray of rows}) for train examples 0..nt-1, or None. Kept per token in ctx['_hb']."""
    cache = _prep(ctx).setdefault('split', {})
    tok = node.get('token')
    if tok in cache:
        return cache[tok]
    r = _split_raw(node, ctx, nt)
    cache[tok] = r
    return r


def _split_raw(node, ctx, nt):
    types = node.get('table_types') or node.get('types') or []
    xr = node.get('x_rows') or []
    if not types or not xr:
        return None
    w = None
    out = {}
    glob = []
    for ent in xr:
        (a, e), rows = ent[0], ent[1]
        if not rows:
            continue
        if w is None:
            w = _widths(types, len(rows[0]))
            if w is None:
                return None
        arr = np.asarray(rows, dtype=np.int64)
        if arr.ndim != 2 or arr.shape[1] != sum(w):
            return None
        if a == 1:
            if e < nt:
                out[e] = arr
        elif a == 0:
            glob.append(arr)
    if w is None:
        return None
    off = np.concatenate([[0], np.cumsum(w)])[:-1].tolist()
    for arr in glob:
        if types[0] == 'Example':
            col = arr[:, 0]
            for e in np.unique(col):
                if 0 <= e < nt:
                    out.setdefault(int(e), arr[col == e])
        else:
            for e in range(nt):
                out.setdefault(e, arr)
    return types, w, off, out


def _mask_pos(rows, o, shape):
    r, c = rows[:, o], rows[:, o + 2]
    m = np.zeros(shape, dtype=bool)
    ok = (r >= 0) & (c >= 0) & (r < shape[0]) & (c < shape[1])
    m[r[ok], c[ok]] = True
    return m


def _mask_box(rows, o, shape):
    m = np.zeros(shape, dtype=bool)
    H, W = shape
    for t, b, l, r in np.unique(rows[:, o:o + 4], axis=0)[:200]:
        r0, r1, c0, c1 = max(t, 0), H - b, max(l, 0), W - r
        if r1 > r0 and c1 > c0:
            m[r0:r1, c0:c1] = True
    return m


def _idents(ctx):
    """{example: {ident: mask}} from the available tables that pair an Ident with a Position or a Box."""
    st = _prep(ctx)
    if st['ident'] is not None:
        return st['ident']
    nt = len(st['ex'])
    best = {}
    for n in ctx['available']:
        types = n.get('table_types') or []
        if 'Ident' not in types or n.get('arity', 0) > 6:
            continue
        pos = 'Position' in types
        if not pos and 'Box' not in types:
            continue
        sp = _split(n, ctx, nt)
        if sp is None:
            continue
        _, w, off, per = sp
        ii = types.index('Ident')
        k = types.index('Position') if pos else types.index('Box')
        for e, rows in per.items():
            shape = st['ex'][e]['a'].shape
            for idv in np.unique(rows[:, off[ii]]):
                sub = rows[rows[:, off[ii]] == idv]
                m = _mask_pos(sub, off[k], shape) if pos else _mask_box(sub, off[k], shape)
                cur = best.setdefault(e, {}).get(int(idv))
                if cur is None or (pos and not cur[1]):
                    best[e][int(idv)] = (m, pos)
    st['ident'] = {e: {i: v[0] for i, v in d.items()} for e, d in best.items()}
    return st['ident']


def _views(node, ctx):
    """[(kind, column, {example: mask})] and the split. A view is a Position, Box or Ident column read as cells."""
    st = _prep(ctx)
    cache = st.setdefault('views', {})
    tok = node.get('token')
    if tok in cache:
        return cache[tok]
    cache[tok] = r = _views_raw(node, ctx)
    return r


def _pdims(rows, o):
    """The grid that a Position column indexes: (height, width), from the margins that each Position carries."""
    h, w = int(rows[0, o] + rows[0, o + 1] + 1), int(rows[0, o + 2] + rows[0, o + 3] + 1)
    return (h, w) if h >= 1 and w >= 1 else (1, 1)


def _views_raw(node, ctx):
    st = _prep(ctx)
    nt = len(st['ex'])
    sp = _split(node, ctx, nt)
    if sp is None:
        return None, None
    types, w, off, per = sp
    ids = None
    views = []
    first = next((k for k, t in enumerate(types) if t == 'Position'), None)
    for k, t in enumerate(types):
        if t not in ('Position', 'Box', 'Ident'):
            continue
        d = {}
        for e, rows in per.items():
            if first is not None:
                shape = _pdims(rows, off[first])
            else:
                shape = st['ex'][e]['a'].shape
            if shape[0] * shape[1] > 2500:
                continue
            if t == 'Position':
                d[e] = _mask_pos(rows, off[k], shape)
            elif t == 'Box':
                d[e] = _mask_box(rows, off[k], shape)
            else:
                if ids is None:
                    ids = _idents(ctx)
                m = np.zeros(shape, dtype=bool)
                got = ids.get(e, {})
                for v in np.unique(rows[:, off[k]])[:300]:
                    g = got.get(int(v))
                    if g is not None and g.shape == shape:
                        m |= g
                d[e] = m
        views.append((t, k, d))
    return views, sp


def _reach(m, ex):
    """The reach masks of the cells m: 8-neighbour dilation, shared row or column, shared diagonal."""
    n = ndimage.binary_dilation(m, structure=EIGHT)
    rc = m.any(1)[:, None] | m.any(0)[None, :]
    df, sm = _idx(m.shape)
    dg = np.isin(df, df[m]) | np.isin(sm, sm[m])
    return n, rc, dg


def _lift(hit, dens):
    return (hit - dens) / (1.0 - dens) if dens < 1.0 else 0.0


def _reach_scores(m, ex, target):
    """Lifts of the three reaches onto target (a mask), and the share of target components that the dilation touches."""
    area = m.size
    t = target
    nt_ = int(t.sum())
    if nt_ == 0:
        return None
    if not m.any():
        return dict(n=0.0, rc=0.0, dg=0.0, comp=0.0, comp_rc=0.0, direct=0.0)
    n, rc, dg = _reach(m, ex)
    out = {}
    for k, r in (('n', n), ('rc', rc), ('dg', dg)):
        out[k] = _lift(float((r & t).sum()) / nt_, float(r.sum()) / area)
    if 'lab' in ex and t is ex['ch']:
        labs = np.unique(ex['lab'][n & (ex['lab'] > 0)])
        out['comp'] = _lift(len(labs) / max(ex['ncomp'], 1), float(n.sum()) / area)
        labs2 = np.unique(ex['lab'][m & (ex['lab'] > 0)])
        out['direct'] = len(labs2) / max(ex['ncomp'], 1)
        labs3 = np.unique(ex['lab'][rc & (ex['lab'] > 0)])
        out['comp_rc'] = _lift(len(labs3) / max(ex['ncomp'], 1), float(rc.sum()) / area)
    else:
        out['comp'] = out['n']
        out['comp_rc'] = out['rc']
        out['direct'] = float((m & t).sum()) / nt_
    return out


def _target(ex, shape):
    """The mask that output cells to explain, for a view on a grid of this shape; None where unknown."""
    if ex['same'] and shape == ex['a'].shape:
        return ex['ch']
    if not ex['same'] and shape == ex['b'].shape:
        return ex['ofg']
    return None


def hb1(node, ctx):
    views, sp = _views(node, ctx)
    if not views:
        return {}
    st = _prep(ctx)
    best = None
    for t, k, d in views:
        rows = collections.defaultdict(list)
        for e, m in d.items():
            ex = st['ex'][e]
            tg = _target(ex, m.shape)
            if tg is None:
                continue
            sc = _reach_scores(m, ex, tg)
            if sc is None:
                continue
            for key, v in sc.items():
                rows[key].append(v)
        if not rows or not rows['n']:
            continue
        agg = {key: float(np.mean(v)) for key, v in rows.items()}
        agg['n_min'] = float(np.min(rows['n']))
        agg['rc_min'] = float(np.min(rows['rc']))
        agg['_s'] = max(agg['n'], agg['rc'], agg['dg'])
        if best is None or agg['_s'] > best['_s']:
            best = agg
    if best is None:
        return {}
    return {'hb1_' + k: v for k, v in best.items() if k != '_s'} | {'hb1_best': best['_s']}


def _attr_cols(types, w, off):
    return [(k, off[k], w[k]) for k, t in enumerate(types) if t in ATTR_TYPES or t == 'Offset']


def _loo_acc(keys, outs):
    """Leave-one-out accuracy of predicting outs (ints in 0..11) from keys (int codes) by the majority of the other cells with the same key. A tie counts one half."""
    keys = np.asarray(keys); outs = np.asarray(outs)
    if len(keys) == 0:
        return 0.0
    g = np.unique(keys, return_inverse=True)[1].ravel()
    m = np.bincount(g * 12 + outs, minlength=(g.max() + 1) * 12).reshape(-1, 12)
    srt = -np.sort(-m, axis=1)
    cnt = m[g, outs]
    other = np.where(cnt < srt[g, 0], srt[g, 0], srt[g, 1])
    co = cnt - 1
    return float(((co > other) + 0.5 * ((co == other) & (co > 0))).sum() / len(keys))


def _codes(a):
    """Int codes of the rows of a 2-d array."""
    out = np.zeros(len(a), dtype=np.int64)
    for j in range(a.shape[1]):
        col = a[:, j] - a[:, j].min()
        out = out * (int(col.max()) + 1) + col
    return out


def hb2(node, ctx):
    st = _prep(ctx)
    nt = len(st['ex'])
    sp = _split(node, ctx, nt)
    if sp is None:
        return {}
    types, w, off, per = sp
    pos = [k for k, t in enumerate(types) if t == 'Position']
    if not pos:
        return {}
    attrs = _attr_cols(types, w, off)
    p0 = pos[0]
    outs, incol = [], []
    cols = collections.defaultdict(list)
    for e, rows in per.items():
        ex = st['ex'][e]
        gs = _pdims(rows, off[p0])
        a, b = ex['a'], ex['b']
        if ex['same'] and gs == a.shape:
            src = a
        elif not ex['same'] and gs == b.shape:
            src = None
        else:
            continue
        r, c = rows[:, off[p0]], rows[:, off[p0] + 2]
        ok = (r >= 0) & (c >= 0) & (r < gs[0]) & (c < gs[1])
        if ok.sum() == 0:
            continue
        rows = rows[ok][:1500]
        r, c = rows[:, off[p0]], rows[:, off[p0] + 2]
        if src is not None:
            outs.append(np.where(a[r, c] == b[r, c], 0, b[r, c] + 1))
            incol.append(a[r, c])
        else:
            outs.append(b[r, c] + 1)
            incol.append(np.zeros(len(r), dtype=int))
        for k, o, wd in attrs:
            cols['a%d' % k].append(rows[:, o:o + wd])
        if len(pos) > 1:
            q = pos[1]
            cols['d'].append(np.stack([rows[:, off[q]] - r, rows[:, off[q] + 2] - c], 1))
    if not outs:
        return {}
    outs = np.concatenate(outs); incol = np.concatenate(incol)
    if len(outs) < 4:
        return {}
    base = _loo_acc(np.zeros(len(outs), int), outs)
    res = {'hb2_base_acc': base, 'hb2_in_acc': _loo_acc(incol, outs)}
    best = best_in = 0.0
    for nm, parts in cols.items():
        a_ = np.concatenate(parts)
        if len(a_) != len(outs):
            continue
        code = _codes(a_)
        best = max(best, _loo_acc(code, outs))
        best_in = max(best_in, _loo_acc(code * 11 + incol, outs))
    if cols:
        res['hb2_attr_acc'] = best
        res['hb2_attr_gain'] = (best - base) / (1 - base) if base < 1 else 0.0
        res['hb2_attr_in_acc'] = best_in
        res['hb2_attr_in_gain'] = (best_in - base) / (1 - base) if base < 1 else 0.0
    return res


def hb3(node, ctx):
    st = _prep(ctx)
    nt = len(st['ex'])
    sp = _split(node, ctx, nt)
    if sp is None:
        return {}
    types, w, off, per = sp
    cols = [off[k] for k, t in enumerate(types) if t == 'Color']
    if not cols:
        return {}
    rec, exact, prec, per_ex = [], [], [], []
    for e, ex in enumerate(st['ex']):
        if e not in per:
            continue
        if ex['same']:
            if ex['nch'] == 0:
                continue
            paint = set(ex['b'][ex['ch']].tolist())
        else:
            paint = set(ex['b'][ex['ofg']].tolist())
        if not paint:
            continue
        best = None
        for o in cols:
            vs = set(per[e][:, o].tolist())
            r = len(vs & paint) / len(paint)
            p = len(vs & paint) / len(vs) if vs else 0.0
            sc = (r, vs == paint, p)
            if best is None or sc > best:
                best = sc
        rec.append(best[0]); exact.append(float(best[1])); prec.append(best[2])
    if not rec:
        return {}
    d = {'hb3_paint_rec': float(np.mean(rec)), 'hb3_paint_exact': float(np.mean(exact)), 'hb3_paint_prec': float(np.mean(prec)),
         'hb3_paint_rec_min': float(np.min(rec))}
    return d


def _bbox(m):
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return None
    return ys.min(), xs.min(), ys.max(), xs.max()


def _iou_box(a, b):
    if a is None or b is None:
        return 0.0
    ih = max(0, min(a[2], b[2]) - max(a[0], b[0]) + 1)
    iw = max(0, min(a[3], b[3]) - max(a[1], b[1]) + 1)
    inter = ih * iw
    ua = (a[2] - a[0] + 1) * (a[3] - a[1] + 1) + (b[2] - b[0] + 1) * (b[3] - b[1] + 1) - inter
    return inter / ua


def hb4(node, ctx):
    views, sp = _views(node, ctx)
    if not views:
        return {}
    st = _prep(ctx)
    best = None
    for t, k, d in views:
        iou, crop, tile, cover = [], [], [], []
        for e, m in d.items():
            ex = st['ex'][e]
            bh, bw = ex['b'].shape
            bb = _bbox(m)
            if bb is None:
                iou.append(0.0); crop.append(0.0); tile.append(0.0)
                continue
            if ex['same'] and m.shape == ex['a'].shape:
                iou.append(_iou_box(bb, _bbox(ex['ch'])) if ex['nch'] else 0.0)
            h, wd = bb[2] - bb[0] + 1, bb[3] - bb[1] + 1
            if not ex['same'] and m.shape == ex['a'].shape:
                crop.append(float((h, wd) == (bh, bw)))
                lab, n = ndimage.label(m, structure=EIGHT)
                hit = 0.0
                for sl in ndimage.find_objects(lab)[:200]:
                    if sl[0].stop - sl[0].start == bh and sl[1].stop - sl[1].start == bw:
                        hit = 1.0
                        break
                tile.append(hit)
            else:
                crop.append(0.0)
        cand = {}
        if iou:
            cand['iou'] = float(np.mean(iou)); cand['iou_min'] = float(np.min(iou))
        if crop and any(not st['ex'][e]['same'] and d[e].shape == st['ex'][e]['a'].shape for e in d):
            cand['crop'] = float(np.mean(crop)); cand['region'] = float(np.mean(tile))
        s = cand.get('iou', 0) + cand.get('crop', 0) + cand.get('region', 0)
        if best is None or s > best[0]:
            best = (s, cand)
    if best is None:
        return {}
    return {'hb4_' + k: v for k, v in best[1].items()}


def _small_cover(ctx, e, shape):
    """The union of the small available views at example e, as a mask; small means under a third of the grid."""
    st = _prep(ctx)
    if st['small'] is None:
        nt = len(st['ex'])
        cov = {}
        for n in ctx['available']:
            if (n.get('arity') or 0) > 8:
                continue
            views, _ = _views(n, ctx)
            for t, k, d in views or ():
                for ee, m in d.items():
                    if m.sum() <= m.size / 3:
                        key = (ee, m.shape)
                        cov[key] = cov[key] | m if key in cov else m.copy()
        st['small'] = cov
    return st['small'].get((e, shape))


def hb5(node, ctx):
    views, sp = _views(node, ctx)
    if not views:
        return {}
    st = _prep(ctx)
    best = None
    for t, k, d in views:
        sc_n, sc_rc, gain = [], [], []
        for e, m in d.items():
            ex = st['ex'][e]
            if not (ex['same'] and m.shape == ex['a'].shape) or ex['nch'] == 0:
                continue
            old = _small_cover(ctx, e, m.shape)
            ch = ex['ch']
            if old is not None and old.any():
                reached = ndimage.binary_dilation(old, structure=EIGHT) | (old.any(1)[:, None] | old.any(0)[None, :])
                resid = ch & ~reached
            else:
                resid = ch
            if not resid.any():
                continue
            n, rc, _ = _reach(m, ex) if m.any() else (m, m, m)
            sc_n.append(_lift(float((n & resid).sum()) / resid.sum(), float(n.sum()) / m.size))
            sc_rc.append(_lift(float((rc & resid).sum()) / resid.sum(), float(rc.sum()) / m.size))
            gain.append(float(resid.sum()) / ex['nch'])
        if not sc_n:
            continue
        cand = {'hb5_resid_n': float(np.mean(sc_n)), 'hb5_resid_rc': float(np.mean(sc_rc)), 'hb5_resid_share': float(np.mean(gain))}
        s = max(cand['hb5_resid_n'], cand['hb5_resid_rc'])
        if best is None or s > best[0]:
            best = (s, cand)
    return best[1] if best else {}


def hb6(node, ctx):
    """The grid that the Position columns index, against the input and the output: a table in the output's space, or in a cell space that tiles the output."""
    st = _prep(ctx)
    nt = len(st['ex'])
    sp = _split(node, ctx, nt)
    if sp is None:
        return {}
    types, w, off, per = sp
    pos = [off[k] for k, t in enumerate(types) if t == 'Position']
    if not pos:
        return {}
    n_out = n_in = n_oth = n_tile = n_sub = 0
    f_out = []
    consts = []
    for o in pos:
        lab = []
        dims = set()
        for e, rows in per.items():
            if len(rows) == 0:
                continue
            ex = st['ex'][e]
            gs = _pdims(rows, o)
            dims.add(gs)
            ish, osh = ex['a'].shape, ex['b'].shape
            if gs == ish:
                lab.append('in')
            elif gs == osh:
                lab.append('out')
            else:
                lab.append('oth')
                if gs[0] <= osh[0] and gs[1] <= osh[1] and osh[0] % gs[0] == 0 and osh[1] % gs[1] == 0:
                    lab.append('tile')
                    lab.pop(-2)
                elif gs[0] < ish[0] and gs[1] < ish[1]:
                    lab.append('sub')
                    lab.pop(-2)
        if not lab:
            continue
        c = collections.Counter(lab)
        top = c.most_common(1)[0][0]
        n_out += top == 'out'; n_in += top == 'in'; n_oth += top == 'oth'; n_tile += top == 'tile'; n_sub += top == 'sub'
        f_out.append(c['out'] / len(lab))
        consts.append(float(len(dims) == 1))
    if not f_out:
        return {}
    anydiff = any(not e['same'] for e in st['ex'])
    return {'hb6_n_out': float(n_out), 'hb6_n_in': float(n_in), 'hb6_n_tile': float(n_tile), 'hb6_n_sub': float(n_sub), 'hb6_n_oth': float(n_oth),
            'hb6_out_share': float(np.mean(f_out)) if anydiff else -1.0, 'hb6_dims_const': float(np.mean(consts))}


def hb7(node, ctx):
    """Numbers in the table against the output's size: a Nat, Int or Offset column that holds the output's height or width, or the ratio of output to input."""
    st = _prep(ctx)
    nt = len(st['ex'])
    sp = _split(node, ctx, nt)
    if sp is None:
        return {}
    types, w, off, per = sp
    cols = [(off[k], w[k]) for k, t in enumerate(types) if t in ('Nat', 'Int')]
    if not cols or not any(not e['same'] for e in st['ex']):
        return {}
    hits, hits_ratio = [], []
    for o, wd in cols:
        h = r = 0
        n = 0
        for e, rows in per.items():
            if len(rows) == 0:
                continue
            ex = st['ex'][e]
            vals = set(rows[:, o].tolist())
            bh, bw = ex['b'].shape
            ah, aw = ex['a'].shape
            n += 1
            h += bool(vals & {bh, bw})
            ratios = set()
            for p, q in ((bh, ah), (bw, aw), (ah, bh), (aw, bw)):
                if q and p % q == 0:
                    ratios.add(p // q)
            r += bool(vals & (ratios - {1}))
        if n:
            hits.append(h / n); hits_ratio.append(r / n)
    if not hits:
        return {}
    return {'hb7_dim_hit': max(hits), 'hb7_ratio_hit': max(hits_ratio)}


def hb(node, ctx):
    d = {}
    for f in (hb1, hb2, hb3, hb4, hb5, hb6, hb7):
        try:
            d.update(f(node, ctx))
        except Exception:
            pass
    return {k: float(v) for k, v in d.items()}


FEATURE_FUNCS = {'hb': hb}
PARTS = {'hb1': hb1, 'hb2': hb2, 'hb3': hb3, 'hb4': hb4, 'hb5': hb5, 'hb6': hb6, 'hb7': hb7}
