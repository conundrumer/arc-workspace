"""Near-miss readings for 9110e3c5.

Rule: the most common non-zero color in the 7x7 input picks a 3x3 glyph drawn in 8.
"""
import json
from collections import Counter
from pathlib import Path

GLYPH_A = [[0, 0, 8], [8, 8, 0], [0, 8, 0]]
GLYPH_B = [[0, 0, 0], [8, 8, 8], [0, 0, 0]]
GLYPH_C = [[0, 8, 8], [0, 8, 0], [0, 8, 0]]
BY_COLOR = {1: GLYPH_A, 2: GLYPH_B, 3: GLYPH_C}
GLYPHS = [GLYPH_A, GLYPH_B, GLYPH_C]


def _copy(g):
    return [list(r) for r in g]


def _counts(inp):
    return Counter(v for r in inp for v in r if v != 0)


def _ranked(inp):
    c = _counts(inp)
    return sorted(c, key=lambda k: (-c[k], k))


def _components(inp, diag=False):
    h, w = len(inp), len(inp[0])
    seen = set()
    sizes = {}
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diag:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    for i in range(h):
        for j in range(w):
            if inp[i][j] == 0 or (i, j) in seen:
                continue
            col = inp[i][j]
            stack = [(i, j)]
            seen.add((i, j))
            n = 0
            while stack:
                a, b = stack.pop()
                n += 1
                for da, db in steps:
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and (x, y) not in seen and inp[x][y] == col:
                        seen.add((x, y))
                        stack.append((x, y))
            sizes[col] = max(sizes.get(col, 0), n)
    return sizes


def _glyph_of(col):
    # Colors outside the three seen in the train pairs reuse the glyphs cyclically.
    g = BY_COLOR.get(col) or GLYPHS[(col - 1) % 3]
    return _copy(g)


def _true_color(inp):
    return _ranked(inp)[0]


def second_most_common(inp, out):
    r = _ranked(inp)
    return _glyph_of(r[1]) if len(r) > 1 else None


def least_common(inp, out):
    c = _counts(inp)
    col = min(c, key=lambda k: (c[k], k))
    return _glyph_of(col)


def rolled_down(inp, out):
    # Glyph offset by one row (wrapping), an off-by-one placement.
    return [list(out[-1])] + [list(r) for r in out[:-1]]


def last_row_dropped(inp, out):
    # Too little drawn: the bottom row of the glyph is left empty.
    return [list(r) for r in out[:-1]] + [[0, 0, 0]]


def next_glyph_in_cycle(inp, out):
    k = GLYPHS.index(out) if out in GLYPHS else None
    return _copy(GLYPHS[(k + 1) % 3]) if k is not None else None


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def mirrored(inp, out):
    return [r[::-1] for r in out]


def rotated_cw(inp, out):
    return [list(r) for r in zip(*out[::-1])]


def wrong_ink(inp, out):
    c = _true_color(inp)
    return [[c if v else 0 for v in r] for r in out]


def inverted(inp, out):
    return [[0 if v else 8 for v in r] for r in out]


def counting_zero(inp, out):
    # Background counted as a color: 0 is most common, so no glyph is drawn.
    return [[0] * 3 for _ in range(3)]


def padded_crop(inp, out):
    # Off-by-one output size: a 4x4 canvas with the glyph in the top-left.
    g = [r + [0] for r in out]
    g.append([0] * 4)
    return g


ALTERNATIVES = [
    ("glyph of the second most common color", second_most_common),
    ("glyph of the least common color", least_common),
    ("glyph shifted down one row with wraparound", rolled_down),
    ("bottom row of the glyph left empty", last_row_dropped),
    ("output 4x4 canvas with the glyph in the top-left (size off by one)", padded_crop),
    ("next glyph in the cycle instead of the right one", next_glyph_in_cycle),
    ("glyph transposed", transposed),
    ("glyph mirrored left to right", mirrored),
    ("glyph rotated 90 degrees clockwise", rotated_cw),
    ("glyph drawn in the most common input color instead of 8", wrong_ink),
    ("glyph with ink and background swapped", inverted),
    ("background counted as a color: empty 3x3 output", counting_zero),
]



def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/9110e3c5.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
