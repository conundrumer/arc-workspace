"""Near-miss readings for ARC task 447fd412.

Rule: a template (cells of the rarest color, with end marks of the other
color) is copied and scaled so that its marks land on blocks of the mark
color; the scale is the block side.
"""
import json
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    counts = {}
    for row in inp:
        for v in row:
            if v:
                counts[v] = counts.get(v, 0) + 1
    ink = min(counts, key=lambda c: (counts[c], c))
    seen, comps = set(), []
    for r in range(h):
        for c in range(w):
            if inp[r][c] and (r, c) not in seen:
                stack, comp = [(r, c)], []
                seen.add((r, c))
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = y + dy, x + dx
                            if (0 <= ny < h and 0 <= nx < w and inp[ny][nx]
                                    and (ny, nx) not in seen):
                                seen.add((ny, nx))
                                stack.append((ny, nx))
                comps.append(comp)
    tmpl = next(c for c in comps if any(inp[y][x] == ink for y, x in c))
    blocks = []
    for comp in comps:
        if comp is tmpl:
            continue
        ys = [p[0] for p in comp]
        xs = [p[1] for p in comp]
        blocks.append((min(ys), min(xs), max(ys) - min(ys) + 1,
                       max(xs) - min(xs) + 1, comp))
    mark = [c for c in counts if c != ink][0]
    inks = sorted(p for p in tmpl if inp[p[0]][p[1]] == ink)
    marks = sorted(p for p in tmpl if inp[p[0]][p[1]] == mark)
    k = blocks[0][2]
    tops = {(b[0], b[1]) for b in blocks}
    m0 = marks[0]
    places = []
    for (r0, c0) in sorted(tops):
        if all((r0 + k * (mr - m0[0]), c0 + k * (mc - m0[1])) in tops
               for mr, mc in marks):
            places.append((r0, c0))
    return dict(ink=ink, mark=mark, tmpl=tmpl, inks=inks, marks=marks,
                blocks=blocks, k=k, m0=m0, places=places)


def _render(inp, tf=lambda d: d, kr=None, kc=None, k=None, places=None,
            color=None):
    P = _parse(inp)
    k = P["k"] if k is None else k
    kr = k if kr is None else kr
    kc = k if kc is None else kc
    places = P["places"] if places is None else places
    color = P["ink"] if color is None else color
    g = [row[:] for row in inp]
    h, w = len(inp), len(inp[0])
    m0r, m0c = P["m0"]
    for r0, c0 in places:
        for r, c in P["inks"]:
            dr, dc = tf((r - m0r, c - m0c))
            for y in range(r0 + kr * dr, r0 + kr * dr + kr):
                for x in range(c0 + kc * dc, c0 + kc * dc + kc):
                    if 0 <= y < h and 0 <= x < w and inp[y][x] == 0:
                        g[y][x] = color
    return g


def correct(inp, out):
    return _render(inp)


def unchanged(inp, out):
    return [row[:] for row in inp]


def scale_one(inp, out):
    return _render(inp, k=1)


def scale_plus_one(inp, out):
    return _render(inp, k=_parse(inp)["k"] + 1)


def mark_color(inp, out):
    P = _parse(inp)
    return _render(inp, color=P["mark"])


def first_only(inp, out):
    P = _parse(inp)
    if len(P["places"]) < 2:
        return None
    return _render(inp, places=P["places"][:1])


def rotated_180(inp, out):
    return _render(inp, tf=lambda d: (-d[0], -d[1]))


def transposed(inp, out):
    return _render(inp, tf=lambda d: (d[1], d[0]))


def erase_template(inp, out):
    P = _parse(inp)
    g = [row[:] for row in out]
    for y, x in P["tmpl"]:
        g[y][x] = 0
    return g


def erase_blocks(inp, out):
    P = _parse(inp)
    g = [row[:] for row in out]
    for b in P["blocks"]:
        for y, x in b[4]:
            g[y][x] = 0
    return g


def shifted_right(inp, out):
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for y in range(h):
        for x in range(w):
            if out[y][x] != inp[y][x] and x + 1 < w and inp[y][x + 1] == 0:
                g[y][x + 1] = out[y][x]
    return g


def stretch_columns_only(inp, out):
    return _render(inp, kr=1)


def fill_bbox(inp, out):
    h, w = len(inp), len(inp[0])
    cells = [(y, x) for y in range(h) for x in range(w)
             if out[y][x] != inp[y][x]]
    ys = [p[0] for p in cells]
    xs = [p[1] for p in cells]
    g = [row[:] for row in out]
    for y in range(min(ys), max(ys) + 1):
        for x in range(min(xs), max(xs) + 1):
            if g[y][x] == 0:
                g[y][x] = _parse(inp)["ink"]
    return g


ALTERNATIVES = [
    ("No copy is made: the input is returned unchanged", unchanged),
    ("The copy is not scaled (scale 1) and hangs from the first block", scale_one),
    ("The scale is one more than the block side", scale_plus_one),
    ("The copy is drawn in the block color instead of the drawing color", mark_color),
    ("Only the first placement of the template is drawn", first_only),
    ("The copy is turned 180 degrees about the first mark", rotated_180),
    ("The copy is transposed (rows and columns swapped) about the first mark", transposed),
    ("The template is moved, not copied: the original drawing is erased", erase_template),
    ("The blocks are removed and only the copies remain", erase_blocks),
    ("The copy is shifted one cell to the right", shifted_right),
    ("The copy is stretched by the scale across columns only", stretch_columns_only),
    ("The empty cells inside the copy's bounding box are also filled", fill_bbox),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/447fd412.json"))
    pairs = task["train"]
    print("solver check:", [correct(p["input"], p["output"]) == p["output"] for p in pairs])

    def ok(g, out):
        return (g is not None and len(g) > 0 and len({len(r) for r in g}) == 1
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                and g != out)

    for desc, fn in ALTERNATIVES:
        n = sum(ok(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
