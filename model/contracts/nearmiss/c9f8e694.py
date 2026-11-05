import json
from collections import Counter
from pathlib import Path

TARGET = 5


def _copy(g):
    return [r[:] for r in g]


def _blobs(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    blobs = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == TARGET and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == TARGET and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                blobs.append(cells)
    return blobs


def _row_shift(inp, k):
    g = _copy(inp)
    h = len(inp)
    for r in range(h):
        for c in range(len(inp[0])):
            if inp[r][c] == TARGET:
                rr = r + k
                g[r][c] = inp[rr][0] if 0 <= rr < h else 0
    return g


def above(inp, out):
    return _row_shift(inp, -1)


def below(inp, out):
    return _row_shift(inp, 1)


def right_edge(inp, out):
    g = _copy(inp)
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == TARGET:
                g[r][c] = row[-1]
    return g


def left_half_only(inp, out):
    g = _copy(out)
    w = len(inp[0])
    for r, row in enumerate(inp):
        for c in range(w // 2, w):
            if row[c] == TARGET:
                g[r][c] = TARGET
    return g


def single_majority_color(inp, out):
    keys = Counter(r[0] for r in inp if r[0] != 0)
    col = keys.most_common(1)[0][0]
    return [[col if v == TARGET else v for v in row] for row in inp]


def blob_top_key(inp, out):
    g = _copy(inp)
    for cells in _blobs(inp):
        top = min(r for r, _ in cells)
        col = inp[top][0]
        for r, c in cells:
            g[r][c] = col
    return g


def blob_majority_key(inp, out):
    g = _copy(inp)
    for cells in _blobs(inp):
        cnt = Counter(inp[r][0] for r, _ in cells)
        col = max(cnt, key=lambda k: (cnt[k], -k))
        for r, c in cells:
            g[r][c] = col
    return g


def key_column_cleared(inp, out):
    g = _copy(out)
    for row in g:
        row[0] = 0
    return g


def swap_key_colors(inp, out):
    colors = sorted({r[0] for r in inp if r[0] != 0})
    if len(colors) != 2:
        return None
    m = {colors[0]: colors[1], colors[1]: colors[0]}
    return [[m.get(v, v) for v in row] for row in out]


def largest_blob_only(inp, out):
    blobs = _blobs(inp)
    if len(blobs) < 2:
        return None
    big = max(blobs, key=len)
    g = _copy(inp)
    for r, c in big:
        g[r][c] = out[r][c]
    return g


def erase_targets(inp, out):
    return [[0 if v == TARGET else v for v in row] for row in inp]


def key_from_blob_row_span_first_col(inp, out):
    # key read at the blob's leftmost column neighbour instead of column 0 row key:
    # uses the key of the blob's bottom row for the whole blob
    g = _copy(inp)
    for cells in _blobs(inp):
        bot = max(r for r, _ in cells)
        col = inp[bot][0]
        for r, c in cells:
            g[r][c] = col
    return g


ALTERNATIVES = [
    ("Replacement color is read from the row above (off by one row)", above),
    ("Replacement color is read from the row below (off by one row)", below),
    ("Replacement color is read from the right edge of the row, not the left", right_edge),
    ("Only the blobs in the left half are recolored", left_half_only),
    ("All target cells get one color, the most frequent key color", single_majority_color),
    ("Each blob gets the key color of its top row", blob_top_key),
    ("Each blob gets the most common key color among its rows", blob_majority_key),
    ("Each blob gets the key color of its bottom row", key_from_blob_row_span_first_col),
    ("Key column is cleared after recoloring", key_column_cleared),
    ("The two key colors are swapped in the recolored cells", swap_key_colors),
    ("Only the largest blob is recolored", largest_blob_only),
    ("Target cells are erased to background", erase_targets),
]


def _valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/c9f8e694.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(_copy(p["input"]), _copy(p["output"]))
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
