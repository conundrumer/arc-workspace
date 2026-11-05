"""Near-miss readings for ac3e2b04.

Rule: parallel full-length lines of one color; a mark is a 3x3 frame of the mark
color around a line cell. Through each mark center a new line runs across the
grid at right angles to the marked line, painting background cells. Where the new
line crosses another line (not at a mark), the eight cells around the crossing
take the new color.
"""
import json
from pathlib import Path


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _colors(g):
    return {v for r in g for v in r}


def _draw_color(inp, out):
    new = _colors(out) - _colors(inp)
    return min(new) if new else 1


def _marks(g):
    h, w = len(g), len(g[0])
    res = []
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            ring = [g[r + dr][c + dc] for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                    if (dr, dc) != (0, 0)]
            if g[r][c] != 0 and len(set(ring)) == 1 and ring[0] not in (0, g[r][c]):
                res.append((r, c))
    return res


def _solve(inp, D, frames="eight", color=None, half=False, stop=False,
           first_only=False, skip_marked_lines=False, overwrite=False,
           erase_marks=False, crossing_color=None, bg_only=False, radius=1):
    """Correct solver with switches for the wrong readings."""
    g = [list(r) for r in inp]
    full_rows = [i for i, row in enumerate(g) if all(v != 0 for v in row)]
    transposed = False
    if not full_rows:
        g = _transpose(g)
        transposed = True
        full_rows = [i for i, row in enumerate(g) if all(v != 0 for v in row)]
    h, w = len(g), len(g[0])
    src = [list(r) for r in g]
    marks = _marks(src)
    if first_only:
        marks = marks[:1]
    marked_rows = {r for r, _ in marks}
    paint = D if color is None else color
    out = [list(r) for r in src]
    if erase_marks:
        for r, c in marks:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if (dr, dc) != (0, 0):
                        out[r + dr][c + dc] = 0
    mark_centers = set(marks)
    for r, c in marks:
        rows = range(h)
        crossings = []
        if stop:
            reach = {r}
            for step in (-1, 1):
                i = r + step
                while 0 <= i < h:
                    reach.add(i)
                    if i in full_rows:
                        break
                    i += step
            rows = sorted(reach)
        if half:
            rows = [i for i in rows if i >= r]
        for i in rows:
            if overwrite or src[i][c] == 0:
                out[i][c] = paint
            if i in full_rows and i != r and (i, c) not in mark_centers:
                if skip_marked_lines and i in marked_rows:
                    continue
                crossings.append(i)
        for i in crossings:
            if frames == "none":
                continue
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    if (dr, dc) == (0, 0):
                        continue
                    if frames == "plus" and dr != 0 and dc != 0:
                        continue
                    y, x = i + dr, c + dc
                    if 0 <= y < h and 0 <= x < w:
                        if bg_only and src[y][x] != 0:
                            continue
                        out[y][x] = paint
            if crossing_color is not None:
                out[i][c] = crossing_color
    return _transpose(out) if transposed else out


def no_frames(inp, out):
    return _solve(inp, _draw_color(inp, out), frames="none")


def plus_frames(inp, out):
    return _solve(inp, _draw_color(inp, out), frames="plus")


def half_line(inp, out):
    return _solve(inp, _draw_color(inp, out), half=True)


def wide_frames(inp, out):
    return _solve(inp, _draw_color(inp, out), radius=2)


def crossing_painted(inp, out):
    D = _draw_color(inp, out)
    return _solve(inp, D, crossing_color=D)


def mark_color_line(inp, out):
    D = _draw_color(inp, out)
    marks = _marks(inp)
    m = inp[marks[0][0] - 1][marks[0][1] - 1]
    return _solve(inp, D, color=m)


def overwrite_path(inp, out):
    return _solve(inp, _draw_color(inp, out), overwrite=True)


def erase_marks(inp, out):
    return _solve(inp, _draw_color(inp, out), erase_marks=True)


def first_mark_only(inp, out):
    return _solve(inp, _draw_color(inp, out), first_only=True)


def stop_at_next_line(inp, out):
    return _solve(inp, _draw_color(inp, out), stop=True)


def skip_marked_lines(inp, out):
    return _solve(inp, _draw_color(inp, out), skip_marked_lines=True)


def frame_background_only(inp, out):
    return _solve(inp, _draw_color(inp, out), bg_only=True)


ALTERNATIVES = [
    ("new line drawn but no frames at crossings", no_frames),
    ("crossing frame covers only the four orthogonal neighbors", plus_frames),
    ("new line runs only from the mark to the far edge, one direction", half_line),
    ("crossing frame is 5x5 (radius 2) instead of 3x3", wide_frames),
    ("crossing cell itself is painted with the new color", crossing_painted),
    ("new line is drawn in the mark color instead of a new color", mark_color_line),
    ("new line overwrites every cell on its path, lines and marks included", overwrite_path),
    ("marks are erased in the output", erase_marks),
    ("only the first mark in reading order produces a line", first_mark_only),
    ("new line stops at the first other line in each direction", stop_at_next_line),
    ("crossings with lines that carry a mark get no frame", skip_marked_lines),
    ("crossing frame paints only background cells, line cells stay", frame_background_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/ac3e2b04.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {fn.__name__}: {desc}")
