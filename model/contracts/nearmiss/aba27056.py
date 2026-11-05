import json
from pathlib import Path

FILL = 4


def _analyze(inp):
    h, w = len(inp), len(inp[0])
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != 0]
    r0 = min(r for r, c in cells)
    r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells)
    c1 = max(c for r, c in cells)
    color = inp[cells[0][0]][cells[0][1]]
    sides = {
        "top": ((-1, 0), True, r0, [(r0, c) for c in range(c0 + 1, c1)]),
        "bottom": ((1, 0), True, r1, [(r1, c) for c in range(c0 + 1, c1)]),
        "left": ((0, -1), False, c0, [(r, c0) for r in range(r0 + 1, r1)]),
        "right": ((0, 1), False, c1, [(r, c1) for r in range(r0 + 1, r1)]),
    }
    for name, (out, horiz, line, cs) in sides.items():
        gaps = [p for p in cs if inp[p[0]][p[1]] == 0]
        if gaps:
            ss = [p[1] if horiz else p[0] for p in gaps]
            side_lo = (c0 if horiz else r0)
            side_hi = (c1 if horiz else r1)
            return dict(h=h, w=w, box=(r0, r1, c0, c1), color=color, out=out,
                        horiz=horiz, line=line, lo=min(ss), hi=max(ss),
                        side_lo=side_lo, side_hi=side_hi)
    return None


def _point(a, s, k):
    dr, dc = a["out"]
    if a["horiz"]:
        return (a["line"] + k * dr, s)
    return (s, a["line"] + k * dc)


def _build(inp, beam=True, rays=True, interior=True, opening=True,
           beam_span="opening", ray_start=1, ray_shift=0, ends=(0, 1),
           inward=False, beam_color=FILL, ray_color=FILL):
    a = _analyze(inp)
    if a is None:
        return None
    g = [row[:] for row in inp]

    def put(p, col):
        if 0 <= p[0] < a["h"] and 0 <= p[1] < a["w"]:
            g[p[0]][p[1]] = col

    r0, r1, c0, c1 = a["box"]
    if interior:
        for r in range(r0 + 1, r1):
            for c in range(c0 + 1, c1):
                put((r, c), FILL)
    if opening:
        for s in range(a["lo"], a["hi"] + 1):
            put(_point(a, s, 0), FILL)
    if beam:
        if beam_span == "opening":
            span = range(a["lo"], a["hi"] + 1)
        elif beam_span == "first":
            span = [a["lo"]]
        else:
            span = range(a["side_lo"], a["side_hi"] + 1)
        step = -1 if inward else 1
        k = step
        n = max(a["h"], a["w"])
        for _ in range(n):
            for s in span:
                put(_point(a, s, k), beam_color)
            k += step
    if rays:
        n = max(a["h"], a["w"])
        for end in ends:
            for k in range(ray_start, n):
                if end == 0:
                    s = a["lo"] - k + ray_shift
                else:
                    s = a["hi"] + k - ray_shift
                put(_point(a, s, k), ray_color)
    return g


def _keep(f):
    return f


def no_rays(inp, out):
    return _build(inp, rays=False)


def no_beam(inp, out):
    return _build(inp, beam=False)


def no_interior(inp, out):
    return _build(inp, interior=False)


def beam_inward(inp, out):
    return _build(inp, inward=True)


def beam_one_wide(inp, out):
    return _build(inp, beam_span="first")


def beam_side_wide(inp, out):
    return _build(inp, beam_span="side")


def rays_skip_first(inp, out):
    return _build(inp, ray_start=2)


def rays_lag_one(inp, out):
    return _build(inp, ray_shift=1)


def opening_unfilled(inp, out):
    a = _analyze(inp)
    if a is None:
        return None
    g = [row[:] for row in out]
    for s in range(a["lo"], a["hi"] + 1):
        r, c = _point(a, s, 0)
        g[r][c] = inp[r][c]
    return g


def wall_colored_light(inp, out):
    a = _analyze(inp)
    return _build(inp, beam_color=a["color"], ray_color=a["color"])


def one_ray_only(inp, out):
    return _build(inp, ends=(1,))


ALTERNATIVES = [
    ("only the box interior and opening are filled; no band and no diagonal rays", lambda i, o: _build(i, beam=False, rays=False)),
    ("band and interior filled; diagonal rays left out", no_rays),
    ("rays and interior filled; band left out", no_beam),
    ("band and rays drawn but the interior stays unfilled", no_interior),
    ("band goes into the box and out the far side instead of away from the box", beam_inward),
    ("band is one cell wide instead of as wide as the opening", beam_one_wide),
    ("band is as wide as the whole broken side", beam_side_wide),
    ("diagonal rays start one step too far out", rays_skip_first),
    ("diagonal rays lean one column toward the band", rays_lag_one),
    ("opening cells themselves stay background", opening_unfilled),
    ("band and rays take the box color instead of the new color", wall_colored_light),
    ("diagonal ray only from one end of the opening", one_ray_only),
]


def _valid(g, out):
    if g is None:
        return False
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/aba27056.json").read_text())
    pairs = task["train"]
    truth = [_build(p["input"]) for p in pairs]
    print("truth reproduced:", [t == p["output"] for t, p in zip(truth, pairs)])
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            if _valid(f(p["input"], p["output"]), p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
