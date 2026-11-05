"""Near-miss rules for dc433765.

True rule: the 3 moves one step toward the 4 (sign of the row difference and
sign of the column difference, 0 on an axis where both are level); the 4 stays.
"""
import json
from pathlib import Path


def _find(g, c):
    for r, row in enumerate(g):
        for k, v in enumerate(row):
            if v == c:
                return r, k
    return None


def _sign(x):
    return (x > 0) - (x < 0)


def _clamp(g, r, c):
    return min(max(r, 0), len(g) - 1), min(max(c, 0), len(g[0]) - 1)


def _blank(g):
    return [[0] * len(row) for row in g]


def _render(g, cells):
    o = _blank(g)
    for (r, c), v in cells:
        o[r][c] = v
    return o


def _pos(inp):
    return _find(inp, 3), _find(inp, 4)


def unchanged(inp, out):
    return [row[:] for row in inp]


def only_row_axis(inp, out):
    (r3, c3), (r4, c4) = _pos(inp)
    return _render(inp, [((r4, c4), 4), ((r3 + _sign(r4 - r3), c3), 3)])


def only_col_axis(inp, out):
    (r3, c3), (r4, c4) = _pos(inp)
    return _render(inp, [((r4, c4), 4), ((r3, c3 + _sign(c4 - c3)), 3)])


def away_from_target(inp, out):
    (r3, c3), (r4, c4) = _pos(inp)
    r, c = _clamp(inp, r3 - _sign(r4 - r3), c3 - _sign(c4 - c3))
    return _render(inp, [((r4, c4), 4), ((r, c), 3)])


def copy_not_move(inp, out):
    (r3, c3), (r4, c4) = _pos(inp)
    return _render(inp, [((r3, c3), 3), ((r4, c4), 4),
                         ((r3 + _sign(r4 - r3), c3 + _sign(c4 - c3)), 3)])


def target_moves_instead(inp, out):
    (r3, c3), (r4, c4) = _pos(inp)
    return _render(inp, [((r3, c3), 3), ((r4 + _sign(r3 - r4), c4 + _sign(c3 - c4)), 4)])


def both_move(inp, out):
    (r3, c3), (r4, c4) = _pos(inp)
    return _render(inp, [((r4 + _sign(r3 - r4), c4 + _sign(c3 - c4)), 4),
                         ((r3 + _sign(r4 - r3), c3 + _sign(c4 - c3)), 3)])


def mover_erased(inp, out):
    (r3, c3), (r4, c4) = _pos(inp)
    return _render(inp, [((r4, c4), 4)])


def colors_swapped(inp, out):
    (r3, c3), (r4, c4) = _pos(inp)
    return _render(inp, [((r4, c4), 4), ((r3 + _sign(r4 - r3), c3 + _sign(c4 - c3)), 4)])


def jump_to_midpoint(inp, out):
    (r3, c3), (r4, c4) = _pos(inp)
    dr, dc = r4 - r3, c4 - c3
    r = r3 + _sign(dr) * ((abs(dr) + 1) // 2)
    c = c3 + _sign(dc) * ((abs(dc) + 1) // 2)
    return _render(inp, [((r4, c4), 4), ((r, c), 3)])


def swapped_axes(inp, out):
    (r3, c3), (r4, c4) = _pos(inp)
    r, c = _clamp(inp, r3 + _sign(c4 - c3), c3 + _sign(r4 - r3))
    return _render(inp, [((r4, c4), 4), ((r, c), 3)])


def two_steps(inp, out):
    (r3, c3), (r4, c4) = _pos(inp)
    r, c = _clamp(inp, r3 + 2 * _sign(r4 - r3), c3 + 2 * _sign(c4 - c3))
    return _render(inp, [((r4, c4), 4), ((r, c), 3)])


ALTERNATIVES = [
    ("nothing moves; the input is the output", unchanged),
    ("3 steps toward the 4 along the row axis only", only_row_axis),
    ("3 steps toward the 4 along the column axis only", only_col_axis),
    ("3 steps away from the 4 (clamped to the grid)", away_from_target),
    ("3 is copied one step toward the 4, the old 3 stays", copy_not_move),
    ("the 4 steps toward the 3, the 3 stays", target_moves_instead),
    ("both the 3 and the 4 step toward each other", both_move),
    ("the 3 is erased and not redrawn", mover_erased),
    ("the moved cell gets color 4 and the 3 is erased", colors_swapped),
    ("3 jumps to the midpoint, rounding the half step toward the 4", jump_to_midpoint),
    ("row step uses the column difference and column step uses the row difference", swapped_axes),
    ("3 steps two cells toward the 4 (clamped to the grid)", two_steps),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/dc433765.json").read_text())
    pairs = task["train"]
    print(f"pairs: {len(pairs)}")
    for desc, fn in ALTERNATIVES:
        n = sum(1 for p in pairs if _valid(fn(p["input"], p["output"]), p["output"]))
        print(f"{n}/{len(pairs)}  {desc}")
