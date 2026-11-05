import json
from pathlib import Path

WALL, SPRITE, FILL = 2, 5, 1


def _copy(g):
    return [r[:] for r in g]


def _wall_box(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == WALL]
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def fill_only_in_box(inp, out):
    r0, r1, c0, c1 = _wall_box(inp)
    g = _copy(out)
    for r in range(len(g)):
        for c in range(len(g[0])):
            if g[r][c] == FILL and not (r0 <= r <= r1 and c0 <= c <= c1):
                g[r][c] = 0
    return g


def sprites_left_in_place(inp, out):
    g = _copy(out)
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == SPRITE:
                g[r][c] = SPRITE
    return g


def fill_with_sprite_color(inp, out):
    return [[SPRITE if v == FILL else v for v in row] for row in out]


def one_plug_missing(inp, out):
    h, w = len(out), len(out[0])
    seen = set()
    for r in range(h):
        for c in range(w):
            if out[r][c] == FILL and (r, c) not in seen:
                comp, stack = [], [(r, c)]
                seen.add((r, c))
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and out[ny][nx] == FILL and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                g = _copy(out)
                for y, x in comp:
                    g[y][x] = 0
                return g
    return None


def plug_shifted_down(inp, out):
    h, w = len(out), len(out[0])
    g = [[0 if v == FILL else v for v in row] for row in out]
    for r in range(h):
        for c in range(w):
            if out[r][c] == FILL and r + 1 < h and g[r + 1][c] != WALL:
                g[r + 1][c] = FILL
    return g


def wall_recolored(inp, out):
    return [[FILL if v == WALL else v for v in row] for row in out]


def sprites_erased_nothing_filled(inp, out):
    return [[0 if v == SPRITE else v for v in row] for row in inp]


def notch_columns_filled_down(inp, out):
    r0, r1, c0, c1 = _wall_box(inp)
    g = _copy(out)
    for c in range(len(g[0])):
        if any(out[r][c] == FILL for r in range(r0, r1 + 1)):
            for r in range(r0, len(g)):
                if g[r][c] != WALL:
                    g[r][c] = FILL
    return g


def sprites_recolored_in_place(inp, out):
    return [[FILL if v == SPRITE else v for v in row] for row in inp]


def notches_filled_sprites_kept(inp, out):
    r0, r1, c0, c1 = _wall_box(inp)
    g = _copy(inp)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if g[r][c] == 0:
                g[r][c] = FILL
    return g


def upper_notch_rows_unfilled(inp, out):
    r0, r1, c0, c1 = _wall_box(inp)
    g = _copy(out)
    for r in range(r0, r1):
        for c in range(len(g[0])):
            if inp[r][c] == 0:
                g[r][c] = 0
    return g


ALTERNATIVES = [
    ("plugs stop at the wall box edge: no sprite part below the box is drawn", fill_only_in_box),
    ("notches filled but the sprites stay at their input places", sprites_left_in_place),
    ("plugs drawn in the sprite color instead of the new color", fill_with_sprite_color),
    ("one plug is not found: its notch stays empty", one_plug_missing),
    ("plugs land one row too low", plug_shifted_down),
    ("wall recolored to the fill color", wall_recolored),
    ("sprites erased, nothing filled", sprites_erased_nothing_filled),
    ("each notch column filled down to the grid bottom", notch_columns_filled_down),
    ("sprites recolored in place, notches left empty", sprites_recolored_in_place),
    ("only the wall-box cells are filled and sprites stay", notches_filled_sprites_kept),
    ("notches in the upper box rows are left unfilled", upper_notch_rows_unfilled),
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
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/6a1e5592.json"))
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
