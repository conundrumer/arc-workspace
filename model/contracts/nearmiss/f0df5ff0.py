import json
from collections import Counter
from pathlib import Path


def _colors(inp):
    c = Counter(v for r in inp for v in r)
    bg = c.most_common(1)[0][0]
    ink = min(c, key=lambda k: (c[k], k))
    return bg, ink, c


def _dilate(inp, offsets, color=None, only_bg=True, erase_seed=False):
    bg, ink, _ = _colors(inp)
    if color is None:
        color = ink
    h, w = len(inp), len(inp[0])
    g = [r[:] for r in inp]
    for r in range(h):
        for c in range(w):
            if inp[r][c] != ink:
                continue
            for dr, dc in offsets:
                rr, cc = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc < w and (not only_bg or inp[rr][cc] == bg):
                    g[rr][cc] = color
    if erase_seed:
        for r in range(h):
            for c in range(w):
                if inp[r][c] == ink:
                    g[r][c] = bg
    return g


def _box(rad):
    return [(a, b) for a in range(-rad, rad + 1) for b in range(-rad, rad + 1) if (a, b) != (0, 0)]


def cross(inp, out):
    return _dilate(inp, [(-1, 0), (1, 0), (0, -1), (0, 1)])


def diagonal(inp, out):
    return _dilate(inp, [(-1, -1), (-1, 1), (1, -1), (1, 1)])


def radius2(inp, out):
    return _dilate(inp, _box(2))


def overwrite(inp, out):
    return _dilate(inp, _box(1), only_bg=False)


def wrong_color(inp, out):
    bg, ink, c = _colors(inp)
    others = [k for k, _ in c.most_common() if k not in (bg, ink)]
    return _dilate(inp, _box(1), color=others[0])


def forward_half(inp, out):
    return _dilate(inp, [(0, 1), (1, -1), (1, 0), (1, 1)])


def erase_seed(inp, out):
    return _dilate(inp, _box(1), erase_seed=True)


def seed_any_color(inp, out):
    bg, ink, _ = _colors(inp)
    h, w = len(inp), len(inp[0])
    g = [r[:] for r in inp]
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg and any(
                0 <= r + a < h and 0 <= c + b < w and inp[r + a][c + b] != bg
                for a, b in _box(1)
            ):
                g[r][c] = ink
    return g


def shifted(inp, out):
    return _dilate(inp, [(a + 1, b + 1) for a, b in _box(1) + [(0, 0)]])


def crop_painted(inp, out):
    bg, ink, _ = _colors(inp)
    cells = [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v == ink and inp[r][c] != ink]
    if not cells:
        return None
    r0, r1 = min(r for r, _ in cells), max(r for r, _ in cells)
    c0, c1 = min(c for _, c in cells), max(c for _, c in cells)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def first_block_missed(inp, out):
    bg, ink, _ = _colors(inp)
    h, w = len(inp), len(inp[0])
    for r in range(h):
        for c in range(w):
            if inp[r][c] == ink:
                g = [row[:] for row in out]
                for a, b in _box(1):
                    rr, cc = r + a, c + b
                    if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] == bg:
                        g[rr][cc] = bg
                return g
    return None


def top_half_only(inp, out):
    h = len(inp)
    g = [r[:] for r in out]
    for r in range(h // 2, h):
        g[r] = inp[r][:]
    return g


ALTERNATIVES = [
    ("paint only the 4 orthogonal neighbours of each ink cell", cross),
    ("paint only the 4 diagonal neighbours of each ink cell", diagonal),
    ("paint a 5x5 neighbourhood around each ink cell", radius2),
    ("paint the 3x3 neighbourhood over every cell, including non-background", overwrite),
    ("paint the 3x3 neighbourhood with the most common non-background colour", wrong_color),
    ("paint only the right and lower neighbours of each ink cell", forward_half),
    ("paint the 3x3 neighbourhood and erase the original ink cells", erase_seed),
    ("every non-background colour seeds painting, not only the rarest", seed_any_color),
    ("paint block offset one cell down and right of the ink cell", shifted),
    ("output the bounding box of the painted cells only", crop_painted),
    ("the first ink cell in reading order gets no painted neighbourhood", first_block_missed),
    ("only the top half of the grid is painted", top_half_only),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/f0df5ff0.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
