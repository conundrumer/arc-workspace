import json
from pathlib import Path


def squares(inp):
    """Return list of dicts (r0, c0, r1, c1, holes, hole_groups) per 8-connected nonzero component."""
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
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            r0 = min(y for y, _ in cells); r1 = max(y for y, _ in cells)
            c0 = min(x for _, x in cells); c1 = max(x for _, x in cells)
            holes = {(y, x) for y in range(r0, r1 + 1) for x in range(c0, c1 + 1) if inp[y][x] == 0}
            groups = 0
            left = set(holes)
            while left:
                groups += 1
                st = [left.pop()]
                while st:
                    y, x = st.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        q = (y + dy, x + dx)
                        if q in left:
                            left.remove(q)
                            st.append(q)
            res.append(dict(r0=r0, c0=c0, r1=r1, c1=c1, holes=len(holes), groups=groups,
                            color=inp[cells[0][0]][cells[0][1]], ink=len(cells)))
    return res


def crop(inp, s, dr=0, dc=0, pad=0):
    h, w = len(inp), len(inp[0])
    return [[inp[y][x] if 0 <= y < h and 0 <= x < w else 0
             for x in range(s['c0'] + dc - pad, s['c1'] + dc + pad + 1)]
            for y in range(s['r0'] + dr - pad, s['r1'] + dr + pad + 1)]


def by_key(inp, key, pick):
    sq = squares(inp)
    vals = [key(s) for s in sq]
    t = pick(vals)
    return crop(inp, sq[vals.index(t)])


def most_holes(inp, out):
    return by_key(inp, lambda s: s['holes'], max)


def fewest_holes(inp, out):
    return by_key(inp, lambda s: s['holes'], min)


def top_left(inp, out):
    sq = squares(inp)
    return crop(inp, sq[0])


def bottom_right(inp, out):
    sq = squares(inp)
    return crop(inp, sq[-1])


def most_hole_groups(inp, out):
    return by_key(inp, lambda s: s['groups'], max)


def repeated_count(inp, out):
    # choose a square whose hole count is shared with another square
    sq = squares(inp)
    for s in sq:
        if sum(1 for t in sq if t['holes'] == s['holes']) > 1:
            return crop(inp, s)
    return None


def shifted_right(inp, out):
    sq = squares(inp)
    for s in sq:
        if crop(inp, s) == out:
            return crop(inp, s, dc=1)
    return None


def padded(inp, out):
    sq = squares(inp)
    for s in sq:
        if crop(inp, s) == out:
            return crop(inp, s, pad=1)
    return None


def holes_filled(inp, out):
    col = max(max(r) for r in out)
    return [[col] * len(out[0]) for _ in out]


def inverted(inp, out):
    col = max(max(r) for r in out)
    return [[0 if v else col for v in r] for r in out]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def flipped_lr(inp, out):
    return [r[::-1] for r in out]


def second_fewest(inp, out):
    sq = squares(inp)
    order = sorted(range(len(sq)), key=lambda i: (sq[i]['holes'], i))
    return crop(inp, sq[order[1]]) if len(order) > 1 else None


def next_square(inp, out):
    # off by one in the square list: the square after the right one
    sq = squares(inp)
    for i, s in enumerate(sq):
        if crop(inp, s) == out:
            return crop(inp, sq[(i + 1) % len(sq)])
    return None


ALTERNATIVES = [
    ("pick the square with the most holes", most_holes),
    ("pick the square with the fewest holes", fewest_holes),
    ("pick the first square in reading order", top_left),
    ("pick the last square in reading order", bottom_right),
    ("pick the square with the most separate hole groups", most_hole_groups),
    ("pick a square whose hole count is shared with another square", repeated_count),
    ("crop the right square but offset one column to the right", shifted_right),
    ("crop the right square with a one-cell margin (size 7)", padded),
    ("right square with every hole filled in", holes_filled),
    ("right square with ink and holes swapped", inverted),
    ("right square transposed", transposed),
    ("right square mirrored left-right", flipped_lr),
    ("pick the square with the second-fewest holes", second_fewest),
    ("pick the square after the right one in reading order", next_square),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/358ba94e.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
