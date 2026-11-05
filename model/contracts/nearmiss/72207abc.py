import json
from pathlib import Path


def _seeds(inp):
    """Row index of the seed row and the list of (col, color) seeds."""
    for r, row in enumerate(inp):
        s = [(c, v) for c, v in enumerate(row) if v != 0]
        if s:
            return r, s
    return None, []


def _walk(inp, gap0=None, step=1, order=None, start=None, maxn=None, colors=None, full=False):
    r, s = _seeds(inp)
    if r is None:
        return None
    k = len(s)
    w = len(inp[0])
    cols = [v for _, v in s]
    if order == "reverse":
        cols = cols[::-1]
    if colors is not None:
        cols = colors(cols)
    g = [row[:] for row in inp]
    pos = s[-1][0] if start is None else start
    gap = k if gap0 is None else gap0
    i = 0
    n = 0
    while True:
        pos += gap
        if pos >= w or (maxn is not None and n >= maxn):
            break
        if full:
            for rr in range(len(g)):
                g[rr][pos] = cols[i % len(cols)]
        else:
            g[r][pos] = cols[i % len(cols)]
        i += 1
        n += 1
        gap += step
    return g


def constant_gap(inp, out):
    return _walk(inp, step=0)


def gap_one_too_big(inp, out):
    r, s = _seeds(inp)
    return _walk(inp, gap0=len(s) + 1)


def gap_one_too_small(inp, out):
    r, s = _seeds(inp)
    return _walk(inp, gap0=len(s) - 1)


def step_two(inp, out):
    return _walk(inp, step=2)


def reversed_colors(inp, out):
    return _walk(inp, order="reverse")


def first_color_only(inp, out):
    return _walk(inp, colors=lambda c: [c[0]])


def shifted_colors(inp, out):
    return _walk(inp, colors=lambda c: c[1:] + c[:1])


def from_first_seed(inp, out):
    r, s = _seeds(inp)
    return _walk(inp, start=s[0][0])


def one_mark_short(inp, out):
    g = _walk(inp)
    full = _walk(inp, maxn=None)
    r, s = _seeds(inp)
    marks = [c for c in range(s[-1][0] + 1, len(inp[0])) if out[r][c] != 0 and c > s[-1][0]]
    if not marks:
        return None
    g = [row[:] for row in out]
    g[r][marks[-1]] = 0
    return g


def first_mark_only(inp, out):
    return _walk(inp, maxn=1)


def full_column_stripes(inp, out):
    return _walk(inp, full=True)


def seeds_dropped(inp, out):
    r, s = _seeds(inp)
    g = [row[:] for row in out]
    for c, _ in s:
        g[r][c] = 0
    return g


ALTERNATIVES = [
    ("gap between marks stays constant at the seed count instead of growing", constant_gap),
    ("first gap is one larger than the seed count", gap_one_too_big),
    ("first gap is one smaller than the seed count", gap_one_too_small),
    ("gap grows by two each step instead of one", step_two),
    ("mark colors cycle through the seeds in reverse order", reversed_colors),
    ("every mark takes the color of the first seed", first_color_only),
    ("mark colors cycle starting from the second seed", shifted_colors),
    ("walk starts from the first seed instead of the last seed", from_first_seed),
    ("walk stops one mark early", one_mark_short),
    ("only the first mark after the seeds is drawn", first_mark_only),
    ("each mark fills its whole column instead of one cell", full_column_stripes),
    ("seed cells are erased from the output", seeds_dropped),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/72207abc.json").read_text())
    pairs = task["train"]
    # sanity: the generator reproduces the true output
    for p in pairs:
        assert _walk(p["input"]) == p["output"], "generator does not match truth"
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
