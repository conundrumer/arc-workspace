from pathlib import Path
import json

CYCLE = [2, 5, 0, 5]


def _info(inp):
    h, w = len(inp), len(inp[0])
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != 0]
    r0 = min(r for r, c in cells)
    r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells)
    c1 = max(c for r, c in cells)
    return h, w, r0, r1, c0, c1, inp[r0][c0]


def _paint(inp, cycle, depth_fn=None, skip_depth0=False, offset=0, frame_color=None):
    h, w, r0, r1, c0, c1, fc = _info(inp)
    g = [row[:] for row in inp]
    for r in range(r0 + 1, r1):
        for c in range(c0 + 1, c1):
            if depth_fn:
                d = depth_fn(r, c, r0, r1, c0, c1)
            else:
                d = min(r - r0, r1 - r, c - c0, c1 - c) - 1
            if skip_depth0 and d == 0:
                continue
            g[r][c] = cycle[(d + offset) % len(cycle)]
    if frame_color is not None:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if inp[r][c] == fc:
                    g[r][c] = frame_color
    return g


def period3(inp, out):
    return _paint(inp, [2, 5, 0])


def period2(inp, out):
    return _paint(inp, [2, 5])


def swapped(inp, out):
    return _paint(inp, [0, 5, 2, 5])


def offset_plus(inp, out):
    return _paint(inp, CYCLE, offset=1)


def offset_minus(inp, out):
    return _paint(inp, CYCLE, offset=-1)


def first_ring_only(inp, out):
    h, w, r0, r1, c0, c1, fc = _info(inp)
    g = [row[:] for row in inp]
    for r in range(r0 + 1, r1):
        for c in range(c0 + 1, c1):
            if min(r - r0, r1 - r, c - c0, c1 - c) == 1:
                g[r][c] = 2
    return g


def fill_all_two(inp, out):
    h, w, r0, r1, c0, c1, fc = _info(inp)
    g = [row[:] for row in inp]
    for r in range(r0 + 1, r1):
        for c in range(c0 + 1, c1):
            g[r][c] = 2
    return g


def frame_recolored(inp, out):
    h, w, r0, r1, c0, c1, fc = _info(inp)
    g = [row[:] for row in out]
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if inp[r][c] == fc:
                g[r][c] = 2
    return g


def row_depth_only(inp, out):
    return _paint(inp, CYCLE,
                  depth_fn=lambda r, c, r0, r1, c0, c1: min(r - r0, r1 - r) - 1)


def first_ring_unpainted(inp, out):
    return _paint(inp, CYCLE, offset=0, skip_depth0=True)


def pad_one_more_ring(inp, out):
    # Region wrongly taken to include the frame ring, so depths shift by one
    # and the frame cells take the cycle too.
    h, w, r0, r1, c0, c1, fc = _info(inp)
    g = [row[:] for row in inp]
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            d = min(r - r0, r1 - r, c - c0, c1 - c)
            g[r][c] = CYCLE[d % 4]
    return g


def crop_to_frame(inp, out):
    h, w, r0, r1, c0, c1, fc = _info(inp)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("cycle has period 3 (2,5,0): the last entry 5 is dropped", period3),
    ("cycle has period 2 (2,5): the background-colored gap entry is dropped", period2),
    ("cycle colors 2 and 0 are swapped: 0,5,2,5", swapped),
    ("depth is counted one too high (cycle starts at its second entry)", offset_plus),
    ("depth is counted one too low (cycle starts at its last entry)", offset_minus),
    ("only the ring just inside the frame is colored 2; deeper cells stay", first_ring_only),
    ("whole inside is filled with 2", fill_all_two),
    ("the frame cells are also recolored to 2", frame_recolored),
    ("depth is the distance to the top or bottom side only", row_depth_only),
    ("the ring just inside the frame is left unpainted, deeper rings painted", first_ring_unpainted),
    ("the frame ring counts as depth 0 and the cycle paints it too", pad_one_more_ring),
    ("output is cropped to the frame's bounding box", crop_to_frame),
]


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/a3f84088.json')))
    pairs = task["train"]
    # sanity: the base cycle reproduces the true output
    for p in pairs:
        assert _paint(p["input"], CYCLE) == p["output"], "base cycle mismatch"
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                g = None
            if g is None:
                continue
            ok = (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))
            if ok and g != p["output"]:
                n += 1
        print(n, desc)
