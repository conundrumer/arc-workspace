import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _block(g):
    bg = _bg(g)
    cells = [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v != bg]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return bg, r0, c0, r1, c1


def _paint(inp, colors, h=None, w=None, gap=0, corners=("tl", "tr", "bl", "br"), keep_block=True):
    """Paint a copy at each diagonal corner of the block, in the given color.

    colors maps corner name to color. h, w are the copy size; gap is extra
    clearance between block and copy.
    """
    bg, r0, c0, r1, c1 = _block(inp)
    bh, bw = r1 - r0 + 1, c1 - c0 + 1
    h = bh if h is None else h
    w = bw if w is None else w
    g = [row[:] for row in inp]
    if not keep_block:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                g[r][c] = bg
    n, m = len(g), len(g[0])
    for k in corners:
        if k[0] == "t":
            rs = range(r0 - gap - h, r0 - gap)
        else:
            rs = range(r1 + 1 + gap, r1 + 1 + gap + h)
        if k[1] == "l":
            cs = range(c0 - gap - w, c0 - gap)
        else:
            cs = range(c1 + 1 + gap, c1 + 1 + gap + w)
        for r in rs:
            for c in cs:
                if 0 <= r < n and 0 <= c < m:
                    g[r][c] = colors[k]
    return g


def _corner_colors(inp):
    bg, r0, c0, r1, c1 = _block(inp)
    return {"tl": inp[r0][c0], "tr": inp[r0][c1], "bl": inp[r1][c0], "br": inp[r1][c1]}


def same_corner(inp, out):
    return _paint(inp, _corner_colors(inp))


def mirror_h(inp, out):
    k = _corner_colors(inp)
    return _paint(inp, {"tl": k["tr"], "tr": k["tl"], "bl": k["br"], "br": k["bl"]})


def mirror_v(inp, out):
    k = _corner_colors(inp)
    return _paint(inp, {"tl": k["bl"], "tr": k["br"], "bl": k["tl"], "br": k["tr"]})


def rotate_cw(inp, out):
    k = _corner_colors(inp)
    return _paint(inp, {"tl": k["bl"], "tr": k["tl"], "br": k["tr"], "bl": k["br"]})


def top_only(inp, out):
    k = _corner_colors(inp)
    opp = {"tl": k["br"], "tr": k["bl"], "bl": k["tr"], "br": k["tl"]}
    return _paint(inp, opp, corners=("tl", "tr"))


def gap_one(inp, out):
    k = _corner_colors(inp)
    opp = {"tl": k["br"], "tr": k["bl"], "bl": k["tr"], "br": k["tl"]}
    return _paint(inp, opp, gap=1)


def single_cell(inp, out):
    k = _corner_colors(inp)
    opp = {"tl": k["br"], "tr": k["bl"], "bl": k["tr"], "br": k["tl"]}
    return _paint(inp, opp, h=1, w=1)


def triple_size(inp, out):
    k = _corner_colors(inp)
    opp = {"tl": k["br"], "tr": k["bl"], "bl": k["tr"], "br": k["tl"]}
    return _paint(inp, opp, h=3, w=3)


def one_color_all(inp, out):
    k = _corner_colors(inp)
    return _paint(inp, {c: k["br"] for c in k})


def block_erased(inp, out):
    k = _corner_colors(inp)
    opp = {"tl": k["br"], "tr": k["bl"], "bl": k["tr"], "br": k["tl"]}
    return _paint(inp, opp, keep_block=False)


def bottom_only(inp, out):
    k = _corner_colors(inp)
    opp = {"tl": k["br"], "tr": k["bl"], "bl": k["tr"], "br": k["tl"]}
    return _paint(inp, opp, corners=("bl", "br"))


ALTERNATIVES = [
    ("each copy takes the color of the block corner it touches, not the opposite one", same_corner),
    ("copies take the color of the horizontally adjacent block corner", mirror_h),
    ("copies take the color of the vertically adjacent block corner", mirror_v),
    ("corner colors rotate clockwise instead of going to the opposite corner", rotate_cw),
    ("only the two copies above the block are painted", top_only),
    ("only the two copies below the block are painted", bottom_only),
    ("copies sit one cell further from the block, leaving a gap", gap_one),
    ("copies are single cells instead of block-sized squares", single_cell),
    ("copies are 3x3 instead of block-sized", triple_size),
    ("all four copies use the bottom-right block color", one_color_all),
    ("the original block is erased and only the copies remain", block_erased),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/93b581b8.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
