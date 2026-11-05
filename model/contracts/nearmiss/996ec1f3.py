"""Near-miss readings for ARC task 996ec1f3.

True rule: a uniform row and a uniform column divide the grid into four
panels. The output is 3x3: the four corners hold the panel colors in their
input positions, and every other cell holds the divider color.
"""
import json
from pathlib import Path


def _line(out):
    return out[1][1]


def _corners(out):
    return out[0][0], out[0][2], out[2][0], out[2][2]


def _build(tl, tr, bl, br, c):
    return [[tl, c, tr], [c, c, c], [bl, c, br]]


def hflip_panels(inp, out):
    return [r[::-1] for r in out]


def vflip_panels(inp, out):
    return out[::-1]


def transpose_panels(inp, out):
    return [list(r) for r in zip(*out)]


def rotate_clockwise(inp, out):
    return [list(r) for r in zip(*out[::-1])]


def rotate_180(inp, out):
    return [r[::-1] for r in out[::-1]]


def cross_in_panel_color(inp, out):
    tl, tr, bl, br = _corners(out)
    return _build(tl, tr, bl, br, tl)


def input_corner_cells(inp, out):
    c = _line(out)
    return _build(inp[0][0], inp[0][-1], inp[-1][0], inp[-1][-1], c)


def two_by_two(inp, out):
    tl, tr, bl, br = _corners(out)
    return [[tl, tr], [bl, br]]


def center_only_wrong(inp, out):
    g = [r[:] for r in out]
    g[1][1] = out[0][0]
    return g


def divider_bar_missing_arm(inp, out):
    g = [r[:] for r in out]
    g[1][0] = out[0][0]
    g[1][2] = out[0][2]
    return g


def thick_divider(inp, out):
    tl, tr, bl, br = _corners(out)
    c = _line(out)
    return [[tl, c, c, tr], [c, c, c, c], [c, c, c, c], [bl, c, c, br]]


def adjacent_panels_swapped(inp, out):
    tl, tr, bl, br = _corners(out)
    return _build(tl, tr, br, bl, _line(out))


ALTERNATIVES = [
    ("panels mirrored left-right", hflip_panels),
    ("panels mirrored top-bottom", vflip_panels),
    ("panel layout transposed", transpose_panels),
    ("panel layout rotated 90 degrees clockwise", rotate_clockwise),
    ("panel layout rotated 180 degrees", rotate_180),
    ("divider cells filled with the top-left panel color", cross_in_panel_color),
    ("panel colors read from the input's outermost corner cells", input_corner_cells),
    ("output has only the 2x2 panels, no divider row or column", two_by_two),
    ("center cell takes the top-left panel color instead of the divider color", center_only_wrong),
    ("horizontal arms of the divider replaced by the adjacent panel colors", divider_bar_missing_arm),
    ("divider counted two cells thick, giving a 4x4 output", thick_divider),
    ("bottom two panels swapped", adjacent_panels_swapped),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    w = len(g[0])
    if w == 0:
        return False
    for r in g:
        if not isinstance(r, list) or len(r) != w:
            return False
        if any(type(v) is not int or not 0 <= v <= 9 for v in r):
            return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/996ec1f3.json"))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
