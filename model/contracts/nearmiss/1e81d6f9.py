import json
from collections import Counter
from pathlib import Path


def _wall(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 5]
    return max(r for r, _ in cells), max(c for _, c in cells)


def _target(inp):
    """Box (top-left of the 5 wall), target color, and the target cells outside the box."""
    wr, wc = _wall(inp)
    col = None
    for r in range(wr):
        for c in range(wc):
            if inp[r][c] not in (0, 5):
                col = inp[r][c]
    outside = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row)
               if v == col and not (r < wr and c < wc)]
    return wr, wc, col, outside


def _copy(g):
    return [row[:] for row in g]


def erase_everywhere(inp, out):
    wr, wc, col, _ = _target(inp)
    return [[0 if v == col else v for v in row] for row in inp]


def erase_first_only(inp, out):
    _, _, _, outside = _target(inp)
    g = _copy(inp)
    r, c = outside[0]
    g[r][c] = 0
    return g


def erase_bottom_right_only(inp, out):
    n, m = len(inp), len(inp[0])
    _, _, _, outside = _target(inp)
    g = _copy(inp)
    for r, c in outside:
        if r >= n // 2 and c >= m // 2:
            g[r][c] = 0
    return g


def erase_most_common_other_color(inp, out):
    _, _, col, _ = _target(inp)
    cnt = Counter(v for row in inp for v in row if v not in (0, 5, col))
    other = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    wr, wc, _, _ = _target(inp)
    return [[0 if (v == other and not (r < wr and c < wc)) else v
             for c, v in enumerate(row)] for r, row in enumerate(inp)]


def erase_wall_too(inp, out):
    return [[0 if v == 5 else v for v in row] for row in out]


def fill_with_wall_color(inp, out):
    return [[5 if (inp[r][c] != out[r][c]) else out[r][c] for c in range(len(out[0]))]
            for r in range(len(out))]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def box_at_bottom_right(inp, out):
    n, m = len(inp), len(inp[0])
    wr, wc, col, _ = _target(inp)
    return [[0 if (v == col and not (r >= n - wr and c >= m - wc)) else v
             for c, v in enumerate(row)] for r, row in enumerate(inp)]


def erase_neighborhood(inp, out):
    n, m = len(inp), len(inp[0])
    _, _, _, outside = _target(inp)
    g = _copy(inp)
    for r, c in outside:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < n and 0 <= cc < m and g[rr][cc] != 5:
                    g[rr][cc] = 0
    return None if g == out else g


def keep_only_target_color(inp, out):
    wr, wc, col, _ = _target(inp)
    return [[v if v in (col, 5) else 0 for v in row] for row in inp]


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("erase the target color everywhere, including the corner box", erase_everywhere),
    ("erase only the first target-color cell outside the box (row-major)", erase_first_only),
    ("erase target-color cells only in the bottom-right quadrant", erase_bottom_right_only),
    ("erase the most common other color outside the box instead of the target color", erase_most_common_other_color),
    ("correct erasure but the 5 wall is also erased", erase_wall_too),
    ("erased cells are filled with 5 instead of background 0", fill_with_wall_color),
    ("correct output transposed (wrong orientation)", transposed),
    ("keep zone is read as the bottom-right corner box instead of top-left", box_at_bottom_right),
    ("erase the 3x3 neighborhood of each target-color cell outside the box", erase_neighborhood),
    ("keep only target color and wall, erase every other color", keep_only_target_color),
    ("return the input unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/1e81d6f9.json'))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for name, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), name)
