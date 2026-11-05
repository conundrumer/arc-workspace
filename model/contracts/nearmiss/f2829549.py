import json
from pathlib import Path


def _halves(inp):
    left = [r[:3] for r in inp]
    right = [r[4:] for r in inp]
    return left, right


def _combine(inp, f, color=3):
    left, right = _halves(inp)
    return [[color if f(a != 0, b != 0) else 0 for a, b in zip(l, r)] for l, r in zip(left, right)]


def xor_rule(inp, out):
    return _combine(inp, lambda a, b: a != b)


def and_rule(inp, out):
    return _combine(inp, lambda a, b: a and b)


def or_rule(inp, out):
    return _combine(inp, lambda a, b: a or b)


def nand_rule(inp, out):
    return _combine(inp, lambda a, b: not (a and b))


def left_only(inp, out):
    return _combine(inp, lambda a, b: not a)


def right_only(inp, out):
    return _combine(inp, lambda a, b: not b)


def wrong_color(inp, out):
    return [[2 if c == 3 else c for c in r] for r in out]


def mirrored_right(inp, out):
    left, right = _halves(inp)
    right = [r[::-1] for r in right]
    return [[3 if a == 0 and b == 0 else 0 for a, b in zip(l, r)] for l, r in zip(left, right)]


def flipped_vertical(inp, out):
    return out[::-1]


def shifted_right(inp, out):
    left, right = _halves(inp)
    right = [[0] + r[:-1] for r in right]
    return [[3 if a == 0 and b == 0 else 0 for a, b in zip(l, r)] for l, r in zip(left, right)]


def include_separator(inp, out):
    # treat the separator column as part of the left panel: 4 wide output
    right = [r[4:] for r in inp]
    left = [r[:4] for r in inp]
    return [[3 if l[i] == 0 and (r[i - 1] == 0 if i > 0 else True) else 0 for i in range(4)]
            for l, r in zip(left, right)]


def filled_marked(inp, out):
    # marks cells covered in either panel, copying the input colors
    left, right = _halves(inp)
    return [[a or b for a, b in zip(l, r)] for l, r in zip(left, right)]


ALTERNATIVES = [
    ("3 where exactly one panel is filled (XOR)", xor_rule),
    ("3 where both panels are filled (AND)", and_rule),
    ("3 where either panel is filled (OR)", or_rule),
    ("3 unless both panels are filled (NAND)", nand_rule),
    ("3 where the left panel is empty, right panel ignored", left_only),
    ("3 where the right panel is empty, left panel ignored", right_only),
    ("correct cells but color 2 instead of 3", wrong_color),
    ("right panel mirrored left-right before the NOR", mirrored_right),
    ("true output flipped upside down", flipped_vertical),
    ("right panel shifted one column before the NOR", shifted_right),
    ("separator column included in the left panel, 4-wide output", include_separator),
    ("overlay of both panels' input colors", filled_marked),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/f2829549.json'))
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
