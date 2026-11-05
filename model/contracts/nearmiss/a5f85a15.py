import json
from pathlib import Path


def _lines(inp):
    """Ink cells grouped by main diagonal (r - c), each sorted from the top."""
    groups = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v != 0:
                groups.setdefault(r - c, []).append((r, c))
    return [sorted(g) for _, g in sorted(groups.items(), key=lambda kv: min(kv[1]))]


def _mark(inp, pick, color=4, base=None):
    """Copy of inp (or base); for each line, cells whose (index, length) satisfy pick get color."""
    g = [row[:] for row in (base if base is not None else inp)]
    for line in _lines(inp):
        n = len(line)
        for i, (r, c) in enumerate(line):
            if pick(i, n):
                g[r][c] = color
    return g


def phase_even(inp, out):
    return _mark(inp, lambda i, n: i % 2 == 0)


def from_far_end(inp, out):
    return _mark(inp, lambda i, n: (n - 1 - i) % 2 == 1)


def all_cells(inp, out):
    return _mark(inp, lambda i, n: True)


def every_third(inp, out):
    return _mark(inp, lambda i, n: i % 3 == 1)


def wrong_color(inp, out):
    return _mark(inp, lambda i, n: i % 2 == 1, color=8)


def erase_marked(inp, out):
    return _mark(inp, lambda i, n: i % 2 == 1, color=0)


def only_first_line(inp, out):
    lines = _lines(inp)
    g = [row[:] for row in inp]
    for i, (r, c) in enumerate(lines[0]):
        if i % 2 == 1:
            g[r][c] = 4
    return g


def only_line_ends(inp, out):
    return _mark(inp, lambda i, n: i in (0, n - 1))


def global_row_major_count(inp, out):
    g = [row[:] for row in inp]
    k = 0
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v != 0:
                if k % 2 == 1:
                    g[r][c] = 4
                k += 1
    return g


def even_column_parity(inp, out):
    g = [row[:] for row in inp]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v != 0 and c % 2 == 0:
                g[r][c] = 4
    return g


def marks_only_first_half(inp, out):
    return _mark(inp, lambda i, n: i % 2 == 1 and i < n / 2)


def marks_on_background_instead(inp, out):
    # marks the background cells beside the line rather than the line cells
    g = [row[:] for row in inp]
    h, w = len(inp), len(inp[0])
    for line in _lines(inp):
        for i, (r, c) in enumerate(line):
            if i % 2 == 1 and r + 1 < h and c < w and inp[r + 1][c] == 0:
                g[r + 1][c] = 4
    return g


def _none_if_true(fn):
    def wrapped(inp, out):
        g = fn(inp, out)
        return None if g == out else g
    return wrapped


ALTERNATIVES = [
    ("mark the even-position cells (0, 2, 4, ...) of each line instead of the odd ones", phase_even),
    ("count from the far end of each line, so the other parity is marked", from_far_end),
    ("mark every cell of every line", all_cells),
    ("mark every third cell of each line (period 3, offset 1)", every_third),
    ("mark the right cells with the wrong color 8", wrong_color),
    ("erase the odd cells to background instead of marking them 4", erase_marked),
    ("only the first line is marked, the other lines stay unchanged", only_first_line),
    ("only the two end cells of each line are marked", only_line_ends),
    ("the alternation count runs over all ink cells in row-major order and is not reset per line", global_row_major_count),
    ("mark ink cells by column parity (even columns) instead of position along the line", even_column_parity),
    ("only the first half of each line is alternately marked", marks_only_first_half),
    ("mark the background cell below each odd line cell instead of the line cell", marks_on_background_instead),
]

ALTERNATIVES = [(d, _none_if_true(f)) for d, f in ALTERNATIVES]


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/a5f85a15.json').read_text())
    pairs = task['train']
    print('pairs', len(pairs))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is None:
                continue
            valid = (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                     and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))
            if valid and g != p['output']:
                ok += 1
        print(ok, desc)
