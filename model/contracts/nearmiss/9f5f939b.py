import json
from pathlib import Path

DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _bg(g):
    flat = [v for row in g for v in row]
    return max(set(flat), key=flat.count)


def _centers(inp, out):
    return [(r, c) for r in range(len(inp)) for c in range(len(inp[0]))
            if inp[r][c] != out[r][c]]


def _mark_color(inp, out):
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            if inp[r][c] != out[r][c]:
                return out[r][c]
    return None


def _ink(g, r, c):
    return 0 <= r < len(g) and 0 <= c < len(g[0]) and g[r][c] != _bg(g)


def _copy(g):
    return [row[:] for row in g]


def _arm_k(inp, r, c, d, gap=1, length=2):
    # domino of given length whose near end is gap cells beyond the empty gap
    dr, dc = d
    if any(_ink(inp, r + dr * k, c + dc * k) for k in range(1, gap + 1)):
        return False
    return all(_ink(inp, r + dr * (gap + 1 + i), c + dc * (gap + 1 + i))
               for i in range(length))


def _cells(inp, test):
    return [(r, c) for r in range(len(inp)) for c in range(len(inp[0]))
            if not _ink(inp, r, c) and test(r, c)]


def _paint(inp, cells, color):
    g = _copy(inp)
    for r, c in cells:
        g[r][c] = color
    return g


def wrong_color(inp, out):
    g = _copy(out)
    m = _mark_color(inp, out)
    for r, c in _centers(inp, out):
        g[r][c] = 3 if m != 3 else 2
    return g


def mark_gap_cell(inp, out):
    g = _copy(inp)
    m = _mark_color(inp, out)
    for r, c in _centers(inp, out):
        g[r - 1][c] = m
    return g


def plus_shape(inp, out):
    g = _copy(out)
    m = _mark_color(inp, out)
    for r, c in _centers(inp, out):
        for dr, dc in DIRS:
            g[r + dr][c + dc] = m
    return g


def one_arm(inp, out):
    m = _mark_color(inp, out)
    cells = _cells(inp, lambda r, c: any(_arm_k(inp, r, c, d) for d in DIRS))
    return _paint(inp, cells, m)


def four_gap_cells(inp, out):
    g = _copy(out)
    m = _mark_color(inp, out)
    for r, c in _centers(inp, out):
        g[r][c] = inp[r][c]
        for dr, dc in DIRS:
            g[r + dr][c + dc] = m
    return g


def touching_only(inp, out):
    m = _mark_color(inp, out)
    cells = _cells(inp, lambda r, c: all(_arm_k(inp, r, c, d, gap=0) for d in DIRS))
    return _paint(inp, cells, m)


def drop_first_cross(inp, out):
    g = _copy(out)
    r, c = _centers(inp, out)[0]
    g[r][c] = inp[r][c]
    return g


def recolor_dominoes(inp, out):
    g = _copy(out)
    m = _mark_color(inp, out)
    for r, c in _centers(inp, out):
        for dr, dc in DIRS:
            for k in (2, 3):
                g[r + dr * k][c + dc * k] = m
    return g


def fill_horizontal_span(inp, out):
    g = _copy(out)
    m = _mark_color(inp, out)
    for r, c in _centers(inp, out):
        for k in (-1, 0, 1):
            g[r][c + k] = m
    return g


def shifted_center(inp, out):
    g = _copy(inp)
    m = _mark_color(inp, out)
    for r, c in _centers(inp, out):
        g[r][c + 1] = m
    return g


def transposed(inp, out):
    return [list(row) for row in zip(*out)]


ALTERNATIVES = [
    ("cross center takes the wrong color (3 instead of the new mark color)", wrong_color),
    ("mark lands on the gap cell above the center, not on the center", mark_gap_cell),
    ("mark fills the center and its four neighbors (plus shape)", plus_shape),
    ("one domino pointing at a cell suffices to mark it", one_arm),
    ("mark fills the four gap cells and leaves the center", four_gap_cells),
    ("dominoes must touch the center (no gap), so nothing is marked", touching_only),
    ("output transposed (rows and columns swapped)", transposed),
    ("the first cross in reading order gets no mark", drop_first_cross),
    ("the dominoes of a cross are recolored with the mark color as well", recolor_dominoes),
    ("mark fills the horizontal span: center and its left and right neighbors", fill_horizontal_span),
    ("mark is shifted one column right of the center", shifted_center),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/9f5f939b.json').read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
