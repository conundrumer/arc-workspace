import json
from pathlib import Path


def _copy(g):
    return [row[:] for row in g]


def _gaps(inp, dr, dc):
    """Background cells with a 1 on both sides along the direction (dr, dc)."""
    h, w = len(inp), len(inp[0])
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0:
                continue
            r1, c1, r2, c2 = r - dr, c - dc, r + dr, c + dc
            if (0 <= r1 < h and 0 <= c1 < w and 0 <= r2 < h and 0 <= c2 < w
                    and inp[r1][c1] == 1 and inp[r2][c2] == 1):
                res.append((r, c))
    return res


def _twos(out):
    return [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v == 2]


def wrong_fill_color(inp, out):
    return [[3 if v == 2 else v for v in row] for row in out]


def fill_with_dot_color(inp, out):
    return [[1 if v == 2 else v for v in row] for row in out]


def vertical_axis(inp, out):
    g = _copy(inp)
    for r, c in _gaps(inp, 1, 0):
        g[r][c] = 2
    return g


def diagonal_axes(inp, out):
    g = _copy(inp)
    for d in [(1, 1), (1, -1)]:
        for r, c in _gaps(inp, *d):
            g[r][c] = 2
    return g


def recolor_dots_too(inp, out):
    g = _copy(out)
    for r, c in _twos(out):
        for dc in (-1, 1):
            g[r][c + dc] = 2
    return g


def fill_next_to_dots(inp, out):
    g = _copy(inp)
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == 0 and any(0 <= c + dc < len(row) and row[c + dc] == 1 for dc in (-1, 1)):
                g[r][c] = 2
    return g


def transposed(inp, out):
    return [list(col) for col in zip(*out)]


def gap_shifted_right(inp, out):
    g = _copy(out)
    for r, c in _twos(out):
        g[r][c] = 0
    for r, c in _twos(out):
        if c + 1 < len(g[0]):
            g[r][c + 1] = 2
    return g


def first_gap_unfilled(inp, out):
    t = sorted(_twos(out))
    g = _copy(out)
    r, c = t[0]
    g[r][c] = 0
    return g


def last_gap_unfilled(inp, out):
    t = sorted(_twos(out))
    g = _copy(out)
    r, c = t[-1]
    g[r][c] = 0
    return g


def extend_past_chain_ends(inp, out):
    g = _copy(out)
    for r, row in enumerate(out):
        for c, v in enumerate(row):
            if v == 1 and c + 1 < len(row) and row[c + 1] == 0 and c > 0 and row[c - 1] == 2:
                g[r][c + 1] = 2
    return g


def only_top_half(inp, out):
    g = _copy(out)
    h = len(out)
    for r, c in _twos(out):
        if r >= h // 2:
            g[r][c] = 0
    return g


ALTERNATIVES = [
    ("gap cells are filled with 3 instead of 2", wrong_fill_color),
    ("gap cells are filled with the dot color 1 instead of 2", fill_with_dot_color),
    ("gaps are looked for along the vertical axis", vertical_axis),
    ("gaps are looked for along the two diagonal axes", diagonal_axes),
    ("the flanking dots are recolored to 2 along with the gap", recolor_dots_too),
    ("every background cell next to a dot is filled, flanked or not", fill_next_to_dots),
    ("output is the transposed true output (wrong orientation)", transposed),
    ("fill is placed one cell right of the gap (off by one)", gap_shifted_right),
    ("the first gap in reading order is left unfilled", first_gap_unfilled),
    ("the last gap in reading order is left unfilled", last_gap_unfilled),
    ("fill also extends one cell past the right end of each chain", extend_past_chain_ends),
    ("only gaps in the top half of the grid are filled", only_top_half),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/a699fb00.json'))
    pairs = task['train']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(f'{n}/{len(pairs)}  {desc}')
