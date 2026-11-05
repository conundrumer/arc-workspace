"""Near-miss rules for ARC task 6ecd11f4.

Rule: the input holds one large shape (a coarse pattern drawn at block scale)
and one small multicolor NxN square. The shape's box splits into NxN blocks.
The output is the square, where cells whose block is filled in the shape keep
the square's color, and the other cells become background.
"""
import json
from pathlib import Path


def _parts(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0
                                and (ny, nx) not in seen):
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            comps.append(cells)

    def box(cells):
        ys = [p[0] for p in cells]
        xs = [p[1] for p in cells]
        return min(ys), min(xs), max(ys), max(xs)

    def area(cells):
        y0, x0, y1, x1 = box(cells)
        return (y1 - y0 + 1) * (x1 - x0 + 1)

    sq = min(comps, key=area)
    sh = max(comps, key=area)
    sy0, sx0, sy1, sx1 = box(sq)
    n = sy1 - sy0 + 1
    square = [[inp[sy0 + i][sx0 + j] for j in range(n)] for i in range(n)]
    hy0, hx0, hy1, hx1 = box(sh)
    k = (hy1 - hy0 + 1) // n
    shape_cells = set(sh)
    mask = [[1 if (hy0 + i * k, hx0 + j * k) in shape_cells else 0
             for j in range(n)] for i in range(n)]
    shape_col = inp[sh[0][0]][sh[0][1]]
    return square, mask, shape_col, k


def _apply(square, mask, col=None):
    n = len(square)
    return [[(square[i][j] if col is None else col) if mask[i][j] else 0
             for j in range(n)] for i in range(n)]


def inverted_mask(inp, out):
    sq, m, _, _ = _parts(inp)
    return _apply(sq, [[1 - v for v in row] for row in m])


def square_mirrored(inp, out):
    sq, m, _, _ = _parts(inp)
    return _apply([row[::-1] for row in sq], m)


def square_transposed(inp, out):
    sq, m, _, _ = _parts(inp)
    return _apply([list(r) for r in zip(*sq)], m)


def mask_mirrored(inp, out):
    sq, m, _, _ = _parts(inp)
    g = _apply(sq, [row[::-1] for row in m])
    return None if g == out else g


def mask_flipped_vertically(inp, out):
    sq, m, _, _ = _parts(inp)
    g = _apply(sq, m[::-1])
    return None if g == out else g


def shape_color_fill(inp, out):
    sq, m, col, _ = _parts(inp)
    return _apply(sq, m, col)


def unmasked_square(inp, out):
    sq, _, _, _ = _parts(inp)
    return [row[:] for row in sq]


def padded_border(inp, out):
    w = len(out[0])
    return ([[0] * (w + 2)] + [[0] + row + [0] for row in out]
            + [[0] * (w + 2)])


def square_rotated(inp, out):
    sq, m, _, _ = _parts(inp)
    rot = [list(r)[::-1] for r in zip(*sq)]
    return _apply(rot, m)


def single_square_color(inp, out):
    sq, m, _, _ = _parts(inp)
    flat = [v for row in sq for v in row]
    col = max(set(flat), key=flat.count)
    return _apply(sq, m, col)


def block_scale_output(inp, out):
    _, _, _, k = _parts(inp)
    return [[v for v in row for _ in range(k)] for row in out for _ in range(k)]


def mask_shifted_one_column(inp, out):
    sq, m, _, _ = _parts(inp)
    return _apply(sq, [row[-1:] + row[:-1] for row in m])


ALTERNATIVES = [
    ("fill the blocks the shape lacks instead of the blocks it has", inverted_mask),
    ("read the square's colors mirrored left to right", square_mirrored),
    ("read the square's colors transposed", square_transposed),
    ("mirror the shape's block mask left to right", mask_mirrored),
    ("flip the shape's block mask upside down", mask_flipped_vertically),
    ("color the filled cells with the shape's color, not the square's", shape_color_fill),
    ("output the whole square with no masking by the shape", unmasked_square),
    ("output with an extra background border around it", padded_border),
    ("rotate the square a quarter turn before masking", square_rotated),
    ("fill the filled cells with the square's most common color", single_square_color),
    ("output at the shape's block scale instead of one cell per block", block_scale_output),
    ("shift the shape's block mask one column right", mask_shifted_one_column),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/6ecd11f4.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
