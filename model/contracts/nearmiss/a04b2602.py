import json
from pathlib import Path

BG, BLOCK, MARK, HALO = 0, 3, 2, 1
N8 = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]
N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def boxes(inp, diag=False):
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    nb = N8 if diag else N4
    for r in range(h):
        for c in range(w):
            if inp[r][c] == BLOCK and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x))
                    for dy, dx in nb:
                        a, b = y + dy, x + dx
                        if 0 <= a < h and 0 <= b < w and inp[a][b] == BLOCK and (a, b) not in seen:
                            seen.add((a, b))
                            st.append((a, b))
                rs = [p[0] for p in cells]
                cs = [p[1] for p in cells]
                res.append((min(rs), min(cs), max(rs), max(cs)))
    return res


def marks(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == MARK]


def inside(p, b, grow=0, shrink=0):
    r, c = p
    return b[0] - grow + shrink <= r <= b[2] + grow - shrink and b[1] - grow + shrink <= c <= b[3] + grow - shrink


def render(inp, triggers, offsets=N8, color=HALO, only=None, keep_marks=True, clear_center=False):
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    trig = set(triggers)
    for r, c in triggers:
        for dy, dx in offsets:
            a, b = r + dy, c + dx
            if not (0 <= a < h and 0 <= b < w):
                continue
            if keep_marks and inp[a][b] == MARK and (a, b) in trig:
                continue
            if only is not None and not only(inp[a][b]):
                continue
            g[a][b] = color
        if clear_center:
            g[r][c] = color
    return g


def inside_marks(inp, grow=0, shrink=0, diag=False):
    bs = boxes(inp, diag)
    return [p for p in marks(inp) if any(inside(p, b, grow, shrink) for b in bs)]


def alt_plus(inp, out):
    return render(inp, inside_marks(inp), offsets=N4)


def alt_radius2(inp, out):
    off = [(a, b) for a in range(-2, 3) for b in range(-2, 3) if (a, b) != (0, 0)]
    return render(inp, inside_marks(inp), offsets=off)


def alt_block_only(inp, out):
    return render(inp, inside_marks(inp), only=lambda v: v == BLOCK)


def alt_field_only(inp, out):
    return render(inp, inside_marks(inp), only=lambda v: v == BG)


def alt_all_marks(inp, out):
    return render(inp, marks(inp))


def alt_strays_only(inp, out):
    ins = set(inside_marks(inp))
    return render(inp, [p for p in marks(inp) if p not in ins])


def alt_interior_only(inp, out):
    return render(inp, inside_marks(inp, shrink=1))


def alt_box_grown(inp, out):
    return render(inp, inside_marks(inp, grow=1))


def alt_clear_center(inp, out):
    return render(inp, inside_marks(inp), clear_center=True)


def alt_overwrite_marks(inp, out):
    return render(inp, inside_marks(inp), keep_marks=False)


def alt_wrong_color(inp, out):
    return render(inp, inside_marks(inp), color=4)


def alt_eight_connected(inp, out):
    return render(inp, inside_marks(inp, diag=True))


def alt_first_per_box(inp, out):
    bs = boxes(inp)
    trig = []
    for b in bs:
        for p in marks(inp):  # row-major order
            if inside(p, b):
                trig.append(p)
                break
    return render(inp, trig)


ALTERNATIVES = [
    ("halo only on the four orthogonal neighbours", alt_plus),
    ("halo spans two cells around each inside mark", alt_radius2),
    ("halo paints only block cells, not field cells", alt_block_only),
    ("halo paints only field cells, not block cells", alt_field_only),
    ("every mark cell gets a halo, including stray marks outside rectangles", alt_all_marks),
    ("only stray marks outside rectangles get a halo", alt_strays_only),
    ("only marks strictly inside the rectangle, not on its border cells, get a halo", alt_interior_only),
    ("marks one cell outside a rectangle's bounding box count as inside", alt_box_grown),
    ("the inside mark's own cell is also painted with the halo color", alt_clear_center),
    ("a halo overwrites neighbouring inside marks", alt_overwrite_marks),
    ("halo color is 4 instead of 1", alt_wrong_color),
    ("only the first inside mark of each rectangle gets a halo", alt_first_per_box),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/a04b2602.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
