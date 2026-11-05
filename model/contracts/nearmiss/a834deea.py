import json
from collections import Counter
from pathlib import Path

KEY = {(-1, -1): 1, (-1, 0): 7, (-1, 1): 6, (0, -1): 4, (0, 1): 5,
       (1, -1): 2, (1, 0): 9, (1, 1): 3}


def frame_color(inp):
    cnt = Counter(v for row in inp for v in row)
    return min(cnt, key=lambda k: (cnt[k], k))


def boxes(inp):
    """Top-left corners (r, c) of 5x5 windows whose border is all frame color."""
    f = frame_color(inp)
    h, w = len(inp), len(inp[0])
    res = []
    for r in range(h - 4):
        for c in range(w - 4):
            ok = all(inp[r][c + k] == f and inp[r + 4][c + k] == f
                     and inp[r + k][c] == f and inp[r + k][c + 4] == f
                     for k in range(5))
            if ok:
                res.append((r, c))
    return res


def copy(g):
    return [list(r) for r in g]


def fill(inp, key, cond=None, shift=(0, 0), only=None, center=None):
    f = frame_color(inp)
    g = copy(inp)
    bs = boxes(inp)
    if only is not None:
        bs = bs[:only]
    for r, c in bs:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr = r + 2 + dr + shift[0]
                cc = c + 2 + dc + shift[1]
                if not (0 <= rr < len(g) and 0 <= cc < len(g[0])):
                    continue
                if (dr, dc) == (0, 0):
                    if center is not None:
                        g[rr][cc] = center
                    continue
                if (dr, dc) not in key:
                    continue
                if cond is None or cond(inp[rr][cc], f):
                    g[rr][cc] = key[(dr, dc)]
    return g


def is_frame(v, f):
    return v == f


def not_frame(v, f):
    return v != f


def always(v, f):
    return True


def keymap(fn):
    return {p: KEY[fn(p)] for p in KEY}


def alt_center(inp, out):
    return fill(inp, KEY, is_frame, center=5)


def alt_mirror_lr(inp, out):
    return fill(inp, keymap(lambda p: (p[0], -p[1])), is_frame)


def alt_flip_ud(inp, out):
    return fill(inp, keymap(lambda p: (-p[0], p[1])), is_frame)


def alt_transpose(inp, out):
    return fill(inp, keymap(lambda p: (p[1], p[0])), is_frame)


def alt_rotate(inp, out):
    return fill(inp, keymap(lambda p: (p[1], -p[0])), is_frame)


def alt_corners_only(inp, out):
    k = {p: v for p, v in KEY.items() if p[0] != 0 and p[1] != 0}
    return fill(inp, k, is_frame)


def alt_edges_only(inp, out):
    k = {p: v for p, v in KEY.items() if p[0] == 0 or p[1] == 0}
    return fill(inp, k, is_frame)


def alt_all_cells(inp, out):
    return fill(inp, KEY, always)


def alt_single_color(inp, out):
    return fill(inp, {p: 4 for p in KEY}, is_frame)


def alt_shifted(inp, out):
    return fill(inp, KEY, is_frame, shift=(0, 1))


def alt_other_cells(inp, out):
    return fill(inp, KEY, not_frame)


def alt_first_box(inp, out):
    return fill(inp, KEY, is_frame, only=1)


def alt_unchanged(inp, out):
    return copy(inp)


ALTERNATIVES = [
    ("the center of the interior is recolored too (color 5)", alt_center),
    ("left and right interior keys are swapped", alt_mirror_lr),
    ("top and bottom interior keys are swapped", alt_flip_ud),
    ("keys are read transposed (row and column offsets swapped)", alt_transpose),
    ("keys are read rotated a quarter turn", alt_rotate),
    ("only corner cells of the interior are recolored", alt_corners_only),
    ("only side-middle cells of the interior are recolored", alt_edges_only),
    ("every non-center interior cell is recolored, not only frame-colored ones", alt_all_cells),
    ("every frame-colored interior cell gets one color (4)", alt_single_color),
    ("the interior window is taken one column to the right of the true one", alt_shifted),
    ("non-frame-colored interior cells are recolored instead of frame-colored ones", alt_other_cells),
    ("the input is returned unchanged", alt_unchanged),
]


def valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/a834deea.json"))
    pairs = task["train"]
    # sanity: the correct rule reproduces the outputs
    for p in pairs:
        assert fill(p["input"], KEY, is_frame) == p["output"], "correct rule check failed"
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(n, "/", len(pairs), desc)
