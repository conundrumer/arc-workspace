import json
from pathlib import Path


def _t(g):
    return [list(r) for r in zip(*g)]


def unchanged(inp, out):
    return [r[:] for r in inp]


def flip_h(inp, out):
    return [r[::-1] for r in inp]


def flip_v(inp, out):
    return [r[:] for r in inp[::-1]]


def rot_cw(inp, out):
    return [list(r) for r in zip(*inp[::-1])]


def rot_ccw(inp, out):
    return [list(r) for r in zip(*inp)][::-1]


def rot_180(inp, out):
    return [r[::-1] for r in inp[::-1]]


def anti_transpose(inp, out):
    return [r[::-1] for r in _t(inp)[::-1]]


def union_with_input(inp, out):
    # keep original cells and also add the mirrored ones
    n = len(inp)
    return [[inp[i][j] or out[i][j] for j in range(n)] for i in range(n)]


def lower_triangle_only(inp, out):
    n = len(out)
    return [[out[i][j] if j <= i else 0 for j in range(n)] for i in range(n)]


def recolor_to_diagonal(inp, out):
    n = len(out)
    d = out[0][0]
    return [[d if out[i][j] else 0 for j in range(n)] for i in range(n)]


def diagonal_cleared(inp, out):
    n = len(out)
    return [[0 if i == j else out[i][j] for j in range(n)] for i in range(n)]


def last_column_dropped(inp, out):
    return [r[:-1] + [0] for r in out]


def shifted_one_column(inp, out):
    return [r[1:] + r[:1] for r in out]


ALTERNATIVES = [
    ("input returned unchanged", unchanged),
    ("horizontal flip instead of transpose", flip_h),
    ("vertical flip instead of transpose", flip_v),
    ("rotation 90 degrees clockwise instead of transpose", rot_cw),
    ("rotation 90 degrees counterclockwise instead of transpose", rot_ccw),
    ("rotation 180 degrees instead of transpose", rot_180),
    ("anti-diagonal transpose instead of main-diagonal transpose", anti_transpose),
    ("mirror across the diagonal but keep the original cells too", union_with_input),
    ("only cells below the diagonal appear in the output", lower_triangle_only),
    ("transposed cells all recolored to the diagonal color", recolor_to_diagonal),
    ("diagonal color cells removed from the transposed grid", diagonal_cleared),
    ("last column of the transposed grid left empty (crop off by one)", last_column_dropped),
    ("transposed grid shifted one column left with wraparound", shifted_one_column),
]


def _valid(g, o):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) and r for r in g)
        and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r) and g != o
    )


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/9dfd6313.json').read_text())
    pairs = task['train']
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(n, len(pairs), desc)
