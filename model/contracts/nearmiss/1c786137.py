import json
from pathlib import Path


def locate(inp, out):
    """Top-left corner of the interior window (where out sits inside inp)."""
    h, w = len(out), len(out[0])
    for r in range(len(inp) - h + 1):
        for c in range(len(inp[0]) - w + 1):
            if all(inp[r + i][c:c + w] == out[i] for i in range(h)):
                return r, c
    return None


def crop(inp, r0, c0, r1, c1):
    """Rows r0..r1-1, cols c0..c1-1 of inp, or None if outside the grid."""
    if r0 < 0 or c0 < 0 or r1 > len(inp) or c1 > len(inp[0]) or r1 <= r0 or c1 <= c0:
        return None
    return [row[c0:c1] for row in inp[r0:r1]]


def with_border(inp, out):
    r, c = locate(inp, out)
    return crop(inp, r - 1, c - 1, r + len(out) + 1, c + len(out[0]) + 1)


def inset(inp, out):
    if len(out) < 3 or len(out[0]) < 3:
        return None
    return [row[1:-1] for row in out[1:-1]]


def shifted(inp, out):
    r, c = locate(inp, out)
    return crop(inp, r + 1, c + 1, r + 1 + len(out), c + 1 + len(out[0]))


def drop_last_col(inp, out):
    return [row[:-1] for row in out]


def border_rows_only(inp, out):
    r, c = locate(inp, out)
    return crop(inp, r - 1, c, r + len(out) + 1, c + len(out[0]))


def transposed(inp, out):
    return [list(col) for col in zip(*out)]


def flipped_h(inp, out):
    return [row[::-1] for row in out]


def rotated_cw(inp, out):
    return [list(col) for col in zip(*out[::-1])]


def mirrored_position(inp, out):
    r, c = locate(inp, out)
    h, w = len(out), len(out[0])
    flipped = inp[::-1]
    return crop(flipped, len(inp) - r - h, c, len(inp) - r, c + w)


def interior_erased(inp, out):
    r, c = locate(inp, out)
    g = [row[:] for row in inp]
    for i in range(len(out)):
        for j in range(len(out[0])):
            g[r + i][c + j] = 0
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("crop includes the outline border", with_border),
    ("crop is inset one more cell inside the interior on every side", inset),
    ("crop window shifted one cell down and right", shifted),
    ("crop drops the last interior column", drop_last_col),
    ("crop keeps the border rows but trims the border columns", border_rows_only),
    ("correct interior crop, transposed", transposed),
    ("correct interior crop, mirrored left to right", flipped_h),
    ("correct interior crop, rotated 90 degrees clockwise", rotated_cw),
    ("same-size window at the vertically mirrored position of the grid", mirrored_position),
    ("whole grid with the interior cleared to 0 instead of cropped", interior_erased),
    ("input returned unchanged", unchanged),
]


def valid(g, out):
    return (
        isinstance(g, list) and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/1c786137.json").read_text())
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(valid(fn(p["input"], p["output"]), p["output"]) for p in train)
        print(f"{n}/{len(train)}  {desc}")
