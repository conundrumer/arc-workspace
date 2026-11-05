import json
from pathlib import Path

DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
OPP = {"up": "down", "down": "up", "left": "right", "right": "left"}
PERP = {"up": "right", "right": "down", "down": "left", "left": "up"}


def find_mark(inp):
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v not in (0, 1):
                return r, c, v
    raise ValueError("no mark")


def edge_dir(inp, r, c):
    h, w = len(inp), len(inp[0])
    if c == w - 1:
        return "right"
    if c == 0:
        return "left"
    if r == 0:
        return "up"
    return "down"


def simulate(inp, fall=1, fill=0, direction=None, count_mark=True, beam_delta=0,
             beam_gap=0, beam_all=False, beam_color=9, beam=True, uniform=False):
    h, w = len(inp), len(inp[0])
    r0, c0, mc = find_mark(inp)
    d = direction or edge_dir(inp, r0, c0)
    dr, dc = DIRS[d]
    horiz = dr == 0
    nlines = h if horiz else w
    length = w if horiz else h
    mline = r0 if horiz else c0
    counts = []
    for ln in range(nlines):
        cells = [inp[ln][k] if horiz else inp[k][ln] for k in range(length)]
        n = sum(1 for v in cells if v == fall)
        if ln == mline and count_mark:
            n += 1
        counts.append(n)
    if uniform:
        counts = [counts[mline]] * nlines
    out = [[fill] * w for _ in range(h)]

    def put(ln, k, v):
        if 0 <= k < length:
            if horiz:
                out[ln][k] = v
            else:
                out[k][ln] = v

    sign = dr + dc  # +1 falls toward high index
    for ln in range(nlines):
        n = counts[ln]
        for i in range(n):
            k = length - 1 - i if sign > 0 else i
            put(ln, k, fall)
    if beam:
        for ln in range(nlines):
            if not beam_all and ln != mline:
                continue
            n = counts[ln]
            blen = n - 1 + beam_delta
            inner = length - n if sign > 0 else n - 1
            for i in range(1 + beam_gap, blen + 1 + beam_gap):
                k = inner - i if sign > 0 else inner + i
                if 0 <= k < length:
                    put(ln, k, beam_color)
    # mark
    out[r0][c0] = mc
    return out


def base(inp):
    return simulate(inp)


def zeros_fall(inp, out):
    return simulate(inp, fall=0, fill=1)


def mark_not_counted(inp, out):
    return simulate(inp, count_mark=False)


def fall_opposite(inp, out):
    r, c, _ = find_mark(inp)
    return simulate(inp, direction=OPP[edge_dir(inp, r, c)])


def fall_perpendicular(inp, out):
    r, c, _ = find_mark(inp)
    return simulate(inp, direction=PERP[edge_dir(inp, r, c)])


def beam_shorter(inp, out):
    return simulate(inp, beam_delta=-1)


def beam_longer(inp, out):
    return simulate(inp, beam_delta=1)


def beam_mark_color(inp, out):
    _, _, mc = find_mark(inp)
    return simulate(inp, beam_color=mc)


def no_beam(inp, out):
    return simulate(inp, beam=False)


def beam_every_line(inp, out):
    return simulate(inp, beam_all=True)


def beam_gap(inp, out):
    return simulate(inp, beam_gap=1)


def uniform_stack(inp, out):
    return simulate(inp, uniform=True)


ALTERNATIVES = [
    ("cells of the fill color 0 fall and stack, and 1 is the background", zeros_fall),
    ("the mark cell is not counted as a falling cell, so its line stacks one cell fewer", mark_not_counted),
    ("cells fall away from the mark's edge, toward the opposite edge", fall_opposite),
    ("cells fall toward an edge perpendicular to the mark's edge", fall_perpendicular),
    ("the beam is one cell shorter than the correct length", beam_shorter),
    ("the beam is one cell longer than the correct length", beam_longer),
    ("the beam is drawn in the mark color instead of 9", beam_mark_color),
    ("no beam is drawn; only the stacks are output", no_beam),
    ("a beam is drawn from the stack of every line, not only the mark's line", beam_every_line),
    ("the beam starts one cell away from the stack, leaving a gap", beam_gap),
    ("every line stacks as many cells as the mark's line", uniform_stack),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/5e6bbc0b.json"))
    train = task["train"]
    assert all(base(p["input"]) == p["output"] for p in train), "base solver mismatch"
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
