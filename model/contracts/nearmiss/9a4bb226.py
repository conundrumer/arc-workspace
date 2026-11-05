import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _blocks(inp):
    """Return list of blocks (r0, c0, r1, c1, cells) in reading order of first cell."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
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
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != bg and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            rs = [p[0] for p in cells]
            cs = [p[1] for p in cells]
            res.append((min(rs), min(cs), max(rs), max(cs), cells))
    return res


def _ncolors(inp, b):
    return len({inp[y][x] for y, x in b[4]})


def _crop(inp, b, pad=0, dr=0, dc=0):
    h, w = len(inp), len(inp[0])
    out = []
    for y in range(b[0] - pad + dr, b[2] + pad + 1 + dr):
        row = []
        for x in range(b[1] - pad + dc, b[3] + pad + 1 + dc):
            row.append(inp[y][x] if 0 <= y < h and 0 <= x < w else 0)
        out.append(row)
    return out


def _target(inp):
    bs = _blocks(inp)
    return max(bs, key=lambda b: _ncolors(inp, b))


def fewest_first(inp, out):
    bs = _blocks(inp)
    m = min(_ncolors(inp, b) for b in bs)
    return _crop(inp, [b for b in bs if _ncolors(inp, b) == m][0])


def fewest_last(inp, out):
    bs = _blocks(inp)
    m = min(_ncolors(inp, b) for b in bs)
    return _crop(inp, [b for b in bs if _ncolors(inp, b) == m][-1])


def first_block(inp, out):
    return _crop(inp, _blocks(inp)[0])


def last_block(inp, out):
    return _crop(inp, _blocks(inp)[-1])


def padded_crop(inp, out):
    return _crop(inp, _target(inp), pad=1)


def drop_last_row_col(inp, out):
    return [r[:-1] for r in out[:-1]]


def shifted_window(inp, out):
    return _crop(inp, _target(inp), dc=1)


def in_place_only_target(inp, out):
    bg = _bg(inp)
    t = _target(inp)
    keep = set(t[4])
    return [[inp[y][x] if (y, x) in keep else bg for x in range(len(inp[0]))] for y in range(len(inp))]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def mirrored(inp, out):
    return [r[::-1] for r in out]


def most_frequent_color_block(inp, out):
    bs = _blocks(inp)

    def peak(b):
        return max(Counter(inp[y][x] for y, x in b[4]).values())
    return _crop(inp, max(bs, key=peak))


def majority_only(inp, out):
    maj = Counter(v for r in out for v in r).most_common(1)[0][0]
    return [[v if v == maj else 0 for v in r] for r in out]


def global_rarest_color_block(inp, out):
    bg = _bg(inp)
    cnt = Counter(v for r in inp for v in r if v != bg)
    bs = _blocks(inp)

    def rare(b):
        return min(cnt[inp[y][x]] for y, x in b[4])
    return _crop(inp, min(bs, key=rare))


ALTERNATIVES = [
    ("pick the first block with the fewest colors instead of the most", fewest_first),
    ("pick the last block with the fewest colors instead of the most", fewest_last),
    ("pick the first block in reading order, ignoring color counts", first_block),
    ("pick the last block in reading order, ignoring color counts", last_block),
    ("crop the 3-color block with a 1-cell background margin", padded_crop),
    ("crop one row and column too few, dropping the last row and column", drop_last_row_col),
    ("crop window offset one column to the right of the 3-color block", shifted_window),
    ("keep only the 3-color block at its input position, erase the rest", in_place_only_target),
    ("output transposed", transposed),
    ("output mirrored left to right", mirrored),
    ("pick the block whose most frequent color has the largest count", most_frequent_color_block),
    ("keep only the majority color of the block, others set to background", majority_only),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/9a4bb226.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, e)
                g = None
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
