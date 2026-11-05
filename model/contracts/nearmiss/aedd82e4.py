import json
from pathlib import Path

D4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
D8 = D4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def copy(g):
    return [list(r) for r in g]


def isolated(inp, dirs=D4, wrap=False, ink=2):
    h, w = len(inp), len(inp[0])
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != ink:
                continue
            ok = True
            for dr, dc in dirs:
                rr, cc = r + dr, c + dc
                if wrap:
                    rr, cc = rr % h, cc % w
                if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] == ink and (rr, cc) != (r, c):
                    ok = False
                    break
            if ok:
                res.append((r, c))
    return res


def paint(inp, cells, color):
    g = copy(inp)
    for r, c in cells:
        g[r][c] = color
    return g


def components(inp, ink=2):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == ink and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                comp = []
                while st:
                    a, b = st.pop()
                    comp.append((a, b))
                    for dr, dc in D4:
                        x, y = a + dr, b + dc
                        if 0 <= x < h and 0 <= y < w and inp[x][y] == ink and (x, y) not in seen:
                            seen.add((x, y))
                            st.append((x, y))
                comps.append(comp)
    return comps


def eight_conn(inp, out):
    return paint(inp, isolated(inp, D8), 1)


def mark_eight(inp, out):
    return [[8 if v == 1 else v for v in r] for r in out]


def mark_three(inp, out):
    return [[3 if v == 1 else v for v in r] for r in out]


def horizontal_only(inp, out):
    return paint(inp, isolated(inp, [(0, -1), (0, 1)]), 1)


def vertical_only(inp, out):
    return paint(inp, isolated(inp, [(-1, 0), (1, 0)]), 1)


def inverted(inp, out):
    iso = set(isolated(inp))
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 2 and (r, c) not in iso]
    return paint(inp, cells, 1)


def small_components(inp, out):
    cells = [p for comp in components(inp) if len(comp) <= 4 for p in comp]
    return paint(inp, cells, 1)


def drop_one(inp, out):
    iso = isolated(inp)
    if not iso:
        return None
    r, c = iso[0]
    g = copy(out)
    g[r][c] = 2
    return g


def only_last(inp, out):
    iso = isolated(inp)
    if not iso:
        return None
    return paint(inp, [iso[-1]], 1)


def wrap_around(inp, out):
    return paint(inp, isolated(inp, wrap=True), 1)


def border_excluded(inp, out):
    h, w = len(inp), len(inp[0])
    cells = [(r, c) for r, c in isolated(inp) if 0 < r < h - 1 and 0 < c < w - 1]
    return paint(inp, cells, 1)


def unchanged(inp, out):
    return copy(inp)


ALTERNATIVES = [
    ("isolation judged with 8-connectivity (diagonal neighbours count as grouped)", eight_conn),
    ("isolated cells marked with 8 instead of 1", mark_eight),
    ("isolated cells marked with 3 instead of 1", mark_three),
    ("isolation judged by horizontal neighbours only", horizontal_only),
    ("isolation judged by vertical neighbours only", vertical_only),
    ("inverted: cells that have a neighbour are marked, isolated ones stay", inverted),
    ("every component of size 4 or less is marked", small_components),
    ("one isolated cell (first in reading order) left unmarked", drop_one),
    ("only the last isolated cell in reading order is marked", only_last),
    ("grid treated as wrapping around its edges when judging isolation", wrap_around),
    ("isolated cells on the border of the grid are not marked", border_excluded),
    ("input returned unchanged", unchanged),
]


def valid(g, out):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/aedd82e4.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
