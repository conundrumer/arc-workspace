import json
from pathlib import Path


def blocks(out):
    """Block matrix of the output: one value per 2x2 block, stride 3."""
    m = (len(out) + 1) // 3
    return [[out[3 * i][3 * j] for j in range(m)] for i in range(m)]


def render(B, bs=2, gap=1):
    m = len(B)
    size = m * bs + (m - 1) * gap
    g = [[0] * size for _ in range(size)]
    for i in range(m):
        for j in range(m):
            for a in range(bs):
                for b in range(bs):
                    g[i * (bs + gap) + a][j * (bs + gap) + b] = B[i][j]
    return g


def legend(inp):
    """Legend colors from the last column, top to bottom."""
    return [r[-1] for r in inp if r[-1] != 0]


def shapes(inp):
    cells = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row[:-1]):
            if v:
                cells.setdefault(v, []).append((r, c))
    return cells


def norm(cs):
    r0 = min(r for r, _ in cs)
    c0 = min(c for _, c in cs)
    return frozenset((r - r0, c - c0) for r, c in cs)


def d4(cs):
    res = []
    cur = list(cs)
    for _ in range(4):
        cur = [(c, -r) for r, c in cur]
        res.append(("rot", norm(cur)))
        res.append(("refl", norm([(r, -c) for r, c in cur])))
    return res


def similarity(inp, mode):
    sh = shapes(inp)
    cols = legend(inp)
    n = len(cols)
    B = [[0] * (n + 1) for _ in range(n + 1)]
    for i, a in enumerate(cols):
        B[0][i + 1] = a
        B[i + 1][0] = a
        for j, b in enumerate(cols):
            if i == j:
                continue
            A, Bb = sh[a], sh[b]
            if mode == "translation":
                same = norm(A) == norm(Bb)
            elif mode == "rotation":
                same = any(k == "rot" and s == norm(Bb) for k, s in d4(A)) or norm(A) == norm(Bb)
            elif mode == "count":
                same = len(A) == len(Bb)
            elif mode == "bbox":
                ha = max(r for r, _ in A) - min(r for r, _ in A)
                wa = max(c for _, c in A) - min(c for _, c in A)
                hb = max(r for r, _ in Bb) - min(r for r, _ in Bb)
                wb = max(c for _, c in Bb) - min(c for _, c in Bb)
                same = (ha, wa) == (hb, wb)
            B[i + 1][j + 1] = 2 if same else 5
    return B


def swap25(inp, out):
    return [[5 if v == 2 else 2 if v == 5 else v for v in r] for r in out]


def diag2(inp, out):
    B = blocks(out)
    for i in range(1, len(B)):
        B[i][i] = 2
    return render(B)


def all5(inp, out):
    return [[5 if v == 2 else v for v in r] for r in out]


def reverse_legend(inp, out):
    B = blocks(out)
    m = len(B)
    perm = [0] + list(range(m - 1, 0, -1))
    return render([[B[perm[i]][perm[j]] for j in range(m)] for i in range(m)])


def reverse_row_header_only(inp, out):
    B = blocks(out)
    m = len(B)
    hdr = B[0][1:][::-1]
    for j in range(1, m):
        B[0][j] = hdr[j - 1]
    return render(B)


def sort_by_color(inp, out):
    B = blocks(out)
    m = len(B)
    order = sorted(range(1, m), key=lambda i: B[i][0])
    perm = [0] + order
    return render([[B[perm[i]][perm[j]] for j in range(m)] for i in range(m)])


def no_gap(inp, out):
    return render(blocks(out), bs=2, gap=0)


def one_cell_blocks(inp, out):
    return render(blocks(out), bs=1, gap=1)


def flipped(inp, out):
    return [r[::-1] for r in out[::-1]]


def crop_header(inp, out):
    return [r[3:] for r in out[3:]]


def translation_only(inp, out):
    return render(similarity(inp, "translation"))


def rotation_only(inp, out):
    return render(similarity(inp, "rotation"))


def same_cell_count(inp, out):
    return render(similarity(inp, "count"))


def same_bbox(inp, out):
    return render(similarity(inp, "bbox"))


def legend_not_header(inp, out):
    """Header skipped: shapes' own color listed by shape position (left to right) instead of legend order."""
    sh = shapes(inp)
    cols = sorted(legend(inp), key=lambda c: min(cc for _, cc in sh[c]))
    B = blocks(out)
    m = len(B)
    idx = {B[i][0]: i for i in range(1, m)}
    perm = [0] + [idx[c] for c in cols]
    return render([[B[perm[i]][perm[j]] for j in range(m)] for i in range(m)])


ALTERNATIVES = [
    ("same and different fill colors swapped (2 and 5 exchanged)", swap25),
    ("diagonal blocks filled with 2 as a shape matching itself", diag2),
    ("every off-diagonal block is 5 (no shape matching)", all5),
    ("legend read bottom to top for header and rows", reverse_legend),
    ("only the top header row reversed, left column kept", reverse_row_header_only),
    ("header colors sorted by color value instead of legend order", sort_by_color),
    ("blocks packed with no gap lines", no_gap),
    ("blocks are single cells with gaps", one_cell_blocks),
    ("output rotated 180 degrees so header is at bottom right", flipped),
    ("shapes match only if identical without rotation or reflection", translation_only),
    ("shapes match if same cell count", same_cell_count),
]


def valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/6165ea8f.json").read_text())
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        cnt = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                cnt += 1
        print(cnt, desc)
