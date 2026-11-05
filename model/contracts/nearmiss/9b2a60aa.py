"""Near-miss readings for ARC task 9b2a60aa."""
import json
from pathlib import Path


def _comps(cells):
    cells = set(cells)
    seen, out = set(), []
    for s in sorted(cells):
        if s in seen:
            continue
        stack, comp = [s], []
        seen.add(s)
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    q = (r + dr, c + dc)
                    if q in cells and q not in seen:
                        seen.add(q)
                        stack.append(q)
        out.append(sorted(comp))
    return out


def _parse(inp, out):
    H, W = len(inp), len(inp[0])
    ink = [(r, c) for r in range(H) for c in range(W) if inp[r][c]]
    comps = _comps(ink)
    shape = max(comps, key=len)
    markers = [x[0] for x in comps if len(x) == 1]
    scol = inp[shape[0][0]][shape[0][1]]
    diff = [(r, c) for r in range(H) for c in range(W) if inp[r][c] != out[r][c]]
    copies = _comps(diff)
    mr = {r for r, _ in markers}
    horizontal = len(mr) == 1
    ax = 1 if horizontal else 0  # index of the along-line coordinate
    copies.sort(key=lambda comp: min(p[ax] for p in comp))
    return H, W, shape, scol, markers, copies, ax


def _paint(inp, out, copies, ax, fn):
    """Start from inp; paint each copy as fn(index, comp) -> list of (r, c, color)."""
    g = [row[:] for row in inp]
    for i, comp in enumerate(copies):
        for r, c, col in fn(i, comp):
            if 0 <= r < len(g) and 0 <= c < len(g[0]):
                g[r][c] = col
    return g


def _cells(out, comp):
    return [(r, c, out[r][c]) for r, c in comp]


def no_recolor(inp, out):
    H, W, shape, scol, markers, copies, ax = _parse(inp, out)
    return _paint(inp, out, copies, ax,
                  lambda i, comp: [(r, c, scol) for r, c in comp])


def drop_farthest(inp, out):
    H, W, shape, scol, markers, copies, ax = _parse(inp, out)
    sh = sum(p[ax] for p in shape) / len(shape)
    far = max(range(len(copies)),
              key=lambda i: abs(sum(p[ax] for p in copies[i]) / len(copies[i]) - sh))
    return _paint(inp, out, copies, ax,
                  lambda i, comp: [] if i == far else _cells(out, comp))


def drop_nearest(inp, out):
    H, W, shape, scol, markers, copies, ax = _parse(inp, out)
    sh = sum(p[ax] for p in shape) / len(shape)
    near = min(range(len(copies)),
               key=lambda i: abs(sum(p[ax] for p in copies[i]) / len(copies[i]) - sh))
    return _paint(inp, out, copies, ax,
                  lambda i, comp: [] if i == near else _cells(out, comp))


def shift_one(inp, out):
    H, W, shape, scol, markers, copies, ax = _parse(inp, out)
    d = (0, 1) if ax == 1 else (1, 0)
    return _paint(inp, out, copies, ax,
                  lambda i, comp: [(r + d[0], c + d[1], out[r][c]) for r, c in comp])


def origin_at_marker(inp, out):
    H, W, shape, scol, markers, copies, ax = _parse(inp, out)
    others = sorted((m for m in markers if inp[m[0]][m[1]] != scol),
                    key=lambda p: p[ax])
    if len(others) != len(copies):
        return None

    def fn(i, comp):
        lo = min(p[ax] for p in comp)
        sh = others[i][ax] - lo
        return [(r + (0 if ax == 1 else sh), c + (sh if ax == 1 else 0), out[r][c])
                for r, c in comp]
    return _paint(inp, out, copies, ax, fn)


def transposed_copies(inp, out):
    H, W, shape, scol, markers, copies, ax = _parse(inp, out)

    def fn(i, comp):
        r0, c0 = min(p[0] for p in comp), min(p[1] for p in comp)
        r1, c1 = max(p[0] for p in comp), max(p[1] for p in comp)
        if r1 - r0 != c1 - c0:
            return None
        return [(r0 + (c - c0), c0 + (r - r0), out[r][c]) for r, c in comp]
    for comp in copies:
        if fn(0, comp) is None:
            return None
    return _paint(inp, out, copies, ax, fn)


def flipped_copies(inp, out):
    H, W, shape, scol, markers, copies, ax = _parse(inp, out)

    def fn(i, comp):
        r0, r1 = min(p[0] for p in comp), max(p[0] for p in comp)
        return [(r0 + r1 - r, c, out[r][c]) for r, c in comp]
    return _paint(inp, out, copies, ax, fn)


def move_not_copy(inp, out):
    g = [row[:] for row in out]
    H, W, shape, scol, markers, copies, ax = _parse(inp, out)
    for r, c in shape:
        g[r][c] = 0
    return g


def one_copy_per_color(inp, out):
    H, W, shape, scol, markers, copies, ax = _parse(inp, out)
    seen = set()
    keep = set()
    for i, comp in enumerate(copies):
        col = out[comp[0][0]][comp[0][1]]
        if col not in seen:
            seen.add(col)
            keep.add(i)
    return _paint(inp, out, copies, ax,
                  lambda i, comp: _cells(out, comp) if i in keep else [])


def solid_box_copies(inp, out):
    H, W, shape, scol, markers, copies, ax = _parse(inp, out)

    def fn(i, comp):
        col = out[comp[0][0]][comp[0][1]]
        r0, r1 = min(p[0] for p in comp), max(p[0] for p in comp)
        c0, c1 = min(p[1] for p in comp), max(p[1] for p in comp)
        return [(r, c, col) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
    return _paint(inp, out, copies, ax, fn)


def packed_no_gaps(inp, out):
    """Copies packed one after another along the line, ignoring marker gaps."""
    H, W, shape, scol, markers, copies, ax = _parse(inp, out)
    sh_lo = min(p[ax] for p in shape)
    ext = max(p[ax] for p in shape) - sh_lo + 1
    # first copy starts next to the shape's slot, then each follows with no gap
    first = min(p[ax] for p in copies[0])
    step = ext
    if ax == 1:
        start = sh_lo
    else:
        start = sh_lo
    sign = 1 if first >= sh_lo else -1

    def fn(i, comp):
        lo = min(p[ax] for p in comp)
        tgt = start + sign * step * (i + 1)
        sh = tgt - lo
        return [(r + (0 if ax == 1 else sh), c + (sh if ax == 1 else 0), out[r][c])
                for r, c in comp]
    return _paint(inp, out, copies, ax, fn)


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("copies keep the shape's color instead of the marker's color", no_recolor),
    ("the copy farthest from the shape is left out", drop_farthest),
    ("the copy nearest the shape is left out", drop_nearest),
    ("every copy sits one cell off along the marker line", shift_one),
    ("each copy starts at its marker's coordinate, ignoring slot widths", origin_at_marker),
    ("copies are transposed shapes", transposed_copies),
    ("copies are flipped across the line direction", flipped_copies),
    ("the shape moves to the markers instead of being copied (original erased)", move_not_copy),
    ("only the first marker of each color gets a copy", one_copy_per_color),
    ("copies are solid boxes of the marker's color", solid_box_copies),
    ("copies packed with shape-width spacing, marker gaps ignored", packed_no_gaps),
    ("output equals the input", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/9b2a60aa.json").read_text())
    pairs = task["train"]
    print(len(pairs), "train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
