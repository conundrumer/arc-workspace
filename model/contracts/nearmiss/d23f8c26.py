import json
from pathlib import Path


def _blank(inp):
    return [[0] * len(r) for r in inp]


def _keep_cols(inp, cols):
    res = _blank(inp)
    for r in range(len(inp)):
        for c in cols:
            if 0 <= c < len(inp[0]):
                res[r][c] = inp[r][c]
    return res


def middle_row(inp, out):
    res = _blank(inp)
    m = len(inp) // 2
    res[m] = list(inp[m])
    return res


def left_of_middle(inp, out):
    return _keep_cols(inp, [len(inp[0]) // 2 - 1])


def right_of_middle(inp, out):
    return _keep_cols(inp, [len(inp[0]) // 2 + 1])


def first_column(inp, out):
    return _keep_cols(inp, [0])


def cross(inp, out):
    res = _keep_cols(inp, [len(inp[0]) // 2])
    m = len(inp) // 2
    res[m] = list(inp[m])
    return res


def three_columns(inp, out):
    m = len(inp[0]) // 2
    return _keep_cols(inp, [m - 1, m, m + 1])


def cropped_column(inp, out):
    m = len(inp[0]) // 2
    return [[row[m]] for row in inp]


def flipped_column(inp, out):
    m = len(inp[0]) // 2
    res = _blank(inp)
    n = len(inp)
    for r in range(n):
        res[r][m] = inp[n - 1 - r][m]
    return res


def top_half_only(inp, out):
    m = len(inp[0]) // 2
    res = _blank(inp)
    for r in range(len(inp) // 2):
        res[r][m] = inp[r][m]
    return res


def recolor_first_color(inp, out):
    col = next((v for row in inp for v in row if v), None)
    if col is None:
        return None
    return [[col if v else 0 for v in row] for row in out]


def drop_last_cell(inp, out):
    res = [list(r) for r in out]
    for r in range(len(res) - 1, -1, -1):
        if any(res[r]):
            res[r] = [0] * len(res[r])
            return res
    return None


def whole_objects(inp, out):
    h, w = len(inp), len(inp[0])
    m = w // 2
    seen = set()
    stack = [(r, m) for r in range(h) if inp[r][m]]
    while stack:
        r, c = stack.pop()
        if (r, c) in seen:
            continue
        seen.add((r, c))
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and inp[nr][nc] and (nr, nc) not in seen:
                stack.append((nr, nc))
    res = _blank(inp)
    for r, c in seen:
        res[r][c] = inp[r][c]
    return res


ALTERNATIVES = [
    ("keeps the middle row instead of the middle column", middle_row),
    ("keeps the column left of the middle", left_of_middle),
    ("keeps the column right of the middle", right_of_middle),
    ("keeps the first column", first_column),
    ("keeps both the middle row and the middle column", cross),
    ("keeps the three middle columns", three_columns),
    ("crops the middle column out as a one-wide grid", cropped_column),
    ("keeps the middle column but reversed top to bottom", flipped_column),
    ("keeps only the top half of the middle column", top_half_only),
    ("keeps the middle column shape but paints it with the first input color", recolor_first_color),
    ("keeps the middle column but drops its lowest colored cell", drop_last_cell),
    ("keeps whole objects that touch the middle column", whole_objects),
]


def _valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/d23f8c26.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
