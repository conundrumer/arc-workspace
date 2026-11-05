import json
from collections import Counter
from pathlib import Path


def _analyse(inp):
    h, w = len(inp), len(inp[0])
    edges = {
        (0, 1): [inp[r][0] for r in range(h)],      # wall on the left, away = right
        (0, -1): [inp[r][w - 1] for r in range(h)],
        (1, 0): list(inp[0]),
        (-1, 0): list(inp[h - 1]),
    }
    away = None
    for d, line in edges.items():
        if len(set(line)) == 1:
            away = d
            break
    wall = edges[away][0]
    counts = Counter(v for row in inp for v in row)
    bg = counts.most_common(1)[0][0]
    mark = min((c for c in counts if c not in (wall, bg)), key=lambda c: counts[c])
    dr, dc = away
    runs = []
    seen = set()
    for r in range(h):
        for c in range(w):
            if inp[r][c] == mark and (r, c) not in seen:
                # walk back to the start of the run against the away direction
                pr, pc = r - dr, c - dc
                if 0 <= pr < h and 0 <= pc < w and inp[pr][pc] == mark:
                    continue
                cells = []
                rr, cc = r, c
                while 0 <= rr < h and 0 <= cc < w and inp[rr][cc] == mark:
                    cells.append((rr, cc))
                    seen.add((rr, cc))
                    rr += dr
                    cc += dc
                runs.append(cells)
    full = max(len(x) for x in runs)
    return h, w, away, wall, bg, mark, runs, full


def _line_cells(h, w, away, cell):
    """Cells of the line through `cell` along the away axis, ordered from the wall."""
    dr, dc = away
    r, c = cell
    while 0 <= r - dr < h and 0 <= c - dc < w:
        r -= dr
        c -= dc
    out = []
    while 0 <= r < h and 0 <= c < w:
        out.append((r, c))
        r += dr
        c += dc
    return out


def _build(inp, erase_full=True, land_color="wall", land_len=None, land_shift=0,
           land_at_wall=False, ext_short=1, ext_full=0, ext_color="mark",
           ext_back=False, move_short=False, full_thresh=None, keep_full_in_place=False):
    h, w, away, wall, bg, mark, runs, full = _analyse(inp)
    if full_thresh is None:
        full_thresh = full
    g = [row[:] for row in inp]
    dr, dc = away
    colors = {"wall": wall, "mark": mark, "bg": bg}
    landings = []
    for run in runs:
        n = len(run)
        is_full = n >= full_thresh
        if is_full or move_short:
            if erase_full:
                for r, c in run:
                    g[r][c] = bg
            line = _line_cells(h, w, away, run[0])
            k = n if land_len is None else land_len
            if land_at_wall:
                cells = line[:k]
            else:
                cells = line[len(line) - k - land_shift: len(line) - land_shift]
            landings.append(cells)
        if is_full:
            ext = ext_full
        else:
            ext = ext_short
        if ext and (not is_full or ext_full) and not (move_short and not is_full):
            sgn = -1 if ext_back else 1
            er, ec = (run[-1] if not ext_back else run[0])
            for i in range(1, ext + 1):
                r, c = er + sgn * dr * i, ec + sgn * dc * i
                if 0 <= r < h and 0 <= c < w:
                    g[r][c] = colors[ext_color]
    for cells in landings:
        for r, c in cells:
            g[r][c] = colors[land_color]
    return g


def _correct(inp, out):
    return _build(inp)


def _no_land(inp, keep):
    h, w, away, wall, bg, mark, runs, full = _analyse(inp)
    g = [row[:] for row in inp]
    dr, dc = away
    for run in runs:
        if len(run) < full:
            r, c = run[-1]
            g[r + dr][c + dc] = mark
    return g


def _erase_only(inp, out):
    h, w, away, wall, bg, mark, runs, full = _analyse(inp)
    g = _no_land(inp, keep=True)
    for run in runs:
        if len(run) >= full:
            for r, c in run:
                g[r][c] = bg
    return g


def _no_erase(inp, out):
    return _build(inp, erase_full=False)


def _land_mark_color(inp, out):
    return _build(inp, land_color="mark")


def _short_not_extended(inp, out):
    return _build(inp, ext_short=0)


def _short_extended_twice(inp, out):
    return _build(inp, ext_short=2)


def _short_extended_toward_wall(inp, out):
    return _build(inp, ext_back=True)


def _short_extended_wall_color(inp, out):
    return _build(inp, ext_color="wall")


def _land_one_short(inp, out):
    return _build(inp, land_shift=1)


def _land_at_wall(inp, out):
    return _build(inp, land_at_wall=True)


def _land_single_cell(inp, out):
    return _build(inp, land_len=1)


def _every_run_moves(inp, out):
    return _build(inp, move_short=True)


ALTERNATIVES = [
    ("full runs are erased but nothing lands at the far edge", _erase_only),
    ("full runs land at the far edge but their original cells stay", _no_erase),
    ("landed runs are painted in the mark colour instead of the wall colour", _land_mark_color),
    ("short runs are left as they are (not extended away from the wall)", _short_not_extended),
    ("short runs are extended by two cells instead of one", _short_extended_twice),
    ("short runs are extended toward the wall instead of away from it", _short_extended_toward_wall),
    ("short runs are extended with the wall colour instead of the mark colour", _short_extended_wall_color),
    ("full runs land one cell short of the far edge", _land_one_short),
    ("full runs land against the wall side instead of the far edge", _land_at_wall),
    ("full runs land as a single cell instead of keeping their length", _land_single_cell),
    ("every run slides to the far edge, none is extended", _every_run_moves),
    ("full runs stay in place and short runs are extended", lambda i, o: _no_land(i, True)),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/758abdf0.json"))
    pairs = task["train"]
    assert all(_correct(p["input"], p["output"]) == p["output"] for p in pairs), "model of true rule is wrong"
    print("task 758abdf0, pairs:", len(pairs), "readings:", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(n, desc)
