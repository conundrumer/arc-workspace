import json
from collections import Counter
from pathlib import Path

CLS_COLOR = {"H": 1, "V": 3, "D": 6}


def _bg(g):
    return Counter(x for r in g for x in r).most_common(1)[0][0]


def _comps(g, bg, diag=True):
    H, W = len(g), len(g[0])
    seen = set()
    res = []
    steps = [(da, db) for da in (-1, 0, 1) for db in (-1, 0, 1) if (da or db) and (diag or not (da and db))]
    for r in range(H):
        for c in range(W):
            if g[r][c] != bg and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cs = []
                while st:
                    a, b = st.pop()
                    cs.append((a, b))
                    for da, db in steps:
                        n = (a + da, b + db)
                        if 0 <= n[0] < H and 0 <= n[1] < W and n not in seen and g[n[0]][n[1]] != bg:
                            seen.add(n)
                            st.append(n)
                res.append(cs)
    return res


def _bbox(cs):
    return (min(a for a, b in cs), min(b for a, b in cs), max(a for a, b in cs), max(b for a, b in cs))


def _cls(cs):
    r0, c0, r1, c1 = _bbox(cs)
    S = set(cs)
    if (r1 - r0) == (c1 - c0):
        d1 = all((r0 + (b - c0), c0 + (a - r0)) in S for a, b in cs)
        d2 = all((r0 + (c1 - b), c0 + (r1 - a)) in S for a, b in cs)
        if d1 and d2:
            return "D"
    if all((r0 + r1 - a, b) in S for a, b in cs):
        return "H"
    if all((a, c0 + c1 - b) in S for a, b in cs):
        return "V"
    return None


def _render(inp, colors=None, erase_max=1, erase_color=None, diag=True, keep_noise=False,
            shape_filter=None, fill_bbox=False, keep_shapes=False):
    bg = _bg(inp)
    colors = colors or CLS_COLOR
    g = [row[:] for row in inp]
    seen_cls = set()
    for cs in _comps(inp, bg, diag):
        if len(cs) <= erase_max:
            if not keep_noise:
                for a, b in cs:
                    g[a][b] = bg if erase_color is None else erase_color
            continue
        if keep_shapes:
            continue
        k = _cls(cs)
        if k is None:
            continue
        if shape_filter is not None and not shape_filter(k, seen_cls):
            continue
        seen_cls.add(k)
        col = colors[k]
        if fill_bbox:
            r0, c0, r1, c1 = _bbox(cs)
            for a in range(r0, r1 + 1):
                for b in range(c0, c1 + 1):
                    g[a][b] = col
        else:
            for a, b in cs:
                g[a][b] = col
    return g


def swap_hv(inp, out):
    return _render(inp, {"H": 3, "V": 1, "D": 6})


def keep_noise(inp, out):
    return _render(inp, keep_noise=True)


def aspect_class(inp, out):
    bg = _bg(inp)
    g = _render(inp, keep_shapes=True)
    for cs in _comps(inp, bg):
        if len(cs) <= 1:
            continue
        r0, c0, r1, c1 = _bbox(cs)
        h, w = r1 - r0 + 1, c1 - c0 + 1
        k = "D" if h == w else ("V" if h > w else "H")
        for a, b in cs:
            g[a][b] = CLS_COLOR[k]
    return g


def erase_under_ten(inp, out):
    return _render(inp, erase_max=9)


def one_color(inp, out):
    return _render(inp, {"H": 1, "V": 1, "D": 1})


def noise_gets_class_color(inp, out):
    bg = _bg(inp)
    g = _render(inp, keep_noise=True)
    for cs in _comps(inp, bg):
        if len(cs) == 1:
            a, b = cs[0]
            g[a][b] = 1
    return g


def erase_to_zero(inp, out):
    return _render(inp, erase_color=0)


def rotated_colors(inp, out):
    return _render(inp, {"H": 3, "V": 6, "D": 1})


def bbox_fill(inp, out):
    return _render(inp, fill_bbox=True)


def first_shape_per_class(inp, out):
    return _render(inp, shape_filter=lambda k, seen: k not in seen)


def diag_as_horizontal(inp, out):
    if "D" not in {_cls(cs) for cs in _comps(inp, _bg(inp)) if len(cs) > 1}:
        return None
    return _render(inp, {"H": 1, "V": 3, "D": 1})


def no_recolor(inp, out):
    return _render(inp, keep_shapes=True)


ALTERNATIVES = [
    ("horizontal-mirror and vertical-mirror classes swap their colors", swap_hv),
    ("single-cell components are left as figure cells instead of erased", keep_noise),
    ("shape class is read from the bounding box aspect ratio: wide is horizontal, tall is vertical, square is diagonal", aspect_class),
    ("components under 10 cells are erased as noise, not only single cells", erase_under_ten),
    ("every non-noise shape takes one color regardless of mirror class", one_color),
    ("single-cell components take the horizontal-class color instead of the background", noise_gets_class_color),
    ("erased cells take color 0 instead of the background color", erase_to_zero),
    ("class colors are rotated: horizontal 3, vertical 6, diagonal 1", rotated_colors),
    ("the whole bounding box of each shape is filled with its class color", bbox_fill),
    ("only the first shape of each mirror class is recolored", first_shape_per_class),
    ("diagonal-mirror shapes take the horizontal-class color", diag_as_horizontal),
    ("noise is erased but shapes keep their input color", no_recolor),
]


def _valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= 9 for r in g for x in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/a09f6c25.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = sum(1 for p in pairs if (lambda g: g is not None and _valid(g, p["output"]))(fn(p["input"], p["output"])))
        print(n, "/", len(pairs), desc)
