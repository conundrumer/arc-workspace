import json
from pathlib import Path

DIRS = [(-1, 0), (0, 1), (1, 0), (0, -1)]  # up, right, down, left (clockwise)


def _marker(inp):
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == 2:
                return r, c


def _heading(inp, r, c):
    h, w = len(inp), len(inp[0])
    if r == 0:
        return 2
    if r == h - 1:
        return 0
    if c == 0:
        return 1
    return 3


def _walk(inp, turn_of, mode="resume", head_shift=0, max_defl=None, paint_marker=True):
    """Simulate the walker. turn_of maps obstacle color -> +1 (right) / -1 (left).
    mode: resume (correct: sidestep then keep heading), stop (halt at obstacle),
    jump (skip over obstacle cells), permanent (sidestep and keep new heading),
    single (only one sidestep attempt, then halt if still blocked)."""
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    r, c = _marker(inp)
    d = (_heading(inp, r, c) + head_shift) % 4
    defl = 0
    for _ in range(2000):
        dr, dc = DIRS[d]
        nr, nc = r + dr, c + dc
        if not (0 <= nr < h and 0 <= nc < w):
            break
        if inp[nr][nc] == 0:
            r, c = nr, nc
            g[r][c] = 2
            continue
        if mode == "stop":
            break
        if mode == "jump":
            r, c = nr, nc
            continue
        if max_defl is not None and defl >= max_defl:
            break
        defl += 1
        t = turn_of(inp[nr][nc])
        sd = (d + t) % 4
        sr, sc = DIRS[sd]
        qr, qc = r + sr, c + sc
        if not (0 <= qr < h and 0 <= qc < w) or inp[qr][qc] != 0:
            break
        r, c = qr, qc
        g[r][c] = 2
        if mode == "permanent":
            d = sd
    if not paint_marker:
        mr, mc = _marker(inp)
        g[mr][mc] = 0
    return g


TRUE_TURN = lambda col: 1 if col == 3 else -1


def always_right(inp, out):
    return _walk(inp, lambda col: 1)


def always_left(inp, out):
    return _walk(inp, lambda col: -1)


def swapped_turns(inp, out):
    return _walk(inp, lambda col: -TRUE_TURN(col))


def stop_at_obstacle(inp, out):
    return _walk(inp, TRUE_TURN, mode="stop")


def jump_over_obstacles(inp, out):
    return _walk(inp, TRUE_TURN, mode="jump")


def permanent_turn(inp, out):
    return _walk(inp, TRUE_TURN, mode="permanent")


def single_sidestep(inp, out):
    # sidestep once, then stop if the ahead cell is still blocked
    g = _walk(inp, TRUE_TURN, max_defl=1)
    return g


def perpendicular_heading(inp, out):
    return _walk(inp, TRUE_TURN, head_shift=1)


def path_wrong_color(inp, out):
    mr, mc = _marker(inp)
    return [[1 if (v == 2 and (r, c) != (mr, mc)) else v for c, v in enumerate(row)]
            for r, row in enumerate(out)]


def marker_cell_erased(inp, out):
    mr, mc = _marker(inp)
    g = [row[:] for row in out]
    g[mr][mc] = 0
    return g


def path_only_after_first_deflection(inp, out):
    # erase path cells before the first sidestep: keep only paint on rows/cols past the straight run
    mr, mc = _marker(inp)
    d = DIRS[_heading(inp, mr, mc)]
    g = [row[:] for row in out]
    r, c = mr + d[0], mc + d[1]
    h, w = len(g), len(g[0])
    while 0 <= r < h and 0 <= c < w and inp[r][c] == 0:
        g[r][c] = 0
        r, c = r + d[0], c + d[1]
    return g


def obstacle_cells_painted(inp, out):
    # path paints over the obstacle cells it deflects around
    g = _walk(inp, TRUE_TURN)
    mr, mc = _marker(inp)
    d = DIRS[_heading(inp, mr, mc)]
    r, c = mr + d[0], mc + d[1]
    h, w = len(g), len(g[0])
    while 0 <= r < h and 0 <= c < w and inp[r][c] == 0:
        r, c = r + d[0], c + d[1]
    if 0 <= r < h and 0 <= c < w:
        g[r][c] = 2
    return g


ALTERNATIVES = [
    ("every deflection turns right", always_right),
    ("every deflection turns left", always_left),
    ("turn directions swapped between obstacle colors", swapped_turns),
    ("path stops at the first obstacle with no deflection", stop_at_obstacle),
    ("path jumps straight over obstacle cells without deflecting", jump_over_obstacles),
    ("after a sidestep the walker keeps the new heading", permanent_turn),
    ("walker deflects at most once, then stops", single_sidestep),
    ("walker heads perpendicular to the away-from-edge direction", perpendicular_heading),
    ("path is drawn in color 1 instead of 2", path_wrong_color),
    ("marker cell itself is erased", marker_cell_erased),
    ("straight run before the first obstacle is left unpainted", path_only_after_first_deflection),
    ("first obstacle cell is also painted 2", obstacle_cells_painted),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/96a8c0cd.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            ok = (
                g is not None
                and len(g) > 0
                and all(isinstance(row, list) and len(row) == len(g[0]) for row in g)
                and all(isinstance(v, int) and 0 <= v <= 9 for row in g for v in row)
                and g != p["output"]
            )
            n += ok
        print(n, desc)
