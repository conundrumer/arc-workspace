import json
from pathlib import Path


def _bg(inp):
    flat = [c for r in inp for c in r]
    return max(set(flat), key=flat.count)


def _sources(inp):
    b = _bg(inp)
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != b]


def _ray(inp, dr, dc, limit=None, start=1, both=None):
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    dirs = [(dr, dc)] + ([both] if both else [])
    for r, c, v in _sources(inp):
        for (a, b) in dirs:
            k = start
            while limit is None or k < start + limit:
                rr, cc = r + a * k, c + b * k
                if not (0 <= rr < h and 0 <= cc < w):
                    break
                if inp[rr][cc] == _bg(inp):
                    g[rr][cc] = v
                k += 1
    return g


def up(inp, out):
    return _ray(inp, -1, 0)


def right(inp, out):
    return _ray(inp, 0, 1)


def left(inp, out):
    return _ray(inp, 0, -1)


def down_one_cell(inp, out):
    return _ray(inp, 1, 0, limit=1)


def down_skip_one(inp, out):
    return _ray(inp, 1, 0, start=2)


def up_and_down(inp, out):
    return _ray(inp, 1, 0, both=(-1, 0))


def diagonal_down_right(inp, out):
    return _ray(inp, 1, 1)


def down_and_right(inp, out):
    return _ray(inp, 1, 0, both=(0, 1))


def first_color_for_all(inp, out):
    srcs = _sources(inp)
    col = srcs[0][2]
    g = [row[:] for row in inp]
    for r, c, v in srcs:
        for rr in range(r + 1, len(g)):
            if inp[rr][c] == _bg(inp):
                g[rr][c] = col
    return g


def only_leftmost_source(inp, out):
    srcs = _sources(inp)
    cmin = min(c for _, c, _ in srcs)
    g = [row[:] for row in inp]
    for r, c, v in srcs:
        if c != cmin:
            continue
        for rr in range(r + 1, len(g)):
            if inp[rr][c] == _bg(inp):
                g[rr][c] = v
    return g


def transposed_output(inp, out):
    return [list(r) for r in zip(*out)]


def sources_erased_after_fill(inp, out):
    g = [row[:] for row in out]
    for r, c, v in _sources(inp):
        g[r][c] = _bg(inp)
    return g


ALTERNATIVES = [
    ("fill upward instead of downward", up),
    ("fill rightward along rows", right),
    ("fill leftward along rows", left),
    ("extend each colored cell by one cell only", down_one_cell),
    ("fill downward but start two cells below the source", down_skip_one),
    ("fill both up and down", up_and_down),
    ("fill diagonally down-right", diagonal_down_right),
    ("fill down and right", down_and_right),
    ("every ray takes the first colored cell's color", first_color_for_all),
    ("only the leftmost colored cell extends", only_leftmost_source),
    ("output is the transpose of the true output", transposed_output),
    ("source cells are cleared after the fill", sources_erased_after_fill),
]


def _valid(g):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/d037b0a7.json").read_text())
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
