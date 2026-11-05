import json
from pathlib import Path


def _bg(inp):
    cnt = {}
    for r in inp:
        for v in r:
            cnt[v] = cnt.get(v, 0) + 1
    return max(cnt, key=cnt.get)


def _objects(inp):
    """8-connected components of non-background cells: (cells, color, bbox)."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    objs = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for da in (-1, 0, 1):
                    for db in (-1, 0, 1):
                        x, y = a + da, b + db
                        if 0 <= x < h and 0 <= y < w and (x, y) not in seen and inp[x][y] != bg:
                            seen.add((x, y))
                            stack.append((x, y))
            rs = [p[0] for p in cells]
            cs = [p[1] for p in cells]
            objs.append((cells, inp[r][c], (min(rs), min(cs), max(rs), max(cs))))
    return objs


def _corners(box):
    r0, c0, r1, c1 = box
    # (corner cell, outward direction)
    return [((r0, c0), (-1, -1)), ((r0, c1), (-1, 1)), ((r1, c0), (1, -1)), ((r1, c1), (1, 1))]


def _tips(inp):
    """Correct tips: empty bbox corners with outward diagonal direction and object color."""
    res = []
    for cells, col, box in _objects(inp):
        s = set(cells)
        for p, d in _corners(box):
            if p not in s:
                res.append((p, d, col))
    return res


def _copy(g):
    return [row[:] for row in g]


def _draw(inp, rays, start_off=0, maxlen=None, bounce=False, color=None):
    """rays: (corner, dir, color). Paint cells from corner + (start_off)*dir outward."""
    g = _copy(inp)
    h, w = len(g), len(g[0])
    for (r, c), (dr, dc), col in rays:
        k = start_off
        n = 0
        while True:
            x, y = r + dr * k, c + dc * k
            if not (0 <= x < h and 0 <= y < w):
                break
            if maxlen is not None and n >= maxlen:
                break
            g[x][y] = col if color is None else color
            k += 1
            n += 1
    return g


def start_on_corner(inp, out):
    return _draw(inp, _tips(inp), start_off=0)


def skip_first(inp, out):
    return _draw(inp, _tips(inp), start_off=2)


def short_ray(inp, out):
    return _draw(inp, _tips(inp), start_off=1, maxlen=3)


def wrong_color(inp, out):
    bg = _bg(inp)
    cols = {v for r in inp for v in r if v != bg}
    new = 5 if 5 not in cols else 8
    return _draw(inp, _tips(inp), start_off=1, color=new)


def mirrored_horizontal(inp, out):
    rays = [(p, (d[0], -d[1]), col) for p, d, col in _tips(inp)]
    return _draw(inp, rays, start_off=1)


def mirrored_vertical(inp, out):
    rays = [(p, (-d[0], d[1]), col) for p, d, col in _tips(inp)]
    return _draw(inp, rays, start_off=1)


def straight_horizontal(inp, out):
    rays = [(p, (0, d[1]), col) for p, d, col in _tips(inp)]
    return _draw(inp, rays, start_off=1)


def straight_vertical(inp, out):
    rays = [(p, (d[0], 0), col) for p, d, col in _tips(inp)]
    return _draw(inp, rays, start_off=1)


def all_corners(inp, out):
    rays = []
    for cells, col, box in _objects(inp):
        for p, d in _corners(box):
            rays.append((p, d, col))
    return _draw(inp, rays, start_off=1)


def only_largest_object(inp, out):
    objs = _objects(inp)
    if len(objs) < 2:
        return None
    big = max(objs, key=lambda o: len(o[0]))
    rays = []
    s = set(big[0])
    for p, d in _corners(big[2]):
        if p not in s:
            rays.append((p, d, big[1]))
    return _draw(inp, rays, start_off=1)


def both_directions(inp, out):
    rays = []
    for p, d, col in _tips(inp):
        rays.append((p, d, col))
        rays.append((p, (-d[0], -d[1]), col))
    g = _draw(inp, rays, start_off=1)
    # restore object cells so the object itself is not overwritten
    for cells, col, box in _objects(inp):
        for r, c in cells:
            g[r][c] = inp[r][c]
    return g


def bounce_at_wall(inp, out):
    g = _copy(inp)
    h, w = len(g), len(g[0])
    for (r, c), (dr, dc), col in _tips(inp):
        x, y = r + dr, c + dc
        for _ in range(h + w):
            if x < 0 or x >= h:
                dr = -dr
                x += 2 * dr
            if y < 0 or y >= w:
                dc = -dc
                y += 2 * dc
            if not (0 <= x < h and 0 <= y < w):
                break
            if inp[x][y] == _bg(inp):
                g[x][y] = col
            x += dr
            y += dc
    return g


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("ray starts on the empty bbox corner cell itself instead of the cell after it", start_on_corner),
    ("ray skips one more cell, starting two cells past the corner", skip_first),
    ("ray is cut off after 3 cells instead of running to the grid edge", short_ray),
    ("ray is painted in a color other than the object's color", wrong_color),
    ("ray direction mirrored left-right (leaves the bbox on the wrong side horizontally)", mirrored_horizontal),
    ("ray direction mirrored up-down (leaves the bbox on the wrong side vertically)", mirrored_vertical),
    ("ray goes straight horizontally from the empty corner instead of diagonally", straight_horizontal),
    ("ray goes straight vertically from the empty corner instead of diagonally", straight_vertical),
    ("rays are shot from every bbox corner, filled ones included", all_corners),
    ("only the largest object shoots a ray", only_largest_object),
    ("ray also extends backwards through the bbox, as a full diagonal line", both_directions),
    ("output equals the input", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/6e19193c.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
