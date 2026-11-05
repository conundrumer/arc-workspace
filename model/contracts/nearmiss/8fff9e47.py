import json
from pathlib import Path


def _blocks(inp, s):
    """Blocks of s x s cells, keyed by (block row, block col)."""
    h, w = len(inp), len(inp[0])
    return {
        (br, bc): [row[bc * s:(bc + 1) * s] for row in inp[br * s:(br + 1) * s]]
        for br in range(h // s)
        for bc in range(w // s)
    }


def _size(inp, out):
    n = len(out) // 2
    s = int(round((len(inp) * len(inp[0]) / n) ** 0.5))
    return n, s


def _order_rev_rowmajor(inp, s):
    h, w = len(inp) // s, len(inp[0]) // s
    return [(r, c) for r in range(h - 1, -1, -1) for c in range(w - 1, -1, -1)]


def _build(blocks, order, n, s, cell_of=None, depth_of=None):
    """Nested rings: ring d of each quadrant takes a cell of block order[d]."""
    size = 2 * n
    if cell_of is None:
        cell_of = lambda qr, qc: (qr, qc)
    if depth_of is None:
        depth_of = lambda r, c: min(r, c, size - 1 - r, size - 1 - c)
    g = []
    for r in range(size):
        row = []
        for c in range(size):
            d = depth_of(r, c)
            qr, qc = cell_of(int(r >= n), int(c >= n))
            row.append(blocks[order[d]][qr][qc])
        g.append(row)
    return g


def _ref(inp, out):
    n, s = _size(inp, out)
    return n, s, _blocks(inp, s), _order_rev_rowmajor(inp, s)


def forward_order(inp, out):
    n, s, b, o = _ref(inp, out)
    return _build(b, o[::-1], n, s)


def column_major_order(inp, out):
    n, s, b, o = _ref(inp, out)
    h, w = len(inp) // s, len(inp[0]) // s
    o2 = [(r, c) for c in range(w - 1, -1, -1) for r in range(h - 1, -1, -1)]
    return _build(b, o2, n, s)


def snake_order(inp, out):
    n, s, b, o = _ref(inp, out)
    h, w = len(inp) // s, len(inp[0]) // s
    o2 = []
    for i, r in enumerate(range(h - 1, -1, -1)):
        cols = range(w - 1, -1, -1) if i % 2 == 0 else range(w)
        o2 += [(r, c) for c in cols]
    return _build(b, o2, n, s)


def swap_quadrant_diagonal(inp, out):
    n, s, b, o = _ref(inp, out)
    return _build(b, o, n, s, cell_of=lambda qr, qc: (qc, qr))


def mirror_quadrants_horizontally(inp, out):
    n, s, b, o = _ref(inp, out)
    return _build(b, o, n, s, cell_of=lambda qr, qc: (qr, 1 - qc))


def outer_two_blocks_only(inp, out):
    n, s, b, o = _ref(inp, out)
    o2 = [o[min(d, 1)] for d in range(n)]
    return _build(b, o2, n, s)


def rotated_order(inp, out):
    n, s, b, o = _ref(inp, out)
    return _build(b, o[1:] + o[:1], n, s)


def swap_outer_pair(inp, out):
    n, s, b, o = _ref(inp, out)
    o2 = [o[1], o[0]] + o[2:]
    return _build(b, o2, n, s)


def cell_blocks(inp, out):
    n, s, b, o = _ref(inp, out)
    cells = _blocks(inp, 1)
    order = _order_rev_rowmajor(inp, 1)
    m = len(order)
    size = 2 * m
    g = [[0] * size for _ in range(size)]
    for r in range(size):
        for c in range(size):
            d = min(r, c, size - 1 - r, size - 1 - c)
            g[r][c] = cells[order[d]][0][0]
    return g


def top_left_quadrant_only(inp, out):
    n = len(out) // 2
    return [row[:n] for row in out[:n]]


def quadrant_corner_rings(inp, out):
    n, s, b, o = _ref(inp, out)
    return _build(b, o, n, s, depth_of=lambda r, c: max(r % n, c % n))


def transposed_input(inp, out):
    n, s, b, o = _ref(inp, out)
    t = [list(r) for r in zip(*inp)]
    return _build(_blocks(t, s), _order_rev_rowmajor(t, s), n, s)


ALTERNATIVES = [
    ("blocks nest in forward row-major order (top-left block outermost)", forward_order),
    ("blocks nest in reverse column-major order instead of reverse row-major", column_major_order),
    ("blocks nest in a boustrophedon (snake) order", snake_order),
    ("quadrants take the block's cells transposed (top-right and bottom-left swapped)", swap_quadrant_diagonal),
    ("quadrants take the block's cells mirrored left-right", mirror_quadrants_horizontally),
    ("only the two outermost blocks are used; deeper rings repeat the second block", outer_two_blocks_only),
    ("nesting order shifted by one: outermost block placed at the centre", rotated_order),
    ("the two outermost blocks are swapped", swap_outer_pair),
    ("every single cell is a block, giving one ring per cell", cell_blocks),
    ("only the top-left quadrant of the output is produced", top_left_quadrant_only),
    ("rings are L-shaped around each quadrant's top-left corner instead of square rings", quadrant_corner_rings),
    ("the input is read transposed before blocking", transposed_input),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/8fff9e47.json").read_text())
    pairs = task["train"]
    n, s, b, o = _ref(pairs[0]["input"], pairs[0]["output"])
    for p in pairs:
        n, s, b, o = _ref(p["input"], p["output"])
        assert _build(b, o, n, s) == p["output"], "reference build mismatch"
    print("pairs:", len(pairs), "readings:", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
