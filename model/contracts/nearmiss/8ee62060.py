from pathlib import Path
import json


def blocks(g, b):
    n, m = len(g), len(g[0])
    if n % b or m % b:
        return None
    return [[[row[c:c + b] for row in g[r:r + b]] for c in range(0, m, b)]
            for r in range(0, n, b)]


def unblocks(bg):
    out = []
    for brow in bg:
        b = len(brow[0])
        for i in range(b):
            out.append([v for blk in brow for v in blk[i]])
    return out


def hflip(g):
    return [r[::-1] for r in g]


def vflip(g):
    return g[::-1]


def transpose(g):
    return [list(r) for r in zip(*g)]


def block_map(inp, b, pos, content=lambda x: x):
    bg = blocks(inp, b)
    if bg is None:
        return None
    nr, nc = len(bg), len(bg[0])
    new = [[None] * nc for _ in range(nr)]
    for r in range(nr):
        for c in range(nc):
            r2, c2 = pos(r, c, nr, nc)
            new[r2][c2] = content(bg[r][c])
    return unblocks(new)


def whole_hflip(inp, out):
    return hflip(inp)


def whole_vflip(inp, out):
    return vflip(inp)


def whole_rot180(inp, out):
    return vflip(hflip(inp))


def whole_transpose(inp, out):
    return transpose(inp)


def mirror_blocks_flip_contents_h(inp, out):
    return block_map(inp, 2, lambda r, c, nr, nc: (r, nc - 1 - c), hflip)


def mirror_blocks_flip_contents_v(inp, out):
    return block_map(inp, 2, lambda r, c, nr, nc: (r, nc - 1 - c), vflip)


def vflip_blocks_flip_contents_v(inp, out):
    return block_map(inp, 2, lambda r, c, nr, nc: (nr - 1 - r, c), vflip)


def halves_swapped(inp, out):
    n = len(inp)
    m = len(inp[0])
    if m % 2:
        return None
    h = m // 2
    return [r[h:] + r[:h] for r in inp]


def half_applied(inp, out):
    n = len(inp)
    h = (n // 4) * 2
    return [list(out[i]) if i < h else list(inp[i]) for i in range(n)]


def roll_blocks(inp, out):
    return block_map(inp, 2, lambda r, c, nr, nc: (r, (c + 1) % nc))


def blocks_of_three(inp, out):
    return block_map(inp, 3, lambda r, c, nr, nc: (r, nc - 1 - c))


def blocks_of_size_one_wrong_size(inp, out):
    # block size taken as 4 instead of 2
    return block_map(inp, 4, lambda r, c, nr, nc: (r, nc - 1 - c))


def top_block_row_only(inp, out):
    # only the first block row is moved; the others stay
    bg = blocks(inp, 2)
    og = blocks(out, 2)
    if bg is None:
        return None
    new = [row[:] for row in bg]
    new[0] = og[0]
    return unblocks(new)


ALTERNATIVES = [
    ("mirror the whole grid left-right (block contents mirrored too)", whole_hflip),
    ("flip the whole grid top-bottom", whole_vflip),
    ("rotate the whole grid 180 degrees", whole_rot180),
    ("transpose the whole grid", whole_transpose),
    ("mirror block positions left-right and mirror each block's contents", mirror_blocks_flip_contents_h),
    ("mirror block positions left-right and flip each block's contents top-bottom", mirror_blocks_flip_contents_v),
    ("flip block positions top-bottom and flip each block's contents top-bottom", vflip_blocks_flip_contents_v),
    ("swap the left and right halves of the grid", halves_swapped),
    ("apply the true output only to the upper half of rows", half_applied),
    ("shift block columns cyclically by one instead of mirroring", roll_blocks),
    ("take blocks as 3x3 and mirror their positions", blocks_of_three),
    ("take blocks as 4x4 and mirror their positions", blocks_of_size_one_wrong_size),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/8ee62060.json')))
    pairs = t["train"]
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("ERROR", desc, e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
