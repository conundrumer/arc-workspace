import json
from collections import Counter
from pathlib import Path

ROWS = [(1, 4), (5, 8)]
COLS = [(1, 3), (4, 6), (7, 9)]


def blocks(inp):
    return [[[inp[r][c] for r in range(r0, r1) for c in range(c0, c1)]
             for (c0, c1) in COLS] for (r0, r1) in ROWS]


def ranked(cells):
    cnt = Counter(cells)
    return sorted(cnt, key=lambda k: (-cnt[k], k))


def framed(inner, ring=1):
    w = len(inner[0]) + 2 * ring
    z = [0] * w
    return ([z[:] for _ in range(ring)]
            + [[0] * ring + list(r) + [0] * ring for r in inner]
            + [z[:] for _ in range(ring)])


def inner_of(out):
    return [row[1:-1] for row in out[1:-1]]


def build(inp, pick):
    return framed([[pick(b) for b in row] for row in blocks(inp)])


def least_common(inp, out):
    return build(inp, lambda b: ranked(b)[-1])


def second_common(inp, out):
    return build(inp, lambda b: ranked(b)[1] if len(ranked(b)) > 1 else ranked(b)[0])


def top_left(inp, out):
    return build(inp, lambda b: b[3])


def bottom_right(inp, out):
    return build(inp, lambda b: b[-1])


def no_border(inp, out):
    return inner_of(out)


def extra_ring(inp, out):
    return framed(out, 1)


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def mirror_h(inp, out):
    return [r[::-1] for r in out]


def mirror_v(inp, out):
    return out[::-1]


def band_mode(inp, out):
    bl = blocks(inp)
    res = []
    for row in bl:
        col = ranked([x for b in row for x in b])[0]
        res.append([col] * len(row))
    return framed(res)


def global_mode(inp, out):
    col = ranked([x for r in inp for x in r if x != 0])[0]
    return framed([[col] * 3 for _ in range(2)])


ALTERNATIVES = [
    ("each block takes its least common color", least_common),
    ("each block takes its second most common color", second_common),
    ("each block takes its middle-row left cell", top_left),
    ("each block takes its last cell in reading order", bottom_right),
    ("output has no bg border", no_border),
    ("output border is two cells wide", extra_ring),
    ("output is transposed (block rows and columns swapped)", transposed),
    ("output is mirrored left to right", mirror_h),
    ("output is mirrored top to bottom", mirror_v),
    ("each output cell takes the commonest color of its whole block row", band_mode),
    ("every output cell takes the commonest non-bg color of the whole input", global_mode),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/af24b4cc.json'))
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
