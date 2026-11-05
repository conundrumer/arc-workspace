import json
from pathlib import Path


def _panels(inp, out):
    """Panel colors in reading order (one color per panel), from the input."""
    n = len(out)
    size = (len(inp) - n + 1) // n
    step = size + 1
    return [[inp[i * step][j * step] for j in range(n)] for i in range(n)], size


def _line_color(inp, out):
    _, size = _panels(inp, out)
    return inp[size][size]


def _fliplr(g):
    return [row[::-1] for row in g]


def _flipud(g):
    return [row[:] for row in g[::-1]]


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _rot_cw(g):
    return [list(r) for r in zip(*g[::-1])]


def _rot_ccw(g):
    return [list(r) for r in zip(*g)][::-1]


def no_flip(inp, out):
    g, _ = _panels(inp, out)
    return g


def flip_vertical(inp, out):
    g, _ = _panels(inp, out)
    return _flipud(g)


def transposed(inp, out):
    g, _ = _panels(inp, out)
    return _transpose(g)


def rotated_cw(inp, out):
    g, _ = _panels(inp, out)
    return _rot_cw(g)


def rotated_ccw(inp, out):
    g, _ = _panels(inp, out)
    return _rot_ccw(g)


def rotated_180(inp, out):
    g, _ = _panels(inp, out)
    return _flipud(_fliplr(g))


def keep_lines(inp, out):
    """Flipped panels, but with the cutting lines kept between them."""
    g, _ = _panels(inp, out)
    g = _fliplr(g)
    n = len(g)
    line = _line_color(inp, out)
    res = []
    for i in range(2 * n - 1):
        if i % 2:
            res.append([line] * (2 * n - 1))
        else:
            res.append([g[i // 2][j // 2] if j % 2 == 0 else line for j in range(2 * n - 1)])
    return res


def drop_last_panel_row_col(inp, out):
    """Flipped panels, but the last panel row and column are lost."""
    g, _ = _panels(inp, out)
    g = _fliplr(g)
    return [row[:-1] for row in g[:-1]]


def line_color_for_filled(inp, out):
    """Flipped panels, but each non-zero panel gets the cutting line's color."""
    g, _ = _panels(inp, out)
    line = _line_color(inp, out)
    return [[line if c else 0 for c in row] for row in _fliplr(g)]


def majority_color_only(inp, out):
    """Flipped panels, but every non-zero panel gets the most common non-zero panel color."""
    g, _ = _panels(inp, out)
    counts = {}
    for row in g:
        for c in row:
            if c:
                counts[c] = counts.get(c, 0) + 1
    if not counts:
        return None
    top = max(sorted(counts), key=lambda c: counts[c])
    return [[top if c else 0 for c in row] for row in _fliplr(g)]


def empty_panels_get_line_color(inp, out):
    """Flipped panels, but zero panels take the cutting line's color."""
    g, _ = _panels(inp, out)
    line = _line_color(inp, out)
    return [[c if c else line for c in row] for row in _fliplr(g)]


def upscaled_blocks(inp, out):
    """Flipped panels, each drawn as a block of the panel's size."""
    g, size = _panels(inp, out)
    g = _fliplr(g)
    return [[c for c in row for _ in range(size)] for row in g for _ in range(size)]


def shifted_one_column(inp, out):
    """Flipped panels, shifted one column to the left with wrap-around."""
    g, _ = _panels(inp, out)
    return [row[1:] + row[:1] for row in _fliplr(g)]


ALTERNATIVES = [
    ("read the panels in plain reading order, with no mirroring", no_flip),
    ("mirror the panel arrangement top to bottom instead of left to right", flip_vertical),
    ("transpose the panel arrangement", transposed),
    ("rotate the panel arrangement 90 degrees clockwise", rotated_cw),
    ("rotate the panel arrangement 90 degrees counterclockwise", rotated_ccw),
    ("rotate the panel arrangement 180 degrees", rotated_180),
    ("keep the cutting lines in the output between the mirrored panel cells", keep_lines),
    ("lose the last panel row and column of the mirrored arrangement", drop_last_panel_row_col),
    ("paint non-zero panels with the cutting line color instead of the panel color", line_color_for_filled),
    ("paint all non-zero panels with the most common non-zero panel color", majority_color_only),
    ("paint zero panels with the cutting line color", empty_panels_get_line_color),
    ("draw each mirrored panel as a block of the panel size", upscaled_blocks),
    ("shift the mirrored arrangement one column left with wrap-around", shifted_one_column),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(type(c) is int and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/9f236235.json").read_text())
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(train)}  {desc}")
