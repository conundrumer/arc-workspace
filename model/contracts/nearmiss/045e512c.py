import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _comps(g, bg):
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            col = g[r][c]
            st = [(r, c)]
            seen.add((r, c))
            cells = []
            while st:
                y, x = st.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen
                                and g[ny][nx] == col):
                            seen.add((ny, nx))
                            st.append((ny, nx))
            res.append((col, cells))
    return res


def _cen(cells):
    return (sum(y for y, _ in cells) / len(cells), sum(x for _, x in cells) / len(cells))


def _sgn(v, tol=0.0):
    return 0 if abs(v) <= tol else (1 if v > 0 else -1)


def _analyse(inp, out):
    """Returns bg, template color, and chains: list of lists of copy components,
    each ordered from nearest the template outward. Each component is (color, cells)."""
    bg = _bg(inp)
    tcol, tcells = max(_comps(inp, bg), key=lambda t: len(t[1]))
    tc = _cen(tcells)
    chains = {}
    for col, cells in _comps(out, bg):
        if col == tcol:
            continue
        cc = _cen(cells)
        key = (col, _sgn(cc[0] - tc[0], 1.5), _sgn(cc[1] - tc[1], 1.5))
        chains.setdefault(key, []).append((col, cells))
    res = []
    for key in sorted(chains):
        lst = chains[key]
        lst.sort(key=lambda t: (_cen(t[1])[0] - tc[0]) ** 2 + (_cen(t[1])[1] - tc[1]) ** 2)
        res.append(lst)
    return bg, tcol, tc, res


def _draw(inp, items, bg, overwrite=False):
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for col, cells in items:
        for y, x in cells:
            if 0 <= y < h and 0 <= x < w and (overwrite or g[y][x] == bg):
                g[y][x] = col
    return g


def unchanged(inp, out):
    return [r[:] for r in inp]


def recolor_template(inp, out):
    bg, tcol, tc, chains = _analyse(inp, out)
    g = [r[:] for r in out]
    for ch in chains:
        for col, cells in ch:
            for y, x in cells:
                if inp[y][x] == bg:
                    g[y][x] = tcol
    return g


def first_copy_only(inp, out):
    bg, tcol, tc, chains = _analyse(inp, out)
    return _draw(inp, [ch[0] for ch in chains], bg)


def drop_farthest(inp, out):
    bg, tcol, tc, chains = _analyse(inp, out)
    items = [c for ch in chains for c in ch[:-1]]
    return _draw(inp, items, bg)


def skip_first_copy(inp, out):
    bg, tcol, tc, chains = _analyse(inp, out)
    g = [r[:] for r in out]
    for ch in chains:
        if len(ch) < 2:
            continue
        for y, x in ch[0][1]:
            if inp[y][x] == bg:
                g[y][x] = bg
    return g


def one_marker_color_only(inp, out):
    bg, tcol, tc, chains = _analyse(inp, out)
    first = None
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            v = inp[r][c]
            if v != bg and v != tcol:
                first = v
                break
        if first is not None:
            break
    if first is None:
        return None
    items = [c for ch in chains for c in ch if c[0] == first]
    return _draw(inp, items, bg)


def period_three(inp, out):
    bg, tcol, tc, chains = _analyse(inp, out)
    items = []
    for ch in chains:
        if len(ch) < 2:
            items.extend(ch)
            continue
        c0, c1 = _cen(ch[0][1]), _cen(ch[1][1])
        dy, dx = _sgn(c1[0] - c0[0], 1.5), _sgn(c1[1] - c0[1], 1.5)
        for j, (col, cells) in enumerate(ch):
            items.append((col, [(y - j * dy, x - j * dx) for y, x in cells]))
    return _draw(inp, items, bg)


def _reflected(inp, bg, chains):
    items = []
    for ch in chains:
        col, cells = ch[0]
        mk = [(y, x) for y, x in cells if inp[y][x] == col] or cells
        py, px = _cen(mk)
        py, px = round(py), round(px)
        for col, cells in ch:
            items.append((col, [(2 * py - y, 2 * px - x) for y, x in cells]))
    return items


def opposite_direction(inp, out):
    bg, tcol, tc, chains = _analyse(inp, out)
    return _draw(inp, _reflected(inp, bg, chains), bg)


def both_directions(inp, out):
    bg, tcol, tc, chains = _analyse(inp, out)
    items = [c for ch in chains for c in ch] + _reflected(inp, bg, chains)
    return _draw(out, items, bg)


def crop_to_content(inp, out):
    bg = _bg(inp)
    ys = [r for r in range(len(out)) for c in range(len(out[0])) if out[r][c] != bg]
    xs = [c for r in range(len(out)) for c in range(len(out[0])) if out[r][c] != bg]
    if not ys:
        return None
    return [row[min(xs):max(xs) + 1] for row in out[min(ys):max(ys) + 1]]


def solid_copies(inp, out):
    bg, tcol, tc, chains = _analyse(inp, out)
    g = [r[:] for r in out]
    for ch in chains:
        for col, cells in ch:
            ys = [y for y, _ in cells]
            xs = [x for _, x in cells]
            for y in range(min(ys), max(ys) + 1):
                for x in range(min(xs), max(xs) + 1):
                    if inp[y][x] == bg:
                        g[y][x] = col
    return g


ALTERNATIVES = [
    ("copies never made: the output equals the input", unchanged),
    ("copies are drawn in the template's color instead of the marker's color", recolor_template),
    ("only one copy per marker is made (the copy at the marker)", first_copy_only),
    ("the copy farthest from the template is left out in each direction", drop_farthest),
    ("copying starts one step further out: the copy at the marker is left out", skip_first_copy),
    ("only the first marker color (reading order) is copied; other markers are ignored", one_marker_color_only),
    ("copies are spaced by the template size with no gap cell (period 3 instead of 4)", period_three),
    ("copies go the wrong way: mirrored through the marker, back toward the template", opposite_direction),
    ("copies go both ways from each marker", both_directions),
    ("output is cropped to the bounding box of the non-background cells", crop_to_content),
    ("each copy is a solid rectangle over the template's bounding box", solid_copies),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/045e512c.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
