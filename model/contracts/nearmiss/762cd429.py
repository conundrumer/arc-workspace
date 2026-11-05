"""Near-miss readings for ARC task 762cd429 (2x2 seed at the left edge grows rightward into copies of doubling scale, centered on the seed's rows)."""
import json
from pathlib import Path


def seed_of(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return r0, c0, r1 - r0 + 1, c1 - c0 + 1


def render(inp, scale=lambda k: 2 ** k, vert="center", gap=0, first=1,
           levels=None, copy_fn=None, keep_seed=True, direction="right"):
    H, W = len(inp), len(inp[0])
    r0, c0, h, w = seed_of(inp)
    seed = [row[c0:c0 + w] for row in inp[r0:r0 + h]]
    if copy_fn:
        seed_copy = copy_fn(seed)
    else:
        seed_copy = seed
    g = [[0] * W for _ in range(H)]
    if direction == "right":
        pos = c0 + w + gap
    else:
        pos = r0 - gap
    k = first
    n = 0
    while levels is None or n < levels:
        s = scale(k)
        bh, bw = h * s, w * s
        if direction == "right":
            if pos >= W:
                break
            if vert == "center":
                top = r0 - (bh - h) // 2
            elif vert == "top":
                top = r0
            else:
                top = r0 + h - bh
            left = pos
            pos += bw + gap
        else:
            if pos <= 0:
                break
            top = pos - bh
            left = c0 - (bw - w) // 2
            pos = top - gap
        for i in range(bh):
            for j in range(bw):
                y, x = top + i, left + j
                if 0 <= y < H and 0 <= x < W:
                    g[y][x] = seed_copy[i // s][j // s]
        k += 1
        n += 1
    if keep_seed:
        for i in range(h):
            for j in range(w):
                g[r0 + i][c0 + j] = seed[i][j]
    return g


def correct(inp, out):
    return render(inp)


def linear_growth(inp, out):
    return render(inp, scale=lambda k: k + 1)


def factor_three(inp, out):
    return render(inp, scale=lambda k: 3 ** k)


def start_at_scale_one(inp, out):
    return render(inp, scale=lambda k: 2 ** k, first=0)


def first_copy_only(inp, out):
    return render(inp, levels=1)


def top_aligned(inp, out):
    return render(inp, vert="top")


def bottom_aligned(inp, out):
    return render(inp, vert="bottom")


def gap_between_copies(inp, out):
    return render(inp, gap=1)


def grow_upward(inp, out):
    return render(inp, direction="up")


def mirrored_copies(inp, out):
    return render(inp, copy_fn=lambda s: [r[::-1] for r in s])


def single_color_copies(inp, out):
    return render(inp, copy_fn=lambda s: [[s[0][0]] * len(s[0]) for _ in s])


def seed_removed(inp, out):
    return render(inp, keep_seed=False)


def unchanged(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("copy scale grows by one cell per level (2,3,4,...) instead of doubling", linear_growth),
    ("copy scale triples per level (3,9,27,...)", factor_three),
    ("first copy has the seed's own size (scales 1,2,4,...)", start_at_scale_one),
    ("only the first copy is drawn", first_copy_only),
    ("copies are aligned to the seed's top row instead of centered on it", top_aligned),
    ("copies are aligned to the seed's bottom row instead of centered on it", bottom_aligned),
    ("one background column separates consecutive copies", gap_between_copies),
    ("copies grow upward from the seed instead of rightward", grow_upward),
    ("copies are the seed mirrored left-right", mirrored_copies),
    ("every copy is painted in the seed's top-left color only", single_color_copies),
    ("seed cells are cleared to background in the output", seed_removed),
    ("no growth: output equals the input", unchanged),
]


def valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/762cd429.json"))
    train = task["train"]
    for p in train:
        assert correct(p["input"], p["output"]) == p["output"], "model of the true rule is off"
    for desc, fn in ALTERNATIVES:
        n = sum(valid(fn(p["input"], p["output"]), p["output"]) for p in train)
        print(f"{n}/{len(train)}  {desc}")
