import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _bbox(inp, cells=None):
    bg = _bg(inp)
    pts = [(i, j) for i, r in enumerate(inp) for j, c in enumerate(r)
           if c != bg and (cells is None or c in cells)]
    return (min(p[0] for p in pts), max(p[0] for p in pts),
            min(p[1] for p in pts), max(p[1] for p in pts))


def _crop(inp, r0, r1, c0, c1, fill=None):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    g = []
    for i in range(r0, r1 + 1):
        row = []
        for j in range(c0, c1 + 1):
            row.append(inp[i][j] if 0 <= i < h and 0 <= j < w else bg)
        g.append(row)
    return g


def _hflip(g):
    return [r[::-1] for r in g]


def _vflip(g):
    return g[::-1]


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _crop_bbox(inp):
    return _crop(inp, *_bbox(inp))


def unflipped_crop(inp, out):
    return _crop_bbox(inp)


def vertical_flip(inp, out):
    return _vflip(_crop_bbox(inp))


def rotate_180(inp, out):
    return _vflip(_hflip(_crop_bbox(inp)))


def transpose(inp, out):
    return _transpose(_crop_bbox(inp))


def rotate_90_cw(inp, out):
    return _hflip(_transpose(_crop_bbox(inp)))


def margin_one(inp, out):
    r0, r1, c0, c1 = _bbox(inp)
    return _hflip(_crop(inp, r0 - 1, r1 + 1, c0 - 1, c1 + 1))


def drop_last_column(inp, out):
    r0, r1, c0, c1 = _bbox(inp)
    return _hflip(_crop(inp, r0, r1, c0, c1 - 1))


def drop_first_row(inp, out):
    r0, r1, c0, c1 = _bbox(inp)
    return _hflip(_crop(inp, r0 + 1, r1, c0, c1))


def flip_whole_grid(inp, out):
    return _hflip(inp)


def bbox_of_minor_color_only(inp, out):
    bg = _bg(inp)
    cnt = Counter(c for r in inp for c in r if c != bg)
    minor = min(cnt, key=lambda c: cnt[c])
    return _hflip(_crop(inp, *_bbox(inp, {minor})))


def background_zeroed(inp, out):
    bg = _bg(inp)
    shape = [[c if c != bg else 0 for c in r] for r in out]
    # cells of the dominant object color are erased, only the accent remains
    obj = Counter(c for r in out for c in r).most_common(1)[0][0]
    return [[0 if c == obj else c for c in r] for r in out] if shape else None


def swapped_colors(inp, out):
    cols = sorted(set(c for r in out for c in r))
    if len(cols) != 2:
        return None
    a, b = cols
    return [[b if c == a else a for c in r] for r in out]


ALTERNATIVES = [
    ("crop the bounding box without flipping", unflipped_crop),
    ("crop the bounding box and flip it vertically", vertical_flip),
    ("crop the bounding box and rotate it 180 degrees", rotate_180),
    ("crop the bounding box and transpose it", transpose),
    ("crop the bounding box and rotate it 90 degrees clockwise", rotate_90_cw),
    ("bounding box with a one-cell margin, flipped horizontally", margin_one),
    ("bounding box one column too narrow, flipped horizontally", drop_last_column),
    ("bounding box one row too short, flipped horizontally", drop_first_row),
    ("flip the whole input grid horizontally without cropping", flip_whole_grid),
    ("bounding box of the less frequent color only, flipped horizontally", bbox_of_minor_color_only),
    ("correct output with the object's main color erased to 0", background_zeroed),
    ("correct output with its two colors swapped", swapped_colors),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/7468f01a.json'))
    train = task['train']
    print('pairs', len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(f'{n}/{len(train)}  {desc}')
