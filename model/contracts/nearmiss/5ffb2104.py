from pathlib import Path
import json
from collections import Counter

def bg_of(g):
    return Counter(c for r in g for c in r).most_common(1)[0][0]

def components(g, bg, diag=False, by_color=True, merge_color=False):
    h, w = len(g), len(g[0])
    if merge_color:
        comps = {}
        for y in range(h):
            for x in range(w):
                if g[y][x] != bg:
                    comps.setdefault(g[y][x], []).append((y, x))
        return [[(y, x, c) for (y, x) in cells] for c, cells in comps.items()]
    seen, out = set(), []
    nb = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    if diag:
        nb += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    for y in range(h):
        for x in range(w):
            if g[y][x] == bg or (y, x) in seen:
                continue
            st, comp = [(y, x)], []
            seen.add((y, x))
            while st:
                cy, cx = st.pop()
                comp.append((cy, cx, g[cy][cx]))
                for dy, dx in nb:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != bg and (ny, nx) not in seen \
                            and (not by_color or g[ny][nx] == g[y][x]):
                        seen.add((ny, nx))
                        st.append((ny, nx))
            out.append(comp)
    return out

def settle(inp, d=(0, 1), comps=None, reverse=False, stack=True, trim=0, static=None):
    """Slide components in direction d. Returns grid and per-component shifts."""
    bg = bg_of(inp)
    h, w = len(inp), len(inp[0])
    dy, dx = d
    if comps is None:
        comps = components(inp, bg)
    key = lambda c: max(y * dy + x * dx for y, x, _ in c)
    order = sorted(comps, key=key, reverse=not reverse)
    occ = {}
    if not stack:
        occ = None
    grid = [[bg] * w for _ in range(h)]
    fixed = set()
    movers = []
    for c in order:
        if static and static(c):
            for y, x, col in c:
                grid[y][x] = col
                fixed.add((y, x))
        else:
            movers.append(c)
    for c in movers:
        cells = {(y, x) for y, x, _ in c}
        k = 0
        while True:
            ok = True
            for y, x in cells:
                ny, nx = y + dy * (k + 1), x + dx * (k + 1)
                if not (0 <= ny < h and 0 <= nx < w):
                    ok = False
                    break
                if stack and grid[ny][nx] != bg and (ny, nx) not in cells:
                    ok = False
                    break
                if (ny, nx) in fixed:
                    ok = False
                    break
            if not ok:
                break
            k += 1
        k = max(0, k - trim) if k > 0 else 0
        for y, x, col in c:
            grid[y + dy * k][x + dx * k] = col
    return grid

def same(a, b):
    return a == b

def mk(**kw):
    return lambda inp, out: settle(inp, **kw)

def left(inp, out): return settle(inp, d=(0, -1))
def down(inp, out): return settle(inp, d=(1, 0))
def up(inp, out): return settle(inp, d=(-1, 0))
def nostack(inp, out):
    bg = bg_of(inp); h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    for c in components(inp, bg):
        k = w - 1 - max(x for _, x, _ in c)
        for y, x, col in c:
            g[y][x + k] = col
    return g
def diag8(inp, out):
    bg = bg_of(inp)
    return settle(inp, comps=components(inp, bg, diag=True, by_color=False))
def merge_color(inp, out):
    bg = bg_of(inp)
    return settle(inp, comps=components(inp, bg, merge_color=True))
def short1(inp, out): return settle(inp, trim=1)
def rigid(inp, out):
    bg = bg_of(inp); w = len(inp[0])
    k = min(w - 1 - x for r in inp for x, c in enumerate(r) if c != bg)
    return [[bg] * k + r[:w - k] for r in inp]
def far_first(inp, out): return settle(inp, reverse=True)
def singles_stay(inp, out): return settle(inp, static=lambda c: len(c) == 1)
def nodiag_by_any_color(inp, out):
    bg = bg_of(inp)
    return settle(inp, comps=components(inp, bg, diag=False, by_color=False))
def largest_stays(inp, out):
    bg = bg_of(inp)
    m = max(len(c) for c in components(inp, bg))
    return settle(inp, static=lambda c: len(c) == m)
def lose_last(inp, out):
    # true output, but the object stack's first-settled object is not drawn
    bg = bg_of(inp)
    g = [r[:] for r in out]
    w = len(g[0])
    for r in g:
        pass
    # remove the wall-touching cells of the topmost-leftmost row's last cell
    y = next(i for i, r in enumerate(g) if r[w - 1] != bg)
    g[y][w - 1] = bg
    return g

ALTERNATIVES = [
    ("gravity pulls left instead of right", left),
    ("gravity pulls down instead of right", down),
    ("gravity pulls up instead of right", up),
    ("objects slide to the right wall independently, no stacking against each other", nostack),
    ("objects are any-color 8-connected clusters moving as one body", diag8),
    ("the largest object does not move", largest_stays),
    ("all cells of one color form one rigid object", merge_color),
    ("objects stop one cell short of their resting place", short1),
    ("the whole grid shifts right by the smallest gap to the wall", rigid),
    ("objects settle in the wrong order, farthest from the wall first", far_first),
    ("single-cell objects do not move", singles_stay),
    ("true output with the first right-edge cell of the top row erased", lose_last),
]

def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r))

if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/5ffb2104.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", e); g = None
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
