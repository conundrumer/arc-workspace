from pathlib import Path
import json
from collections import Counter

DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
OPP = {"up": "down", "down": "up", "left": "right", "right": "left"}
ROT = {"up": "right", "right": "down", "down": "left", "left": "up"}


def analyse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    ink = {c: n for c, n in cnt.items() if c != bg}
    body = max(ink, key=lambda c: ink[c])
    mark = min(ink, key=lambda c: ink[c])
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != bg]
    r0 = min(r for r, c in cells)
    r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells)
    c1 = max(c for r, c in cells)
    mr, mc = next((r, c) for r, c in cells if inp[r][c] == mark)
    side = min([("up", mr - r0), ("down", r1 - mr), ("left", mc - c0), ("right", c1 - mc)],
               key=lambda t: t[1])[0]
    return dict(h=h, w=w, bg=bg, body=body, mark=mark, mpos=(mr, mc), side=side,
                box=(r0, c0, r1, c1))


def cast(inp, d, color=None, overwrite=False, stop_at_ink=False, drop_last=0,
         max_len=None, width=1, start=None):
    a = analyse(inp)
    g = [row[:] for row in inp]
    color = a["mark"] if color is None else color
    dr, dc = DIRS[d]
    pr, pc = dr * 0, dc * 0
    r, c = start if start else a["mpos"]
    # perpendicular offsets for thick rays
    offs = [0] if width == 1 else [-1, 0, 1]
    cells = []
    r, c = r + dr, c + dc
    while 0 <= r < a["h"] and 0 <= c < a["w"]:
        cells.append((r, c))
        r, c = r + dr, c + dc
    if drop_last:
        cells = cells[:len(cells) - drop_last]
    if max_len is not None:
        cells = cells[:max_len]
    for (r, c) in cells:
        for o in offs:
            rr, cc = (r + o, c) if dr == 0 else (r, c + o)
            if not (0 <= rr < a["h"] and 0 <= cc < a["w"]):
                continue
            if g[rr][cc] == a["bg"] or overwrite:
                g[rr][cc] = color
        if stop_at_ink and g[r][c] != a["bg"]:
            break
    return g


def true_dir(inp):
    return OPP[analyse(inp)["side"]]


def reverse_dir(inp, out):
    return cast(inp, analyse(inp)["side"])


def body_color(inp, out):
    a = analyse(inp)
    return cast(inp, true_dir(inp), color=a["body"])


def overwrite_body(inp, out):
    return cast(inp, true_dir(inp), overwrite=True)


def blocked(inp, out):
    return cast(inp, true_dir(inp), stop_at_ink=True)


def one_cell(inp, out):
    return cast(inp, true_dir(inp), max_len=1)


def short_by_one(inp, out):
    return cast(inp, true_dir(inp), drop_last=1)


def both_dirs(inp, out):
    g = cast(inp, true_dir(inp))
    a = analyse(inp)
    dr, dc = DIRS[a["side"]]
    r, c = a["mpos"][0] + dr, a["mpos"][1] + dc
    while 0 <= r < a["h"] and 0 <= c < a["w"]:
        if g[r][c] == a["bg"]:
            g[r][c] = a["mark"]
        r, c = r + dr, c + dc
    return g


def four_dirs(inp, out):
    g = inp
    for d in DIRS:
        h = cast(g, d)
        g = h
    return g


def perpendicular(inp, out):
    return cast(inp, ROT[true_dir(inp)])


def thick(inp, out):
    return cast(inp, true_dir(inp), width=3)


def erase_mark(inp, out):
    a = analyse(inp)
    g = cast(inp, true_dir(inp))
    r, c = a["mpos"]
    g[r][c] = a["bg"]
    return g


def from_bbox_centre(inp, out):
    # ray cast from the middle of the shape along the true direction's axis
    a = analyse(inp)
    r0, c0, r1, c1 = a["box"]
    d = true_dir(inp)
    cr, cc = (r0 + r1) // 2, (c0 + c1) // 2
    if d in ("left", "right"):
        start = (cr, cc)
    else:
        start = (cr, cc)
    g = [row[:] for row in inp]
    dr, dc = DIRS[d]
    r, c = start
    while 0 <= r < a["h"] and 0 <= c < a["w"]:
        if g[r][c] == a["bg"]:
            g[r][c] = a["mark"]
        r, c = r + dr, c + dc
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("ray goes toward the side the mark sits on instead of away", reverse_dir),
    ("ray is painted with the body color instead of the mark color", body_color),
    ("ray overwrites body cells it crosses", overwrite_body),
    ("ray stops at the first non-background cell", blocked),
    ("ray is one cell long", one_cell),
    ("ray stops one cell short of the grid edge", short_by_one),
    ("ray is cast in both the true and the reverse direction", both_dirs),
    ("ray is cast in all four directions", four_dirs),
    ("ray goes perpendicular to the true direction", perpendicular),
    ("ray is three cells wide", thick),
    ("mark cell is erased after casting", erase_mark),
    ("no ray is drawn, input returned", unchanged),
]


def valid(g, out):
    if g is None:
        return False
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/25d487eb.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, e)
                g = None
            n += valid(g, p["output"])
        print(n, desc)
