import json
from pathlib import Path


def _markers(inp):
    return [(c, v) for c, v in enumerate(inp[0]) if v != 0]


def _draw(inp, rows_center, rows_flank, flank_dx=(-1, 1), color_of=None):
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    marks = _markers(inp)
    for i, (c, v) in enumerate(marks):
        col = color_of(i, v, marks) if color_of else v
        for r in range(h):
            if r in rows_center:
                g[r][c] = col
            if r in rows_flank:
                for dx in flank_dx:
                    if 0 <= c + dx < w:
                        g[r][c + dx] = col
    return g


def _rows(h, start, step):
    return set(range(start, h, step))


def no_flanks(inp, out):
    h = len(inp)
    return _draw(inp, _rows(h, 0, 2), set())


def solid_line(inp, out):
    h = len(inp)
    return _draw(inp, _rows(h, 0, 1), set())


def period_three(inp, out):
    h = len(inp)
    return _draw(inp, _rows(h, 0, 3), _rows(h, 1, 3))


def flanks_with_centers(inp, out):
    h = len(inp)
    return _draw(inp, _rows(h, 0, 2), _rows(h, 0, 2))


def phase_shifted(inp, out):
    h = len(inp)
    return _draw(inp, _rows(h, 1, 2), _rows(h, 2, 2))


def single_stamp(inp, out):
    return _draw(inp, {0}, {1})


def right_flank_only(inp, out):
    h = len(inp)
    return _draw(inp, _rows(h, 0, 2), _rows(h, 1, 2), flank_dx=(1,))


def half_length(inp, out):
    h = len(inp)
    g = _draw(inp, _rows(h, 0, 2), _rows(h, 1, 2))
    return [row if r < h // 2 else [0] * len(row) for r, row in enumerate(g)]


def first_color_everywhere(inp, out):
    h = len(inp)
    g = _draw(inp, _rows(h, 0, 2), _rows(h, 1, 2),
              color_of=lambda i, v, marks: marks[0][1])
    return None if g == out else g


def anchored_at_bottom(inp, out):
    return [row[:] for row in reversed(out)]


def wide_flanks(inp, out):
    h = len(inp)
    return _draw(inp, _rows(h, 0, 2), _rows(h, 1, 2), flank_dx=(-2, 2))


def horizontal_trail(inp, out):
    return [list(col) for col in zip(*out)]


ALTERNATIVES = [
    ("trail has centers only, no diagonal flank cells", no_flanks),
    ("trail is a solid line of the marker color in every row", solid_line),
    ("trail repeats with period 3 instead of 2", period_three),
    ("flank cells appear on the same rows as the centers", flanks_with_centers),
    ("pattern phase shifted by one row: centers on odd rows, flanks on even rows", phase_shifted),
    ("only one stamp is drawn below the marker, no repetition", single_stamp),
    ("flanks only on the right of the center", right_flank_only),
    ("trail stops halfway down the grid", half_length),
    ("every trail uses the first marker's color", first_color_everywhere),
    ("trail is anchored at the bottom edge, pattern flipped vertically", anchored_at_bottom),
    ("flank cells two columns from the center instead of one", wide_flanks),
    ("trail runs horizontally (output transposed)", horizontal_trail),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/3ac3eb23.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
