from pathlib import Path
import json


def hflip(g):
    return [r[::-1] for r in g]


def vflip(g):
    return [r[:] for r in g[::-1]]


def transpose(g):
    return [list(c) for c in zip(*g)]


def hcat(a, b):
    return [x + y for x, y in zip(a, b)]


ALTERNATIVES = [
    ("tile the input twice to the right with no mirroring",
     lambda inp, out: hcat(inp, inp)),
    ("mirror placed on the left of the input instead of the right",
     lambda inp, out: hcat(hflip(inp), inp)),
    ("mirror stacked below the input (vertical axis) instead of beside it",
     lambda inp, out: [r[:] for r in inp] + vflip(inp)),
    ("input stacked twice below itself with no mirroring",
     lambda inp, out: [r[:] for r in inp] + [r[:] for r in inp]),
    ("append the 180-degree rotation of the input to the right",
     lambda inp, out: hcat(inp, vflip(hflip(inp)))),
    ("append the transpose of the input to the right",
     lambda inp, out: hcat(inp, transpose(inp))),
    ("mirror shares the boundary column, so the output is one column narrow",
     lambda inp, out: [r + r[::-1][1:] for r in inp]),
    ("full 2x2 mirrored tiling (mirror in both axes)",
     lambda inp, out: [r + r[::-1] for r in inp] + [r + r[::-1] for r in inp[::-1]]),
    ("output only the mirrored copy, without the original",
     lambda inp, out: hflip(inp)),
    ("three tiles: input, mirror, input again",
     lambda inp, out: [r + r[::-1] + r for r in inp]),
    ("mirror copy has its rows in reversed order (vertical flip instead of horizontal)",
     lambda inp, out: hcat(inp, vflip(inp))),
    ("output is the true output but the mirrored half keeps the original last column",
     lambda inp, out: [r[:-1] + [i[-1]] for r, i in zip(out, inp)]),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/6d0aefbc.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for name, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, name)
