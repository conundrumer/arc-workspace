"""Near-miss readings for ARC task 12eac192.

True rule: split the non-zero cells into 4-connected components of one color;
a component with fewer than 3 cells is repainted 3, other components stay.
"""
import json
from pathlib import Path

BG = 0
PAINT = 3
N4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
N8 = N4 + [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def _components(g, nbrs, same_color):
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    for i in range(h):
        for j in range(w):
            if g[i][j] == BG or (i, j) in seen:
                continue
            seen.add((i, j))
            stack = [(i, j)]
            cells = []
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for da, db in nbrs:
                    c, d = a + da, b + db
                    if 0 <= c < h and 0 <= d < w and (c, d) not in seen and g[c][d] != BG:
                        if same_color and g[c][d] != g[a][b]:
                            continue
                        seen.add((c, d))
                        stack.append((c, d))
            comps.append(cells)
    return comps


def _repaint(g, pred, color=PAINT, nbrs=N4, same_color=True):
    out = [r[:] for r in g]
    for cells in _components(g, nbrs, same_color):
        if pred(cells, g):
            for a, b in cells:
                out[a][b] = color
    return out


def threshold_1(inp, out):
    return _repaint(inp, lambda c, g: len(c) <= 1)


def threshold_3(inp, out):
    return _repaint(inp, lambda c, g: len(c) <= 3)


def threshold_4(inp, out):
    return _repaint(inp, lambda c, g: len(c) <= 4)


def eight_connected(inp, out):
    return _repaint(inp, lambda c, g: len(c) <= 2, nbrs=N8)


def mixed_color_components(inp, out):
    return _repaint(inp, lambda c, g: len(c) <= 2, same_color=False)


def paint_one(inp, out):
    return _repaint(inp, lambda c, g: len(c) <= 2, color=1)


def erase_small(inp, out):
    return _repaint(inp, lambda c, g: len(c) <= 2, color=BG)


def repaint_large(inp, out):
    return _repaint(inp, lambda c, g: len(c) >= 3)


def only_colors_1_and_5(inp, out):
    return _repaint(inp, lambda c, g: len(c) <= 2 and g[c[0][0]][c[0][1]] in (1, 5))


def skip_color_7(inp, out):
    return _repaint(inp, lambda c, g: len(c) <= 2 and g[c[0][0]][c[0][1]] != 7)


def paint_whole_grid_colors(inp, out):
    # recolor every cell of colors 1 and 5, ignoring size
    return [[PAINT if v in (1, 5) else v for v in r] for r in inp]


def mirrored_output(inp, out):
    return [r[::-1] for r in out]


ALTERNATIVES = [
    ("only isolated single cells are repainted (size threshold 1)", threshold_1),
    ("components of up to 3 cells are repainted (threshold too high by one)", threshold_3),
    ("components of up to 4 cells are repainted (threshold too high by two)", threshold_4),
    ("components are 8-connected, so diagonal neighbors join", eight_connected),
    ("components join touching cells of different colors", mixed_color_components),
    ("small components are repainted with color 1 instead of 3", paint_one),
    ("small components are erased to background instead of repainted", erase_small),
    ("large components are repainted instead of small ones", repaint_large),
    ("only small components of color 1 or 5 are repainted", only_colors_1_and_5),
    ("small components of color 7 are left alone", skip_color_7),
    ("every cell of color 1 or 5 is repainted regardless of size", paint_whole_grid_colors),
    ("true output mirrored left to right", mirrored_output),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/12eac192.json").read_text())
    pairs = task["train"]
    # sanity: the true rule reproduces every output
    ok = all(_repaint(p["input"], lambda c, g: len(c) <= 2) == p["output"] for p in pairs)
    print("true rule reproduces outputs:", ok)
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
