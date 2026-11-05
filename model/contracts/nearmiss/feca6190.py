import json
from pathlib import Path


def render(row, size, offset=0, maxlen=None, wrap=False, vertical=False):
    """Input row on the bottom row; each ink cell sends a ray up and to the right."""
    g = [[0] * size for _ in range(size)]
    for c, v in enumerate(row):
        if v == 0:
            continue
        c += offset
        k = 0
        while True:
            r = size - 1 - k
            cc = c if vertical else c + k
            if wrap:
                cc %= size
            if r < 0 or cc < 0 or cc >= size or (maxlen is not None and k >= maxlen):
                break
            if 0 <= c < size or wrap:
                g[r][cc] = v
            k += 1
    return g


def ink(inp):
    return sum(1 for v in inp[0] if v)


def size_minus_one(inp, out):
    return render(inp[0], 5 * ink(inp) - 1)


def size_plus_one(inp, out):
    return render(inp[0], 5 * ink(inp) + 1)


def size_from_zeros(inp, out):
    zeros = sum(1 for v in inp[0] if v == 0)
    return render(inp[0], 5 * zeros)


def flip_horizontal(inp, out):
    return [r[::-1] for r in out]


def flip_vertical(inp, out):
    return out[::-1]


def no_diagonals(inp, out):
    n = len(out)
    g = [[0] * n for _ in range(n)]
    g[n - 1][:len(inp[0])] = inp[0]
    return g


def wrap_around(inp, out):
    return render(inp[0], len(out), wrap=True)


def shifted_right(inp, out):
    return render(inp[0], len(out), offset=1)


def vertical_rays(inp, out):
    return render(inp[0], len(out), vertical=True)


def short_rays(inp, out):
    return render(inp[0], len(out), maxlen=2)


def right_aligned(inp, out):
    n = len(out)
    return render(inp[0], n, offset=n - len(inp[0]))


ALTERNATIVES = [
    ("output side is 5 times the ink count, minus one", size_minus_one),
    ("output side is 5 times the ink count, plus one", size_plus_one),
    ("output side is 5 times the zero count instead of the ink count", size_from_zeros),
    ("rays go up-left, input sits at the bottom-right", flip_horizontal),
    ("rays go down-right, input sits in the top row", flip_vertical),
    ("input is copied to the bottom row, no diagonal rays", no_diagonals),
    ("rays wrap around the right edge instead of stopping", wrap_around),
    ("input is placed one column to the right in the bottom row", shifted_right),
    ("rays go straight up instead of diagonally", vertical_rays),
    ("each ray is cut after two cells", short_rays),
    ("input is right-aligned in the bottom row of the output", right_aligned),
]


def valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/feca6190.json').read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(1 for p in pairs if (g := fn(p["input"], p["output"])) is not None and valid(g, p["output"]))
        print(n, desc)
