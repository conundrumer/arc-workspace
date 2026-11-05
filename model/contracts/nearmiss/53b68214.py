import json
from pathlib import Path


def _period(inp):
    n = len(inp)
    for p in range(1, n + 1):
        if all(inp[i] == inp[i - p] for i in range(p, n)):
            return p
    return n


def _grow(inp, n, phase=0):
    p = _period(inp)
    rows = [list(r) for r in inp]
    while len(rows) < n:
        rows.append(list(inp[(len(rows) - phase) % p]))
    return rows[:n]


def _zeros(h, w):
    return [[0] * w for _ in range(h)]


def unchanged(inp, out):
    return [list(r) for r in inp]


def zero_pad_below(inp, out):
    w = len(inp[0])
    return [list(r) for r in inp] + _zeros(len(out) - len(inp), w)


def zero_pad_above(inp, out):
    w = len(inp[0])
    return _zeros(len(out) - len(inp), w) + [list(r) for r in inp]


def one_row_short(inp, out):
    return [list(r) for r in out[:-1]]


def one_row_long(inp, out):
    return _grow(inp, len(out) + 1)


def tile_whole_input(inp, out):
    n = len(inp)
    return [list(inp[i % n]) for i in range(len(out))]


def mirror_extension(inp, out):
    rows = [list(r) for r in inp]
    k = 0
    while len(rows) < len(out):
        rows.append(list(inp[len(inp) - 1 - k]))
        k += 1
    return rows


def phase_shifted(inp, out):
    return _grow(inp, len(out), phase=1)


def extension_recolored(inp, out):
    res = [list(r) for r in out]
    for i in range(len(inp), len(res)):
        res[i] = [5 if v else 0 for v in res[i]]
    return res


def transposed(inp, out):
    return [list(c) for c in zip(*out)]


def new_rows_only(inp, out):
    return [list(r) for r in out[len(inp):]]


ALTERNATIVES = [
    ("output is the input unchanged, nothing grown", unchanged),
    ("input kept at the top, grown rows left empty", zero_pad_below),
    ("input kept at the bottom, empty rows above, pattern not continued", zero_pad_above),
    ("pattern continued one row too short (9 rows)", one_row_short),
    ("pattern continued one row too long (11 rows)", one_row_long),
    ("whole input block tiled as the period instead of the fundamental period", tile_whole_input),
    ("grown rows mirror the input end instead of continuing the period", mirror_extension),
    ("pattern continued with its phase off by one", phase_shifted),
    ("grown rows drawn in color 5 instead of the pattern color", extension_recolored),
    ("pattern grown along the other axis (transposed result)", transposed),
    ("output holds only the newly grown rows", new_rows_only),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/53b68214.json"))
    train = task["train"]
    print("pairs", len(train))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for pr in train:
            g = fn(pr["input"], pr["output"])
            if g is None:
                continue
            good = (
                isinstance(g, list) and len(g) > 0
                and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            )
            if good and g != pr["output"]:
                ok += 1
        print(ok, desc)
