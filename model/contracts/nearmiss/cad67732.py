"""Near-miss readings for ARC task cad67732 (diagonal band doubled and continued)."""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _period(inp, dc):
    """Least K > 0 with inp unchanged under shift (K, dc*K) where both cells lie in the grid."""
    n = len(inp)
    for k in range(1, n):
        ok = True
        for r in range(n):
            for c in range(n):
                r2, c2 = r + k, c + dc * k
                if 0 <= r2 < n and 0 <= c2 < n and inp[r][c] != inp[r2][c2]:
                    ok = False
        if ok:
            return k
    return n


def _gen(inp, ar, ac, scale, k, limit=None, bg=None):
    """Input at output corner (ar, ac); band continues away from it with period k."""
    n = len(inp)
    m = scale * n
    bg = _bg(inp) if bg is None else bg
    r0, c0 = ar * (m - n), ac * (m - n)
    dr, dc = (1 if ar == 0 else -1), (1 if ac == 0 else -1)
    out = [[bg] * m for _ in range(m)]
    for r in range(m):
        for c in range(m):
            if r0 <= r < r0 + n and c0 <= c < c0 + n:
                out[r][c] = inp[r - r0][c - c0]
                continue
            j = 1
            while True:
                if limit is not None and j > limit:
                    break
                qr, qc = r - j * k * dr, c - j * k * dc
                if not (0 <= qr < m and 0 <= qc < m):
                    break
                if r0 <= qr < r0 + n and c0 <= qc < c0 + n:
                    out[r][c] = inp[qr - r0][qc - c0]
                    break
                j += 1
    return out


def _true_corner(inp, out):
    n = len(inp)
    for ar in (0, 1):
        for ac in (0, 1):
            dc = 1 if ac == 0 else -1
            if _gen(inp, ar, ac, 2, _period(inp, dc)) == out:
                return ar, ac
    return 0, 0


def _band_dc(inp, out):
    return 1 if _true_corner(inp, out)[1] == 0 else -1


def vertical_flip(inp, out):
    return [list(r) for r in reversed(out)]


def wrong_diagonal(inp, out):
    ar, ac = _true_corner(inp, out)
    dc = -1 if ac == 0 else 1
    return _gen(inp, ar, 1 - ac, 2, _period(inp, dc))


def period_plus_one(inp, out):
    ar, ac = _true_corner(inp, out)
    dc = 1 if ac == 0 else -1
    return _gen(inp, ar, ac, 2, _period(inp, dc) + 1)


def period_is_side(inp, out):
    ar, ac = _true_corner(inp, out)
    return _gen(inp, ar, ac, 2, len(inp) - 1)


def one_period_only(inp, out):
    ar, ac = _true_corner(inp, out)
    dc = 1 if ac == 0 else -1
    return _gen(inp, ar, ac, 2, _period(inp, dc), limit=1)


def scale_three(inp, out):
    ar, ac = _true_corner(inp, out)
    dc = 1 if ac == 0 else -1
    return _gen(inp, ar, ac, 3, _period(inp, dc))


def tile_two_by_two(inp, out):
    return [list(r) + list(r) for r in inp] * 2


def pixel_doubling(inp, out):
    res = []
    for r in inp:
        row = [v for v in r for _ in (0, 1)]
        res.append(row)
        res.append(list(row))
    return res


def mirrored_output(inp, out):
    return [list(reversed(r)) for r in out]


def off_by_one_size(inp, out):
    return [list(r[:-1]) for r in out[:-1]]


def shifted_continuation(inp, out):
    """Continuation outside the input block is displaced one cell along the band."""
    ar, ac = _true_corner(inp, out)
    n, m = len(inp), len(out)
    bg = _bg(inp)
    r0, c0 = ar * (m - n), ac * (m - n)
    dr, dc = (1 if ar == 0 else -1), (1 if ac == 0 else -1)
    res = [list(r) for r in out]
    for r in range(m):
        for c in range(m):
            if r0 <= r < r0 + n and c0 <= c < c0 + n:
                continue
            qr, qc = r - dr, c - dc
            res[r][c] = out[qr][qc] if 0 <= qr < m and 0 <= qc < m else bg
    return res


def input_unchanged(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("input anchored at the bottom or top edge opposite the true one (true output flipped vertically)", vertical_flip),
    ("band continued along the other diagonal, anchored at the adjacent corner", wrong_diagonal),
    ("period one cell too long", period_plus_one),
    ("period taken as one less than the input side", period_is_side),
    ("only one period of continuation is drawn, the rest stays background", one_period_only),
    ("output scale three instead of two", scale_three),
    ("input tiled in a two by two block layout", tile_two_by_two),
    ("each input cell doubled to a 2x2 block, no continuation", pixel_doubling),
    ("true output mirrored left to right", mirrored_output),
    ("output one row and one column too small", off_by_one_size),
    ("continuation shifted one cell along the band", shifted_continuation),
    ("input returned unchanged", input_unchanged),
]


def _valid(g, out):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/cad67732.json"))
    train = task["train"]
    for p in train:
        ar, ac = _true_corner(p["input"], p["output"])
        dc = 1 if ac == 0 else -1
        assert _gen(p["input"], ar, ac, 2, _period(p["input"], dc)) == p["output"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
