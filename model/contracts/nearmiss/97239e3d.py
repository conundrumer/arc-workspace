import json
from pathlib import Path


def _boxes(inp):
    """Map color -> (r1, c1, r2, c2): bounding box of the crossings the marks snap to."""
    cells = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v not in (0, 8):
                cells.setdefault(v, []).append((r, c))
    boxes = {}
    for col, ps in cells.items():
        rs = [round(r / 4) * 4 for r, _ in ps]
        cs = [round(c / 4) * 4 for _, c in ps]
        boxes[col] = (min(rs), min(cs), max(rs), max(cs))
    return boxes


def _kind(inp, r, c):
    v = inp[r][c]
    if v == 8:
        return "ring"
    if r % 4 == 0 or c % 4 == 0:
        return "street"
    return "hole"


def _paint(inp, boxes, border=True, streets=False, holes=True, rings=False,
           color=None, base=None):
    g = [list(row) for row in (base if base is not None else inp)]
    n, m = len(inp), len(inp[0])
    for col, (r1, c1, r2, c2) in boxes.items():
        k = col if color is None else color
        for r in range(max(r1, 0), min(r2, n - 1) + 1):
            for c in range(max(c1, 0), min(c2, m - 1) + 1):
                edge = r in (r1, r2) or c in (c1, c2)
                kind = _kind(inp, r, c)
                if edge:
                    if border:
                        g[r][c] = k
                elif kind == "street":
                    if streets:
                        g[r][c] = k
                elif kind == "hole":
                    if holes:
                        g[r][c] = k
                elif rings:
                    g[r][c] = k
    return g


def outline_only(inp, out):
    return _paint(inp, _boxes(inp), holes=False)


def holes_only(inp, out):
    return _paint(inp, _boxes(inp), border=False)


def streets_filled(inp, out):
    return _paint(inp, _boxes(inp), streets=True)


def solid_box(inp, out):
    return _paint(inp, _boxes(inp), streets=True, rings=True)


def expanded_box(inp, out):
    b = {k: (r1 - 4, c1 - 4, r2 + 4, c2 + 4) for k, (r1, c1, r2, c2) in _boxes(inp).items()}
    return _paint(inp, b)


def drop_far_edge(inp, out):
    b = {k: (r1, c1, r2 - 1, c2 - 1) for k, (r1, c1, r2, c2) in _boxes(inp).items()}
    return _paint(inp, b)


def wrong_color(inp, out):
    return _paint(inp, _boxes(inp), color=8)


def transposed_marks(inp, out):
    b = {k: (c1, r1, c2, r2) for k, (r1, c1, r2, c2) in _boxes(inp).items()}
    return _paint(inp, b)


def full_lines(inp, out):
    g = [list(row) for row in inp]
    for col, (r1, c1, r2, c2) in _boxes(inp).items():
        for r in (r1, r2):
            for c in range(len(inp[0])):
                g[r][c] = col
        for c in (c1, c2):
            for r in range(len(inp)):
                g[r][c] = col
    return g


def first_color_only(inp, out):
    b = _boxes(inp)
    if len(b) < 2:
        return None
    first = min(b)
    return _paint(inp, {first: b[first]})


def all_holes_filled(inp, out):
    b = _boxes(inp)
    g = _paint(inp, b)
    col = min(b)
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            if inp[r][c] == 0 and _kind(inp, r, c) == "hole" and g[r][c] == 0:
                g[r][c] = col
    return g


def unchanged(inp, out):
    return [list(row) for row in inp]


ALTERNATIVES = [
    ("outline the box on the streets but leave the ring holes unfilled", outline_only),
    ("fill the ring holes inside the box but draw no outline", holes_only),
    ("also paint the interior streets of the box", streets_filled),
    ("paint the whole box solid, rings included", solid_box),
    ("box grows by one block on every side", expanded_box),
    ("box loses its bottom row and right column", drop_far_edge),
    ("paint the box with color 8 instead of the mark color", wrong_color),
    ("take the marks' row and column swapped when placing the box", transposed_marks),
    ("draw full-width street lines through the crossings, no box", full_lines),
    ("paint only the box of the lowest mark color", first_color_only),
    ("fill the holes of every ring in the grid with the lowest mark color", all_holes_filled),
    ("return the input unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/97239e3d.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
