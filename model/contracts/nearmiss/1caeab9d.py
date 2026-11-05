import json
from pathlib import Path


def _cells(g):
    d = {}
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v:
                d.setdefault(v, []).append((r, c))
    return d


def _blank(g):
    return [[0] * len(g[0]) for _ in g]


def _render(g, placements):
    """placements: list of cell lists (r, c, color), drawn in order."""
    h, w = len(g), len(g[0])
    o = _blank(g)
    for cells in placements:
        for r, c, v in cells:
            if 0 <= r < h and 0 <= c < w:
                o[r][c] = v
    return o


def _anchor(inp, out):
    ci, co = _cells(inp), _cells(out)
    for col, cs in ci.items():
        if sorted(cs) == sorted(co.get(col, [])):
            return col
    return None


def _shifted(cs, col, dr, dc):
    return [(r + dr, c + dc, col) for r, c in cs]


def _align_rows_to(inp, target, edge="top"):
    """Move every block so its top (or bottom) row matches that of block `target`."""
    ci = _cells(inp)
    if target not in ci:
        return None
    ref = ci[target]
    ref_r = min(r for r, _ in ref) if edge == "top" else max(r for r, _ in ref)
    pl = []
    for col, cs in ci.items():
        cur = min(r for r, _ in cs) if edge == "top" else max(r for r, _ in cs)
        pl.append(_shifted(cs, col, ref_r - cur, 0))
    return _render(inp, pl)


def anchor_is_2(inp, out):
    return _align_rows_to(inp, 2)


def anchor_is_4(inp, out):
    return _align_rows_to(inp, 4)


def align_to_topmost(inp, out):
    ci = _cells(inp)
    t = min(ci, key=lambda k: min(r for r, _ in ci[k]))
    return _align_rows_to(inp, t)


def align_to_bottommost(inp, out):
    ci = _cells(inp)
    t = max(ci, key=lambda k: max(r for r, _ in ci[k]))
    return _align_rows_to(inp, t, "bottom")


def horizontal_align(inp, out):
    a = _anchor(inp, out)
    ci = _cells(inp)
    ref = min(c for _, c in ci[a])
    pl = [_shifted(cs, col, 0, ref - min(c for _, c in cs)) for col, cs in ci.items() if col != a]
    pl.append(_shifted(ci[a], a, 0, 0))
    return _render(inp, pl)


def moved_blocks_erased(inp, out):
    a = _anchor(inp, out)
    return _render(inp, [_shifted(_cells(inp)[a], a, 0, 0)])


def copy_not_move(inp, out):
    a = _anchor(inp, out)
    ci = _cells(inp)
    ref = min(r for r, _ in ci[a])
    pl = [_shifted(cs, col, 0, 0) for col, cs in ci.items()]
    pl += [_shifted(cs, col, ref - min(r for r, _ in cs), 0) for col, cs in ci.items() if col != a]
    pl.append(_shifted(ci[a], a, 0, 0))
    return _render(inp, pl)


def off_by_one_down(inp, out):
    a = _anchor(inp, out)
    co = _cells(out)
    pl = [_shifted(cs, col, 1, 0) for col, cs in co.items() if col != a]
    pl.append(_shifted(co[a], a, 0, 0))
    return _render(inp, pl)


def top_at_anchor_bottom(inp, out):
    a = _anchor(inp, out)
    ci = _cells(inp)
    ref = max(r for r, _ in ci[a])
    pl = [_shifted(cs, col, ref - min(r for r, _ in cs), 0) for col, cs in ci.items() if col != a]
    pl.append(_shifted(ci[a], a, 0, 0))
    return _render(inp, pl)


def only_leftmost_moves(inp, out):
    a = _anchor(inp, out)
    ci = _cells(inp)
    ref = min(r for r, _ in ci[a])
    others = sorted((col for col in ci if col != a), key=lambda k: min(c for _, c in ci[k]))
    mv = others[0]
    pl = [_shifted(cs, col, 0, 0) for col, cs in ci.items() if col != mv]
    pl.append(_shifted(ci[mv], mv, ref - min(r for r, _ in ci[mv]), 0))
    return _render(inp, pl)


def align_to_grid_top(inp, out):
    ci = _cells(inp)
    pl = [_shifted(cs, col, -min(r for r, _ in cs), 0) for col, cs in ci.items()]
    return _render(inp, pl)


def crop_to_content(inp, out):
    co = _cells(out)
    allc = [p for cs in co.values() for p in cs]
    r0, r1 = min(r for r, _ in allc), max(r for r, _ in allc)
    c0, c1 = min(c for _, c in allc), max(c for _, c in allc)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("blocks align to the 2-colored block instead of the unchanged block", anchor_is_2),
    ("blocks align to the 4-colored block instead of the unchanged block", anchor_is_4),
    ("blocks align to the topmost block's rows", align_to_topmost),
    ("blocks align to the bottommost block's bottom edge", align_to_bottommost),
    ("blocks slide horizontally to the anchor's columns instead of vertically to its rows", horizontal_align),
    ("moved blocks are removed and only the anchor remains", moved_blocks_erased),
    ("blocks are copied to the anchor's rows and the originals stay", copy_not_move),
    ("moved blocks land one row too low", off_by_one_down),
    ("moved blocks put their top row on the anchor's bottom row", top_at_anchor_bottom),
    ("only the leftmost non-anchor block moves", only_leftmost_moves),
    ("all blocks, anchor included, move up to the top grid row", align_to_grid_top),
    ("output is cropped to the bounding box of the colored cells", crop_to_content),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/1caeab9d.json'))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error:", desc, repr(e))
                g = None
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
