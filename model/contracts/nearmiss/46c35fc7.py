import json
from collections import Counter
from pathlib import Path

# Ring positions clockwise from top-left; even indices are corners, odd are edges.
RING = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]


def find_rings(g):
    h, w = len(g), len(g[0])
    bg = Counter(v for r in g for v in r).most_common(1)[0][0]
    rings = []
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            if g[r][c] == bg and all(g[r + a][c + b] != bg for a, b in RING):
                rings.append((r, c))
    return rings


def permute(g, src_of, only=None, skip_first=False):
    """Rewrite each ring: new[i] = old[src_of(i)]; src_of returns None to keep."""
    res = [row[:] for row in g]
    rings = find_rings(g)
    if only is not None:
        rings = [rings[only]] if len(rings) > only else []
    for r, c in rings:
        for i, (a, b) in enumerate(RING):
            s = src_of(i)
            if s is None:
                continue
            da, db = RING[s % 8]
            res[r + a][c + b] = g[r + da][c + db]
    return res


def corners_ccw_edges_cw(i):  # true rule
    return (i + 2) % 8 if i % 2 == 0 else (i - 2) % 8


def both_cw(inp, out):
    return permute(inp, lambda i: (i - 2) % 8)


def both_ccw(inp, out):
    return permute(inp, lambda i: (i + 2) % 8)


def swapped_senses(inp, out):
    return permute(inp, lambda i: (i - 2) % 8 if i % 2 == 0 else (i + 2) % 8)


def two_steps(inp, out):
    return permute(inp, lambda i: (i + 4) % 8 if i % 2 == 0 else (i - 4) % 8)


def single_cycle(inp, out):
    return permute(inp, lambda i: (i - 1) % 8)


def corners_only(inp, out):
    return permute(inp, lambda i: (i + 2) % 8 if i % 2 == 0 else None)


def edges_only(inp, out):
    return permute(inp, lambda i: (i - 2) % 8 if i % 2 == 1 else None)


def mirror_ring(inp, out):
    return permute(inp, lambda i: (-i) % 8)


def one_ring_only(inp, out):
    if len(find_rings(inp)) < 2:
        return None
    return permute(inp, corners_ccw_edges_cw, only=0)


def hole_filled(inp, out):
    res = [row[:] for row in out]
    for r, c in find_rings(inp):
        res[r][c] = inp[r - 1][c]
    return res


def ring_transposed_and_rotated(inp, out):
    # Reflect across the main diagonal instead of rotating.
    return permute(inp, lambda i: (2 - i) % 8)


def ring_cells_zeroed_ring_unmoved(inp, out):
    # Ring moved but the rotated ring cells' corners swapped with the opposite corner only.
    return permute(inp, lambda i: (i + 4) % 8 if i % 2 == 0 else None)


ALTERNATIVES = [
    ("corners and edges both rotate clockwise", both_cw),
    ("corners and edges both rotate counterclockwise", both_ccw),
    ("corner and edge senses swapped (corners cw, edges ccw)", swapped_senses),
    ("corners and edges each turn two steps in the true senses", two_steps),
    ("whole 8-cell ring shifts one position clockwise as a single cycle", single_cycle),
    ("only the corners rotate, edges stay", corners_only),
    ("only the edges rotate, corners stay", edges_only),
    ("ring is mirrored left-right instead of rotated", mirror_ring),
    ("only the first ring found is rotated, others left alone", one_ring_only),
    ("rotation correct but the hole is filled with the top-edge color", hole_filled),
    ("ring reflected across the main diagonal", ring_transposed_and_rotated),
    ("corners swap with the opposite corner, edges stay", ring_cells_zeroed_ring_unmoved),
]


def valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    w = len(g[0])
    if any(not isinstance(r, list) or len(r) != w for r in g):
        return False
    if any(not isinstance(v, int) or not 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/46c35fc7.json").read_text())
    pairs = task["train"]
    for p in pairs:
        assert permute(p["input"], corners_ccw_edges_cw) == p["output"], "true rule check"
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(n, desc)
