"""Near-miss readings for ARC task b20f7c8b (legend strip, 5x5 glyph boxes <-> solid boxes)."""
import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    board = Counter(v for r in inp for v in r).most_common(1)[0][0]
    left = all(inp[r][0] != board for r in range(h))
    c0, c1 = (0, 6) if left else (w - 6, w)
    panel = Counter(inp[r][c] for r in range(h) for c in range(c0, c1)).most_common(1)[0][0]

    def comps(cells):
        seen, res = set(), []
        for s in sorted(cells):
            if s in seen:
                continue
            st, comp = [s], []
            seen.add(s)
            while st:
                r, c = st.pop()
                comp.append((r, c))
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        n = (r + dr, c + dc)
                        if n in cells and n not in seen:
                            seen.add(n)
                            st.append(n)
            res.append(sorted(comp))
        return res

    strip_cells = {(r, c) for r in range(h) for c in range(c0, c1) if inp[r][c] != panel}
    glyphs = []
    for comp in comps(strip_cells):
        r0 = min(r for r, _ in comp)
        cc0 = min(c for _, c in comp)
        pat = tuple(tuple((r0 + i, cc0 + j) in set(comp) for j in range(3)) for i in range(3))
        glyphs.append({"color": inp[comp[0][0]][comp[0][1]], "pat": pat, "r": r0})
    glyphs.sort(key=lambda g: g["r"])
    box_cells = {(r, c) for r in range(h) for c in range(w)
                 if not (c0 <= c < c1) and inp[r][c] != board}
    boxes = []
    for comp in comps(box_cells):
        r0 = min(r for r, _ in comp)
        bc0 = min(c for _, c in comp)
        cols = Counter(inp[r][c] for r, c in comp)
        if len(cols) == 1:
            boxes.append({"r": r0, "c": bc0, "solid": True, "color": next(iter(cols))})
        else:
            frame = inp[r0][bc0]
            ink = next(k for k in cols if k != frame)
            pat = tuple(tuple(inp[r0 + 1 + i][bc0 + 1 + j] == ink for j in range(3)) for i in range(3))
            boxes.append({"r": r0, "c": bc0, "solid": False, "frame": frame, "ink": ink, "pat": pat})
    boxes.sort(key=lambda b: (b["r"], b["c"]))
    return {"board": board, "c0": c0, "c1": c1, "panel": panel, "glyphs": glyphs, "boxes": boxes}


def _rot(p):
    return tuple(zip(*p[::-1]))


def _variants(p):
    res = []
    for q in (p, tuple(r[::-1] for r in p)):
        for _ in range(4):
            res.append(q)
            q = _rot(q)
    return res


def _transpose(p):
    return tuple(zip(*p))


def _fill(g, b, color):
    for i in range(5):
        for j in range(5):
            g[b["r"] + i][b["c"] + j] = color


def _draw_glyph(g, b, frame, ink, pat):
    _fill(g, b, frame)
    for i in range(3):
        for j in range(3):
            if pat[i][j]:
                g[b["r"] + 1 + i][b["c"] + 1 + j] = ink


def _copy(g):
    return [list(r) for r in g]


def _glyph_of(P, color):
    return next(g for g in P["glyphs"] if g["color"] == color)


def _colors(P):
    for b in P["boxes"]:
        if not b["solid"]:
            return b["frame"], b["ink"]
    return 2, 1


def _restore_boxes(inp, out, boxes):
    g = _copy(out)
    for b in boxes:
        for i in range(5):
            for j in range(5):
                g[b["r"] + i][b["c"] + j] = inp[b["r"] + i][b["c"] + j]
    return g


def only_glyph_to_solid(inp, out):
    P = _parse(inp)
    return _restore_boxes(inp, out, [b for b in P["boxes"] if b["solid"]])


def only_solid_to_glyph(inp, out):
    P = _parse(inp)
    return _restore_boxes(inp, out, [b for b in P["boxes"] if not b["solid"]])


def solid_becomes_empty_frame(inp, out):
    P = _parse(inp)
    g = _copy(out)
    for b in P["boxes"]:
        if b["solid"]:
            _fill(g, b, _colors(P)[0])
    return g


def solid_swapped_frame_ink(inp, out):
    P = _parse(inp)
    F, I = _colors(P)
    g = _copy(out)
    for b in P["boxes"]:
        if b["solid"]:
            _draw_glyph(g, b, I, F, _glyph_of(P, b["color"])["pat"])
    return g


def glyph_box_takes_frame_color(inp, out):
    P = _parse(inp)
    g = _copy(out)
    for b in P["boxes"]:
        if not b["solid"]:
            _fill(g, b, b["frame"])
    return g


def exact_match_only(inp, out):
    P = _parse(inp)
    g = _copy(out)
    for b in P["boxes"]:
        if not b["solid"]:
            if not any(gl["pat"] == b["pat"] for gl in P["glyphs"]):
                _restore_boxes_one(inp, g, b)
    return g


def _restore_boxes_one(inp, g, b):
    for i in range(5):
        for j in range(5):
            g[b["r"] + i][b["c"] + j] = inp[b["r"] + i][b["c"] + j]


def legend_order_assignment(inp, out):
    P = _parse(inp)
    g = _copy(out)
    gb = [b for b in P["boxes"] if not b["solid"]]
    for b, gl in zip(gb, P["glyphs"]):
        _fill(g, b, gl["color"])
    return g


def solid_glyph_transposed(inp, out):
    P = _parse(inp)
    F, I = _colors(P)
    g = _copy(out)
    for b in P["boxes"]:
        if b["solid"]:
            _draw_glyph(g, b, F, I, _transpose(_glyph_of(P, b["color"])["pat"]))
    return g


def solid_fill_keeps_frame(inp, out):
    P = _parse(inp)
    g = _copy(out)
    for b in P["boxes"]:
        if not b["solid"]:
            c = out[b["r"] + 2][b["c"] + 2]
            for i in range(1, 4):
                for j in range(1, 4):
                    g[b["r"] + i][b["c"] + j] = c
            for i in range(5):
                for j in range(5):
                    if i in (0, 4) or j in (0, 4):
                        g[b["r"] + i][b["c"] + j] = b["frame"]
    return g


def legend_erased(inp, out):
    P = _parse(inp)
    g = _copy(out)
    for r in range(len(g)):
        for c in range(P["c0"], P["c1"]):
            g[r][c] = P["board"]
    return g


def crop_off_legend(inp, out):
    P = _parse(inp)
    return [r[P["c1"]:] if P["c0"] == 0 else r[:P["c0"]] for r in out]


ALTERNATIVES = [
    ("only glyph boxes become solid; solid boxes stay unchanged", only_glyph_to_solid),
    ("only solid boxes become glyph boxes; glyph boxes stay unchanged", only_solid_to_glyph),
    ("solid box becomes an all-frame-color box with no glyph drawn", solid_becomes_empty_frame),
    ("solid box becomes glyph box with frame and ink colors swapped", solid_swapped_frame_ink),
    ("glyph box becomes solid in its own frame color", glyph_box_takes_frame_color),
    ("glyph box matches legend by exact pattern only; unmatched stays", exact_match_only),
    ("glyph boxes take legend colors by position order, not by shape match", legend_order_assignment),
    ("solid box draws the transposed legend glyph", solid_glyph_transposed),
    ("glyph box turns solid only inside; its frame stays frame color", solid_fill_keeps_frame),
    ("legend strip is erased to board color", legend_erased),
    ("output is cropped to the board, dropping the legend strip", crop_off_legend),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/b20f7c8b.json"))
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
