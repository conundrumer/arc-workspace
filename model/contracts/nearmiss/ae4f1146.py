import json
from collections import Counter
from pathlib import Path


def _blocks(inp):
    """Return list of (r0, c0, r1, c1) bounding boxes of 8-connected non-background components."""
    bg = Counter(v for row in inp for v in row).most_common(1)[0][0]
    h, w = len(inp), len(inp[0])
    seen = set()
    boxes = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] != bg:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            boxes.append((min(ys), min(xs), max(ys), max(xs)))
    boxes.sort()
    return bg, boxes


def _crop(inp, box):
    r0, c0, r1, c1 = box
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def _mark(inp, bg):
    cnt = Counter(v for row in inp for v in row if v != bg)
    return min(cnt, key=lambda k: (cnt[k], k))


def _score(inp, box, bg):
    m = _mark(inp, bg)
    return sum(v == m for row in _crop(inp, box) for v in row)


def _ranked(inp):
    bg, boxes = _blocks(inp)
    boxes = sorted(boxes, key=lambda b: -_score(inp, b, bg))
    return bg, boxes


def fewest(inp, out):
    bg, boxes = _ranked(inp)
    return _crop(inp, boxes[-1])


def second(inp, out):
    bg, boxes = _ranked(inp)
    return _crop(inp, boxes[1])


def first_block(inp, out):
    bg, boxes = _blocks(inp)
    return _crop(inp, boxes[0])


def last_block(inp, out):
    bg, boxes = _blocks(inp)
    return _crop(inp, boxes[-1])


def padded(inp, out):
    bg, boxes = _ranked(inp)
    r0, c0, r1, c1 = boxes[0]
    h, w = len(inp), len(inp[0])
    r0, c0, r1, c1 = max(r0 - 1, 0), max(c0 - 1, 0), min(r1 + 1, h - 1), min(c1 + 1, w - 1)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def top_left_2x2(inp, out):
    return [row[:2] for row in out[:2]]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def hflip(inp, out):
    return [row[::-1] for row in out]


def swap_colors(inp, out):
    a, b = sorted({v for row in out for v in row})[:2] if len({v for row in out for v in row}) > 1 else (None, None)
    return [[b if v == a else a if v == b else v for v in row] for row in out]


def mark_only(inp, out):
    bg = Counter(v for row in inp for v in row).most_common(1)[0][0]
    m = _mark(inp, bg)
    return [[v if v == m else bg for v in row] for row in out]


def most_by_largest_mark_cluster(inp, out):
    """Pick the block with the largest 4-connected cluster of mark cells."""
    bg, boxes = _blocks(inp)
    m = _mark(inp, bg)

    def cluster(box):
        g = _crop(inp, box)
        h, w = len(g), len(g[0])
        seen = set()
        best = 0
        for r in range(h):
            for c in range(w):
                if g[r][c] != m or (r, c) in seen:
                    continue
                st = [(r, c)]
                seen.add((r, c))
                n = 0
                while st:
                    y, x = st.pop()
                    n += 1
                    for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                        if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and g[ny][nx] == m:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                best = max(best, n)
        return best

    best = max(boxes, key=cluster)
    return _crop(inp, best)


ALTERNATIVES = [
    ("pick the block with the fewest mark cells instead of the most", fewest),
    ("pick the block with the second-most mark cells", second),
    ("pick the first block in reading order, ignoring counts", first_block),
    ("pick the last block in reading order, ignoring counts", last_block),
    ("crop the winning block with a one-cell margin of surrounding cells", padded),
    ("output only a 2x2 corner of the winning block (off-by-one size)", top_left_2x2),
    ("output the winning block transposed", transposed),
    ("output the winning block mirrored left-right", hflip),
    ("output the winning block with its two colors swapped", swap_colors),
    ("output only the mark cells of the winning block, other cells blanked to background", mark_only),
    ("pick the block with the largest connected cluster of mark cells instead of the most mark cells", most_by_largest_mark_cluster),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/ae4f1146.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
