import json
from pathlib import Path


def _map(g, m):
    return [[m.get(v, v) for v in row] for row in g]


def only_5_to_8(inp, out):
    return _map(inp, {5: 8})


def only_8_to_5(inp, out):
    return _map(inp, {8: 5})


def left_half_only(inp, out):
    w = len(inp[0])
    return [[({5: 8, 8: 5}.get(v, v) if c < w // 2 else v)
             for c, v in enumerate(row)] for row in inp]


def swap_5_4(inp, out):
    return _map(inp, {5: 4, 4: 5})


def all_to_5(inp, out):
    return _map(inp, {8: 5})


def eight_to_zero(inp, out):
    return _map(inp, {5: 8, 8: 0})


def largest_component_only(inp, out):
    h, w = len(inp), len(inp[0])
    seen = set()
    best = []
    for r in range(h):
        for c in range(w):
            if (r, c) in seen or inp[r][c] not in (5, 8):
                continue
            col = inp[r][c]
            comp = []
            stack = [(r, c)]
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if (0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen
                            and inp[ny][nx] == col):
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            if len(comp) > len(best):
                best = comp
    g = [row[:] for row in inp]
    for y, x in best:
        g[y][x] = 13 - inp[y][x]
    return g


def rows_with_both(inp, out):
    return [_map([row], {5: 8, 8: 5})[0] if (5 in row and 8 in row) else row[:]
            for row in inp]


def transposed_swap(inp, out):
    s = _map(inp, {5: 8, 8: 5})
    return [list(r) for r in zip(*s)]


def erase_5_and_8(inp, out):
    return _map(inp, {5: 0, 8: 0})


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("only 5 becomes 8; 8 is left as is", only_5_to_8),
    ("only 8 becomes 5; 5 is left as is", only_8_to_5),
    ("5 and 8 swap only in the left half of the grid", left_half_only),
    ("the swapped pair is 5 and 4 instead of 5 and 8", swap_5_4),
    ("8 becomes 5 and 5 stays 5 (merge instead of swap)", all_to_5),
    ("5 becomes 8 and 8 is erased to 0", eight_to_zero),
    ("only the largest same-color blob of 5 or 8 is swapped", largest_component_only),
    ("5 and 8 swap only in rows that hold both colors", rows_with_both),
    ("the swap is right but the grid is transposed", transposed_swap),
    ("5 and 8 are both erased to 0", erase_5_and_8),
    ("output equals the input", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/d511f180.json"))
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
