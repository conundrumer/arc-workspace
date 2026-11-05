"""Near-miss rules for bbb1b8b6.

The input has a base tile, a column of 5, and a piece tile. When the piece
exactly fills the holes (0 cells) of the base, the output is the base with the
piece cells added. Otherwise the output is the base.
"""
import json
from pathlib import Path


def _split(inp):
    sep = next(c for c in range(len(inp[0])) if all(r[c] == 5 for r in inp))
    base = [r[:sep] for r in inp]
    piece = [r[sep + 1:] for r in inp]
    return base, piece, sep


def _piece_color(piece):
    return next((v for r in piece for v in r if v), 0)


def _overlay(base, piece):
    return [[b if b else p for b, p in zip(rb, rp)] for rb, rp in zip(base, piece)]


def _guard(fn):
    def wrapped(inp, out):
        res = fn(inp, out)
        if res is None or res == out:
            return None
        return res
    return wrapped


@_guard
def always_base(inp, out):
    return _split(inp)[0]


@_guard
def always_piece(inp, out):
    return _split(inp)[1]


@_guard
def overlay_without_fit_check(inp, out):
    base, piece, _ = _split(inp)
    return _overlay(base, piece)


@_guard
def union_in_base_color(inp, out):
    base, piece, _ = _split(inp)
    bc = _piece_color(base) or 1
    return [[bc if (b or p) else 0 for b, p in zip(rb, rp)] for rb, rp in zip(base, piece)]


@_guard
def piece_mirrored_left_right(inp, out):
    base, piece, _ = _split(inp)
    return _overlay(base, [r[::-1] for r in piece])


@_guard
def piece_flipped_up_down(inp, out):
    base, piece, _ = _split(inp)
    return _overlay(base, piece[::-1])


@_guard
def piece_transposed(inp, out):
    base, piece, _ = _split(inp)
    if len(piece) != len(piece[0]):
        return None
    t = [list(r) for r in zip(*piece)]
    return _overlay(base, t)


@_guard
def first_piece_row_only(inp, out):
    base, piece, _ = _split(inp)
    if out == base:
        return None
    res = [r[:] for r in base]
    res[0] = [b if b else p for b, p in zip(base[0], piece[0])]
    return res


@_guard
def keep_separator_column(inp, out):
    return [r + [5] for r in out]


@_guard
def drop_last_row(inp, out):
    return [r[:] for r in out[:-1]]


@_guard
def base_recolored_with_piece_color(inp, out):
    base, piece, _ = _split(inp)
    pc = _piece_color(piece)
    return [[pc if v else 0 for v in r] for r in base]


@_guard
def fill_holes_with_separator_color(inp, out):
    base, piece, _ = _split(inp)
    return [[b if b else (5 if p else 0) for b, p in zip(rb, rp)] for rb, rp in zip(base, piece)]


ALTERNATIVES = [
    ("always output the base tile, never merging the piece", always_base),
    ("always output the piece tile", always_piece),
    ("always overlay the piece on the base without checking that it fits the holes", overlay_without_fit_check),
    ("union of base and piece cells, all drawn in the base color", union_in_base_color),
    ("piece mirrored left-right before overlay", piece_mirrored_left_right),
    ("piece flipped up-down before overlay", piece_flipped_up_down),
    ("piece transposed before overlay", piece_transposed),
    ("only the first row of the piece is merged into the base", first_piece_row_only),
    ("output keeps the separator column of 5s", keep_separator_column),
    ("output crop is one row short", drop_last_row),
    ("base cells recolored with the piece color, holes left empty", base_recolored_with_piece_color),
    ("piece cells drawn in the separator color 5", fill_holes_with_separator_color),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/bbb1b8b6.json').read_text())
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
