"""Near-miss rules for c1990cce.

Rule: a 1xN input holds one seed cell. The output is NxN. Two arms of the seed
color run down diagonally from the seed until they leave the grid. Below the
arms, inside the cone, diagonal stripes of a second color run down and to the
right, on every fourth diagonal counted from the right arm's diagonal.
"""
import json
from pathlib import Path


def _info(inp, out):
    n = len(out)
    sc = next(i for i, v in enumerate(inp[0]) if v)
    seed = inp[0][sc]
    echo = next(v for row in out for v in row if v not in (0, seed))
    return n, sc, seed, echo


def _render(n, sc, seed, echo, stripe, arms=True, arm_color=None):
    """stripe(r, c) -> bool decides echo cells inside the cone."""
    g = [[0] * n for _ in range(n)]
    for r in range(n):
        for c in range(n):
            if r >= 1 and abs(c - sc) < r and stripe(r, c):
                g[r][c] = echo
    g[0][sc] = seed
    if arms:
        for r in range(1, n):
            for c in (sc - r, sc + r):
                if 0 <= c < n:
                    g[r][c] = seed if arm_color is None else arm_color
    return g


def _copy(g):
    return [row[:] for row in g]


def echo_in_seed_color(inp, out):
    n, sc, seed, echo = _info(inp, out)
    return [[seed if v == echo else v for v in row] for row in out]


def echo_mirrored(inp, out):
    n, sc, seed, echo = _info(inp, out)
    return [[echo if row[n - 1 - c] == echo else (v if v != echo else 0)
             for c, v in enumerate(row)] for row in out]


def echo_period_2(inp, out):
    n, sc, seed, echo = _info(inp, out)
    return _render(n, sc, seed, echo, lambda r, c: (c - r - sc) % 2 == 0)


def echo_period_8(inp, out):
    n, sc, seed, echo = _info(inp, out)
    return _render(n, sc, seed, echo, lambda r, c: (c - r - sc) % 8 == 0)


def echo_phase_shifted(inp, out):
    n, sc, seed, echo = _info(inp, out)
    return _render(n, sc, seed, echo, lambda r, c: (c - r - sc) % 4 == 2)


def echo_fills_cone(inp, out):
    n, sc, seed, echo = _info(inp, out)
    return _render(n, sc, seed, echo, lambda r, c: True)


def echo_both_directions(inp, out):
    n, sc, seed, echo = _info(inp, out)
    g = _copy(out)
    for r in range(n):
        for c in range(n):
            if out[r][n - 1 - c] == echo and g[r][c] == 0:
                g[r][c] = echo
    return g


def arms_in_echo_color(inp, out):
    n, sc, seed, echo = _info(inp, out)
    return _render(n, sc, seed, echo, lambda r, c: (c - r - sc) % 4 == 0,
                   arm_color=echo)


def arms_bounce_off_walls(inp, out):
    n, sc, seed, echo = _info(inp, out)
    g = _copy(out)
    for d in (-1, 1):
        c = sc
        step = d
        for r in range(1, n):
            c += step
            if c < 0 or c >= n:
                step = -step
                c += 2 * step
            if 0 <= c < n:
                g[r][c] = seed
    return g


def no_echo(inp, out):
    n, sc, seed, echo = _info(inp, out)
    return [[0 if v == echo else v for v in row] for row in out]


def half_height(inp, out):
    n = len(out)
    return _copy(out[:(n + 1) // 2])


def flipped_vertically(inp, out):
    return _copy(out[::-1])


ALTERNATIVES = [
    ("echo stripes drawn in the seed color instead of the second color", echo_in_seed_color),
    ("echo stripes slant down-left instead of down-right", echo_mirrored),
    ("echo stripes repeat every 2 diagonals instead of every 4", echo_period_2),
    ("echo stripes repeat every 8 diagonals instead of every 4", echo_period_8),
    ("echo stripes start at the wrong phase, offset 2 diagonals from the arm", echo_phase_shifted),
    ("echo fills the whole cone below the arms", echo_fills_cone),
    ("echo stripes drawn in both slant directions", echo_both_directions),
    ("arms drawn in the echo color", arms_in_echo_color),
    ("arms bounce off the side walls and keep going", arms_bounce_off_walls),
    ("no echo stripes, arms only", no_echo),
    ("output cropped to the rows until the arms reach the walls", half_height),
    ("output flipped vertically, seed at the bottom", flipped_vertically),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/c1990cce.json").read_text())
    pairs = task["train"]
    # sanity: the period-4 model reproduces the true outputs
    for p in pairs:
        n, sc, seed, echo = _info(p["input"], p["output"])
        assert _render(n, sc, seed, echo, lambda r, c: (c - r - sc) % 4 == 0) == p["output"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn([r[:] for r in p["input"]], [r[:] for r in p["output"]])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
