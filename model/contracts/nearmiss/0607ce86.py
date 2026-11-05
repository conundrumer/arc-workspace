"""Near-miss readings for ARC task 0607ce86.

The input holds several copies of one block pattern, spread over a noisy
background. The output keeps only the copies, each restored to the pattern
that most copies agree on, and clears everything else.
"""
import json
from collections import Counter
from pathlib import Path

BG = 0


def _blocks(out):
    """Bounding boxes (r0, c0, r1, c1), inclusive, of the connected non-bg regions of out."""
    h, w = len(out), len(out[0])
    seen = set()
    boxes = []
    for r in range(h):
        for c in range(w):
            if out[r][c] == BG or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            r0 = r1 = r
            c0 = c1 = c
            while stack:
                y, x = stack.pop()
                r0, r1, c0, c1 = min(r0, y), max(r1, y), min(c0, x), max(c1, x)
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and out[ny][nx] != BG and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            boxes.append((r0, c0, r1, c1))
    return sorted(boxes)


def _copy(g):
    return [list(r) for r in g]


def _crop(g, box):
    r0, c0, r1, c1 = box
    return [list(row[c0:c1 + 1]) for row in g[r0:r1 + 1]]


def _paste(g, box, tile):
    r0, c0, r1, c1 = box
    for i in range(r1 - r0 + 1):
        for j in range(c1 - c0 + 1):
            g[r0 + i][c0 + j] = tile[i][j]


def _differs(g, out):
    return g if g != out else None


def noisy_copies_kept(inp, out):
    # Cleans the background but leaves each copy as it appears in the input.
    g = _copy(out)
    for b in _blocks(out):
        _paste(g, b, _crop(inp, b))
    return _differs(g, out)


def first_copy_as_template(inp, out):
    # Takes the top-left copy, noise included, as the pattern for every copy.
    boxes = _blocks(out)
    tile = _crop(inp, boxes[0])
    g = _copy(out)
    for b in boxes:
        _paste(g, b, tile)
    return _differs(g, out)


def last_copy_as_template(inp, out):
    # Takes the bottom-right copy, noise included, as the pattern for every copy.
    boxes = _blocks(out)
    tile = _crop(inp, boxes[-1])
    g = _copy(out)
    for b in boxes:
        _paste(g, b, tile)
    return _differs(g, out)


def drop_minority_color(inp, out):
    # Treats the rarest non-background color as the noise color and erases it everywhere.
    counts = Counter(v for row in out for v in row if v != BG)
    rare = min(counts, key=lambda k: (counts[k], k))
    g = [[BG if v == rare else v for v in row] for row in out]
    return _differs(g, out)


def last_copy_erased(inp, out):
    # Misses the last copy and clears its region.
    boxes = _blocks(out)
    g = _copy(out)
    r0, c0, r1, c1 = boxes[-1]
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            g[r][c] = BG
    return _differs(g, out)


def crop_to_copies(inp, out):
    # Outputs only the bounding box of all copies.
    boxes = _blocks(out)
    r0 = min(b[0] for b in boxes)
    c0 = min(b[1] for b in boxes)
    r1 = max(b[2] for b in boxes)
    c1 = max(b[3] for b in boxes)
    return _differs(_crop(out, (r0, c0, r1, c1)), out)


def single_template_only(inp, out):
    # Outputs just one restored copy of the pattern.
    return _differs(_crop(out, _blocks(out)[0]), out)


def shifted_down_one(inp, out):
    # Places every restored copy one row too low.
    h, w = len(out), len(out[0])
    g = [[BG] * w] + [list(r) for r in out[:h - 1]]
    return _differs(g, out)


def shifted_right_one(inp, out):
    # Places every restored copy one column too far right.
    g = [[BG] + list(r[:-1]) for r in out]
    return _differs(g, out)


def background_noise_kept(inp, out):
    # Restores the copies but leaves the noise cells that lie outside them.
    boxes = _blocks(out)
    g = _copy(out)
    for r in range(len(out)):
        for c in range(len(out[0])):
            inside = any(b[0] <= r <= b[2] and b[1] <= c <= b[3] for b in boxes)
            if not inside:
                g[r][c] = inp[r][c]
    return _differs(g, out)


def copy_region_grown_by_one(inp, out):
    # Takes each copy's region one cell too large, so adjacent noise is kept as is.
    boxes = _blocks(out)
    h, w = len(out), len(out[0])
    g = _copy(out)
    for r in range(h):
        for c in range(w):
            if any(b[0] - 1 <= r <= b[2] + 1 and b[1] - 1 <= c <= b[3] + 1 for b in boxes):
                if not any(b[0] <= r <= b[2] and b[1] <= c <= b[3] for b in boxes):
                    g[r][c] = inp[r][c]
    return _differs(g, out)


def pattern_flipped_vertically(inp, out):
    # Restores the right pattern but draws it upside down in every copy.
    g = _copy(out)
    for b in _blocks(out):
        _paste(g, b, _crop(out, b)[::-1])
    return _differs(g, out)


ALTERNATIVES = [
    ("copies keep their input noise; only the background is cleared", noisy_copies_kept),
    ("top-left copy, noise included, is the pattern for all copies", first_copy_as_template),
    ("bottom-right copy, noise included, is the pattern for all copies", last_copy_as_template),
    ("rarest non-background color is taken as noise and erased everywhere", drop_minority_color),
    ("last copy is missed and cleared", last_copy_erased),
    ("output is cropped to the bounding box of the copies", crop_to_copies),
    ("output is a single restored copy", single_template_only),
    ("restored copies sit one row too low", shifted_down_one),
    ("restored copies sit one column too far right", shifted_right_one),
    ("noise outside the copies is left in place", background_noise_kept),
    ("copy region is one cell too large, so adjacent noise stays", copy_region_grown_by_one),
    ("pattern is drawn upside down in every copy", pattern_flipped_vertically),
]


def _valid(g):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    return all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/0607ce86.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {fn.__name__}: {desc}")
