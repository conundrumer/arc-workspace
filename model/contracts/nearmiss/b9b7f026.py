"""Near-miss rules for b9b7f026: the output is the color of the rectangle that encloses a hole."""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _boxes(inp):
    bg = _bg(inp)
    d = {}
    for i, r in enumerate(inp):
        for j, c in enumerate(r):
            if c == bg:
                continue
            b = d.setdefault(c, [i, i, j, j, 0])
            b[0] = min(b[0], i)
            b[1] = max(b[1], i)
            b[2] = min(b[2], j)
            b[3] = max(b[3], j)
            b[4] += 1
    return d


def _holed(inp):
    for c, (r0, r1, c0, c1, n) in _boxes(inp).items():
        if (r1 - r0 + 1) * (c1 - c0 + 1) > n:
            return c
    return None


def _one(c):
    return [[c]]


def _pick(key):
    def f(inp, out):
        d = _boxes(inp)
        return _one(min(d, key=lambda c: key(d[c], c)))
    return f


def _holed_crop(inp, out):
    c = _holed(inp)
    r0, r1, c0, c1, _ = _boxes(inp)[c]
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def _hole_crop(inp, out):
    c = _holed(inp)
    bg = _bg(inp)
    r0, r1, c0, c1, _ = _boxes(inp)[c]
    cells = [(i, j) for i in range(r0, r1 + 1) for j in range(c0, c1 + 1) if inp[i][j] == bg]
    a0 = min(i for i, _ in cells); a1 = max(i for i, _ in cells)
    b0 = min(j for _, j in cells); b1 = max(j for _, j in cells)
    return [row[b0:b1 + 1] for row in inp[a0:a1 + 1]]


def _filled(inp, out):
    c = _holed(inp)
    bg = _bg(inp)
    r0, r1, c0, c1, _ = _boxes(inp)[c]
    g = [list(r) for r in inp]
    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            if g[i][j] == bg:
                g[i][j] = c
    return g


def _hole_area(inp, out):
    c = _holed(inp)
    r0, r1, c0, c1, n = _boxes(inp)[c]
    return _one((r1 - r0 + 1) * (c1 - c0 + 1) - n)


def _second_largest(inp, out):
    d = _boxes(inp)
    cs = sorted(d, key=lambda c: -d[c][4])
    return _one(cs[1])


def _nearest_to_holed(inp, out):
    d = _boxes(inp)
    h = _holed(inp)
    hr = (d[h][0] + d[h][1]) / 2
    hc = (d[h][2] + d[h][3]) / 2
    others = [c for c in d if c != h]
    return _one(min(others, key=lambda c: abs((d[c][0] + d[c][1]) / 2 - hr) + abs((d[c][2] + d[c][3]) / 2 - hc)))


ALTERNATIVES = [
    ("color of the rectangle with the most cells", _pick(lambda b, c: -b[4])),
    ("color of the rectangle with the fewest cells", _pick(lambda b, c: b[4])),
    ("color of the topmost rectangle", _pick(lambda b, c: (b[0], b[2]))),
    ("color of the bottommost rectangle", _pick(lambda b, c: (-b[1], b[2]))),
    ("color of the leftmost rectangle", _pick(lambda b, c: (b[2], b[0]))),
    ("color of the rectangle with the widest bounding box", _pick(lambda b, c: -(b[3] - b[2]))),
    ("output the hole's own color (background) as a 1x1 grid", lambda inp, out: _one(_bg(inp))),
    ("crop of the holed rectangle's bounding box instead of its color", _holed_crop),
    ("crop of the hole region only", _hole_crop),
    ("input with the hole filled with the holed rectangle's color", _filled),
    ("1x1 grid holding the hole's cell count as a color", _hole_area),
    ("color of the second-largest rectangle", _second_largest),
    ("color of the rectangle nearest the holed one", _nearest_to_holed),
][:12]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) and r for r in g)
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b9b7f026.json").read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error:", desc, e)
                continue
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
