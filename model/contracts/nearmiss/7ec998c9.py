import json
from collections import Counter
from pathlib import Path


def _info(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    mr, mc = next((r, c) for r in range(h) for c in range(w) if inp[r][c] != bg)
    return h, w, bg, mr, mc, inp[mr][mc]


def _line_color(inp, out):
    h, w, bg, mr, mc, mk = _info(inp)
    return next(out[r][c] for r in range(h) for c in range(w) if out[r][c] not in (bg, mk))


def _draw(inp, out, up=True, down=True, top_dir=None, bot_dir=None, arm_off=0,
          trim=0, color=None, hit_mark=False, cross=False):
    h, w, bg, mr, mc, mk = _info(inp)
    col = _line_color(inp, out) if color is None else color
    d = -1 if (mr + mc) % 2 == 1 else 1
    td = d if top_dir is None else top_dir
    bd = -d if bot_dir is None else bot_dir
    g = [[bg] * w for _ in range(h)]
    g[mr][mc] = mk
    if up:
        for r in range(0, mr):
            g[r][mc] = col
    if down:
        for r in range(mr + 1, h):
            g[r][mc] = col
    for row, dd in ((arm_off, td), (h - 1 - arm_off, bd)):
        if dd == 0:
            continue
        rng = range(mc, -1, -1) if dd < 0 else range(mc, w)
        cells = [c for c in rng]
        if trim:
            cells = cells[:-trim]
        for c in cells:
            if (row, c) != (mr, mc):
                g[row][c] = col
    if cross:
        for c in range(w):
            if c != mc and (mr, c) != (mr, mc):
                g[mr][c] = col
    if hit_mark:
        g[mr][mc] = col
    return g


def alt_horizontal_stem(inp, out):
    t = lambda g: [list(r) for r in zip(*g)]
    return t(_draw(t(inp), t(out)))


def alt_arms_swapped(inp, out):
    d = _draw(inp, out)
    h, w, bg, mr, mc, mk = _info(inp)
    return _draw(inp, out, top_dir=-1 if (mr + mc) % 2 == 0 else 1,
                 bot_dir=1 if (mr + mc) % 2 == 0 else -1)


def alt_stem_only(inp, out):
    return _draw(inp, out, top_dir=0, bot_dir=0)


def alt_stem_above_only(inp, out):
    return _draw(inp, out, down=False, bot_dir=0)


def alt_mark_overwritten(inp, out):
    return _draw(inp, out, hit_mark=True)


def alt_arms_same_side(inp, out):
    h, w, bg, mr, mc, mk = _info(inp)
    d = -1 if (mr + mc) % 2 == 1 else 1
    return _draw(inp, out, top_dir=d, bot_dir=d)


def alt_arms_inset_one_row(inp, out):
    return _draw(inp, out, arm_off=1)


def alt_mark_color_line(inp, out):
    h, w, bg, mr, mc, mk = _info(inp)
    return _draw(inp, out, color=mk)


def alt_arm_short(inp, out):
    return _draw(inp, out, trim=1)


def alt_full_cross(inp, out):
    return _draw(inp, out, cross=True)


def alt_transposed_output(inp, out):
    return [list(r) for r in zip(*out)]


def alt_arms_ignore_parity_always_left(inp, out):
    return _draw(inp, out, top_dir=-1, bot_dir=1)


def alt_unchanged(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("stem runs along the mark's row instead of its column (transposed rule)", alt_horizontal_stem),
    ("arm directions swapped: parity of mark position read the opposite way", alt_arms_swapped),
    ("only the stem is drawn, no arms", alt_stem_only),
    ("stem drawn only above the mark, no bottom arm", alt_stem_above_only),
    ("the mark cell itself is recolored to the line color", alt_mark_overwritten),
    ("both arms point the same way instead of opposite ways", alt_arms_same_side),
    ("arms drawn one row inside the edge instead of on the edge row", alt_arms_inset_one_row),
    ("line drawn in the mark's color instead of the new color", alt_mark_color_line),
    ("each arm stops one cell short of the grid edge", alt_arm_short),
    ("a full cross: the mark's row is also filled", alt_full_cross),
    ("true output transposed (whole figure rotated)", alt_transposed_output),
    ("arm direction fixed (top left, bottom right) regardless of mark parity", alt_arms_ignore_parity_always_left),
    ("output equals input", alt_unchanged),
]

# unchanged is the single allowed identity reading; keep list within 8-12
ALTERNATIVES = [a for a in ALTERNATIVES if a[1] is not alt_transposed_output]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/7ec998c9.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
