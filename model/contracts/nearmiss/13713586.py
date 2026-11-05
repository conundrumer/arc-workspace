import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _wall(inp, bg):
    """Return (wall color, direction (dr, dc) from bars toward the wall)."""
    h, w = len(inp), len(inp[0])
    sides = {
        (-1, 0): inp[0],
        (1, 0): inp[h - 1],
        (0, -1): [r[0] for r in inp],
        (0, 1): [r[w - 1] for r in inp],
    }
    for d, line in sides.items():
        if len(set(line)) == 1 and line[0] != bg:
            return line[0], d
    return None, (0, 1)


def _bars(inp, bg, wall):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if (r, c) in seen or inp[r][c] in (bg, wall):
                continue
            col = inp[r][c]
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] == col:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            comps.append((col, min(ys), max(ys), min(xs), max(xs)))
    return comps


def _paint(inp, d=None, near_wins=True, stop_at_bar=False, extra=0, trim=0,
           conflict_empty=False, color_override=None, only=None, cover_bars=False,
           widen_both=False):
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    wall, wd = _wall(inp, bg)
    if d is None:
        d = wd
    comps = _bars(inp, bg, wall)
    if only is not None:
        comps = only(comps, wd)
    claims = {}
    for col, r0, r1, c0, c1 in comps:
        if d[1] != 0:
            lines = range(max(0, r0 - (extra if widen_both else 0)), min(h, r1 + 1 + extra))
            k = (w - 1 - c1) if d[1] > 0 else c0
            start = c1 + 1 if d[1] > 0 else c0 - 1
            for y in lines:
                x = start
                while 0 <= x < w:
                    if inp[y][x] != bg:
                        if stop_at_bar and inp[y][x] != wall:
                            break
                        if not cover_bars or inp[y][x] == wall:
                            x += d[1]
                            continue
                    claims.setdefault((y, x), []).append((k, col))
                    x += d[1]
        else:
            lines = range(max(0, c0 - (extra if widen_both else 0)), min(w, c1 + 1 + extra))
            k = (h - 1 - r1) if d[0] > 0 else r0
            start = r1 + 1 if d[0] > 0 else r0 - 1
            for x in lines:
                y = start
                while 0 <= y < h:
                    if inp[y][x] != bg:
                        if stop_at_bar and inp[y][x] != wall:
                            break
                        if not cover_bars or inp[y][x] == wall:
                            y += d[0]
                            continue
                    claims.setdefault((y, x), []).append((k, col))
                    y += d[0]
    res = [row[:] for row in inp]
    for (y, x), lst in claims.items():
        if inp[y][x] == wall:
            continue
        if trim:
            if d[1] != 0:
                dist = (w - 1 - x) if d[1] > 0 else x
            else:
                dist = (h - 1 - y) if d[0] > 0 else y
            if dist <= trim:
                continue
        lst.sort()
        if conflict_empty and len({c for _, c in lst}) > 1:
            continue
        res[y][x] = lst[0][1] if near_wins else lst[-1][1]
        if color_override is not None:
            res[y][x] = color_override(wall)
    return res


def _opposite(inp, out):
    bg = _bg(inp)
    _, d = _wall(inp, bg)
    return _paint(inp, d=(-d[0], -d[1]))


def _perp(inp, out):
    bg = _bg(inp)
    _, d = _wall(inp, bg)
    return _paint(inp, d=(d[1], d[0]))


def _perp_rev(inp, out):
    bg = _bg(inp)
    _, d = _wall(inp, bg)
    return _paint(inp, d=(-d[1], -d[0]))


def _far_wins(inp, out):
    return _paint(inp, near_wins=False)


def _stop_bar(inp, out):
    return _paint(inp, stop_at_bar=True)


def _trim_one(inp):
    bg = _bg(inp)
    wall, d = _wall(inp, bg)
    h, w = len(inp), len(inp[0])
    res = _paint(inp)
    for y in range(h):
        for x in range(w):
            if inp[y][x] != bg:
                continue
            ny, nx = y + d[0], x + d[1]
            if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == wall:
                res[y][x] = inp[y][x]
    return res


def _conflict(inp, out):
    return _paint(inp, conflict_empty=True)


def _wall_color(inp, out):
    return _paint(inp, color_override=lambda wall: wall)


def _wider(inp, out):
    return _paint(inp, extra=1)


def _wider_both(inp, out):
    return _paint(inp, extra=1, widen_both=True)


def _only_nearest(inp, out):
    def pick(comps, d):
        def key(c):
            col, r0, r1, c0, c1 = c
            if d[1] > 0:
                return -c1
            if d[1] < 0:
                return c0
            if d[0] > 0:
                return -r1
            return r0
        return [min(comps, key=key)] if comps else comps
    return _paint(inp, only=pick)


def _only_farthest(inp, out):
    def pick(comps, d):
        def key(c):
            col, r0, r1, c0, c1 = c
            if d[1] > 0:
                return c1
            if d[1] < 0:
                return -c0
            if d[0] > 0:
                return r1
            return -r0
        return [min(comps, key=key)] if comps else comps
    return _paint(inp, only=pick)


def _cover_bars(inp, out):
    return _paint(inp, cover_bars=True, near_wins=False)


def _bars_dropped(inp, out):
    """True shadows, but a bar covered by a farther bar's shadow keeps the shadow color."""
    return _paint(inp, cover_bars=True)


def _unchanged(inp, out):
    return [r[:] for r in inp]


def _short_ray(inp, out):
    """Shadow only one cell deep next to each bar."""
    bg = _bg(inp)
    wall, d = _wall(inp, bg)
    full = _paint(inp)
    res = [r[:] for r in inp]
    h, w = len(inp), len(inp[0])
    for y in range(h):
        for x in range(w):
            if full[y][x] != inp[y][x]:
                py, px = y - d[0], x - d[1]
                if 0 <= py < h and 0 <= px < w and inp[py][px] not in (bg, wall):
                    res[y][x] = full[y][x]
    return res


ALTERNATIVES = [
    ("shadow cast away from the wall instead of toward it", _opposite),
    ("shadow cast along the axis perpendicular to the wall", _perp),
    ("shadow cast perpendicular, to the opposite side of the perpendicular one", _perp_rev),
    ("a bar farther from the wall wins where shadows overlap", _far_wins),
    ("a shadow paints over other bars in its path (nearer shadow still wins)", _bars_dropped),
    ("shadow stops one cell short of the wall", lambda inp, out: _trim_one(inp)),
    ("cells hit by shadows of different colors stay empty", _conflict),
    ("shadows painted in the wall color", _wall_color),
    ("shadow one cell wider than the bar on one side", _wider),
    ("shadow one cell wider than the bar on both sides", _wider_both),
    ("only the bar nearest the wall casts a shadow", _only_nearest),
    ("only the bar farthest from the wall casts a shadow", _only_farthest),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/13713586.json'))
    pairs = task["train"]

    def valid(g, out):
        return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != out)

    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
    # sanity: the generic solver matches the true output
    print("solver ok:", all(_paint(p["input"]) == p["output"] for p in pairs))
