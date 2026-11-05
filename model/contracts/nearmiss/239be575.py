import json
from pathlib import Path

ORTH = [(1, 0), (-1, 0), (0, 1), (0, -1)]
EIGHT = ORTH + [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def _components(inp, colors, steps):
    h, w = len(inp), len(inp[0])
    comp = {}
    n = 0
    for r in range(h):
        for c in range(w):
            if inp[r][c] in colors and (r, c) not in comp:
                stack = [(r, c)]
                comp[(r, c)] = n
                while stack:
                    y, x = stack.pop()
                    for dy, dx in steps:
                        a, b = y + dy, x + dx
                        if 0 <= a < h and 0 <= b < w and inp[a][b] in colors and (a, b) not in comp:
                            comp[(a, b)] = n
                            stack.append((a, b))
                n += 1
    return comp


def _joined(inp, colors, steps):
    comp = _components(inp, colors, steps)
    ids = {comp[(r, c)] for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] == 2}
    return len(ids) <= 1


def _verdict(joined):
    return [[8 if joined else 0]]


def _differ(g, out):
    return None if g == out else g


def flipped(inp, out):
    return [[8 if out[0][0] == 0 else 0]]


def mark_color(inp, out):
    return [[2]]


def big_eight_blob(inp, out):
    comp = _components(inp, {8}, ORTH)
    sizes = {}
    for k in comp.values():
        sizes[k] = sizes.get(k, 0) + 1
    return _differ(_verdict(max(sizes.values(), default=0) >= 4), out)


def always_joined(inp, out):
    return _differ([[8]], out)


def always_apart(inp, out):
    return _differ([[0]], out)


def any_touch(inp, out):
    h, w = len(inp), len(inp[0])
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 8:
                for dy, dx in ORTH:
                    a, b = r + dy, c + dx
                    if 0 <= a < h and 0 <= b < w and inp[a][b] == 2:
                        return _differ([[8]], out)
    return _differ([[0]], out)


def through_any_color(inp, out):
    return _differ(_verdict(_joined(inp, {0, 2, 8}, ORTH)), out)


def input_size(inp, out):
    return [[out[0][0]] * len(inp[0]) for _ in inp]


def two_by_two(inp, out):
    return [[out[0][0]] * 2 for _ in range(2)]


def unchanged(inp, out):
    return [row[:] for row in inp]


def many_eights(inp, out):
    return _differ(_verdict(sum(row.count(8) for row in inp) >= 10), out)


def eight_count_majority(inp, out):
    n8 = sum(row.count(8) for row in inp)
    n0 = sum(row.count(0) for row in inp)
    return _differ([[8 if n8 >= n0 else 0]], out)


ALTERNATIVES = [
    ("verdict inverted: 8 when the blocks are apart, 0 when joined", flipped),
    ("output painted with the block color 2", mark_color),
    ("blocks judged joined when some orthogonal blob of 8 cells has at least 4 cells", big_eight_blob),
    ("blocks always judged joined", always_joined),
    ("blocks always judged apart", always_apart),
    ("blocks joined if any 8 cell touches a block", any_touch),
    ("path may run through any cell, 0 included", through_any_color),
    ("correct verdict painted over the full input size", input_size),
    ("correct verdict painted as a 2x2 grid", two_by_two),
    ("output is the input unchanged", unchanged),
    ("blocks judged joined when the grid has at least 10 cells of 8", many_eights),
    ("verdict is 8 when 8 cells outnumber 0 cells", eight_count_majority),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/239be575.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
