from pathlib import Path
import json

FULL = {3: 4, 4: 3, 1: 5, 5: 1, 2: 6, 6: 2, 8: 9, 9: 8}


def remap(inp, m, cols=None, rows=None):
    return [[m.get(v, v) if (cols is None or j in cols) and (rows is None or i in rows) else v
             for j, v in enumerate(r)] for i, r in enumerate(inp)]


def only_forward(inp, out):
    return remap(inp, {3: 4, 1: 5, 2: 6, 8: 9})


def only_backward(inp, out):
    return remap(inp, {4: 3, 5: 1, 6: 2, 9: 8})


def only_3_4(inp, out):
    return remap(inp, {3: 4, 4: 3})


def miss_8_9(inp, out):
    return remap(inp, {k: v for k, v in FULL.items() if k not in (8, 9)})


def first_column_only(inp, out):
    return remap(inp, FULL, cols={0})


def first_row_only(inp, out):
    return remap(inp, FULL, rows={0})


def wrong_pairing(inp, out):
    m = dict(FULL)
    m.update({1: 6, 6: 1, 2: 5, 5: 2})
    return remap(inp, m)


def cyclic_plus_one(inp, out):
    return [[v % 9 + 1 for v in r] for r in inp]


def mirrored(inp, out):
    return [r[::-1] for r in out]


def drop_last_column(inp, out):
    return [r[:-1] for r in out]


def middle_left_unchanged(inp, out):
    return [[v if j == 1 else out[i][j] for j, v in enumerate(r)] for i, r in enumerate(inp)]


def constant_color(inp, out):
    return [[out[0][0]] * len(r) for r in out]


ALTERNATIVES = [
    ("swap applied one way only (3->4, 1->5, 2->6, 8->9), reverse direction missed", only_forward),
    ("swap applied one way only (4->3, 5->1, 6->2, 9->8), forward direction missed", only_backward),
    ("only the 3/4 pair is swapped", only_3_4),
    ("the 8/9 pair is missed", miss_8_9),
    ("swap applied to the first column only", first_column_only),
    ("swap applied to the first row only", first_row_only),
    ("1 and 2 paired with the wrong partners (1<->6, 2<->5)", wrong_pairing),
    ("each color replaced by the next color, 9 wrapping to 1", cyclic_plus_one),
    ("correct colors but columns mirrored", mirrored),
    ("correct output with the last column dropped", drop_last_column),
    ("middle column left as in the input", middle_left_unchanged),
    ("whole grid filled with the first output color", constant_color),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/0d3d703e.json')))
    pairs = t["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
