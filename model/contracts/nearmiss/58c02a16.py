"""Near-miss readings for 58c02a16.

Rule: the pattern block sits in a corner of the input, closed by a separator
line of one colour. The output tiles a grid-sized layout whose period is the
block squared: every ink cell of the block is replaced by a copy of the block
in that cell's colour, and every background cell of the block by a copy of the
block in the separator colour.
"""
import json
from collections import Counter
from pathlib import Path


def _parts(inp):
    bg = Counter(v for row in inp for v in row).most_common(1)[0][0]
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != bg]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    box = [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]
    sep = box[-1][-1]
    block = [row[:-1] for row in box[:-1]]
    return bg, box, sep, block


def _kron(block, bg, sep, swap=False):
    h, w = len(block), len(block[0])
    rows = []
    for R in range(h):
        for r in range(h):
            row = []
            for C in range(w):
                for c in range(w):
                    outer, inner = block[R][C], block[r][c]
                    if swap:
                        v = (inner if inner != bg else sep) if outer != bg else bg
                    else:
                        v = (outer if outer != bg else sep) if inner != bg else bg
                    row.append(v)
            rows.append(row)
    return rows


def _tile(k, n, m, dr=0, dc=0):
    H, W = len(k), len(k[0])
    return [[k[(r + dr) % H][(c + dc) % W] for c in range(m)] for r in range(n)]


def _dims(out):
    return len(out), len(out[0])


def sep_erased(inp, out):
    bg, box, sep, block = _parts(inp)
    return [[bg if v == sep else v for v in row] for row in out]


def roles_swapped(inp, out):
    bg, box, sep, block = _parts(inp)
    n, m = _dims(out)
    return _tile(_kron(block, bg, sep, swap=True), n, m)


def shifted_tiling(inp, out):
    bg, box, sep, block = _parts(inp)
    n, m = _dims(out)
    return _tile(_kron(block, bg, sep), n, m, 0, 1)


def single_copy(inp, out):
    bg, box, sep, block = _parts(inp)
    n, m = _dims(out)
    k = _kron(block, bg, sep)
    return [[k[r][c] if r < len(k) and c < len(k[0]) else bg for c in range(m)]
            for r in range(n)]


def plain_box_tiling(inp, out):
    bg, box, sep, block = _parts(inp)
    n, m = _dims(out)
    return _tile(box, n, m)


def box_as_block(inp, out):
    bg, box, sep, block = _parts(inp)
    n, m = _dims(out)
    return _tile(_kron(box, bg, sep), n, m)


def flipped_block(inp, out):
    bg, box, sep, block = _parts(inp)
    n, m = _dims(out)
    fb = [row[::-1] for row in block]
    return _tile(_kron(fb, bg, sep), n, m)


def ink_sep_swapped(inp, out):
    bg, box, sep, block = _parts(inp)
    ink = [v for row in block for v in row if v != bg][0]
    return [[sep if v == ink else ink if v == sep else v for v in row] for row in out]


def flipped_vertically(inp, out):
    return [row[:] for row in out[::-1]]


def gapped_period(inp, out):
    bg, box, sep, block = _parts(inp)
    n, m = _dims(out)
    k = [[bg] + row for row in _kron(block, bg, sep)]
    k.insert(0, [bg] * len(k[0]))
    return _tile(k, n, m)


ALTERNATIVES = [
    ("separator-colour blocks left as background", sep_erased),
    ("outer and inner roles of the block swapped in the nested layout", roles_swapped),
    ("tiling anchored one column off the corner", shifted_tiling),
    ("only one copy of the nested layout, the rest background", single_copy),
    ("the corner box with its separators tiled as is, no nesting", plain_box_tiling),
    ("separator line counted as part of the block", box_as_block),
    ("block mirrored left to right before nesting", flipped_block),
    ("ink colour and separator colour exchanged", ink_sep_swapped),
    ("true layout flipped top to bottom", flipped_vertically),
    ("period one cell too long, a background gap between copies", gapped_period),
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
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/58c02a16.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                ok += 1
        print(ok, desc)
