import json
from collections import Counter
from pathlib import Path

N = 4  # noise color


def noise_cells(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == N]


def from_source(inp, src):
    """Replace each noise cell by inp at src(r, c); keep the noise color if that cell is noise too."""
    n = len(inp)
    out = [row[:] for row in inp]
    for r, c in noise_cells(inp):
        rr, cc = src(r, c, n)
        out[r][c] = inp[rr][cc]
    return out


def fill_vertical_only(inp, out):
    return from_source(inp, lambda r, c, n: (n - 1 - r, c))


def fill_transpose_only(inp, out):
    return from_source(inp, lambda r, c, n: (c, r))


def fill_antitranspose_only(inp, out):
    return from_source(inp, lambda r, c, n: (n - 1 - c, n - 1 - r))


def fill_global_mode(inp, out):
    cnt = Counter(v for row in inp for v in row if v != N)
    col = cnt.most_common(1)[0][0]
    return [[col if v == N else v for v in row] for row in inp]


def fill_with_zero(inp, out):
    return [[0 if v == N else v for v in row] for row in inp]


def fill_left_neighbor(inp, out):
    res = [row[:] for row in inp]
    for r, row in enumerate(res):
        for c, v in enumerate(row):
            if v == N:
                k = c
                while k > 0 and inp[r][k] == N:
                    k -= 1
                row[c] = inp[r][k] if inp[r][k] != N else row[c]
    return res


def fill_top_half_only(inp, out):
    n = len(inp)
    return [[out[r][c] if (inp[r][c] == N and r < n // 2) else inp[r][c]
             for c in range(len(inp[0]))] for r in range(n)]


def fill_first_patch_only(inp, out):
    cells = set(noise_cells(inp))
    if not cells:
        return None
    start = min(cells)
    seen, stack = {start}, [start]
    while stack:
        r, c = stack.pop()
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p = (r + d[0], c + d[1])
            if p in cells and p not in seen:
                seen.add(p)
                stack.append(p)
    return [[out[r][c] if (r, c) in seen else inp[r][c]
             for c in range(len(inp[0]))] for r in range(len(inp))]


def shifted_fill(inp, out):
    n, m = len(inp), len(inp[0])
    res = [row[:] for row in inp]
    for r, c in noise_cells(inp):
        res[r][c] = out[r][min(c + 1, m - 1)]
    return res


def crop_noise_box(inp, out):
    cells = noise_cells(inp)
    if not cells:
        return None
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def fill_row_mode(inp, out):
    res = [row[:] for row in inp]
    for r, row in enumerate(inp):
        cnt = Counter(v for v in row if v != N)
        if not cnt:
            continue
        col = cnt.most_common(1)[0][0]
        for c, v in enumerate(row):
            if v == N:
                res[r][c] = col
    return res


ALTERNATIVES = [
    ("repair noise by vertical mirror only", fill_vertical_only),
    ("repair noise by transpose only", fill_transpose_only),
    ("repair noise by anti-diagonal transpose only", fill_antitranspose_only),
    ("fill every noise cell with the grid's most common clean color", fill_global_mode),
    ("fill noise cells with color 0", fill_with_zero),
    ("fill each noise cell with the nearest clean color to its left", fill_left_neighbor),
    ("repair only noise in the top half of the grid", fill_top_half_only),
    ("repair only the first noise patch", fill_first_patch_only),
    ("repair noise with the true value taken one column to the right", shifted_fill),
    ("output only the repaired patch cropped to the noise bounding box", crop_noise_box),
    ("fill noise cells with the most common clean color of their row", fill_row_mode),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/b8825c91.json').read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn([r[:] for r in p["input"]], [r[:] for r in p["output"]])
            if g is not None and valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
