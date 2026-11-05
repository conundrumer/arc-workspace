"""Near-miss readings for ARC task 7e2bad24.

Rule: a diagonal seed line of the rarest color continues as a beam in the
same direction. The beam overwrites cells it crosses, passes through walls of
colors it changes, and turns at walls of colors that stay unchanged.
"""
from collections import Counter

DIAGS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _info(inp, out):
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    ray = min(cnt, key=lambda k: (cnt[k], k))
    walls = {k for k in cnt if k not in (bg, ray)}
    changed = {inp[r][c] for r in range(len(inp)) for c in range(len(inp[0]))
               if inp[r][c] != out[r][c]}
    transparent = walls & changed
    reflective = walls - changed
    return bg, ray, walls, transparent, reflective


def _starts(inp, ray):
    h, w = len(inp), len(inp[0])

    def is_ray(r, c):
        return 0 <= r < h and 0 <= c < w and inp[r][c] == ray

    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != ray:
                continue
            for dr, dc in DIAGS:
                if is_ray(r - dr, c - dc) and not is_ray(r + dr, c + dc):
                    res.append((r, c, dr, dc))
    return res


def _beam(inp, out, reflect=None, opaque=None, bounce="flip", late=False,
          flip_start=False, border=False):
    """Trace the beam; return the ordered list of cells it visits."""
    bg, ray, walls, transparent, reflective = _info(inp, out)
    if reflect is None:
        reflect = reflective
    if opaque is None:
        opaque = set()
    h, w = len(inp), len(inp[0])

    def wall(r, c):
        return 0 <= r < h and 0 <= c < w and inp[r][c] in reflect

    cells = []
    for (r, c, dr, dc) in _starts(inp, ray):
        if flip_start:
            dc = -dc
        seen = set()
        skip_check = False
        for _ in range(400):
            if (r, c, dr, dc) in seen:
                break
            seen.add((r, c, dr, dc))
            if not skip_check:
                a = wall(r, c + dc)
                b = wall(r + dr, c)
                d = wall(r + dr, c + dc)
                if a or b or d:
                    if bounce == "stop":
                        break
                    if bounce == "reverse":
                        ndr, ndc = -dr, -dc
                    else:
                        ndr = -dr if (b or (d and not a)) else dr
                        ndc = -dc if (a or (d and not b)) else dc
                    if late:
                        r, c = r + dr, c + dc
                        if 0 <= r < h and 0 <= c < w:
                            cells.append((r, c))
                        else:
                            break
                    dr, dc = ndr, ndc
            skip_check = False
            nr, nc = r + dr, c + dc
            if not (0 <= nr < h and 0 <= nc < w):
                if not border:
                    break
                if not 0 <= nr < h:
                    dr = -dr
                if not 0 <= nc < w:
                    dc = -dc
                nr, nc = r + dr, c + dc
                if not (0 <= nr < h and 0 <= nc < w):
                    break
            if inp[nr][nc] in opaque:
                break
            r, c = nr, nc
            cells.append((r, c))
    return cells


def _paint(inp, out, cells, color=None, keep_walls=False):
    bg, ray, *_ = _info(inp, out)
    g = [row[:] for row in inp]
    col = ray if color is None else color
    for (r, c) in cells:
        if keep_walls and inp[r][c] != bg:
            continue
        g[r][c] = col
    return g


def _wrap(f):
    def inner(inp, out):
        g = f(inp, out)
        if g is None or g == out:
            return None
        return g
    return inner


@_wrap
def all_reflect(inp, out):
    walls = _info(inp, out)[2]
    return _paint(inp, out, _beam(inp, out, reflect=walls))


@_wrap
def none_reflect(inp, out):
    return _paint(inp, out, _beam(inp, out, reflect=set()))


@_wrap
def swapped_roles(inp, out):
    _, _, _, transparent, reflective = _info(inp, out)
    return _paint(inp, out, _beam(inp, out, reflect=transparent))


@_wrap
def transparent_block(inp, out):
    _, _, walls, transparent, reflective = _info(inp, out)
    return _paint(inp, out, _beam(inp, out, opaque=transparent))


@_wrap
def stop_at_reflective(inp, out):
    return _paint(inp, out, _beam(inp, out, bounce="stop"))


@_wrap
def reverse_at_bounce(inp, out):
    return _paint(inp, out, _beam(inp, out, bounce="reverse"))


@_wrap
def turn_late(inp, out):
    return _paint(inp, out, _beam(inp, out, late=True))


@_wrap
def wrong_orientation(inp, out):
    return _paint(inp, out, _beam(inp, out, flip_start=True))


@_wrap
def keep_crossed_walls(inp, out):
    return _paint(inp, out, _beam(inp, out), keep_walls=True)


@_wrap
def wall_colored_beam(inp, out):
    cnt = Counter(v for row in inp for v in row)
    bg, ray, walls, _, _ = _info(inp, out)
    wc = max(walls, key=lambda k: (cnt[k], k))
    return [[wc if (inp[r][c] != out[r][c] and out[r][c] == ray) else out[r][c]
             for c in range(len(out[0]))] for r in range(len(out))]


@_wrap
def seed_erased(inp, out):
    bg, ray, *_ = _info(inp, out)
    return [[bg if inp[r][c] == ray else out[r][c]
             for c in range(len(out[0]))] for r in range(len(out))]


@_wrap
def border_bounce(inp, out):
    return _paint(inp, out, _beam(inp, out, border=True))


ALTERNATIVES = [
    ("every wall color reflects the beam", all_reflect),
    ("no wall reflects the beam; it goes straight through all", none_reflect),
    ("reflective and transparent wall roles are swapped", swapped_roles),
    ("walls the beam should cross block it", transparent_block),
    ("beam stops at a reflective wall instead of turning", stop_at_reflective),
    ("beam reverses back along its path at a reflective wall", reverse_at_bounce),
    ("beam enters the wall cell before turning (one step late)", turn_late),
    ("beam leaves the seed on the other diagonal orientation", wrong_orientation),
    ("beam leaves crossed wall cells unpainted", keep_crossed_walls),
    ("beam takes the wall color instead of the seed color", wall_colored_beam),
    ("original seed cells are erased", seed_erased),
    ("beam also bounces off the grid border", border_bounce),
]


if __name__ == "__main__":
    import json
    from pathlib import Path

    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/7e2bad24.json").read_text())
    pairs = task["train"]
    for name, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(row, list) for row in g)
                  and len({len(row) for row in g}) == 1
                  and all(isinstance(v, int) and 0 <= v <= 9 for row in g for v in row))
            if ok and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {name}")
