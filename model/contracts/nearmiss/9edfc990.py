from pathlib import Path
import json
from collections import deque

N4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
N8 = N4 + [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def flood(inp, seeds=None, nbrs=N4, maxdist=None, passable=(0,)):
    """Return the set of cells reached from seeds through passable cells."""
    h, w = len(inp), len(inp[0])
    if seeds is None:
        seeds = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == 1]
    dist = {s: 0 for s in seeds}
    q = deque(seeds)
    reached = set()
    while q:
        r, c = q.popleft()
        d = dist[(r, c)]
        if maxdist is not None and d >= maxdist:
            continue
        for dr, dc in nbrs:
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w and (rr, cc) not in dist and inp[rr][cc] in passable:
                dist[(rr, cc)] = d + 1
                reached.add((rr, cc))
                q.append((rr, cc))
    return reached


def paint(inp, cells, color=1):
    g = [row[:] for row in inp]
    for r, c in cells:
        g[r][c] = color
    return g


def diag(inp, out):
    return paint(inp, flood(inp, nbrs=N8))


def one_step(inp, out):
    return paint(inp, flood(inp, maxdist=1))


def two_steps(inp, out):
    return paint(inp, flood(inp, maxdist=2))


def first_seed_only(inp, out):
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == 1:
                return paint(inp, flood(inp, seeds=[(r, c)]))
    return None


def all_zeros(inp, out):
    return paint(inp, [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 0])


def wrong_color(inp, out):
    return paint(inp, flood(inp), 3)


def not_border(inp, out):
    h, w = len(inp), len(inp[0])
    cells = [(r, c) for r, c in flood(inp) if 0 < r < h - 1 and 0 < c < w - 1]
    return paint(inp, cells)


def horizontal_only(inp, out):
    return paint(inp, flood(inp, nbrs=[(0, 1), (0, -1)]))


def vertical_only(inp, out):
    return paint(inp, flood(inp, nbrs=[(1, 0), (-1, 0)]))


def border_seeds(inp, out):
    h, w = len(inp), len(inp[0])
    seeds = [(r, c) for r in range(h) for c in range(w)
             if inp[r][c] == 1 and (r in (0, h - 1) or c in (0, w - 1))]
    return paint(inp, flood(inp, seeds=seeds))


def largest_region_only(inp, out):
    reached = flood(inp)
    comps, seen = [], set()
    for s in reached:
        if s in seen:
            continue
        comp, q = {s}, [s]
        seen.add(s)
        while q:
            r, c = q.pop()
            for dr, dc in N4:
                n = (r + dr, c + dc)
                if n in reached and n not in seen:
                    seen.add(n)
                    comp.add(n)
                    q.append(n)
        comps.append(comp)
    if not comps:
        return None
    return paint(inp, max(comps, key=len))


def fill_and_neighbors(inp, out):
    h, w = len(inp), len(inp[0])
    reached = flood(inp)
    extra = set(reached)
    for r, c in reached:
        for dr, dc in N4:
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] in (2, 3):
                extra.add((rr, cc))
    return paint(inp, extra)


ALTERNATIVES = [
    ("flood spreads through 8-neighbours instead of 4", diag),
    ("each 1 only colors its adjacent 0 cells (one step)", one_step),
    ("flood stops after two steps from each 1", two_steps),
    ("only the first 1 in reading order seeds the flood", first_seed_only),
    ("every 0 cell becomes 1, no connectivity needed", all_zeros),
    ("flood fills reached cells with the wrong color 3", wrong_color),
    ("flood never recolors cells on the grid border", not_border),
    ("flood spreads only along rows", horizontal_only),
    ("flood spreads only along columns", vertical_only),
    ("only 1s on the grid border seed the flood", border_seeds),
    ("only the largest reached region is filled", largest_region_only),
    ("flood also recolors adjacent 2 and 3 cells", fill_and_neighbors),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/9edfc990.json')))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
