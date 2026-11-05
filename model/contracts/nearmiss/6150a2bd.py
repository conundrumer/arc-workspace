import json
from collections import Counter
from pathlib import Path


def rot180(g):
    return [r[::-1] for r in g[::-1]]


def transpose(g):
    return [list(r) for r in zip(*g)]


def rot_cw(g):
    return [list(r) for r in zip(*g[::-1])]


def rot_ccw(g):
    return [list(r) for r in zip(*g)][::-1]


def anti_transpose(g):
    return rot180(transpose(g))


def flip_h(g):
    return [r[::-1] for r in g]


def flip_v(g):
    return g[::-1]


def copy(g):
    return [list(r) for r in g]


def rot180_crop_last(inp, out):
    # off-by-one crop: rotate only the grid without its last row and column
    return rot180([r[:-1] for r in inp[:-1]])


def rot180_keep_top_row(inp, out):
    # rotate the lower rows only; the top row stays in place
    return [list(inp[0])] + rot180(inp[1:])


def rot180_drop_commonest(inp, out):
    # rotate, then erase the most frequent non-zero color
    c = Counter(v for r in out for v in r if v)
    if not c:
        return None
    top = c.most_common(1)[0][0]
    return [[0 if v == top else v for v in r] for r in out]


def rot180_center_row_unmoved(inp, out):
    # rotate 180, but the middle row is left as in the input
    g = copy(out)
    m = len(g) // 2
    g[m] = list(inp[m])
    return g


ALTERNATIVES = [
    ("rotate 90 degrees clockwise instead of 180", lambda i, o: rot_cw(i)),
    ("rotate 90 degrees counterclockwise instead of 180", lambda i, o: rot_ccw(i)),
    ("transpose across the main diagonal", lambda i, o: transpose(i)),
    ("transpose across the anti-diagonal", lambda i, o: anti_transpose(i)),
    ("mirror left-right only", lambda i, o: flip_h(i)),
    ("mirror top-bottom only", lambda i, o: flip_v(i)),
    ("return the input unchanged", lambda i, o: copy(i)),
    ("rotate 180 but crop off the last row and column first", rot180_crop_last),
    ("rotate 180 only the rows below the top row", rot180_keep_top_row),
    ("rotate 180 then erase the most frequent non-zero color", rot180_drop_commonest),
    ("rotate 180 but leave the middle row as in the input", rot180_center_row_unmoved),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/6150a2bd.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
