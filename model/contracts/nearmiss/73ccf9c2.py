from pathlib import Path
import json

def comps(g, conn8=True):
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    nb = [(-1,0),(1,0),(0,-1),(0,1)]
    if conn8:
        nb += [(-1,-1),(-1,1),(1,-1),(1,1)]
    for r in range(h):
        for c in range(w):
            if g[r][c] and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    a, b = st.pop()
                    cells.append((a, b))
                    for dr, dc in nb:
                        n = (a+dr, b+dc)
                        if 0 <= n[0] < h and 0 <= n[1] < w and g[n[0]][n[1]] and n not in seen:
                            seen.add(n)
                            st.append(n)
                res.append(cells)
    return res

def crop(g, cells, pad=0, trim_last=False):
    r0 = min(a for a, b in cells); r1 = max(a for a, b in cells)
    c0 = min(b for a, b in cells); c1 = max(b for a, b in cells)
    h, w = len(g), len(g[0])
    if trim_last:
        r1 -= 1; c1 -= 1
    return [[g[r][c] if 0 <= r < h and 0 <= c < w else 0
             for c in range(c0-pad, c1+1+pad)] for r in range(r0-pad, r1+1+pad)]

def fliplr(g): return [r[::-1] for r in g]
def flipud(g): return g[::-1]
def transpose(g): return [list(r) for r in zip(*g)]
def rot90(g): return fliplr(transpose(g))
def rot180(g): return flipud(fliplr(g))
def rot270(g): return transpose(fliplr(g))

def d4(g):
    t = transpose(g)
    return [g, rot90(g), rot180(g), rot270(g), fliplr(g), flipud(g), t, rot180(t)]

def figures(inp, conn8=True):
    return [(cells, crop(inp, cells)) for cells in comps(inp, conn8)]

def odd_and_others(inp, out):
    figs = figures(inp)
    odd = None
    others = []
    for cells, cr in figs:
        if odd is None and cr == out:
            odd = (cells, cr)
        else:
            others.append((cells, cr))
    if odd is None:
        return None, others
    return odd, others

def other_raw_largest(inp, out):
    odd, others = odd_and_others(inp, out)
    if not others: return None
    return max(others, key=lambda f: len(f[0]))[1]

def other_raw_smallest(inp, out):
    odd, others = odd_and_others(inp, out)
    if not others: return None
    return min(others, key=lambda f: len(f[0]))[1]

def first_in_reading_order(inp, out):
    return figures(inp)[0][1]

def biggest_bbox(inp, out):
    f = figures(inp)
    return max(f, key=lambda x: len(x[1]) * len(x[1][0]))[1]

def largest_raw(inp, out):
    f = figures(inp)
    return max(f, key=lambda x: len(x[0]))[1]

def largest_4conn(inp, out):
    f = figures(inp, False)
    return max(f, key=lambda x: len(x[0]))[1]

def odd_pad1(inp, out):
    odd, _ = odd_and_others(inp, out)
    if not odd: return None
    return crop(inp, odd[0], pad=1)

def odd_trim(inp, out):
    odd, _ = odd_and_others(inp, out)
    if not odd: return None
    return crop(inp, odd[0], trim_last=True)

def invert(inp, out):
    c = max(v for r in out for v in r)
    return [[0 if v else c for v in r] for r in out]

def tr(f):
    return lambda inp, out: f(out)

def odd_color_wrong(inp, out):
    return [[(v + 1) % 10 if v else 0 for v in r] for r in out]

def odd_bbox_whole_filled(inp, out):
    c = max(v for r in out for v in r)
    return [[c for v in r] for r in out]

ALTERNATIVES = [
    ("outputs a different (largest non-odd) figure in its raw orientation", other_raw_largest),
    ("outputs a different (smallest non-odd) figure in its raw orientation", other_raw_smallest),
    ("outputs the largest figure by cell count instead of the odd one", largest_raw),
    ("segments by 4-connectivity only and outputs the largest piece", largest_4conn),
    ("crops the odd figure with a one-cell margin on every side", odd_pad1),
    ("crops the odd figure one row and column short", odd_trim),
    ("outputs the first figure in reading order", first_in_reading_order),
    ("outputs the figure with the largest bounding box", biggest_bbox),
    ("reorients with a left-right flip only", tr(fliplr)),
    ("reorients with a top-bottom flip only", tr(flipud)),
    ("reorients with a transpose instead of the correct transform", tr(transpose)),
    ("swaps figure and background colors inside the crop", invert),
]

if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/73ccf9c2.json')))
    pairs = t["train"]
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", e); g = None
            ok = (g is not None and len(g) > 0 and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != p["output"])
            n += ok
        print(n, desc)
