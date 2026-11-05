"""Near-miss readings for ARC task a65b410d."""
import json
from pathlib import Path


def _bar(inp):
    for r, row in enumerate(inp):
        n = sum(1 for v in row if v != 0)
        if n:
            return r, n, [v for v in row if v][0]
    return None


def _build(inp, up=3, down=1, grow=-1, up_len=lambda L, k: L + k,
           down_len=lambda L, k: L - k, bar_color=None, mirror=False,
           down_floor=False):
    """Staircase builder. grow is the row direction in which runs grow."""
    r, L, c = _bar(inp)
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    for x in range(L):
        g[r][x] = c if bar_color is None else bar_color
    k = 1
    while True:
        ra, rb = r + grow * k, r - grow * k
        done = True
        if 0 <= ra < h:
            done = False
            for x in range(min(max(up_len(L, k), 0), w)):
                g[ra][x] = up
        if 0 <= rb < h:
            done = False
            n = down_len(L, k)
            if down_floor:
                n = max(n, 1)
            for x in range(min(max(n, 0), w)):
                g[rb][x] = down
        if done:
            break
        k += 1
    if mirror:
        g = [row[::-1] for row in g]
    return g


def swap_colors(inp, out):
    return _build(inp, up=1, down=3)


def flip_direction(inp, out):
    return _build(inp, grow=1)


def above_off_by_one(inp, out):
    return _build(inp, up_len=lambda L, k: L + k - 1)


def below_off_by_one(inp, out):
    return _build(inp, down_len=lambda L, k: L - k + 1)


def only_above(inp, out):
    return _build(inp, down_len=lambda L, k: 0)


def only_below(inp, out):
    return _build(inp, up_len=lambda L, k: 0)


def right_anchored(inp, out):
    return _build(inp, mirror=True)


def double_step(inp, out):
    return _build(inp, up_len=lambda L, k: L + 2 * k,
                  down_len=lambda L, k: L - 2 * k)


def constant_length(inp, out):
    return _build(inp, up_len=lambda L, k: L, down_len=lambda L, k: L)


def bar_recolored(inp, out):
    return _build(inp, bar_color=3)


def transposed(inp, out):
    g = _build(inp)
    return [list(col) for col in zip(*g)]


def below_never_ends(inp, out):
    return _build(inp, down_floor=True)


ALTERNATIVES = [
    ("above and below colors swapped (1 above, 3 below)", swap_colors),
    ("runs grow downward and shrink upward", flip_direction),
    ("above runs one cell too short (L+k-1)", above_off_by_one),
    ("below runs one cell too long (L-k+1)", below_off_by_one),
    ("only the growing runs above are drawn, shrinking runs omitted", only_above),
    ("only the shrinking runs below are drawn, growing runs omitted", only_below),
    ("runs anchored on the right edge instead of the left", right_anchored),
    ("runs change by two cells per line instead of one", double_step),
    ("every run keeps the bar length L", constant_length),
    ("bar line recolored with the above color", bar_recolored),
    ("staircase drawn along columns (transposed)", transposed),
    ("below runs stop shrinking at length 1 and continue to the bottom", below_never_ends),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/a65b410d.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
