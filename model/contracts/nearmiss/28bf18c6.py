import json
from pathlib import Path


def box(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return r0, r1, c0, c1


def crop(inp, dr0=0, dr1=0, dc0=0, dc1=0):
    r0, r1, c0, c1 = box(inp)
    r0 += dr0
    r1 += dr1
    c0 += dc0
    c1 += dc1
    h, w = len(inp), len(inp[0])
    out = []
    for r in range(r0, r1 + 1):
        out.append([inp[r][c] if 0 <= r < h and 0 <= c < w else 0 for c in range(c0, c1 + 1)])
    return out


def hcat(*gs):
    return [sum((g[r] for g in gs), []) for r in range(len(gs[0]))]


def one_copy(inp, out):
    return crop(inp)


def three_copies(inp, out):
    b = crop(inp)
    return hcat(b, b, b)


def vertical_tiling(inp, out):
    b = crop(inp)
    return b + [row[:] for row in b]


def grid_2x2(inp, out):
    b = crop(inp)
    row = hcat(b, b)
    return row + [r[:] for r in row]


def mirrored_second_copy(inp, out):
    b = crop(inp)
    return hcat(b, [r[::-1] for r in b])


def flipped_second_copy(inp, out):
    b = crop(inp)
    return hcat(b, b[::-1])


def box_extra_column(inp, out):
    b = crop(inp, dc1=1)
    return hcat(b, b)


def box_missing_last_row(inp, out):
    b = crop(inp, dr1=-1)
    return hcat(b, b)


def full_width_rows(inp, out):
    r0, r1, _, _ = box(inp)
    return [inp[r][:] for r in range(r0, r1 + 1)]


def recolored(inp, out):
    return [[0 if v == 0 else (v % 9) + 1 for v in row] for row in out]


def inverted_second_copy(inp, out):
    b = crop(inp)
    col = max(v for row in b for v in row)
    inv = [[0 if v else col for v in row] for row in b]
    return hcat(b, inv)


def overlapped_copies(inp, out):
    b = crop(inp)
    h, w = len(b), len(b[0])
    res = [[0] * (2 * w - 1) for _ in range(h)]
    for k in range(2):
        for r in range(h):
            for c in range(w):
                if b[r][c]:
                    res[r][c + k * (w - 1)] = b[r][c]
    return res


def transposed_box(inp, out):
    b = crop(inp)
    t = [list(x) for x in zip(*b)]
    return hcat(t, t)


ALTERNATIVES = [
    ("Output is a single copy of the shape's bounding box, not tiled", one_copy),
    ("Shape box tiled three times horizontally", three_copies),
    ("Shape box tiled twice vertically instead of horizontally", vertical_tiling),
    ("Shape box tiled in a 2x2 grid", grid_2x2),
    ("Second copy is mirrored left-right", mirrored_second_copy),
    ("Second copy is flipped top-bottom", flipped_second_copy),
    ("Bounding box one column too wide on the right, then tiled twice", box_extra_column),
    ("Bounding box one row too short at the bottom, then tiled twice", box_missing_last_row),
    ("Crop takes the box rows across the full input width, no tiling", full_width_rows),
    ("Correct tiling with the shape color changed to the next color", recolored),
    ("Second copy has filled and empty cells swapped", inverted_second_copy),
    ("Copies overlap by one column and are merged", overlapped_copies),
]


def valid(g):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/28bf18c6.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
