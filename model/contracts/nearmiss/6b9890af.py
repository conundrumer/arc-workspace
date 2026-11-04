from pathlib import Path
import json, sys


def _parts(inp, out):
    fc = out[0][0]
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == fc]
    r0 = min(r for r, c in cells); r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells); c1 = max(c for r, c in cells)
    obj = [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row)
           if v not in (0, fc)]
    orr0 = min(r for r, c, v in obj); orr1 = max(r for r, c, v in obj)
    oc0 = min(c for r, c, v in obj); oc1 = max(c for r, c, v in obj)
    pat = [[inp[r][c] for c in range(oc0, oc1 + 1)] for r in range(orr0, orr1 + 1)]
    ocol = obj[0][2]
    return fc, (r0, c0, r1, c1), pat, ocol


def _hole_size(box):
    r0, c0, r1, c1 = box
    return r1 - r0 - 1, c1 - c0 - 1


def _scale(pat, k, h, w):
    g = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            pr, pc = r // k, c // k
            if pr < len(pat) and pc < len(pat[0]):
                g[r][c] = pat[pr][pc]
    return g


def _frame(fc, hole, margin=0, color=None):
    h, w = len(hole), len(hole[0])
    col = fc if color is None else color
    g = [[col] * (w + 2) for _ in range(h + 2)]
    for r in range(h):
        for c in range(w):
            g[r + 1][c + 1] = hole[r][c]
    return g


def _true_k(pat, box):
    h, w = _hole_size(box)
    return h // len(pat)


def _flip_h(p):
    return [row[::-1] for row in p]


def _transpose(p):
    return [list(r) for r in zip(*p)]


def _rot(p):
    return [list(r) for r in zip(*p[::-1])]


def a_scale_plus1(inp, out):
    fc, box, pat, oc = _parts(inp, out)
    h, w = _hole_size(box)
    k = _true_k(pat, box) + 1
    return _frame(fc, _scale(pat, k, h, w))


def a_unscaled(inp, out):
    fc, box, pat, oc = _parts(inp, out)
    h, w = _hole_size(box)
    return _frame(fc, _scale(pat, 1, h, w))


def a_hole_only(inp, out):
    fc, box, pat, oc = _parts(inp, out)
    return [row[1:-1] for row in out[1:-1]]


def a_margin_crop(inp, out):
    fc, (r0, c0, r1, c1), pat, oc = _parts(inp, out)
    g = []
    for r in range(r0 - 1, r1 + 2):
        row = []
        for c in range(c0 - 1, c1 + 2):
            if r0 <= r <= r1 and c0 <= c <= c1:
                row.append(out[r - r0][c - c0])
            else:
                row.append(0)
        g.append(row)
    return g


def a_flip(inp, out):
    fc, box, pat, oc = _parts(inp, out)
    h, w = _hole_size(box)
    return _frame(fc, _scale(_flip_h(pat), _true_k(pat, box), h, w))


def a_transpose(inp, out):
    fc, box, pat, oc = _parts(inp, out)
    h, w = _hole_size(box)
    return _frame(fc, _scale(_transpose(pat), _true_k(pat, box), h, w))


def a_rotate(inp, out):
    fc, box, pat, oc = _parts(inp, out)
    h, w = _hole_size(box)
    return _frame(fc, _scale(_rot(pat), _true_k(pat, box), h, w))


def a_invert(inp, out):
    fc, box, pat, oc = _parts(inp, out)
    h, w = _hole_size(box)
    inv = [[0 if v else oc for v in row] for row in pat]
    return _frame(fc, _scale(inv, _true_k(pat, box), h, w))


def a_fill_solid(inp, out):
    fc, box, pat, oc = _parts(inp, out)
    h, w = _hole_size(box)
    return _frame(fc, [[oc] * w for _ in range(h)])


def a_tile(inp, out):
    fc, box, pat, oc = _parts(inp, out)
    h, w = _hole_size(box)
    return _frame(fc, [[pat[r % len(pat)][c % len(pat[0])] for c in range(w)]
                       for r in range(h)])


def a_frame_object_color(inp, out):
    fc, box, pat, oc = _parts(inp, out)
    h, w = _hole_size(box)
    return _frame(fc, _scale(pat, _true_k(pat, box), h, w), color=oc)


def a_input_crop(inp, out):
    fc, (r0, c0, r1, c1), pat, oc = _parts(inp, out)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def a_object_crop(inp, out):
    fc, box, pat, oc = _parts(inp, out)
    return [list(r) for r in pat]


def a_no_frame_cols(inp, out):
    # frame edge drawn in background color
    fc, box, pat, oc = _parts(inp, out)
    h, w = _hole_size(box)
    return _frame(fc, _scale(pat, _true_k(pat, box), h, w), color=0)


def _wrap(f):
    def g(inp, out):
        try:
            return f(inp, out)
        except Exception:
            return None
    return g


ALTERNATIVES = [
    ("pattern scaled one factor too large, clipped to the hole", a_scale_plus1),
    ("pattern pasted unscaled in the hole's top-left corner", a_unscaled),
    ("output is only the hole, frame border cropped away", a_hole_only),
    ("crop of the frame has a one-cell margin of background", a_margin_crop),
    ("pattern mirrored left-right before scaling", a_flip),
    ("pattern transposed before scaling", a_transpose),
    ("pattern rotated 90 degrees before scaling", a_rotate),
    ("pattern colors inverted: object cells empty, gaps filled", a_invert),
    ("whole hole filled with the object color", a_fill_solid),
    ("pattern tiled at original size across the hole instead of scaled", a_tile),
    ("frame border drawn in the object color", a_frame_object_color),
    ("input cropped to the frame, object not drawn", a_input_crop),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/6b9890af.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, e)
                g = None
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
