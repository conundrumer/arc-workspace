from pathlib import Path
import json
import copy


def legend(inp):
    rows = []
    r = 0
    while r < len(inp) and inp[r][0] != 0:
        rows.append((inp[r][0], inp[r][1]))
        r += 1
    return rows


def dot_boxes(inp, leg):
    """Per dot color: bounding box (r0, c0, r1, c1) of its cells outside the legend."""
    n = len(leg)
    boxes = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if r < n and c < 2:
                continue
            if v in [d for d, _ in leg]:
                b = boxes.setdefault(v, [r, c, r, c])
                b[0] = min(b[0], r)
                b[1] = min(b[1], c)
                b[2] = max(b[2], r)
                b[3] = max(b[3], c)
    return boxes


def render(inp, order_top_first=True, grow=(1, 1, 1, 1), anchor=(0, 0),
           swap=False, show_dots=True, complete=True, fills=None, solid=False,
           ring_only=False, period=2):
    h, w = len(inp), len(inp[0])
    leg = legend(inp)
    boxes = dot_boxes(inp, leg)
    out = [[0] * w for _ in range(h)]
    seq = list(range(len(leg)))
    # painted last = on top
    seq = seq[::-1] if order_top_first else seq
    for i in seq:
        dot, fill = leg[i]
        if fills is not None:
            fill = fills[i]
        if dot not in boxes:
            continue
        r0, c0, r1, c1 = boxes[dot]
        pr0, pc0 = max(0, r0 - grow[0]), max(0, c0 - grow[1])
        pr1, pc1 = min(h - 1, r1 + grow[2]), min(w - 1, c1 + grow[3])
        ink, bgc = (fill, dot) if swap else (dot, fill)
        for r in range(pr0, pr1 + 1):
            for c in range(pc0, pc1 + 1):
                if ring_only and pr0 < r < pr1 and pc0 < c < pc1:
                    continue
                is_dot = ((r - r0 - anchor[0]) % period == 0
                          and (c - c0 - anchor[1]) % period == 0
                          and r0 <= r <= r1 and c0 <= c <= c1)
                if is_dot and not complete:
                    is_dot = inp[r][c] == dot
                if solid or not show_dots:
                    is_dot = False
                out[r][c] = ink if is_dot else bgc
    return out


def true_model(inp):
    return render(inp)


def alt_reverse_stack(inp, out):
    return render(inp, order_top_first=False)


def alt_no_ring(inp, out):
    return render(inp, grow=(0, 0, 0, 0))


def alt_ring_two(inp, out):
    return render(inp, grow=(2, 2, 2, 2))


def alt_ring_one_sided(inp, out):
    return render(inp, grow=(0, 0, 1, 1))


def alt_swap_colors(inp, out):
    return render(inp, swap=True)


def alt_period_three(inp, out):
    return render(inp, period=3)


def alt_solid_panel(inp, out):
    return render(inp, solid=True)


def alt_ring_only(inp, out):
    return render(inp, ring_only=True)


def alt_shifted_lattice(inp, out):
    return render(inp, anchor=(1, 1))


def alt_fill_off_by_one(inp, out):
    leg = legend(inp)
    fills = [leg[(i + 1) % len(leg)][1] for i in range(len(leg))]
    return render(inp, fills=fills)


def alt_keep_legend(inp, out):
    g = copy.deepcopy(out)
    n = len(legend(inp))
    for r in range(n):
        for c in range(2):
            g[r][c] = inp[r][c]
    return g


def alt_no_fill(inp, out):
    return render(inp, fills=[0] * len(legend(inp)))


ALTERNATIVES = [
    ("overlap goes to the later legend entry instead of the earlier one", alt_reverse_stack),
    ("panel is the dots' bounding box with no surrounding ring", alt_no_ring),
    ("panel ring is two cells wide instead of one", alt_ring_two),
    ("ring grown only on the bottom and right sides", alt_ring_one_sided),
    ("dot color and fill color swapped inside each panel", alt_swap_colors),
    ("dots repeat every third cell instead of every second", alt_period_three),
    ("panels painted solid fill with no dots", alt_solid_panel),
    ("only the ring is filled, the inside of the dot box is left background", alt_ring_only),
    ("dot lattice anchored on the ring corner, shifted one cell", alt_shifted_lattice),
    ("each dot color takes the fill of the next legend row", alt_fill_off_by_one),
    ("legend block copied into the output", alt_keep_legend),
    ("panels have no fill: ring and gaps stay background", alt_no_fill),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/305b1341.json')))
    train = task["train"]
    print("model matches truth:", [true_model(p["input"]) == p["output"] for p in train])
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = f(copy.deepcopy(p["input"]), copy.deepcopy(p["output"]))
            except Exception as e:
                print("ERR", desc, e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, "/", len(train), desc)
