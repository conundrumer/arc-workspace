import json
from pathlib import Path


def _color(out):
    return out[0][0]


def _cells(inp):
    return [v for row in inp for v in row]


def copy_input_color(inp, out):
    # output the silhouette's own color instead of the shape class
    return [[max(_cells(inp))]]


def count_nonzero(inp, out):
    # output the number of filled cells instead of the shape class
    return [[sum(1 for v in _cells(inp) if v != 0)]]


def class_off_by_one(inp, out):
    # right shape, class label shifted by one
    return [[(_color(out) + 1) % 10]]


def full_3x3_block(inp, out):
    # keep input size: fill the whole 3x3 grid with the class color
    return [[_color(out)] * 3 for _ in range(3)]


def constant_one(inp, out):
    # treat every shape as the corner-only class; None where that is correct
    return None if _color(out) == 1 else [[1]]


def swap_class_pairs(inp, out):
    # confuse X-like shape with diagonal-L shape and corner shape with plus
    m = {1: 6, 6: 1, 2: 3, 3: 2}
    return [[m.get(_color(out), 0)]]


def return_input(inp, out):
    # no reduction: output is the input
    return [r[:] for r in inp]


def center_cell_value(inp, out):
    # output the center cell's value
    return [[inp[1][1]]]


def count_background(inp, out):
    # output the number of background cells
    return [[sum(1 for v in _cells(inp) if v == 0)]]


def row_instead_of_cell(inp, out):
    # output is a 1x3 row instead of a single cell
    return [[_color(out)] * 3]


def edge_midpoint_count(inp, out):
    # count filled edge-midpoint cells instead of corner cells
    n = sum(1 for r, c in ((0, 1), (1, 0), (1, 2), (2, 1)) if inp[r][c] != 0)
    return [[n]]


ALTERNATIVES = [
    ("output the silhouette's color instead of the shape class", copy_input_color),
    ("output the number of filled cells", count_nonzero),
    ("shape class label off by one", class_off_by_one),
    ("fill a whole 3x3 grid with the class color", full_3x3_block),
    ("always answer the corner-only class", constant_one),
    ("swap the classes of the X shape and the diagonal-L shape, and of the corner shape and the plus", swap_class_pairs),
    ("return the input unchanged", return_input),
    ("output the center cell's value", center_cell_value),
    ("output the number of background cells", count_background),
    ("output a 1x3 row of the class color", row_instead_of_cell),
    ("count filled edge-midpoint cells instead of corners", edge_midpoint_count),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/27a28665.json'))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
