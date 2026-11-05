import json
from pathlib import Path


def T(g):
    return [list(r) for r in zip(*g)]


def detect(inp):
    """Return (transposed, a, b, F, L, P) with lines at columns a<b in the oriented grid."""
    F = inp[0][0]
    for tr in (False, True):
        g = T(inp) if tr else inp
        H, W = len(g), len(g[0])
        for c in sorted({v for r in g for v in r} - {F, 0}):
            cols = [j for j in range(W) if sum(1 for i in range(H) if g[i][j] == c) >= H - 2]
            if len(cols) == 2:
                a, b = cols
                rest = {v for r in g for v in r} - {F, 0, c}
                P = min(rest) if rest else 2
                return tr, a, b, F, c, P
    raise ValueError("no lines")


def oriented(fn):
    """Run fn on the oriented (vertical lines) grids, then orient back."""
    def run(inp, out):
        tr, a, b, F, L, P = detect(inp)
        i2, o2 = (T(inp), T(out)) if tr else (inp, out)
        res = fn(i2, [r[:] for r in o2], a, b, F, L, P)
        if res is None:
            return None
        return T(res) if tr else res
    return run


@oriented
def wrong_pattern_color(inp, o, a, b, F, L, P):
    # outside bands painted with the pattern colour instead of the frame colour
    for r in o:
        for j in range(len(r)):
            if (j < a or j > b) and r[j] == F:
                r[j] = P
    return o


@oriented
def inverted_phase(inp, o, a, b, F, L, P):
    # outside: frame colour and background swapped
    for r in o:
        for j in range(len(r)):
            if j < a or j > b:
                r[j] = 0 if r[j] == F else F
    return o


@oriented
def lines_not_extended(inp, o, a, b, F, L, P):
    # lines stay inside the frame; the first and last rows keep the frame colour on them
    H = len(o)
    for i in (0, H - 1):
        o[i][a] = F
        o[i][b] = F
    return o


@oriented
def frame_kept(inp, o, a, b, F, L, P):
    # frame cells outside the strip are left as in the input
    H, W = len(o), len(o[0])
    for i in range(H):
        for j in range(W):
            if (j < a or j > b) and (i in (0, H - 1) or j in (0, W - 1)):
                o[i][j] = inp[i][j]
    return o


@oriented
def phase_shift(inp, o, a, b, F, L, P):
    # outside bands shifted one cell along the lines
    H, W = len(o), len(o[0])
    res = [r[:] for r in o]
    for i in range(H):
        for j in range(W):
            if j < a or j > b:
                res[i][j] = o[(i + 1) % H][j]
    return res


@oriented
def outside_line_color(inp, o, a, b, F, L, P):
    # outside bands painted with the line colour
    for r in o:
        for j in range(len(r)):
            if (j < a or j > b) and r[j] == F:
                r[j] = L
    return o


@oriented
def strip_pattern_erased(inp, o, a, b, F, L, P):
    # pattern cells between the lines are cleared to background
    for r in o:
        for j in range(a + 1, b):
            if r[j] == P:
                r[j] = 0
    return o


@oriented
def one_side_only(inp, o, a, b, F, L, P):
    # bands painted only on the high-index side; the other side is background
    for r in o:
        for j in range(a):
            r[j] = 0
    return o


@oriented
def lines_erased(inp, o, a, b, F, L, P):
    # lines removed from the output
    for r in o:
        r[a] = 0
        r[b] = 0
    return o


@oriented
def band_too_thick(inp, o, a, b, F, L, P):
    # each outside band is one cell too long
    H, W = len(o), len(o[0])
    res = [r[:] for r in o]
    for i in range(1, H):
        for j in range(W):
            if (j < a or j > b) and o[i - 1][j] == F:
                res[i][j] = F
    return res


def crop_frame(inp, out):
    # frame cropped away
    return [r[1:-1] for r in out[1:-1]]


def unchanged(inp, out):
    return [r[:] for r in inp]


ALTERNATIVES = [
    ("outside bands use the pattern colour instead of the frame colour", wrong_pattern_color),
    ("outside bands in anti-phase: frame colour and background swapped", inverted_phase),
    ("lines not extended through the first and last row/column", lines_not_extended),
    ("frame cells outside the strip kept as in the input", frame_kept),
    ("outside bands shifted one cell along the lines", phase_shift),
    ("outside bands use the line colour", outside_line_color),
    ("pattern between the lines cleared", strip_pattern_erased),
    ("bands painted on one side of the strip only", one_side_only),
    ("lines removed from the output", lines_erased),
    ("outside bands one cell too long", band_too_thick),
    ("frame cropped away", crop_frame),
    ("input returned unchanged", unchanged),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/6a980be1.json'))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
