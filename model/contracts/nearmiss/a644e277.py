import json
from pathlib import Path


def _locate(inp, out):
    h, w = len(out), len(out[0])
    for r in range(len(inp) - h + 1):
        for c in range(len(inp[0]) - w + 1):
            if all(inp[r + i][c:c + w] == out[i] for i in range(h)):
                return r, c
    return None


def _colors(out):
    line = out[0][1]
    bg = out[0][0]
    noise = {v for row in out for v in row} - {line, bg}
    return line, bg, noise


def _crop(inp, r0, r1, c0, c1):
    r0, c0 = max(r0, 0), max(c0, 0)
    r1, c1 = min(r1, len(inp)), min(c1, len(inp[0]))
    return [row[c0:c1] for row in inp[r0:r1]]


def strip_border(inp, out):
    return [row[1:-1] for row in out[1:-1]]


def margin_one(inp, out):
    p = _locate(inp, out)
    h, w = len(out), len(out[0])
    return _crop(inp, p[0] - 1, p[0] + h + 1, p[1] - 1, p[1] + w + 1)


def full_width_rows(inp, out):
    p = _locate(inp, out)
    return _crop(inp, p[0], p[0] + len(out), 0, len(inp[0]))


def full_height_cols(inp, out):
    p = _locate(inp, out)
    return _crop(inp, 0, len(inp), p[1], p[1] + len(out[0]))


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def flipped(inp, out):
    return [row[:] for row in out[::-1]]


def corners_line_color(inp, out):
    line, bg, noise = _colors(out)
    g = [row[:] for row in out]
    for r in (0, len(g) - 1):
        for c in (0, len(g[0]) - 1):
            g[r][c] = line
    return g


def noise_cleared(inp, out):
    line, bg, noise = _colors(out)
    return [[bg if v in noise else v for v in row] for row in out]


def lines_removed(inp, out):
    line, bg, noise = _colors(out)
    return [[bg if v == line else v for v in row] for row in out]


def short_one(inp, out):
    return [row[:-1] for row in out[:-1]]


def first_tile(inp, out):
    h, w = len(out), len(out[0])
    line = out[0][1]
    rows = [r for r in range(1, h - 1) if out[r][1:-1] and all(v == line for v in out[r][1:-1])]
    cols = [c for c in range(1, w - 1) if all(out[r][c] == line for r in range(1, h - 1))]
    r1 = rows[0] if rows else h - 1
    c1 = cols[0] if cols else w - 1
    return [row[1:c1] for row in out[1:r1]]


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("crop the gap rectangle but drop its border rows and columns", strip_border),
    ("crop the gap rectangle with one extra cell of margin on every side", margin_one),
    ("keep the gap rectangle's rows but across the full grid width", full_width_rows),
    ("keep the gap rectangle's columns but down the full grid height", full_height_cols),
    ("crop correctly but transpose the result", transposed),
    ("crop correctly but flip the result upside down", flipped),
    ("the four gap corners drawn in the line color", corners_line_color),
    ("the crop with the third color cells cleared to background", noise_cleared),
    ("the crop with the line cells replaced by background", lines_removed),
    ("crop one row and one column short at the bottom and right", short_one),
    ("only the first tile inside the rectangle", first_tile),
    ("the input grid unchanged", unchanged),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/a644e277.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, repr(e))
                continue
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))
            if ok and g != p["output"]:
                n += 1
        print(n, desc)
