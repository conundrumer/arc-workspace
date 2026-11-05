"""Near-miss rules for ed36ccf7. The true rule rotates the grid 90 degrees counter-clockwise."""
import json
from pathlib import Path


def _ccw(g):
    h, w = len(g), len(g[0])
    return [[g[r][w - 1 - c] for r in range(h)] for c in range(w)]


def _cw(g):
    h, w = len(g), len(g[0])
    return [[g[h - 1 - r][c] for r in range(h)] for c in range(w)]


def _r180(g):
    return [row[::-1] for g_ in [g] for row in g_[::-1]]


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _anti(g):
    return _r180(_transpose(g))


def _fliph(g):
    return [row[::-1] for row in g]


def _flipv(g):
    return [row[:] for row in g[::-1]]


def _nonzero_color(g):
    return max(v for row in g for v in row)


def rotate_cw(inp, out):
    return _cw(inp)


def rotate_180(inp, out):
    return _r180(inp)


def transpose(inp, out):
    return _transpose(inp)


def anti_transpose(inp, out):
    return _anti(inp)


def mirror_horizontal(inp, out):
    return _fliph(inp)


def mirror_vertical(inp, out):
    return _flipv(inp)


def unchanged(inp, out):
    return [row[:] for row in inp]


def ccw_then_flip_rows(inp, out):
    return _flipv(out)


def ccw_then_flip_cols(inp, out):
    return _fliph(out)


def rotate_top_left_2x2(inp, out):
    # Apply the rotation only to the top-left 2x2 block.
    g = [row[:] for row in inp]
    a, b, c, d = g[0][0], g[0][1], g[1][0], g[1][1]
    g[0][0], g[0][1], g[1][0], g[1][1] = b, d, a, c
    return g


def ccw_off_by_one_roll(inp, out):
    # Correct rotation, then the rows shifted cyclically down by one.
    return [out[-1][:]] + [r[:] for r in out[:-1]]


def ccw_swap_colors(inp, out):
    # Correct rotation, but background and color swapped.
    col = _nonzero_color(inp)
    return [[0 if v == col else col for v in row] for row in out]


def _skip_equal(fn):
    def wrapped(inp, out):
        g = fn(inp, out)
        return None if g == out else g
    wrapped.__name__ = fn.__name__
    return wrapped


_RAW = [
    ("rotate 90 degrees clockwise instead of counter-clockwise", rotate_cw),
    ("rotate 180 degrees", rotate_180),
    ("transpose along the main diagonal", transpose),
    ("transpose along the anti-diagonal", anti_transpose),
    ("mirror left-right", mirror_horizontal),
    ("mirror top-bottom", mirror_vertical),
    ("return the input unchanged", unchanged),
    ("rotate counter-clockwise, then flip top-bottom", ccw_then_flip_rows),
    ("rotate counter-clockwise, then flip left-right", ccw_then_flip_cols),
    ("rotate only the top-left 2x2 block", rotate_top_left_2x2),
    ("rotate counter-clockwise, then shift rows down by one with wrap", ccw_off_by_one_roll),
    ("rotate counter-clockwise, then swap 0 and the color", ccw_swap_colors),
]

ALTERNATIVES = [(d, _skip_equal(f)) for d, f in _RAW]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/ed36ccf7.json'))
    pairs = task["train"]
    assert all(_ccw(p["input"]) == p["output"] for p in pairs)
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
