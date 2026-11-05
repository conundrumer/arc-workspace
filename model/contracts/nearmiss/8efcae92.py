import json
from collections import Counter
from pathlib import Path


def _comps(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0 and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            res.append(cells)
    return res


def _box(cells):
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return min(ys), max(ys), min(xs), max(xs)


def _crop(inp, b, pad=0):
    r0, r1, c0, c1 = b
    h, w = len(inp), len(inp[0])
    r0, c0 = max(0, r0 - pad), max(0, c0 - pad)
    r1, c1 = min(h - 1, r1 + pad), min(w - 1, c1 + pad)
    if r1 < r0 or c1 < c0:
        return None
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def _marks(inp, cells):
    cnt = Counter(v for row in inp for v in row if v != 0)
    mark = min(cnt, key=lambda k: (cnt[k], k))
    return sum(1 for y, x in cells if inp[y][x] == mark)


def _ranked(inp, key):
    cs = _comps(inp)
    return sorted(cs, key=lambda cells: (key(inp, cells), -_box(cells)[0], -_box(cells)[2]))


def _pick(inp, key, idx):
    cs = _ranked(inp, key)
    if len(cs) <= abs(idx) - (1 if idx < 0 else 0):
        return None
    return cs[idx]


def fewest_marks(inp, out):
    return _crop(inp, _box(_pick(inp, _marks, 0)))


def largest_area(inp, out):
    return _crop(inp, _box(_pick(inp, lambda i, c: len(c), -1)))


def smallest_area(inp, out):
    return _crop(inp, _box(_pick(inp, lambda i, c: len(c), 0)))


def first_in_reading_order(inp, out):
    cs = _comps(inp)
    return _crop(inp, _box(min(cs, key=lambda c: (_box(c)[0], _box(c)[2]))))


def second_most_marks(inp, out):
    c = _pick(inp, _marks, -2)
    return _crop(inp, _box(c)) if c else None


def padded_by_one(inp, out):
    cs = _comps(inp)
    w = max(cs, key=lambda c: _marks(inp, c))
    return _crop(inp, _box(w), pad=1)


def trimmed_by_one(inp, out):
    cs = _comps(inp)
    w = max(cs, key=lambda c: _marks(inp, c))
    r0, r1, c0, c1 = _box(w)
    return _crop(inp, (r0 + 1, r1 - 1, c0 + 1, c1 - 1))


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def mirrored(inp, out):
    return [row[::-1] for row in out]


def marks_erased(inp, out):
    cnt = Counter(v for row in inp for v in row if v != 0)
    mark = min(cnt, key=lambda k: (cnt[k], k))
    body = Counter(v for row in out for v in row if v != mark).most_common(1)[0][0]
    return [[body if v == mark else v for v in row] for row in out]


def most_cells_of_body_color(inp, out):
    # picks the rectangle with most cells of the commonest color, not of the rarest
    cnt = Counter(v for row in inp for v in row if v != 0)
    body = cnt.most_common(1)[0][0]
    cs = _comps(inp)
    w = max(cs, key=lambda c: (sum(1 for y, x in c if inp[y][x] == body), -_box(c)[0]))
    return _crop(inp, _box(w))


def without_last_row(inp, out):
    return out[:-1] if len(out) > 1 else None


def whole_grid_with_winner_only(inp, out):
    cs = _comps(inp)
    w = max(cs, key=lambda c: _marks(inp, c))
    keep = set(w)
    return [[inp[y][x] if (y, x) in keep else 0 for x in range(len(inp[0]))] for y in range(len(inp))]


ALTERNATIVES = [
    ("rectangle with the fewest rare-color cells instead of the most", fewest_marks),
    ("largest rectangle by area", largest_area),
    ("smallest rectangle by area", smallest_area),
    ("first rectangle in reading order", first_in_reading_order),
    ("rectangle with the second most rare-color cells", second_most_marks),
    ("crop with a one-cell border around the rectangle", padded_by_one),
    ("crop with one cell trimmed from each edge", trimmed_by_one),
    ("correct crop, transposed", transposed),
    ("correct crop, mirrored left to right", mirrored),
    ("correct crop with rare-color cells replaced by the body color", marks_erased),
    ("rectangle with the most cells of the commonest color", most_cells_of_body_color),
    ("winner kept in place, rest of the grid cleared (no crop)", whole_grid_with_winner_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/8efcae92.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
