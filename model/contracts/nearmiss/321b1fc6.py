from pathlib import Path
import json

BLANK = 8


def parts(inp):
    h, w = len(inp), len(inp[0])
    tmpl = [(r, c, inp[r][c]) for r in range(h) for c in range(w) if inp[r][c] not in (0, BLANK)]
    seen = set()
    blocks = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == BLANK and (r, c) not in seen:
                comp, st = [], [(r, c)]
                seen.add((r, c))
                while st:
                    y, x = st.pop()
                    comp.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == BLANK and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                blocks.append(sorted(comp))
    blocks.sort(key=lambda b: b[0])
    return tmpl, blocks


def origin(cells):
    return min(c[0] for c in cells), min(c[1] for c in cells)


def build(inp, erase_tmpl=True, erase_blocks=True, paint=None, transform=None, anchor=None):
    """paint: indices of blocks to paint (None = all)."""
    h, w = len(inp), len(inp[0])
    tmpl, blocks = parts(inp)
    g = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v == BLANK and erase_blocks:
                v = 0
            g[r][c] = v
    if erase_tmpl:
        for r, c, _ in tmpl:
            g[r][c] = 0
    tr, tc = origin(tmpl)
    rel = [(r - tr, c - tc, v) for r, c, v in tmpl]
    if transform:
        rel = transform(rel)
    for i, b in enumerate(blocks):
        if paint is not None and i not in paint:
            continue
        br, bc = origin(b) if anchor is None else anchor(b, (tr, tc))
        for dr, dc, v in rel:
            y, x = br + dr, bc + dc
            if 0 <= y < h and 0 <= x < w:
                g[y][x] = v
    return g


def keep_template(inp, out):
    return build(inp, erase_tmpl=False)


def keep_blocks(inp, out):
    return build(inp, paint=[])


def no_erase_template_but_nothing_painted(inp, out):
    return build(inp, erase_tmpl=False, paint=[])


def first_block_only(inp, out):
    return build(inp, paint=[0])


def last_block_only(inp, out):
    _, blocks = parts(inp)
    return build(inp, paint=[len(blocks) - 1])


def mirror(rel):
    w = max(c for _, c, _ in rel)
    return [(r, w - c, v) for r, c, v in rel]


def transpose(rel):
    return [(c, r, v) for r, c, v in rel]


def rot180(rel):
    h = max(r for r, _, _ in rel)
    w = max(c for _, c, _ in rel)
    return [(h - r, w - c, v) for r, c, v in rel]


def mirrored(inp, out):
    return build(inp, transform=mirror)


def transposed(inp, out):
    return build(inp, transform=transpose)


def rotated(inp, out):
    return build(inp, transform=rot180)


def shifted_right(inp, out):
    return build(inp, anchor=lambda b, t: (origin(b)[0], origin(b)[1] + 1))


def absolute_offset(inp, out):
    return build(inp, anchor=lambda b, t: (origin(b)[0] + t[0], origin(b)[1] + t[1]))


def solid_fill(inp, out):
    h, w = len(inp), len(inp[0])
    tmpl, blocks = parts(inp)
    col = min(tmpl)[2]
    g = build(inp, paint=[])
    for b in blocks:
        for y, x in b:
            g[y][x] = col
    return g


ALTERNATIVES = [
    ("template left in place and also copied onto blocks", keep_template),
    ("template erased but blocks are not replaced and stay color 8", keep_blocks),
    ("blocks erased to background and template left in place, nothing copied", no_erase_template_but_nothing_painted),
    ("template copied only onto the first block in reading order, other blocks erased", first_block_only),
    ("template copied only onto the last block in reading order, other blocks erased", last_block_only),
    ("template copied mirrored left-right", mirrored),
    ("template copied transposed", transposed),
    ("template copied rotated 180 degrees", rotated),
    ("template copied one column right of the block's top-left corner", shifted_right),
    ("template copied at block corner plus the template's own absolute position", absolute_offset),
    ("each block filled solid with the template's top-left color", solid_fill),
]


def valid(g, truth):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
        and g != truth
    )


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/321b1fc6.json')))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
