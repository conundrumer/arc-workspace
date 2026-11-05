import json
from pathlib import Path


def halves(inp):
    n = (len(inp) - 1) // 2
    return inp[:n], inp[n + 1:]


def combine(inp, f, color=3):
    a, b = halves(inp)
    return [[color if f(x != 0, y != 0) else 0 for x, y in zip(ra, rb)]
            for ra, rb in zip(a, b)]


def or_(inp, out):
    return combine(inp, lambda x, y: x or y)


def and_(inp, out):
    return combine(inp, lambda x, y: x and y)


def nor(inp, out):
    return combine(inp, lambda x, y: not (x or y))


def xnor(inp, out):
    return combine(inp, lambda x, y: x == y)


def top_only(inp, out):
    return combine(inp, lambda x, y: x and not y)


def bottom_only(inp, out):
    return combine(inp, lambda x, y: y and not x)


def wrong_color(inp, out):
    return [[1 if v else 0 for v in r] for r in out]


def xor_mirror(inp, out):
    a, b = halves(inp)
    b = b[::-1]
    return [[3 if (x != 0) != (y != 0) else 0 for x, y in zip(ra, rb)]
            for ra, rb in zip(a, b)]


def xor_shift_col(inp, out):
    a, b = halves(inp)
    return [[3 if (ra[j] != 0) != (rb[(j + 1) % len(rb)] != 0) else 0
             for j in range(len(ra))] for ra, rb in zip(a, b)]


def drop_last_row(inp, out):
    return [r[:] for r in out[:-1]]


def full_with_separator(inp, out):
    a, b = halves(inp)
    x = [[3 if (p != 0) != (q != 0) else 0 for p, q in zip(ra, rb)]
         for ra, rb in zip(a, b)]
    return x + [[4] * len(x[0])] + [[0] * len(x[0]) for _ in x]


def top_row_zeroed(inp, out):
    g = [r[:] for r in out]
    g[0] = [0] * len(g[0])
    return g


def keep_input_colors(inp, out):
    a, b = halves(inp)
    return [[(x or y) if (x != 0) != (y != 0) else 0 for x, y in zip(ra, rb)]
            for ra, rb in zip(a, b)]


ALTERNATIVES = [
    ("OR of the two halves instead of XOR", or_),
    ("AND of the two halves instead of XOR", and_),
    ("NOR: mark cells empty in both halves", nor),
    ("XNOR: mark cells where both halves agree", xnor),
    ("mark only cells set in the top half and not the bottom", top_only),
    ("mark only cells set in the bottom half and not the top", bottom_only),
    ("XOR result painted with color 1 instead of 3", wrong_color),
    ("bottom half flipped vertically before XOR", xor_mirror),
    ("bottom half shifted one column before XOR", xor_shift_col),
    ("output drops its last row (off-by-one size)", drop_last_row),
    ("output keeps the whole input frame with separator", full_with_separator),
    ("XOR cells keep their source color (1 or 2)", keep_input_colors),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/99b1bc43.json'))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
