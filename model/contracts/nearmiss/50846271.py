import json
from pathlib import Path

FILL = 8
MARK = 2


def _copy(g):
    return [r[:] for r in g]


def _diff(inp, out):
    return {(r, c) for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] != out[r][c]}


def _nbrs(r, c, h, w):
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if 0 <= r + dr < h and 0 <= c + dc < w:
            yield r + dr, c + dc


def _components(inp, cells):
    """Groups of changed cells; two cells join if a path of changed cells and mark cells joins them."""
    h, w = len(inp), len(inp[0])
    cells = set(cells)
    seen, comps = set(), []
    for s in sorted(cells):
        if s in seen:
            continue
        comp, stack = set(), [s]
        seen.add(s)
        while stack:
            r, c = stack.pop()
            comp.add((r, c))
            for n in _nbrs(r, c, h, w):
                if n in cells and n not in seen:
                    seen.add(n)
                    stack.append(n)
                elif inp[n[0]][n[1]] == MARK and n not in seen:
                    # step through one mark cell to the next changed cell in line
                    dr, dc = n[0] - r, n[1] - c
                    m = (n[0] + dr, n[1] + dc)
                    if m in cells and m not in seen:
                        seen.add(m)
                        stack.append(m)
        comps.append(comp)
    return comps


def identity(inp, out):
    return _copy(inp)


def wrong_color(inp, out):
    g = _copy(out)
    for r, c in _diff(inp, out):
        g[r][c] = 3
    return g


def clear_instead(inp, out):
    g = _copy(out)
    for r, c in _diff(inp, out):
        g[r][c] = 0
    return g


def marks_overwritten(inp, out):
    g = _copy(out)
    h, w = len(inp), len(inp[0])
    for r, c in _diff(inp, out):
        for n in _nbrs(r, c, h, w):
            if inp[n[0]][n[1]] == MARK:
                g[n[0]][n[1]] = FILL
    return g


def one_plus_missed(inp, out):
    comps = _components(inp, _diff(inp, out))
    if not comps:
        return None
    comp = sorted(comps, key=lambda s: (min(s), len(s)))[0]
    g = _copy(out)
    for r, c in comp:
        g[r][c] = inp[r][c]
    return g


def largest_plus_missed(inp, out):
    comps = _components(inp, _diff(inp, out))
    if not comps:
        return None
    comp = max(comps, key=lambda s: (len(s), min(s)))
    g = _copy(out)
    for r, c in comp:
        g[r][c] = inp[r][c]
    return g


def arms_one_short(inp, out):
    h, w = len(inp), len(inp[0])
    g = _copy(out)
    for r, c in _diff(inp, out):
        if any(inp[n[0]][n[1]] == MARK for n in _nbrs(r, c, h, w)):
            g[r][c] = inp[r][c]
    return g


def arms_one_long(inp, out):
    h, w = len(inp), len(inp[0])
    d = _diff(inp, out)
    g = _copy(out)
    for r, c in d:
        for n in _nbrs(r, c, h, w):
            if n not in d and inp[n[0]][n[1]] not in (MARK, 0):
                g[n[0]][n[1]] = FILL
    return g


def fill_eight_neighbourhood(inp, out):
    h, w = len(inp), len(inp[0])
    g = _copy(out)
    for r, c in _diff(inp, out):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                y, x = r + dr, c + dc
                if 0 <= y < h and 0 <= x < w and inp[y][x] == 5:
                    g[y][x] = FILL
    return g


def mirrored_fill(inp, out):
    w = len(inp[0])
    g = _copy(inp)
    for r, c in _diff(inp, out):
        if g[r][w - 1 - c] != MARK:
            g[r][w - 1 - c] = FILL
    return g


def fill_row_and_column_lines(inp, out):
    """Fill every non-mark, non-background cell on the full row and column of each filled cell."""
    h, w = len(inp), len(inp[0])
    d = _diff(inp, out)
    g = _copy(out)
    for r, c in d:
        for k in range(w):
            if inp[r][k] not in (MARK, 0):
                g[r][k] = FILL
        for k in range(h):
            if inp[k][c] not in (MARK, 0):
                g[k][c] = FILL
    return g


def horizontal_arms_only(inp, out):
    h, w = len(inp), len(inp[0])
    d = _diff(inp, out)
    g = _copy(out)
    for r, c in d:
        horiz = any(0 <= c + k < w and ((r, c + k) in d or inp[r][c + k] == MARK) for k in (-1, 1))
        if not horiz:
            g[r][c] = inp[r][c]
    return g


ALTERNATIVES = [
    ("Output equals the input; no plus is completed", identity),
    ("Filled cells get color 3 instead of 8", wrong_color),
    ("Filled cells are cleared to 0 instead of colored 8", clear_instead),
    ("The mark cells next to filled cells are also recolored to 8", marks_overwritten),
    ("The topmost plus is not completed", one_plus_missed),
    ("The largest plus is not completed", largest_plus_missed),
    ("Each arm is one cell short: the cells beside the marks stay unfilled", arms_one_short),
    ("Each arm is one cell too long: the neighbouring non-background cells are filled too", arms_one_long),
    ("Every 5 cell in the 3x3 neighbourhood of a filled cell is filled too", fill_eight_neighbourhood),
    ("The fill is placed at the left-right mirrored columns", mirrored_fill),
    ("Every non-mark, non-background cell on the full rows and columns of the fill is filled", fill_row_and_column_lines),
    ("Only the horizontal arms of each plus are filled", horizontal_arms_only),
]


def _valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/50846271.json").read_text())
    train = task["train"]
    print("pairs", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
