import json
from pathlib import Path


def _markers(inp):
    cnt = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            cnt.setdefault(v, []).append((r, c))
    twos = [v for v, cells in cnt.items() if len(cells) == 2]
    if len(twos) != 1:
        return None, None
    return twos[0], cnt[twos[0]]


def _segment(inp):
    col, m = _markers(inp)
    if m is None:
        return None
    (r1, c1), (r2, c2) = m
    n = max(abs(r1 - r2), abs(c1 - c2))
    dr = (r2 - r1) // n if r2 != r1 else 0
    dc = (c2 - c1) // n if c2 != c1 else 0
    cells = [(r1 + dr * i, c1 + dc * i) for i in range(1, n)]
    return col, m, cells, (dr, dc)


def _copy(g):
    return [row[:] for row in g]


def _revert(inp, out, pred):
    s = _segment(inp)
    if s is None:
        return None
    g = _copy(out)
    for r, c in s[2]:
        if pred(inp[r][c]):
            g[r][c] = inp[r][c]
    return g


def only_zero_painted(inp, out):
    return _revert(inp, out, lambda v: v == 1)


def only_one_painted(inp, out):
    return _revert(inp, out, lambda v: v == 0)


def swapped_paint(inp, out):
    s = _segment(inp)
    g = _copy(out)
    for r, c in s[2]:
        g[r][c] = 3 if inp[r][c] == 0 else 2
    return g


def all_marker_color(inp, out):
    s = _segment(inp)
    g = _copy(out)
    for r, c in s[2]:
        g[r][c] = s[0]
    return g


def all_three(inp, out):
    s = _segment(inp)
    g = _copy(out)
    for r, c in s[2]:
        g[r][c] = 3
    return g


def markers_painted(inp, out):
    s = _segment(inp)
    g = _copy(out)
    for r, c in s[1]:
        g[r][c] = 3
    return g


def skip_cell_next_to_first_marker(inp, out):
    s = _segment(inp)
    g = _copy(out)
    r, c = s[2][0]
    g[r][c] = inp[r][c]
    return g


def first_half_only(inp, out):
    s = _segment(inp)
    g = _copy(out)
    cells = s[2]
    for r, c in cells[len(cells) // 2:]:
        g[r][c] = inp[r][c]
    return g


def shifted_line(inp, out):
    s = _segment(inp)
    col = s[0]
    dr, dc = s[3]
    sr, sc = (1, 0) if dr == 0 else (0, 1)
    g = _copy(inp)
    h, w = len(inp), len(inp[0])
    for r, c in s[2]:
        r2, c2 = r + sr, c + sc
        if 0 <= r2 < h and 0 <= c2 < w and inp[r2][c2] != col:
            g[r2][c2] = 2 if inp[r2][c2] == 0 else 3
    return g


def global_recolor(inp, out):
    s = _segment(inp)
    g = _copy(inp)
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == 1:
                g[r][c] = 3
    for r, c in s[2]:
        if inp[r][c] == 0:
            g[r][c] = 2
    return g


def mirrored_line(inp, out):
    s = _segment(inp)
    col = s[0]
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r, c in s[2]:
        r2, c2 = (h - 1 - r, c) if s[3][0] == 0 else (r, w - 1 - c)
        if inp[r2][c2] != col:
            g[r2][c2] = 2 if inp[r2][c2] == 0 else 3
    return g


ALTERNATIVES = [
    ("only 0 cells on the segment are painted; 1 cells are left", only_zero_painted),
    ("only 1 cells on the segment are painted; 0 cells are left", only_one_painted),
    ("paint swapped: 0 becomes 3 and 1 becomes 2 on the segment", swapped_paint),
    ("every segment cell takes the marker color", all_marker_color),
    ("every segment cell becomes 3", all_three),
    ("the two markers are also recolored to 3", markers_painted),
    ("segment misses the cell next to the first marker", skip_cell_next_to_first_marker),
    ("only the half of the segment nearer the first marker is drawn", first_half_only),
    ("line drawn one cell beside the true segment", shifted_line),
    ("every 1 in the grid becomes 3, and segment 0 cells become 2", global_recolor),
    ("line drawn in the mirror image of the true segment across the grid's middle", mirrored_line),
]


def _valid(g, out):
    if g is None or not g or not isinstance(g, list):
        return False
    w = len(g[0])
    if not all(isinstance(r, list) and len(r) == w for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/bcb3040b.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error:", desc, repr(e))
                g = None
            n += _valid(g, p["output"])
        print(n, "/", len(pairs), desc)
