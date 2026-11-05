"""Near-miss rules for 84551f4c.

Bars of ink stand on the bottom edge. The bars of the rarest color topple
to the right and land flat along the bottom row, with the same length. A
bar that a landed bar touches on its right topples too.
"""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _bars(inp):
    """Bars standing on the bottom row: list of (col, height, color)."""
    bg = _bg(inp)
    H = len(inp)
    bars = []
    for x in range(len(inp[0])):
        c = inp[H - 1][x]
        if c == bg:
            continue
        h = 0
        while h < H and inp[H - 1 - h][x] == c:
            h += 1
        bars.append((x, h, c))
    return bars


def _sim(inp, pusher=None, chain="full", sign=1, offset=0, dlen=0,
         recolor=False, clear=True, row="base", paint=True):
    bg = _bg(inp)
    H, W = len(inp), len(inp[0])
    bars = _bars(inp)
    byx = {b[0]: b for b in bars}
    if pusher is None:
        cnt = Counter(b[2] for b in bars)
        pusher = min(cnt, key=lambda c: cnt[c])
    pc = pusher
    fallen = [b for b in bars if b[2] == pc]
    done = {b[0] for b in fallen}
    if chain != "none":
        frontier = list(fallen)
        steps = 0
        while frontier:
            steps += 1
            if chain == "one" and steps > 1:
                break
            new = []
            for x, h, c in frontier:
                nx = x + sign * h
                if chain == "all":
                    cands = [b for b in bars if (b[0] - x) * sign > 0]
                else:
                    cands = [byx[nx]] if nx in byx else []
                for b in cands:
                    if b[0] not in done:
                        done.add(b[0])
                        new.append(b)
            fallen += new
            frontier = new
    g = [r[:] for r in inp]
    if clear:
        for x, h, c in fallen:
            for k in range(h):
                g[H - 1 - k][x] = bg
    if paint:
        for x, h, c in fallen:
            col = pc if recolor else c
            r = H - 1 if row == "base" else H - h
            for k in range(max(h + dlen, 0)):
                cx = x + sign * k + offset
                if 0 <= cx < W:
                    g[r][cx] = col
    return g


def _rightmost_color(inp):
    return _bars(inp)[-1][2]


def _common_color(inp):
    cnt = Counter(b[2] for b in _bars(inp))
    return max(cnt, key=lambda c: (cnt[c], c))


def no_chain(inp, out):
    return _sim(inp, chain="none")


def chain_one_step(inp, out):
    return _sim(inp, chain="one")


def chain_to_all_right(inp, out):
    return _sim(inp, chain="all", pusher=None)


def pusher_most_common(inp, out):
    return _sim(inp, pusher=_common_color(inp))


def pusher_last_bar_color(inp, out):
    return _sim(inp, pusher=_rightmost_color(inp))


def fall_left(inp, out):
    return _sim(inp, sign=-1)


def fall_offset_one(inp, out):
    return _sim(inp, offset=1)


def fall_short(inp, out):
    return _sim(inp, dlen=-1)


def fall_recolor(inp, out):
    return _sim(inp, recolor=True)


def bar_left_standing(inp, out):
    return _sim(inp, clear=False)


def lands_on_top_row(inp, out):
    return _sim(inp, row="top")


def bars_vanish(inp, out):
    return _sim(inp, paint=False)


ALTERNATIVES = [
    ("only the rarest-color bars topple; a touched bar stays standing", no_chain),
    ("a touched bar topples, but the toppling stops after one step", chain_one_step),
    ("every bar right of a toppled bar topples, touched or not", chain_to_all_right),
    ("the most common bar color topples instead of the rarest", pusher_most_common),
    ("the color of the rightmost bar is the one that topples", pusher_last_bar_color),
    ("bars topple to the left instead of the right", fall_left),
    ("a toppled bar lands one cell too far right", fall_offset_one),
    ("a toppled bar lands one cell shorter than its height", fall_short),
    ("every landed bar takes the color of the rarest color", fall_recolor),
    ("a toppled bar leaves its standing cells in place", bar_left_standing),
    ("a toppled bar lands in its top row, not the bottom row", lands_on_top_row),
    ("a toppled bar is erased and nothing lands", bars_vanish),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/84551f4c.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
