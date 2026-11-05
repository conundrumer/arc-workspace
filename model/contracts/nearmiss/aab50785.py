"""Near-miss readings for aab50785.

The rule: the input holds an even number of 2x2 blocks of one marker color
(8), which pair off along rows. Each pair bounds a window, the cells of the
band strictly between its two blocks. The windows stack top to bottom, in the
order of their bands, to form the output.
"""
import json
from pathlib import Path


def _marker(inp, out):
    ins = {v for r in inp for v in r}
    outs = {v for r in out for v in r}
    for col in sorted(ins - outs):
        for r in range(len(inp) - 1):
            for c in range(len(inp[0]) - 1):
                if inp[r][c] == inp[r][c + 1] == inp[r + 1][c] == inp[r + 1][c + 1] == col:
                    return col
    return 8


def _bands(inp, out):
    """List of (r0, r1, c_left_start, c_left_end, c_right_start, c_right_end)
    for each band, sorted top to bottom."""
    m = _marker(inp, out)
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == m and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == m and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                ys = [p[0] for p in cells]
                xs = [p[1] for p in cells]
                comps.append((min(ys), max(ys), min(xs), max(xs)))
    byrow = {}
    for b in comps:
        byrow.setdefault((b[0], b[1]), []).append(b)
    bands = []
    for (r0, r1), bl in sorted(byrow.items()):
        bl.sort(key=lambda b: b[2])
        a, b = bl[0], bl[-1]
        bands.append((r0, r1, a[2], a[3], b[2], b[3]))
    return bands


def _win(inp, r0, r1, c0, c1):
    return [list(inp[r][c0:c1 + 1]) for r in range(r0, r1 + 1)]


def _true_windows(inp, out):
    return [_win(inp, r0, r1, a1 + 1, b0 - 1) for r0, r1, a0, a1, b0, b1 in _bands(inp, out)]


def _stack(wins):
    res = []
    for w in wins:
        res.extend(w)
    return res


def includes_blocks(inp, out):
    return _stack([_win(inp, r0, r1, a0, b1) for r0, r1, a0, a1, b0, b1 in _bands(inp, out)])


def one_extra_col_left(inp, out):
    return _stack([_win(inp, r0, r1, a1, b0 - 1) for r0, r1, a0, a1, b0, b1 in _bands(inp, out)])


def one_col_short_right(inp, out):
    return _stack([_win(inp, r0, r1, a1 + 1, b0 - 2) for r0, r1, a0, a1, b0, b1 in _bands(inp, out)])


def extra_row_above(inp, out):
    wins = []
    for r0, r1, a0, a1, b0, b1 in _bands(inp, out):
        top = r0 - 1 if r0 > 0 else r0
        bot = r1 if r0 > 0 else r1 + 1
        wins.append(_win(inp, top, bot, a1 + 1, b0 - 1))
    return _stack(wins)


def bottom_to_top(inp, out):
    return _stack(list(reversed(_true_windows(inp, out))))


def side_by_side(inp, out):
    wins = _true_windows(inp, out)
    if len(wins) < 2:
        return None
    h = len(wins[0])
    return [sum((w[i] for w in wins), []) for i in range(h)]


def windows_mirrored(inp, out):
    return _stack([[row[::-1] for row in w] for w in _true_windows(inp, out)])


def window_rows_flipped(inp, out):
    return _stack([w[::-1] for w in _true_windows(inp, out)])


def first_window_only(inp, out):
    wins = _true_windows(inp, out)
    if len(wins) < 2:
        return None
    return wins[0]


def first_row_of_band_only(inp, out):
    return _stack([[w[0]] for w in _true_windows(inp, out)])


def zero_separator_rows(inp, out):
    wins = _true_windows(inp, out)
    if len(wins) < 2:
        return None
    res = []
    width = len(wins[0][0])
    for i, w in enumerate(wins):
        if i:
            res.append([0] * width)
        res.extend(w)
    return res


def transposed_output(inp, out):
    return [list(r) for r in zip(*out)]


ALTERNATIVES = [
    ("windows include the marker blocks themselves", includes_blocks),
    ("window starts one column too early, taking the last column of the left block", one_extra_col_left),
    ("window ends one column too early, dropping the last gap column", one_col_short_right),
    ("window band is one row taller, taking the row above the blocks", extra_row_above),
    ("windows stack bottom band first", bottom_to_top),
    ("windows are placed side by side instead of stacked", side_by_side),
    ("each window is mirrored left to right", windows_mirrored),
    ("rows inside each window are reversed", window_rows_flipped),
    ("only the top pair gives a window", first_window_only),
    ("only the first row of each band is copied", first_row_of_band_only),
    ("a row of 0 separates the stacked windows", zero_separator_rows),
    ("the stack is turned onto its side (transposed)", transposed_output),
]


def _valid(g, out):
    if not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/aab50785.json"))
    pairs = task["train"]
    print("pairs:", len(pairs), "readings:", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
