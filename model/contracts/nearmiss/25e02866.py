import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _panels(inp):
    """Return (bg, panel_color, [(box, paint_dict)]) with 4-connected panels of ink."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    ink = {(r, c) for r in range(h) for c in range(w) if inp[r][c] != bg}
    pc = Counter(inp[r][c] for r, c in ink).most_common(1)[0][0]
    seen, panels = set(), []
    for s in sorted(ink):
        if s in seen:
            continue
        stack, comp = [s], []
        seen.add(s)
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (r + d[0], c + d[1])
                if n in ink and n not in seen:
                    seen.add(n)
                    stack.append(n)
        r0 = min(r for r, _ in comp)
        c0 = min(c for _, c in comp)
        r1 = max(r for r, _ in comp)
        c1 = max(c for _, c in comp)
        paint = {(r - r0, c - c0): inp[r][c] for r, c in comp if inp[r][c] != pc}
        panels.append(((r1 - r0 + 1, c1 - c0 + 1), paint))
    return bg, pc, panels


def _compose(inp, selected=None, fill=None, paint_color_ok=lambda c: True):
    bg, pc, panels = _panels(inp)
    if selected is not None:
        panels = selected(panels)
    h, w = panels[0][0]
    g = [[pc if fill is None else fill] * w for _ in range(h)]
    for _, paint in panels:
        for (r, c), v in paint.items():
            if paint_color_ok(v):
                g[r][c] = v
    return g


def bg_fill(inp, out):
    bg = _bg(inp)
    return _compose(inp, fill=bg)


def zero_fill(inp, out):
    return _compose(inp, fill=0)


def first_panel_only(inp, out):
    return _compose(inp, selected=lambda ps: ps[:1])


def last_panel_only(inp, out):
    return _compose(inp, selected=lambda ps: ps[-1:])


def densest_panel_only(inp, out):
    return _compose(inp, selected=lambda ps: [max(ps, key=lambda p: len(p[1]))])


def intersection_of_paints(inp, out):
    bg, pc, panels = _panels(inp)
    common = set(panels[0][1].items())
    for _, p in panels[1:]:
        common &= set(p.items())
    h, w = panels[0][0]
    g = [[pc] * w for _ in range(h)]
    for (r, c), v in common:
        g[r][c] = v
    return g


def drop_least_frequent_paint(inp, out):
    bg, pc, panels = _panels(inp)
    cnt = Counter(v for _, p in panels for v in p.values())
    if len(cnt) < 2:
        return None
    least = min(cnt, key=lambda k: (cnt[k], k))
    return _compose(inp, paint_color_ok=lambda c: c != least)


def paint_as_fill(inp, out):
    bg, pc, panels = _panels(inp)
    cnt = Counter(v for _, p in panels for v in p.values())
    top = cnt.most_common(1)[0][0]
    return _compose(inp, fill=top, paint_color_ok=lambda c: c != top)


def crop_interior(inp, out):
    return [r[1:-1] for r in out[1:-1]]


def extra_row(inp, out):
    return [list(r) for r in out] + [[_panels(inp)[1]] * len(out[0])]


def pad_with_bg(inp, out):
    bg = _bg(inp)
    w = len(out[0]) + 2
    return [[bg] * w] + [[bg] + list(r) + [bg] for r in out] + [[bg] * w]


def mirror_horizontal(inp, out):
    return [list(reversed(r)) for r in out]


def rotate_ccw(inp, out):
    return [list(r) for r in zip(*out)][::-1]


def unchanged_input(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("unpainted frame cells get the background color instead of the panel color", bg_fill),
    ("unpainted frame cells are 0", zero_fill),
    ("only the first panel's painted cells are overlaid", first_panel_only),
    ("only the last panel's painted cells are overlaid", last_panel_only),
    ("only the panel with the most painted cells is overlaid", densest_panel_only),
    ("painted cells kept only where every panel paints the same color (intersection, not union)", intersection_of_paints),
    ("the least frequent paint color is dropped", drop_least_frequent_paint),
    ("the most frequent paint color is taken as the frame fill and not painted", paint_as_fill),
    ("output is the frame's interior only, border cropped away", crop_interior),
    ("output frame is one row too tall", extra_row),
    ("output has an extra border of background color around the frame", pad_with_bg),
    ("output is mirrored left-right", mirror_horizontal),
]


def _valid(g, out):
    if g is None:
        return False
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/25e02866.json").read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error:", e)
                g = None
            n += _valid(g, p["output"])
        print(f"{n}/{len(train)}  {desc}")
