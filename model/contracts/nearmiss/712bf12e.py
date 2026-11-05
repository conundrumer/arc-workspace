import json
from pathlib import Path

BG = 0
MARK = 2


def _markers(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == MARK]


def _walk(inp, *, up=True, turn=1, paint=2, paint_side=True, max_turns=None,
          alternate=False, through=False, only_first=False, short=0,
          keep_marker_blockers=True):
    """Simulate marker walks. Moves up from each marker; when the next cell is
    blocked, steps sideways (turn=+1 right, -1 left) and continues."""
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    ms = _markers(inp)
    if only_first:
        ms = sorted(ms, key=lambda p: p[1])[:1]
    dr = -1 if up else 1
    for (r, c) in ms:
        if not up:
            r = 0 if r == h - 1 else r
        turns = 0
        t = turn
        steps = 0
        limit = h - 1 - short
        while steps < limit + w * 2:
            steps += 1
            nr = r + dr
            if nr < 0 or nr >= h:
                break
            if short and (nr < short if up else nr > h - 1 - short):
                break
            v = inp[nr][c]
            if v == BG or (through and v != MARK):
                r = nr
                g[r][c] = paint
                continue
            if max_turns is not None and turns >= max_turns:
                break
            nc = c + t
            if 0 <= nc < w and inp[r][nc] == BG:
                c = nc
                if paint_side:
                    g[r][c] = paint
                turns += 1
                if alternate:
                    t = -t
                continue
            break
    return g


def _true(inp):
    return _walk(inp)


def a_left(inp, out):
    return _walk(inp, turn=-1)


def a_no_turn(inp, out):
    return _walk(inp, max_turns=0)


def a_through(inp, out):
    return _walk(inp, through=True)


def a_from_top(inp, out):
    return _walk(inp, up=False)


def a_color5(inp, out):
    return _walk(inp, paint=5)


def a_no_side_paint(inp, out):
    return _walk(inp, paint_side=False)


def a_first_only(inp, out):
    return _walk(inp, only_first=True)


def a_one_turn(inp, out):
    return _walk(inp, max_turns=1)


def a_short(inp, out):
    return _walk(inp, short=1)


def a_alternate(inp, out):
    return _walk(inp, alternate=True)


def a_erase_blockers(inp, out):
    # true output, but the blocking 5 cells touched by walks are replaced by 2
    g = [row[:] for row in out]
    h, w = len(g), len(g[0])
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 5 and any(
                0 <= r + dr < h and 0 <= c + dc < w and out[r + dr][c + dc] == 2
                and inp[r + dr][c + dc] == 0 for dr, dc in ((1, 0), (0, 1), (0, -1))
            ):
                g[r][c] = 2
    return g


def a_marker_row_only(inp, out):
    # only the vertical straight column above each marker, no turning, ignoring blockers
    g = [row[:] for row in inp]
    for (r, c) in _markers(inp):
        for rr in range(r):
            g[rr][c] = 2
    return g


ALTERNATIVES = [
    ("walk sidesteps left instead of right at a blocker", a_left),
    ("walk stops at the first blocker, no sidestep", a_no_turn),
    ("walk passes straight through blocking cells, overwriting them", a_through),
    ("walks start from the top edge and go down", a_from_top),
    ("walk is painted with the blocker color 5", a_color5),
    ("sidestep cell is skipped when painting the walk", a_no_side_paint),
    ("only the leftmost marker casts a walk", a_first_only),
    ("walk sidesteps at most once, then stops at the next blocker", a_one_turn),
    ("walk ends one row short of the top edge", a_short),
    ("walk alternates sidestep direction, right then left", a_alternate),
    ("blocker cells beside a walk are also recolored to 2", a_erase_blockers),
    ("full straight column above each marker, ignoring blockers", a_marker_row_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/712bf12e.json'))
    pairs = task["train"]
    assert all(_true(p["input"]) == p["output"] for p in pairs), "sim mismatch"
    print("task 712bf12e pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
