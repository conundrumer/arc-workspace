import json
from collections import Counter
from pathlib import Path


def _parts(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    cols = [c for c in cnt if c != bg]
    occ = fig = None
    for c in cols:
        cells = [(r, k) for r in range(h) for k in range(w) if inp[r][k] == c]
        r0 = min(r for r, _ in cells); r1 = max(r for r, _ in cells)
        k0 = min(k for _, k in cells); k1 = max(k for _, k in cells)
        if len(cells) == (r1 - r0 + 1) * (k1 - k0 + 1):
            occ = c
        else:
            fig = c
    return h, w, bg, occ, fig


def _fig_box(inp, fig):
    h, w = len(inp), len(inp[0])
    cells = [(r, k) for r in range(h) for k in range(w) if inp[r][k] == fig]
    return (min(r for r, _ in cells), max(r for r, _ in cells),
            min(k for _, k in cells), max(k for _, k in cells))


def _repair(inp, vertical=False, shift=0, center2=None, paint=None,
            keep_occ=False, erase_only=False, rot180=False, whole=False):
    """Fill occluder cells from the mirrored figure."""
    h, w, bg, occ, fig = _parts(inp)
    r0, r1, k0, k1 = _fig_box(inp, fig)
    g = [row[:] for row in inp]
    for r in range(h):
        for k in range(w):
            if inp[r][k] != occ:
                continue
            if not keep_occ:
                g[r][k] = bg
    if erase_only:
        return g
    for r in range(h):
        for k in range(w):
            target = (inp[r][k] == occ) or (whole and inp[r][k] == bg)
            if not target:
                continue
            if rot180:
                sr, sk = (r0 + r1) - r, (k0 + k1) - k
            elif vertical:
                sr, sk = (r0 + r1) - r + shift, k
            else:
                c2 = (k0 + k1) if center2 is None else center2
                sk, sr = c2 - k + shift, r
            if 0 <= sr < h and 0 <= sk < w and inp[sr][sk] == fig:
                g[r][k] = fig if paint is None else paint(occ, fig)
    return g


def _unchanged(inp, out):
    return [row[:] for row in inp]


def _erase_only(inp, out):
    return _repair(inp, erase_only=True)


def _vertical(inp, out):
    return _repair(inp, vertical=True)


def _shift_right(inp, out):
    return _repair(inp, shift=1)


def _shift_left(inp, out):
    return _repair(inp, shift=-1)


def _occ_color(inp, out):
    return _repair(inp, paint=lambda occ, fig: occ)


def _keep_occ(inp, out):
    return _repair(inp, keep_occ=True)


def _fill_bbox(inp, out):
    h, w, bg, occ, fig = _parts(inp)
    g = [row[:] for row in inp]
    for r in range(h):
        for k in range(w):
            if inp[r][k] == occ:
                g[r][k] = fig
    return g


def _image_center(inp, out):
    w = len(inp[0])
    return _repair(inp, center2=w - 1)


def _rot180(inp, out):
    return _repair(inp, rot180=True)


def _crop_figure(inp, out):
    h, w, bg, occ, fig = _parts(inp)
    r0, r1, k0, k1 = _fig_box(inp, fig)
    return [row[k0:k1 + 1] for row in out[r0:r1 + 1]]


def _last_row_missed(inp, out):
    # repair stops one row short: the occluder's bottom row is erased but not repaired
    h, w, bg, occ, fig = _parts(inp)
    rows = [r for r in range(h) if occ in inp[r]]
    last = max(rows)
    g = [row[:] for row in out]
    for k in range(w):
        if inp[last][k] == occ:
            g[last][k] = bg
    return g


def _occ_survives(inp, out):
    # occluder cells left unrepaired: true output with the repaired cells put back to occluder
    h, w, bg, occ, fig = _parts(inp)
    g = [row[:] for row in out]
    for r in range(h):
        for k in range(w):
            if inp[r][k] == occ and out[r][k] == fig:
                g[r][k] = occ
    return g


ALTERNATIVES = [
    ("leave the occluder in place and change nothing", _unchanged),
    ("erase the occluder to background without repairing the figure", _erase_only),
    ("mirror the figure top-to-bottom instead of left-to-right", _vertical),
    ("mirror axis shifted one column right", _shift_right),
    ("mirror axis shifted one column left", _shift_left),
    ("repaired cells take the occluder color instead of the figure color", _occ_color),
    ("repair cells from the mirror but leave the other occluder cells in place", _keep_occ),
    ("replace every occluder cell with the figure color", _fill_bbox),
    ("mirror about the center column of the grid instead of the figure", _image_center),
    ("fill from the 180-degree point reflection of the figure", _rot180),
    ("crop the output to the figure bounding box", _crop_figure),
    ("repair stops one row short of the occluder's bottom row", _last_row_missed),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/3345333e.json').read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
