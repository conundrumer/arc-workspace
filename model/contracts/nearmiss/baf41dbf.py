"""Near-miss rules for baf41dbf."""
import json
from collections import Counter
from pathlib import Path


def parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r if v != 0)
    fc = cnt.most_common(1)[0][0]
    mc = [c for c in cnt if c != fc][0]
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == fc]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    drows = [r for r in range(r0 + 1, r1)
             if all(inp[r][c] == fc for c in range(c0, c1 + 1))]
    dcols = [c for c in range(c0 + 1, c1)
             if all(inp[r][c] == fc for r in range(r0, r1 + 1))]
    marks = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == mc]
    return h, w, fc, mc, (r0, r1, c0, c1), drows, dcols, marks


def pulls(box, marks, gap=0, only=None, symmetric=False, h=None, w=None):
    """Return new box where sides move next to the farthest marker beyond."""
    r0, r1, c0, c1 = box
    n = [r0, r1, c0, c1]
    up = [r for r, c in marks if r < r0]
    dn = [r for r, c in marks if r > r1]
    lf = [c for r, c in marks if c < c0]
    rt = [c for r, c in marks if c > c1]
    if up and only in (None, "v", "first"):
        n[0] = min(up) + 1 + gap
    if dn and only in (None, "v", "first"):
        n[1] = max(dn) - 1 - gap
    if lf and only in (None, "h", "first"):
        n[2] = min(lf) + 1 + gap
    if rt and only in (None, "h", "first"):
        n[3] = max(rt) - 1 - gap
    return tuple(n)


def render(inp, box, drows, dcols, dividers="stretch", marks_on=True,
           frame_over_marks=True, old=None):
    h, w, fc, mc, ob, _, _, marks = parse(inp)
    g = [[0] * w for _ in range(h)]
    r0, r1, c0, c1 = box

    def frame():
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if r in (r0, r1) or c in (c0, c1):
                    g[r][c] = fc
        if dividers == "stretch":
            for r in drows:
                for c in range(c0, c1 + 1):
                    g[r][c] = fc
            for c in dcols:
                for r in range(r0, r1 + 1):
                    g[r][c] = fc
        elif dividers == "old":
            for r in drows:
                for c in range(ob[2], ob[3] + 1):
                    g[r][c] = fc
            for c in dcols:
                for r in range(ob[0], ob[1] + 1):
                    g[r][c] = fc

    def mk():
        if marks_on:
            for r, c in marks:
                g[r][c] = mc

    if frame_over_marks:
        mk()
        frame()
    else:
        frame()
        mk()
    return g


def true_box(inp):
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    return pulls(box, marks)


def alt_gap(inp, out):
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    return render(inp, pulls(box, marks, gap=1), dr, dc)


def alt_overlap(inp, out):
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    r0, r1, c0, c1 = pulls(box, marks)
    b = [r0, r1, c0, c1]
    for r, c in marks:
        if r < box[0]:
            b[0] = min(b[0], r)
        if r > box[1]:
            b[1] = max(b[1], r)
        if c < box[2]:
            b[2] = min(b[2], c)
        if c > box[3]:
            b[3] = max(b[3], c)
    b = tuple(b)
    return render(inp, b, dr, dc)


def alt_horizontal_only(inp, out):
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    return render(inp, pulls(box, marks, only="h"), dr, dc)


def alt_vertical_only(inp, out):
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    return render(inp, pulls(box, marks, only="v"), dr, dc)


def alt_first_marker(inp, out):
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    return render(inp, pulls(box, marks[:1]), dr, dc)


def alt_nearest_axis(inp, out):
    """Only the marker nearest to the frame pulls."""
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    r0, r1, c0, c1 = box

    def dist(m):
        r, c = m
        return max(r0 - r, r - r1, c0 - c, c - c1)
    m = min(marks, key=dist)
    return render(inp, pulls(box, [m]), dr, dc)


def alt_old_dividers(inp, out):
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    if not dr and not dc:
        return None
    return render(inp, pulls(box, marks), dr, dc, dividers="old")


def alt_no_dividers(inp, out):
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    if not dr and not dc:
        return None
    return render(inp, pulls(box, marks), dr, dc, dividers="none")


def alt_old_outline_kept(inp, out):
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    g = [row[:] for row in out]
    for r in range(h):
        for c in range(w):
            if inp[r][c] == fc:
                g[r][c] = fc
    return g


def alt_markers_erased(inp, out):
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    g = [row[:] for row in out]
    for r, c in marks:
        g[r][c] = 0
    return g


def alt_translate(inp, out):
    """The whole frame slides toward the markers without growing."""
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    nb = pulls(box, marks)
    dr_ = (nb[1] - box[1]) + (nb[0] - box[0])
    dc_ = (nb[3] - box[3]) + (nb[2] - box[2])
    r0, r1, c0, c1 = box
    sb = (r0 + dr_, r1 + dr_, c0 + dc_, c1 + dc_)
    if sb[0] < 0 or sb[2] < 0 or sb[1] >= h or sb[3] >= w:
        return None
    g = render(inp, sb, [r + dr_ for r in dr], [c + dc_ for c in dc],
               frame_over_marks=False)
    return g


def alt_symmetric(inp, out):
    """A pulled side moves, and the opposite side moves out by the same amount."""
    h, w, fc, mc, box, dr, dc, marks = parse(inp)
    nb = list(pulls(box, marks))
    r0, r1, c0, c1 = box
    d = [nb[0] - r0, nb[1] - r1, nb[2] - c0, nb[3] - c1]
    n = list(box)
    n[0] = r0 + d[0] if d[0] else r0 - d[1]
    n[1] = r1 + d[1] if d[1] else r1 - d[0]
    n[2] = c0 + d[2] if d[2] else c0 - d[3]
    n[3] = c1 + d[3] if d[3] else c1 - d[2]
    n[0] = max(n[0], 0)
    n[2] = max(n[2], 0)
    n[1] = min(n[1], h - 1)
    n[3] = min(n[3], w - 1)
    return render(inp, tuple(n), dr, dc)


ALTERNATIVES = [
    ("sides stop one extra cell short of the marker", alt_gap),
    ("sides move onto the marker cell and cover it", alt_overlap),
    ("only left and right sides move", alt_horizontal_only),
    ("only top and bottom sides move", alt_vertical_only),
    ("only the first marker in reading order pulls", alt_first_marker),
    ("only the marker nearest the frame pulls", alt_nearest_axis),
    ("dividers keep their old extent instead of spanning the new box", alt_old_dividers),
    ("dividers are dropped", alt_no_dividers),
    ("old outline cells are not erased", alt_old_outline_kept),
    ("markers are erased", alt_markers_erased),
    ("whole frame slides toward markers without growing", alt_translate),
    ("opposite side also moves out by the same amount", alt_symmetric),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/baf41dbf.json").read_text())
    pairs = task["train"]
    for p in pairs:
        assert render(p["input"], true_box(p["input"]), parse(p["input"])[5],
                      parse(p["input"])[6]) == p["output"], "base render mismatch"
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
