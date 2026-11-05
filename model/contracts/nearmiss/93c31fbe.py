"""Near-miss readings for ARC task 93c31fbe.

Rule: a box is four 3-cell corner brackets. Content (the rarest color) inside a
box is mirrored across the box centre, along the box's longer axis, and the
original stays. Content outside every box is erased.
"""
import json
from collections import Counter
from pathlib import Path


def _colors(inp):
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    content = min(cnt, key=lambda k: cnt[k])
    marks = [k for k in cnt if k not in (bg, content)]
    return bg, content, marks[0]


def _boxes(inp):
    """Return list of (r0, c0, r1, c1) box extents, corners included."""
    bg, content, mk = _colors(inp)
    h, w = len(inp), len(inp[0])
    seen, comps = set(), []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == mk and (r, c) not in seen:
                st, comp = [(r, c)], []
                seen.add((r, c))
                while st:
                    y, x = st.pop()
                    comp.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            n = (y + dy, x + dx)
                            if (0 <= n[0] < h and 0 <= n[1] < w and n not in seen
                                    and inp[n[0]][n[1]] == mk):
                                seen.add(n)
                                st.append(n)
                comps.append(comp)
    corners = {"TL": [], "TR": [], "BL": [], "BR": []}
    for comp in comps:
        r0 = min(y for y, _ in comp); r1 = max(y for y, _ in comp)
        c0 = min(x for _, x in comp); c1 = max(x for _, x in comp)
        s = set(comp)
        if (r0, c0) in s and (r1, c1) not in s:
            corners["TL"].append((r0, c0))
        elif (r0, c1) in s and (r1, c0) not in s:
            corners["TR"].append((r0, c1))
        elif (r1, c0) in s and (r0, c1) not in s:
            corners["BL"].append((r1, c0))
        elif (r1, c1) in s and (r0, c0) not in s:
            corners["BR"].append((r1, c1))
    boxes = []
    for (r0, c0) in corners["TL"]:
        trs = sorted(c for (r, c) in corners["TR"] if r == r0 and c > c0)
        bls = sorted(r for (r, c) in corners["BL"] if c == c0 and r > r0)
        for c1 in trs:
            for r1 in bls:
                if (r1, c1) in corners["BR"]:
                    boxes.append((r0, c0, r1, c1))
                    break
            else:
                continue
            break
    return boxes


def _content_cells(inp, box):
    bg, content, mk = _colors(inp)
    r0, c0, r1, c1 = box
    return [(r, c) for r in range(r0 + 1, r1) for c in range(c0 + 1, c1)
            if inp[r][c] == content]


def _blank(inp, keep_stray=False):
    """Marks only; all content removed (or kept where it lies outside boxes)."""
    bg, content, mk = _colors(inp)
    g = [[(v if v == mk else bg) for v in row] for row in inp]
    if keep_stray:
        for r, row in enumerate(inp):
            for c, v in enumerate(row):
                if v == content:
                    g[r][c] = v
    return g


def _long_axis(box):
    r0, c0, r1, c1 = box
    return "h" if (c1 - c0) >= (r1 - r0) else "v"


def _render(inp, per_box, keep_stray=False, keep_orig=True, paint=None,
            erase_box=False):
    """per_box(box, cells) -> list of image cells (r, c) to paint."""
    bg, content, mk = _colors(inp)
    g = _blank(inp, keep_stray)
    if keep_stray:
        # stray content stays; content inside boxes is handled below
        for box in _boxes(inp):
            for r, c in _content_cells(inp, box):
                g[r][c] = bg
    for box in _boxes(inp):
        cells = _content_cells(inp, box)
        if keep_orig:
            for r, c in cells:
                g[r][c] = content
        for r, c in _inb(g, per_box(box, cells)):
            g[r][c] = content if paint is None else paint(mk, content)
    if erase_box:
        for r0, c0, r1, c1 in _boxes(inp):
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    if g[r][c] == mk:
                        g[r][c] = bg
    return g


def _mirror_h(box, cells, off=0):
    r0, c0, r1, c1 = box
    return [(r, c0 + c1 - c + off) for r, c in cells]


def _mirror_v(box, cells, off=0):
    r0, c0, r1, c1 = box
    return [(r0 + r1 - r + off, c) for r, c in cells]


def _inb(g, cells):
    return [(r, c) for r, c in cells if 0 <= r < len(g) and 0 <= c < len(g[0])]


def alt_short_axis(inp, out):
    def f(box, cells):
        return _mirror_v(box, cells) if _long_axis(box) == "h" else _mirror_h(box, cells)
    return _render(inp, f)


def alt_both_axes(inp, out):
    def f(box, cells):
        return _mirror_h(box, cells) + _mirror_v(box, cells) + \
            _mirror_v(box, _mirror_h(box, cells))
    return _render(inp, f)


def alt_replace(inp, out):
    def f(box, cells):
        return _mirror_h(box, cells) if _long_axis(box) == "h" else _mirror_v(box, cells)
    return _render(inp, f, keep_orig=False)


def alt_keep_stray(inp, out):
    def f(box, cells):
        return _mirror_h(box, cells) if _long_axis(box) == "h" else _mirror_v(box, cells)
    return _render(inp, f, keep_stray=True)


def alt_off_by_one(inp, out):
    def f(box, cells):
        return _mirror_h(box, cells, 1) if _long_axis(box) == "h" else _mirror_v(box, cells, 1)
    return _render(inp, f)


def alt_translate(inp, out):
    """Copy shifted by half the box length, without flipping."""
    def f(box, cells):
        r0, c0, r1, c1 = box
        if _long_axis(box) == "h":
            half = (c1 - c0 + 1) // 2
            return [(r, c + half) for r, c in cells]
        half = (r1 - r0 + 1) // 2
        return [(r + half, c) for r, c in cells]
    return _render(inp, f)


def alt_box_color_image(inp, out):
    def f(box, cells):
        return _mirror_h(box, cells) if _long_axis(box) == "h" else _mirror_v(box, cells)
    return _render(inp, f, paint=lambda mk, content: mk)


def alt_point_reflection(inp, out):
    def f(box, cells):
        r0, c0, r1, c1 = box
        return [(r0 + r1 - r, c0 + c1 - c) for r, c in cells]
    return _render(inp, f)


def alt_content_axis(inp, out):
    """Axis chosen by the shape of the content, not of the box."""
    def f(box, cells):
        if not cells:
            return []
        h = max(r for r, _ in cells) - min(r for r, _ in cells)
        w = max(c for _, c in cells) - min(c for _, c in cells)
        return _mirror_h(box, cells) if w >= h else _mirror_v(box, cells)
    return _render(inp, f)


def alt_largest_box_only(inp, out):
    boxes = _boxes(inp)
    big = max(boxes, key=lambda b: (b[2] - b[0] + 1) * (b[3] - b[1] + 1))

    def f(box, cells):
        if box != big:
            return []
        return _mirror_h(box, cells) if _long_axis(box) == "h" else _mirror_v(box, cells)
    return _render(inp, f)


def alt_box_erased(inp, out):
    def f(box, cells):
        return _mirror_h(box, cells) if _long_axis(box) == "h" else _mirror_v(box, cells)
    return _render(inp, f, erase_box=True)


def alt_grid_mirror(inp, out):
    """Mirror about the grid centre line on the box's long axis."""
    h, w = len(inp), len(inp[0])

    def f(box, cells):
        if _long_axis(box) == "h":
            return _inb(inp, [(r, w - 1 - c) for r, c in cells])
        return _inb(inp, [(h - 1 - r, c) for r, c in cells])
    return _render(inp, f)


def alt_input_unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("mirror across the box's shorter axis instead of the longer", alt_short_axis),
    ("mirror across both axes, giving four copies", alt_both_axes),
    ("replace the content with its mirror image, dropping the original", alt_replace),
    ("keep content that lies outside the boxes", alt_keep_stray),
    ("mirror about a line one cell off the box centre", alt_off_by_one),
    ("copy the content shifted by half the box length without flipping", alt_translate),
    ("paint the mirror image in the box color", alt_box_color_image),
    ("rotate the content 180 degrees about the box centre", alt_point_reflection),
    ("pick the mirror axis from the content's shape, not the box's", alt_content_axis),
    ("mirror only the content of the largest box", alt_largest_box_only),
    ("erase the box corners from the output", alt_box_erased),
    ("mirror about the grid centre instead of the box centre", alt_grid_mirror),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
               for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/93c31fbe.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
