import json
from pathlib import Path


def _map(g, f):
    return [[f(r, c, v) for c, v in enumerate(row)] for r, row in enumerate(g)]


def recolor_7(inp, out):
    return _map(inp, lambda r, c, v: 2 if v == 7 else v)


def all_two(inp, out):
    return _map(inp, lambda r, c, v: 2)


def wrong_target_color(inp, out):
    return _map(inp, lambda r, c, v: 8 if v == 6 else v)


def top_half_only(inp, out):
    h = len(inp) // 2 or 1
    return _map(inp, lambda r, c, v: 2 if (v == 6 and r < h) else v)


def left_half_only(inp, out):
    w = len(inp[0]) // 2
    return _map(inp, lambda r, c, v: 2 if (v == 6 and c < w) else v)


def first_cell_missed(inp, out):
    g = [row[:] for row in out]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == 6:
                g[r][c] = 6
                return g
    return None


def swap_roles(inp, out):
    return _map(inp, lambda r, c, v: 7 if v == 6 else 2)


def six_to_seven_seven_to_two(inp, out):
    return _map(inp, lambda r, c, v: 7 if v == 6 else (2 if v == 7 else v))


def flip_rows(inp, out):
    return out[::-1]


def drop_last_column(inp, out):
    return [row[:-1] for row in out]


def drop_first_row(inp, out):
    return out[1:]


def only_non_isolated(inp, out):
    h, w = len(inp), len(inp[0])

    def nb(r, c):
        return any(
            0 <= r + dr < h and 0 <= c + dc < w and inp[r + dr][c + dc] == 6
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )

    return _map(inp, lambda r, c, v: 2 if (v == 6 and nb(r, c)) else v)


def seven_also_two_on_border(inp, out):
    h, w = len(inp), len(inp[0])
    return _map(
        out,
        lambda r, c, v: 2 if (v == 7 and (r in (0, h - 1) or c in (0, w - 1))) else v,
    )


ALTERNATIVES = [
    ("recolor 7 to 2 instead of 6 to 2", recolor_7),
    ("fill the whole grid with 2", all_two),
    ("recolor 6 to 8 instead of 2", wrong_target_color),
    ("recolor 6 to 2 in the top half only", top_half_only),
    ("recolor 6 to 2 in the left half only", left_half_only),
    ("true output with the first 6 in reading order left unrecolored", first_cell_missed),
    ("swap roles: 6 becomes 7 and 7 becomes 2", six_to_seven_seven_to_two),
    ("binarize: 6 becomes 7, everything else becomes 2", swap_roles),
    ("true output flipped top to bottom", flip_rows),
    ("true output with the last column dropped", drop_last_column),
    ("recolor only 6 cells that touch another 6 orthogonally", only_non_isolated),
    ("true output with all border 7 cells also recolored to 2", seven_also_two_on_border),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/b1948b0a.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn([r[:] for r in p["input"]], [r[:] for r in p["output"]])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
