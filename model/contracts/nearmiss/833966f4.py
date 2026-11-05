"""Near-miss readings for ARC task 833966f4 (5x1 column: reverse each end part, keep the middle cell)."""
import json
from pathlib import Path


def _col(g):
    return [r[0] for r in g]


def _grid(vals):
    return [[v] for v in vals]


def whole_reverse(inp, out):
    return _grid(_col(inp)[::-1])


def no_gap_pairs(inp, out):
    v = _col(inp)
    return _grid([v[1], v[0], v[3], v[2], v[4]])


def parts_three_two(inp, out):
    v = _col(inp)
    return _grid(v[:3][::-1] + v[3:][::-1])


def blocks_swapped_unreversed(inp, out):
    v = _col(inp)
    return _grid(v[3:] + [v[2]] + v[:2])


def first_only(inp, out):
    v = _col(inp)
    return _grid(v[:2][::-1] + v[2:])


def second_only(inp, out):
    v = _col(inp)
    return _grid(v[:3] + v[3:][::-1])


def cyclic_shift_down(inp, out):
    v = _col(inp)
    return _grid(v[-1:] + v[:-1])


def gap_set_background(inp, out):
    o = _col(out)
    o[2] = 0
    return _grid(o)


def row_output(inp, out):
    return [_col(out)]


def sort_parts_ascending(inp, out):
    v = _col(inp)
    return _grid(sorted(v[:2]) + [v[2]] + sorted(v[3:]))


def reverse_middle_three(inp, out):
    v = _col(inp)
    return _grid(v[:1] + v[1:4][::-1] + v[4:])


def swap_outer_cells(inp, out):
    v = _col(inp)
    return _grid([v[4], v[1], v[2], v[3], v[0]])


ALTERNATIVES = [
    ("reverse the whole column", whole_reverse),
    ("no gap: tiles of 2 cells, last cell left alone", no_gap_pairs),
    ("split into 3 and 2 cells, reverse each", parts_three_two),
    ("swap the two end parts without reversing inside them", blocks_swapped_unreversed),
    ("reverse only the first part", first_only),
    ("reverse only the second part", second_only),
    ("shift the column down by one cell cyclically", cyclic_shift_down),
    ("reverse both parts and clear the gap cell to 0", gap_set_background),
    ("output transposed to one row", row_output),
    ("sort each part in ascending order", sort_parts_ascending),
    ("reverse the three middle cells, keep the two outer cells", reverse_middle_three),
    ("swap only the first and last cell", swap_outer_cells),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/833966f4.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
