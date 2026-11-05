"""Near-miss readings for ARC task 72322fa7.

Rule: the input holds complete figures (a center cell with arm cells of a
second color) and incomplete ones (a lone center, or arms with a missing
center). Each incomplete figure is completed with the arm pattern of the
complete figure that has the same center color.
"""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for row in inp for v in row).most_common(1)[0][0]


def _copy(g):
    return [list(r) for r in g]


def _added(inp, out):
    return [(r, c) for r in range(len(inp)) for c in range(len(inp[0]))
            if inp[r][c] != out[r][c]]


def _neighbors(inp, r, c, bg):
    res = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if (dr or dc) and 0 <= r + dr < len(inp) and 0 <= c + dc < len(inp[0]):
                if inp[r + dr][c + dc] != bg:
                    res.append((r + dr, c + dc))
    return res


def _clusters(cells):
    """Group cells that lie within Chebyshev distance 2 of each other."""
    left = set(cells)
    groups = []
    while left:
        start = min(left)
        stack, grp = [start], set()
        left.discard(start)
        while stack:
            r, c = stack.pop()
            grp.add((r, c))
            for q in list(left):
                if max(abs(q[0] - r), abs(q[1] - c)) <= 2:
                    left.discard(q)
                    stack.append(q)
        groups.append(sorted(grp))
    return sorted(groups)


def _with_cells(inp, out, cells):
    g = _copy(inp)
    for r, c in cells:
        g[r][c] = out[r][c]
    return g


def unchanged(inp, out):
    return _copy(inp)


def first_cluster_only(inp, out):
    groups = _clusters(_added(inp, out))
    if len(groups) < 2:
        return None
    return _with_cells(inp, out, groups[0])


def drop_last_cluster(inp, out):
    groups = _clusters(_added(inp, out))
    if len(groups) < 2:
        return None
    return _with_cells(inp, out, [p for g in groups[:-1] for p in g])


def template_erased(inp, out):
    """Template figures are moved rather than copied."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    g = _copy(out)
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            comp, stack = [], [(r, c)]
            seen.add((r, c))
            while stack:
                p = stack.pop()
                comp.append(p)
                for q in _neighbors(inp, p[0], p[1], bg):
                    if q not in seen:
                        seen.add(q)
                        stack.append(q)
            if len(comp) >= 3:
                for p in comp:
                    g[p[0]][p[1]] = bg
    return g


def neighbor_color(inp, out):
    """Each new cell takes the color of the figure cell next to it."""
    bg = _bg(inp)
    g = _copy(out)
    for r, c in _added(inp, out):
        nb = _neighbors(inp, r, c, bg)
        if nb:
            g[r][c] = inp[nb[0][0]][nb[0][1]]
    return g


def _is_gap(inp, r, c, bg):
    return len(_neighbors(inp, r, c, bg)) >= 2


def only_lone_centers(inp, out):
    """Completes lone centers but not figures whose center is missing."""
    bg = _bg(inp)
    cells = [p for p in _added(inp, out) if not _is_gap(inp, p[0], p[1], bg)]
    return _with_cells(inp, out, cells)


def only_missing_centers(inp, out):
    """Completes figures whose center is missing but not lone centers."""
    bg = _bg(inp)
    cells = [p for p in _added(inp, out) if _is_gap(inp, p[0], p[1], bg)]
    return _with_cells(inp, out, cells)


def shifted_right(inp, out):
    """New cells land one column to the right."""
    g = _copy(inp)
    w = len(inp[0])
    for r, c in _added(inp, out):
        if c + 1 < w:
            g[r][c + 1] = out[r][c]
    return g


def crop_to_content(inp, out):
    """Output is cropped to the bounding box of the completed content."""
    bg = _bg(out)
    rs = [r for r, row in enumerate(out) for v in row if v != bg]
    cs = [c for row in out for c, v in enumerate(row) if v != bg]
    if not rs:
        return None
    return [row[min(cs):max(cs) + 1] for row in out[min(rs):max(rs) + 1]]


def doubled_arms(inp, out):
    """Arms around a lone center sit two cells away instead of one."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r, c in _added(inp, out):
        nb = _neighbors(inp, r, c, bg)
        if len(nb) >= 2:
            g[r][c] = out[r][c]
        elif nb:
            cr, cc = nb[0]
            nr, nc = cr + 2 * (r - cr), cc + 2 * (c - cc)
            if 0 <= nr < h and 0 <= nc < w:
                g[nr][nc] = out[r][c]
    return g


def one_arm_short(inp, out):
    """Each figure with several new cells misses its last new cell."""
    cells = []
    for grp in _clusters(_added(inp, out)):
        cells.extend(grp[:-1] if len(grp) > 1 else grp)
    return _with_cells(inp, out, cells)


ALTERNATIVES = [
    ("no figure is completed; output equals input", unchanged),
    ("only the topmost group of completions is drawn", first_cluster_only),
    ("the last group of completions is left out", drop_last_cluster),
    ("template figures are erased after being copied", template_erased),
    ("new cells take the color of the adjacent figure cell, not the arm color", neighbor_color),
    ("only lone centers get arms; figures with a missing center stay open", only_lone_centers),
    ("only missing centers are filled; lone centers get no arms", only_missing_centers),
    ("completions land one column to the right of the right place", shifted_right),
    ("output is cropped to the bounding box of the non-background content", crop_to_content),
    ("arms around a lone center are placed two cells away instead of one", doubled_arms),
    ("each completed figure misses its last new cell", one_arm_short),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/72322fa7.json').read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(_copy(p["input"]), _copy(p["output"]))
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
