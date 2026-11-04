from pathlib import Path
import json

MARK = 2


def parse(inp):
    cells = [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]
    r0 = min(r for r, c, v in cells)
    c0 = min(c for r, c, v in cells)
    r1 = max(r for r, c, v in cells)
    c1 = max(c for r, c, v in cells)
    trail = [v for r, c, v in cells if v != MARK][0]
    markers = [(r, c) for r, c, v in cells if v == MARK]
    corners = []
    for r, c in markers:
        dr = -1 if r - r0 < r1 - r else 1
        dc = -1 if c - c0 < c1 - c else 1
        corners.append((dr, dc))
    return cells, (r0, c0, r1, c1), trail, markers, corners


def render(inp, sources, dirs, color, keep_marks=False, limit=None, block_color=None):
    n, m = len(inp), len(inp[0])
    cells, _, trail, markers, _ = parse(inp)
    g = [[0] * m for _ in range(n)]
    for r, c in sources:
        for dr, dc in dirs:
            rr, cc, k = r, c, 0
            while 0 <= rr < n and 0 <= cc < m and (limit is None or k <= limit):
                g[rr][cc] = color
                rr += dr
                cc += dc
                k += 1
    for r, c, v in cells:
        if keep_marks:
            g[r][c] = v
        elif block_color is not None:
            g[r][c] = block_color
        else:
            g[r][c] = trail
    return g


def block_cells(inp):
    return [(r, c) for r, c, v in parse(inp)[0]]


def reverse_dirs(inp, out):
    cells, bb, trail, markers, corners = parse(inp)
    return render(inp, block_cells(inp), [(-a, -b) for a, b in corners], trail)


def only_marker_sources(inp, out):
    cells, bb, trail, markers, corners = parse(inp)
    return render(inp, markers, corners, trail)


def mark_color_rays(inp, out):
    cells, bb, trail, markers, corners = parse(inp)
    return render(inp, block_cells(inp), corners, MARK, block_color=MARK)


def marks_stay(inp, out):
    cells, bb, trail, markers, corners = parse(inp)
    return render(inp, block_cells(inp), corners, trail, keep_marks=True)


def first_marker_only(inp, out):
    cells, bb, trail, markers, corners = parse(inp)
    return render(inp, block_cells(inp), corners[:1], trail)


def orthogonal(inp, out):
    cells, bb, trail, markers, corners = parse(inp)
    dirs = set()
    for a, b in corners:
        dirs.add((a, 0))
        dirs.add((0, b))
    return render(inp, block_cells(inp), sorted(dirs), trail)


def all_diagonals(inp, out):
    cells, bb, trail, markers, corners = parse(inp)
    return render(inp, block_cells(inp), [(1, 1), (1, -1), (-1, 1), (-1, -1)], trail)


def short_rays(inp, out):
    cells, bb, trail, markers, corners = parse(inp)
    return render(inp, block_cells(inp), corners, trail, limit=3)


def vertical_mirror(inp, out):
    cells, bb, trail, markers, corners = parse(inp)
    return render(inp, block_cells(inp), [(-a, b) for a, b in corners], trail)


def nonmarker_sources(inp, out):
    cells, bb, trail, markers, corners = parse(inp)
    src = [(r, c) for r, c, v in cells if v != MARK]
    return render(inp, src, corners, trail)


def one_corner_sources_opposite(inp, out):
    # rays only from the block cell diagonally opposite each marker
    cells, bb, trail, markers, corners = parse(inp)
    r0, c0, r1, c1 = bb
    src = []
    for a, b in corners:
        src.append((r1 if a == -1 else r0, c1 if b == -1 else c0))
    return render(inp, src, corners, trail)


def unfilled_block(inp, out):
    g = [row[:] for row in out]
    for r, c, v in parse(inp)[0]:
        g[r][c] = 0
    return g


ALTERNATIVES = [
    ("rays go away from the marker corner instead of toward it", reverse_dirs),
    ("only the marker cells cast rays, not the whole block", only_marker_sources),
    ("rays and block are drawn in the marker color instead of the other block color", mark_color_rays),
    ("marker cells keep the marker color while rays use the other color", marks_stay),
    ("only the first marker corner gets rays", first_marker_only),
    ("rays go straight up/down/left/right instead of diagonally", orthogonal),
    ("rays go in all four diagonal directions", all_diagonals),
    ("rays stop after a short fixed length", short_rays),
    ("ray direction is flipped vertically only", vertical_mirror),
    ("only the non-marker block cells cast rays", nonmarker_sources),
    ("only the block cell diagonally opposite each marker casts rays", one_corner_sources_opposite),
    ("block cells are erased and only rays remain", unfilled_block),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/1f0c79e5.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for name, f in ALTERNATIVES:
        k = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", e)
                g = None
            if g is not None and valid(g, p["output"]):
                k += 1
        print(k, name)
