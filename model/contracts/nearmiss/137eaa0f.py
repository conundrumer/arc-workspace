import json
from pathlib import Path


def _copy(g):
    return [list(r) for r in g]


def _flip_h(inp, out):
    return [r[::-1] for r in out]


def _flip_v(inp, out):
    return [list(r) for r in out[::-1]]


def _transpose(inp, out):
    return [list(r) for r in zip(*out)]


def _rot180(inp, out):
    return [r[::-1] for r in out[::-1]]


def _no_anchor(inp, out):
    return [[0 if v == 5 else v for v in r] for r in out]


def _anchor_color_as_ink(inp, out):
    # Anchor cell drawn in the most common other ink color.
    counts = {}
    for r in out:
        for v in r:
            if v not in (0, 5):
                counts[v] = counts.get(v, 0) + 1
    if not counts:
        return None
    c = max(counts, key=lambda k: (counts[k], k))
    return [[c if v == 5 else v for v in r] for r in out]


def _shift_anchor_corner(inp, out):
    # Fragments aligned with the anchor at the top-left cell instead of the center.
    h, w = len(out), len(out[0])
    pos = [(i, j) for i in range(h) for j in range(w) if out[i][j] == 5]
    if not pos:
        return None
    ai, aj = pos[0]
    g = [[0] * w for _ in range(h)]
    for i in range(h):
        for j in range(w):
            ni, nj = i - ai, j - aj
            if 0 <= ni < h and 0 <= nj < w and out[i][j]:
                g[ni][nj] = out[i][j]
    return g


def _shift_right(inp, out):
    h, w = len(out), len(out[0])
    return [[0] + list(r[:-1]) for r in out]


def _pad_size(inp, out):
    # Output frame one larger than the true 3x3 (off-by-one size).
    g = _copy(out)
    for r in g:
        r.append(0)
    g.append([0] * (len(out[0]) + 1))
    return g


def _drop_top_color(inp, out):
    counts = {}
    for r in out:
        for v in r:
            if v not in (0, 5):
                counts[v] = counts.get(v, 0) + 1
    if not counts:
        return None
    c = max(counts, key=lambda k: (counts[k], k))
    return [[0 if v == c else v for v in r] for r in out]


def _components(inp, diag=True):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    if diag:
        nbr = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
    else:
        nbr = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for i in range(h):
        for j in range(w):
            if inp[i][j] and (i, j) not in seen:
                st = [(i, j)]
                seen.add((i, j))
                cells = []
                while st:
                    a, b = st.pop()
                    cells.append((a, b))
                    for da, db in nbr:
                        x, y = a + da, b + db
                        if 0 <= x < h and 0 <= y < w and inp[x][y] and (x, y) not in seen:
                            seen.add((x, y))
                            st.append((x, y))
                comps.append(cells)
    return comps


def _crop(inp, cells):
    r0 = min(a for a, b in cells)
    r1 = max(a for a, b in cells)
    c0 = min(b for a, b in cells)
    c1 = max(b for a, b in cells)
    g = [[0] * (c1 - c0 + 1) for _ in range(r1 - r0 + 1)]
    for a, b in cells:
        g[a - r0][b - c0] = inp[a][b]
    return g


def _largest_fragment(inp, out):
    comps = _components(inp)
    if not comps:
        return None
    return _crop(inp, max(comps, key=len))


def _bbox_of_all(inp, out):
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v]
    if not cells:
        return None
    r0 = min(a for a, b in cells)
    r1 = max(a for a, b in cells)
    c0 = min(b for a, b in cells)
    c1 = max(b for a, b in cells)
    return [list(r[c0:c1 + 1]) for r in inp[r0:r1 + 1]]


def _align_topleft(inp, out):
    # Fragments overlaid by bounding-box top-left corner instead of by the 5.
    h, w = len(out), len(out[0])
    g = [[0] * w for _ in range(h)]
    for cells in _components(inp):
        r0 = min(a for a, b in cells)
        c0 = min(b for a, b in cells)
        for a, b in cells:
            i, j = a - r0, b - c0
            if i < h and j < w:
                g[i][j] = inp[a][b]
    return g


def _four_conn_first(inp, out):
    # 4-connectivity: only the fragment holding the first-found cell is kept, centered on the 5.
    comps = _components(inp, diag=False)
    if not comps:
        return None
    h, w = len(out), len(out[0])
    cells = comps[0]
    five = [(a, b) for a, b in cells if inp[a][b] == 5]
    if not five:
        return None
    ai, aj = five[0]
    g = [[0] * w for _ in range(h)]
    for a, b in cells:
        i, j = a - ai + h // 2, b - aj + w // 2
        if 0 <= i < h and 0 <= j < w:
            g[i][j] = inp[a][b]
    return g


ALTERNATIVES = [
    ("fragments overlaid mirrored left-right", _flip_h),
    ("fragments overlaid mirrored top-bottom", _flip_v),
    ("fragments overlaid transposed", _transpose),
    ("anchor 5 cell left empty in the output", _no_anchor),
    ("anchor 5 cell drawn in the most common fragment color", _anchor_color_as_ink),
    ("anchor placed at top-left cell of the frame, overflow cropped", _shift_anchor_corner),
    ("overlay shifted one column right (off-by-one offset)", _shift_right),
    ("output frame 4x4 instead of 3x3", _pad_size),
    ("most common fragment color left unfilled", _drop_top_color),
    ("output is the largest single fragment cropped", _largest_fragment),
    ("output is the crop of the bounding box of all non-zero input cells", _bbox_of_all),
    ("fragments aligned by bounding-box top-left instead of by the 5", _align_topleft),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not isinstance(g[0], list) or not g[0]:
        return False
    w = len(g[0])
    for r in g:
        if not isinstance(r, list) or len(r) != w:
            return False
        for v in r:
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9:
                return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/137eaa0f.json").read_text())
    pairs = task["train"]
    print("pairs:", len(pairs), "readings:", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = sum(
            1
            for p in pairs
            if (g := fn(_copy(p["input"]), _copy(p["output"]))) is not None and _valid(g, p["output"])
        )
        print(f"{n}/{len(pairs)}  {desc}")
