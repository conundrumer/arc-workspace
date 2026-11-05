import json
from pathlib import Path


def _panels(inp):
    w = len(inp[0]) // 2
    left = [r[:w] for r in inp]
    right = [r[w:] for r in inp]
    return left, right


def _combine(inp, f, color=5, flip_right=None):
    left, right = _panels(inp)
    if flip_right == "h":
        right = [r[::-1] for r in right]
    elif flip_right == "v":
        right = right[::-1]
    return [[color if f(a != 0, b != 0) else 0 for a, b in zip(rl, rr)]
            for rl, rr in zip(left, right)]


def xor_panels(inp, out):
    return _combine(inp, lambda a, b: a != b)


def and_panels(inp, out):
    return _combine(inp, lambda a, b: a and b)


def or_panels(inp, out):
    return _combine(inp, lambda a, b: a or b)


def left_only(inp, out):
    return _combine(inp, lambda a, b: not a)


def right_only(inp, out):
    return _combine(inp, lambda a, b: not b)


def wrong_color(inp, out):
    return [[3 if v == 5 else v for v in r] for r in out]


def flip_right_h(inp, out):
    return _combine(inp, lambda a, b: not (a or b), flip_right="h")


def flip_right_v(inp, out):
    return _combine(inp, lambda a, b: not (a or b), flip_right="v")


def shifted_cols(inp, out):
    return [r[-1:] + r[:-1] for r in out]


def full_width_background(inp, out):
    return [[5 if v == 0 else 0 for v in r] for r in inp]


def transposed(inp, out):
    return [list(c) for c in zip(*out)]


def left_half_only_crop(inp, out):
    w = len(inp[0]) // 2 - 1
    left, right = _panels(inp)
    return [[5 if (a == 0 and b == 0) else 0 for a, b in zip(rl[:w], rr[:w])]
            for rl, rr in zip(left, right)]


ALTERNATIVES = [
    ("5 where exactly one panel is filled (XOR) instead of neither", xor_panels),
    ("5 where both panels are filled (AND)", and_panels),
    ("5 where either panel is filled (OR), the inverse of the true output", or_panels),
    ("only the left (3) panel is considered when finding empty cells", left_only),
    ("only the right (2) panel is considered when finding empty cells", right_only),
    ("empty cells painted 3 instead of 5", wrong_color),
    ("right panel mirrored left-right before overlay", flip_right_h),
    ("right panel mirrored top-bottom before overlay", flip_right_v),
    ("true output shifted one column right with wraparound", shifted_cols),
    ("full-width 4x14 grid with 5 on every input background cell", full_width_background),
    ("true output transposed", transposed),
    ("overlay computed with panels cropped one column short", left_half_only_crop),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/66f2d22f.json").read_text())
    pairs = task["train"]

    def valid(g, out):
        return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
                and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
                and g != out)

    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
