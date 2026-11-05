"""Near-miss rules for ARC task 538b439f.

True rule: the most common color is the field. One full row or column of
another color is a divider. Each solid rectangle (a different color, at least
2x2) is mirrored across the divider, and the cells between the rectangle and
its mirror image, in the rectangle's band, are painted with the divider color.
"""
import json
from collections import Counter
from pathlib import Path


def transpose(g):
    return [list(r) for r in zip(*g)]


def analyze(inp):
    """Return (field, axis, line, divcolor, rects) or None."""
    H, W = len(inp), len(inp[0])
    field = Counter(v for r in inp for v in r).most_common(1)[0][0]
    div = None
    for c in range(W):
        vals = {inp[r][c] for r in range(H)}
        if len(vals) == 1 and field not in vals:
            div = ("v", c, vals.pop())
    for r in range(H):
        vals = set(inp[r])
        if len(vals) == 1 and field not in vals:
            div = ("h", r, vals.pop())
    if div is None:
        return None
    axis, line, dcol = div
    seen = set()
    rects = []
    for r in range(H):
        for c in range(W):
            col = inp[r][c]
            if (r, c) in seen or col in (field, dcol):
                continue
            stack = [(r, c)]
            seen.add((r, c))
            comp = []
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if (0 <= ny < H and 0 <= nx < W and (ny, nx) not in seen
                            and inp[ny][nx] == col):
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            r0 = min(p[0] for p in comp)
            r1 = max(p[0] for p in comp)
            c0 = min(p[1] for p in comp)
            c1 = max(p[1] for p in comp)
            h, w = r1 - r0 + 1, c1 - c0 + 1
            if h >= 2 and w >= 2 and h * w == len(comp):
                rects.append((r0, r1, c0, c1, col))
    if not rects:
        return None
    return field, axis, line, dcol, rects


def render(inp, flip_axis=False, shift=0, image=True, fill="divider",
           margin=0, keep_noise=False, erase=False, largest_only=False,
           stop_at_divider=False, full_band=False):
    st = analyze(inp)
    if st is None:
        return None
    field, axis, line, dcol, rects = st
    # Work in a frame where the reflection runs along columns.
    use_t = (axis == "h") != flip_axis
    g = transpose(inp) if use_t else [list(r) for r in inp]
    orig = [list(r) for r in g]
    if axis == "h":
        rects = [(c0, c1, r0, r1, col) for (r0, r1, c0, c1, col) in rects]
    if use_t != (axis == "h"):
        # frame differs from the divider's own frame
        pass
    H, W = len(g), len(g[0])
    if flip_axis:
        S = W - 1
        L = (W - 1) / 2
    else:
        L = line
        S = 2 * line + shift
    if largest_only:
        rects = [max(rects, key=lambda t: (t[1] - t[0] + 1) * (t[3] - t[2] + 1))]
    for (r0, r1, c0, c1, col) in rects:
        a, b = S - c1, S - c0
        if c0 < a:
            lo, hi = c1 + 1, a - 1
        else:
            lo, hi = b + 1, c0 - 1
        lo += margin
        hi -= margin
        if stop_at_divider:
            if c0 < a:
                hi = min(hi, L)
            else:
                lo = max(lo, L)
        if full_band:
            cols = [x for x in range(W) if not (c0 <= x <= c1 or a <= x <= b)]
        else:
            cols = [x for x in range(lo, hi + 1) if 0 <= x < W]
        fc = {"divider": dcol, "field": field, "rect": col, "none": None}[fill]
        for y in range(r0, r1 + 1):
            for x in (cols if fc is not None else []):
                if keep_noise and orig[y][x] != field:
                    continue
                g[y][x] = fc
        if erase:
            for y in range(r0, r1 + 1):
                for x in range(c0, c1 + 1):
                    g[y][x] = field
        if image:
            for y in range(r0, r1 + 1):
                for x in range(a, b + 1):
                    if 0 <= x < W:
                        g[y][x] = col
    return transpose(g) if use_t else g


def image_only(inp, out):
    """Mirror the rectangles but never fill the cells between."""
    return render(inp, fill="none")


def span_without_image(inp, out):
    return render(inp, image=False)


def fill_stops_at_divider(inp, out):
    return render(inp, stop_at_divider=True)


def fill_with_field(inp, out):
    return render(inp, fill="field")


def fill_whole_band(inp, out):
    return render(inp, full_band=True)


def mirror_off_by_one(inp, out):
    return render(inp, shift=1)


def largest_rect_only(inp, out):
    return render(inp, largest_only=True)


def noise_kept(inp, out):
    return render(inp, keep_noise=True)


def wrong_axis(inp, out):
    return render(inp, flip_axis=True)


def fill_with_rect_color(inp, out):
    return render(inp, fill="rect")


def move_instead_of_copy(inp, out):
    return render(inp, erase=True)


def fill_shrunk(inp, out):
    return render(inp, margin=1)


ALTERNATIVES = [
    ("Rectangles are mirrored across the divider but the cells between are left unfilled", image_only),
    ("The band between is filled with the divider color but the mirrored rectangle is not drawn", span_without_image),
    ("The band is filled only from the rectangle up to the divider, not on the far side", fill_stops_at_divider),
    ("The band between is filled with the field color instead of the divider color", fill_with_field),
    ("The band is filled across the whole grid instead of only between rectangle and image", fill_whole_band),
    ("The mirror axis is taken one cell off, so each image sits one cell too far", mirror_off_by_one),
    ("Only the largest rectangle is mirrored and filled", largest_rect_only),
    ("Noise cells inside the band survive instead of being painted over", noise_kept),
    ("Rectangles are mirrored across the perpendicular axis through the grid center", wrong_axis),
    ("The band between is filled with the rectangle color instead of the divider color", fill_with_rect_color),
    ("Each rectangle is moved to its mirror position and its original is erased", move_instead_of_copy),
    ("The fill leaves one cell gap next to the rectangle and next to the image", fill_shrunk),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
               for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/538b439f.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
