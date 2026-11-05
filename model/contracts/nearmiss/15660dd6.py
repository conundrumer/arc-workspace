import json
from pathlib import Path


def parse(inp):
    h, w = len(inp), len(inp[0])
    bg = inp[0][0]
    rows = [r for r in range(h) if any(c != bg for c in inp[r])]
    bands = []
    for r in rows:
        if bands and bands[-1][1] == r:
            bands[-1][1] = r + 1
        else:
            bands.append([r, r + 1])
    labels = [inp[b[0]][0] for b in bands]
    cols = []
    r0 = bands[0][0]
    for c in range(1, w):
        if inp[r0][c] != bg:
            if cols and cols[-1][1] == c:
                cols[-1][1] = c + 1
            else:
                cols.append([c, c + 1])
    # interior[band][col] = grid of the panel interior
    interior = [[[row[c0 + 1:c1 - 1] for row in inp[r0b + 1:r1b - 1]] for c0, c1 in cols]
                for r0b, r1b in bands]
    return bg, labels, interior


def single(g):
    return len({c for row in g for c in row}) == 1


def info(inp):
    """Per column: donor band index, fill color, stencil grid, other band indices."""
    bg, labels, interior = parse(inp)
    nb, nc = len(interior), len(interior[0])
    cols = []
    for j in range(nc):
        donor = [i for i in range(nb) if single(interior[i][j])][0]
        others = [i for i in range(nb) if i != donor]
        cols.append(dict(donor=donor, fill=interior[donor][j][0][0],
                         stencil=interior[others[0]][j], others=others))
    return bg, labels, cols


def build(bg, panels):
    """panels: list of (ring color, interior grid). Panels are laid side by side, separated by bg."""
    k = len(panels[0][1])
    out = [[] for _ in range(k + 2)]
    for n, (ring, g) in enumerate(panels):
        if n:
            for r in out:
                r.append(bg)
        out[0] += [ring] * (k + 2)
        out[-1] += [ring] * (k + 2)
        for i in range(k):
            out[i + 1] += [ring] + list(g[i]) + [ring]
    return out


def render(inp, ring=None, interior=None, bg_override=None):
    bg, labels, cols = info(inp)
    panels = []
    for j, c in enumerate(cols):
        r = labels[c['donor']]
        g = [[c['fill'] if v != bg else bg for v in row] for row in c['stencil']]
        if ring:
            r = ring(j, c, labels)
        if interior:
            g = interior(j, c, cols, bg)
        panels.append((r, g))
    return build(bg, panels)


def alt_ring_nondonor(inp, out):
    return render(inp, ring=lambda j, c, L: L[c['others'][0]])


def alt_ring_fill(inp, out):
    return render(inp, ring=lambda j, c, L: c['fill'])


def alt_inverted(inp, out):
    return render(inp, interior=lambda j, c, cols, bg:
                  [[bg if v != bg else c['fill'] for v in row] for row in c['stencil']])


def alt_stencil_color(inp, out):
    return render(inp, interior=lambda j, c, cols, bg:
                  [list(row) for row in c['stencil']])


def alt_solid(inp, out):
    return render(inp, interior=lambda j, c, cols, bg:
                  [[c['fill']] * len(c['stencil'][0]) for _ in c['stencil']])


def alt_transposed(inp, out):
    return [list(r) for r in zip(*out)]


def alt_reversed_panels(inp, out):
    h = len(out)
    bg = info(inp)[0]
    n = (len(out[0]) + 1) // (h + 1)
    blocks = [[row[i * (h + 1):i * (h + 1) + h] for row in out] for i in range(n)]
    blocks.reverse()
    res = [[] for _ in range(h)]
    for i, b in enumerate(blocks):
        for r in range(h):
            if i:
                res[r].append(bg)
            res[r] += b[r]
    return res


def alt_padded(inp, out):
    bg = info(inp)[0]
    w = len(out[0])
    return [[bg] * (w + 2)] + [[bg] + list(r) + [bg] for r in out] + [[bg] * (w + 2)]


def alt_no_ring(inp, out):
    bg = info(inp)[0]
    h = len(out)
    res = [list(r) for r in out]
    for r in range(h):
        for c in range(len(out[0])):
            pc = c % (h + 1)
            if pc < h and (r in (0, h - 1) or pc in (0, h - 1)):
                res[r][c] = bg
    return res


def alt_first_column(inp, out):
    h = len(out)
    return [list(r[:h]) for r in out]


def alt_neighbor_stencil(inp, out):
    return render(inp, interior=lambda j, c, cols, bg:
                  [[c['fill'] if v != bg else bg for v in row]
                   for row in cols[(j + 1) % len(cols)]['stencil']])


def alt_swapped(inp, out):
    bg, labels, cols = info(inp)
    panels = []
    for c in cols:
        lab = labels[c['donor']]
        g = [[lab if v != bg else bg for v in row] for row in c['stencil']]
        panels.append((c['fill'], g))
    return build(bg, panels)


ALTERNATIVES = [
    ("ring takes the band label of a non-donor panel instead of the donor's band", alt_ring_nondonor),
    ("ring takes the donor's fill color instead of its band label", alt_ring_fill),
    ("stencil inverted: fill goes on the background cells of the shape", alt_inverted),
    ("shape keeps its own color instead of the donor's color", alt_stencil_color),
    ("interior filled solid with the donor color, shape ignored", alt_solid),
    ("panels stacked vertically instead of side by side (transposed output)", alt_transposed),
    ("panel order reversed left to right", alt_reversed_panels),
    ("output padded with an outer background border", alt_padded),
    ("ring omitted: ring cells left as background", alt_no_ring),
    ("only the first column is output", alt_first_column),
    ("each column takes the shape of the next column", alt_neighbor_stencil),
    ("label color and donor color swap roles (ring = donor color, fill = label)", alt_swapped),
]


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/15660dd6.json'))
    pairs = task['train']

    def valid(g, out):
        if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
            return False
        if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
            return False
        if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
            return False
        return g != out

    print('pairs', len(pairs), 'readings', len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(n, desc)
