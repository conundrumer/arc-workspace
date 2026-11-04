from pathlib import Path
import json
import copy

def objects(inp):
    """Return list of (color, r0, c0, side) in reading order of top-left corner,
    with box grid (side x side, bg=0) and the missing corner ('TL','TR','BL','BR')."""
    cells = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v:
                cells.setdefault(v, []).append((r, c))
    objs = []
    for col, cs in cells.items():
        r0 = min(r for r, _ in cs); r1 = max(r for r, _ in cs)
        c0 = min(c for _, c in cs); c1 = max(c for _, c in cs)
        s = r1 - r0 + 1
        box = [[inp[r][c] if inp[r][c] == col else 0 for c in range(c0, c1 + 1)]
               for r in range(r0, r1 + 1)]
        miss = None
        for name, (rr, cc) in {"TL": (0, 0), "TR": (0, s - 1), "BL": (s - 1, 0), "BR": (s - 1, s - 1)}.items():
            if box[rr][cc] == 0:
                miss = name
        objs.append(dict(color=col, r0=r0, c0=c0, side=s, box=box, miss=miss))
    objs.sort(key=lambda o: (o["r0"], o["c0"]))
    return objs

OPP = {"TL": "BR", "BR": "TL", "TR": "BL", "BL": "TR"}
SAME = {k: k for k in OPP}
HFLIP = {"TL": "TR", "TR": "TL", "BL": "BR", "BR": "BL"}
VFLIP = {"TL": "BL", "BL": "TL", "TR": "BR", "BR": "TR"}

def compose(objs, quad_of, gap=0, fill_hole=False, boxfn=None):
    s = objs[0]["side"]
    n = 2 * s + gap
    g = [[0] * n for _ in range(n)]
    off = {"TL": (0, 0), "TR": (0, s + gap), "BL": (s + gap, 0), "BR": (s + gap, s + gap)}
    for i, o in enumerate(objs):
        q = quad_of(i, o)
        box = o["box"]
        if fill_hole:
            box = [[o["color"] for _ in row] for row in box]
        if boxfn:
            box = boxfn(box)
        r, c = off[q]
        for y in range(s):
            for x in range(s):
                g[r + y][c + x] = box[y][x]
    return g

def ok(g, out):
    return None if g == out else g

def by_map(m):
    def f(inp, out):
        objs = objects(inp)
        return ok(compose(objs, lambda i, o: m[o["miss"]]), out)
    return f

def same_corner(inp, out): return by_map(SAME)(inp, out)
def hflip_only(inp, out): return by_map(HFLIP)(inp, out)
def vflip_only(inp, out): return by_map(VFLIP)(inp, out)

def hole_filled(inp, out):
    objs = objects(inp)
    return ok(compose(objs, lambda i, o: OPP[o["miss"]], fill_hole=True), out)

def mirrored_boxes(inp, out):
    objs = objects(inp)
    return ok(compose(objs, lambda i, o: OPP[o["miss"]], boxfn=lambda b: [r[::-1] for r in b]), out)

def rotated_boxes(inp, out):
    objs = objects(inp)
    rot = lambda b: [list(r) for r in zip(*b[::-1])]
    return ok(compose(objs, lambda i, o: OPP[o["miss"]], boxfn=rot), out)

def reading_order(inp, out):
    objs = objects(inp)
    order = ["TL", "TR", "BL", "BR"]
    return ok(compose(objs, lambda i, o: order[i]), out)

def spaced_by_gap(inp, out):
    objs = objects(inp)
    return ok(compose(objs, lambda i, o: OPP[o["miss"]], gap=1), out)

def swap_tr_bl(inp, out):
    n = len(out); h = n // 2
    g = copy.deepcopy(out)
    for y in range(h):
        for x in range(h):
            g[y][h + x] = out[h + y][x]
            g[h + y][x] = out[y][h + x]
    return ok(g, out)

def drop_last_object(inp, out):
    objs = objects(inp)
    last = objs[-1]
    g = compose(objs[:-1] + [], lambda i, o: OPP[o["miss"]]) if False else None
    s = last["side"]
    g = copy.deepcopy(out)
    q = OPP[last["miss"]]
    r = 0 if q[0] == "T" else s
    c = 0 if q[1] == "L" else s
    for y in range(s):
        for x in range(s):
            g[r + y][c + x] = 0
    return ok(g, out)

def crop_all_objects(inp, out):
    rs = [r for r, row in enumerate(inp) for v in row if v]
    cs = [c for row in inp for c, v in enumerate(row) if v]
    g = [row[min(cs):max(cs) + 1] for row in inp[min(rs):max(rs) + 1]]
    return ok(g, out)

def layout_preserved(inp, out):
    """Quadrant by the object's rank by row, then by column, in the input layout."""
    objs = objects(inp)
    by_row = sorted(range(len(objs)), key=lambda i: (objs[i]["r0"], objs[i]["c0"]))
    top = set(by_row[:2])
    quad = {}
    for half in (by_row[:2], by_row[2:]):
        pair = sorted(half, key=lambda i: objs[i]["c0"])
        for k, i in enumerate(pair):
            quad[i] = ("T" if half is by_row[:2] or set(half) == top else "B") + ("L" if k == 0 else "R")
    return ok(compose(objs, lambda i, o: quad[i]), out)

def transposed_hole(inp, out):
    """Quadrant follows the missing corner transposed across the main diagonal, then opposite."""
    T = {"TL": "TL", "BR": "BR", "TR": "BL", "BL": "TR"}
    objs = objects(inp)
    return ok(compose(objs, lambda i, o: OPP[T[o["miss"]]]), out)

ALTERNATIVES = [
    ("each box goes to the quadrant of its own missing corner instead of the opposite one", same_corner),
    ("box placed in the horizontally opposite quadrant only, keeping its vertical half", hflip_only),
    ("box placed in the vertically opposite quadrant only, keeping its horizontal half", vflip_only),
    ("missing corner cells are filled with the object's color instead of background", hole_filled),
    ("each box is mirrored left-right when placed in its opposite quadrant", mirrored_boxes),
    ("each box is rotated 90 degrees when placed in its opposite quadrant", rotated_boxes),
    ("boxes go to quadrants in input reading order, ignoring the missing corners", reading_order),
    ("a one-cell background gap is left between the boxes, giving a 5x5 output", spaced_by_gap),
    ("the top-right and bottom-left quadrants of the true output are swapped", swap_tr_bl),
    ("the last object in reading order is left out and its quadrant stays background", drop_last_object),
    ("output is the crop of the input's bounding box of all objects", crop_all_objects),
    ("quadrant follows the missing corner transposed over the main diagonal, then opposite", transposed_hole),
]

if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/a61ba2ce.json')))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  ERROR", desc, repr(e)); g = None
            if (g is not None and isinstance(g, list) and g
                    and all(isinstance(r, list) and len(r) == len(g[0]) and r for r in g)
                    and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
                    and g != p["output"]):
                n += 1
        print(n, desc)
