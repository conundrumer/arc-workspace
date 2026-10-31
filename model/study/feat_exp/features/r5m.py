"""Round 5, explorer M: what the train grids demand of X, beyond how much of a source table X keeps.

M1: the share of the cells the task changes that the boxes of a Box column cover.
M2: whether X's row or cell counts equal a count that the train grids show (an output side, the foreground, the changed cells).
M3: the share of the input's foreground cells that an input-frame Position column holds.
M4: how the bounding box of an input-frame Position column's cells compares with the bounding box of the output's foreground, the input's foreground and the changed cells.
M5: the share of the output's colors that X's Color columns hold.

The cells off a grid's most common color count as its foreground only where that color covers at least half of the grid.
A column belongs to the frame its tag names. Only the tags `input` and `output` are read in the train grids, and only on
train examples whose input and output have one size. All the features read the first model of each context.
"""
import collections as C

from featlib import feature


def _train_list(p):
    tr = p.train
    return tr['train'] if isinstance(tr, dict) and 'train' in tr else tr


def _ctxs(table):
    """(assignment, train) -> (train index, rows) of the first model of each context, rows being lists of cells."""
    out = {}
    for e in table.entries:
        out.setdefault((e['assignment'], e['train']), (e['train'], e['rows']))
    return out


def _values(rows):
    return {tuple(tuple(c['value']) for c in r) for r in rows}


def _background(grid):
    """The most common color of a grid, the smallest on a tie."""
    count = C.Counter(v for row in grid for v in row)
    top = max(count.values())
    return min(v for v, k in count.items() if k == top)


def _has_background(grid):
    """Whether the most common color covers at least half of the grid's cells. A grid without that has no background,
    and its cells off the most common color are most of the grid."""
    count = C.Counter(v for row in grid for v in row)
    return 2 * max(count.values()) >= sum(count.values())


def _same_size(grid_in, grid_out):
    return len(grid_in) == len(grid_out) and len(grid_in[0]) == len(grid_out[0])


# ---------------------------------------------------------------- M1

def _prefix(mask, h, w):
    """2D prefix sums of a set of cells, so that the count of cells in a rectangle takes four reads."""
    acc = [[0] * (w + 1) for _ in range(h + 1)]
    for r in range(h):
        run = 0
        for c in range(w):
            run += (r, c) in mask
            acc[r + 1][c + 1] = acc[r][c + 1] + run
    return acc


def _rect(acc, top, bottom, left, right):
    """Cells of the rectangle rows top..bottom, columns left..right (inclusive) that the prefix sums count."""
    return acc[bottom + 1][right + 1] - acc[top][right + 1] - acc[bottom + 1][left] + acc[top][left]


@feature
def m1_box_cover(p):
    """M1: over the Box columns of X with frame tag `input` or `output`, on train examples whose input and output have one size and differ: the share of changed cells that the union of the column's boxes covers (recall), the share of the union that is changed (prec), the share of its distinct boxes that hold a changed cell (touch) and the share of the grid that the union covers (cover); for the column with the largest recall. Boxes outside the grid or of another extent are left out. None without such a column or example. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    train = _train_list(p)
    cols = [i for i, f in enumerate(x.fields) if f['type'] == 'Box' and f.get('frame', '') in ('input', 'output')]
    if not cols:
        return None
    ctxs = [(t, rows) for t, rows in _ctxs(x).values() if t < len(train)]
    best = None
    for ci in cols:
        acc = {'recall': 0.0, 'prec': 0.0, 'touch': 0.0, 'cover': 0.0}
        n = 0
        for t, rows in ctxs:
            gin, gout = train[t]['input'], train[t]['output']
            if not _same_size(gin, gout):
                continue
            h, w = len(gin), len(gin[0])
            changed = {(r, c) for r in range(h) for c in range(w) if gin[r][c] != gout[r][c]}
            if not changed:
                continue
            pre = _prefix(changed, h, w)
            boxes = set()
            for row in rows:
                cell = row[ci]
                v = cell['value']
                if len(v) != 4:
                    continue
                if cell.get('extent_status') == 'resolved' and tuple(cell.get('extent') or ()) != (h, w):
                    continue
                top, bottom, left, right = v
                if min(v) < 0 or top + bottom > h - 1 or left + right > w - 1:
                    continue
                boxes.add((top, bottom, left, right))
            lines = [bytearray(w) for _ in range(h)]
            touched = 0
            for top, bottom, left, right in boxes:
                for r in range(top, h - bottom):
                    lines[r][left:w - right] = b'\x01' * (w - right - left)
                touched += _rect(pre, top, h - 1 - bottom, left, w - 1 - right) > 0
            union = sum(sum(line) for line in lines)
            hit = sum(lines[r][c] for r, c in changed)
            acc['recall'] += hit / len(changed)
            acc['prec'] += hit / union if union else 0.0
            acc['touch'] += touched / len(boxes) if boxes else 0.0
            acc['cover'] += union / (h * w)
            n += 1
        if n:
            res = {k: v / n for k, v in acc.items()}
            if best is None or (res['recall'], -res['cover']) > (best['recall'], -best['cover']):
                best = res
    if best is None:
        return None
    best['cols'] = len(cols)
    return best


# ---------------------------------------------------------------- M2

@feature
def m2_count_agree(p):
    """M2: the share of X's contexts (train examples) whose count equals a count read off the train grids, for counts of at least 3. The count is X's number of distinct rows (dim: an output side; area: the output's cell count; dim and area count only where the output side, or the output's cell count, takes two values over the train examples, since one value is shared by every example; fg_in: the input's cells off its most common color, where that color covers at least half of the input; fg_out: the same in the output; chg: the cells where the output differs, on one-size examples), or the number of distinct cells of an input-frame Position column (cells_fg: against fg_in; cells_chg: against chg); exact_chg is 1 when the column's distinct (top, left) cells are exactly the changed cells. any is the share of contexts with at least one count agreement. None when X has no context on a train example. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    train = _train_list(p)
    pos = [i for i, f in enumerate(x.fields) if f['type'] == 'Position' and f.get('frame', '') == 'input']
    keys = ('dim', 'area', 'fg_in', 'fg_out', 'chg', 'cells_fg', 'cells_chg', 'exact_chg', 'any')
    acc = dict.fromkeys(keys, 0.0)
    heights = {len(g['output']) for g in train}
    widths = {len(g['output'][0]) for g in train}
    areas = {len(g['output']) * len(g['output'][0]) for g in train}
    n = 0
    for t, rows in _ctxs(x).values():
        if t >= len(train):
            continue
        gin, gout = train[t]['input'], train[t]['output']
        n += 1
        rowcount = len(_values(rows))
        cells = max((len({tuple(r[i]['value']) for r in rows}) for i in pos), default=0)
        exact = False
        hin, win, hout, wout = len(gin), len(gin[0]), len(gout), len(gout[0])
        back_in, back_out = _background(gin), _background(gout)
        fg_in = sum(v != back_in for row in gin for v in row) if _has_background(gin) else -1
        fg_out = sum(v != back_out for row in gout for v in row)
        chg = sum(gin[r][c] != gout[r][c] for r in range(hin) for c in range(win)) if _same_size(gin, gout) else -1
        if chg > 0:
            changed = {(r, c) for r in range(hin) for c in range(win) if gin[r][c] != gout[r][c]}
            for i in pos:
                held = {(r[i]['value'][0], r[i]['value'][2]) for r in rows if len(r[i]['value']) == 4}
                exact |= held == changed
        hit = {
            'dim': rowcount >= 3 and (rowcount == hout and len(heights) > 1 or rowcount == wout and len(widths) > 1),
            'area': rowcount >= 3 and rowcount == hout * wout and len(areas) > 1,
            'fg_in': rowcount >= 3 and rowcount == fg_in,
            'fg_out': rowcount >= 3 and rowcount == fg_out,
            'chg': rowcount >= 3 and rowcount == chg,
            'cells_fg': cells >= 3 and cells == fg_in,
            'cells_chg': cells >= 3 and cells == chg,
            'exact_chg': exact,
        }
        for k, v in hit.items():
            acc[k] += v
        acc['any'] += any(hit.values())
    if not n:
        return None
    return {k: v / n for k, v in acc.items()}


# ---------------------------------------------------------------- M3

@feature
def m3_foreground_cover(p):
    """M3: for the Position columns of X with frame tag `input`, whose cells lie inside the train input and have its extent: the share of the input's cells off its most common color that the column holds (recall), the share of the column's distinct cells that are off that color (prec), and exact, 1 when some column has both at 1 in every example. Distinct cells per example, averaged over the contexts whose input's most common color covers at least half of its cells; the column with the largest recall. None without such a column. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    train = _train_list(p)
    cols = [i for i, f in enumerate(x.fields) if f['type'] == 'Position' and f.get('frame', '') == 'input']
    if not cols:
        return None
    ctxs = [(t, rows) for t, rows in _ctxs(x).values() if t < len(train)]
    best = None
    for ci in cols:
        rec = prec = 0.0
        exact = 1
        n = 0
        for t, rows in ctxs:
            grid = train[t]['input']
            if not _has_background(grid):
                continue
            h, w = len(grid), len(grid[0])
            back = _background(grid)
            fg = {(r, c) for r in range(h) for c in range(w) if grid[r][c] != back}
            cells = set()
            for row in rows:
                cell = row[ci]
                v = cell['value']
                if len(v) != 4 or cell.get('extent_status') != 'resolved' or tuple(cell.get('extent') or ()) != (h, w):
                    continue
                if min(v) >= 0 and v[0] + v[1] == h - 1 and v[2] + v[3] == w - 1:
                    cells.add((v[0], v[2]))
            if not fg:
                continue
            on = len(cells & fg)
            r_ = on / len(fg)
            p_ = on / len(cells) if cells else 0.0
            rec += r_
            prec += p_
            exact &= r_ == 1.0 and p_ == 1.0
            n += 1
        if n:
            res = {'recall': rec / n, 'prec': prec / n, 'exact': int(exact)}
            if best is None or (res['recall'], res['prec']) > (best['recall'], best['prec']):
                best = res
    return best


# ---------------------------------------------------------------- M4

def _bbox(cells):
    """(top, bottom, left, right) rows and columns spanned by a set of (row, column) cells; None if empty."""
    if not cells:
        return None
    rows = [c[0] for c in cells]
    cols = [c[1] for c in cells]
    return min(rows), max(rows), min(cols), max(cols)


def _iou(a, b):
    if a is None or b is None:
        return 0.0
    h = min(a[1], b[1]) - max(a[0], b[0]) + 1
    w = min(a[3], b[3]) - max(a[2], b[2]) + 1
    inter = max(h, 0) * max(w, 0)
    area = lambda r: (r[1] - r[0] + 1) * (r[3] - r[2] + 1)
    return inter / (area(a) + area(b) - inter)


@feature
def m4_span_agree(p):
    """M4: for the Position columns of X with frame tag `input`, whose cells lie inside the train input and have its extent: the bounding box of a column's distinct cells in one example, against the bounding box of the input's cells off its most common color (iou_in, eq_in: intersection over union, and 1 when equal), and, on one-size examples, of the output's cells off its most common color (iou_out, eq_out) and of the cells where the output differs (iou_chg, eq_chg). The input's box is read only in examples whose input has a most common color that covers at least half of its cells. Where X has two or more such Position columns, they are the ends of a relation and range over the whole node set, not a selection, and the input keys are named iou_in_pair and eq_in_pair. Averaged over the examples where the column holds a cell; the column with the largest iou_out. None without such a column. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    train = _train_list(p)
    cols = [i for i, f in enumerate(x.fields) if f['type'] == 'Position' and f.get('frame', '') == 'input']
    if not cols:
        return None
    ctxs = [(t, rows) for t, rows in _ctxs(x).values() if t < len(train)]
    suffix = '_pair' if len(cols) > 1 else ''
    best = None
    for ci in cols:
        acc = C.Counter()
        count = C.Counter()
        for t, rows in ctxs:
            gin, gout = train[t]['input'], train[t]['output']
            h, w = len(gin), len(gin[0])
            cells = set()
            for row in rows:
                cell = row[ci]
                v = cell['value']
                if len(v) != 4 or cell.get('extent_status') != 'resolved' or tuple(cell.get('extent') or ()) != (h, w):
                    continue
                if min(v) >= 0 and v[0] + v[1] == h - 1 and v[2] + v[3] == w - 1:
                    cells.add((v[0], v[2]))
            if not cells:
                continue
            box = _bbox(cells)
            if _has_background(gin):
                back = _background(gin)
                ref = _bbox({(r, c) for r in range(h) for c in range(w) if gin[r][c] != back})
                acc['iou_in' + suffix] += _iou(box, ref)
                acc['eq_in' + suffix] += box == ref
                count['in'] += 1
            if _same_size(gin, gout):
                back = _background(gout)
                ref = _bbox({(r, c) for r in range(h) for c in range(w) if gout[r][c] != back})
                acc['iou_out'] += _iou(box, ref)
                acc['eq_out'] += box == ref
                ref = _bbox({(r, c) for r in range(h) for c in range(w) if gin[r][c] != gout[r][c]})
                acc['iou_chg'] += _iou(box, ref)
                acc['eq_chg'] += box == ref
                count['out'] += 1
        if count['in'] or count['out']:
            res = {k: v / count['in' if '_in' in k else 'out'] for k, v in acc.items()}
            if best is None or res.get('iou_out', 0.0) > best.get('iou_out', 0.0):
                best = res
    return best


# ---------------------------------------------------------------- M5

@feature
def m5_color_cover(p):
    """M5: for X's Color columns, per train example (context), against the colors of the output grid off its most common color: the share of those colors that the columns hold (out_cov), the same against the input's colors off its most common color (in_cov) and against the colors that the output has and the input lacks (new_cov, 1 when there are none), averaged over the contexts. None without a Color column. (`g12_colors.seen` is the share of X's colors that occur in the input or the output.) None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    train = _train_list(p)
    cols = [i for i, t in enumerate(x.types()) if t == 'Color']
    if not cols:
        return None
    acc = C.Counter()
    n = 0
    for t, rows in _ctxs(x).values():
        if t >= len(train):
            continue
        gin, gout = train[t]['input'], train[t]['output']
        back_in, back_out = _background(gin), _background(gout)
        out_colors = {v for row in gout for v in row if v != back_out}
        in_colors = {v for row in gin for v in row if v != back_in}
        new_colors = out_colors - in_colors
        held = {row[i]['value'][0] for row in rows for i in cols}
        n += 1
        acc['out_cov'] += len(held & out_colors) / len(out_colors) if out_colors else 1.0
        acc['in_cov'] += len(held & in_colors) / len(in_colors) if in_colors else 1.0
        acc['new_cov'] += len(held & new_colors) / len(new_colors) if new_colors else 1.0
    if not n:
        return None
    return {k: v / n for k, v in acc.items()}
