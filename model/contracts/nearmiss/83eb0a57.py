import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(c for r in g for c in r).most_common(1)[0][0]


def _components(g):
    bg = _bg(g)
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    for i in range(h):
        for j in range(w):
            if g[i][j] == bg or (i, j) in seen:
                continue
            stack = [(i, j)]
            seen.add((i, j))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h and 0 <= nx < w and g[ny][nx] != bg
                                and (ny, nx) not in seen):
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            comps.append(cells)
    return comps


def _bbox(cells):
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return min(ys), min(xs), max(ys), max(xs)


def _crop(g, box):
    y0, x0, y1, x1 = box
    return [r[x0:x1 + 1] for r in g[y0:y1 + 1]]


def _largest(inp):
    return max(_components(inp), key=len)


def _smallest(inp):
    return min(_components(inp), key=len)


def crop_largest_only(inp, out):
    return _crop(inp, _bbox(_largest(inp)))


def crop_margin(inp, out):
    y0, x0, y1, x1 = _bbox(_largest(inp))
    h, w = len(inp), len(inp[0])
    y0, x0, y1, x1 = max(0, y0 - 1), max(0, x0 - 1), min(h - 1, y1 + 1), min(w - 1, x1 + 1)
    return _crop(inp, (y0, x0, y1, x1))


def crop_smallest(inp, out):
    return _crop(inp, _bbox(_smallest(inp)))


def unchanged(inp, out):
    return [r[:] for r in inp]


def body_to_bg(inp, out):
    body = _bg(out)
    bg = _bg(inp)
    return [[bg if c == body else c for c in r] for r in out]


def body_to_overlay_color(inp, out):
    cnt = Counter(c for r in out for c in r).most_common()
    if len(cnt) < 2:
        return None
    body, other = cnt[0][0], cnt[1][0]
    return [[other if c == body else c for c in r] for r in out]


def flip_vertical(inp, out):
    return out[::-1]


def transpose(inp, out):
    return [list(r) for r in zip(*out)]


def drop_last_row_col(inp, out):
    return [r[:-1] for r in out[:-1]]


def marks_erased(inp, out):
    g = _crop(inp, _bbox(_largest(inp)))
    body = _bg(g)
    return [[body] * len(r) for r in g]


def overlay_at_corner(inp, out):
    comps = _components(inp)
    big = max(comps, key=len)
    g = _crop(inp, _bbox(big))
    g = [r[:] for r in g]
    for comp in comps:
        if comp is big:
            continue
        y0, x0, y1, x1 = _bbox(comp)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if y - y0 < len(g) and x - x0 < len(g[0]):
                    g[y - y0][x - x0] = inp[y][x]
    return g


ALTERNATIVES = [
    ("crop the largest rectangle only, ignore the smaller rectangles", crop_largest_only),
    ("crop the largest rectangle with a one-cell margin of background", crop_margin),
    ("crop the smallest rectangle as the canvas", crop_smallest),
    ("return the input unchanged", unchanged),
    ("canvas body left as the input background color", body_to_bg),
    ("canvas body takes the overlay body color", body_to_overlay_color),
    ("output flipped top to bottom", flip_vertical),
    ("output transposed", transpose),
    ("crop one row and one column short", drop_last_row_col),
    ("largest rectangle's marks filled with its body color, no overlay", marks_erased),
    ("smaller rectangles pasted raw at the crop's top-left corner", overlay_at_corner),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/83eb0a57.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
