from pathlib import Path
import json

M = 2


def cp(g):
    return [r[:] for r in g]


def slide(inp, dr, dc, limit=None):
    """Move every 2 by up to `limit` cells (None = until blocked) in direction (dr, dc),
    stopping at non-zero cells and at already placed movers."""
    g = cp(inp)
    h, w = len(g), len(g[0])
    cells = [(r, c) for r in range(h) for c in range(w) if g[r][c] == M]
    for r, c in cells:
        g[r][c] = 0
    # process nearest-to-the-destination first
    cells.sort(key=lambda p: p[0] * dr + p[1] * dc)
    for r, c in cells:
        n = 0
        while 0 <= r + dr < h and 0 <= c + dc < w and g[r + dr][c + dc] == 0:
            if limit is not None and n >= limit:
                break
            r += dr
            c += dc
            n += 1
        g[r][c] = M
    return g


def gravity_down(inp, out):
    return slide(inp, 1, 0)


def gravity_left(inp, out):
    return slide(inp, 0, -1)


def gravity_right(inp, out):
    return slide(inp, 0, 1)


def one_step(inp, out):
    return slide(inp, -1, 0, limit=1)


def erased_only(inp, out):
    return [[0 if v == M else v for v in r] for r in out]


def keep_originals(inp, out):
    g = cp(out)
    for r in range(len(g)):
        for c in range(len(g[0])):
            if inp[r][c] == M:
                g[r][c] = M
    return g


def recolored_one(inp, out):
    return [[1 if v == M else v for v in r] for r in out]


def no_stacking(inp, out):
    # every mover in a column stops at the landing cell of the first mover
    g = cp(out)
    h, w = len(g), len(g[0])
    for c in range(w):
        rows = [r for r in range(h) if g[r][c] == M]
        if len(rows) > 1:
            for r in rows[1:]:
                g[r][c] = 0
    return g


def ignore_structure(inp, out):
    # structure does not block: movers fly to the top edge
    g = cp(inp)
    h, w = len(g), len(g[0])
    for c in range(w):
        n = sum(1 for r in range(h) if g[r][c] == M)
        for r in range(h):
            if g[r][c] == M:
                g[r][c] = 0
        for r in range(n):
            g[r][c] = M
    return g


def lowest_stays_out(inp, out):
    # the lowest landed mover in each column is lost
    g = cp(out)
    h, w = len(g), len(g[0])
    for c in range(w):
        rows = [r for r in range(h) if g[r][c] == M]
        if rows:
            g[max(rows)][c] = 0
    return g


def gap_below_structure(inp, out):
    # off by one: movers stop one cell short of the structure
    g = cp(out)
    h, w = len(g), len(g[0])
    for c in range(w):
        rows = sorted((r for r in range(h) if g[r][c] == M), reverse=True)
        for r in rows:
            if r + 1 < h and g[r + 1][c] == 0:
                g[r][c] = 0
                g[r + 1][c] = M
    return g


def first_mover_column_only(inp, out):
    # only the leftmost column that holds movers is moved
    h, w = len(inp), len(inp[0])
    cols = [c for c in range(w) if any(inp[r][c] == M for r in range(h))]
    if not cols:
        return None
    c0 = cols[0]
    moved = slide(inp, -1, 0)
    g = cp(inp)
    for r in range(h):
        g[r][c0] = moved[r][c0]
    return g


ALTERNATIVES = [
    ("movers fall down instead of up", gravity_down),
    ("movers slide left instead of up", gravity_left),
    ("movers slide right instead of up", gravity_right),
    ("movers move only one cell up", one_step),
    ("movers leave their start cells but land cells are not drawn", erased_only),
    ("movers are copied to the landing cells but also stay at their start cells", keep_originals),
    ("landed movers take the structure color 1", recolored_one),
    ("movers do not stack: one mover per column lands", no_stacking),
    ("structure does not block: movers pile at the top edge", ignore_structure),
    ("the lowest mover of each column is lost", lowest_stays_out),
    ("movers stop one cell short of the structure", gap_below_structure),
    ("only the leftmost mover column moves up", first_mover_column_only),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/3906de3d.json')))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(cp(p["input"]), cp(p["output"]))
            except Exception as e:
                print("  error", e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
