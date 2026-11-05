"""Near-miss rules for ARC task 98c475bf."""
import json
from pathlib import Path


def _copy(g):
    return [r[:] for r in g]


def _parts(inp, out):
    """Return facts both grids share: border color, mark color, figure color,
    line rows, and the cells of the shape in out."""
    h, w = len(out), len(out[0])
    bc = out[0][0]
    cols = {v for r in out for v in r} - {0, bc}
    mc = next(iter(cols))
    lr = next(r for r in range(h) if out[r][1] == mc and out[r][w - 2] == mc)
    shape = [(r, c) for r in range(h) for c in range(1, w - 1)
             if out[r][c] == mc and r != lr]
    icols = {v for r in inp for v in r} - {0, bc, mc}
    dc = next(iter(icols))
    ilr = next(r for r in range(h) if inp[r][1] == dc and inp[r][w - 2] == dc)
    ishape = [(r, c) for r in range(h) for c in range(1, w - 1)
              if inp[r][c] == dc and r != ilr]
    return h, w, bc, mc, lr, shape, dc, ilr, ishape


def recolor_figure_color(inp, out):
    h, w, bc, mc, lr, shape, dc, ilr, ishape = _parts(inp, out)
    g = _copy(out)
    for r in range(h):
        for c in range(w):
            if g[r][c] == mc:
                g[r][c] = dc
    return g


def recolor_border_color(inp, out):
    h, w, bc, mc, lr, shape, dc, ilr, ishape = _parts(inp, out)
    g = _copy(out)
    for r in range(h):
        for c in range(1, w - 1):
            if g[r][c] == mc:
                g[r][c] = bc
    return g


def keep_original_figure(inp, out):
    h, w, bc, mc, lr, shape, dc, ilr, ishape = _parts(inp, out)
    g = _copy(out)
    for r in range(h):
        for c in range(1, w - 1):
            if inp[r][c] == dc and g[r][c] == 0:
                g[r][c] = dc
    return g


def line_at_figure_row(inp, out):
    h, w, bc, mc, lr, shape, dc, ilr, ishape = _parts(inp, out)
    d = ilr - lr
    g = _copy(out)
    for r in range(h):
        for c in range(1, w - 1):
            g[r][c] = 0
    for r in range(h):
        for c in range(1, w - 1):
            if out[r][c] == mc and 0 <= r + d < h:
                g[r + d][c] = mc
    return g


def line_misses_shape_center(inp, out):
    h, w, bc, mc, lr, shape, dc, ilr, ishape = _parts(inp, out)
    cs = [c for _, c in shape]
    g = _copy(out)
    g[lr][(min(cs) + max(cs)) // 2] = 0
    return g


def shape_omitted(inp, out):
    h, w, bc, mc, lr, shape, dc, ilr, ishape = _parts(inp, out)
    g = _copy(out)
    for r, c in shape:
        g[r][c] = 0
    return g


def mirrored_horizontally(inp, out):
    h, w, bc, mc, lr, shape, dc, ilr, ishape = _parts(inp, out)
    g = _copy(out)
    for r in range(h):
        g[r][1:w - 1] = out[r][1:w - 1][::-1]
    return g


def shape_off_by_one_column(inp, out):
    h, w, bc, mc, lr, shape, dc, ilr, ishape = _parts(inp, out)
    g = _copy(out)
    for r, c in shape:
        g[r][c] = 0
    for r, c in shape:
        if c + 1 < w - 1:
            g[r][c + 1] = mc
    return g


def shape_stays_at_figure_column(inp, out):
    h, w, bc, mc, lr, shape, dc, ilr, ishape = _parts(inp, out)
    oc = [c for _, c in shape]
    ic = [c for _, c in ishape]
    d = (min(ic) + max(ic)) // 2 - (min(oc) + max(oc)) // 2
    g = _copy(out)
    for r, c in shape:
        g[r][c] = 0
    for r, c in shape:
        if 1 <= c + d < w - 1:
            g[r][c + d] = mc
    return g


def line_spans_border(inp, out):
    h, w, bc, mc, lr, shape, dc, ilr, ishape = _parts(inp, out)
    g = _copy(out)
    g[lr][0] = mc
    g[lr][w - 1] = mc
    return g


def shape_filled_solid(inp, out):
    h, w, bc, mc, lr, shape, dc, ilr, ishape = _parts(inp, out)
    rs = [r for r, _ in shape]
    cs = [c for _, c in shape]
    g = _copy(out)
    for r in range(min(rs), max(rs) + 1):
        for c in range(min(cs), max(cs) + 1):
            g[r][c] = mc
    return g


def shape_above_line_only(inp, out):
    h, w, bc, mc, lr, shape, dc, ilr, ishape = _parts(inp, out)
    g = _copy(out)
    for r, c in shape:
        if r > lr:
            g[r][c] = 0
    return g


ALTERNATIVES = [
    ("line and shape drawn in the old figure's color instead of the marker color", recolor_figure_color),
    ("line and shape drawn in the border color", recolor_border_color),
    ("old figure left in place beside the new one", keep_original_figure),
    ("new figure drawn at the old figure's line row instead of the marker row", line_at_figure_row),
    ("line leaves the shape's center column unlit", line_misses_shape_center),
    ("only the line is drawn, no shape", shape_omitted),
    ("whole canvas mirrored left to right", mirrored_horizontally),
    ("shape offset one column to the right", shape_off_by_one_column),
    ("shape kept at the old figure's column position", shape_stays_at_figure_column),
    ("line also drawn over the two border columns", line_spans_border),
    ("shape drawn as a solid block over its bounding box", shape_filled_solid),
    ("only the half of the shape above the line is drawn", shape_above_line_only),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / "data/tasks/98c475bf.json"
    train = json.load(open(path))["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                g = None
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
