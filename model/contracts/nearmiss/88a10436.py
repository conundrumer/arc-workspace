import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    ink = {(r, c) for r in range(h) for c in range(w) if inp[r][c] != 0}
    def lone(p):
        r, c = p
        return not any((r + dr, c + dc) in ink
                       for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0))
    marker = sorted(p for p in ink if lone(p))[0]
    shape = {p: inp[p[0]][p[1]] for p in ink if p != marker}
    r0 = min(r for r, _ in shape)
    r1 = max(r for r, _ in shape)
    c0 = min(c for _, c in shape)
    c1 = max(c for _, c in shape)
    return marker, shape, (r0, c0, r1, c1)


def _patch(inp, marker, shape, bbox, tr, tc, erase_marker=True, erase_src=False, keep_marker=False):
    """Paste `shape` (dict) whose bbox top-left moves to (tr, tc)."""
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    if erase_marker:
        g[marker[0]][marker[1]] = 0
    if erase_src:
        for (r, c) in shape:
            g[r][c] = 0
    dr, dc = tr - bbox[0], tc - bbox[1]
    for (r, c), v in shape.items():
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w:
            g[nr][nc] = v
    if keep_marker:
        g[marker[0]][marker[1]] = inp[marker[0]][marker[1]]
    return g


def _centered(inp, shape_map=None, off=(0, 0), **kw):
    marker, shape, bbox = _parse(inp)
    if shape_map is not None:
        shape, bbox = shape_map(shape, bbox)
    bh = bbox[2] - bbox[0] + 1
    bw = bbox[3] - bbox[1] + 1
    tr = marker[0] - bh // 2 + off[0]
    tc = marker[1] - bw // 2 + off[1]
    return _patch(inp, marker, shape, bbox, tr, tc, **kw)


def top_left_at_marker(inp, out):
    marker, shape, bbox = _parse(inp)
    return _patch(inp, marker, shape, bbox, marker[0], marker[1])


def bottom_right_at_marker(inp, out):
    marker, shape, bbox = _parse(inp)
    bh = bbox[2] - bbox[0]
    bw = bbox[3] - bbox[1]
    return _patch(inp, marker, shape, bbox, marker[0] - bh, marker[1] - bw)


def marker_kept(inp, out):
    marker, _, _ = _parse(inp)
    g = [row[:] for row in out]
    g[marker[0]][marker[1]] = inp[marker[0]][marker[1]]
    return g


def _mirror_h(shape, bbox):
    c0, c1 = bbox[1], bbox[3]
    return {(r, c0 + c1 - c): v for (r, c), v in shape.items()}, bbox


def _mirror_v(shape, bbox):
    r0, r1 = bbox[0], bbox[2]
    return {(r0 + r1 - r, c): v for (r, c), v in shape.items()}, bbox


def _rot_cw(shape, bbox):
    r0, c0, r1, c1 = bbox
    h = r1 - r0 + 1
    new = {}
    for (r, c), v in shape.items():
        rr, cc = r - r0, c - c0
        new[(r0 + cc, c0 + (h - 1 - rr))] = v
    return new, (r0, c0, r0 + (c1 - c0), c0 + (r1 - r0))


def mirrored_horizontally(inp, out):
    return _centered(inp, _mirror_h)


def mirrored_vertically(inp, out):
    return _centered(inp, _mirror_v)


def rotated_quarter_turn(inp, out):
    return _centered(inp, _rot_cw)


def all_marker_color(inp, out):
    marker, shape, bbox = _parse(inp)
    mc = inp[marker[0]][marker[1]]
    return _centered(inp, lambda s, b: ({p: mc for p in s}, b))


def moved_not_copied(inp, out):
    return _centered(inp, erase_src=True)


def center_one_row_low(inp, out):
    return _centered(inp, off=(1, 0))


def center_one_col_left(inp, out):
    return _centered(inp, off=(0, -1))


def rarest_color_dropped(inp, out):
    marker, shape, bbox = _parse(inp)
    cnt = Counter(shape.values())
    rare = min(cnt, key=lambda k: (cnt[k], k))
    return _centered(inp, lambda s, b: ({p: v for p, v in s.items() if v != rare}, b))


def top_row_only(inp, out):
    return _centered(inp, lambda s, b: ({p: v for p, v in s.items() if p[0] == b[0]}, b))


def marker_removed_only(inp, out):
    marker, _, _ = _parse(inp)
    g = [row[:] for row in inp]
    g[marker[0]][marker[1]] = 0
    return g


ALTERNATIVES = [
    ("copy has its top-left corner at the marker instead of its center", top_left_at_marker),
    ("copy has its bottom-right corner at the marker instead of its center", bottom_right_at_marker),
    ("copy is correct but the marker cell stays in the output", marker_kept),
    ("copy is mirrored left-right", mirrored_horizontally),
    ("copy is mirrored top-bottom", mirrored_vertically),
    ("copy is rotated a quarter turn", rotated_quarter_turn),
    ("copy is painted entirely in the marker color", all_marker_color),
    ("shape is moved to the marker, original erased", moved_not_copied),
    ("copy is centered one row below the marker", center_one_row_low),
    ("copy is centered one column left of the marker", center_one_col_left),
    ("copy omits the rarest color of the shape", rarest_color_dropped),
    ("copy holds only the top row of the shape", top_row_only),
]


def _valid(g):
    return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/88a10436.json').read_text())
    pairs = task["train"]
    print("pairs:", len(pairs), "readings:", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn([r[:] for r in p["input"]], [r[:] for r in p["output"]])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
