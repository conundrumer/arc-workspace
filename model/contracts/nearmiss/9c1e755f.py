"""Near-miss readings for ARC task 9c1e755f.

Rule: a straight rail (color 5) has a swatch hanging off one end. The swatch
repeats along the rail, filling the rail's length times the swatch's width.
"""
import json
from collections import Counter
from pathlib import Path

RAIL = 5
BG = 0


def _components(grid, pred):
    h, w = len(grid), len(grid[0])
    seen, comps = set(), []
    for r in range(h):
        for c in range(w):
            if (r, c) in seen or not pred(grid[r][c]):
                continue
            stack, comp = [(r, c)], []
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and pred(grid[ny][nx]):
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append(comp)
    return comps


def _analyze(inp):
    """One info per rail: a position map (t, a) -> (r, c), swatch content S."""
    h, w = len(inp), len(inp[0])
    infos = []
    for rail in _components(inp, lambda v: v == RAIL):
        rs = [p[0] for p in rail]
        cs = [p[1] for p in rail]
        r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
        if r0 == r1 and c0 == c1:
            continue
        vertical = c0 == c1
        rail_set = set(rail)
        seed = None
        for (y, x) in rail:
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                ny, nx = y + dy, x + dx
                if (ny, nx) in rail_set or not (0 <= ny < h and 0 <= nx < w):
                    continue
                if inp[ny][nx] not in (BG, RAIL):
                    if (vertical and dx != 0) or (not vertical and dy != 0):
                        seed = (ny, nx, dy, dx)
        if seed is None:
            continue
        sy, sx, dy, dx = seed
        sw = [c for c in _components(inp, lambda v: v not in (BG, RAIL))
              if (sy, sx) in c][0]
        sr0, sr1 = min(p[0] for p in sw), max(p[0] for p in sw)
        sc0, sc1 = min(p[1] for p in sw), max(p[1] for p in sw)
        if vertical:
            n, L, wd = r1 - r0 + 1, sr1 - sr0 + 1, sc1 - sc0 + 1
            if sr1 == r1:
                along = lambda t, r1=r1: r1 - t
            elif sr0 == r0:
                along = lambda t, r0=r0: r0 + t
            else:
                continue
            across = (lambda a, c0=c0, dx=dx: c0 + dx * (1 + a))
            pos = lambda t, a, al=along, ac=across: (al(t), ac(a))
        else:
            n, L, wd = c1 - c0 + 1, sc1 - sc0 + 1, sr1 - sr0 + 1
            if sc1 == c1:
                along = lambda t, c1=c1: c1 - t
            elif sc0 == c0:
                along = lambda t, c0=c0: c0 + t
            else:
                continue
            across = (lambda a, r0=r0, dy=dy: r0 + dy * (1 + a))
            pos = lambda t, a, al=along, ac=across: (ac(a), al(t))
        S = [[inp[pos(t, a)[0]][pos(t, a)[1]] for a in range(wd)] for t in range(L)]
        infos.append({"pos": pos, "N": n, "L": L, "W": wd, "S": S,
                      "vertical": vertical, "dy": dy, "dx": dx})
    return infos


def _paint(inp, t_range, a_range, color, only_empty=False, infos=None):
    """Paint cells (t, a) of every rail's frame; color(info, t, a) may be None."""
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for info in (infos if infos is not None else _analyze(inp)):
        for t in t_range(info):
            for a in a_range(info):
                v = color(info, t, a)
                if v is None:
                    continue
                r, c = info["pos"](t, a)
                if not (0 <= r < h and 0 <= c < w) or inp[r][c] == RAIL:
                    continue
                if only_empty and inp[r][c] != BG:
                    continue
                g[r][c] = v
    return g


def _tile(info, t, a):
    return info["S"][t % info["L"]][a]


def _full_t(info):
    return range(info["N"])


def _full_a(info):
    return range(info["W"])


def _unchanged(inp, out):
    return [row[:] for row in inp]


def _one_copy(inp, out):
    return _paint(inp, lambda i: range(min(2 * i["L"], i["N"])), _full_a, _tile)


def _stretch_edge(inp, out):
    return _paint(inp, _full_t, _full_a, lambda i, t, a: i["S"][0][a])


def _mirror_across(inp, out):
    return _paint(inp, _full_t, _full_a,
                  lambda i, t, a: i["S"][t % i["L"]][i["W"] - 1 - a])


def _overshoot(inp, out):
    return _paint(inp, lambda i: range(i["N"] + 1), _full_a, _tile)


def _undershoot(inp, out):
    return _paint(inp, lambda i: range(i["N"] - 1), _full_a, _tile)


def _narrow(inp, out):
    return _paint(inp, _full_t, lambda i: range(i["W"] - 1), _tile)


def _gap_between_copies(inp, out):
    def color(i, t, a):
        k = t % (i["L"] + 1)
        return None if k == i["L"] else i["S"][k][a]
    return _paint(inp, _full_t, _full_a, color)


def _across_to_edge(inp, out):
    h, w = len(inp), len(inp[0])
    return _paint(inp, _full_t, lambda i: range(max(h, w)),
                  lambda i, t, a: i["S"][t % i["L"]][a % i["W"]], only_empty=True)


def _solid_dominant(inp, out):
    def color(i, t, a):
        cnt = Counter(v for row in i["S"] for v in row)
        return cnt.most_common(1)[0][0]
    return _paint(inp, _full_t, _full_a, color)


def _opposite_side(inp, out):
    infos = _analyze(inp)
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for i in infos:
        for t in range(i["N"]):
            for a in range(i["W"]):
                # mirror the cell through the rail line
                r2, c2 = i["pos"](t, -2 - a)
                if 0 <= r2 < h and 0 <= c2 < w and inp[r2][c2] == BG:
                    g[r2][c2] = _tile(i, t, a)
    return g


ALTERNATIVES = [
    ("rule not applied: the output is the input", _unchanged),
    ("only one extra copy of the swatch is drawn next to the original", _one_copy),
    ("the swatch's outermost line is stretched over the whole field, ignoring the swatch length", _stretch_edge),
    ("copies are mirrored across the rail's perpendicular, so each copy is flipped", _mirror_across),
    ("the field overshoots the rail by one line past its far end", _overshoot),
    ("the field stops one line short of the rail's far end", _undershoot),
    ("the field is one line narrower across, so the swatch's outer line is not repeated", _narrow),
    ("copies are separated by a one-line background gap", _gap_between_copies),
    ("the pattern is tiled across to the grid edge, beyond the swatch width", _across_to_edge),
    ("the field is filled solid with the swatch's most common color", _solid_dominant),
    ("copies go to the opposite side of the rail from the swatch", _opposite_side),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/9c1e755f.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error:", desc, repr(e))
                g = None
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
