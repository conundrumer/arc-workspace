"""Near-miss readings for ARC task 8a004b2b."""
import json
from collections import Counter
from pathlib import Path


def _bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), min(cs), max(rs), max(cs)


def _parse(inp, out):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for row in inp for v in row).most_common(1)[0][0]
    marker = None
    for col in range(10):
        cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == col]
        if col != bg and len(cells) == 4:
            r0, c0, r1, c1 = _bbox(cells)
            if set(cells) == {(r0, c0), (r0, c1), (r1, c0), (r1, c1)}:
                marker = col
                fr = (r0, c0, r1, c1)
    r0, c0, r1, c1 = fr
    crop = [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]
    blocks = {(r, c) for r in range(len(crop)) for c in range(len(crop[0]))
              if crop[r][c] not in (bg, marker)}
    outside = [(r, c) for r in range(h) for c in range(w)
               if inp[r][c] != bg and not (r0 <= r <= r1 and c0 <= c <= c1)]
    br0, bc0, br1, bc1 = _bbox(outside)
    bp = [row[bc0:bc1 + 1] for row in inp[br0:br1 + 1]]
    ink = [(r, c) for r in range(len(out)) for c in range(len(out[0]))
           if out[r][c] not in (bg, marker)]
    ir0, ic0, ir1, ic1 = _bbox(ink)
    k = (ir1 - ir0 + 1) // len(bp)
    return dict(bg=bg, marker=marker, crop=crop, blocks=blocks, bp=bp, k=k,
                ink=(ir0, ic0, ir1, ic1), fr=fr)


def _scale(g, k):
    return [[v for v in row for _ in range(k)] for row in g for _ in range(k)]


def _render(inp, out, P, draw, r0=None, c0=None, keep_blocks=True,
            recolor=None):
    ir0, ic0, ir1, ic1 = P["ink"]
    r0 = ir0 if r0 is None else r0
    c0 = ic0 if c0 is None else c0
    g = [row[:] for row in out]
    for r in range(ir0, ir1 + 1):
        for c in range(ic0, ic1 + 1):
            g[r][c] = P["bg"]
    for i, row in enumerate(draw):
        for j, v in enumerate(row):
            r, c = r0 + i, c0 + j
            if v != P["bg"] and 0 <= r < len(g) and 0 <= c < len(g[0]):
                g[r][c] = v if recolor is None else recolor
    for r, c in P["blocks"]:
        g[r][c] = P["crop"][r][c] if keep_blocks else P["bg"]
    return g


def frame_crop_only(inp, out):
    return [row[:] for row in _parse(inp, out)["crop"]]


def inset_crop(inp, out):
    return [row[1:-1] for row in out[1:-1]]


def unscaled_drawing(inp, out):
    P = _parse(inp, out)
    return _render(inp, out, P, P["bp"])


def oversized_drawing(inp, out):
    P = _parse(inp, out)
    return _render(inp, out, P, _scale(P["bp"], P["k"] + 1))


def mirrored_drawing(inp, out):
    P = _parse(inp, out)
    bp = [row[::-1] for row in P["bp"]]
    return _render(inp, out, P, _scale(bp, P["k"]))


def transposed_drawing(inp, out):
    P = _parse(inp, out)
    bp = [list(r) for r in zip(*P["bp"])]
    return _render(inp, out, P, _scale(bp, P["k"]))


def blocks_erased(inp, out):
    P = _parse(inp, out)
    return _render(inp, out, P, _scale(P["bp"], P["k"]), keep_blocks=False)


def drawing_shifted_right(inp, out):
    P = _parse(inp, out)
    return _render(inp, out, P, _scale(P["bp"], P["k"]),
                   c0=P["ink"][1] + 1)


def drawing_crop_only(inp, out):
    ir0, ic0, ir1, ic1 = _parse(inp, out)["ink"]
    return [row[ic0:ic1 + 1] for row in out[ir0:ir1 + 1]]


def drawing_in_marker_color(inp, out):
    P = _parse(inp, out)
    return _render(inp, out, P, _scale(P["bp"], P["k"]), recolor=P["marker"])


def raw_blueprint(inp, out):
    return [row[:] for row in _parse(inp, out)["bp"]]


ALTERNATIVES = [
    ("output the frame interior as in the input, without painting the drawing", frame_crop_only),
    ("crop one cell inside the marker corners, dropping the marker row and column", inset_crop),
    ("paint the outside drawing unscaled (one cell per drawing cell)", unscaled_drawing),
    ("scale the drawing one step larger than the block side", oversized_drawing),
    ("paint the drawing mirrored left to right", mirrored_drawing),
    ("paint the drawing transposed", transposed_drawing),
    ("paint the drawing but blank the original block cells", blocks_erased),
    ("paint the drawing shifted one cell right of where the blocks match", drawing_shifted_right),
    ("output only the painted drawing area, cropped out of the frame", drawing_crop_only),
    ("paint the drawing in the marker color instead of its own colors", drawing_in_marker_color),
    ("output the outside blueprint itself, unscaled and uncropped to the frame", raw_blueprint),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/8a004b2b.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
