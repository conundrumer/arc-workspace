"""Near-miss readings for ARC task 79fb03f4.

Rule: the rarest color (1) streams rightward along its row. A marker (a color
other than the background and the stream) met by the stream is bypassed through
a 3x3 ring of stream cells around it.
"""
import json
from pathlib import Path

BG, FLOW = 0, 1


def _copy(g):
    return [list(r) for r in g]


def _markers(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v not in (BG, FLOW)]


def _flows(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == FLOW]


def ring_only(inp, out):
    # Rings around markers, but no stream along the flow rows.
    g = _copy(inp)
    h, w = len(g), len(g[0])
    for r, c in _markers(inp):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if (dr or dc) and 0 <= rr < h and 0 <= cc < w and inp[rr][cc] == BG:
                    g[rr][cc] = FLOW
    return g


def stream_only(inp, out):
    # Straight stream through the flow row; markers get no detour and stay.
    g = _copy(inp)
    for r, c in _flows(inp):
        for cc in range(c, len(g[0])):
            if inp[r][cc] == BG:
                g[r][cc] = FLOW
    return g


def stop_at_marker(inp, out):
    # The stream ends at the first marker in its row; no ring.
    g = _copy(inp)
    for r, c in _flows(inp):
        for cc in range(c, len(g[0])):
            if inp[r][cc] not in (BG, FLOW):
                break
            g[r][cc] = FLOW
    return g


def recolor_flow(inp, out):
    # Stream drawn in the marker color instead of the flow color.
    ms = _markers(inp)
    if not ms:
        return None
    from collections import Counter
    col = Counter(inp[r][c] for r, c in ms).most_common(1)[0][0]
    return [[col if v == FLOW else v for v in row] for row in out]


def plus_ring(inp, out):
    # Detour is a plus shape (4 neighbours) rather than the full 3x3 ring.
    g = _copy(out)
    for r, c in _markers(inp):
        for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < len(g) and 0 <= cc < len(g[0]) and inp[rr][cc] == BG:
                g[rr][cc] = BG
    return g


def erase_markers(inp, out):
    # Markers are overwritten by the stream.
    return [[FLOW if (inp[r][c] not in (BG, FLOW)) else v for c, v in enumerate(row)]
            for r, row in enumerate(out)]


def all_marker_rows(inp, out):
    # The stream also runs through the row of every marker, not only flow rows.
    g = _copy(out)
    for r, c in _markers(inp):
        for cc in range(len(g[0])):
            if inp[r][cc] == BG:
                g[r][cc] = FLOW
    return g


def flow_column(inp, out):
    # The stream runs down the flow cell's column instead of along its row.
    g = _copy(inp)
    for r, c in _flows(inp):
        for rr in range(r, len(g)):
            if inp[rr][c] == BG:
                g[rr][c] = FLOW
    return g


def detour_above_only(inp, out):
    # The ring is drawn only on the row above each marker; row below is left out.
    g = _copy(out)
    for r, c in _markers(inp):
        rr = r + 1
        if rr < len(g):
            for cc in range(c - 1, c + 2):
                if 0 <= cc < len(g[0]) and inp[rr][cc] == BG:
                    g[rr][cc] = BG
    return g


def wide_ring(inp, out):
    # Detour ring has radius 2 (5x5) instead of radius 1.
    g = _copy(out)
    h, w = len(g), len(g[0])
    for r, c in _markers(inp):
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                rr, cc = r + dr, c + dc
                if max(abs(dr), abs(dc)) == 2 and 0 <= rr < h and 0 <= cc < w and inp[rr][cc] == BG:
                    g[rr][cc] = FLOW
    return g


def stream_leftward(inp, out):
    # The stream runs from the flow cell toward the left edge, with rings.
    g = ring_only(inp, out)
    for r, c in _flows(inp):
        for cc in range(0, c + 1):
            if inp[r][cc] == BG:
                g[r][cc] = FLOW
    return g


def first_flow_only(inp, out):
    # Only the topmost flow cell streams; the others are ignored.
    fl = _flows(inp)
    if len(fl) < 2:
        return None
    keep = fl[0]
    return _stream_from(inp, [keep])


def _stream_from(inp, starts):
    g = _copy(inp)
    h, w = len(g), len(g[0])
    for r, c in starts:
        for cc in range(c, w):
            if inp[r][cc] == BG:
                g[r][cc] = FLOW
    for r, c in _markers(inp):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if (dr or dc) and 0 <= rr < h and 0 <= cc < w and inp[rr][cc] == BG:
                    g[rr][cc] = FLOW
    return g


ALTERNATIVES = [
    ("rings around markers only, no stream along the flow row", ring_only),
    ("straight stream along the flow row, no detour around markers", stream_only),
    ("stream stops at the first marker in its row", stop_at_marker),
    ("stream drawn in the marker color instead of the flow color", recolor_flow),
    ("detour is a plus shape instead of the 3x3 ring", plus_ring),
    ("markers are overwritten by the stream", erase_markers),
    ("stream also runs through the row of every marker", all_marker_rows),
    ("stream runs down the flow cell's column instead of along its row", flow_column),
    ("detour drawn on the row above each marker only, below left out", detour_above_only),
    ("detour ring has radius 2 instead of 1", wide_ring),
    ("stream runs leftward from the flow cell", stream_leftward),
    ("only the first flow cell streams, other flow cells ignored", first_flow_only),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / "data/tasks/79fb03f4.json"
    train = json.load(open(path))["train"]
    print(f"{len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(_copy(p["input"]), _copy(p["output"]))
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
