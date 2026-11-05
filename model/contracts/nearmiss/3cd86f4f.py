import json
from pathlib import Path


def place(inp, shifts, width, pad=0):
    return [[pad] * s + list(r) + [pad] * (width - s - len(r)) for r, s in zip(inp, shifts)]


def lean_right(inp, out):
    # slant the wrong way: row i shifted by i
    h, w = len(inp), len(inp[0])
    return place(inp, [i for i in range(h)], w + h - 1)


def one_extra_column(inp, out):
    h, w = len(inp), len(inp[0])
    return place(inp, [h - i for i in range(h)], w + h)


def one_less_column(inp, out):
    h, w = len(inp), len(inp[0])
    return place(inp, [max(h - 2 - i, 0) for i in range(h)], w + h - 2)


def step_two(inp, out):
    h, w = len(inp), len(inp[0])
    return place(inp, [2 * (h - 1 - i) for i in range(h)], w + 2 * (h - 1))


def vertical_slant(inp, out):
    # slide columns instead of rows
    h, w = len(inp), len(inp[0])
    H = h + w - 1
    g = [[0] * w for _ in range(H)]
    for j in range(w):
        for i in range(h):
            g[i + (w - 1 - j)][j] = inp[i][j]
    return g


def wrap_around(inp, out):
    # rows rotate cyclically, no widening
    h, w = len(inp), len(inp[0])
    res = []
    for i, r in enumerate(inp):
        s = (h - 1 - i) % w
        res.append(r[-s:] + r[:-s] if s else list(r))
    return res


def pad_with_corner_color(inp, out):
    h, w = len(inp), len(inp[0])
    c = inp[0][0]
    return place(inp, [h - 1 - i for i in range(h)], w + h - 1, c)


def only_left_pad_colored(inp, out):
    h, w = len(inp), len(inp[0])
    res = place(inp, [h - 1 - i for i in range(h)], w + h - 1)
    for i, r in enumerate(res):
        for j in range(h - 1 - i):
            r[j] = inp[i][0]
    return res


def mirrored(inp, out):
    return [r[::-1] for r in out]


def upside_down(inp, out):
    return out[::-1]


def top_half_only(inp, out):
    h, w = len(inp), len(inp[0])
    sh = [(h - 1 - i) if i < h // 2 else 0 for i in range(h)]
    return place(inp, sh, w + h - 1)


def input_as_is(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("slant leans the other way: row i shifts right by i", lean_right),
    ("output one column too wide (shift h-i instead of h-1-i)", one_extra_column),
    ("output one column too narrow; bottom two rows both unshifted", one_less_column),
    ("each row shifts by 2 more than the row below", step_two),
    ("columns slide down instead of rows sliding sideways", vertical_slant),
    ("rows rotate cyclically with wrap-around, grid not widened", wrap_around),
    ("padding filled with the input's top-left color instead of 0", pad_with_corner_color),
    ("only the left padding is filled, with each row's first color", only_left_pad_colored),
    ("true output mirrored left to right", mirrored),
    ("true output flipped top to bottom", upside_down),
    ("only the top half of the rows is shifted", top_half_only),
    ("input returned unchanged", input_as_is),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/3cd86f4f.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
