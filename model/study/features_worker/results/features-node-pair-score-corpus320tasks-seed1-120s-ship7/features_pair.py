"""Second-order (pair) content features for two pool nodes.

  sk = sketch(node, pairs)       # once per node, when its rows are available. A few KB.
  d  = features(sk_a, sk_b)      # {name: float}, symmetric in (a, b). Reads two sketches only.

`node` is a node record (fields: types, table_types, arity, depth, parents, x_rows, token; `tags` is never read).
`pairs` is the list of the task's train pairs as `Pair` objects (nodefeat.Pair): .a input grid, .b output grid.
Neither function reads gold, test outputs, task ids, node age/order, or `tags`.

Sketch: each table column becomes one Python int used as a bit set.
  Position column  bit  e*900 + i*30 + j          (cell (i, j) of train example e; a table with no example column is copied to every e)
  Color column     bit  e*16 + color
  other types      bit  hash(value) % 512         (a Bloom set over all examples)
A Position column and a Color column of one table also give a bit set of cells per color ('cm').
The task's target masks (changed cells, output foreground, cells that become color k) are built once per task and shared by reference.
"""
import itertools
import re

_WORD = re.compile(r'\((?!:)([A-Za-z_][A-Za-z_0-9.]*)')

CELL = 900          # bits per example in a Position set
SIDE = 30
CSTRIDE = 16        # bits per example in a Color set
BLOOM = 512
WIDE = {'Position': 4, 'Box': 4}
MAXC = 3            # columns used per type

FEATURES = {
    # --- type profile of the pair
    'ty_shared': 'Number of column types the two tables share (multiset intersection).',
    'ty_jacc': 'Jaccard overlap of the two tables\' column-type sets.',
    'ty_share_pos': 'Both tables have a Position column.',
    'ty_share_col': 'Both tables have a Color column.',
    'ty_share_oth': 'Number of shared column types other than Position and Color.',
    'ty_complement': 'One table has a Position column and no Color column, and the other has a Color column and no Position column.',
    'ty_pos_n': 'Number of the two tables that have a Position column (0 to 2).',
    'ty_ncols_min': 'Smaller column count of the two tables.',
    'ty_ncols_max': 'Larger column count of the two tables.',
    # --- size and context
    'sz_rows_min_log': 'log2(1 + rows) of the smaller table, rows summed over train examples.',
    'sz_rows_max_log': 'log2(1 + rows) of the larger table.',
    'sz_small_any': 'One table has at most 1 row per example (a parameter table).',
    'sz_ctx_overlap': 'Share of train examples where both tables are non-empty.',
    'sz_ctx_min': 'Smaller share of train examples with a non-empty table.',
    'sz_glob_any': 'One table has no example column (the same rows for every example).',
    # --- Position columns joined on the cell
    'pos_jacc': 'Jaccard of the two Position sets (best column pair by Jaccard).',
    'pos_cont_lo': 'Smaller of the two containments |A and B| / |A| and |A and B| / |B| (best column pair).',
    'pos_cont_hi': 'Larger of the two containments (best column pair).',
    'pos_nested': 'One Position set lies strictly inside the other.',
    'pos_equal': 'The two Position sets are equal.',
    'pos_disjoint': 'Both tables have Position columns and every column pair is disjoint.',
    'pos_pairs_hit': 'Share of Position column pairs that overlap.',
    'pos_adj': 'Share of the smaller Position set that touches the other set (4-neighbours) without overlapping it.',
    # --- Color columns joined on the value
    'col_jacc': 'Jaccard of the two Color sets (best column pair).',
    'col_cont_lo': 'Smaller containment of the two Color sets.',
    'col_cont_hi': 'Larger containment of the two Color sets.',
    'col_nested': 'One Color set lies strictly inside the other.',
    'col_equal': 'The two Color sets are equal.',
    # --- other shared types joined on the value (Bloom sets)
    'oth_jacc': 'Largest Jaccard of Bloom sets over column pairs of one shared type other than Position and Color.',
    'oth_cont_lo': 'Largest smaller-containment over those column pairs.',
    'oth_cont_hi': 'Largest larger-containment over those column pairs.',
    'oth_pairs_hit': 'Share of those column pairs whose Bloom sets overlap.',
    # --- a Position set against a color-split Position table
    'x_one_color': 'Share of one table\'s cells that fall on the cells of a single color in the other table\'s Position-Color table (best direction).',
    'x_color_cover': 'Share of one color\'s cells (in the other table) that the first table\'s cells cover (best direction).',
    'x_color_nsplit': 'Number of colors the first table\'s cells fall on in the other table\'s Position-Color table (smallest over directions).',
    # --- a Color table selecting the cells of a Position-Color table
    'sel_frac': 'Share of cells of a Position-Color table whose color is in the other table\'s Color set (best direction).',
    'sel_proper': 'The Color set selects some, not all, cells of the Position-Color table.',
    'sel_iou_target': 'IoU of the selected cells with the target cells (changed cells, or output foreground when sizes differ).',
    'sel_gain': 'sel_iou_target minus the IoU of the whole Position-Color table with the target.',
    # --- set algebra of Position sets against the target
    'alg_union_gain': 'IoU(A or B, target) minus the larger of IoU(A, target) and IoU(B, target).',
    'alg_inter_gain': 'IoU(A and B, target) minus the larger of the two IoU.',
    'alg_diff_gain': 'Larger of IoU(A minus B, target) and IoU(B minus A, target), minus the larger of the two IoU.',
    'alg_best_iou': 'Largest IoU with the target among A and B, A or B, A and B, A minus B, B minus A.',
    'alg_inter_prec': 'Share of A and B that lies on the target.',
    'alg_union_rec': 'Share of the target that A or B covers.',
    # --- Position table painted with the other table's colors
    'paint_fixed': 'Share of the target-color cells that one table\'s cells cover when painted with a color of the other table (best direction and color).',
    'paint_prec': 'Share of the painted cells that land on cells which become that color (same choice).',
    'paint_gain': 'paint_fixed minus the larger paint_fixed of either table alone with its own colors.',
    # --- structure
    'st_parent': 'One node is a direct parent of the other.',
    'st_shared_parent': 'Number of direct parents the two nodes share.',
    'st_depth_diff': 'Absolute difference of the two depths.',
    'st_depth_max': 'Larger depth of the two nodes.',
}
TYPES = ['Position', 'Color', 'Nat', 'Axis', 'Dir', 'Example', 'Box', 'Int', 'Ident', 'Dir8', 'DiagDir', 'D4']
for _t in TYPES:
    FEATURES['tc_' + _t] = 'Number of %s columns over the two tables.' % _t
FEATURES.update({
    'kd_det': 'Number of the two nodes whose clause is a DET (a domain or a direct view of the grids).',
    'kd_rule': 'Number of the two nodes whose clause is a RULE.',
    'kd_init': 'Number of the two nodes whose clause is an INIT (an operator result).',
    'map_ab': 'Share of changed cells whose input color is in one node\'s Color set and whose output color is in the other node\'s Color set (best direction).',
    'map_src': 'Share of changed cells whose input color is in the union of the two Color sets.',
    'map_dst': 'Share of changed cells whose output color is in the union of the two Color sets.',
})
FEATURES.update({
    'pos_ctx_hit': 'Share of train examples where the best-overlapping Position column pair shares a cell.',
    'al_rows': 'Jaccard of the sets of grid rows the two tables\' cells occupy.',
    'al_cols': 'Jaccard of the sets of grid columns the two tables\' cells occupy.',
    'bx_in': 'Share of one table\'s cells that lie inside the other table\'s boxes (best direction).',
    'bx_jacc': 'Jaccard of the cells covered by the two tables\' Box columns.',
    'bx_fill': 'Share of the cells in one table\'s boxes that the other table\'s cells cover (best direction).',
    'nat_hit': 'A Nat or Int value of one table equals a count of the other table (rows, distinct grid rows, distinct grid columns or cells in an example).',
    'rl_fg_min': 'Smaller share, over the two tables, of Position cells that are input foreground.',
    'rl_fg_max': 'Larger share of Position cells that are input foreground.',
    'rl_chg_min': 'Smaller share of Position cells that are changed cells.',
    'rl_chg_max': 'Larger share of Position cells that are changed cells.',
    'rl_incolor_agree': 'Both tables\' cells lie almost wholly (over 90%) on input cells of the same color.',
})
FEATURES.update({
    'cl_jacc': 'Jaccard of the sets of builtin relation names (words after an open parenthesis, such as input, split, apply) in the two clauses.',
    'cl_shared': 'Number of builtin relation names the two clauses share.',
    'st_anc': 'One node is an ancestor of the other (needs node[\'anc\'], the set of ancestor tokens).',
    'st_anc_common': 'Number of ancestors the two nodes share (needs node[\'anc\']).',
    'st_anc_jacc': 'Jaccard of the two ancestor sets (needs node[\'anc\']).',
})
FEATURES.update({
    'ic_frac': 'Share of one table\'s cells that lie on input cells whose color is in the other table\'s Color set (best direction).',
    'ic_cover': 'Share of the input cells with those colors that the first table\'s cells cover.',
    'ic_proper': 'The Color set selects some, not all, of the first table\'s cells (on the input grid).',
    'ic_gain': 'IoU(selected cells, target) minus IoU(the first table\'s cells, target).',
    'oc_frac': 'Share of one table\'s cells whose output color is in the other table\'s Color set (best direction).',
    'oc_lift': 'oc_frac minus the share of all output cells with a color in that Color set.',
})
STRUCT = ['st_parent', 'st_shared_parent', 'st_depth_diff', 'st_depth_max']


# ---------------------------------------------------------------------------------------------------------------- task masks
def _task_masks(pairs):
    tm = getattr(pairs[0], '_pm', None) if pairs else None
    if tm is not None and tm.get('n') == len(pairs):
        return tm
    n = len(pairs)
    chg = ofg = fg = 0
    chg_k = [0] * 10
    out_k = [0] * 10
    in_k = [0] * 10
    same = all(p.same for p in pairs)
    for e, p in enumerate(pairs):
        base = e * CELL
        for i, j in p.changed:
            if i < SIDE and j < SIDE:
                b = 1 << (base + i * SIDE + j)
                chg |= b
                chg_k[p.b[i][j]] |= b
        for i, j in p.ofg:
            if i < SIDE and j < SIDE:
                ofg |= 1 << (base + i * SIDE + j)
        for i, j in p.fg:
            if i < SIDE and j < SIDE:
                fg |= 1 << (base + i * SIDE + j)
        for i in range(min(p.h, SIDE)):
            row = p.a[i]
            for j in range(min(p.w, SIDE)):
                in_k[row[j]] |= 1 << (base + i * SIDE + j)
        for i in range(min(len(p.b), SIDE)):
            row = p.b[i]
            for j in range(min(len(row), SIDE)):
                out_k[row[j]] |= 1 << (base + i * SIDE + j)
    tgt = chg if same and chg else ofg
    dims = [(p.h, p.w) for p in pairs]
    cmap = [[0] * 10 for _ in range(10)]
    for p in pairs:
        for i, j in p.changed:
            cmap[p.a[i][j]][p.b[i][j]] += 1
    ncell = sum(p.h * p.w for p in pairs)
    ncell_out = sum(len(p.b) * len(p.b[0]) for p in pairs)
    rep = sum(1 << (CELL * e) for e in range(n))
    repc = sum(1 << (CSTRIDE * e) for e in range(n))
    tm = dict(ncell=ncell, ncell_out=ncell_out, n=n, same=same, cmap=cmap, dims=dims, in_k=in_k, chg=chg, ofg=ofg, fg=fg, chg_k=chg_k, out_k=out_k, tgt=tgt, ntgt=tgt.bit_count(), rep=rep, repc=repc,
              nchg=sum(chg_k[k].bit_count() for k in range(10)))
    try:
        pairs[0]._pm = tm
    except AttributeError:
        pass
    return tm


def _bloom(v):
    h = hash(v) & 0xFFFFFFFF
    return 1 << ((h * 2654435761 >> 8) % BLOOM)


# ---------------------------------------------------------------------------------------------------------------- sketch
def sketch(node, pairs):
    """Small dict for one node. Needs node['table_types'] or node['types'], node['x_rows'], depth, parents, token."""
    tm = _task_masks(pairs)
    n = tm['n']
    types = node.get('table_types') or node['types']
    w = [WIDE.get(t, 1) for t in types]
    offs = [0]
    for x in w:
        offs.append(offs[-1] + x)
    width = offs[-1]
    ex_col = types.index('Example') if 'Example' in types else None
    per_e = {}
    glob = []
    for ent in node.get('x_rows') or []:
        (a, e), rows = ent[0], ent[1]
        if a == 1 and e < n:
            per_e.setdefault(e, []).extend(r for r in rows if len(r) == width)
        elif a == 0:
            if ex_col is not None:
                o = offs[ex_col]
                for r in rows:
                    if len(r) == width and r[o] < n:
                        per_e.setdefault(r[o], []).append(r)
            else:
                glob.extend(r for r in rows if len(r) == width)
    rows_n = sum(len(v) for v in per_e.values()) + len(glob)
    ne = 0
    for e in range(n):
        if per_e.get(e) or glob:
            ne |= 1 << e
    cols = []
    pos_first = col_first = None
    cm = {}
    cnt = {}
    for ci, t in enumerate(types):
        cnt[t] = cnt.get(t, 0) + 1
        if cnt[t] > MAXC or t == 'Example':
            continue
        o = offs[ci]
        m = 0
        if t == 'Position':
            for e, rows in per_e.items():
                base = e * CELL
                for r in rows:
                    i = r[o]; j = r[o + 2]
                    if 0 <= i < SIDE and 0 <= j < SIDE:
                        m |= 1 << (base + i * SIDE + j)
            if glob:
                g = 0
                for r in glob:
                    i = r[o]; j = r[o + 2]
                    if 0 <= i < SIDE and 0 <= j < SIDE:
                        g |= 1 << (i * SIDE + j)
                m |= g * tm['rep']
            if pos_first is None:
                pos_first = ci
        elif t == 'Color':
            for e, rows in per_e.items():
                base = e * CSTRIDE
                for r in rows:
                    m |= 1 << (base + r[o])
            if glob:
                g = 0
                for r in glob:
                    g |= 1 << r[o]
                m |= g * tm['repc']
            if col_first is None:
                col_first = ci
        elif t == 'Box':
            seen = set()
            for e, rows in per_e.items():
                H, W = tm['dims'][e]
                for r in rows:
                    seen.add((e, r[o], r[o + 1], r[o + 2], r[o + 3]))
            if glob:
                for e in range(n):
                    for r in glob:
                        seen.add((e, r[o], r[o + 1], r[o + 2], r[o + 3]))
            for e, tp, bt, lf, rt in seen:
                H, W = tm['dims'][e]
                r0, r1, c0, c1 = tp, H - 1 - bt, lf, W - 1 - rt
                if r1 < r0 or c1 < c0 or c1 >= SIDE or r1 >= SIDE or r0 < 0 or c0 < 0:
                    continue
                rowm = ((1 << (c1 - c0 + 1)) - 1) << c0
                base = e * CELL + r0 * SIDE
                for i in range(r1 - r0 + 1):
                    m |= rowm << (base + i * SIDE)
        else:
            if w[ci] == 1:
                for rows in per_e.values():
                    for r in rows:
                        m |= _bloom(r[o])
                for r in glob:
                    m |= _bloom(r[o])
            else:
                for rows in per_e.values():
                    for r in rows:
                        m |= _bloom(tuple(r[o:o + w[ci]]))
                for r in glob:
                    m |= _bloom(tuple(r[o:o + w[ci]]))
        cols.append((t, m, m.bit_count(), ci))
    nat = set()
    for ci, t in enumerate(types):
        if t in ('Nat', 'Int') and len(nat) < 24:
            o = offs[ci]
            for rows in per_e.values():
                nat.update(r[o] for r in rows[:50])
            nat.update(r[o] for r in glob[:50])
    cnts = set()
    for ci, t in enumerate(types):
        if t in ('Ident', 'Nat', 'Int', 'Axis', 'Color'):
            o = offs[ci]
            for rows in per_e.values():
                cnts.add(len({r[o] for r in rows}))
    for rows in per_e.values():
        cnts.add(len(rows))
    cnts.add(len(glob))
    # cells per color, from the first Position and first Color column of the table
    if pos_first is not None and col_first is not None:
        po, co = offs[pos_first], offs[col_first]
        for e, rows in per_e.items():
            base = e * CELL
            for r in rows:
                i = r[po]; j = r[po + 2]
                if 0 <= i < SIDE and 0 <= j < SIDE:
                    k = r[co]
                    cm[k] = cm.get(k, 0) | (1 << (base + i * SIDE + j))
        if glob:
            gm = {}
            for r in glob:
                i = r[po]; j = r[po + 2]
                if 0 <= i < SIDE and 0 <= j < SIDE:
                    k = r[co]
                    gm[k] = gm.get(k, 0) | (1 << (i * SIDE + j))
            for k, g in gm.items():
                cm[k] = cm.get(k, 0) | (g * tm['rep'])
    poscols = [c for c in cols if c[0] == 'Position']
    colcols = [c for c in cols if c[0] == 'Color']
    othcols = [c for c in cols if c[0] not in ('Position', 'Color')]
    P = 0
    for c in poscols:
        P |= c[1]
    C = 0
    for c in colcols:
        C |= c[1]
    cset = 0                                    # colors present, over all examples
    for k in range(10):
        if C & sum(1 << (CSTRIDE * e + k) for e in range(n)):
            cset |= 1 << k
    BM = 0
    for c in cols:
        if c[0] == 'Box':
            BM |= c[1]
    # grid rows and columns occupied by the Position cells; cell counts per example
    RS = CS = 0
    if P:
        full = (1 << CELL) - 1
        for e in range(n):
            blk = P >> (e * CELL) & full
            if not blk:
                continue
            acc = 0
            nr = 0
            for i in range(SIDE):
                rb = blk >> (i * SIDE) & ((1 << SIDE) - 1)
                if rb:
                    acc |= rb; RS |= 1 << (e * 32 + i); nr += 1
            CS |= acc << (e * 32)
            cnts.add(nr); cnts.add(acc.bit_count()); cnts.add(blk.bit_count())
    cm_tuple = tuple(sorted(cm.items()))
    tgt = tm['tgt']
    sk = dict(
        kind=(node.get('clause') or '(?').split(' ', 1)[0], words=frozenset(w for w in _WORD.findall(node.get('clause') or '') if w not in ('DET', 'RULE', 'INIT', 'NOT', 'OR', 'IF', 'AND')), anc=frozenset(node.get('anc') or ()), tok=node.get('token'), parents=tuple(node.get('parents') or ()), depth=node.get('depth', 0),
        types=tuple(sorted(types)), ncols=len(types), rows=rows_n, ne=ne, glob=bool(glob) and not per_e, small=rows_n <= n,
        pos=poscols, col=colcols, oth=othcols, P=P, nP=P.bit_count(), cset=cset, cm=cm_tuple, tm=tm,
    )
    sk.update(BM=BM, nBM=BM.bit_count(), RS=RS, CS=CS, nRS=RS.bit_count(), nCS=CS.bit_count(), nat=frozenset(nat), cnts=frozenset(cnts))
    if P:
        nP = sk['nP']
        sk['fg'] = (P & tm['fg']).bit_count() / nP
        sk['chg'] = (P & tm['chg']).bit_count() / nP
        best_k, best_v = -1, 0
        for k in range(10):
            v = (P & tm['in_k'][k]).bit_count()
            if v > best_v:
                best_k, best_v = k, v
        sk['inc'] = best_k if best_v >= 0.9 * nP else -1
    # cells the node would fix when painted with each of its own colors (Position-Color table)
    own = 0
    if cm and tm['nchg']:
        for k, m in cm.items():
            own = max(own, (m & tm['chg_k'][k]).bit_count())
        sk['own_fixed'] = own / tm['nchg']
    else:
        sk['own_fixed'] = 0.0
    return sk


# ---------------------------------------------------------------------------------------------------------------- pair features
def _ov(x, y):
    """(jaccard, lo, hi) containment of two (mask, count) sets."""
    i = (x[0] & y[0]).bit_count()
    if not i:
        return 0.0, 0.0, 0.0, 0
    a = i / x[1]; b = i / y[1]
    return i / (x[1] + y[1] - i), min(a, b), max(a, b), i


def _iou(m, t, nt):
    if not m and not t:
        return 0.0
    i = (m & t).bit_count()
    return i / (m.bit_count() + nt - i) if (m or nt) else 0.0


def _dil(m):
    """4-neighbour dilation, over concatenated examples."""
    return m | (m << 1) | (m >> 1) | (m << SIDE) | (m >> SIDE)


def features(sa, sb):
    """Symmetric pair features from two sketches."""
    tm = sa['tm']
    n = tm['n']
    d = {}
    ta, tb = sa['types'], sb['types']
    ca, cb = {}, {}
    for t in ta: ca[t] = ca.get(t, 0) + 1
    for t in tb: cb[t] = cb.get(t, 0) + 1
    shared = sum(min(v, cb.get(k, 0)) for k, v in ca.items())
    d['ty_shared'] = shared
    d['ty_jacc'] = shared / (len(ta) + len(tb) - shared) if ta or tb else 0.0
    ha_p, hb_p = 'Position' in ca, 'Position' in cb
    ha_c, hb_c = 'Color' in ca, 'Color' in cb
    d['ty_share_pos'] = float(ha_p and hb_p)
    d['ty_share_col'] = float(ha_c and hb_c)
    d['ty_share_oth'] = sum(min(v, cb.get(k, 0)) for k, v in ca.items() if k not in ('Position', 'Color'))
    d['ty_complement'] = float((ha_p and not ha_c and hb_c and not hb_p) or (hb_p and not hb_c and ha_c and not ha_p))
    d['ty_pos_n'] = ha_p + hb_p
    d['ty_ncols_min'] = min(sa['ncols'], sb['ncols']); d['ty_ncols_max'] = max(sa['ncols'], sb['ncols'])
    ra, rb = sa['rows'], sb['rows']
    d['sz_rows_min_log'] = (1 + min(ra, rb)).bit_length(); d['sz_rows_max_log'] = (1 + max(ra, rb)).bit_length()
    d['sz_small_any'] = float(sa['small'] or sb['small'])
    both = (sa['ne'] & sb['ne']).bit_count()
    d['sz_ctx_overlap'] = both / n
    d['sz_ctx_min'] = min(sa['ne'].bit_count(), sb['ne'].bit_count()) / n
    d['sz_glob_any'] = float(sa['glob'] or sb['glob'])
    # Position x Position
    pa, pb = sa['pos'], sb['pos']
    best = None; hit = tot = 0
    for x in pa:
        for y in pb:
            r = _ov((x[1], x[2]), (y[1], y[2]))
            tot += 1; hit += r[3] > 0
            if best is None or r[0] > best[0] or (r[0] == best[0] and r[2] > best[2]):
                best = r + (x, y)
    best_pos = best[4:6] if best else None
    if best:
        d['pos_jacc'], d['pos_cont_lo'], d['pos_cont_hi'] = best[0], best[1], best[2]
        x, y = best[4], best[5]
        d['pos_equal'] = float(x[1] == y[1])
        d['pos_nested'] = float(x[1] != y[1] and best[3] == min(x[2], y[2]) and best[3] > 0)
        d['pos_disjoint'] = float(hit == 0)
        d['pos_pairs_hit'] = hit / tot
        # touching
        if x[2] and y[2]:
            v1 = (_dil(x[1]) & y[1] & ~x[1]).bit_count() / max(y[2], 1)
            v2 = (_dil(y[1]) & x[1] & ~y[1]).bit_count() / max(x[2], 1)
            d['pos_adj'] = v1 if x[2] > y[2] else v2 if x[2] < y[2] else max(v1, v2)
    # Color x Color
    best = None
    for x in sa['col']:
        for y in sb['col']:
            r = _ov((x[1], x[2]), (y[1], y[2]))
            if best is None or r[0] > best[0] or (r[0] == best[0] and r[2] > best[2]):
                best = r + (x, y)
    if best:
        d['col_jacc'], d['col_cont_lo'], d['col_cont_hi'] = best[0], best[1], best[2]
        x, y = best[4], best[5]
        d['col_equal'] = float(x[1] == y[1])
        d['col_nested'] = float(x[1] != y[1] and best[3] == min(x[2], y[2]) and best[3] > 0)
    # other types
    oj = olo = ohi = 0.0; hit = tot = 0
    for x in sa['oth']:
        for y in sb['oth']:
            if x[0] != y[0]:
                continue
            r = _ov((x[1], x[2]), (y[1], y[2]))
            tot += 1; hit += r[3] > 0
            oj = max(oj, r[0]); olo = max(olo, r[1]); ohi = max(ohi, r[2])
    if tot:
        d['oth_jacc'], d['oth_cont_lo'], d['oth_cont_hi'], d['oth_pairs_hit'] = oj, olo, ohi, hit / tot
    # Position set against a color-split table
    tgt, ntgt = tm['tgt'], tm['ntgt']
    one_c = cover = 0.0; nsplit = None
    for X, Y in ((sa, sb), (sb, sa)):
        if X['nP'] and Y['cm']:
            P = X['P']
            hits = [((P & m).bit_count(), m.bit_count()) for k, m in Y['cm']]
            tot_in = sum(h for h, _ in hits)
            if tot_in:
                mx = max(range(len(hits)), key=lambda q: hits[q][0])
                one_c = max(one_c, hits[mx][0] / X['nP'])
                cover = max(cover, max(h / mm for h, mm in hits if mm))
                ns = sum(1 for h, _ in hits if h)
                nsplit = ns if nsplit is None else min(nsplit, ns)
    if nsplit is not None:
        d['x_one_color'], d['x_color_cover'], d['x_color_nsplit'] = one_c, cover, nsplit
    # a Color set selecting cells of the other table's Position-Color table
    sf = None
    for X, Y in ((sa, sb), (sb, sa)):
        if X['cset'] and Y['cm'] and Y['nP']:
            J = 0
            for k, m in Y['cm']:
                if X['cset'] >> k & 1:
                    J |= m
            fr = J.bit_count() / Y['nP']
            io = _iou(J, tgt, ntgt)
            g = io - _iou(Y['P'], tgt, ntgt)
            cand = (J.bit_count() and J != Y['P'], fr, io, g)
            if sf is None or (cand[2], cand[1], cand[3]) > (sf[2], sf[1], sf[3]):
                sf = cand
    if sf is not None:
        d['sel_proper'] = float(bool(sf[0])); d['sel_frac'] = sf[1]; d['sel_iou_target'] = sf[2]; d['sel_gain'] = sf[3]
    # Position set algebra against the target
    if sa['nP'] and sb['nP'] and ntgt:
        A, B = sa['P'], sb['P']
        ia, ib = _iou(A, tgt, ntgt), _iou(B, tgt, ntgt)
        m = max(ia, ib)
        U, I, AB, BA = A | B, A & B, A & ~B, B & ~A
        iu, ii = _iou(U, tgt, ntgt), _iou(I, tgt, ntgt)
        idf = max(_iou(AB, tgt, ntgt), _iou(BA, tgt, ntgt))
        d['alg_union_gain'] = iu - m; d['alg_inter_gain'] = ii - m; d['alg_diff_gain'] = idf - m
        d['alg_best_iou'] = max(m, iu, ii, idf)
        if I:
            d['alg_inter_prec'] = (I & tgt).bit_count() / I.bit_count()
        d['alg_union_rec'] = (U & tgt).bit_count() / ntgt
    # paint: positions of one table, a color of the other
    nchg = tm['nchg']
    if nchg:
        pf = None
        for X, Y in ((sa, sb), (sb, sa)):
            if X['nP'] and Y['cset']:
                for k in range(10):
                    if Y['cset'] >> k & 1:
                        ck = tm['chg_k'][k]
                        fx = (X['P'] & ck).bit_count()
                        cand = (fx / nchg, fx / X['nP'])
                        if pf is None or cand > pf:
                            pf = cand
        if pf is not None:
            d['paint_fixed'], d['paint_prec'] = pf
            d['paint_gain'] = pf[0] - max(sa['own_fixed'], sb['own_fixed'])
    # a Color set against the input and output grids
    icb = None; ocb = None
    for X, Y in ((sa, sb), (sb, sa)):
        if X['nP'] and Y['cset']:
            U = 0; V = 0
            cs = Y['cset']
            for k in range(10):
                if cs >> k & 1:
                    U |= tm['in_k'][k]; V |= tm['out_k'][k]
            J = X['P'] & U
            nj = J.bit_count()
            cand = (nj / X['nP'], nj / U.bit_count() if U else 0.0, float(0 < nj < X['nP']), _iou(J, tgt, ntgt) - _iou(X['P'], tgt, ntgt))
            if icb is None or cand > icb:
                icb = cand
            oj = (X['P'] & V).bit_count() / X['nP']
            lift = oj - V.bit_count() / max(tm['ncell_out'], 1)
            if ocb is None or (oj, lift) > ocb:
                ocb = (oj, lift)
    if icb is not None:
        d['ic_frac'], d['ic_cover'], d['ic_proper'], d['ic_gain'] = icb
        d['oc_frac'], d['oc_lift'] = ocb
    # per-example reach of the position overlap
    if best_pos is not None:
        I = best_pos[0][1] & best_pos[1][1]
        full = (1 << CELL) - 1
        d['pos_ctx_hit'] = sum(1 for e in range(n) if I >> (e * CELL) & full) / n
    if sa['nP'] and sb['nP']:
        for nm, k in (('al_rows', 'RS'), ('al_cols', 'CS')):
            i_ = (sa[k] & sb[k]).bit_count(); u_ = sa['n' + k] + sb['n' + k] - i_
            d[nm] = i_ / u_ if u_ else 0.0
        fa, fb = sa['fg'], sb['fg']; ga, gb = sa['chg'], sb['chg']
        d['rl_fg_min'], d['rl_fg_max'] = min(fa, fb), max(fa, fb)
        d['rl_chg_min'], d['rl_chg_max'] = min(ga, gb), max(ga, gb)
        d['rl_incolor_agree'] = float(sa['inc'] >= 0 and sa['inc'] == sb['inc'])
    # boxes
    bx_in = bx_fill = 0.0
    for X, Y in ((sa, sb), (sb, sa)):
        if X['nP'] and Y['nBM']:
            i_ = (X['P'] & Y['BM']).bit_count()
            bx_in = max(bx_in, i_ / X['nP']); bx_fill = max(bx_fill, i_ / Y['nBM'])
    if (sa['nP'] and sb['nBM']) or (sb['nP'] and sa['nBM']):
        d['bx_in'], d['bx_fill'] = bx_in, bx_fill
    if sa['nBM'] and sb['nBM']:
        i_ = (sa['BM'] & sb['BM']).bit_count()
        d['bx_jacc'] = i_ / (sa['nBM'] + sb['nBM'] - i_)
    if (sa['nat'] or sb['nat']) and (sa['cnts'] or sb['cnts']):
        d['nat_hit'] = float(bool(sa['nat'] & sb['cnts']) or bool(sb['nat'] & sa['cnts']))
    # kinds and column types
    kd = (sa['kind'], sb['kind'])
    d['kd_det'] = (kd[0] == '(DET') + (kd[1] == '(DET'); d['kd_rule'] = (kd[0] == '(RULE') + (kd[1] == '(RULE'); d['kd_init'] = (kd[0] == '(INIT') + (kd[1] == '(INIT')
    for t in TYPES:
        d['tc_' + t] = ca.get(t, 0) + cb.get(t, 0)
    # color mapping of the changed cells
    if nchg and sa['cset'] and sb['cset']:
        cm_ = tm['cmap']; A_, B_ = sa['cset'], sb['cset']
        ab = ba = srcs = dsts = 0
        U_ = A_ | B_
        for k in range(10):
            row = cm_[k]
            ka_ = A_ >> k & 1; kb_ = B_ >> k & 1; ku = U_ >> k & 1
            for m in range(10):
                v = row[m]
                if v:
                    if ka_ and B_ >> m & 1: ab += v
                    if kb_ and A_ >> m & 1: ba += v
                    if ku: srcs += v
                    if U_ >> m & 1: dsts += v
        d['map_ab'] = max(ab, ba) / nchg; d['map_src'] = srcs / nchg; d['map_dst'] = dsts / nchg
    # structure
    ta_, tb_ = sa['tok'], sb['tok']
    wa, wb = sa['words'], sb['words']
    d['cl_shared'] = len(wa & wb)
    d['cl_jacc'] = len(wa & wb) / len(wa | wb) if wa or wb else 0.0
    if sa['anc'] or sb['anc']:
        ia = sa['anc'] & sb['anc']
        d['st_anc'] = float(ta_ in sb['anc'] or tb_ in sa['anc'])
        d['st_anc_common'] = len(ia)
        d['st_anc_jacc'] = len(ia) / len(sa['anc'] | sb['anc'])
    d['st_parent'] = float(ta_ in sb['parents'] or tb_ in sa['parents'])
    d['st_shared_parent'] = len(set(sa['parents']) & set(sb['parents']))
    d['st_depth_diff'] = abs(sa['depth'] - sb['depth'])
    d['st_depth_max'] = max(sa['depth'], sb['depth'])
    return d
