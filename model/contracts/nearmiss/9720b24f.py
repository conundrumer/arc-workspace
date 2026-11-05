import json
from collections import Counter
from pathlib import Path

DIRS4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _copy(g):
    return [row[:] for row in g]


def _erased(inp, out):
    return [(r, c) for r in range(len(inp)) for c in range(len(inp[0]))
            if inp[r][c] != out[r][c]]


def _ray(inp, r, c, d, skip=()):
    """First non-zero cell colour seen from (r, c) in direction d, skipping cells in skip."""
    h, w = len(inp), len(inp[0])
    r += d[0]
    c += d[1]
    while 0 <= r < h and 0 <= c < w:
        if inp[r][c] != 0 and (r, c) not in skip:
            return inp[r][c]
        r += d[0]
        c += d[1]
    return None


def _bracketed(inp, r, c, d1, d2, skip):
    a = _ray(inp, r, c, d1, skip)
    b = _ray(inp, r, c, d2, skip)
    return a is not None and b is not None and a != inp[r][c] and b != inp[r][c]


def unchanged(inp, out):
    return _copy(inp)


def keep_dominant_color_only(inp, out):
    cnt = Counter(v for row in inp for v in row if v != 0)
    top = cnt.most_common(1)[0][0]
    return [[v if v == top else 0 for v in row] for row in inp]


def fill_with_container_color(inp, out):
    g = _copy(out)
    er = set(_erased(inp, out))
    for r, c in er:
        cols = Counter(x for x in (_ray(inp, r, c, d, er) for d in DIRS4) if x is not None)
        if cols:
            g[r][c] = cols.most_common(1)[0][0]
    return g


def erase_container_instead(inp, out):
    er = set(_erased(inp, out))
    g = _copy(inp)
    for r, c in er:
        cols = Counter(x for x in (_ray(inp, r, c, d, er) for d in DIRS4) if x is not None)
        if cols:
            k = cols.most_common(1)[0][0]
            for rr in range(len(g)):
                for cc in range(len(g[0])):
                    if inp[rr][cc] == k and (rr, cc) not in er:
                        g[rr][cc] = 0
    return g


def horizontal_only(inp, out):
    g = _copy(out)
    er = set(_erased(inp, out))
    for r, c in er:
        if not _bracketed(inp, r, c, (0, -1), (0, 1), er):
            g[r][c] = inp[r][c]
    return g


def vertical_only(inp, out):
    g = _copy(out)
    er = set(_erased(inp, out))
    for r, c in er:
        if not _bracketed(inp, r, c, (-1, 0), (1, 0), er):
            g[r][c] = inp[r][c]
    return g


def all_four_sides_required(inp, out):
    g = _copy(out)
    er = set(_erased(inp, out))
    for r, c in er:
        ok = all(_ray(inp, r, c, d, er) not in (None, inp[r][c]) for d in DIRS4)
        if not ok:
            g[r][c] = inp[r][c]
    return g


def erase_with_margin(inp, out):
    g = _copy(out)
    h, w = len(g), len(g[0])
    for r, c in _erased(inp, out):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc < w:
                    g[rr][cc] = 0
    return g


def erase_intruder_colors_everywhere(inp, out):
    cols = {inp[r][c] for r, c in _erased(inp, out)}
    return [[0 if v in cols else v for v in row] for row in inp]


def erase_inside_color_bboxes(inp, out):
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    boxes = {}
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v:
                b = boxes.setdefault(v, [r, r, c, c])
                b[0] = min(b[0], r); b[1] = max(b[1], r)
                b[2] = min(b[2], c); b[3] = max(b[3], c)
    for k, (r0, r1, c0, c1) in boxes.items():
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if inp[r][c] not in (0, k):
                    g[r][c] = 0
    return g


def crop_to_dominant_color_box(inp, out):
    cnt = Counter(v for row in inp for v in row if v != 0)
    top = cnt.most_common(1)[0][0]
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == top]
    r0 = min(r for r, _ in cells); r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells); c1 = max(c for _, c in cells)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


ALTERNATIVES = [
    ("Output is the input unchanged (no erasing)", unchanged),
    ("Keep only the most common non-background colour and erase every other colour", keep_dominant_color_only),
    ("Erased cells take the surrounding container's colour instead of background", fill_with_container_color),
    ("The surrounding container is erased and the intruder cells stay", erase_container_instead),
    ("Only cells bracketed left and right by another colour are erased", horizontal_only),
    ("Only cells bracketed above and below by another colour are erased", vertical_only),
    ("A cell is erased only if another colour is seen in all four directions", all_four_sides_required),
    ("Erase the intruder cells and also every cell in their 8-neighbourhood", erase_with_margin),
    ("Erase every cell of an intruder colour everywhere, also outside containers", erase_intruder_colors_everywhere),
    ("Erase every cell of another colour inside the bounding box of each colour", erase_inside_color_bboxes),
    ("Output is the input cropped to the bounding box of the most common colour", crop_to_dominant_color_box),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/9720b24f.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
