import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _cells(inp):
    bg = _bg(inp)
    d = {}
    for i, r in enumerate(inp):
        for j, v in enumerate(r):
            if v != bg:
                d.setdefault(v, []).append((i, j))
    return d


def _bbox(cs):
    rs = [c[0] for c in cs]
    cs2 = [c[1] for c in cs]
    return min(rs), min(cs2), max(rs), max(cs2)


def _is_ring(cs):
    r0, c0, r1, c1 = _bbox(cs)
    if r1 - r0 != 2 or c1 - c0 != 2 or len(cs) != 8:
        return False
    return (r0 + 1, c0 + 1) not in cs


def _parts(inp):
    d = _cells(inp)
    rings = {c: _bbox(cs) for c, cs in d.items() if _is_ring(cs)}
    frame = [c for c in d if c not in rings]
    if len(frame) != 1:
        return None
    return d, rings, frame[0]


def _crop(inp, box, margin=0):
    r0, c0, r1, c1 = box
    h, w = len(inp), len(inp[0])
    return [row[max(0, c0 - margin):min(w, c1 + margin + 1)]
            for row in inp[max(0, r0 - margin):min(h, r1 + margin + 1)]]


def _selected(inp):
    p = _parts(inp)
    d, rings, fc = p
    fr0, fc0, fr1, fc1 = _bbox(d[fc])
    for c, (r0, c0, r1, c1) in rings.items():
        if r0 > fr0 and c0 > fc0 and r1 < fr1 and c1 < fc1:
            return c
    return None


def _others(inp):
    d, rings, fc = _parts(inp)
    s = _selected(inp)
    return [(c, b) for c, b in rings.items() if c != s]


def wrong_ring_first(inp, out):
    o = sorted(_others(inp), key=lambda x: (x[1][0], x[1][1]))
    return _crop(inp, o[0][1])


def wrong_ring_last(inp, out):
    o = sorted(_others(inp), key=lambda x: (x[1][0], x[1][1]))
    return _crop(inp, o[-1][1])


def wrong_ring_center(inp, out):
    h, w = len(inp), len(inp[0])
    o = _others(inp)
    best = min(o, key=lambda x: abs(x[1][0] + 1 - (h - 1) / 2) + abs(x[1][1] + 1 - (w - 1) / 2))
    return _crop(inp, best[1])


def wrong_ring_nearest_frame(inp, out):
    d, rings, fc = _parts(inp)
    fcells = d[fc]
    def dist(b):
        r0, c0, r1, c1 = b
        return min(max(r0 - i, 0, i - r1) + max(c0 - j, 0, j - c1) for i, j in fcells)
    best = min(_others(inp), key=lambda x: dist(x[1]))
    return _crop(inp, best[1])


def filled_hole(inp, out):
    g = [r[:] for r in out]
    g[1][1] = g[0][0]
    return g


def hole_frame_color(inp, out):
    g = [r[:] for r in out]
    g[1][1] = _parts(inp)[2]
    return g


def ring_in_frame_color(inp, out):
    fc = _parts(inp)[2]
    return [[fc if v == out[0][0] else v for v in r] for r in out]


def margin_crop(inp, out):
    c = _selected(inp)
    return _crop(inp, _parts(inp)[1][c], margin=1)


def frame_bbox_crop(inp, out):
    d, rings, fc = _parts(inp)
    return _crop(inp, _bbox(d[fc]))


def corners_dropped(inp, out):
    g = [r[:] for r in out]
    bg = out[1][1]
    for i, j in ((0, 0), (0, 2), (2, 0), (2, 2)):
        g[i][j] = bg
    return g


def only_selected_uncropped(inp, out):
    d, rings, fc = _parts(inp)
    c = _selected(inp)
    bg = _bg(inp)
    return [[v if v == c else bg for v in r] for r in inp]


def short_crop(inp, out):
    c = _selected(inp)
    r0, c0, r1, c1 = _parts(inp)[1][c]
    return _crop(inp, (r0, c0, r1 - 1, c1 - 1))


ALTERNATIVES = [
    ("crops the first outside ring in reading order instead of the ring inside the frame", wrong_ring_first),
    ("crops the last outside ring in reading order instead of the ring inside the frame", wrong_ring_last),
    ("crops the outside ring nearest the grid center", wrong_ring_center),
    ("crops the outside ring nearest to any frame-colored cell", wrong_ring_nearest_frame),
    ("fills the ring's hole with the ring color", filled_hole),
    ("fills the ring's hole with the frame color", hole_frame_color),
    ("draws the ring in the frame color", ring_in_frame_color),
    ("crops the ring with a one-cell margin on each side", margin_crop),
    ("crops the bounding box of the frame-colored cells", frame_bbox_crop),
    ("drops the ring's four corner cells", corners_dropped),
    ("keeps only the selected ring at full grid size, no crop", only_selected_uncropped),
    ("crops the selected ring one row and column short", short_crop),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/bf699163.json').read_text())
    train = task['train']
    print(len(ALTERNATIVES), 'readings,', len(train), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p['input'], p['output'])
            except Exception as e:
                print('  error', fn.__name__, e)
                g = None
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
