import json
from pathlib import Path


def _key(inp):
    cells = [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v not in (0, 5)]
    cells.sort()
    return cells


def _trails(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 5 and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                comp = []
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            q = (y + dy, x + dx)
                            if 0 <= q[0] < h and 0 <= q[1] < w and inp[q[0]][q[1]] == 5 and q not in seen:
                                seen.add(q)
                                stack.append(q)
                comps.append(comp)
    return comps


def _geometry(comp, head):
    """Return (n, T, cell -> (u, v)) for a trail; head is 'top' or 'bottom'."""
    r0 = min(r for r, _ in comp)
    r1 = max(r for r, _ in comp)
    c0 = min(c for _, c in comp)
    c1 = max(c for _, c in comp)
    S = r1 - r0 + 1
    edge = r0 if head == "top" else r1
    row_cols = [c for r, c in comp if r == edge]
    n = len(row_cols)
    hc = min(row_cols)
    dc = 1 if hc == c0 else -1
    T = S - n
    uv = {}
    for r, c in comp:
        u = r - r0 if head == "top" else r1 - r
        v = c - hc if dc == 1 else hc + n - 1 - c
        uv[(r, c)] = (u, v)
    return n, T, uv, dc


def _paint(inp, head="top", reverse=False, phase=0, first_wins=False, cap=True,
           clamp=False, dn=0, only_largest=False, u_only=False, head_by_reading=False):
    key = [v for _, _, v in _key(inp)]
    if reverse:
        key = key[::-1]
    K = len(key)
    g = [row[:] for row in inp]
    comps = _trails(inp)
    if only_largest and len(comps) < 2:
        return None
    if only_largest:
        comps = [max(comps, key=len)]
    for comp in comps:
        hd = head
        if head_by_reading:
            c0 = min(c for _, c in comp)
            top_c = min(c for r, c in comp if r == min(r for r, _ in comp))
            hd = "top" if top_c == c0 else "bottom"
        n, T, uv, _ = _geometry(comp, hd)
        m = n + dn
        for (r, c), (u, v) in uv.items():
            lo = max(0, max(u, v) - m + 1)
            hi = min(u, v, T) if cap else min(u, v)
            if u_only:
                hi = min(u, T)
                lo = 0
            if lo > hi:
                continue
            t = lo if first_wins else hi
            idx = min(t, K - 1) if clamp else (t + phase) % K
            g[r][c] = key[idx % K]
    return g


def _reverse_key(inp, out):
    return _paint(inp, reverse=True)


def _far_head(inp, out):
    return _paint(inp, head="bottom")


def _reading_head(inp, out):
    return _paint(inp, head_by_reading=True)


def _first_wins(inp, out):
    return _paint(inp, first_wins=True)


def _phase(inp, out):
    return _paint(inp, phase=1)


def _clamp(inp, out):
    return _paint(inp, clamp=True)


def _no_cap(inp, out):
    return _paint(inp, cap=False)


def _small_square(inp, out):
    return _paint(inp, dn=-1)


def _largest_only(inp, out):
    return _paint(inp, only_largest=True)


def _u_only(inp, out):
    return _paint(inp, u_only=True)


def _erase_key(inp, out):
    g = [row[:] for row in out]
    for r, c, _ in _key(inp):
        g[r][c] = 0
    return g


ALTERNATIVES = [
    ("key colors read in reverse order (from the other end of the key)", _reverse_key),
    ("slide starts at the end of each trail far from the key line", _far_head),
    ("slide starts at the end that comes first left to right, not the end nearer the key", _reading_head),
    ("a cell takes the color of the first step that covers it, not the last", _first_wins),
    ("color cycle is shifted one step: step t takes c(t+1)", _phase),
    ("key colors are used once each, the last color then repeats, with no cycling", _clamp),
    ("the far square is not solid: the step index is not capped at T", _no_cap),
    ("the moving square is one cell smaller than the trail's end square", _small_square),
    ("only the largest trail is recolored, other trails stay 5", _largest_only),
    ("color depends only on the distance from the head's top edge, not the side edge", _u_only),
    ("the key is erased from the output", _erase_key),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/b457fec5.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    # sanity: the correct reading reproduces the true outputs
    print("correct reading matches:", sum(_paint(p["input"]) == p["output"] for p in pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
