import json
from pathlib import Path


def _ink(inp):
    row = inp[0]
    return row[0], sum(1 for v in row if v != 0), len(row)


def _stairs(inp, rows, step=1, start=0, color=None):
    c, n, w = _ink(inp)
    c = c if color is None else color
    out = []
    for k in range(rows):
        m = min(w, n + step * max(0, k - start))
        out.append([c] * m + [0] * (w - m))
    return out


def grow_two(inp, out):
    return _stairs(inp, len(out), step=2)


def one_row_short(inp, out):
    return out[:-1]


def one_row_extra(inp, out):
    return _stairs(inp, len(out) + 1)


def right_aligned(inp, out):
    return [row[::-1] for row in out]


def reversed_rows(inp, out):
    return out[::-1]


def wrong_color(inp, out):
    c = out[0][0]
    c2 = 1 if c != 1 else 2
    return [[c2 if v else 0 for v in row] for row in out]


def no_growth(inp, out):
    return [list(inp[0]) for _ in out]


def growth_delayed(inp, out):
    return _stairs(inp, len(out), start=1)


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def square_output(inp, out):
    return _stairs(inp, len(inp[0]))


def drop_input_row(inp, out):
    return out[1:]


def full_bottom_row(inp, out):
    return out[:-1] + [[out[0][0]] * len(out[0])]


ALTERNATIVES = [
    ("each row grows by two cells instead of one", grow_two),
    ("one row too few", one_row_short),
    ("one row too many, growth continues", one_row_extra),
    ("staircase grows from the right edge (mirrored)", right_aligned),
    ("rows in reverse order, longest first", reversed_rows),
    ("shape drawn in a wrong color", wrong_color),
    ("input row copied for every output row, no growth", no_growth),
    ("growth starts one row late (second row repeats the input)", growth_delayed),
    ("output transposed, growth down columns", transposed),
    ("number of rows equals the width, not half of it", square_output),
    ("the input row is left out, only grown rows", drop_input_row),
    ("last row filled to full width", full_bottom_row),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/bbc9ae5d.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                ok += 1
        print(ok, desc)
