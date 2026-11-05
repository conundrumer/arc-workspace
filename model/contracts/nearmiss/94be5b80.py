"""Near-miss rules for ARC task 94be5b80.

Rule: a legend strip (a band of rows with one column of each color) lists the
colors of a vertical stack of identical shapes. The stack is extended with
more copies, in legend order, above and below, and the legend is erased.
"""
import json
from pathlib import Path


def parse(inp):
    h, w = len(inp), len(inp[0])
    rows = [r for r in range(h) if any(inp[r])]
    # first contiguous band of non-background rows is the legend
    end = rows[0]
    while end + 1 in rows:
        end += 1
    leg_rows = range(rows[0], end + 1)
    legend = [v for v in inp[rows[0]] if v]
    shape_cells = {}
    for r in range(h):
        if r in leg_rows:
            continue
        for c in range(w):
            if inp[r][c]:
                shape_cells.setdefault(inp[r][c], []).append((r, c))
    members = []
    for col, cells in shape_cells.items():
        r0 = min(r for r, _ in cells)
        r1 = max(r for r, _ in cells)
        c0 = min(c for _, c in cells)
        c1 = max(c for _, c in cells)
        members.append((r0, r1, c0, c1, col, cells))
    members.sort()
    r0, r1, c0, c1, col, cells = members[0]
    mask = {(r - r0, c - c0) for r, c in cells}
    return dict(h=h, w=w, leg_rows=leg_rows, legend=legend,
                top=r0, ht=r1 - r0 + 1, left=c0, mask=mask,
                start=legend.index(col), stack=[m[4] for m in members],
                leg_cells=[(r, c, inp[r][c]) for r in leg_rows
                           for c in range(w) if inp[r][c]])


def render(p, colors=None, gap=0, dx=0, drop_last=0, flip=False,
           only_extras_above=False, extras_color=None):
    colors = colors if colors is not None else p['legend']
    g = [[0] * p['w'] for _ in range(p['h'])]
    ht = p['ht']
    s = p['start']
    nstack = len(p['stack'])
    for i, col in enumerate(colors):
        is_extra = not (s <= i < s + nstack)
        if only_extras_above and i > s:
            if is_extra:
                continue
        top = p['top'] + (i - s) * (ht + gap)
        if is_extra and extras_color is not None:
            col = extras_color(i, s, nstack, p)
        for (dr, dc) in p['mask']:
            if flip and is_extra:
                dr = ht - 1 - dr
            if drop_last and is_extra and dr >= ht - drop_last:
                continue
            r, c = top + dr, p['left'] + dc + (dx if is_extra else 0)
            if 0 <= r < p['h'] and 0 <= c < p['w']:
                g[r][c] = col
    return g


def legend_kept(inp, out):
    g = [row[:] for row in out]
    p = parse(inp)
    for r, c, v in p['leg_cells']:
        g[r][c] = v
    return g


def legend_erased_only(inp, out):
    p = parse(inp)
    g = [row[:] for row in inp]
    for r in p['leg_rows']:
        g[r] = [0] * p['w']
    return g


def legend_reversed(inp, out):
    p = parse(inp)
    return render(p, colors=p['legend'][::-1])


def extras_all_below(inp, out):
    p = parse(inp)
    g = [[0] * p['w'] for _ in range(p['h'])]
    seq = p['legend'][p['start']:] + p['legend'][:p['start']]
    for k, col in enumerate(seq):
        top = p['top'] + k * p['ht']
        for dr, dc in p['mask']:
            r, c = top + dr, p['left'] + dc
            if 0 <= r < p['h'] and 0 <= c < p['w']:
                g[r][c] = col
    return g


def extras_take_neighbor_color(inp, out):
    p = parse(inp)

    def f(i, s, n, p):
        return p['legend'][s] if i < s else p['legend'][s + n - 1]
    return render(p, extras_color=f)


def only_above_extended(inp, out):
    p = parse(inp)
    return render(p, only_extras_above=True)


def gap_between_copies(inp, out):
    return render(parse(inp), gap=1)


def extras_shifted_right(inp, out):
    return render(parse(inp), dx=1)


def extras_missing_last_row(inp, out):
    return render(parse(inp), drop_last=1)


def extras_flipped(inp, out):
    return render(parse(inp), flip=True)


def cropped_to_content(inp, out):
    rows = [r for r in range(len(out)) if any(out[r])]
    cols = [c for c in range(len(out[0])) if any(out[r][c] for r in range(len(out)))]
    return [row[cols[0]:cols[-1] + 1] for row in out[rows[0]:rows[-1] + 1]]


def colors_shifted_one(inp, out):
    p = parse(inp)
    L = p['legend']
    return render(p, colors=L[1:] + L[:1])


ALTERNATIVES = [
    ("legend strip left in place instead of erased", legend_kept),
    ("legend erased but stack not extended", legend_erased_only),
    ("legend read right to left when coloring copies", legend_reversed),
    ("all extra copies appended below the stack", extras_all_below),
    ("extra copies reuse the adjacent stack color, not the legend color", extras_take_neighbor_color),
    ("only copies above the stack are added, those below are dropped", only_above_extended),
    ("copies spaced with a one-row gap instead of touching", gap_between_copies),
    ("extra copies offset one column to the right", extras_shifted_right),
    ("extra copies one row short", extras_missing_last_row),
    ("extra copies flipped vertically", extras_flipped),
    ("output cropped to the bounding box of the stack", cropped_to_content),
    ("legend colors assigned shifted by one position", colors_shifted_one),
]


def valid(g):
    return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/94be5b80.json'))
    pairs = task['train']
    # sanity: the parser reproduces the true output
    for pr in pairs:
        assert render(parse(pr['input'])) == pr['output'], "parser does not reproduce output"
    print(f"{len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in pairs:
            g = fn(pr['input'], pr['output'])
            if g is not None and valid(g) and g != pr['output']:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
