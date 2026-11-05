import json
from collections import Counter
from pathlib import Path

W = 6


def _bg(g):
    return Counter(c for r in g for c in r).most_common(1)[0][0]


def _tiles(out):
    return [[row[:] for row in out[i:i + W]] for i in range(0, len(out), W)]


def _stack(tiles):
    return [row[:] for t in tiles for row in t]


def _fig(tile, bg):
    for r in tile:
        for c in r:
            if c != bg:
                return c
    return bg


def reversed_stack(inp, out):
    return _stack(_tiles(out)[::-1])


def rotated_stack(inp, out):
    t = _tiles(out)
    return _stack(t[1:] + t[:1])


def swap_first_two(inp, out):
    t = _tiles(out)
    t[0], t[1] = t[1], t[0]
    return _stack(t)


def side_by_side(inp, out):
    t = _tiles(out)
    return [sum((tt[i] for tt in t), []) for i in range(W)]


def drop_last(inp, out):
    return _stack(_tiles(out)[:-1])


def front_only(inp, out):
    return _tiles(out)[0]


def with_noise_tile(inp, out):
    bg = _bg(out)
    t = _tiles(out)
    used = {_fig(x, bg) for x in t}
    cnt = Counter(c for r in inp for c in r)
    noise = [c for c in cnt if c != bg and c not in used]
    if not noise:
        return None
    n = min(noise, key=lambda c: cnt[c])
    extra = [[n if c != bg else bg for c in r] for r in t[-1]]
    return _stack(t + [extra])


def inverted_tiles(inp, out):
    bg = _bg(out)
    res = []
    for tile in _tiles(out):
        f = _fig(tile, bg)
        res.append([[bg if c == f else f for c in r] for r in tile])
    return _stack(res)


def solid_tiles(inp, out):
    bg = _bg(out)
    return _stack([[[_fig(tile, bg)] * W for _ in range(W)] for tile in _tiles(out)])


def shifted_shape(inp, out):
    return [r[1:] + r[:1] for r in out]


def short_tiles(inp, out):
    return _stack([tile[:-1] for tile in _tiles(out)])


ALTERNATIVES = [
    ("stack order reversed: backmost figure first", reversed_stack),
    ("stack order cycled: frontmost figure moved to the end", rotated_stack),
    ("front two figures swapped, so the wrong one is judged in front", swap_first_two),
    ("tiles laid side by side instead of stacked", side_by_side),
    ("backmost figure left out of the stack", drop_last),
    ("only the frontmost figure is output", front_only),
    ("a stray input color is taken as one more figure and stacked last", with_noise_tile),
    ("tile colors swapped: figure cells carry the ground color and the reverse", inverted_tiles),
    ("each tile filled solid with the figure color instead of its shape", solid_tiles),
    ("shape shifted one column inside each tile", shifted_shape),
    ("each tile cropped one row short", short_tiles),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/652646ff.json'))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(train), desc)
