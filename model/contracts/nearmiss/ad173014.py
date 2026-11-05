import json
import math
from pathlib import Path


def _boxes(inp):
    """Frame (color 2) components as dicts, in clockwise order around the loop centre."""
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 2 and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == 2 and (ny, nx) not in seen:
                                seen.add((ny, nx))
                                stack.append((ny, nx))
                comps.append(cells)
    ones = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == 1]
    lr = (min(r for r, _ in ones) + max(r for r, _ in ones)) / 2
    lc = (min(c for _, c in ones) + max(c for _, c in ones)) / 2
    boxes = []
    for cells in comps:
        r0 = min(r for r, _ in cells)
        r1 = max(r for r, _ in cells)
        c0 = min(c for _, c in cells)
        c1 = max(c for _, c in cells)
        shape = [(r, c) for r in range(r0 + 1, r1) for c in range(c0 + 1, c1) if inp[r][c] != 0]
        col = inp[shape[0][0]][shape[0][1]] if shape else 0
        ang = math.atan2((r0 + r1) / 2 - lr, (c0 + c1) / 2 - lc)
        boxes.append(dict(r0=r0, r1=r1, c0=c0, c1=c1, cells=cells, shape=shape, color=col, ang=ang))
    boxes.sort(key=lambda b: b["ang"])
    return boxes


def _recolor(inp, boxes, newcols):
    g = [row[:] for row in inp]
    for b, col in zip(boxes, newcols):
        for r, c in b["shape"]:
            g[r][c] = col
    return g


def _cw(inp, k):
    bs = _boxes(inp)
    n = len(bs)
    return _recolor(inp, bs, [bs[(i + k) % n]["color"] for i in range(n)])


def counter_clockwise(inp, out):
    return _cw(inp, -1)


def two_steps(inp, out):
    return _cw(inp, 2)


def no_wraparound(inp, out):
    bs = _boxes(inp)
    n = len(bs)
    cols = [bs[(i + 1) % n]["color"] for i in range(n)]
    cols[-1] = bs[-1]["color"]
    return _recolor(inp, bs, cols)


def next_larger_color(inp, out):
    bs = _boxes(inp)
    order = sorted(bs, key=lambda b: b["color"])
    nxt = {id(order[i]): order[(i + 1) % len(order)]["color"] for i in range(len(order))}
    return _recolor(inp, bs, [nxt[id(b)] for b in bs])


def swap_neighbour_pairs(inp, out):
    bs = _boxes(inp)
    n = len(bs)
    cols = [b["color"] for b in bs]
    for i in range(0, n - 1, 2):
        cols[i], cols[i + 1] = cols[i + 1], cols[i]
    return _recolor(inp, bs, cols)


def frame_takes_new_color(inp, out):
    bs = _boxes(inp)
    n = len(bs)
    g = _cw(inp, 1)
    for i, b in enumerate(bs):
        for r, c in b["cells"]:
            g[r][c] = bs[(i + 1) % n]["color"]
    return g


def shape_moves_not_color(inp, out):
    """The next box's shape is copied (centred) into each box, with the next box's color."""
    bs = _boxes(inp)
    n = len(bs)
    g = [row[:] for row in inp]
    for b in bs:
        for r, c in b["shape"]:
            g[r][c] = 0
    for i, b in enumerate(bs):
        s = bs[(i + 1) % n]
        sr0 = min(r for r, _ in s["shape"])
        sc0 = min(c for _, c in s["shape"])
        sh = max(r for r, _ in s["shape"]) - sr0 + 1
        sw = max(c for _, c in s["shape"]) - sc0 + 1
        ih = b["r1"] - b["r0"] - 1
        iw = b["c1"] - b["c0"] - 1
        orr = b["r0"] + 1 + (ih - sh) // 2
        occ = b["c0"] + 1 + (iw - sw) // 2
        for r, c in s["shape"]:
            g[orr + r - sr0][occ + c - sc0] = s["color"]
    return g


def only_topmost_changes(inp, out):
    bs = _boxes(inp)
    top = min(bs, key=lambda b: (b["r0"], b["c0"]))
    g = [row[:] for row in inp]
    for r, c in top["shape"]:
        g[r][c] = out[r][c]
    return g


def all_take_topmost_color(inp, out):
    bs = _boxes(inp)
    top = min(bs, key=lambda b: (b["r0"], b["c0"]))
    return _recolor(inp, bs, [top["color"]] * len(bs))


def crop_to_loop(inp, out):
    ones = [(r, c) for r in range(len(out)) for c in range(len(out[0])) if out[r][c] == 1]
    r0 = min(r for r, _ in ones)
    r1 = max(r for r, _ in ones)
    c0 = min(c for _, c in ones)
    c1 = max(c for _, c in ones)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("each shape takes the color of the previous box (counter-clockwise) instead of the next box", counter_clockwise),
    ("each shape takes the color from two boxes on along the loop", two_steps),
    ("the cycle is a chain: the last box in order keeps its own color instead of wrapping to the first", no_wraparound),
    ("each shape takes the next larger color among the shape colors, cyclically, ignoring loop order", next_larger_color),
    ("neighbouring boxes swap colors in pairs instead of rotating around the whole loop", swap_neighbour_pairs),
    ("the frames take the new color as well as the shapes", frame_takes_new_color),
    ("the next box's shape geometry is copied into each box (centred), not only its color", shape_moves_not_color),
    ("only the topmost box's shape is recolored; the other boxes are left alone", only_topmost_changes),
    ("every shape takes the color of the topmost box's shape", all_take_topmost_color),
    ("the answer is cropped to the bounding box of the loop", crop_to_loop),
    ("the input is returned unchanged", unchanged),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/ad173014.json"))
    train = task["train"]
    # sanity: clockwise-next reading reproduces the truth
    print("sanity clockwise == truth:", [_cw(p["input"], 1) == p["output"] for p in train])
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            ok = (
                g is not None
                and len(g) > 0
                and all(isinstance(row, list) and len(row) == len(g[0]) for row in g)
                and all(isinstance(v, int) and 0 <= v <= 9 for row in g for v in row)
                and g != p["output"]
            )
            n += ok
        print(f"{n}/{len(train)}  {desc}")
