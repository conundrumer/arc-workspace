import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(c for r in inp for c in r).most_common(1)[0][0]
    sep = [all(inp[r][c] == bg for r in range(h)) for c in range(w)]
    panels = []
    c = 0
    while c < w:
        if sep[c]:
            c += 1
            continue
        s = c
        while c < w and not sep[c]:
            c += 1
        panels.append((s, c))
    inks = []
    for s, e in panels:
        cols = {inp[r][x] for r in range(h) for x in range(s, e)} - {bg}
        inks.append(min(cols) if cols else bg)
    return bg, sep, panels, inks


def _render(inp, fillers, recolor_ink=None, fill_seps=None, fill_marks=False):
    """fillers[i]: color for bg cells of panel i (None keeps bg)."""
    bg, sep, panels, inks = _parse(inp)
    g = [row[:] for row in inp]
    for i, (s, e) in enumerate(panels):
        for r in range(len(g)):
            for x in range(s, e):
                if inp[r][x] == bg and fillers[i] is not None:
                    g[r][x] = fillers[i]
                elif inp[r][x] != bg and fill_marks and fillers[i] is not None:
                    g[r][x] = fillers[i]
    return g


def _ok(inp):
    bg, sep, panels, inks = _parse(inp)
    return len(panels) >= 2 and len(set(inks)) == len(inks) and bg not in inks


def fill_from_previous(inp, out):
    bg, sep, panels, inks = _parse(inp)
    n = len(panels)
    return _render(inp, [inks[(i - 1) % n] for i in range(n)])


def no_wrap(inp, out):
    bg, sep, panels, inks = _parse(inp)
    n = len(panels)
    return _render(inp, [inks[i + 1] if i + 1 < n else None for i in range(n)])


def own_color_for_last(inp, out):
    bg, sep, panels, inks = _parse(inp)
    n = len(panels)
    return _render(inp, [inks[(i + 1) % n] if i + 1 < n else inks[i] for i in range(n)])


def separators_filled(inp, out):
    bg, sep, panels, inks = _parse(inp)
    g = [row[:] for row in out]
    n = len(panels)
    for i in range(n - 1):
        for c in range(panels[i][1], panels[i + 1][0]):
            for r in range(len(g)):
                g[r][c] = inks[i + 1]
    return g


def only_first_panel(inp, out):
    bg, sep, panels, inks = _parse(inp)
    n = len(panels)
    return _render(inp, [inks[1]] + [None] * (n - 1))


def own_color_fill(inp, out):
    bg, sep, panels, inks = _parse(inp)
    return _render(inp, inks[:])


def marks_recolored_not_background(inp, out):
    bg, sep, panels, inks = _parse(inp)
    n = len(panels)
    g = [row[:] for row in inp]
    for i, (s, e) in enumerate(panels):
        for r in range(len(g)):
            for x in range(s, e):
                if inp[r][x] != bg:
                    g[r][x] = inks[(i + 1) % n]
    return g


def all_take_first_color(inp, out):
    bg, sep, panels, inks = _parse(inp)
    n = len(panels)
    return _render(inp, [inks[0]] * n)


def solid_panels(inp, out):
    bg, sep, panels, inks = _parse(inp)
    n = len(panels)
    return _render(inp, [inks[(i + 1) % n] for i in range(n)], fill_marks=True)


def marks_lost_in_output(inp, out):
    """Marks of each panel erased to background; fill stays."""
    bg, sep, panels, inks = _parse(inp)
    g = [row[:] for row in out]
    for i, (s, e) in enumerate(panels):
        for r in range(len(g)):
            for x in range(s, e):
                if inp[r][x] != bg:
                    g[r][x] = bg
    return g


def crop_last_column(inp, out):
    return [row[:-1] for row in out]


def input_unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("each panel takes the color of the panel to its left, the first takes the last's", fill_from_previous),
    ("no wrap: the last panel is left unfilled", no_wrap),
    ("the last panel fills with its own color instead of the first panel's", own_color_for_last),
    ("separator lines between panels also take the color of the panel to their right", separators_filled),
    ("only the first panel is filled", only_first_panel),
    ("every panel fills its background cells with its own color", own_color_fill),
    ("marks are recolored with the next panel's color and the background stays", marks_recolored_not_background),
    ("every panel fills with the first panel's color", all_take_first_color),
    ("marks are painted over too, so each panel is a solid block of the next color", solid_panels),
    ("fill is right but the marks of each panel are erased to background", marks_lost_in_output),
    ("output is cropped by one column on the right", crop_last_column),
    ("output equals the input", input_unchanged),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/c4d1a9ae.json").read_text())
    train = task["train"]
    print("readings", len(ALTERNATIVES), "pairs", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
