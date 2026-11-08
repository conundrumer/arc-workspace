"""Model input layer: whether a table's rows act as a map: whether a pair of cells, a cell with a move or a symmetry, or a pair of colors carries the
input to the train output; whether a number is a period, a scale or a tile count of the grids; how a number stands to the size of its group; and how
a cell set's lines and groups are laid out.
"""
from grammar import ABSENT, INPUT, OUTPUT, Var, operator
from vocabulary import BASE_STAGE, GRID_STAGE, MAX_CELLS, MAX_ROWS, OWN_STAGE, columns, guarded, grids_same_size, other_than, proportion

NUM = ('Nat', 'Int')

p, q, n, x, g = (Var(v) for v in 'p q n x g'.split())


def periods(array):
    """{translations along a row or a column that keep every cell of the grid whose image lies in the grid}, each as its length."""
    H, W = len(array), len(array[0])
    out = set()
    for k in range(1, W):
        if all(row[c] == row[c + k] for row in array for c in range(W - k)):
            out.add(k)
    for k in range(1, H):
        if all(array[r][c] == array[r + k][c] for r in range(H - k) for c in range(W)):
            out.add(k)
    return out


_grids = {}


def periods_of(array):
    key = id(array)
    held = _grids.get(key)
    if held is None or held[0] is not array:
        if len(_grids) > 64:
            _grids.clear()
        held = (array, periods(array))
        _grids[key] = held
    return held[1]


def upscaled(array, k):
    return [[x_ for x_ in row for _ in range(k)] for row in array for _ in range(k)]


def pattern_form(cells):
    """A pattern ({cell: color}) translated so that its bounding box starts at (0, 0)."""
    r0, k0 = min(u[0] for u in cells), min(u[1] for u in cells)
    return frozenset(((u[0] - r0, u[1] - k0), y) for u, y in cells.items())


def d4_forms(cells):
    """The form of the pattern under each element of D4."""
    import outputs as OC
    H, W = max(u[0] for u in cells) + 1, max(u[1] for u in cells) + 1
    return {pattern_form({OC.cell_image(u, H, W, d): y for u, y in cells.items()}) for d in OC.D4}


def frame_columns(c, e):
    """A Position column whose values lie in one frame, with no value off it."""
    out = []
    if not c.rows or len(c.rows) > MAX_ROWS:
        return out
    for i, col in enumerate(c.cols):
        if col[1] == 'Position' and len({(r[i][0] + r[i][1] + 1, r[i][2] + r[i][3] + 1) for r in c.rows}) == 1 and not any(min(r[i]) < 0 for r in c.rows):
            out.append((i, col[0]))
    return out


def label_columns(*others):
    """A column that can name a pattern: an Ident, a key, or another Position column."""
    def dom(c, e):
        taken = {e[v] for v in others if e.get(v) is not None}
        return [(i, col[0]) for i, col in enumerate(c.cols) if (col[1] in ('Ident', 'Position') or col[0].startswith('key.')) and i not in taken]
    return dom


@operator(memo=True, reads=('input',))
def patterns(c, e, v, u, label):
    """{label value: {cell: color}} of the rows: the colors of column u, or the input's where u is None and the column lies in the input's frame. ABSENT where a cell of one
    pattern holds two colors, or where the patterns number under two or over 200, or hold too many cells."""
    i, j, k = e[v], None if u is None else e[u], e[label]
    if j is None and {(r[i][0] + r[i][1] + 1, r[i][2] + r[i][3] + 1) for r in c.rows} != {(len(c.gi), len(c.gi[0]))}:
        return ABSENT
    held = {}
    for r in c.rows:
        cell = (r[i][0], r[i][2])
        y = c.gi[cell[0]][cell[1]] if j is None else r[j]
        if held.setdefault(str(r[k]), {}).setdefault(cell, y) != y:
            return ABSENT
    if not 2 <= len(held) <= 200 or sum(len(m) for m in held.values()) > MAX_CELLS * 3:
        return ABSENT
    return held


@operator(memo=True)
def pattern_counts(c, e, v, u, label):
    held = patterns(v, u, label)(c, e)
    if held is ABSENT:
        return ABSENT
    out = {}
    for m in held.values():
        form = pattern_form(m)
        out[form] = out.get(form, 0) + 1
    return out


def output_form(c):
    return frozenset(((r, k), y) for r, row in enumerate(c.go) for k, y in enumerate(row))


@operator(reads=('output',))
def some_pattern_is_output(c, e, v, u, label):
    counts = pattern_counts(v, u, label)(c, e)
    return ABSENT if counts is ABSENT else output_form(c) in counts


@operator(reads=('output',))
def extreme_pattern_is_output(c, e, v, u, label, extreme):
    counts = pattern_counts(v, u, label)(c, e)
    if counts is ABSENT:
        return ABSENT
    target = output_form(c)
    return target in counts and counts[target] == extreme(counts.values()) and len(counts) > 1


@operator(reads=('output',))
def some_pattern_is_output_under_d4(c, e, v, u, label):
    held = patterns(v, u, label)(c, e)
    if held is ABSENT or len(held) > 30:
        return ABSENT
    target = output_form(c)
    return any(target in d4_forms(m) for m in held.values())


@operator
def distinct_patterns(c, e, v, u, label):
    counts = pattern_counts(v, u, label)(c, e)
    return ABSENT if counts is ABSENT else len(counts)


@operator
def one_pattern_differs(c, e, v, u, label):
    counts = pattern_counts(v, u, label)(c, e)
    return ABSENT if counts is ABSENT else len(counts) == 2 and min(counts.values()) == 1


@operator
def distinct_patterns_under_d4(c, e, v, u, label):
    held = patterns(v, u, label)(c, e)
    if held is ABSENT or len(held) > 30:
        return ABSENT
    return len({min(tuple(sorted(y, key=repr)) for y in d4_forms(m)) for m in held.values()})


def declare_patterns():
    for head, color, binders in (('{p}', None, dict(p=frame_columns, g=label_columns(p))), ('{p},{x}', x, dict(p=frame_columns, x=columns(('Color',)), g=label_columns(p, x)))):
        lead = head + ' patterns by {g} '
        GRID_STAGE.define(lead + 'some pattern is the output', some_pattern_is_output(p, color, g), **binders)
        GRID_STAGE.define(lead + 'the most frequent pattern is the output', extreme_pattern_is_output(p, color, g, max), **binders)
        GRID_STAGE.define(lead + 'the least frequent pattern is the output', extreme_pattern_is_output(p, color, g, min), **binders)
        GRID_STAGE.define(lead + 'some pattern is the output up to rotation and reflection', some_pattern_is_output_under_d4(p, color, g), **binders)
        OWN_STAGE.define(lead + 'distinct', distinct_patterns(p, color, g), **binders)
        OWN_STAGE.define(lead + 'exactly one pattern differs', one_pattern_differs(p, color, g), **binders)
        OWN_STAGE.define(lead + 'distinct up to rotation and reflection', distinct_patterns_under_d4(p, color, g), **binders)


# ---- a row as a map from the input to the output

def is_cell(v, H, W):
    return v[0] + v[1] + 1 == H and v[2] + v[3] + 1 == W and min(v) >= 0


def few_rows(c):
    return c.rows and len(c.rows) <= MAX_ROWS


def positions(c, e):
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[1] == 'Position'] if few_rows(c) else ()


@operator(memo=True, reads=('input', 'output'))
def input_to_output_pairs(c, e, v, u):
    Hi, Wi, Ho, Wo = len(c.gi), len(c.gi[0]), len(c.go), len(c.go[0])
    i, j = e[v], e[u]
    return [(r[i], r[j]) for r in c.rows if is_cell(r[i], Hi, Wi) and is_cell(r[j], Ho, Wo)]


@operator(reads=('input', 'output'))
def column_preserves_color(c, e, v, u):
    pairs = input_to_output_pairs(v, u)(c, e)
    if not pairs:
        return ABSENT
    return proportion(c.gi[a[0]][a[2]] == c.go[b[0]][b[2]] for a, b in {(tuple(a), tuple(b)) for a, b in pairs})


@operator(reads=('output',))
def column_covers_output(c, e, v, u):
    pairs = input_to_output_pairs(v, u)(c, e)
    if not pairs:
        return ABSENT
    return round(len({(b[0], b[2]) for _, b in pairs}) / (len(c.go) * len(c.go[0])), 3)


@operator(reads=('input', 'output'))
def translation_preserves_color(c, e, v, u):
    Hi, Wi, Ho, Wo = len(c.gi), len(c.gi[0]), len(c.go), len(c.go[0])
    if (Hi, Wi) != (Ho, Wo):
        return ABSENT
    hits = []
    for a, t in {(tuple(r[e[v]]), tuple(r[e[u]])) for r in c.rows if is_cell(r[e[v]], Hi, Wi)}:
        y, w = a[0] + t[0], a[2] + t[2]
        if 0 <= y < Ho and 0 <= w < Wo:
            hits.append(c.gi[a[0]][a[2]] == c.go[y][w])
    return proportion(hits) if hits else ABSENT


@operator(reads=('input', 'output'))
def symmetry_preserves_color(c, e, v, u):
    import outputs as OC
    Hi, Wi, Ho, Wo = len(c.gi), len(c.gi[0]), len(c.go), len(c.go[0])
    hits = []
    for a, d in {(tuple(r[e[v]]), r[e[u]]) for r in c.rows if is_cell(r[e[v]], Hi, Wi)}:
        if ((Wi, Hi) if d in ('D4_CW', 'D4_CC', 'D4_DG', 'D4_AD') else (Hi, Wi)) != (Ho, Wo):
            continue  # the image of the input frame is not the output frame, so a cell's image has no place there
        y, w = OC.cell_image((a[0], a[2]), Hi, Wi, d)
        if 0 <= y < Ho and 0 <= w < Wo:
            hits.append(c.gi[a[0]][a[2]] == c.go[y][w])
    return proportion(hits) if hits else ABSENT


@operator(reads=('input', 'output'))
def output_is_input_or_row_color(c, e, v, u):
    Hi, Wi = len(c.gi), len(c.gi[0])
    usable = [r for r in c.rows if is_cell(r[e[v]], Hi, Wi)]
    if len(usable) < 2:
        return ABSENT
    i, j = e[v], e[u]
    return proportion(c.go[r[i][0]][r[i][2]] in (c.gi[r[i][0]][r[i][2]], r[j]) for r in usable)


@operator(memo=True)
def color_map(c, e, a, b):
    """{color of column a: color of column b}, or ABSENT where a color of column a has two images."""
    table = {}
    for r in c.rows:
        table.setdefault(r[e[a]], set()).add(r[e[b]])
    if not all(len(y) == 1 for y in table.values()):
        return ABSENT
    return {k: next(iter(y)) for k, y in table.items()}


@operator(reads=('input', 'output'))
def color_map_on_mapped_cells(c, e, a, b):
    table = color_map(a, b)(c, e)
    if table is ABSENT:
        return ABSENT
    touched = [(y, c.go[r][k]) for r, row in enumerate(c.gi) for k, y in enumerate(row) if y in table]
    return proportion(table[y] == w for y, w in touched) if touched else ABSENT


@operator(reads=('input', 'output'))
def color_map_gives_output(c, e, a, b):
    table = color_map(a, b)(c, e)
    if table is ABSENT:
        return ABSENT
    return all(table.get(y, y) == c.go[r][k] for r, row in enumerate(c.gi) for k, y in enumerate(row))


def positive_values(c, e, v):
    return {r[e[v]] for r in c.rows if r[e[v]] > 0}


def numbers_with_positive_value(c, e):
    if not few_rows(c):
        return ()
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[1] in NUM and any(r[i] > 0 for r in c.rows)]


@operator
def proportion_periods(c, e, v, grid):
    held = periods_of(c.array(grid))
    return proportion(y in held for y in positive_values(c, e, v))


@operator(reads=('input', 'output'))
def proportion_size_ratios(c, e, v):
    Hi, Wi, Ho, Wo = len(c.gi), len(c.gi[0]), len(c.go), len(c.go[0])
    return proportion((Ho == y * Hi or Wo == y * Wi or Hi == y * Ho or Wi == y * Wo) for y in positive_values(c, e, v))


@operator(reads=('input', 'output'))
def proportion_upscales(c, e, v):
    Hi, Wi, Ho, Wo = len(c.gi), len(c.gi[0]), len(c.go), len(c.go[0])
    big = [y for y in positive_values(c, e, v) if 2 <= y <= 30]
    if not big:
        return ABSENT
    return proportion(Ho == Hi * y and Wo == Wi * y and upscaled(c.gi, y) == [list(w) for w in c.go] for y in big)


def declare_maps():
    GRID_STAGE.define('{p},{q} carries the input colors to the output, proportion', column_preserves_color(p, q), p=positions, q=other_than(p, ('Position',)))
    GRID_STAGE.define('{p},{q} covers the output cells, proportion', column_covers_output(p, q), p=positions, q=other_than(p, ('Position',)))
    GRID_STAGE.define('{p},{n} translates the input color onto the output, proportion', translation_preserves_color(p, n), p=positions, n=columns(('Offset',)))
    GRID_STAGE.define('{p},{n} rotates or reflects the input color onto the output, proportion', symmetry_preserves_color(p, n), p=positions, n=columns(('D4', 'C4')))
    GRID_STAGE.define('{p},{x} the output color is the input color or this color, proportion', guarded(grids_same_size(), output_is_input_or_row_color(p, x)), p=positions, x=other_than(p, ('Color',)))
    colors = lambda c, e: [(i, col[0]) for i, col in enumerate(c.cols) if col[1] == 'Color'] if few_rows(c) else ()
    GRID_STAGE.define('{p},{q} maps the input colors to the output, proportion', guarded(grids_same_size(), color_map_on_mapped_cells(p, q)), p=colors, q=other_than(p, ('Color',)))
    GRID_STAGE.define('{p},{q} maps the input onto the output', guarded(grids_same_size(), color_map_gives_output(p, q)), p=colors, q=other_than(p, ('Color',)))
    GRID_STAGE.define('{n} is a period of the output, proportion', proportion_periods(n, OUTPUT), n=numbers_with_positive_value)
    GRID_STAGE.define('{n} is the ratio of an output side to the input side, proportion', proportion_size_ratios(n), n=numbers_with_positive_value)
    GRID_STAGE.define('{n} scales the input to the output, proportion', proportion_upscales(n), n=numbers_with_positive_value)
    OWN_STAGE.define('{n} is a period of the input, proportion', proportion_periods(n, INPUT), n=numbers_with_positive_value)


# ---- how a cell set's lines and groups are laid out

def cell_columns_with_few_cells(c, e):
    if not few_rows(c):
        return ()
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.cs and c.cs[col[0]][1] and len(c.cs[col[0]][1]) <= MAX_CELLS]


@operator
def spacing_kinds(c, e, v, pool):
    S = c.cs[c.cols[e[v]][0]][1]
    held = []
    for axis in (0, 1):
        lines = sorted({u[axis] for u in S})
        held.append(len({b - a for a, b in zip(lines, lines[1:])}))
    return pool(held)


@operator(memo=True)
def several_groups(c, e, v):
    import features as F
    groups = c.grouped(e[v])
    return groups if groups and 2 <= len(groups) <= 200 else ABSENT


@operator
def groups_inside_another_box(c, e, v):
    groups = several_groups(v)(c, e)
    if groups is ABSENT:
        return ABSENT
    boxes = [(min(u[0] for u in y), max(u[0] for u in y), min(u[1] for u in y), max(u[1] for u in y)) for y in groups.values()]
    return proportion(any(a != b and boxes[b][0] <= boxes[a][0] and boxes[a][1] <= boxes[b][1] and boxes[b][2] <= boxes[a][2] and boxes[a][3] <= boxes[b][3] for b in range(len(boxes))) for a in range(len(boxes)))


@operator
def number_monotone_in_group_size(c, e, v, u):
    groups = several_groups(v)(c, e)
    if groups is ABSENT:
        return ABSENT
    gcols = [j for j, (m, ty, _) in enumerate(c.cols) if ty in ('Ident', 'Color') or m.startswith('key.')]
    per = {}
    for r in c.rows:
        per.setdefault(tuple(str(r[y]) for y in gcols), set()).add(r[e[u]])
    if not (all(len(y) == 1 for y in per.values()) and len({next(iter(y)) for y in per.values()}) > 1):
        return ABSENT
    pairs = sorted({(len(groups[k]), next(iter(y))) for k, y in per.items()})
    if any(a[0] == b[0] for a, b in zip(pairs, pairs[1:])):
        return 'neither'
    return 'rises' if all(a[1] <= b[1] for a, b in zip(pairs, pairs[1:])) else 'falls' if all(a[1] >= b[1] for a, b in zip(pairs, pairs[1:])) else 'neither'


def declare_layout():
    GROUPS = 'its Ident, Color and key columns'
    OWN_STAGE.define('{p} spacing kinds of its lines, min', spacing_kinds(p, min), p=cell_columns_with_few_cells)
    OWN_STAGE.define('{p} spacing kinds of its lines, max', spacing_kinds(p, max), p=cell_columns_with_few_cells)
    OWN_STAGE.define('{p} groups of %s inside the box of another, proportion' % GROUPS, groups_inside_another_box(p), p=cell_columns_with_few_cells)
    OWN_STAGE.define('{p},{n} as its group grows of %s' % GROUPS, number_monotone_in_group_size(p, n), p=cell_columns_with_few_cells, n=columns(NUM))


declare_patterns()
declare_maps()
declare_layout()
