"""Near-miss readings for ARC task 42f83767.

Rule: a stencil color (it vanishes) forms a horizontal strip of blocks. A legend in the
strip's rows gives one color per block. A small composition grid of legend colors lies
elsewhere. Each composition cell becomes a tile: the block whose legend color is that cell's
color, drawn in that color.
"""
import json
from pathlib import Path


def parse(inp, out):
    h, w = len(inp), len(inp[0])
    in_colors = {v for r in inp for v in r}
    out_colors = {v for r in out for v in r}
    vanished = sorted(in_colors - out_colors - {0})
    if len(vanished) != 1:
        return None
    s = vanished[0]
    cells = [(i, j) for i in range(h) for j in range(w) if inp[i][j] == s]
    r0 = min(i for i, _ in cells)
    r1 = max(i for i, _ in cells)
    cols = sorted({j for _, j in cells})
    groups = []
    for j in cols:
        if groups and j == groups[-1][-1] + 1:
            groups[-1].append(j)
        else:
            groups.append([j])
    blocks = [[[1 if inp[i][j] == s else 0 for j in g] for i in range(r0, r1 + 1)] for g in groups]
    legend = []
    for j in range(w):
        for i in range(r0, r1 + 1):
            v = inp[i][j]
            if v not in (0, s) and v not in legend:
                legend.append(v)
    comp_cells = [(i, j) for i in range(h) for j in range(w)
                  if inp[i][j] not in (0, s) and not (r0 <= i <= r1)]
    if not comp_cells or len(legend) != len(blocks):
        return None
    a0 = min(i for i, _ in comp_cells)
    a1 = max(i for i, _ in comp_cells)
    b0 = min(j for _, j in comp_cells)
    b1 = max(j for _, j in comp_cells)
    comp = [[inp[i][j] for j in range(b0, b1 + 1)] for i in range(a0, a1 + 1)]
    return dict(s=s, blocks=blocks, legend=legend, comp=comp,
                bh=len(blocks[0]), bw=len(blocks[0][0]), gap=1)


def render(comp, tile_for, bh, bw):
    """tile_for(color) -> bh x bw grid, or None for a blank tile."""
    out = []
    for row in comp:
        tiles = []
        for c in row:
            t = tile_for(c) if c != 0 else None
            tiles.append(t if t is not None else [[0] * bw for _ in range(bh)])
        for a in range(bh):
            out.append([v for t in tiles for v in t[a]])
    return out


def paint(mask, color):
    return [[color if v else 0 for v in r] for r in mask]


def correct_tile(p, order=None):
    legend = order if order is not None else p["legend"]

    def f(c):
        if c not in legend:
            return None
        return paint(p["blocks"][legend.index(c)], c)
    return f


def wrap(fn):
    def g(inp, out):
        p = parse(inp, out)
        if p is None:
            return None
        res = fn(p, inp, out)
        if res is None or res == out:
            return None
        return res
    return g


def stencil_color_tiles(p, inp, out):
    # Tiles keep the stencil color instead of the legend color.
    return render(p["comp"], lambda c: paint(p["blocks"][p["legend"].index(c)], p["s"]) if c in p["legend"] else None,
                  p["bh"], p["bw"])


def reversed_legend(p, inp, out):
    # Block order read right-to-left.
    return render(p["comp"], correct_tile(p, p["legend"][::-1]), p["bh"], p["bw"])


def sorted_legend(p, inp, out):
    # Legend colors matched to blocks by color value, not by position.
    return render(p["comp"], correct_tile(p, sorted(p["legend"])), p["bh"], p["bw"])


def first_block_only(p, inp, out):
    # Every tile uses the first block's shape.
    return render(p["comp"], lambda c: paint(p["blocks"][0], c), p["bh"], p["bw"])


def solid_tiles(p, inp, out):
    # Tiles are filled solid with the cell color; block shapes are ignored.
    return render(p["comp"], lambda c: [[c] * p["bw"] for _ in range(p["bh"])], p["bh"], p["bw"])


def inverted_shapes(p, inp, out):
    # The complement of each block shape is drawn.
    def f(c):
        if c not in p["legend"]:
            return None
        m = p["blocks"][p["legend"].index(c)]
        return paint([[1 - v for v in r] for r in m], c)
    return render(p["comp"], f, p["bh"], p["bw"])


def mirrored_composition(p, inp, out):
    # Composition read mirrored left-to-right.
    return render([r[::-1] for r in p["comp"]], correct_tile(p), p["bh"], p["bw"])


def dropped_last_row(p, inp, out):
    # Composition crop is one row short.
    return render(p["comp"][:-1], correct_tile(p), p["bh"], p["bw"])


def first_legend_color_only(p, inp, out):
    # Only cells of the first legend color are expanded; others stay blank.
    first = p["legend"][0]
    return render(p["comp"], lambda c: correct_tile(p)(c) if c == first else None, p["bh"], p["bw"])


def tiles_with_gap(p, inp, out):
    # Each tile includes the one-cell gap column that separates blocks in the strip.
    def f(c):
        t = correct_tile(p)(c)
        return None if t is None else [r + [0] for r in t]
    return render(p["comp"], f, p["bh"], p["bw"] + 1)


def mirrored_shapes(p, inp, out):
    # Each block shape is flipped left-to-right.
    def f(c):
        t = correct_tile(p)(c)
        return None if t is None else [r[::-1] for r in t]
    return render(p["comp"], f, p["bh"], p["bw"])


def unexpanded_composition(p, inp, out):
    # The composition is output as is, with no tile expansion.
    return [r[:] for r in p["comp"]]


ALTERNATIVES = [
    ("tiles drawn in the stencil color instead of the legend color", wrap(stencil_color_tiles)),
    ("legend read right-to-left when matching colors to blocks", wrap(reversed_legend)),
    ("legend colors matched to blocks in color-value order", wrap(sorted_legend)),
    ("every tile uses the first block's shape", wrap(first_block_only)),
    ("tiles filled solid, block shapes ignored", wrap(solid_tiles)),
    ("complement of each block shape drawn", wrap(inverted_shapes)),
    ("composition mirrored left-to-right before expanding", wrap(mirrored_composition)),
    ("composition crop one row short", wrap(dropped_last_row)),
    ("only cells of the first legend color expanded", wrap(first_legend_color_only)),
    ("tile width includes the gap column between blocks", wrap(tiles_with_gap)),
    ("each block shape flipped left-to-right", wrap(mirrored_shapes)),
    ("composition output unexpanded, no tiles", wrap(unexpanded_composition)),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/42f83767.json"))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for p in pairs:
        q = parse(p["input"], p["output"])
        assert q and render(q["comp"], correct_tile(q), q["bh"], q["bw"]) == p["output"], "parse check failed"
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
