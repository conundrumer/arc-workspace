import json
from collections import Counter
from pathlib import Path


def _s(out):
    return len(out) // 3


def _blocks(out):
    s = _s(out)
    return [[[row[bj * s:(bj + 1) * s] for row in out[bi * s:(bi + 1) * s]]
             for bj in range(3)] for bi in range(3)]


def _join(b):
    s = len(b[0][0])
    return [sum((b[bi][bj][r] for bj in range(3)), []) for bi in range(3) for r in range(s)]


def _fill(out):
    return Counter(c for r in out for c in r).most_common(1)[0][0]


def _map_blocks(out, f):
    b = _blocks(out)
    return _join([[f(b[i][j]) for j in range(3)] for i in range(3)])


def transposed(inp, out):
    b = _blocks(out)
    return _join([[b[j][i] for j in range(3)] for i in range(3)])


def mirror_lr(inp, out):
    b = _blocks(out)
    return _join([[b[i][2 - j] for j in range(3)] for i in range(3)])


def mirror_ud(inp, out):
    b = _blocks(out)
    return _join([[b[2 - i][j] for j in range(3)] for i in range(3)])


def rot180_arrangement(inp, out):
    b = _blocks(out)
    return _join([[b[2 - i][2 - j] for j in range(3)] for i in range(3)])


def empty_is_bg(inp, out):
    f = _fill(out)
    bg = 0
    def g(blk):
        if all(c == f for r in blk for c in r):
            return [[bg] * len(blk[0]) for _ in blk]
        return blk
    return _map_blocks(out, g)


def pieces_rot180(inp, out):
    return _map_blocks(out, lambda blk: [r[::-1] for r in blk[::-1]])


def pieces_flip_h(inp, out):
    return _map_blocks(out, lambda blk: [r[::-1] for r in blk])


def gap_between_blocks(inp, out):
    s = _s(out)
    w = 3 * s + 2
    res = []
    for bi in range(3):
        for r in range(s):
            row = []
            for bj in range(3):
                row += out[bi * s + r][bj * s:(bj + 1) * s]
                if bj < 2:
                    row.append(0)
            res.append(row)
        if bi < 2:
            res.append([0] * w)
    return res


def crop_off_by_one(inp, out):
    return [r[:-1] for r in out[:-1]]


def roll_blocks(inp, out):
    b = _blocks(out)
    return _join([[b[i][(j + 1) % 3] for j in range(3)] for i in range(3)])


def one_mark_color(inp, out):
    f = _fill(out)
    marks = Counter(c for r in out for c in r if c != f)
    if not marks:
        return None
    m = marks.most_common(1)[0][0]
    return [[c if c == f else m for c in r] for r in out]


def input_unchanged(inp, out):
    return [r[:] for r in inp]


ALTERNATIVES = [
    ("pieces placed at the transposed block (row and column swapped)", transposed),
    ("pieces placed at the mirrored block on the horizontal axis only", mirror_lr),
    ("pieces placed at the mirrored block on the vertical axis only", mirror_ud),
    ("pieces point away from their marks on both axes (arrangement rotated 180)", rot180_arrangement),
    ("blocks no piece points to are background instead of fill", empty_is_bg),
    ("each piece is copied rotated 180 degrees", pieces_rot180),
    ("each piece is copied mirrored left to right", pieces_flip_h),
    ("blocks are separated by a one-cell background gap", gap_between_blocks),
    ("output cropped one row and column short", crop_off_by_one),
    ("pieces shifted one block cyclically to the side", roll_blocks),
    ("all marks recolored to the commonest mark color", one_mark_color),
    ("input returned unchanged", input_unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/a8c38be5.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
