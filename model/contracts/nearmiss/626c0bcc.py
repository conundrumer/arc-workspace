import json
from pathlib import Path


def _swap(out, a, b):
    m = {a: b, b: a}
    return [[m.get(v, v) for v in row] for row in out]


def _map(out, mapping):
    return [[mapping.get(v, v) for v in row] for row in out]


def swap_2_3(inp, out):
    return _swap(out, 2, 3)


def swap_2_4(inp, out):
    return _swap(out, 2, 4)


def swap_3_4(inp, out):
    return _swap(out, 3, 4)


def swap_1_2(inp, out):
    return _swap(out, 1, 2)


def squares_unpainted(inp, out):
    return _map(out, {1: 8})


def corners_unpainted(inp, out):
    return _map(out, {2: 8, 3: 8, 4: 8})


def corners_as_square_color(inp, out):
    return _map(out, {2: 1, 3: 1, 4: 1})


def single_color_ink(inp, out):
    return [[1 if v == 8 else v for v in row] for row in inp]


def ink_erased(inp, out):
    return [[0 if v == 8 else v for v in row] for row in inp]


def shifted_right(inp, out):
    return [[0] + row[:-1] for row in out]


def shifted_down(inp, out):
    return [[0] * len(out[0])] + [row[:] for row in out[:-1]]


def mirrored(inp, out):
    return [row[::-1] for row in out]


ALTERNATIVES = [
    ("Colors 2 and 3 exchanged between the two L orientations", swap_2_3),
    ("Colors 2 and 4 exchanged between the two L orientations", swap_2_4),
    ("Colors 3 and 4 exchanged between the two L orientations", swap_3_4),
    ("Square color 1 and L color 2 exchanged", swap_1_2),
    ("2x2 squares left unpainted (still 8)", squares_unpainted),
    ("L trominoes left unpainted (still 8)", corners_unpainted),
    ("L trominoes painted with the square color", corners_as_square_color),
    ("Every ink cell painted one color 1 (no piece split)", single_color_ink),
    ("Ink cells erased to background", ink_erased),
    ("Output shifted one column right", shifted_right),
    ("Output shifted one row down", shifted_down),
    ("Output mirrored left to right", mirrored),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/626c0bcc.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
