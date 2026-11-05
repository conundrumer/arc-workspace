"""Near-miss readings for ARC task 494ef9d7.

Rule: in a row holding exactly two colored cells whose colors form an
attracting pair ({4,7} or {1,8}), the right cell moves left to sit next to the
left cell. Other rows stay.
"""
import json
from pathlib import Path

BG = 0
PAIRS = [{4, 7}, {1, 8}]


def _copy(g):
    return [list(r) for r in g]


def _rows(g):
    """Yield (row index, [(col, color), ...]) for rows with exactly two cells."""
    for i, r in enumerate(g):
        cells = [(j, v) for j, v in enumerate(r) if v != BG]
        if len(cells) == 2:
            yield i, cells


def _apply(inp, pred, place, erase_far=True, recolor_near=False, move_near=False):
    """For each qualifying row, relocate a cell. place(near_j, far_j, w) -> new col."""
    g = _copy(inp)
    w = len(inp[0])
    for i, ((j1, c1), (j2, c2)) in ((i, c) for i, c in _rows(inp)):
        if not pred(c1, c2):
            continue
        if move_near:
            nj = place(j2, j1, w)
            g[i][j1] = BG
            g[i][nj] = c1
        else:
            nj = place(j1, j2, w)
            if erase_far:
                g[i][j2] = BG
            g[i][nj] = c1 if recolor_near else c2
    return g


def _is_pair(c1, c2):
    return {c1, c2} in PAIRS


def _adjacent(nj, fj, w):
    return nj + 1


def _fn(inp, **kw):
    return _apply(inp, kw.pop("pred", _is_pair), kw.pop("place", _adjacent), **kw)


def over_apply_any_two(inp, out):
    return _fn(inp, pred=lambda a, b: True)


def only_four_seven(inp, out):
    return _fn(inp, pred=lambda a, b: {a, b} == {4, 7})


def only_one_eight(inp, out):
    return _fn(inp, pred=lambda a, b: {a, b} == {1, 8})


def near_cell_moves(inp, out):
    return _fn(inp, move_near=True, place=lambda nj, fj, w: fj - 1)


def far_cell_to_edge(inp, out):
    return _fn(inp, place=lambda nj, fj, w: 0)


def far_cell_copied(inp, out):
    return _fn(inp, erase_far=False)


def one_cell_gap(inp, out):
    return _fn(inp, place=lambda nj, fj, w: nj + 2)


def takes_near_color(inp, out):
    return _fn(inp, recolor_near=True)


def any_member_of_pair_colors(inp, out):
    members = {4, 7, 1, 8}
    return _fn(inp, pred=lambda a, b: a in members or b in members)


def order_dependent_pair(inp, out):
    # pair only counts when the larger color is on the left
    return _fn(inp, pred=lambda a, b: _is_pair(a, b) and a > b)


def vertical_pull(inp, out):
    # columns instead of rows: the lower cell moves up next to the upper cell
    t = [list(c) for c in zip(*inp)]
    g = _apply(t, _is_pair, _adjacent)
    return [list(c) for c in zip(*g)]


def pair_swap_places(inp, out):
    # the two cells swap places instead of the far one moving
    g = _copy(inp)
    for i, ((j1, c1), (j2, c2)) in ((i, c) for i, c in _rows(inp)):
        if _is_pair(c1, c2):
            g[i][j1], g[i][j2] = c2, c1
    return g


ALTERNATIVES = [
    ("every row with two colored cells pulls, whatever the colors", over_apply_any_two),
    ("only the 4-7 pair attracts; 1-8 rows stay", only_four_seven),
    ("only the 1-8 pair attracts; 4-7 rows stay", only_one_eight),
    ("the left cell moves right to meet the right cell", near_cell_moves),
    ("the right cell moves all the way to the left edge", far_cell_to_edge),
    ("the right cell is copied beside the left cell, not moved", far_cell_copied),
    ("the right cell stops one cell short, leaving a gap", one_cell_gap),
    ("the moved cell takes the left cell's color", takes_near_color),
    ("any row with one of the colors 1, 4, 7, 8 pulls", any_member_of_pair_colors),
    ("a pair attracts only when the larger color is on the left", order_dependent_pair),
    ("pull works along columns, upward, instead of along rows", vertical_pull),
    ("the two cells of a pair swap places", pair_swap_places),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/494ef9d7.json").read_text())
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (
                isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                and len({len(r) for r in g}) == 1
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                and g != p["output"]
            )
            n += ok
        print(n, desc)
