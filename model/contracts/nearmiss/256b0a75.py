import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != bg and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] == inp[r][c]:
                                seen.add((ny, nx))
                                st.append((ny, nx))
                comps.append(cells)
    pieces = [cs for cs in comps if len(cs) >= 3]
    pcells = {p for cs in pieces for p in cs}
    cnt = Counter(inp[y][x] for y, x in pcells)
    frame = cnt.most_common(1)[0][0]
    fill = [k for k in cnt if k != frame][0]
    ys = [y for y, _ in pcells]
    xs = [x for _, x in pcells]
    box = (min(ys), max(ys), min(xs), max(xs))
    dots = {(y, x): inp[y][x] for y in range(h) for x in range(w)
            if inp[y][x] != bg and (y, x) not in pcells}
    return bg, frame, fill, box, pcells, dots


def _solve(inp, fill_color=None, interior_color=None, band=True, inset=0, grow=0,
           arm_dir="out", arm_stop=True, arm_color=None, sides="hv", full_border=True,
           keep_pieces=False, all_bg=False, arm_trim=0, restore_dots=True):
    h, w = len(inp), len(inp[0])
    bg, frame, fill, box, pcells, dots = _parse(inp)
    if fill_color is not None:
        fill = fill_color
    ic = fill if interior_color is None else interior_color
    r0, r1, c0, c1 = box
    r0 += inset; r1 -= inset; c0 += inset; c1 -= inset
    g = [row[:] for row in inp]
    for (y, x) in pcells:
        g[y][x] = bg
    if all_bg:
        for y in range(h):
            for x in range(w):
                if (y, x) not in dots:
                    g[y][x] = ic
    # band fill and marks
    bl = lambda v: v
    for y in range(h):
        for x in range(w):
            inr = r0 - grow <= y <= r1 + grow
            inc = c0 - grow <= x <= c1 + grow
            inside = r0 <= y <= r1 and c0 <= x <= c1
            if inside:
                g[y][x] = ic
            elif band and ((inr and "h" in sides) or (inc and "v" in sides)):
                g[y][x] = ic
    # arms
    for (y, x), col in dots.items():
        inr = r0 - grow <= y <= r1 + grow
        inc = c0 - grow <= x <= c1 + grow
        d = None
        if inr and "h" in sides and not (r0 <= y <= r1 and c0 <= x <= c1):
            d = (0, -1) if x < c0 else (0, 1)
        elif inc and "v" in sides and not (r0 <= y <= r1 and c0 <= x <= c1):
            d = (-1, 0) if y < r0 else (1, 0)
        if d is None:
            continue
        ac = col if arm_color is None else arm_color
        out_d = d
        in_d = (-d[0], -d[1])
        use = out_d if arm_dir == "out" else in_d
        ny, nx = y + use[0], x + use[1]
        n = 0
        while 0 <= ny < h and 0 <= nx < w:
            if arm_stop and (ny, nx) in dots:
                break
            if arm_dir == "in" and (r0 <= ny <= r1 and c0 <= nx <= c1):
                break
            n += 1
            g[ny][nx] = ac
            ny += use[0]
            nx += use[1]
        if arm_trim and arm_dir == "out":
            for k in range(1, arm_trim + 1):
                ty, tx = ny - use[0] * k, nx - use[1] * k
                if 0 <= ty < h and 0 <= tx < w and (ty, tx) not in dots:
                    g[ty][tx] = ic if band else inp[ty][tx]
    for (y, x), col in dots.items():
        if restore_dots:
            g[y][x] = col
    # frame
    for y in range(r0, r1 + 1):
        for x in range(c0, c1 + 1):
            edge = y in (r0, r1) or x in (c0, c1)
            if edge:
                if full_border or (y, x) in pcells:
                    g[y][x] = frame
    if keep_pieces:
        for (y, x) in pcells:
            g[y][x] = inp[y][x]
    return g


def _wrap(**kw):
    return lambda inp, out: _solve(inp, **kw)


def _fill_frame(inp, out):
    bg, frame, fill, box, pcells, dots = _parse(inp)
    return _solve(inp, fill_color=frame)


def _fill_common_dot(inp, out):
    bg, frame, fill, box, pcells, dots = _parse(inp)
    cnt = Counter(dots.values())
    best = max(cnt.items(), key=lambda kv: (kv[1], -kv[0]))[0]
    if best == fill:
        best = min((k for k in cnt if k != fill), key=lambda k: -cnt[k], default=None)
        if best is None:
            return None
    return _solve(inp, fill_color=best)


def _arms_ignore_marks(inp, out):
    return _solve(inp, arm_stop=False, restore_dots=False)


def _interior_frame_color(inp, out):
    bg, frame, fill, box, pcells, dots = _parse(inp)
    return _solve(inp, interior_color=frame, band=True)


ALTERNATIVES = [
    ("fill color is taken as the frame color (all L pieces read as one color, so box and bands are filled with it)", _fill_frame),
    ("fill color is the most common dot color instead of the odd-colored L piece", _fill_common_dot),
    ("only the box interior is filled; the aligned bands outside the box stay background", _wrap(band=False)),
    ("dot arms run toward the box (dot color between dot and box) instead of outward to the edge", _wrap(arm_dir="in")),
    ("dot arms run outward but do not stop at the next dot in the same line", _arms_ignore_marks),
    ("box border is not completed: only the original L pieces are recolored to the frame color", _wrap(full_border=False)),
    ("box taken one cell smaller on every side (frame drawn one cell inside the L pieces)", _wrap(inset=1)),
    ("bands one cell too wide on each side, so dots beside the band also get arms", _wrap(grow=1)),
    ("only dots left and right of the box get arms and band fill; top and bottom bands ignored", _wrap(sides="h")),
    ("only dots above and below the box get arms and band fill; left and right bands ignored", _wrap(sides="v")),
    ("arms are painted in the fill color instead of the dot color", _wrap(arm_color="fill")),
    ("odd-colored L piece keeps its input color in the frame instead of becoming the frame color", _wrap(keep_pieces=True)),
]


def _arm_fill_fix(inp, out):
    return None


def _make_arm_fill():
    def f(inp, out):
        bg, frame, fill, box, pcells, dots = _parse(inp)
        return _solve(inp, arm_color=fill)
    return f


ALTERNATIVES[10] = (ALTERNATIVES[10][0], _make_arm_fill())


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/256b0a75.json'))
    train = task["train"]
    base = [_solve(p["input"]) == p["output"] for p in train]
    print("baseline solver matches:", base)
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
