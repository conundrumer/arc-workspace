import json
from collections import Counter
from pathlib import Path


def locate(inp, out):
    """Top-left (r, c) where out occurs in inp, or None."""
    h, w = len(out), len(out[0])
    for r in range(len(inp) - h + 1):
        for c in range(len(inp[0]) - w + 1):
            if all(inp[r + i][c:c + w] == out[i] for i in range(h)):
                return r, c
    return None


def crop(inp, r0, r1, c0, c1):
    """Rows r0..r1-1, cols c0..c1-1, or None if outside the grid or empty."""
    if r0 < 0 or c0 < 0 or r1 > len(inp) or c1 > len(inp[0]) or r1 <= r0 or c1 <= c0:
        return None
    return [row[c0:c1] for row in inp[r0:r1]]


def frames(inp):
    """Interior boxes (r0, r1, c0, c1) of rectangles whose border is one nonzero color."""
    H, W = len(inp), len(inp[0])
    found = []
    for r1 in range(H):
        for r2 in range(r1 + 2, H):
            for c1 in range(W):
                col = inp[r1][c1]
                if col == 0:
                    continue
                for c2 in range(c1 + 2, W):
                    if inp[r1][c2] != col or inp[r2][c1] != col or inp[r2][c2] != col:
                        continue
                    if all(inp[r1][c] == col and inp[r2][c] == col for c in range(c1, c2 + 1)) and \
                       all(inp[r][c1] == col and inp[r][c2] == col for r in range(r1, r2 + 1)):
                        found.append(((r2 - r1 - 1) * (c2 - c1 - 1), (r1 + 1, r2, c1 + 1, c2)))
    return found


def other_frame(inp, out, pick):
    loc = locate(inp, out)
    if loc is None:
        return None
    true_box = (loc[0], loc[0] + len(out), loc[1], loc[1] + len(out[0]))
    cands = sorted({f for f in frames(inp) if f[1] != true_box})
    if not cands:
        return None
    return pick(cands)


def with_border(inp, out):
    loc = locate(inp, out)
    if loc is None:
        return None
    r, c = loc
    return crop(inp, r - 1, r + len(out) + 1, c - 1, c + len(out[0]) + 1)


def shift_down_right(inp, out):
    loc = locate(inp, out)
    if loc is None:
        return None
    r, c = loc
    return crop(inp, r + 1, r + 1 + len(out), c + 1, c + 1 + len(out[0]))


def shift_up_left(inp, out):
    loc = locate(inp, out)
    if loc is None:
        return None
    r, c = loc
    return crop(inp, r - 1, r - 1 + len(out), c - 1, c - 1 + len(out[0]))


def shrunk(inp, out):
    if len(out) < 3 or len(out[0]) < 3:
        return None
    return [row[1:-1] for row in out[1:-1]]


def extra_bottom_right(inp, out):
    loc = locate(inp, out)
    if loc is None:
        return None
    r, c = loc
    return crop(inp, r, r + len(out) + 1, c, c + len(out[0]) + 1)


def full_width_rows(inp, out):
    loc = locate(inp, out)
    if loc is None:
        return None
    r, _ = loc
    return crop(inp, r, r + len(out), 0, len(inp[0]))


def largest_other(inp, out):
    def pick(cands):
        a, (r0, r1, c0, c1) = max(cands)
        return crop(inp, r0, r1, c0, c1)
    return other_frame(inp, out, pick)


def smallest_other(inp, out):
    def pick(cands):
        a, (r0, r1, c0, c1) = min(cands)
        return crop(inp, r0, r1, c0, c1)
    return other_frame(inp, out, pick)


def ink_erased(inp, out):
    return [[0] * len(out[0]) for _ in out]


def frame_color_filled(inp, out):
    loc = locate(inp, out)
    if loc is None:
        return None
    r, c = loc
    border = inp[r - 1][c - 1] if r > 0 and c > 0 else None
    if border is None:
        return None
    return [[border if v == 0 else v for v in row] for row in out]


def only_commonest_ink(inp, out):
    cnt = Counter(v for row in out for v in row if v != 0)
    if not cnt:
        return None
    keep = cnt.most_common(1)[0][0]
    return [[v if v == keep else 0 for v in row] for row in out]


def mirrored(inp, out):
    return [row[::-1] for row in out]


def transposed(inp, out):
    return [list(col) for col in zip(*out)]


ALTERNATIVES = [
    ("Crop includes the frame border, one cell wider on every side", with_border),
    ("Crop is the right size but offset one cell down and right", shift_down_right),
    ("Crop is the right size but offset one cell up and left", shift_up_left),
    ("Crop is one cell too small on every side (interior of the interior)", shrunk),
    ("Crop runs one extra row and column past the interior at bottom and right", extra_bottom_right),
    ("Right rows but the full grid width instead of the frame's columns", full_width_rows),
    ("Picks the largest frame other than the correct one", largest_other),
    ("Picks the smallest frame instead of the largest", smallest_other),
    ("Window kept at the right size but all ink erased to background", ink_erased),
    ("Window with background cells recolored to the frame color", frame_color_filled),
    ("Window keeps only its most common ink color", only_commonest_ink),
    ("Window mirrored left to right", mirrored),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/1a6449f1.json').read_text())
    pairs = task['train']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g) and g != p['output']:
                n += 1
        print(f'{n}/{len(pairs)}  {desc}')
