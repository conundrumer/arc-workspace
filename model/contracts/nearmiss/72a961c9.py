"""Near-miss readings for task 72a961c9.

Rule: a full row of one color (the line) holds a few cells of other colors
(marks). Each mark grows a ray upward from the line. Color 2 reaches 4 cells
above the line, color 8 reaches 3. The top cell has the mark's color; the
cells below it have the line's color.
"""
import json
from collections import Counter
from pathlib import Path

TRUE_LEN = {2: 4, 8: 3}


def _line_row(g):
    best = max(range(len(g)), key=lambda r: sum(1 for v in g[r] if v))
    return best


def _marks(g):
    r = _line_row(g)
    lc = Counter(g[r]).most_common(1)[0][0]
    return r, lc, [(c, v) for c, v in enumerate(g[r]) if v != lc]


def _draw(inp, length, direction=-1, tip=True, body=None, both=False, only_first=False,
          clear_marks=False):
    g = [row[:] for row in inp]
    r, lc, marks = _marks(inp)
    if only_first:
        marks = marks[:1]
    dirs = [-1, 1] if both else [direction]
    for c, v in marks:
        n = length(v, inp, r)
        if clear_marks:
            g[r][c] = lc
        for d in dirs:
            for k in range(1, n + 1):
                rr = r + d * k
                if not (0 <= rr < len(g)):
                    break
                last = k == n
                if last and tip:
                    g[rr][c] = v
                else:
                    g[rr][c] = lc if body is None else v
    return g


def _ok(f):
    def w(inp, out):
        g = f(inp, out)
        return g
    return w


def down(inp, out):
    return _draw(inp, lambda v, i, r: TRUE_LEN[v], direction=1)


def both_dirs(inp, out):
    return _draw(inp, lambda v, i, r: TRUE_LEN[v], both=True)


def all_three(inp, out):
    return _draw(inp, lambda v, i, r: 3)


def all_four(inp, out):
    return _draw(inp, lambda v, i, r: 4)


def swapped(inp, out):
    return _draw(inp, lambda v, i, r: {2: 3, 8: 4}[v])


def to_edge(inp, out):
    return _draw(inp, lambda v, i, r: r)


def body_in_mark_color(inp, out):
    return _draw(inp, lambda v, i, r: TRUE_LEN[v], body=True)


def no_tip(inp, out):
    return _draw(inp, lambda v, i, r: TRUE_LEN[v], tip=False)


def marks_erased(inp, out):
    return _draw(inp, lambda v, i, r: TRUE_LEN[v], clear_marks=True)


def first_mark_only(inp, out):
    return _draw(inp, lambda v, i, r: TRUE_LEN[v], only_first=True)


def one_short(inp, out):
    return _draw(inp, lambda v, i, r: TRUE_LEN[v] - 1)


def one_long(inp, out):
    return _draw(inp, lambda v, i, r: TRUE_LEN[v] + 1)


def transposed_out(inp, out):
    return [list(col) for col in zip(*out)]


ALTERNATIVES = [
    ("rays grow downward from the line instead of upward", down),
    ("rays grow in both directions from the line", both_dirs),
    ("every ray has length 3 regardless of color", all_three),
    ("every ray has length 4 regardless of color", all_four),
    ("ray lengths swapped between colors (2 gets 3, 8 gets 4)", swapped),
    ("rays run to the grid edge", to_edge),
    ("ray body takes the mark color instead of the line color", body_in_mark_color),
    ("ray tip has the line color, not the mark color", no_tip),
    ("marks on the line are replaced by the line color", marks_erased),
    ("only the leftmost mark grows a ray", first_mark_only),
    ("each ray is one cell too short", one_short),
    ("each ray is one cell too long", one_long),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/72a961c9.json").read_text())
    train = task["train"]
    print("pairs", len(train))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
