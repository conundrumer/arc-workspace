import json
from pathlib import Path


def blocks(inp):
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
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            res.append((min(ys), min(xs), max(ys), max(xs), cells))
    return res


def crop(inp, b):
    r0, c0, r1, c1 = b[:4]
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def count(inp, b, colors):
    return sum(1 for y, x in b[4] if inp[y][x] in colors)


def pick(inp, key):
    bs = blocks(inp)
    return crop(inp, min(bs, key=key))


def most_marks(inp, out):
    bs = blocks(inp)
    return crop(inp, max(bs, key=lambda b: count(inp, b, (4, 6))))


def fewest_fours(inp, out):
    return pick(inp, lambda b: count(inp, b, (4,)))


def fewest_sixes(inp, out):
    return pick(inp, lambda b: count(inp, b, (6,)))


def largest_block(inp, out):
    return pick(inp, lambda b: -len(b[4]))


def smallest_block(inp, out):
    return pick(inp, lambda b: len(b[4]))


def lowest_density(inp, out):
    return pick(inp, lambda b: count(inp, b, (4, 6)) / len(b[4]))


def second_fewest(inp, out):
    bs = sorted(blocks(inp), key=lambda b: count(inp, b, (4, 6)))
    return crop(inp, bs[1]) if len(bs) > 1 else None


def padded_crop(inp, out):
    bs = blocks(inp)
    b = min(bs, key=lambda b: count(inp, b, (4, 6)))
    h, w = len(inp), len(inp[0])
    r0, c0, r1, c1 = b[:4]
    r0, c0, r1, c1 = max(r0 - 1, 0), max(c0 - 1, 0), min(r1 + 1, h - 1), min(c1 + 1, w - 1)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def trimmed_crop(inp, out):
    return [row[:-1] for row in out[:-1]]


def marks_erased(inp, out):
    return [[1 if v in (4, 6) else v for v in row] for row in out]


def swapped_marks(inp, out):
    m = {4: 6, 6: 4}
    return [[m.get(v, v) for v in row] for row in out]


def mirrored(inp, out):
    return [row[::-1] for row in out]


ALTERNATIVES = [
    ("pick the block with the most marked cells instead of the fewest", most_marks),
    ("count only color 4 as marks and pick the block with the fewest 4s", fewest_fours),
    ("count only color 6 as marks and pick the block with the fewest 6s", fewest_sixes),
    ("pick the largest block by cell count", largest_block),
    ("pick the smallest block by cell count", smallest_block),
    ("pick the block with the lowest mark share of its cells", lowest_density),
    ("pick the block with the second fewest marks", second_fewest),
    ("crop the chosen block with a one-cell border of background", padded_crop),
    ("crop the chosen block one row and one column short", trimmed_crop),
    ("crop the chosen block but paint its marks as body color", marks_erased),
    ("crop the chosen block with colors 4 and 6 swapped", swapped_marks),
    ("crop the chosen block mirrored left to right", mirrored),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/7bb29440.json'))
    pairs = task['train']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g) and g != p['output']:
                n += 1
        print(n, '/', len(pairs), desc)
