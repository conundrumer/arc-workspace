import copy


def _cups(inp):
    """Same-colour 4-connected components of non-zero cells: (colour, r0, r1, c0, c1)."""
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 or (r, c) in seen:
                continue
            col = inp[r][c]
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] == col:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            res.append((col, min(ys), max(ys), min(xs), max(xs)))
    res.sort(key=lambda t: (t[3], t[1]))
    return res


def _blank(inp):
    return [row[:] for row in inp]


def _result(g, inp, out):
    return None if g == out else g


def top_row(inp, out):
    g = _blank(inp)
    for col, r0, r1, c0, c1 in _cups(inp):
        g[0][(c0 + c1) // 2] = 4
    return _result(g, inp, out)


def gap_cell(inp, out):
    g = _blank(inp)
    for col, r0, r1, c0, c1 in _cups(inp):
        g[r1][(c0 + c1) // 2] = 4
    return _result(g, inp, out)


def cup_color(inp, out):
    g = copy.deepcopy(out)
    for col, r0, r1, c0, c1 in _cups(inp):
        g[-1][(c0 + c1) // 2] = col
    return _result(g, inp, out)


def first_cup_only(inp, out):
    g = _blank(inp)
    col, r0, r1, c0, c1 = _cups(inp)[0]
    g[-1][(c0 + c1) // 2] = 4
    return _result(g, inp, out)


def left_edge_col(inp, out):
    g = _blank(inp)
    for col, r0, r1, c0, c1 in _cups(inp):
        g[-1][c0] = 4
    return _result(g, inp, out)


def right_edge_col(inp, out):
    g = _blank(inp)
    for col, r0, r1, c0, c1 in _cups(inp):
        g[-1][c1] = 4
    return _result(g, inp, out)


def full_width_mark(inp, out):
    g = _blank(inp)
    for col, r0, r1, c0, c1 in _cups(inp):
        for c in range(c0, c1 + 1):
            g[-1][c] = 4
    return _result(g, inp, out)


def vertical_line(inp, out):
    g = _blank(inp)
    for col, r0, r1, c0, c1 in _cups(inp):
        x = (c0 + c1) // 2
        for r in range(r1 + 1, len(g)):
            g[r][x] = 4
    return _result(g, inp, out)


def union_center(inp, out):
    g = _blank(inp)
    cups = _cups(inp)
    c0 = min(c[3] for c in cups)
    c1 = max(c[4] for c in cups)
    g[-1][(c0 + c1) // 2] = 4
    return _result(g, inp, out)


def second_last_row(inp, out):
    g = _blank(inp)
    for col, r0, r1, c0, c1 in _cups(inp):
        g[-2][(c0 + c1) // 2] = 4
    return _result(g, inp, out)


def just_below_cup(inp, out):
    g = _blank(inp)
    for col, r0, r1, c0, c1 in _cups(inp):
        if r1 + 1 < len(g):
            g[r1 + 1][(c0 + c1) // 2] = 4
    return _result(g, inp, out)


def whole_bottom_row(inp, out):
    g = _blank(inp)
    g[-1] = [4 if v == 0 else v for v in g[-1]]
    return _result(g, inp, out)


ALTERNATIVES = [
    ("mark goes on the top edge row instead of the bottom edge", top_row),
    ("mark goes in the empty cell inside each cup", gap_cell),
    ("mark takes the cup's own color instead of the new color", cup_color),
    ("only the first (leftmost) cup gets a mark", first_cup_only),
    ("mark sits under the cup's left edge column, not its center", left_edge_col),
    ("mark sits under the cup's right edge column, not its center", right_edge_col),
    ("mark spans the cup's full width on the bottom row", full_width_mark),
    ("mark is a vertical line from the cup down to the bottom edge", vertical_line),
    ("one mark at the center of all cups together", union_center),
    ("mark is one row above the bottom edge", second_last_row),
    ("mark sits right under each cup instead of at the grid edge", just_below_cup),
    ("whole bottom row is filled with the mark color", whole_bottom_row),
]


if __name__ == "__main__":
    import json
    from pathlib import Path

    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/54d82841.json').read_text())
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                  and g != p["output"])
            if ok:
                n += 1
        print(n, desc)
