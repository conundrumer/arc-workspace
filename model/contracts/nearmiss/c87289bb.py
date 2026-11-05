"""Near-miss readings for c87289bb: 8 streams fall from the top edge; a stream
that meets a row of 2-bars detours around the bar's nearer end."""
import json
from pathlib import Path


def _simulate(inp, pick=None, exit_off=1, lane_shift=0, fall=True,
              blocked_stop=False, through=False, run_color=8, fall_color=8,
              fall_from_run=True, run_short=0, lane_at_end=False):
    """Run the streams. pick(c, a, b, w) returns -1 (left) or +1 (right)."""
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    bar_rows = [r for r in range(h) if any(v == 2 for v in inp[r])]
    if not bar_rows:
        return g
    r = bar_rows[0]
    streams = [c for c in range(w) if inp[0][c] == 8]
    for c in streams:
        s = 0
        while s + 1 < h and inp[s + 1][c] == 8:
            s += 1
        if inp[r][c] != 2:
            for i in range(s + 1, h):
                if g[i][c] == 0:
                    g[i][c] = 8
            continue
        a = c
        while a > 0 and inp[r][a - 1] == 2:
            a -= 1
        b = c
        while b < w - 1 and inp[r][b + 1] == 2:
            b += 1
        lane = s if lane_at_end else r - 1 + lane_shift
        for i in range(s + 1, lane + 1):
            g[i][c] = 8
        if through:
            for i in range(lane + 1, h):
                if g[i][c] == 0:
                    g[i][c] = 8
            continue
        if blocked_stop:
            continue
        d = pick(c, a, b, w)
        end = a if d < 0 else b
        e = end + d * exit_off
        if not 0 <= e < w:
            continue
        lo, hi = min(c, e), max(c, e)
        if run_short:
            if e > c:
                hi -= 1
            else:
                lo += 1
        for x in range(lo, hi + 1):
            if g[lane][x] in (0, 8):
                g[lane][x] = run_color
        if fall:
            start = lane if fall_from_run else lane + 1
            for i in range(start, h):
                if g[i][e] == 0:
                    g[i][e] = fall_color
    return g


def _nearer(right_on_tie):
    def pick(c, a, b, w):
        dl, dr = c - a, b - c
        if dl < dr:
            return -1
        if dr < dl:
            return 1
        return 1 if right_on_tie else -1
    return pick


def _farther(c, a, b, w):
    dl, dr = c - a, b - c
    if dl < dr:
        return 1
    if dr < dl:
        return -1
    return 1


def _edge_nearer(c, a, b, w):
    return -1 if c < w - 1 - c else 1


def _tie_left(inp, out):
    return _simulate(inp, _nearer(False))


def _farther_end(inp, out):
    return _simulate(inp, _farther)


def _always_right(inp, out):
    return _simulate(inp, lambda c, a, b, w: 1)


def _always_left(inp, out):
    return _simulate(inp, lambda c, a, b, w: -1)


def _stop_above_bar(inp, out):
    return _simulate(inp, blocked_stop=True)


def _pass_through_bar(inp, out):
    return _simulate(inp, through=True)


def _exit_on_end_cell(inp, out):
    return _simulate(inp, _nearer(True), exit_off=0)


def _exit_two_past(inp, out):
    return _simulate(inp, _nearer(True), exit_off=2)


def _no_fall_after_run(inp, out):
    return _simulate(inp, _nearer(True), fall=False)


def _detour_painted_2(inp, out):
    return _simulate(inp, _nearer(True), run_color=2, fall_color=2)


def _run_stops_short(inp, out):
    # lateral run stops one cell before the exit column; the fall starts below the lane
    return _simulate(inp, _nearer(True), run_short=1, fall_from_run=False)


def _lane_at_stream_end(inp, out):
    # the lateral run happens in the stream's last row, not in the row above the bar
    return _simulate(inp, _nearer(True), lane_at_end=True)


ALTERNATIVES = [
    ("tie at the bar's middle cell goes left instead of right", _tie_left),
    ("stream detours toward the bar's farther end", _farther_end),
    ("every detour goes right", _always_right),
    ("every detour goes left", _always_left),
    ("stream stops on the cell above the bar, no detour", _stop_above_bar),
    ("stream falls straight through the bar's column, bar keeps its color", _pass_through_bar),
    ("fall starts in the bar's end column (off by one, not past the end)", _exit_on_end_cell),
    ("fall starts two cells past the bar's end", _exit_two_past),
    ("stream runs along the bar to the end but does not fall on", _no_fall_after_run),
    ("detour cells are painted with the bar color 2", _detour_painted_2),
    ("lateral run stops one cell short of the exit column, leaving a gap", _run_stops_short),
    ("lateral run is drawn in the stream's last row instead of the row above the bar", _lane_at_stream_end),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/c87289bb.json"))
    pairs = task["train"]
    # sanity: the base simulation reproduces the true output
    base = [_simulate(p["input"], _nearer(True)) == p["output"] for p in pairs]
    print("base reproduces outputs:", base)
    for name, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), name)
