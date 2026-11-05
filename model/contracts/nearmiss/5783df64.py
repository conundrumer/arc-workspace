import json
from pathlib import Path


def _cells(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def _n(out):
    return len(out)


def _place(inp, out, f):
    n = _n(out)
    g = [[0] * n for _ in range(n)]
    k = len(inp) // n
    for r, c, v in _cells(inp):
        rr, cc = f(r, c, k, n)
        if 0 <= rr < n and 0 <= cc < n:
            g[rr][cc] = v
    return g


def transposed(inp, out):
    return _place(inp, out, lambda r, c, k, n: (c // k, r // k))


def mirror_h(inp, out):
    return [row[::-1] for row in out]


def mirror_v(inp, out):
    return out[::-1]


def modulo(inp, out):
    return _place(inp, out, lambda r, c, k, n: (r % n, c % n))


def offset_tiles(inp, out):
    return _place(inp, out, lambda r, c, k, n: (min((r + 1) // k, n - 1), min((c + 1) // k, n - 1)))


def reading_order(inp, out):
    n = _n(out)
    g = [[0] * n for _ in range(n)]
    for i, (r, c, v) in enumerate(_cells(inp)):
        g[i // n][i % n] = v
    return g


def column_order(inp, out):
    n = _n(out)
    g = [[0] * n for _ in range(n)]
    cs = sorted(_cells(inp), key=lambda t: (t[1], t[0]))
    for i, (r, c, v) in enumerate(cs):
        g[i % n][i // n] = v
    return g


def drop_top_left_tile(inp, out):
    g = [row[:] for row in out]
    g[0][0] = 0
    return g


def only_large_colors(inp, out):
    return [[v if v >= 5 else 0 for v in row] for row in out]


def rotate_cw(inp, out):
    return [list(r) for r in zip(*out[::-1])]


def finer_tiles(inp, out):
    # tile size k-1 instead of k, output grid grows accordingly
    n = _n(out)
    k = len(inp) // n
    kk = k - 1
    m = -(-len(inp) // kk)
    g = [[0] * m for _ in range(m)]
    for r, c, v in _cells(inp):
        g[r // kk][c // kk] = v
    return g


def row_tiles_only(inp, out):
    # place by tile row only, stacking along the column in reading order
    n = _n(out)
    k = len(inp) // n
    g = [[0] * n for _ in range(n)]
    cnt = [0] * n
    for r, c, v in sorted(_cells(inp)):
        rr = r // k
        g[rr][cnt[rr] % n] = v
        cnt[rr] += 1
    return g


ALTERNATIVES = [
    ("place each colored cell at its tile position transposed (column tile as row)", transposed),
    ("correct placement then mirrored left-right", mirror_h),
    ("correct placement then flipped top-bottom", mirror_v),
    ("position taken as cell coordinates modulo output size instead of tile index", modulo),
    ("tiles offset by one cell (row+1, col+1 before dividing)", offset_tiles),
    ("colored cells packed into output in input reading order, ignoring tile position", reading_order),
    ("colored cells packed column by column, ignoring tile position", column_order),
    ("correct output with the top-left tile left empty", drop_top_left_tile),
    ("only colors 5 and above are kept", only_large_colors),
    ("correct placement then rotated 90 degrees clockwise", rotate_cw),
    ("tile side one smaller than needed, so output grid is larger", finer_tiles),
    ("cells packed left to right within their tile row, ignoring tile column", row_tiles_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/5783df64.json'))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
