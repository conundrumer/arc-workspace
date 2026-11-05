import json
from pathlib import Path


def _band(inp):
    rows = [i for i, r in enumerate(inp) if any(v != 0 for v in r)]
    return rows[0], rows[-1]


def _tile(inp, pattern, r0, phase=0, lo=None, hi=None):
    """Row i takes pattern[(i - r0 + phase) % len(pattern)]; rows outside [lo, hi] are blank."""
    h, w = len(inp), len(inp[0])
    lo = 0 if lo is None else lo
    hi = h - 1 if hi is None else hi
    g = []
    for i in range(h):
        if lo <= i <= hi:
            g.append(list(pattern[(i - r0 + phase) % len(pattern)]))
        else:
            g.append([0] * w)
    return g


def tile_down_only(inp, out):
    r0, r1 = _band(inp)
    pat = [inp[i] for i in range(r0, r1 + 1)]
    return _tile(inp, pat, r0, lo=r0)


def tile_up_only(inp, out):
    r0, r1 = _band(inp)
    pat = [inp[i] for i in range(r0, r1 + 1)]
    return _tile(inp, pat, r0, hi=r1)


def phase_shift_one(inp, out):
    r0, r1 = _band(inp)
    pat = [inp[i] for i in range(r0, r1 + 1)]
    return _tile(inp, pat, r0, phase=1)


def period_two(inp, out):
    r0, r1 = _band(inp)
    pat = [inp[i] for i in range(r0, r1)]
    return _tile(inp, pat, r0)


def period_with_gap(inp, out):
    r0, r1 = _band(inp)
    pat = [inp[i] for i in range(r0, r1 + 1)] + [[0] * len(inp[0])]
    return _tile(inp, pat, r0)


def mirror_tiling(inp, out):
    r0, r1 = _band(inp)
    pat = [inp[i] for i in range(r0, r1 + 1)]
    n = len(pat)
    cyc = pat + pat[::-1]
    return _tile(inp, cyc, r0)


def swap_colors(inp, out):
    cols = {v for r in out for v in r if v != 0}
    if len(cols) != 1:
        return None
    c = cols.pop()
    return [[0 if v == c else c for v in r] for r in out]


def horizontal_offset(inp, out):
    return [r[-1:] + r[:-1] for r in out]


def drop_solid_rows(inp, out):
    return [[0] * len(r) if all(v != 0 for v in r) else list(r) for r in out]


def one_repeat_each_side(inp, out):
    r0, r1 = _band(inp)
    n = r1 - r0 + 1
    pat = [inp[i] for i in range(r0, r1 + 1)]
    return _tile(inp, pat, r0, lo=r0 - n, hi=r1 + n)


def crop_band_only(inp, out):
    r0, r1 = _band(inp)
    return [list(inp[i]) for i in range(r0, r1 + 1)]


def unchanged(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("tile the band downward only, rows above it stay blank", tile_down_only),
    ("tile the band upward only, rows below it stay blank", tile_up_only),
    ("tile phase anchored one row off the band", phase_shift_one),
    ("tile period of two rows (last band row dropped)", period_two),
    ("tile period of band plus one blank row", period_with_gap),
    ("tile with mirrored repeats instead of plain repeats", mirror_tiling),
    ("swap the pattern color and the background", swap_colors),
    ("tiled output shifted one column to the right", horizontal_offset),
    ("solid rows treated as background and left blank", drop_solid_rows),
    ("only one repeat of the band on each side of it", one_repeat_each_side),
    ("output is only the cropped band", crop_band_only),
    ("input returned unchanged", unchanged),
]


def _valid(g, out):
    if g is None or not g or not isinstance(g, list):
        return False
    w = len(g[0])
    for r in g:
        if not isinstance(r, list) or len(r) != w:
            return False
        for v in r:
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9:
                return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/8eb1be9a.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
