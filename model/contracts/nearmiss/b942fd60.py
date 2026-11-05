import json
from collections import Counter
from pathlib import Path

DIRS = [(0, 1), (1, 0), (0, -1), (-1, 0)]


def _find(inp):
    cnt = Counter(c for r in inp for c in r)
    bg = cnt.most_common(1)[0][0]
    line = min(cnt, key=lambda c: (cnt[c], c))
    for y, r in enumerate(inp):
        for x, c in enumerate(r):
            if c == line:
                return bg, line, (y, x)


def _start_dir(inp, seed):
    h, w = len(inp), len(inp[0])
    y, x = seed
    if x == 0:
        return (0, 1)
    if x == w - 1:
        return (0, -1)
    if y == 0:
        return (1, 0)
    return (-1, 0)


def sim(inp, depth=None, sides=(1, -1), stop=0, edge_branch=False,
        zero_branch=False, color=None, seed_blocks=False, starts=None,
        pass_through=False, back=0, erase=False):
    """Ray simulation. stop: 0 stops before the obstacle, -1 paints the
    obstacle cell too, 1 stops one cell earlier."""
    h, w = len(inp), len(inp[0])
    bg, line, seed = _find(inp)
    g = [r[:] for r in inp]
    col = line if color is None else color
    if starts is None:
        starts = [_start_dir(inp, seed)]
    todo = [(seed, d, 0) for d in starts]
    seen = set()
    while todo:
        (y, x), d, lvl = todo.pop()
        if ((y, x), d) in seen:
            continue
        seen.add(((y, x), d))
        cy, cx = y, x
        n = 0
        hit = False
        while True:
            ny, nx = cy + d[0], cx + d[1]
            if not (0 <= ny < h and 0 <= nx < w):
                break
            c = inp[ny][nx]
            blocked = c != bg and not (c == line and not seed_blocks)
            if blocked and pass_through:
                blocked = False
            if blocked:
                hit = True
                if stop == -1:
                    cy, cx = ny, nx
                    n += 1
                break
            cy, cx = ny, nx
            n += 1
        if stop == 1 and hit and n > 0:
            cy, cx = cy - d[0], cx - d[1]
            n -= 1
        # paint
        py, px = y, x
        for _ in range(n):
            py, px = py + d[0], px + d[1]
            if g[py][px] == bg or stop == -1:
                g[py][px] = col
        if erase and hit:
            ey, ex = cy + d[0], cx + d[1]
            if stop == 0 and 0 <= ey < h and 0 <= ex < w:
                g[ey][ex] = bg
        if back and n >= 1 + back:
            cy, cx = cy - back * d[0], cx - back * d[1]
        if depth is not None and lvl >= depth:
            continue
        if (hit or edge_branch) and (n > 0 or zero_branch):
            for s in sides:
                pd = (d[1] * s, -d[0] * s)
                todo.append(((cy, cx), pd, lvl + 1))
    return g


def a_no_branch(inp, out):
    return sim(inp, depth=0)


def a_one_level(inp, out):
    return sim(inp, depth=1)


def a_one_side(inp, out):
    return sim(inp, sides=(1,))


def a_paint_obstacle(inp, out):
    return sim(inp, stop=-1)


def a_early_stop(inp, out):
    return sim(inp, stop=1)


def a_edge_branch(inp, out):
    return sim(inp, edge_branch=True)


def a_back_branch(inp, out):
    return sim(inp, back=1)


def a_erase(inp, out):
    return sim(inp, erase=True)


def a_all_dirs(inp, out):
    return sim(inp, starts=DIRS)


def a_pass_through(inp, out):
    return sim(inp, pass_through=True)


def a_wrong_color(inp, out):
    bg, line, seed = _find(inp)
    cnt = Counter(c for r in inp for c in r)
    others = [c for c in cnt if c not in (bg, line)]
    if not others:
        return None
    return sim(inp, color=max(others, key=lambda c: (cnt[c], c)))


def a_wrong_start(inp, out):
    bg, line, seed = _find(inp)
    d = _start_dir(inp, seed)
    return sim(inp, starts=[(d[1], d[0])])


ALTERNATIVES = [
    ("only the first ray is drawn, no branches", a_no_branch),
    ("branches are drawn one level deep only", a_one_level),
    ("a ray branches to one perpendicular side only", a_one_side),
    ("a ray also paints the obstacle it hits and branches from it", a_paint_obstacle),
    ("a ray stops two cells before an obstacle", a_early_stop),
    ("a ray that reaches the grid edge also branches", a_edge_branch),
    ("branches leave from the cell before the stop cell", a_back_branch),
    ("the obstacle a ray stops at is erased to background", a_erase),
    ("rays leave the seed in all four directions", a_all_dirs),
    ("rays run through obstacles to the grid edge", a_pass_through),
    ("rays are painted in the most common obstacle color", a_wrong_color),
    ("the first ray runs along the grid edge the seed lies on", a_wrong_start),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/b942fd60.json').read_text())
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings', len(pairs), 'pairs')
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(n, desc)
