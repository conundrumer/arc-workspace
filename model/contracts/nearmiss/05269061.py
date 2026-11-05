import json
from pathlib import Path


def _cycle(out):
    """Colors of the true output by (r+c) % 3."""
    h, w = len(out), len(out[0])
    cl = [None] * 3
    for r in range(h):
        for c in range(w):
            cl[(r + c) % 3] = out[r][c]
    return cl


def _build(out, f):
    return [[f(r, c) for c in range(len(out[0]))] for r in range(len(out))]


def main_diagonals(inp, out):
    cl = _cycle(out)
    return _build(out, lambda r, c: cl[(c - r) % 3])


def column_stripes(inp, out):
    cl = _cycle(out)
    return _build(out, lambda r, c: cl[c % 3])


def row_stripes(inp, out):
    cl = _cycle(out)
    return _build(out, lambda r, c: cl[r % 3])


def period_two(inp, out):
    cl = _cycle(out)
    return _build(out, lambda r, c: cl[(r + c) % 2])


def reversed_order(inp, out):
    cl = _cycle(out)
    return _build(out, lambda r, c: cl[2 - (r + c) % 3])


def phase_shifted(inp, out):
    cl = _cycle(out)
    return _build(out, lambda r, c: cl[(r + c + 1) % 3])


def lower_right_unfilled(inp, out):
    n = len(out) - 1
    return _build(out, lambda r, c: 0 if r + c > n else out[r][c])


def single_color(inp, out):
    cl = _cycle(out)
    return _build(out, lambda r, c: cl[0])


def mirrored(inp, out):
    return [row[::-1] for row in out]


def fill_up_to_last_input_stripe(inp, out):
    last = max(r + c for r, row in enumerate(inp) for c, v in enumerate(row) if v)
    return _build(out, lambda r, c: out[r][c] if r + c <= last else 0)


def sorted_color_cycle(inp, out):
    cl = sorted(set(_cycle(out)))
    return _build(out, lambda r, c: cl[(r + c) % 3])


def stripes_of_width_two(inp, out):
    cl = _cycle(out)
    return _build(out, lambda r, c: cl[((r + c) // 2) % 3])


ALTERNATIVES = [
    ("Stripes run along the main diagonal instead of the anti-diagonal", main_diagonals),
    ("Colors repeat by column only", column_stripes),
    ("Colors repeat by row only", row_stripes),
    ("Period is 2 instead of 3: only the first two stripe colors alternate", period_two),
    ("Stripe colors cycle in the reverse order", reversed_order),
    ("Pattern phase is off by one diagonal", phase_shifted),
    ("Stripes are extended only to the upper-left half; the lower-right half stays background", lower_right_unfilled),
    ("The whole grid is filled with one stripe color", single_color),
    ("Pattern is mirrored left to right", mirrored),
    ("Stripes are extended only up to the last diagonal that holds input color", fill_up_to_last_input_stripe),
    ("Stripe colors cycle in sorted color-value order", sorted_color_cycle),
    ("Each stripe is two diagonals wide", stripes_of_width_two),
]


def _valid(g, out):
    if g is None:
        return False
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/05269061.json'))
    train = task['train']
    print(f'{len(ALTERNATIVES)} readings, {len(train)} train pairs')
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p['input'], p['output']), p['output']) for p in train)
        print(f'{n}/{len(train)}  {desc}')
