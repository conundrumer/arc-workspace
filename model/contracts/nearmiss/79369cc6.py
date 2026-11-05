"""Near-miss readings for ARC task 79369cc6."""
import json
from collections import Counter
from pathlib import Path

ROT = [lambda r, c: (r, c), lambda r, c: (c, -r), lambda r, c: (-r, -c), lambda r, c: (-c, r)]
REF = [lambda r, c: (r, -c), lambda r, c: (-r, c), lambda r, c: (c, r), lambda r, c: (-c, -r)]
ALL_D = ROT + REF


def _template(inp):
    cnt = Counter(v for row in inp for v in row)
    fill = min(cnt, key=lambda k: (cnt[k], k))
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == fill]
    r0 = min(r for r, c in cells); r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells); c1 = max(c for r, c in cells)
    box = {(r - r0, c - c0): inp[r][c] for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}
    cols = {v for v in box.values() if v != fill}
    mark = Counter(box.values())
    mark = max(cols, key=lambda k: mark[k]) if cols else None
    return fill, mark, box


def _occurrences(inp, ds=ALL_D, block=True):
    """List of (M, d, fill_positions, mark_positions) for each match."""
    fill, mark, box = _template(inp)
    h, w = len(inp), len(inp[0])
    marks_all = {(r, c) for r in range(h) for c in range(w) if inp[r][c] == mark}
    res = []
    for d in ds:
        img = {d(r, c): v for (r, c), v in box.items()}
        mk = [p for p, v in img.items() if v == mark]
        fl = [p for p, v in img.items() if v == fill]
        for r in range(-3, h + 3):
            for c in range(-3, w + 3):
                if all((r + a, c + b) in marks_all for a, b in mk):
                    fp = [(r + a, c + b) for a, b in fl]
                    if block and any(p in marks_all for p in fp):
                        continue
                    res.append(((r, c), d, fp, [(r + a, c + b) for a, b in mk], [(r + a, c + b) for a, b in img]))
    return res


def _paint(inp, positions, color):
    g = [row[:] for row in inp]
    for r, c in positions:
        if 0 <= r < len(g) and 0 <= c < len(g[0]):
            g[r][c] = color
    return g


def _solve(inp, ds=ALL_D, block=True):
    fill, _, _ = _template(inp)
    pos = set()
    for _, _, fp, _, _ in _occurrences(inp, ds, block):
        pos.update(fp)
    return _paint(inp, pos, fill)


def _changed(inp, out):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if out[r][c] != v]


def identity_only(inp, out):
    return _solve(inp, ROT[:1])


def reflections_only(inp, out):
    return _solve(inp, ROT[:1] + REF)


def rot180_only(inp, out):
    return _solve(inp, ROT[:1] + ROT[2:3])


def background_targets_only(inp, out):
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    fill, _, _ = _template(inp)
    pos = set()
    for _, _, fp, _, _ in _occurrences(inp):
        if all(not (0 <= r < len(inp) and 0 <= c < len(inp[0])) or inp[r][c] == bg for r, c in fp):
            pos.update(fp)
    return _paint(inp, pos, fill)


def whole_box(inp, out):
    fill, _, _ = _template(inp)
    pos = set()
    for _, _, _, _, allp in _occurrences(inp):
        pos.update(allp)
    return _paint(inp, pos, fill)


def mark_color_paint(inp, out):
    fill, mark, _ = _template(inp)
    return _paint(inp, _changed(inp, out), mark)


def background_paint(inp, out):
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    return _paint(inp, _changed(inp, out), bg)


def shifted_right(inp, out):
    ch = _changed(inp, out)
    fill, _, _ = _template(inp)
    g = [row[:] for row in inp]
    return _paint(g, [(r, c + 1) for r, c in ch], fill)


def first_match_only(inp, out):
    fill, _, _ = _template(inp)
    for _, _, fp, _, _ in sorted(_occurrences(inp), key=lambda o: o[0]):
        g = _paint(inp, fp, fill)
        if g != inp:
            return g
    return None


def only_blank_cells(inp, out):
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    g = [row[:] for row in out]
    for r, c in _changed(inp, out):
        if inp[r][c] != bg:
            g[r][c] = inp[r][c]
    return g


def mark_cells_painted(inp, out):
    fill, _, _ = _template(inp)
    pos = set()
    for _, _, _, mp, _ in _occurrences(inp):
        pos.update(mp)
    return _paint(inp, pos, fill)


def drop_last_stamp(inp, out):
    fill, _, _ = _template(inp)
    stamps = []
    for _, _, fp, _, _ in sorted(_occurrences(inp), key=lambda o: o[0]):
        if _paint(inp, fp, fill) != inp and set(fp) not in stamps:
            stamps.append(set(fp))
    if len(stamps) < 2:
        return None
    pos = {p for fp in stamps[:-1] for p in fp}
    return _paint(inp, pos, fill)


ALTERNATIVES = [
    ("Match the template only in its original orientation, no rotations or reflections", identity_only),
    ("Match reflections of the template but not 90 or 270 degree rotations", reflections_only),
    ("Match only the original and the 180 degree rotation of the template", rot180_only),
    ("Stamp only where every target cell is background-colored", background_targets_only),
    ("Fill the whole template box at each match instead of only the fill cells", whole_box),
    ("Paint the stamps with the mark color instead of the fill color", mark_color_paint),
    ("Paint the stamps with the background color instead of the fill color", background_paint),
    ("Place each stamp one column to the right of its match", shifted_right),
    ("Stamp only the first match in reading order", first_match_only),
    ("Fill only background-colored cells and keep other colors under a stamp", only_blank_cells),
    ("Paint the matched mark cells instead of the complementary fill cells", mark_cells_painted),
    ("Stamp every match except the last one in reading order", drop_last_stamp),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) and r for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/79369cc6.json"))
    pairs = task["train"]
    # sanity: the full solver reproduces the true output
    print("solver check:", [_solve(p["input"]) == p["output"] for p in pairs])
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
