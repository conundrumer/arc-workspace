from pathlib import Path
import json

def fh(g): return [r[::-1] for r in g]
def fv(g): return g[::-1]
def r180(g): return fv(fh(g))
def tr(g): return [list(c) for c in zip(*g)]
def rcw(g): return fh(tr(g))
def rccw(g): return tr(fh(g))

def quad(tl, tr_, bl, br):
    return [a + b for a, b in zip(tl, tr_)] + [a + b for a, b in zip(bl, br)]

def plain_tiling(inp, out):
    return quad(inp, inp, inp, inp)

def only_h(inp, out):
    return quad(inp, fh(inp), inp, fh(inp))

def only_v(inp, out):
    return quad(inp, inp, fv(inp), fv(inp))

def anchor_br(inp, out):
    return quad(r180(inp), fv(inp), fh(inp), inp)

def rotations(inp, out):
    return quad(inp, rcw(inp), rccw(inp), r180(inp))

def transposes(inp, out):
    return quad(inp, tr(inp), tr(inp), inp)

def top_strip(inp, out):
    n = len(inp)
    return [r[:] for r in out[:n]]

def br_unmirrored(inp, out):
    n = len(inp)
    g = [r[:] for r in out]
    for i in range(n):
        for j in range(n):
            g[n + i][n + j] = inp[i][j]
    return g

def br_blank(inp, out):
    n = len(inp)
    g = [r[:] for r in out]
    for i in range(n):
        for j in range(n):
            g[n + i][n + j] = 0
    return g

def shared_edge(inp, out):
    n = len(inp)
    g = [r[:] for r in out]
    g = [r[:n] + r[n + 1:] for r in g]
    return g[:n] + g[n + 1:]

def swapped_flips(inp, out):
    return quad(inp, fv(inp), fh(inp), r180(inp))

def three_by_three(inp, out):
    a, b = inp, fh(inp)
    c, d = fv(inp), r180(inp)
    rows = []
    for top, alt in ((a, b), (c, d), (a, b)):
        pass
    r0 = [x + y + z for x, y, z in zip(a, b, a)]
    r1 = [x + y + z for x, y, z in zip(c, d, c)]
    return r0 + r1 + r0

ALTERNATIVES = [
    ("tile the input 2x2 with no mirroring", plain_tiling),
    ("mirror only horizontally, repeat rows unflipped", only_h),
    ("mirror only vertically, repeat columns unflipped", only_v),
    ("anchor the input at the bottom-right tile instead of top-left", anchor_br),
    ("fill the tiles with rotations of the input instead of mirrors", rotations),
    ("fill the tiles with transposes of the input", transposes),
    ("output only the top half (one row of tiles)", top_strip),
    ("bottom-right tile copies the input instead of its 180-degree rotation", br_unmirrored),
    ("bottom-right tile left blank", br_blank),
    ("mirror across a shared edge row and column, so duplicated edge is dropped", shared_edge),
    ("horizontal and vertical flips swapped between the off-diagonal tiles", swapped_flips),
    ("extend the mirroring to a 3x3 arrangement", three_by_three),
]

def valid(g):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    w = len(g[0])
    return all(len(r) == w and all(isinstance(v, int) and 0 <= v <= 9 for v in r) for r in g)

if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/62c24649.json')))
    for desc, f in ALTERNATIVES:
        c = 0
        for p in t["train"]:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("ERR", desc, e)
                g = None
            if g is not None and valid(g) and g != p["output"]:
                c += 1
        print(c, "/", len(t["train"]), desc)
