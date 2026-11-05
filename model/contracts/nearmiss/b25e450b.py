import json
from pathlib import Path


def _blocks(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == 0 and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                r0 = min(y for y, _ in cells)
                r1 = max(y for y, _ in cells)
                c0 = min(x for _, x in cells)
                c1 = max(x for _, x in cells)
                if c0 == 0 and c1 < w - 1:
                    d = (0, 1)
                elif c1 == w - 1 and c0 > 0:
                    d = (0, -1)
                elif r0 == 0 and r1 < h - 1:
                    d = (1, 0)
                elif r1 == h - 1 and r0 > 0:
                    d = (-1, 0)
                else:
                    d = None
                res.append((r0, r1, c0, c1, d))
    return res


def _dest(b, h, w, mode):
    r0, r1, c0, c1, d = b
    dy, dx = d
    if dx:
        full = w - (c1 - c0 + 1)
        if mode == "short":
            tgt = (full if dx > 0 else 0) - dx
        elif mode == "half":
            tgt = (c0 + full) // 2 if dx > 0 else c0 // 2
        else:
            tgt = full if dx > 0 else 0
        nc0 = tgt
        nr0, nr1 = r0, r1
        if mode == "mirror":
            nr0, nr1 = h - 1 - r1, h - 1 - r0
        return (nr0, nr1, nc0, nc0 + c1 - c0)
    full = h - (r1 - r0 + 1)
    if mode == "short":
        tgt = (full if dy > 0 else 0) - dy
    elif mode == "half":
        tgt = (r0 + full) // 2 if dy > 0 else r0 // 2
    else:
        tgt = full if dy > 0 else 0
    nc0, nc1 = c0, c1
    if mode == "mirror":
        nc0, nc1 = w - 1 - c1, w - 1 - c0
    return (tgt, tgt + r1 - r0, nc0, nc1)


def _fill(g, r0, r1, c0, c1, v):
    for y in range(r0, r1 + 1):
        for x in range(c0, c1 + 1):
            g[y][x] = v


def _render(inp, trail=7, track="band", dest="opp", top="block", which="all",
            blockcolor=0, stay=False, allbg=False):
    h, w = len(inp), len(inp[0])
    bl = [b for b in _blocks(inp) if b[4] is not None]
    if which == "largest":
        if len(bl) < 2:
            return None
        bl = [max(bl, key=lambda b: (b[1] - b[0] + 1) * (b[3] - b[2] + 1))]
    g = [row[:] for row in inp]
    if allbg:
        g = [[trail if v != 0 else 0 for v in row] for row in g]
    tracks = []
    for b in bl:
        r0, r1, c0, c1, (dy, dx) = b
        if track == "band":
            t = (r0, r1, 0, w - 1) if dx else (0, h - 1, c0, c1)
        elif track == "perp":
            t = (0, h - 1, c0, c1) if dx else (r0, r1, 0, w - 1)
        elif track == "wide":
            if dx:
                t = (max(r0 - 1, 0), min(r1 + 1, h - 1), 0, w - 1)
            else:
                t = (0, h - 1, max(c0 - 1, 0), min(c1 + 1, w - 1))
        elif track == "foot":
            t = (r0, r1, c0, c1)
        else:
            t = None
        tracks.append(t)
    for t in tracks:
        if t:
            _fill(g, *t, trail)
    for b in bl:
        _fill(g, b[0], b[1], b[2], b[3], trail)
    landed = []
    for b in bl:
        nb = (b[0], b[1], b[2], b[3]) if stay else _dest(b, h, w, dest)
        landed.append(nb)
        _fill(g, *nb, blockcolor)
    if top == "track":
        for t, nb in zip(tracks, landed):
            if not t:
                continue
            for y in range(t[0], t[1] + 1):
                for x in range(t[2], t[3] + 1):
                    if not (nb[0] <= y <= nb[1] and nb[2] <= x <= nb[3]):
                        g[y][x] = trail
    return g


def a_footprint_only(inp, out):
    return _render(inp, track="foot")


def b_trail_five(inp, out):
    return _render(inp, trail=5)


def c_one_short(inp, out):
    return _render(inp, dest="short")


def d_block_stays(inp, out):
    return _render(inp, stay=True)


def e_track_over_other_blocks(inp, out):
    return _render(inp, top="track")


def f_half_way(inp, out):
    return _render(inp, dest="half")


def g_perpendicular_band(inp, out):
    return _render(inp, track="perp")


def h_whole_field_wiped(inp, out):
    return _render(inp, allbg=True)


def i_largest_block_only(inp, out):
    return _render(inp, which="largest")


def j_mirrored_across_other_axis(inp, out):
    return _render(inp, dest="mirror")


def k_band_one_wider(inp, out):
    return _render(inp, track="wide")


def l_no_wipe(inp, out):
    return _render(inp, track="none")


ALTERNATIVES = [
    ("only the cells the block vacates become 7, the rest of the band keeps its color", a_footprint_only),
    ("the track is wiped with 5 instead of 7", b_trail_five),
    ("the block lands one cell short of the opposite edge", c_one_short),
    ("the block stays in place and only the track is wiped", d_block_stays),
    ("a track also wipes blocks that landed from other blocks", e_track_over_other_blocks),
    ("the block moves only half way to the opposite edge", f_half_way),
    ("the wiped band runs along the other axis (columns for a side block, rows for a top block)", g_perpendicular_band),
    ("every non-block cell turns 7", h_whole_field_wiped),
    ("only the largest block moves and wipes", i_largest_block_only),
    ("the block lands at the opposite edge mirrored on the other axis", j_mirrored_across_other_axis),
    ("the wiped band is one row or column wider on each side of the block's span", k_band_one_wider),
    ("the block moves but no track is wiped", l_no_wipe),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/b25e450b.json'))
    pairs = task["train"]
    ref = [_render(p["input"]) for p in pairs]
    print("reference matches:", [r == p["output"] for r, p in zip(ref, pairs)])
    for desc, f in ALTERNATIVES:
        n = 0
        flags = []
        for p in pairs:
            g = f(p["input"], p["output"])
            ok = g is not None and _valid(g) and g != p["output"]
            n += ok
            flags.append(ok)
        print(n, len(pairs), flags, desc)
