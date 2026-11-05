import json
from pathlib import Path


def _bg(inp):
    flat = [c for r in inp for c in r]
    return max(set(flat), key=flat.count)


def _pieces(inp):
    """Return list of (color, cells, bend_corner, missing_corner); corners as (dr, dc) in {0,1}."""
    bg = _bg(inp)
    n, m = len(inp), len(inp[0])
    seen = set()
    res = []
    for r in range(n):
        for c in range(m):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            col = inp[r][c]
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y = a + da, b + db
                    if 0 <= x < n and 0 <= y < m and (x, y) not in seen and inp[x][y] == col:
                        seen.add((x, y))
                        stack.append((x, y))
            r0 = min(a for a, _ in cells)
            c0 = min(b for _, b in cells)
            box = {(r0 + i, c0 + j) for i in range(2) for j in range(2)}
            missing = list(box - set(cells))
            if len(cells) != 3 or len(missing) != 1:
                continue
            mr, mc = missing[0][0] - r0, missing[0][1] - c0
            res.append((col, cells, (1 - mr, 1 - mc), (mr, mc), (r0, c0)))
    return res


def _build(inp, corner_of, arm=None, arms=("h", "v"), bg_fill=None):
    n, m = len(inp), len(inp[0])
    bg = _bg(inp)
    g = [[bg] * m for _ in range(n)]
    k = (n - 1) // 2 if arm is None else arm
    for p in _pieces(inp):
        col = p[0]
        cr, cc = corner_of(p, n, m)
        if "h" in arms:
            for i in range(k):
                g[cr][i if cc == 0 else m - 1 - i] = col
        if "v" in arms:
            for i in range(k):
                g[i if cr == 0 else n - 1 - i][cc] = col
    return g


def _corner_rc(flag, n, m):
    return (0 if flag[0] == 0 else n - 1, 0 if flag[1] == 0 else m - 1)


def _std(p, n, m):
    return _corner_rc(p[2], n, m)


def alt_missing_corner(inp, out):
    return _build(inp, lambda p, n, m: _corner_rc(p[3], n, m))


def alt_quadrant(inp, out):
    def f(p, n, m):
        r = sum(a for a, _ in p[1]) / 3
        c = sum(b for _, b in p[1]) / 3
        return (0 if r < (n - 1) / 2 else n - 1, 0 if c < (m - 1) / 2 else m - 1)
    return _build(inp, f)


def alt_arm_through_middle(inp, out):
    return _build(inp, _std, arm=(len(inp) - 1) // 2 + 1)


def alt_arm_short(inp, out):
    return _build(inp, _std, arm=(len(inp) - 1) // 2 - 1)


def alt_horizontal_only(inp, out):
    return _build(inp, _std, arms=("h",))


def alt_vertical_only(inp, out):
    return _build(inp, _std, arms=("v",))


def alt_flip_lr(inp, out):
    return [row[::-1] for row in out]


def alt_flip_tb(inp, out):
    return out[::-1]


def alt_piece_at_corner(inp, out):
    n, m = len(inp), len(inp[0])
    g = [[_bg(inp)] * m for _ in range(n)]
    for p in _pieces(inp):
        cr, cc = _std(p, n, m)
        # stamp the original L shape, mirrored to fit the corner
        r0, c0 = p[4]
        for (a, b) in p[1]:
            i, j = a - r0, b - c0
            rr = i if cr == 0 else n - 1 - i
            cc2 = j if cc == 0 else m - 1 - j
            g[rr][cc2] = p[0]
    return g


def alt_swap_horizontal_colors(inp, out):
    # arms placed correctly, but colors of left and right corner pairs exchanged
    return _swap(inp)


def _swap(inp):
    n, m = len(inp), len(inp[0])
    bg = _bg(inp)
    g = [[bg] * m for _ in range(n)]
    k = (n - 1) // 2
    for p in _pieces(inp):
        cr, cc = _std(p, n, m)
        # paint horizontal arm with the color of the piece, vertical arm in the same color,
        # but at the corner on the opposite side horizontally
        cc = m - 1 - cc
        for i in range(k):
            g[cr][i if cc == 0 else m - 1 - i] = p[0]
            g[i if cr == 0 else n - 1 - i][cc] = p[0]
    return g


def alt_full_edges(inp, out):
    return _build(inp, _std, arm=len(inp))


ALTERNATIVES = [
    ("each piece goes to the corner of its missing cell instead of its bend cell", alt_missing_corner),
    ("each piece goes to the corner nearest its position in the input", alt_quadrant),
    ("arms run one cell too far, through the middle row and column", alt_arm_through_middle),
    ("arms stop one cell too early", alt_arm_short),
    ("only the horizontal arm is drawn", alt_horizontal_only),
    ("only the vertical arm is drawn", alt_vertical_only),
    ("correct output mirrored left to right", alt_flip_lr),
    ("correct output mirrored top to bottom", alt_flip_tb),
    ("the piece itself is stamped into the corner instead of two arms", alt_piece_at_corner),
    ("each piece goes to the horizontally opposite corner of the correct one", alt_swap_horizontal_colors),
    ("arms run the full length of both edges", alt_full_edges),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/b745798f.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        ok = 0
        for pr in pairs:
            try:
                g = fn(pr["input"], pr["output"])
            except Exception as e:
                print("  error", e)
                g = None
            if g is not None and _valid(g) and g != pr["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
