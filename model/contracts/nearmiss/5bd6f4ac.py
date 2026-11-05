import json
from pathlib import Path


def block(g, r, c, h=3, w=3):
    return [row[c:c + w] for row in g[r:r + h]]


def top_left(inp, out):
    return block(inp, 0, 0)


def bottom_right(inp, out):
    return block(inp, 6, 6)


def bottom_left(inp, out):
    return block(inp, 6, 0)


def center(inp, out):
    return block(inp, 3, 3)


def mirrored(inp, out):
    return [row[::-1] for row in out]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def flipped_vertically(inp, out):
    return out[::-1]


def corner_2x2(inp, out):
    return block(inp, 0, 7, 2, 2)


def corner_4x4(inp, out):
    return block(inp, 0, 5, 4, 4)


def shifted_down(inp, out):
    return block(inp, 1, 6)


def shifted_left(inp, out):
    return block(inp, 0, 5)


def whole_input(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("take the top-left 3x3 block", top_left),
    ("take the bottom-right 3x3 block", bottom_right),
    ("take the bottom-left 3x3 block", bottom_left),
    ("take the center 3x3 block", center),
    ("take the top-right block, mirrored left to right", mirrored),
    ("take the top-right block, transposed", transposed),
    ("take the top-right block, flipped top to bottom", flipped_vertically),
    ("take a 2x2 block at the top-right corner (size off by one)", corner_2x2),
    ("take a 4x4 block at the top-right corner (size off by one)", corner_4x4),
    ("take the 3x3 block one row below the top-right corner", shifted_down),
    ("take the 3x3 block one column left of the top-right corner", shifted_left),
    ("return the input unchanged", whole_input),
]


def valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/5bd6f4ac.json").read_text())
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
