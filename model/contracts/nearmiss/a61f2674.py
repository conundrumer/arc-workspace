from pathlib import Path
import json, copy

def bars(inp):
    """Return list of (col, [rows]) for each column holding bar-color cells, sorted by column."""
    h, w = len(inp), len(inp[0])
    res = []
    for c in range(w):
        rows = [r for r in range(h) if inp[r][c] != 0]
        if rows:
            res.append((c, rows))
    return res

def ranked(inp):
    b = bars(inp)
    hs = [len(rows) for _, rows in b]
    tall = max(range(len(b)), key=lambda i: hs[i])
    short = min(range(len(b)), key=lambda i: hs[i])
    return b, hs, tall, short

def blank_like(inp):
    return [[0] * len(inp[0]) for _ in inp]

def paint(inp, spec, keep_others=None):
    """spec: {bar index: color}; others erased (or kept as input color)."""
    g = blank_like(inp)
    b, hs, tall, short = ranked(inp)
    if keep_others:
        for c, rows in b:
            for r in rows:
                g[r][c] = inp[r][c]
    for i, col in spec.items():
        c, rows = b[i]
        for r in rows:
            g[r][c] = col
    return g

def swap_colors(inp, out):
    m = {1: 2, 2: 1}
    return [[m.get(v, v) for v in row] for row in out]

def tall_only(inp, out):
    b, hs, t, s = ranked(inp)
    return paint(inp, {t: 1})

def short_only(inp, out):
    b, hs, t, s = ranked(inp)
    return paint(inp, {s: 2})

def same_color(inp, out):
    b, hs, t, s = ranked(inp)
    return paint(inp, {t: 1, s: 1})

def second_tallest(inp, out):
    b, hs, t, s = ranked(inp)
    order = sorted(range(len(b)), key=lambda i: -hs[i])
    return paint(inp, {t: 1, order[1]: 2})

def second_shortest(inp, out):
    b, hs, t, s = ranked(inp)
    order = sorted(range(len(b)), key=lambda i: hs[i])
    return paint(inp, {t: 1, order[1]: 2})

def keep_others(inp, out):
    b, hs, t, s = ranked(inp)
    return paint(inp, {t: 1, s: 2}, keep_others=True)

def drop_top_cell(inp, out):
    g = copy.deepcopy(out)
    b, hs, t, s = ranked(inp)
    c, rows = b[t]
    g[min(rows)][c] = 0
    return g

def top_cell_only(inp, out):
    b, hs, t, s = ranked(inp)
    g = blank_like(inp)
    for i, col in ((t, 1), (s, 2)):
        c, rows = b[i]
        g[min(rows)][c] = col
    return g

def flip_vertical(inp, out):
    # bars hang from the top edge instead of standing on the bottom
    return [row[:] for row in out[::-1]]

def full_column(inp, out):
    # recolor the whole grid column of the tallest and shortest bars
    b, hs, t, s = ranked(inp)
    g = blank_like(inp)
    for i, col in ((t, 1), (s, 2)):
        c, _ = b[i]
        for r in range(len(inp)):
            g[r][c] = col
    return g

def extra_row_height(inp, out):
    # measure by span from topmost bar cell to grid bottom plus one: pick by leftmost-first tie-break on
    # a wrong metric, the column index. Rightmost bar is 'tallest', leftmost 'shortest'.
    b, hs, t, s = ranked(inp)
    return paint(inp, {len(b) - 1: 1, 0: 2})

ALTERNATIVES = [
    ("tallest takes 2 and shortest takes 1 (colors swapped)", swap_colors),
    ("only the tallest bar is recolored; the shortest is erased", tall_only),
    ("only the shortest bar is recolored; the tallest is erased", short_only),
    ("tallest and shortest both take color 1", same_color),
    ("second tallest bar is taken as the shortest", second_tallest),
    ("second shortest bar is taken as the shortest", second_shortest),
    ("other bars are kept in the input color instead of erased", keep_others),
    ("recolored bars lose their top cell", drop_top_cell),
    ("only the top cell of each extreme bar is recolored", top_cell_only),
    ("bars hang from the top edge (output flipped vertically)", flip_vertical),
    ("the whole grid column of each extreme bar is recolored", full_column),
    ("rightmost bar is taken as tallest and leftmost as shortest", extra_row_height),
]

def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out

if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/a61f2674.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(copy.deepcopy(p["input"]), copy.deepcopy(p["output"]))
            except Exception as e:
                print("  error", desc, e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
