"""Near-miss rules for ARC task 40f6cd08.

Rule: one non-background object is a nested stack of concentric rectangles.
Each plain one-color rectangle gets the same stack, with the same margins
(in cells) between the layers, inside its own bounding box.
"""
import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _components(g, bg):
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    for y in range(h):
        for x in range(w):
            if g[y][x] == bg or (y, x) in seen:
                continue
            stack = [(y, x)]
            seen.add((y, x))
            cells = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if (0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen
                                and g[ny][nx] != bg):
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            comps.append(cells)
    return comps


def _bbox(cells):
    ys = [c[0] for c in cells]
    xs = [c[1] for c in cells]
    return min(xs), min(ys), max(xs), max(ys)  # l, t, r, b


def _parse(inp):
    """Return (layers, targets). layers: list of (color, (ml, mt, mr, mb)),
    outermost first. targets: list of (color, bbox)."""
    bg = _bg(inp)
    template = None
    targets = []
    for cells in _components(inp, bg):
        colors = {inp[y][x] for y, x in cells}
        if len(colors) > 1:
            template = cells
        else:
            targets.append((colors.pop(), _bbox(cells)))
    tl, tt, tr, tb = _bbox(template)
    info = []
    for c in {inp[y][x] for y, x in template}:
        cs = [(y, x) for y, x in template if inp[y][x] == c]
        l, t, r, b = _bbox(cs)
        info.append(((r - l + 1) * (b - t + 1), c, (l - tl, t - tt, tr - r, tb - b)))
    info.sort(key=lambda e: -e[0])
    layers = [(c, m) for _, c, m in info]
    targets.sort(key=lambda e: (e[1][1], e[1][0]))
    return layers, (tr - tl + 1, tb - tt + 1), targets


def _render(inp, mod_margin=None, colors=None, shift=(0, 0), skip=None,
            drop_inner=False, solid=None, skip_target=None):
    layers, tsize, targets = _parse(inp)
    g = [row[:] for row in inp]
    if drop_inner:
        layers = layers[:-1]
    cols = [c for c, _ in layers]
    if colors is not None:
        cols = colors(cols)
    for i, (tc, (l, t, r, b)) in enumerate(targets):
        if skip_target is not None and skip_target(i, len(targets)):
            continue
        if solid is not None:
            for y in range(t, b + 1):
                for x in range(l, r + 1):
                    g[y][x] = solid(layers)
            continue
        for k, (_, m) in enumerate(layers):
            if k == 0:
                continue
            if mod_margin is not None:
                m = mod_margin(m, tsize, (r - l + 1, b - t + 1))
            ml, mt, mr, mb = m
            x0, y0 = l + ml + shift[0], t + mt + shift[1]
            x1, y1 = r - mr + shift[0], b - mb + shift[1]
            for y in range(max(y0, 0), min(y1, len(g) - 1) + 1):
                for x in range(max(x0, 0), min(x1, len(g[0]) - 1) + 1):
                    g[y][x] = cols[k]
    return g


def _unchanged(inp, out):
    return [row[:] for row in inp]


def _mirror_h(inp, out):
    return _render(inp, mod_margin=lambda m, T, S: (m[2], m[1], m[0], m[3]))


def _mirror_v(inp, out):
    return _render(inp, mod_margin=lambda m, T, S: (m[0], m[3], m[2], m[1]))


def _transposed(inp, out):
    return _render(inp, mod_margin=lambda m, T, S: (m[1], m[0], m[3], m[2]))


def _plus_one(inp, out):
    return _render(inp, mod_margin=lambda m, T, S: tuple(v + 1 for v in m))


def _minus_one(inp, out):
    return _render(inp, mod_margin=lambda m, T, S: tuple(max(v - 1, 0) for v in m))


def _proportional(inp, out):
    def f(m, T, S):
        return (round(m[0] * S[0] / T[0] * 2), round(m[1] * S[1] / T[1] * 2),
                round(m[2] * S[0] / T[0] * 2), round(m[3] * S[1] / T[1] * 2))
    return _render(inp, mod_margin=f)


def _drop_innermost(inp, out):
    return _render(inp, drop_inner=True)


def _reversed_colors(inp, out):
    return _render(inp, colors=lambda cols: cols[::-1])


def _shifted(inp, out):
    return _render(inp, shift=(1, 0))


def _solid_innermost(inp, out):
    return _render(inp, solid=lambda layers: layers[-1][0])


def _last_target_missed(inp, out):
    return _render(inp, skip_target=lambda i, n: i == n - 1)


def _guard(fn):
    def wrapped(inp, out):
        g = fn(inp, out)
        return None if g == out else g
    return wrapped


ALTERNATIVES = [
    ("Leave the plain rectangles as they are (no stack is copied)", _unchanged),
    ("Copy the stack with left and right margins swapped", _guard(_mirror_h)),
    ("Copy the stack with top and bottom margins swapped", _guard(_mirror_v)),
    ("Copy the stack with horizontal and vertical margins swapped", _guard(_transposed)),
    ("Copy the stack with every margin one cell too wide", _guard(_plus_one)),
    ("Copy the stack with every margin one cell too narrow", _guard(_minus_one)),
    ("Scale the margins by the size ratio of target to source instead of copying them", _guard(_proportional)),
    ("Copy the stack but leave out its innermost layer", _guard(_drop_innermost)),
    ("Copy the stack with the layer colors in reverse order", _guard(_reversed_colors)),
    ("Copy the stack with its inner layers shifted one cell right", _guard(_shifted)),
    ("Fill each plain rectangle solid with the stack's innermost color", _guard(_solid_innermost)),
    ("Stamp every plain rectangle except the last one in reading order", _guard(_last_target_missed)),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/40f6cd08.json").read_text())
    pairs = task["train"]
    # sanity: the true stamp reproduces the true output
    for p in pairs:
        assert _render(p["input"]) == p["output"], "true rule model mismatch"
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            ok = (g is not None and isinstance(g, list) and g
                  and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                  and g != p["output"])
            n += bool(ok)
        print(f"{n}/{len(pairs)}  {desc}")
