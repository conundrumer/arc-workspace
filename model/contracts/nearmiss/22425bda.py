import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _ink(inp):
    bg = _bg(inp)
    return [v for r in inp for v in r if v != bg]


def _skip_same(fn):
    def wrapped(inp, out):
        g = fn(inp, out)
        return None if g == out else g
    wrapped.__name__ = fn.__name__
    return wrapped


def _row(out):
    return list(out[0])


def reversed_stack(inp, out):
    return [_row(out)[::-1]]


def column_instead_of_row(inp, out):
    return [[v] for v in _row(out)]


def drop_bottom(inp, out):
    return [_row(out)[1:]]


def drop_top(inp, out):
    return [_row(out)[:-1]]


def sorted_by_value_desc(inp, out):
    return [sorted(_row(out), reverse=True)]


def by_visible_count_asc(inp, out):
    c = Counter(_ink(inp))
    return [sorted(_row(out), key=lambda k: (c[k], k))]


def by_visible_count_desc(inp, out):
    c = Counter(_ink(inp))
    return [sorted(_row(out), key=lambda k: (-c[k], k))]


def by_first_seen_reading_order(inp, out):
    seen = []
    for v in _ink(inp):
        if v not in seen:
            seen.append(v)
    return [seen]


def by_first_seen_column_major(inp, out):
    bg = _bg(inp)
    seen = []
    for x in range(len(inp[0])):
        for y in range(len(inp)):
            v = inp[y][x]
            if v != bg and v not in seen:
                seen.append(v)
    return [seen]


def swap_top_two(inp, out):
    r = _row(out)
    r[-1], r[-2] = r[-2], r[-1]
    return [r]


def top_moved_to_bottom(inp, out):
    r = _row(out)
    return [[r[-1]] + r[:-1]]


def background_included(inp, out):
    return [[_bg(inp)] + _row(out)]


_RAW = [
    ("stack listed top first instead of bottom first", reversed_stack),
    ("stack written as a column instead of a row", column_instead_of_row),
    ("bottom color of the stack left out", drop_bottom),
    ("top color of the stack left out", drop_top),
    ("colors ordered by color value, largest first", sorted_by_value_desc),
    ("colors ordered by visible cell count, fewest first", by_visible_count_asc),
    ("colors ordered by visible cell count, most first", by_visible_count_desc),
    ("colors ordered by first appearance in row-major scan", by_first_seen_reading_order),
    ("colors ordered by first appearance in column-major scan", by_first_seen_column_major),
    ("top two colors swapped", swap_top_two),
    ("top color placed at the bottom, others keep order", top_moved_to_bottom),
    ("background color counted as the bottom layer", background_included),
]


ALTERNATIVES = [(d, _skip_same(f)) for d, f in _RAW]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/22425bda.json").read_text())
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
