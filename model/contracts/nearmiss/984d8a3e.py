"""Near-miss readings for ARC task 984d8a3e.

Rule: three colors. The mover color touches the left edge on every row where it
appears, the far color touches the right edge, and the third color is the
background. The far runs define a zone (the margins from the right edge that
far cells occupy anywhere). In each row the mover cells, counted from the far
edge inward, jump to the background cells of the zone, counted from the far
edge inward; each jumped cell becomes background.
"""
import json
from pathlib import Path


def _flush(inp, color, left):
    seen = False
    for row in inp:
        w = len(row)
        for c in range(w):
            if row[c] != color:
                continue
            seen = True
            nxt = c - 1 if left else c + 1
            if 0 <= nxt < w and row[nxt] == color:
                continue
            if c != (0 if left else w - 1):
                return False
    return seen


def _roles(inp):
    cols = sorted({v for r in inp for v in r})
    m = [c for c in cols if _flush(inp, c, True)]
    f = [c for c in cols if _flush(inp, c, False)]
    if len(m) != 1 or len(f) != 1:
        return None
    b = [c for c in cols if c not in (m[0], f[0])]
    if len(b) != 1:
        return None
    return m[0], f[0], b[0]


def _solve(inp, M, F, B, zone="global", mover_order="far_first",
           slot_order="far_first", vacate=None, slot_paint=None,
           keep_src=False, all_bg=False):
    h, w = len(inp), len(inp[0])
    out = [r[:] for r in inp]
    far_k = [{w - 1 - c for c in range(w) if inp[r][c] == F} for r in range(h)]
    allk = set().union(*far_k)
    if zone == "global":
        zk = allk
    elif zone == "plus1":
        zk = set(range(max(allk) + 2))
    elif zone == "min":
        widths = [len(s) for s in far_k if s]
        zk = set(range(min(widths)))
    elif zone == "minus1":
        zk = set(range(max(allk)))
    for r in range(h):
        if zone == "row":
            zk = far_k[r]
        movers = [w - 1 - c for c in range(w) if inp[r][c] == M]
        if all_bg:
            slots = [w - 1 - c for c in range(w) if inp[r][c] == B]
        else:
            slots = [w - 1 - c for c in range(w) if inp[r][c] == B and (w - 1 - c) in zk]
        movers.sort(reverse=(mover_order == "near_first"))
        slots.sort(reverse=(slot_order == "near_first"))
        for k_from, k_to in zip(movers, slots):
            if not keep_src:
                out[r][w - 1 - k_from] = B if vacate is None else vacate
            out[r][w - 1 - k_to] = M if slot_paint is None else slot_paint
    return out


def _mirror(g):
    return [r[::-1] for r in g]


def _base(inp, **kw):
    ro = _roles(inp)
    if ro is None:
        return None
    M, F, B = ro
    return _solve(inp, M, F, B, **kw)


def reference(inp):
    return _base(inp)


def copy_not_move(inp, out):
    return _base(inp, keep_src=True)


def row_zone(inp, out):
    return _base(inp, zone="row")


def zone_plus_one(inp, out):
    return _base(inp, zone="plus1")


def zone_narrowest(inp, out):
    return _base(inp, zone="min")


def nearest_mover_first(inp, out):
    return _base(inp, mover_order="near_first")


def fill_inner_slots_first(inp, out):
    return _base(inp, slot_order="near_first")


def vacated_becomes_far_color(inp, out):
    ro = _roles(inp)
    if ro is None:
        return None
    return _solve(inp, ro[0], ro[1], ro[2], vacate=ro[1])


def slots_painted_far_color(inp, out):
    ro = _roles(inp)
    if ro is None:
        return None
    return _solve(inp, ro[0], ro[1], ro[2], slot_paint=ro[1])


def any_background_cell_is_slot(inp, out):
    return _base(inp, all_bg=True)


def far_color_moves_left(inp, out):
    ro = _roles(inp)
    if ro is None:
        return None
    M, F, B = ro
    return _mirror(_solve(_mirror(inp), F, M, B))


def mover_cells_not_vacated_to_bg_but_zone_global_off_by_one(inp, out):
    return _base(inp, zone="minus1")


ALTERNATIVES = [
    ("movers are copied into the slots and also stay where they were", copy_not_move),
    ("slot zone is taken per row from that row's own far cells", row_zone),
    ("slot zone is one cell wider than the widest far run", zone_plus_one),
    ("slot zone is as wide as the narrowest far run", zone_narrowest),
    ("movers nearest the left edge jump first instead of those nearest the far edge", nearest_mover_first),
    ("jumping cells fill the slots from the inner end instead of next to the far edge", fill_inner_slots_first),
    ("vacated mover cells turn into the far color instead of the background", vacated_becomes_far_color),
    ("slots are painted with the far color instead of the mover color", slots_painted_far_color),
    ("every background cell of the row is a slot, not only those in the far zone", any_background_cell_is_slot),
    ("roles swapped: the far color moves left into slots next to the mover edge", far_color_moves_left),
    ("slot zone is one cell narrower than the widest far run", mover_cells_not_vacated_to_bg_but_zone_global_off_by_one),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / "data/tasks/984d8a3e.json"
    task = json.loads(path.read_text())
    pairs = task["train"]
    for i, p in enumerate(pairs):
        assert reference(p["input"]) == p["output"], f"reference fails on pair {i}"
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
