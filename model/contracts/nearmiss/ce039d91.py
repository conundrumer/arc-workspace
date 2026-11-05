import json
from pathlib import Path


def _dims(g):
    return len(g), len(g[0])


def _mark(inp, partner, color=1, keep_sym=True):
    """Cells of 5 whose partner cell (given by partner(r, c, h, w)) is also 5 become color."""
    h, w = _dims(inp)
    res = [row[:] for row in inp]
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 5:
                continue
            pr, pc = partner(r, c, h, w)
            ok = 0 <= pr < h and 0 <= pc < w and inp[pr][pc] == 5
            if ok == keep_sym:
                res[r][c] = color
    return res


def wrong_color(inp, out):
    return [[2 if v == 1 else v for v in row] for row in out]


def inverted(inp, out):
    return _mark(inp, lambda r, c, h, w: (r, w - 1 - c), keep_sym=False)


def horizontal_axis(inp, out):
    return _mark(inp, lambda r, c, h, w: (h - 1 - r, c))


def axis_off_by_one(inp, out):
    return _mark(inp, lambda r, c, h, w: (r, w - 2 - c))


def transpose(inp, out):
    return _mark(inp, lambda r, c, h, w: (c, r))


def rot180(inp, out):
    return _mark(inp, lambda r, c, h, w: (h - 1 - r, w - 1 - c))


def complete_symmetry(inp, out):
    h, w = _dims(inp)
    res = [row[:] for row in out]
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 5 and inp[r][w - 1 - c] == 0:
                res[r][w - 1 - c] = 1
    return res


def left_half_only(inp, out):
    h, w = _dims(inp)
    return [[5 if (out[r][c] == 1 and c >= w // 2) else out[r][c] for c in range(w)] for r in range(h)]


def largest_component_only(inp, out):
    h, w = _dims(inp)
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 5 and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                comp = []
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = y + dy, x + dx
                            if (0 <= ny < h and 0 <= nx < w and inp[ny][nx] == 5
                                    and (ny, nx) not in seen):
                                seen.add((ny, nx))
                                stack.append((ny, nx))
                comps.append(comp)
    big = set(max(comps, key=len))
    return [[out[r][c] if (r, c) in big or out[r][c] != 1 else 5 for c in range(w)] for r in range(h)]


def all_to_one(inp, out):
    return [[1 if v == 5 else v for v in row] for row in inp]


def row_has_other(inp, out):
    h, w = _dims(inp)
    res = [row[:] for row in inp]
    for r in range(h):
        if sum(1 for v in inp[r] if v == 5) >= 2:
            res[r] = [1 if v == 5 else v for v in inp[r]]
    return res


def axis_other_way_off(inp, out):
    return _mark(inp, lambda r, c, h, w: (r, w - c))


ALTERNATIVES = [
    ("symmetric cells recolored 2 instead of 1", wrong_color),
    ("asymmetric cells recolored instead of symmetric ones", inverted),
    ("mirror axis is horizontal (top-bottom) instead of vertical", horizontal_axis),
    ("mirror axis shifted by one column (x -> w-2-x)", axis_off_by_one),
    ("symmetry is transpose across the main diagonal", transpose),
    ("symmetry is 180-degree rotation", rot180),
    ("missing mirror partners are also filled with 1", complete_symmetry),
    ("only cells in the left half are recolored", left_half_only),
    ("only the largest connected shape is recolored", largest_component_only),
    ("every 5 is recolored to 1", all_to_one),
    ("5s in rows holding at least two 5s are recolored", row_has_other),
    ("mirror axis on column 5 (x -> w-x)", axis_other_way_off),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/ce039d91.json'))
    pairs = task["train"]

    def valid(g, out):
        return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
                and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
                and g != out)

    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
