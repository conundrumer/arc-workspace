"""Near-miss readings for ARC task 98cf29f8.

Rule: a wide body is joined to an anchor-facing thin arm. The body slides along the
arm's axis until it abuts the anchor rectangle, and the arm disappears.
"""
import json
from collections import Counter
from pathlib import Path


def _cells(g, color):
    return {(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v == color}


def _info(inp, out):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    colors = [c for c in cnt if c != bg]
    anchor = next(c for c in colors if _cells(inp, c) == _cells(out, c))
    lever = next(c for c in colors if c != anchor)
    lev_in, lev_out = _cells(inp, lever), _cells(out, lever)
    delta = None
    for k in range(1, max(h, w)):
        for d in ((k, 0), (-k, 0), (0, k), (0, -k)):
            if all((r - d[0], c - d[1]) in lev_in for r, c in lev_out):
                delta = d
                break
        if delta:
            break
    body = {(r - delta[0], c - delta[1]) for r, c in lev_out}
    return dict(h=h, w=w, bg=bg, A=anchor, L=lever, anchor=_cells(inp, anchor),
                lev_in=lev_in, lev_out=lev_out, delta=delta, body=body,
                arm=lev_in - body)


def _draw(i, layers):
    g = [[i["bg"]] * i["w"] for _ in range(i["h"])]
    for cells, color in layers:
        for r, c in cells:
            if 0 <= r < i["h"] and 0 <= c < i["w"]:
                g[r][c] = color
    return g


def _shift(cells, d):
    return {(r + d[0], c + d[1]) for r, c in cells}


def _unit(d):
    return ((d[0] > 0) - (d[0] < 0), (d[1] > 0) - (d[1] < 0))


def _scale(u, k):
    return (u[0] * k, u[1] * k)


def _dist(d):
    return abs(d[0]) + abs(d[1])


def _final(i, delta, body=None, extra=()):
    body = i["body"] if body is None else body
    return _draw(i, [(i["anchor"], i["A"]), *extra, (_shift(body, delta), i["L"])])


def unchanged(inp, out):
    return [row[:] for row in inp]


def body_stays_arm_erased(inp, out):
    i = _info(inp, out)
    return _draw(i, [(i["anchor"], i["A"]), (i["body"], i["L"])])


def stops_one_short(inp, out):
    i = _info(inp, out)
    u = _unit(i["delta"])
    return _final(i, _scale(u, _dist(i["delta"]) - 1))


def overshoots_into_anchor(inp, out):
    i = _info(inp, out)
    u = _unit(i["delta"])
    return _final(i, _scale(u, _dist(i["delta"]) + 1))


def moves_away_from_anchor(inp, out):
    i = _info(inp, out)
    return _final(i, (-i["delta"][0], -i["delta"][1]))


def moves_half_way(inp, out):
    i = _info(inp, out)
    u = _unit(i["delta"])
    return _final(i, _scale(u, _dist(i["delta"]) // 2))


def body_takes_anchor_color(inp, out):
    i = _info(inp, out)
    return _draw(i, [(i["anchor"], i["A"]), (_shift(i["body"], i["delta"]), i["A"])])


def colors_swapped(inp, out):
    i = _info(inp, out)
    swap = {i["A"]: i["L"], i["L"]: i["A"]}
    return [[swap.get(v, v) for v in row] for row in out]


def whole_lever_shifts_rigidly(inp, out):
    i = _info(inp, out)
    return _draw(i, [(i["anchor"], i["A"]), (_shift(i["lev_in"], i["delta"]), i["L"])])


def moves_along_perpendicular_axis(inp, out):
    i = _info(inp, out)
    d = i["delta"]
    perp = (0, _dist(d)) if d[0] else (_dist(d), 0)
    return _final(i, perp)


def far_edge_line_dropped(inp, out):
    i = _info(inp, out)
    d = i["delta"]
    ax = 0 if d[0] else 1
    u = _unit(d)[ax]
    moved = _shift(i["body"], d)
    far = min(p[ax] * u for p in moved)
    kept = {p for p in moved if p[ax] * u != far}
    return _draw(i, [(i["anchor"], i["A"]), (kept, i["L"])])


def body_offset_sideways_by_one(inp, out):
    i = _info(inp, out)
    d = i["delta"]
    side = (0, 1) if d[0] else (1, 0)
    return _final(i, (d[0] + side[0], d[1] + side[1]))


ALTERNATIVES = [
    ("Grid returned unchanged", unchanged),
    ("Body stays in place and only the arm is erased", body_stays_arm_erased),
    ("Body stops one cell short of the anchor", stops_one_short),
    ("Body overshoots by one cell and overwrites the anchor edge", overshoots_into_anchor),
    ("Body slides away from the anchor instead of toward it", moves_away_from_anchor),
    ("Body slides only half the distance to the anchor", moves_half_way),
    ("Body is painted in the anchor's color", body_takes_anchor_color),
    ("Anchor color and body color are swapped", colors_swapped),
    ("Whole lever including arm moves rigidly, arm kept", whole_lever_shifts_rigidly),
    ("Body slides along the axis perpendicular to the arm", moves_along_perpendicular_axis),
    ("Body lands abutting but lacks its far edge line", far_edge_line_dropped),
    ("Body abuts the anchor but is offset one cell sideways", body_offset_sideways_by_one),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


def _wrap(fn, inp, out):
    try:
        return fn(inp, out)
    except Exception as e:  # report but keep checking
        print("   error:", repr(e))
        return None


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/98cf29f8.json").read_text())
    pairs = task["train"]
    print("pairs:", len(pairs))
    for name, fn in ALTERNATIVES:
        ok = []
        for p in pairs:
            g = _wrap(fn, p["input"], p["output"])
            ok.append(g is not None and _valid(g) and g != p["output"])
        print(f"{sum(ok)}/{len(pairs)}  {name}  {ok}")
