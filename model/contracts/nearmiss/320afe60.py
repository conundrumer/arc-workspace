import json
from collections import Counter
from pathlib import Path

D4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def bg_of(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def shapes_of(g):
    bg = bg_of(g)
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if g[r][c] != bg and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                comp = []
                while st:
                    y, x = st.pop()
                    comp.append((y, x))
                    for dy, dx in D4:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and g[ny][nx] != bg:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                res.append(comp)
    return res


def outside(h, w, wall):
    """Cells reachable from the border without crossing wall cells."""
    reach = set()
    st = [(y, x) for y in range(h) for x in range(w)
          if (y in (0, h - 1) or x in (0, w - 1)) and (y, x) not in wall]
    reach.update(st)
    while st:
        y, x = st.pop()
        for dy, dx in D4:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in reach and (ny, nx) not in wall:
                reach.add((ny, nx))
                st.append((ny, nx))
    return reach


def has_gap(g, comp):
    h, w = len(g), len(g[0])
    cs = set(comp)
    out_ = outside(h, w, cs)
    y0 = min(y for y, _ in comp); y1 = max(y for y, _ in comp)
    x0 = min(x for _, x in comp); x1 = max(x for _, x in comp)
    return any((y, x) not in cs and (y, x) in out_
               for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))


def has_hole(g, comp):
    h, w = len(g), len(g[0])
    cs = set(comp)
    out_ = outside(h, w, cs)
    return any((y, x) not in cs and (y, x) not in out_
               for y in range(h) for x in range(w)
               if min(y for y, _ in comp) <= y <= max(y for y, _ in comp)
               and min(x for _, x in comp) <= x <= max(x for _, x in comp))


def render(g, plan, short=0, keep=False):
    """plan: list of (comp, (dy,dx) or None, color or None). Shapes slide to the edge."""
    h, w = len(g), len(g[0])
    bg = bg_of(g)
    res = [[bg] * w for _ in range(h)]
    if keep:
        res = [r[:] for r in g]
    for comp, d, col in plan:
        if col is None:
            continue
        if d is None:
            sy = sx = 0
        else:
            dy, dx = d
            y0 = min(y for y, _ in comp); y1 = max(y for y, _ in comp)
            x0 = min(x for _, x in comp); x1 = max(x for _, x in comp)
            if dy:
                k = (h - 1 - y1) if dy > 0 else y0
            else:
                k = (w - 1 - x1) if dx > 0 else x0
            k = max(0, k - short)
            sy, sx = dy * k, dx * k
        for y, x in comp:
            res[y + sy][x + sx] = col
    return res


L, R, U, Dn = (0, -1), (0, 1), (-1, 0), (1, 0)


def true_open(g, comp):
    return has_gap(g, comp) and not has_hole(g, comp)


def classic(inp, closed_d=L, open_d=R, cc=2, oc=3, is_open=None, **kw):
    is_open = is_open or true_open
    plan = []
    for comp in shapes_of(inp):
        if is_open(inp, comp):
            plan.append((comp, open_d, oc))
        else:
            plan.append((comp, closed_d, cc))
    return render(inp, plan, **kw)


def swap_dirs(inp, out):
    return classic(inp, closed_d=R, open_d=L)


def swap_colors(inp, out):
    return classic(inp, cc=3, oc=2)


def all_closed(inp, out):
    return classic(inp, is_open=lambda g, c: False)


def all_open(inp, out):
    return classic(inp, is_open=lambda g, c: True)


def vertical(inp, out):
    return classic(inp, closed_d=U, open_d=Dn)


def one_short(inp, out):
    return classic(inp, short=1)


def solid_is_open(inp, out):
    # only shapes with an enclosed hole count as closed
    r = classic(inp, is_open=lambda g, c: not has_hole(g, c))
    if not any(not true_open(inp, c) and not has_hole(inp, c) for c in shapes_of(inp)):
        return None
    return r


def notch_means_open(inp, out):
    # any notch in the bounding box makes a shape open, even if it also has a hole
    return classic(inp, is_open=has_gap)


def copy_not_move(inp, out):
    bg = bg_of(inp)
    res = [r[:] for r in out]
    for y, row in enumerate(inp):
        for x, v in enumerate(row):
            if v != bg:
                res[y][x] = v
    return res


def drop_open(inp, out):
    plan = []
    for comp in shapes_of(inp):
        if true_open(inp, comp):
            plan.append((comp, None, None))
        else:
            plan.append((comp, L, 2))
    return render(inp, plan)


def recolor_in_place(inp, out):
    plan = [(c, None, 3 if true_open(inp, c) else 2) for c in shapes_of(inp)]
    return render(inp, plan)


def open_goes_down(inp, out):
    return classic(inp, open_d=Dn)


def closed_stay(inp, out):
    plan = []
    for comp in shapes_of(inp):
        if true_open(inp, comp):
            plan.append((comp, R, 3))
        else:
            plan.append((comp, None, 2))
    return render(inp, plan)


ALTERNATIVES = [
    ("closed go right and open go left, colors kept", swap_dirs),
    ("closed shapes get color 3 and open shapes color 2, directions kept", swap_colors),
    ("every shape treated as closed (all left, color 2)", all_closed),
    ("every shape treated as open (all right, color 3)", all_open),
    ("closed go up and open go down instead of left/right", vertical),
    ("shapes stop one cell short of the edge", one_short),
    ("solid shapes without a hole counted as open", solid_is_open),
    ("a shape with a notch counts as open even when it also has a hole", notch_means_open),
    ("shapes copied to the edge but the original ink left in place", copy_not_move),
    ("open shapes deleted instead of moved", drop_open),
    ("shapes recolored in place without sliding", recolor_in_place),
    ("open shapes slide down while closed slide left", open_goes_down),
]


def valid(g, true):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
            and g != true)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/320afe60.json').read_text())
    pairs = task["train"]
    # sanity: the right rule reproduces the output
    print("rule check:", [classic(p["input"]) == p["output"] for p in pairs])
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
