"""Round 9, explorer y: symmetry of the train grids against what X holds.

The train grids have a symmetry when every input (or every output) is unchanged by a reflection or a transposition: V (rows
reversed), H (columns reversed), R2 (both), T (transpose, square grids) or A (anti-transpose, square grids). A grid agrees with a
symmetry when the cells that are off its most common color, or whose image is, keep their color under the image; the symmetry
counts for a side when every example agrees at 0.95 or more and the side has at least two such cells in some example.
A Position or Box value is a margin tuple [top, bottom, left, right] in its frame; a symmetry maps it to the margin tuple of the image.
A column belongs to the frame its tag names; only the tags `input` and `output`, or an empty tag whose variable is read from one of those grids, are read against the train grids.
"""
import collections as C
from itertools import product

from featlib import feature

OPS = ('V', 'H', 'R2', 'T', 'A')
OPS7 = OPS + ('R1', 'R3')


def _train_list(p):
    tr = p.train
    return tr['train'] if isinstance(tr, dict) and 'train' in tr else tr


def _image(op, m):
    """The margin tuple of the image of (top, bottom, left, right) under op; for T and A the frame must be square."""
    t, b, l, r = m
    if op == 'V':
        return (b, t, l, r)
    if op == 'H':
        return (t, b, r, l)
    if op == 'R2':
        return (b, t, r, l)
    if op == 'T':
        return (l, r, t, b)
    if op == 'A':
        return (r, l, b, t)
    if op == 'R1':
        return (r, l, t, b)
    return (l, r, b, t)  # R3


def _grid_image(op, g, r, c):
    h, w = len(g), len(g[0])
    if op == 'V':
        return h - 1 - r, c
    if op == 'H':
        return r, w - 1 - c
    if op == 'R2':
        return h - 1 - r, w - 1 - c
    if op == 'T':
        return c, r
    if op == 'A':
        return w - 1 - c, h - 1 - r
    if op == 'R1':
        return w - 1 - c, r
    return c, h - 1 - r  # R3


def _background(g):
    count = C.Counter(v for row in g for v in row)
    top = max(count.values())
    return min(v for v, k in count.items() if k == top)


def _agreement(g, op):
    """(cells that agree, cells counted) of grid g under op: the cells off the background or whose image is."""
    h, w = len(g), len(g[0])
    if op in ('T', 'A', 'R1', 'R3') and h != w:
        return None
    bg = _background(g)
    n = k = 0
    for r in range(h):
        for c in range(w):
            r2, c2 = _grid_image(op, g, r, c)
            if g[r][c] != bg or g[r2][c2] != bg:
                n += 1
                k += g[r][c] == g[r2][c2]
    return k, n


def _side_ops(grids):
    """The ops under which every grid agrees at 0.95 or more, the grids having two or more counted cells in some case."""
    out = []
    for op in OPS:
        res = [_agreement(g, op) for g in grids]
        if not res or any(x is None for x in res):
            continue
        if max(n for _k, n in res) < 2:
            continue
        if all(k >= 0.95 * n for k, n in res):
            out.append(op)
    return out


def _sym(p):
    """({'input': ops, 'output': ops}), cached on the train list."""
    tr = _train_list(p)
    return {side: _side_ops([t[side] for t in tr]) for side in ('input', 'output')}


def _grid_kind(p, col):
    """'input' or 'output' for a column whose tag says so, or whose tag is empty and whose variable is read, at every site that
    has a frame, from that one grid; else None."""
    if col.frame in ('input', 'output'):
        return col.frame
    if col.frame != '':
        return None
    v = p.clause.x_columns.get(col.name)
    if v is None:
        return None
    fr = {f for f in v.frames if f}
    if len(fr) == 1:
        (f,) = fr
        if f in ('input', 'output'):
            return f
    return None


def _cell_sets(p, table, col, kind):
    """{train index: set of margin tuples of the column} of the first model of each context, for a Position or Box column whose
    tag is `input` or `output`; the cell's frame size is the example's grid of that tag."""
    ex = {e.index: e for e in p.examples()}
    out = {}
    for (asg, t), models in table.examples().items():
        if t not in ex or not models:
            continue
        size = ex[t].input.size if kind == 'input' else ex[t].output.size
        s = set()
        for row in models[0]:
            v = row[col.index]
            if not hasattr(v, 'margins'):
                continue
            if v.size is not None and tuple(v.size) != tuple(size):
                continue
            s.add(v.margins)
        out[(asg, t)] = (size, s)
    return out


def _closure(size, s, op):
    """The share of margin tuples of s whose image under op is also in s; None where op needs a square frame and there is none."""
    if op in ('T', 'A', 'R1', 'R3') and size[0] != size[1]:
        return None
    if not s:
        return None
    return sum(_image(op, m) in s for m in s) / len(s)


@feature
def y1_closure(p):
    """Y1: for each Position or Box column of X with frame tag `input` or `output`, the share of its distinct values (per example) whose image under a symmetry of the train grids is also in the column, averaged over examples and over the symmetries of that side (`in_closure` for tag input against the inputs' symmetries, `out_closure` for tag output against the outputs'), and `out_on_in` for tag input against the outputs' symmetries on examples whose input and output have one size; the mean over columns. None where no column and symmetry meet. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    sym = _sym(p)
    ex = {e.index: e for e in p.examples()}
    acc = C.defaultdict(list)
    for col in x.columns():
        if col.type not in ('Position', 'Box'):
            continue
        kind = _grid_kind(p, col)
        if kind is None:
            continue
        sets = _cell_sets(p, x, col, kind)
        plans = []
        if sym[kind]:
            plans.append(('in_closure' if kind == 'input' else 'out_closure', sym[kind], False))
        if kind == 'input' and sym['output']:
            plans.append(('out_on_in', sym['output'], True))
        for name, ops, need_same in plans:
            vals = []
            for (asg, t), (size, s) in sets.items():
                if need_same and not ex[t].same_size:
                    continue
                for op in ops:
                    v = _closure(size, s, op)
                    if v is not None:
                        vals.append(v)
            if vals:
                acc[name].append(sum(vals) / len(vals))
    if not acc:
        return None
    return {k: sum(v) / len(v) for k, v in acc.items()}


# ---------------------------------------------------------------- Y2

def _grid_op(op, g):
    """The grid g transformed by op, as a list of rows."""
    h, w = len(g), len(g[0])
    if op in ('T', 'A', 'R1', 'R3') and h != w:
        return None
    out = [[None] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            r2, c2 = _grid_image(op, g, r, c)
            out[r2][c2] = g[r][c]
    return out


def _tile_ops(p):
    """The ops by which the input appears as an aligned block of the output (blocks of the input's size) in every example whose
    output is a larger multiple of the input; {} where no example is. Ops that map the input to itself are left out
    when the input has that symmetry in every example."""
    ops = None
    for t in _train_list(p):
        gi, go = t['input'], t['output']
        hi, wi, ho, wo = len(gi), len(gi[0]), len(go), len(go[0])
        if (ho, wo) == (hi, wi) or ho % hi or wo % wi:
            continue
        found = set()
        for op in OPS7:
            img = _grid_op(op, gi)
            if img is None:
                continue
            for bi, bj in product(range(ho // hi), range(wo // wi)):
                if all(go[bi * hi + r][bj * wi:(bj + 1) * wi] == img[r] for r in range(hi)):
                    found.add(op)
                    break
        ops = found if ops is None else ops & found
    return ops or set()


def _allowed(p, kinds):
    """The ops the task shows to columns whose grids are `kinds`: the ops by which the input appears as a block of the output,
    the symmetries of the inputs when a column reads the input, and of the outputs when a column reads the output."""
    sym = _sym(p)
    ops = set(_tile_ops(p))
    for k in kinds:
        if k in sym:
            ops |= set(sym[k])
    return ops


def _pair_columns(x):
    cols = [c for c in x.columns() if c.type in ('Position', 'Box')]
    return [(a, b) for i, a in enumerate(cols) for b in cols[i + 1:]]


def _orbit(m, size, ops):
    """The margin tuples reached from m by the ops (any number of them, in any order), m included."""
    h, w = size
    ops = [op for op in ops if h == w or op not in ('T', 'A', 'R1', 'R3')]
    seen = {m}
    todo = [m]
    while todo:
        cur = todo.pop()
        for op in ops:
            nxt = _image(op, cur)
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen


def _generators(ops):
    """The ops that are not a composition of two others in the set: R2 is V then H, A is T then R2, R1 and R3 are V and T."""
    ops = set(ops)
    gens = set(ops)
    if {'V', 'H'} <= ops:
        gens.discard('R2')
    if {'T', 'R2'} <= ops or {'T', 'V', 'H'} <= ops:
        gens.discard('A')
    if {'V', 'T'} <= ops:
        gens -= {'R1', 'R3'}
    return sorted(gens)


@feature
def y2_orbit(p):
    """Y2: over pairs of Position or Box columns (a, b) of X, per example, for each value of a (rows with resolved extents of one size): the images of a, the values of b in rows with that a, against the symmetries the task shows (the ops by which the input appears as a block of the output, the inputs' symmetries when a column reads the input, the outputs' when a column reads the output). `cover` is the mean share of {a} and its images under the ops that are not a composition of two others (`_generators`) that the images hold, `extra` the mean share of the images outside the orbit of a under all the ops (any number of them, a included); the pair (a, b) in either order with the largest `cover`, then the smallest `extra`. None where the task shows no such op or no pair has a row."""
    best = None
    for ca, cb in _pair_columns(p.x):
        ops = sorted(_allowed(p, {_grid_kind(p, ca), _grid_kind(p, cb)}))
        if not ops:
            continue
        for a, b in ((ca, cb), (cb, ca)):
            per = C.defaultdict(lambda: C.defaultdict(set))
            size_of = {}
            for (asg, t, model, row) in p.x.rows():
                if model != 0:
                    continue
                va, vb = row[a.index], row[b.index]
                if not hasattr(va, 'margins') or not hasattr(vb, 'margins'):
                    continue
                if va.size is None or vb.size is None or tuple(va.size) != tuple(vb.size):
                    continue
                per[(asg, t)][va.margins].add(vb.margins)
                size_of[(asg, t)] = tuple(va.size)
            cov = ext = n = 0
            for key, byval in per.items():
                h, w = size_of[key]
                gens = [g for g in _generators(ops) if h == w or g not in ('T', 'A', 'R1', 'R3')]
                for m, imgs in byval.items():
                    orb = _orbit(m, size_of[key], ops)
                    target = {m} | {_image(g, m) for g in gens}
                    cov += len(imgs & target) / len(target)
                    ext += len(imgs - orb) / len(imgs)
                    n += 1
            if n:
                res = {'cover': cov / n, 'extra': ext / n}
                if best is None or (res['cover'], -res['extra']) > (best['cover'], -best['extra']):
                    best = res
    return best


# ---------------------------------------------------------------- Y3

def _reflect(op, a, box):
    """The margin tuple of a Position or Box `a` reflected about the center of `box`, both in one frame: op V mirrors the rows, H the columns, R2 both."""
    t, b, l, r = a
    bt, bb, bl, br = box
    if op in ('V', 'R2'):
        t, b = b + (bt - bb), t - (bt - bb)
    if op in ('H', 'R2'):
        l, r = r + (bl - br), l - (bl - br)
    return (t, b, l, r)


@feature
def y3_box_reflection(p):
    """Y3: where X has a column of type D4 or Sym, over triples of columns of X with one grid tag (`input` or `output`, or an empty tag read from one grid): a Box column B and two other Position or Box columns a, b. For the rows of the first model of each context, the share of rows where b is a reflected by V, by H or by R2 about the center of B (`any`, over the three, and `V`, `H`, `R2` each), the rows with a different from b; the triple with the largest `any`. None without such a triple or without a row with a different from b."""
    x = p.x
    if not any(c.type in ('D4', 'Sym') for c in x.columns()):
        return None
    cols = [c for c in x.columns() if c.type in ('Position', 'Box') and _grid_kind(p, c)]
    boxes = [c for c in cols if c.type == 'Box']
    if not boxes or len(cols) < 3:
        return None
    best = None
    for B in boxes:
        kind = _grid_kind(p, B)
        others = [c for c in cols if c is not B and _grid_kind(p, c) == kind]
        for i, a in enumerate(others):
            for b in others[i + 1:]:
                n = 0
                hit = C.Counter()
                anyhit = 0
                for (_asg, _t, model, row) in x.rows():
                    if model != 0:
                        continue
                    va, vb, vB = row[a.index], row[b.index], row[B.index]
                    if not (hasattr(va, 'margins') and hasattr(vb, 'margins') and hasattr(vB, 'margins')):
                        continue
                    if va.margins == vb.margins:
                        continue
                    n += 1
                    ok = False
                    for op in ('V', 'H', 'R2'):
                        if _reflect(op, va.margins, vB.margins) == vb.margins:
                            hit[op] += 1
                            ok = True
                    anyhit += ok
                if n:
                    res = {'any': anyhit / n, 'V': hit['V'] / n, 'H': hit['H'] / n, 'R2': hit['R2'] / n}
                    if best is None or res['any'] > best['any']:
                        best = res
    return best


# ---------------------------------------------------------------- Y4

def _box_content(g, m):
    """The rows of the input grid g inside the box with margins m, or None for an empty or off-grid box."""
    t, b, l, r = m
    h, w = len(g), len(g[0])
    if min(m) < 0 or t + b >= h or l + r >= w:
        return None
    return [list(row[l:w - r]) for row in g[t:h - b]]


@feature
def y4_box_symmetry(p):
    """Y4: over the Box columns of X with tag `input` or `output` (or an empty tag read from one grid), the distinct boxes of each example (up to 400 per column) that hold at least 4 cells off the most common color of the grid, with the grid read being the example's input or output as the column's tag says. For each box the best agreement of its cells with their image under V, H or R2 about the box's center, as `_agreement` counts it (the cells off the grid's most common color, or whose image is). `mean` is the mean over boxes, `share` the share of boxes at 0.95 or more; the column with the largest `mean`. None without such a box. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    ex = {e.index: e for e in p.examples()}
    best = None
    for col in x.columns():
        if col.type != 'Box':
            continue
        kind = _grid_kind(p, col)
        if kind is None:
            continue
        vals = []
        for (asg, t), models in x.examples().items():
            if t not in ex or not models:
                continue
            g = ex[t].input.cells if kind == 'input' else ex[t].output.cells
            bg = _background(g)
            seen = set()
            for row in models[0]:
                v = row[col.index]
                if not hasattr(v, 'margins') or v.margins in seen:
                    continue
                seen.add(v.margins)
                if len(seen) > 400:
                    break
                sub = _box_content(g, v.margins)
                if sub is None or sum(c != bg for r in sub for c in r) < 4:
                    continue
                score = 0.0
                for op in ('V', 'H', 'R2'):
                    res = _agreement_bg(sub, op, bg)
                    if res and res[1]:
                        score = max(score, res[0] / res[1])
                vals.append(score)
        if vals:
            res = {'mean': sum(vals) / len(vals), 'share': sum(v >= 0.95 for v in vals) / len(vals)}
            if best is None or res['mean'] > best['mean']:
                best = res
    return best


def _agreement_bg(g, op, bg):
    """_agreement of g under op against a given background color."""
    h, w = len(g), len(g[0])
    n = k = 0
    for r in range(h):
        for c in range(w):
            r2, c2 = _grid_image(op, g, r, c)
            if g[r][c] != bg or g[r2][c2] != bg:
                n += 1
                k += g[r][c] == g[r2][c2]
    return k, n
