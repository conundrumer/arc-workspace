import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _parse(inp):
    """Return (bg, ink color, block cells, [(tail r, tail c, dr, dc)])."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    ink = {(r, c) for r in range(h) for c in range(w) if inp[r][c] != bg}
    block = set()
    for (r, c) in ink:
        if any((r + a, c + b) in ink for a, b in ((0, 1), (1, 0), (0, -1), (-1, 0))):
            block.add((r, c))
    tails = []
    for (r, c) in sorted(ink - block):
        for a, b in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            if (r - a, c - b) in block:
                tails.append((r, c, a, b))
    color = inp[next(iter(ink))[0]][next(iter(ink))[1]] if ink else 0
    return bg, color, block, tails


def _copy(g):
    return [list(r) for r in g]


def _ray(g, r, c, a, b, color, limit=None, skip=0):
    h, w = len(g), len(g[0])
    n = 0
    r += a
    c += b
    while 0 <= r < h and 0 <= c < w:
        n += 1
        if n > skip and (limit is None or n - skip <= limit):
            g[r][c] = color
        r += a
        c += b


def reverse_direction(inp, out):
    bg, color, block, tails = _parse(inp)
    g = _copy(inp)
    for r, c, a, b in tails:
        _ray(g, r, c, -a, -b, color)
    return g


def one_cell_only(inp, out):
    bg, color, block, tails = _parse(inp)
    g = _copy(inp)
    for r, c, a, b in tails:
        _ray(g, r, c, a, b, color, limit=1)
    return g


def first_tail_only(inp, out):
    bg, color, block, tails = _parse(inp)
    g = _copy(inp)
    r, c, a, b = tails[0]
    _ray(g, r, c, a, b, color)
    return g


def rotated_direction(inp, out):
    bg, color, block, tails = _parse(inp)
    g = _copy(inp)
    for r, c, a, b in tails:
        _ray(g, r, c, b, -a, color)
    return g


def all_block_corners(inp, out):
    bg, color, block, tails = _parse(inp)
    g = _copy(inp)
    for (r, c) in block:
        for a, b in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            if (r + a, c + b) not in block and all(
                (r + a * k, c + b * j) not in block for k, j in ((1, 0), (0, 1))
            ):
                _ray(g, r, c, a, b, color)
    return g


def wrong_color(inp, out):
    bg, color, block, tails = _parse(inp)
    other = 5 if color != 5 else 6
    g = _copy(out)
    for r, c, a, b in tails:
        rr, cc = r + a, c + b
        while 0 <= rr < len(g) and 0 <= cc < len(g[0]):
            g[rr][cc] = other
            rr += a
            cc += b
    return g


def full_diagonal_line(inp, out):
    bg, color, block, tails = _parse(inp)
    g = _copy(out)
    for r, c, a, b in tails:
        _ray(g, r, c, -a, -b, color)
    return g


def half_length(inp, out):
    bg, color, block, tails = _parse(inp)
    g = _copy(inp)
    for r, c, a, b in tails:
        h, w = len(g), len(g[0])
        rr, cc, n = r + a, c + b, 0
        while 0 <= rr < h and 0 <= cc < w:
            n += 1
            rr += a
            cc += b
        _ray(g, r, c, a, b, color, limit=n // 2)
    return g


def skip_first_cell(inp, out):
    bg, color, block, tails = _parse(inp)
    g = _copy(inp)
    for r, c, a, b in tails:
        _ray(g, r, c, a, b, color, skip=1)
    return g


def straight_vertical(inp, out):
    bg, color, block, tails = _parse(inp)
    g = _copy(inp)
    for r, c, a, b in tails:
        _ray(g, r, c, a, 0, color)
    return g


def crop_to_ink(inp, out):
    bg, color, block, tails = _parse(out)
    cells = [(r, c) for r in range(len(out)) for c in range(len(out[0])) if out[r][c] != bg]
    r0 = min(r for r, c in cells)
    r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells)
    c1 = max(c for r, c in cells)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("rays go from each tail toward and through the block, not away", reverse_direction),
    ("each ray is only one cell long", one_cell_only),
    ("only the first tail casts a ray", first_tail_only),
    ("rays turn 90 degrees from the tail's diagonal", rotated_direction),
    ("rays are cast from every free diagonal corner of the block", all_block_corners),
    ("rays are drawn in a wrong color", wrong_color),
    ("rays extend past the tail toward the block side, forming a full diagonal line", full_diagonal_line),
    ("each ray covers only half the distance to the edge", half_length),
    ("each ray starts one cell beyond the tail", skip_first_cell),
    ("rays run straight vertically instead of diagonally", straight_vertical),
    ("output is cropped to the bounding box of the drawn cells", crop_to_ink),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/7ddcd7ec.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
