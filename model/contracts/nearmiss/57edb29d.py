"""Near-miss readings for ARC task 57edb29d.

Rule: the input holds rectangular panels on a background. Marked panels carry
small marks (a second color) at fixed margins from the panel edges. The one
unmarked panel is the target: the output is that panel, filled with its color,
with the mark design drawn at the same edge margins and in the mark color.
"""
from collections import Counter


def _bg(inp):
    return inp[0][0]


def _panels(inp):
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != bg and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            res.append((min(ys), max(ys), min(xs), max(xs)))
    res.sort()
    return res


def _crop(g, p):
    r0, r1, c0, c1 = p
    return [row[c0:c1 + 1] for row in g[r0:r1 + 1]]


def _colors(g, p):
    return Counter(v for row in _crop(g, p) for v in row)


def _marked(inp):
    return [p for p in _panels(inp) if len(_colors(inp, p)) > 1]


def _field_mark(out):
    cnt = Counter(v for row in out for v in row)
    field = cnt.most_common(1)[0][0]
    marks = [c for c in cnt if c != field]
    return field, (marks[0] if marks else None)


def _replace(g, mapping):
    return [[mapping.get(v, v) for v in row] for row in g]


def field_only(inp, out):
    f, m = _field_mark(out)
    return _replace(out, {m: f})


def wrong_field_color(inp, out):
    f, m = _field_mark(out)
    mk = _marked(inp)
    if not mk:
        return None
    other = _colors(inp, mk[0]).most_common(1)[0][0]
    return _replace(out, {f: other})


def bg_colored_marks(inp, out):
    f, m = _field_mark(out)
    return _replace(out, {m: _bg(inp)})


def swap_roles(inp, out):
    f, m = _field_mark(out)
    return _replace(out, {f: m, m: f})


def top_half_only(inp, out):
    f, m = _field_mark(out)
    h = len(out)
    return [[v if r < h / 2 else f for v in row]
            for r, row in enumerate(out)]


def left_half_only(inp, out):
    f, m = _field_mark(out)
    w = len(out[0])
    return [[v if c < w / 2 else f for c, v in enumerate(row)] for row in out]


def shift_down(inp, out):
    f, m = _field_mark(out)
    h, w = len(out), len(out[0])
    g = [[f] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            if out[r][c] == m and r + 1 < h:
                g[r + 1][c] = m
    return g


def shift_right(inp, out):
    f, m = _field_mark(out)
    h, w = len(out), len(out[0])
    g = [[f] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            if out[r][c] == m and c + 1 < w:
                g[r][c + 1] = m
    return g


def padded_with_border(inp, out):
    b = _bg(inp)
    w = len(out[0])
    return [[b] * (w + 2)] + [[b] + row + [b] for row in out] + [[b] * (w + 2)]


def crop_marked_panel(inp, out):
    mk = _marked(inp)
    if not mk:
        return None
    p = max(mk, key=lambda q: (q[1] - q[0] + 1) * (q[3] - q[2] + 1))
    return _crop(inp, p)


def transposed(inp, out):
    return [list(col) for col in zip(*out)]


def absolute_offsets(inp, out):
    """Copy the first marked panel's marks at the same offsets from the target's top-left."""
    f, m = _field_mark(out)
    mk = _marked(inp)
    if not mk:
        return None
    p = mk[0]
    cnt = _colors(inp, p)
    pf = cnt.most_common(1)[0][0]
    h, w = len(out), len(out[0])
    g = [[f] * w for _ in range(h)]
    for r in range(p[0], p[1] + 1):
        for c in range(p[2], p[3] + 1):
            if inp[r][c] != pf and r - p[0] < h and c - p[2] < w:
                g[r - p[0]][c - p[2]] = m
    return g


ALTERNATIVES = [
    ("fill the unmarked panel with its color and draw no design", field_only),
    ("draw the design on the field color of a marked panel instead of the unmarked panel's color", wrong_field_color),
    ("draw the design in the background color instead of the mark color", bg_colored_marks),
    ("swap the field color and the mark color", swap_roles),
    ("draw only the marks in the top half (apply the margin rule to one vertical side)", top_half_only),
    ("draw only the marks in the left half (apply the margin rule to one horizontal side)", left_half_only),
    ("place every mark one row too low", shift_down),
    ("place every mark one column too far right", shift_right),
    ("crop the target panel with a one-cell background border around it", padded_with_border),
    ("output the largest marked panel as it is, instead of the unmarked one", crop_marked_panel),
    ("output the design transposed (rows and columns exchanged)", transposed),
    ("copy a marked panel's marks at the same offsets from the top-left corner, not at the same edge margins", absolute_offsets),
]


if __name__ == "__main__":
    import json
    from pathlib import Path

    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/57edb29d.json").read_text())
    pairs = task["train"]

    def valid(g, out):
        if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
            return False
        if len({len(r) for r in g}) != 1 or not g[0]:
            return False
        if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
            return False
        return g != out

    counts = []
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        counts.append(n)
        print(f"{n}/{len(pairs)}  {desc}")
    print(len(ALTERNATIVES), "readings", len(pairs), "pairs", counts)
