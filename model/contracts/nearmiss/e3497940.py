"""Near-miss rules for ARC task e3497940."""
import json
from collections import Counter
from pathlib import Path


def _halves(inp):
    w = len(inp[0])
    s = w // 2
    left = [r[:s] for r in inp]
    right = [r[s + 1:] for r in inp]
    return left, right


def _overlay(base, other):
    return [[b if b else o for b, o in zip(rb, ro)] for rb, ro in zip(base, other)]


def _hflip(g):
    return [r[::-1] for r in g]


def _vflip(g):
    return [r[:] for r in g[::-1]]


def no_mirror(inp, out):
    left, right = _halves(inp)
    return _overlay(left, right)


def left_only(inp, out):
    return _halves(inp)[0]


def right_only_mirrored(inp, out):
    return _hflip(_halves(inp)[1])


def right_unmirrored_only(inp, out):
    return _halves(inp)[1]


def vertical_flip_instead(inp, out):
    left, right = _halves(inp)
    return _overlay(left, _vflip(right))


def rotate_180(inp, out):
    left, right = _halves(inp)
    return _overlay(left, _vflip(_hflip(right)))


def mirror_off_by_one(inp, out):
    left, right = _halves(inp)
    g = [r[:] for r in left]
    w = len(left[0])
    for i, row in enumerate(right):
        for j, v in enumerate(row):
            k = w - 2 - j
            if v and 0 <= k < w and not g[i][k]:
                g[i][k] = v
    return g


def single_color(inp, out):
    c = Counter(v for r in out for v in r if v)
    main = c.most_common(1)[0][0]
    return [[main if v else 0 for v in r] for r in out]


def overlap_cancels(inp, out):
    left, right = _halves(inp)
    rf = _hflip(right)
    return [[(a or b) if not (a and b) else 0 for a, b in zip(ra, rb)]
            for ra, rb in zip(left, rf)]


def output_flipped_horizontally(inp, out):
    return _hflip(out)


def output_flipped_vertically(inp, out):
    return _vflip(out)


def include_separator_column(inp, out):
    w = len(inp[0]) // 2
    return [r + [inp[i][w]] for i, r in enumerate(out)]


def right_priority_recolor(inp, out):
    """Right-half ink takes the separator color where it lands."""
    left, right = _halves(inp)
    sep = inp[0][len(inp[0]) // 2]
    rf = _hflip(right)
    return [[sep if b else a for a, b in zip(ra, rb)] for ra, rb in zip(left, rf)]


ALTERNATIVES = [
    ("right half overlaid without mirroring it", no_mirror),
    ("only the left half is kept", left_only),
    ("only the mirrored right half is kept", right_only_mirrored),
    ("right half flipped top to bottom instead of left to right", vertical_flip_instead),
    ("mirror axis off by one column", mirror_off_by_one),
    ("all ink painted in the most common ink color", single_color),
    ("cells inked on both sides are erased", overlap_cancels),
    ("correct overlay flipped left to right", output_flipped_horizontally),
    ("correct overlay flipped top to bottom", output_flipped_vertically),
    ("separator column kept in the output", include_separator_column),
    ("mirrored right-half ink painted in the separator color", right_priority_recolor),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/e3497940.json'))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
