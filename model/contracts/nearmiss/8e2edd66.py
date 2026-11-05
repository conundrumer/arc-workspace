"""Near-miss rules for ARC task 8e2edd66.

True rule: the output is 9x9. Block (a, b) holds the ink color at each cell
(c, d) where the input cell (c, d) is background, and only when the input cell
(a, b) is also background. Other cells are background (0).
"""
import json
from pathlib import Path


def _ink(inp):
    for row in inp:
        for v in row:
            if v != 0:
                return v
    return 0


def _kron(inp, outer_fn, inner_fn, color=None, bg=0):
    n = len(inp)
    m = len(inp[0])
    c = _ink(inp) if color is None else color
    grid = [[bg] * (m * m) for _ in range(n * n)]
    for a in range(n):
        for b in range(m):
            for i in range(n):
                for j in range(m):
                    if outer_fn(inp[a][b]) and inner_fn(inp[i][j]):
                        grid[a * n + i][b * m + j] = c
    return grid


def _is_bg(v):
    return v == 0


def _is_ink(v):
    return v != 0


def both_ink(inp, out):
    return _kron(inp, _is_ink, _is_ink)


def outer_bg_inner_ink(inp, out):
    return _kron(inp, _is_bg, _is_ink)


def outer_ink_inner_bg(inp, out):
    return _kron(inp, _is_ink, _is_bg)


def wrong_color(inp, out):
    c = _ink(inp)
    new = c % 9 + 1
    return [[new if v else 0 for v in row] for row in out]


def either_bg(inp, out):
    return _either(inp)


def _either(inp):
    n = len(inp)
    m = len(inp[0])
    c = _ink(inp)
    grid = [[0] * (m * m) for _ in range(n * n)]
    for a in range(n):
        for b in range(m):
            for i in range(n):
                for j in range(m):
                    if inp[a][b] == 0 or inp[i][j] == 0:
                        grid[a * n + i][b * m + j] = c
    return grid


def filled_blocks(inp, out):
    return _kron(inp, _is_bg, lambda v: True)


def inverse_everywhere(inp, out):
    return _kron(inp, lambda v: True, _is_bg)


def inner_mirrored(inp, out):
    flipped = [row[::-1] for row in inp]
    n = len(inp)
    m = len(inp[0])
    c = _ink(inp)
    grid = [[0] * (m * m) for _ in range(n * n)]
    for a in range(n):
        for b in range(m):
            if inp[a][b] != 0:
                continue
            for i in range(n):
                for j in range(m):
                    if flipped[i][j] == 0:
                        grid[a * n + i][b * m + j] = c
    return grid if grid != out else None


def inner_transposed(inp, out):
    n = len(inp)
    m = len(inp[0])
    c = _ink(inp)
    grid = [[0] * (m * m) for _ in range(n * n)]
    for a in range(n):
        for b in range(m):
            if inp[a][b] != 0:
                continue
            for i in range(n):
                for j in range(m):
                    if inp[j][i] == 0:
                        grid[a * n + i][b * m + j] = c
    return grid


def crop_small(inp, out):
    return [[0 if v else _ink(inp) for v in row] for row in inp]


def shifted_down(inp, out):
    return [out[-1]] + [row[:] for row in out[:-1]]


def outer_transposed(inp, out):
    n = len(inp)
    m = len(inp[0])
    c = _ink(inp)
    grid = [[0] * (m * m) for _ in range(n * n)]
    for a in range(n):
        for b in range(m):
            if inp[b][a] != 0:
                continue
            for i in range(n):
                for j in range(m):
                    if inp[i][j] == 0:
                        grid[a * n + i][b * m + j] = c
    return grid


ALTERNATIVES = [
    ("ink where both outer and inner cells are ink (plain Kronecker, no inversion)", both_ink),
    ("ink where outer cell is background and inner cell is ink (inner not inverted)", outer_bg_inner_ink),
    ("ink where outer cell is ink and inner cell is background (outer inverted)", outer_ink_inner_bg),
    ("correct layout drawn in the wrong color", wrong_color),
    ("ink where either outer or inner cell is background (OR instead of AND)", either_bg),
    ("every background-outer block filled solid with ink, inner pattern dropped", filled_blocks),
    ("inverted pattern placed in every block, outer condition ignored", inverse_everywhere),
    ("inner pattern mirrored left-right", inner_mirrored),
    ("inner pattern transposed", inner_transposed),
    ("output is only the 3x3 inverted input, not expanded", crop_small),
    ("true output shifted down by one row with wraparound", shifted_down),
    ("outer block selection uses the transposed input", outer_transposed),
]


def _valid(g):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    return all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/8e2edd66.json").read_text())
    pairs = task["train"]
    print(f"{len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
