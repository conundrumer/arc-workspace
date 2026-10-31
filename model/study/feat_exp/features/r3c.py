"""Round 3, explorer C: the structure of X inside each example, and X's cells against the train grids.

Position cells are read as (top, left) of the margins [top, bottom, left, right]. A column belongs to the frame its
tag names; only columns with a non-empty tag are compared with each other, and only columns with tag `input` are read
in the train input grid (and then only where the cell's extent equals that grid's size).
"""
import collections as C
import itertools

from featlib import feature


def _train_list(p):
    tr = p.train
    return tr['train'] if isinstance(tr, dict) and 'train' in tr else tr


def _entries(p):
    """First model of each (assignment, train) context: (train index, rows), a row being a list of cells."""
    seen = {}
    for e in p.x.entries:
        seen.setdefault((e['assignment'], e['train']), (e['train'], e['rows']))
    return list(seen.values())


def _pos_cols(p, tag=None):
    return [i for i, f in enumerate(p.x.fields)
            if f['type'] == 'Position' and f.get('frame', '') and (tag is None or f.get('frame') == tag)]


def _cell(c):
    v = c['value']
    return (v[0], v[2]) if len(v) == 4 else None


@feature
def c1_aligned_positions(p):
    """C1: over pairs of Position columns with the same non-empty frame tag, the share of rows whose two cells lie on
    one row or one column (`min`, `mean` over pairs), the number of pairs, and how many pairs are aligned in every row
    (`full`) or in some row not (`broken`). None without such a pair or below 2 rows."""
    cols = _pos_cols(p)
    pairs = [(a, b) for a, b in itertools.combinations(cols, 2)
             if p.x.fields[a].get('frame') == p.x.fields[b].get('frame')]
    if not pairs:
        return None
    ctxs = _entries(p)
    if sum(len(r) for _, r in ctxs) < 2:
        return None
    used = sorted({i for pr in pairs for i in pr})
    flat = {i: [] for i in used}
    tags = []
    for t, rows in ctxs:
        for r in rows:
            tags.append(t)
            for i in used:
                flat[i].append(_cell(r[i]))
    shares = []
    for a, b in pairs:
        seen = {(t, ca, cb) for t, ca, cb in zip(tags, flat[a], flat[b]) if ca is not None and cb is not None}
        if seen:
            shares.append(sum(ca[0] == cb[0] or ca[1] == cb[1] for _, ca, cb in seen) / len(seen))
    if not shares:
        return None
    return {'min': min(shares), 'mean': sum(shares) / len(shares), 'pairs': len(shares),
            'full': sum(s == 1.0 for s in shares), 'broken': sum(s < 1.0 for s in shares)}


def _input_cells(p):
    """For each context with a train grid: (train index, grid, {column index -> set of distinct (top, left) cells
    that lie inside the grid}), over Position columns with tag `input` whose extent equals the grid's size."""
    train = _train_list(p)
    cols = _pos_cols(p, 'input')
    out = []
    if not cols:
        return out
    for t, rows in _entries(p):
        if t >= len(train):
            continue
        grid = train[t]['input']
        h, w = len(grid), len(grid[0])
        per = {}
        for i in cols:
            cells = set()
            for r in rows:
                c = r[i]
                if c.get('extent_status') != 'resolved' or tuple(c.get('extent') or ()) != (h, w):
                    continue
                v = c['value']
                if len(v) == 4 and 0 <= v[0] < h and 0 <= v[2] < w and v[0] + v[1] == h - 1 and v[2] + v[3] == w - 1:
                    cells.add((v[0], v[2]))
            per[i] = cells
        out.append((t, grid, per))
    return out


@feature
def c2_cell_ground(p):
    """C2: what lies under X's input-frame Position cells in the train input. Per column, over distinct cells of all
    examples: `bg` is the share on the grid's most common colour (`bg_min`, `bg_max` over columns), `cover` is the
    share of the grid's cells that the column holds (`cover_max`). None without such a column. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    info = _input_cells(p)
    if not info:
        return None
    cols = set()
    for _, _, per in info:
        cols |= set(per)
    bg, cover = [], []
    for i in sorted(cols):
        tot = on_bg = 0
        cov = []
        for _, grid, per in info:
            cells = per.get(i)
            if not cells:
                continue
            count = C.Counter(v for row in grid for v in row)
            back = count.most_common(1)[0][0]
            tot += len(cells)
            on_bg += sum(grid[r][c] == back for r, c in cells)
            cov.append(len(cells) / (len(grid) * len(grid[0])))
        if tot:
            bg.append(on_bg / tot)
            cover.append(sum(cov) / len(cov))
    if not bg:
        return None
    return {'bg_min': min(bg), 'bg_max': max(bg), 'cover_max': max(cover)}


@feature
def c3_changed_cells(p):
    """C3: X's input-frame Position cells against the cells where the train output differs from the train input, over
    examples whose input and output have the same size. `precision`: share of the distinct cells (union over columns)
    that changed; `coverage`: share of the changed cells that some column holds. None without such a cell or change. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    info = _input_cells(p)
    train = _train_list(p)
    hit = tot = changed = covered = 0
    for t, grid, per in info:
        out = train[t]['output']
        if len(out) != len(grid) or len(out[0]) != len(grid[0]):
            continue
        diff = {(r, c) for r in range(len(grid)) for c in range(len(grid[0])) if grid[r][c] != out[r][c]}
        union = set().union(*per.values()) if per else set()
        tot += len(union)
        hit += len(union & diff)
        changed += len(diff)
        covered += len(union & diff)
    if not tot or not changed:
        return None
    return {'precision': hit / tot, 'coverage': covered / changed}


@feature
def c4_number_order(p):
    """C4: over pairs of Number columns (by name), the pairs whose values are weakly ordered in every row with at least
    one strict row (`ordered`), those with a row of each strict order (`mixed`), and `mixed_share` of all pairs that
    are not equal in every row. None without two Number columns or below 2 rows."""
    cols = [i for i, f in enumerate(p.x.fields) if f['type'] == 'Number']
    if len(cols) < 2:
        return None
    ctxs = _entries(p)
    if sum(len(r) for _, r in ctxs) < 2:
        return None
    ordered = mixed = 0
    for a, b in itertools.combinations(cols, 2):
        lt = gt = False
        for _, rows in ctxs:
            for r in rows:
                x, y = r[a]['value'][0], r[b]['value'][0]
                lt |= x < y
                gt |= x > y
            if lt and gt:
                break
        if lt and gt:
            mixed += 1
        elif lt or gt:
            ordered += 1
    n = ordered + mixed
    return {'ordered': ordered, 'mixed': mixed, 'mixed_share': mixed / n if n else 0.0}


@feature
def c5_example_constant(p):
    """C5: how much of X is fixed inside an example. `const_share`: share of columns (not Example) that take one value
    in every non-empty example; `single`: 1 when every non-empty example has exactly one row; `varying`: number of
    columns with 2 or more values in some example. None when no example has a row."""
    ctxs = [(t, rows) for t, rows in _entries(p) if rows]
    if not ctxs:
        return None
    cols = [i for i, f in enumerate(p.x.fields) if f['type'] != 'Example']
    if not cols:
        return None
    const = 0
    for i in cols:
        const += all(len({tuple(r[i]['value']) for r in rows}) == 1 for _, rows in ctxs)
    return {'const_share': const / len(cols), 'single': float(all(len(rows) == 1 for _, rows in ctxs)),
            'varying': len(cols) - const}
