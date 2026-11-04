from pathlib import Path
import json
from collections import Counter


def _dims(g):
    return len(g), len(g[0])


def _blank(h, w):
    return [[0] * w for _ in range(h)]


def _col_pack(inp, down=True, skip_cols=(), reverse=False):
    h, w = _dims(inp)
    res = _blank(h, w)
    for c in range(w):
        cells = [inp[r][c] for r in range(h) if inp[r][c]]
        if c in skip_cols:
            for r in range(h):
                res[r][c] = inp[r][c]
            continue
        if reverse:
            cells = cells[::-1]
        if down:
            for i, v in enumerate(reversed(cells)):
                res[h - 1 - i][c] = v
        else:
            for i, v in enumerate(cells):
                res[i][c] = v
    return res


def _row_pack(inp, right=True):
    h, w = _dims(inp)
    res = _blank(h, w)
    for r in range(h):
        cells = [v for v in inp[r] if v]
        if right:
            for i, v in enumerate(reversed(cells)):
                res[r][w - 1 - i] = v
        else:
            for i, v in enumerate(cells):
                res[r][i] = v
    return res


def gravity_up(inp, out):
    return _col_pack(inp, down=False)


def gravity_left(inp, out):
    return _row_pack(inp, right=False)


def gravity_right(inp, out):
    return _row_pack(inp, right=True)


def no_stacking(inp, out):
    # each ink cell drops to the bottom row; later cells overwrite earlier ones
    h, w = _dims(inp)
    res = _blank(h, w)
    for c in range(w):
        for r in range(h):
            if inp[r][c]:
                res[h - 1][c] = inp[r][c]
    return res


def fall_one_step(inp, out):
    # each ink cell moves down one row if the cell below is empty (bottom-up pass)
    h, w = _dims(inp)
    res = [row[:] for row in inp]
    for r in range(h - 2, -1, -1):
        for c in range(w):
            if res[r][c] and not res[r + 1][c]:
                res[r + 1][c] = res[r][c]
                res[r][c] = 0
    return res


def only_lone_cells_fall(inp, out):
    # columns holding several ink cells stay as they are; lone cells fall
    h, w = _dims(inp)
    skip = tuple(c for c in range(w) if sum(1 for r in range(h) if inp[r][c]) > 1)
    return _col_pack(inp, down=True, skip_cols=skip)


def leave_bottom_row_empty(inp, out):
    # packs against row h-2, as if the floor were one row too high
    h, w = _dims(inp)
    res = _blank(h, w)
    for c in range(w):
        cells = [inp[r][c] for r in range(h) if inp[r][c]]
        cells = cells[-(h - 1):] if cells else cells
        for i, v in enumerate(reversed(cells)):
            res[h - 2 - i][c] = v
    return res


def rigid_shift(inp, out):
    # all ink moves down together by the distance the lowest ink cell needs
    h, w = _dims(inp)
    low = max((r for r in range(h) for c in range(w) if inp[r][c]), default=0)
    d = h - 1 - low
    res = _blank(h, w)
    for r in range(h):
        for c in range(w):
            if inp[r][c]:
                res[r + d][c] = inp[r][c]
    return res


def skip_first_column(inp, out):
    return _col_pack(inp, down=True, skip_cols=(0,))


def skip_last_column(inp, out):
    h, w = _dims(inp)
    return _col_pack(inp, down=True, skip_cols=(w - 1,))


def fixed_most_common_color(inp, out):
    # the most frequent ink color is treated as fixed; only other colors fall
    h, w = _dims(inp)
    cnt = Counter(v for row in inp for v in row if v)
    if not cnt:
        return None
    top = cnt.most_common(1)[0][0]
    res = _blank(h, w)
    for r in range(h):
        for c in range(w):
            if inp[r][c] == top:
                res[r][c] = top
    for c in range(w):
        movers = [inp[r][c] for r in range(h) if inp[r][c] and inp[r][c] != top]
        free = [r for r in range(h - 1, -1, -1) if res[r][c] == 0]
        for r, v in zip(free, reversed(movers)):
            res[r][c] = v
    return res


def transpose_output(inp, out):
    # gravity applied correctly but the grid is read with rows and columns swapped
    h, w = _dims(out)
    return [[out[r][c] for r in range(h)] for c in range(w)]


ALTERNATIVES = [
    ("gravity points up instead of down", gravity_up),
    ("gravity points left, packing each row", gravity_left),
    ("gravity points right, packing each row", gravity_right),
    ("ink cells do not stack: each drops to the bottom row and overwrites", no_stacking),
    ("each ink cell falls only one row", fall_one_step),
    ("columns with several ink cells stay unchanged; only lone cells fall", only_lone_cells_fall),
    ("floor is one row too high: bottom row left empty", leave_bottom_row_empty),
    ("all ink shifts down rigidly until the lowest cell reaches the bottom", rigid_shift),
    ("first column is left unchanged", skip_first_column),
    ("last column is left unchanged", skip_last_column),
    ("most common ink color stays fixed and others fall around it", fixed_most_common_color),
    ("correct output but transposed", transpose_output),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/1e0a9b12.json')))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
