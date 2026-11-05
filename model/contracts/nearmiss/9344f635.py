import json
from pathlib import Path


def bg_of(inp):
    flat = [c for r in inp for c in r]
    return max(set(flat), key=flat.count)


def segments(inp):
    """Each segment: (first cell in reading order, color, 'H' or 'V', cells)."""
    bg = bg_of(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    segs = []
    for r in range(h):
        for c in range(w):
            col = inp[r][c]
            if col == bg or (r, c) in seen:
                continue
            comp, stack = [], [(r, c)]
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] == col:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comp.sort()
            orient = 'H' if comp[0][0] == comp[-1][0] else 'V'
            segs.append((comp[0], col, orient, comp))
    return segs


def render(inp, order_key=None, keep=None, swap=False, shift=0, thick=1,
           skip_intersection=False, half=False, trim=0, dedupe=False):
    """Paint one full line per segment. Later painted lines cover earlier ones.
    Default paint order: columns first, then rows (rows on top)."""
    bg = bg_of(inp)
    h, w = len(inp), len(inp[0])
    segs = segments(inp)
    if dedupe:
        seen, kept = set(), []
        for s in segs:
            if s[1] not in seen:
                seen.add(s[1])
                kept.append(s)
        segs = kept
    if order_key is None:
        order_key = lambda s: (0 if s[2] == 'V' else 1, s[0])
    segs = sorted(segs, key=order_key)
    g = [[bg] * w for _ in range(h)]
    count = [[0] * w for _ in range(h)]
    for first, col, orient, cells in segs:
        if keep is not None and orient not in keep:
            continue
        o = orient
        if swap:
            o = 'V' if orient == 'H' else 'H'
        if o == 'H':
            base = cells[0][0] if not swap else cells[0][0]
            idxs = [base + shift + t for t in range(thick)]
            start = (max(c[1] for c in cells) + 1) if half else 0
            span = [x for x in range(start, w)][trim:w - start - trim if True else w]
            span = [x for x in range(start, w)]
            if trim:
                span = span[trim:len(span) - trim]
            for i in idxs:
                if 0 <= i < h:
                    for x in span:
                        g[i][x] = col
                        count[i][x] += 1
        else:
            base = cells[0][1]
            idxs = [base + shift + t for t in range(thick)]
            start = (max(c[0] for c in cells) + 1) if half else 0
            span = [y for y in range(start, h)]
            if trim:
                span = span[trim:len(span) - trim]
            for j in idxs:
                if 0 <= j < w:
                    for y in span:
                        g[y][j] = col
                        count[y][j] += 1
    if skip_intersection:
        for y in range(h):
            for x in range(w):
                if count[y][x] > 1:
                    g[y][x] = bg
    return g


def f_cols_over(inp, out):
    return render(inp, order_key=lambda s: (0 if s[2] == 'H' else 1, s[0]))


def f_rows_only(inp, out):
    return render(inp, keep='H')


def f_cols_only(inp, out):
    return render(inp, keep='V')


def f_swapped_orientation(inp, out):
    return render(inp, swap=True)


def f_half_line(inp, out):
    return render(inp, half=True)


def f_shifted(inp, out):
    return render(inp, shift=1)


def f_intersection_bg(inp, out):
    return render(inp, skip_intersection=True)


def f_thick(inp, out):
    return render(inp, thick=2)


def f_dedupe_color(inp, out):
    return render(inp, dedupe=True)


def f_reading_order(inp, out):
    return render(inp, order_key=lambda s: (-s[0][0], -s[0][1]))


def f_trim_ends(inp, out):
    return render(inp, trim=1)


ALTERNATIVES = [
    ("columns drawn over rows at crossings instead of rows over columns", f_cols_over),
    ("only horizontal segments produce row lines; vertical segments ignored", f_rows_only),
    ("only vertical segments produce column lines; horizontal segments ignored", f_cols_only),
    ("orientation swapped: horizontal segments draw columns, vertical segments draw rows", f_swapped_orientation),
    ("a line runs only from the segment to the far edge, not across the whole grid", f_half_line),
    ("every line is placed one cell too far (one row down or one column right)", f_shifted),
    ("crossings of a row line and a column line are left as background", f_intersection_bg),
    ("lines are two cells thick", f_thick),
    ("only the first segment of each color draws a line", f_dedupe_color),
    ("no axis priority: segments paint bottom to top, so the topmost segment's line ends up on top at a crossing", f_reading_order),
    ("lines stop one cell short of the grid border at both ends", f_trim_ends),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == '__main__':
    path = Path(__file__).resolve().parents[3] / 'data/tasks/9344f635.json'
    pairs = json.loads(path.read_text())['train']
    # sanity: true rule reproduces output
    for p in pairs:
        assert render(p['input']) == p['output'], p['index']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
