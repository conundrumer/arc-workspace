import json
from collections import Counter
from pathlib import Path

D4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _analyse(inp):
    """Return (bg, corner_only cells, side cells, shell colors, core colors)."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])

    def ink(r, c):
        return 0 <= r < h and 0 <= c < w and inp[r][c] != bg

    corner, side, diag_any = [], [], []
    shell = set()
    for r in range(h):
        for c in range(w):
            if inp[r][c] != bg:
                continue
            s4 = any(ink(r + dr, c + dc) for dr, dc in D4)
            dg = [(r + dr, c + dc) for dr, dc in DG if ink(r + dr, c + dc)]
            if s4:
                side.append((r, c))
            if dg:
                diag_any.append((r, c))
            if dg and not s4:
                corner.append((r, c))
                shell.update(inp[a][b] for a, b in dg)
    colors = {v for row in inp for v in row if v != bg}
    return bg, corner, side, diag_any, shell, colors - shell


def _paint(inp, cells, color):
    g = [row[:] for row in inp]
    for r, c in cells:
        g[r][c] = color
    return g


def _one(s):
    return next(iter(s)) if len(s) == 1 else None


def alt_shell_color(inp, out):
    bg, corner, side, dia, shell, core = _analyse(inp)
    col = _one(shell)
    return None if col is None else _paint(inp, corner, col)


def alt_side_cells(inp, out):
    bg, corner, side, dia, shell, core = _analyse(inp)
    col = _one(core)
    return None if col is None else _paint(inp, side, col)


def alt_all_adjacent(inp, out):
    bg, corner, side, dia, shell, core = _analyse(inp)
    col = _one(core)
    return None if col is None else _paint(inp, set(corner) | set(side), col)


def alt_any_diagonal(inp, out):
    # missed the condition that the cell must not touch ink orthogonally
    bg, corner, side, dia, shell, core = _analyse(inp)
    col = _one(core)
    return None if col is None else _paint(inp, dia, col)


def alt_top_half_only(inp, out):
    bg, corner, side, dia, shell, core = _analyse(inp)
    col = _one(core)
    if col is None:
        return None
    rows = [r for r, _ in corner]
    mid = (min(rows) + max(rows)) / 2
    return _paint(inp, [(r, c) for r, c in corner if r <= mid], col)


def alt_shifted_down(inp, out):
    bg, corner, side, dia, shell, core = _analyse(inp)
    col = _one(core)
    if col is None:
        return None
    h = len(inp)
    return _paint(inp, [(r + 1, c) for r, c in corner if r + 1 < h], col)


def alt_erase_core(inp, out):
    bg, corner, side, dia, shell, core = _analyse(inp)
    g = [row[:] for row in out]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v in core:
                g[r][c] = bg
    return g


def alt_shell_recolored(inp, out):
    bg, corner, side, dia, shell, core = _analyse(inp)
    col = _one(core)
    if col is None:
        return None
    g = [row[:] for row in out]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v in shell:
                g[r][c] = col
    return g


def alt_corners_erased(inp, out):
    # corner cells found but left as background, ink kept: only extra paint on side
    bg, corner, side, dia, shell, core = _analyse(inp)
    col = _one(core)
    if col is None:
        return None
    g = _paint(inp, corner, col)
    h, w = len(g), len(g[0])
    # also extend each painted corner one step further along its diagonal away from ink
    for r, c in corner:
        for dr, dc in DG:
            a, b = r - dr, c - dc
            if 0 <= a < h and 0 <= b < w and inp[a][b] != bg:
                x, y = r + dr, c + dc
                if 0 <= x < h and 0 <= y < w and inp[x][y] == bg:
                    g[x][y] = col
    return g


def alt_bg_filled(inp, out):
    # picks the wrong color: the background color itself is treated as core
    bg, corner, side, dia, shell, core = _analyse(inp)
    return _paint(inp, corner, 0 if bg != 0 else 5)


def alt_single_diagonal_only(inp, out):
    # keeps only corner cells that touch exactly one ink cell diagonally
    bg, corner, side, dia, shell, core = _analyse(inp)
    col = _one(core)
    if col is None:
        return None
    h, w = len(inp), len(inp[0])

    def n(r, c):
        return sum(
            0 <= r + dr < h and 0 <= c + dc < w and inp[r + dr][c + dc] != bg
            for dr, dc in DG
        )

    return _paint(inp, [(r, c) for r, c in corner if n(r, c) == 1], col)


def alt_transposed(inp, out):
    return [list(r) for r in zip(*out)]


ALTERNATIVES = [
    ("paint the corner-only cells with the shell color instead of the core color", alt_shell_color),
    ("paint the orthogonally adjacent background cells with the core color instead of the diagonal ones", alt_side_cells),
    ("paint every background cell adjacent (8-neighbour) to ink with the core color", alt_all_adjacent),
    ("paint every background cell with a diagonal ink neighbour, even if it also touches ink orthogonally", alt_any_diagonal),
    ("paint only the corner-only cells in the upper half of the shape", alt_top_half_only),
    ("paint the corner-only cells with a one-row-down offset", alt_shifted_down),
    ("erase the core cells to background in addition to the true marks", alt_erase_core),
    ("recolor the shell to the core color in addition to the true marks", alt_shell_recolored),
    ("extend each corner mark one more step diagonally outward", alt_corners_erased),
    ("paint the corner-only cells with the wrong color 0 (or 5) instead of the core color", alt_bg_filled),
    ("paint only the corner-only cells that touch exactly one ink cell diagonally", alt_single_diagonal_only),
    ("output is the true output transposed (wrong orientation)", alt_transposed),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/396d80d7.json").read_text())
    pairs = task["train"]
    print(f"pairs: {len(pairs)}")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
