"""Near-miss wrong readings for ARC task 981add89."""
import json
from collections import Counter
from pathlib import Path


def _field(inp):
    return Counter(c for row in inp for c in row).most_common(1)[0][0]


def _marks(inp):
    f = _field(inp)
    return [(c, v) for c, v in enumerate(inp[0]) if v != f]


def _render(inp, marks=None, flip=True, over_ink=True, stop=False,
            skip_last=False, width=1, paint=None, flip_all=False):
    f = _field(inp)
    h, w = len(inp), len(inp[0])
    if marks is None:
        marks = _marks(inp)
    g = [row[:] for row in inp]
    for c, v in marks:
        col = f if paint == "field" else v
        for r in range(1, h - (1 if skip_last else 0)):
            for cc in range(c, min(w, c + width)):
                cur = inp[r][cc]
                if cur != f and stop:
                    break
                if cur != f and not over_ink:
                    continue
                if cur != f and flip_all:
                    g[r][cc] = f
                elif cur == v and flip and cc == c:
                    g[r][cc] = f
                else:
                    g[r][cc] = col
            else:
                continue
            break
    return g


def no_flip(inp, out):
    return _render(inp, flip=False)


def keep_ink(inp, out):
    return _render(inp, over_ink=False)


def stop_at_ink(inp, out):
    return _render(inp, stop=True)


def only_first_mark(inp, out):
    return _render(inp, marks=_marks(inp)[:1])


def only_last_mark(inp, out):
    return _render(inp, marks=_marks(inp)[-1:])


def flip_every_overlap(inp, out):
    return _render(inp, flip_all=True)


def stop_short(inp, out):
    return _render(inp, skip_last=True)


def two_wide(inp, out):
    return _render(inp, width=2)


def erase_with_field(inp, out):
    return _render(inp, paint="field")


def horizontal_lines(inp, out):
    f = _field(inp)
    g = [row[:] for row in inp]
    for c, v in _marks(inp):
        g[0] = [v] * len(g[0])
    return g


def every_ink_projects(inp, out):
    f = _field(inp)
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for c in range(w):
        for r in range(h):
            if inp[r][c] != f:
                for rr in range(h):
                    g[rr][c] = inp[r][c]
                break
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("Marks paint their column fully, with no inversion where the ink under the line has the mark's color", no_flip),
    ("Marks paint only field cells and never overwrite other ink", keep_ink),
    ("Each line stops at the first ink cell it meets", stop_at_ink),
    ("Only the leftmost mark draws a line", only_first_mark),
    ("Only the rightmost mark draws a line", only_last_mark),
    ("Every ink cell under a line turns to field color, not only same-colored ones", flip_every_overlap),
    ("Each line stops one cell before the far edge", stop_short),
    ("Each line is two columns wide", two_wide),
    ("Lines are drawn in the field color", erase_with_field),
    ("Lines run along the marked edge instead of across the grid", horizontal_lines),
    ("Every top-most ink cell of a column fills its column, rectangles included", every_ink_projects),
    ("Output equals the input", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/981add89.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
