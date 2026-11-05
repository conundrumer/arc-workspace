import json
from collections import Counter
from pathlib import Path


def _mains(rows, shared_ok=False):
    """Main color of each line: most frequent nonzero color not found in another line."""
    res = []
    for i, r in enumerate(rows):
        others = set()
        for j, s in enumerate(rows):
            if j != i:
                others |= set(s)
        c = Counter(v for v in r if v != 0 and (shared_ok or v not in others))
        if not c:
            c = Counter(v for v in r if v != 0)
        res.append(c.most_common(1)[0][0] if c else 0)
    return res


def _swap(row, m):
    return [0 if v == m else m for v in row]


def _transpose(g):
    return [list(c) for c in zip(*g)]


def keep_main(inp, out):
    # main cells stay main; everything else becomes main (no swap with background)
    ms = _mains(inp)
    return [[m for _ in r] for r, m in zip(inp, ms)]


def clear_main_only(inp, out):
    # main cells cleared, nothing filled
    ms = _mains(inp)
    return [[0 if v == m else v for v in r] for r, m in zip(inp, ms)]


def columns_as_lines(inp, out):
    t = _transpose(inp)
    ms = _mains(t)
    return _transpose([_swap(r, m) for r, m in zip(t, ms)])


def shared_as_main(inp, out):
    # a color that also appears in another line is taken as the line's main color
    ms = _mains(inp)
    res = []
    for i, (r, m) in enumerate(zip(inp, ms)):
        others = set()
        for j, s in enumerate(inp):
            if j != i:
                others |= set(s)
        sh = [v for v in r if v != 0 and v in others and v != m]
        res.append(_swap(r, Counter(sh).most_common(1)[0][0]) if sh else _swap(r, m))
    return res


def rarest_color(inp, out):
    ms = []
    for r in inp:
        c = Counter(v for v in r if v != 0)
        ms.append(min(c, key=lambda k: (c[k], k)) if c else 0)
    return [_swap(r, m) for r, m in zip(inp, ms)]


def noise_to_bg(inp, out):
    # other colors become background instead of main color
    ms = _mains(inp)
    return [[m if v == 0 else 0 for v in r] for r, m in zip(inp, ms)]


def noise_kept(inp, out):
    # other-color cells are left as in the input
    ms = _mains(inp)
    return [[0 if v == m else (m if v == 0 else v) for v in r] for r, m in zip(inp, ms)]


def shifted_right(inp, out):
    return [r[-1:] + r[:-1] for r in out]


def mirrored(inp, out):
    return [r[::-1] for r in out]


def rows_reversed(inp, out):
    return [list(r) for r in out[::-1]]


def global_main(inp, out):
    # one main color for the whole grid
    c = Counter(v for r in inp for v in r if v != 0)
    m = c.most_common(1)[0][0]
    return [_swap(r, m) for r in inp]


def first_line_only(inp, out):
    # rule applied to the first line only; other lines unchanged
    ms = _mains(inp)
    return [_swap(inp[0], ms[0])] + [list(r) for r in inp[1:]]


ALTERNATIVES = [
    ("main cells stay main, all other cells become main (no swap with background)", keep_main),
    ("main cells cleared, background and other colors left unchanged", clear_main_only),
    ("lines taken as columns instead of rows", columns_as_lines),
    ("a color shared with other lines is taken as the line's main color", shared_as_main),
    ("main color is the rarest nonzero color of the line", rarest_color),
    ("other-color cells become background instead of main color", noise_to_bg),
    ("other-color cells keep their input color", noise_kept),
    ("true output with each line shifted one cell right (off-by-one offset)", shifted_right),
    ("true output mirrored left to right", mirrored),
    ("true output with line order reversed (colors on wrong lines)", rows_reversed),
    ("one main color for the whole grid", global_main),
    ("rule applied to the first line only", first_line_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/2de01db2.json'))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
