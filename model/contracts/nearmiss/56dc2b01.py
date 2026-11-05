import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r if v)
    anchor = min(cnt, key=lambda c: cnt[c])
    mover = [c for c in cnt if c != anchor][0]
    acells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == anchor]
    mcells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == mover]
    if len({c for _, c in acells}) == 1:  # vertical anchor line
        ac = acells[0][1]
        mc = sum(c for _, c in mcells) / len(mcells)
        d = (0, 1 if ac > mc else -1)
    else:
        ar = acells[0][0]
        mr = sum(r for r, _ in mcells) / len(mcells)
        d = (1 if ar > mr else -1, 0)
    return h, w, anchor, mover, acells, mcells, d


def _gap(acells, mcells, d):
    # free cells between the mover's leading edge and the anchor line
    if d[0]:
        a = acells[0][0]
        lead = max(r for r, _ in mcells) if d[0] > 0 else min(r for r, _ in mcells)
        return abs(a - lead) - 1
    a = acells[0][1]
    lead = max(c for _, c in mcells) if d[1] > 0 else min(c for _, c in mcells)
    return abs(a - lead) - 1


def sim(inp, dk=0, erase=True, line=True, line_color=8, line_gap=0, line_len="full",
        flip=False, reverse=False, line_at_origin=False, fill_old=None, d_override=None):
    h, w, anchor, mover, acells, mcells, d = _parse(inp)
    if reverse:
        d = (-d[0], -d[1])
        k = (min(r for r, _ in mcells) if d[0] < 0 else (h - 1 - max(r for r, _ in mcells))) if d[0] else \
            (min(c for _, c in mcells) if d[1] < 0 else (w - 1 - max(c for _, c in mcells)))
    else:
        k = _gap(acells, mcells, d)
    k += dk
    if k < 0:
        return None
    g = [row[:] for row in inp]
    if erase:
        for r, c in mcells:
            g[r][c] = 0 if fill_old is None else fill_old
    cells = list(mcells)
    if flip:
        if d[0]:
            lo = min(r for r, _ in cells); hi = max(r for r, _ in cells)
            cells = [(lo + hi - r, c) for r, c in cells]
        else:
            lo = min(c for _, c in cells); hi = max(c for _, c in cells)
            cells = [(r, lo + hi - c) for r, c in cells]
    new = [(r + d[0] * k, c + d[1] * k) for r, c in cells]
    if any(not (0 <= r < h and 0 <= c < w) for r, c in new):
        return None
    if line:
        ref = mcells if line_at_origin else new
        if d[0]:
            edge = (min(r for r, _ in ref) - 1 - line_gap) if d[0] > 0 else (max(r for r, _ in ref) + 1 + line_gap)
            if not 0 <= edge < h:
                return None
            if line_len == "full":
                cols = range(w)
            else:
                cols = range(min(c for _, c in ref), max(c for _, c in ref) + 1)
            for c in cols:
                g[edge][c] = line_color
        else:
            edge = (min(c for _, c in ref) - 1 - line_gap) if d[1] > 0 else (max(c for _, c in ref) + 1 + line_gap)
            if not 0 <= edge < w:
                return None
            if line_len == "full":
                rows = range(h)
            else:
                rows = range(min(r for r, _ in ref), max(r for r, _ in ref) + 1)
            for r in rows:
                g[r][edge] = line_color
    for r, c in new:
        g[r][c] = mover
    return g


def no_line(inp, out):
    return sim(inp, line=False)


def wrong_line_color(inp, out):
    return sim(inp, line_color=_parse(inp)[2])


def stops_short(inp, out):
    return sim(inp, dk=-1)


def overshoots(inp, out):
    return sim(inp, dk=1)


def copy_not_move(inp, out):
    return sim(inp, erase=False)


def line_gap_one(inp, out):
    return sim(inp, line_gap=1)


def line_at_origin_edge(inp, out):
    return sim(inp, line_at_origin=True)


def moves_away(inp, out):
    return sim(inp, reverse=True)


def line_only_shape_extent(inp, out):
    return sim(inp, line_len="shape")


def shape_mirrored(inp, out):
    return sim(inp, flip=True)


def line_in_mover_color(inp, out):
    return sim(inp, line_color=_parse(inp)[3])


def input_unchanged(inp, out):
    return [r[:] for r in inp]


ALTERNATIVES = [
    ("the mover lands correctly but no trailing line is drawn", no_line),
    ("the trailing line is drawn in the anchor color instead of 8", wrong_line_color),
    ("the mover stops one cell short of the anchor line", stops_short),
    ("the mover moves one cell too far and overwrites the anchor line", overshoots),
    ("the mover is copied to the landing place and left in its old place", copy_not_move),
    ("the trailing line leaves a one-cell gap behind the mover", line_gap_one),
    ("the trailing line is drawn behind the mover's old position, not the landing place", line_at_origin_edge),
    ("the mover moves away from the anchor line to the grid edge", moves_away),
    ("the trailing line spans only the mover's extent, not the whole grid", line_only_shape_extent),
    ("the mover lands mirrored along its direction of travel", shape_mirrored),
    ("the trailing line is drawn in the mover's color", line_in_mover_color),
    ("the grid is returned unchanged", input_unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/56dc2b01.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
