"""Round 13, explorer b: how X varies from one train example to the next.

B1: X's row count and the distinct-value counts of its columns follow a count read off the train grids, in proportion.
B2: the rows and the column values of X are not the same in every train example.
"""
import collections as C
import functools
import statistics as st

from featlib import feature

MIN_VARIATION = 0.05  # a grid count that varies less than this (coefficient of variation) over the examples fits any table


def _first(rows_by_model):
    """The distinct rows of an example, pooled over its models."""
    seen = {}
    for model in rows_by_model:
        for r in model:
            seen[r] = None
    return list(seen)


def _contexts(p):
    """{train example: distinct rows of X, without the Example column}, for the examples in which X has a row. A row is a
    tuple of decoded cells. None at a Det point whose X has no Example column: that X is the task-level body table, and
    every example's entry holds the rows of all examples."""
    x = p.x
    cols = x.columns()
    if p.kind == 'Det' and not any(c.type == 'Example' for c in cols):
        return None
    keep = [i for i, c in enumerate(cols) if c.type != 'Example']
    out = C.defaultdict(dict)
    for (a, e), models in x.examples().items():
        for r in _first(models):
            out[e][tuple(r[i] for i in keep)] = None
    return {e: list(rows) for e, rows in out.items() if rows}


# ------------------------------------------------------------------------------------------------ B1

def _cv(values):
    m = sum(values) / len(values)
    return st.pstdev(values) / m if m > 0 else None


@functools.lru_cache(maxsize=256)
def _components(cells, same_color, eight):
    """The connected components of a grid (a tuple of rows), as the list of (color, cell count). With same_color, the
    cells of one color are joined; without, the cells off the grid's most common color are joined."""
    h, w = len(cells), len(cells[0]) if cells else 0
    if not h or not w:
        return ()
    top = C.Counter(v for row in cells for v in row)
    bg = min(k for k, v in top.items() if v == max(top.values()))
    steps = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a or b) and (eight or not (a and b))]
    seen, out = set(), []
    for r in range(h):
        for c in range(w):
            if (r, c) in seen or (not same_color and cells[r][c] == bg):
                continue
            seen.add((r, c))
            stack, n = [(r, c)], 0
            while stack:
                a, b = stack.pop()
                n += 1
                for da, db in steps:
                    q = (a + da, b + db)
                    if 0 <= q[0] < h and 0 <= q[1] < w and q not in seen:
                        ok = cells[q[0]][q[1]] == cells[r][c] if same_color else cells[q[0]][q[1]] != bg
                        if ok:
                            seen.add(q)
                            stack.append(q)
            out.append((cells[r][c], n))
    return tuple(out)


def _grid_counts(e):
    """The counts of one train example that a table can follow: sides and area of the input and of the output, cells and
    colors of the input off its most common color, the components, and the changed cells."""
    g, o = e.input, e.output
    h, w = g.size
    top = g.colors()
    bg = min(k for k, v in top.items() if v == max(top.values()))
    fg = sum(v for k, v in top.items() if k != bg)
    same = _components(g.cells, True, False)
    q = {'area': h * w, 'h': h, 'w': w, 'hw': h + w, 'long': max(h, w), 'short': min(h, w),
         'fg': fg, 'bg': h * w - fg, 'colors': len(top), 'fg_colors': len(top) - 1,
         'parts': len(same), 'fg_parts': sum(1 for c, n in same if c != bg),
         'fg_blobs': len(_components(g.cells, False, True)),
         'out_area': o.size[0] * o.size[1], 'out_h': o.size[0], 'out_w': o.size[1]}
    ch = e.changed()
    if ch is not None:
        q['changed'] = len(ch)
    return q


def _best_law(counts, examples, grid):
    """The smallest coefficient of variation of counts[e] / q[e] over the grid counts q that vary over the examples, or None
    where X has no row in an example, no count varies, or there are fewer than two examples."""
    if len(examples) < 2 or any(counts[e] == 0 for e in examples):
        return None
    best = None
    for k in grid[examples[0]]:
        if not all(k in grid[e] for e in examples):
            continue
        qs = [grid[e][k] for e in examples]
        if min(qs) <= 0:
            continue
        v = _cv(qs)
        if v is None or v < MIN_VARIATION:
            continue
        c = _cv([counts[e] / grid[e][k] for e in examples])
        if c is not None and (best is None or c < best):
            best = c
    return best


@feature
def b1_scale_law(p):
    """B1: over the train examples in which X has rows, `rows` is the smallest coefficient of variation of (X's rows in
    example e) / q(e) over the grid counts q (sides, areas, cells and colors off the most common color, components, changed
    cells) that vary over the examples; `col_min` and `col_mean` are the same for the distinct values of each column
    (the smallest, the mean). 0 means X grows exactly in proportion to one count. None without two examples that have
    rows or without a grid count that varies, and at a Det point whose X has no Example column.

    Needs: partial. Monotone: no.
    """
    ctx = _contexts(p)
    if not ctx or len(ctx) < 2:
        return None
    x = p.x
    keep = [i for i, c in enumerate(x.columns()) if c.type != 'Example']
    exs = {e.index: e for e in p.examples()}
    es = sorted(e for e in ctx if e in exs)
    if len(es) < 2:
        return None
    grid = {e: _grid_counts(exs[e]) for e in es}
    out = {}
    law = _best_law({e: len(ctx[e]) for e in es}, es, grid)
    if law is not None:
        out['rows'] = law
    cols = []
    for k in range(len(keep)):
        c = _best_law({e: len({r[k] for r in ctx[e]}) for e in es}, es, grid)
        if c is not None:
            cols.append(c)
    if cols:
        out['col_min'] = min(cols)
        out['col_mean'] = sum(cols) / len(cols)
    return out or None


# ------------------------------------------------------------------------------------------------ B2

@feature
def b2_example_overlap(p):
    """B2: how much of X is shared between train examples. Over the examples in which X has rows (the rows without the
    Example and Ident columns): `rows` is the mean Jaccard overlap of two examples' row sets; `contain` the mean share of the
    smaller row set found in the other; `col_min` and `col_mean` the smallest and the mean, over columns, of the mean Jaccard
    overlap of two examples' value sets; `same` the share of examples whose row set equals another example's. 1 for a table
    that does not read the grids (an enumeration of a library type). None with fewer than two such examples, without a column
    other than Example and Ident, and at a Det point whose X has no Example column.

    Needs: partial. Monotone: no.
    """
    x = p.x
    cols = x.columns()
    keep = [i for i, c in enumerate(cols) if c.type not in ('Example', 'Ident')]
    if not keep:
        return None
    ctx = _contexts(p)
    if not ctx:
        return None
    pos = {i: j for j, i in enumerate(i for i, c in enumerate(cols) if c.type != 'Example')}
    sets = [frozenset(tuple(r[pos[i]] for i in keep) for r in ctx[e]) for e in sorted(ctx)]
    if len(sets) < 2:
        return None
    pairs = [(a, b) for k, a in enumerate(sets) for b in sets[k + 1:]]
    out = {'rows': sum(len(a & b) / len(a | b) for a, b in pairs) / len(pairs),
           'contain': sum(len(a & b) / min(len(a), len(b)) for a, b in pairs) / len(pairs)}
    per_col = []
    for j in range(len(keep)):
        vs = [frozenset(t[j] for t in s) for s in sets]
        per_col.append(sum(len(a & b) / len(a | b) for k, a in enumerate(vs) for b in vs[k + 1:]) / len(pairs))
    out['col_min'] = min(per_col)
    out['col_mean'] = sum(per_col) / len(per_col)
    cnt = C.Counter(sets)
    out['same'] = sum(v for v in cnt.values() if v > 1) / len(sets)
    return out
