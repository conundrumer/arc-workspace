"""Model input layer: what a table's values claim about the input grid of its example, and how nearly its colored cells repeat under a symmetry or a
move. A cell set is compared with the input's colors and with its components, the input's 8-connected sets of cells of one color.
"""
from grammar import ABSENT, INPUT, Var, operator
from vocabulary import BASE_STAGE, GROUPS, MAX_CELLS, MAX_ROWS, columns, proportion
import roles as RO


n, x, b = (Var(v) for v in 'n x b'.split())


def grid_view(c):
    return RO.grid_view(c, INPUT)


def repeats(M):
    """{feature: value} of how nearly the colored cells M ({cell: color}) repeat: the greatest proportion of cells that a reflection or a rotation of their bounding box maps onto a
    cell of the same color, and the greatest proportion of pairs of cells one translation along a row or a column apart that hold one color."""
    rs, ks = [u[0] for u in M], [u[1] for u in M]
    r0, r1, k0, k1 = min(rs), max(rs), min(ks), max(ks)
    H, W = r1 - r0 + 1, k1 - k0 + 1
    if H * W < 2:
        return {}

    def agreement(fn):
        hits = total = 0
        for (r, k), y in M.items():
            w = M.get(fn(r - r0, k - k0))
            if w is not None:
                total += 1
                hits += w == y
        return hits / total if total else 0.0
    reflections = [lambda r, k: (r + r0, k1 - k), lambda r, k: (r1 - r, k + k0)]
    rotations = [lambda r, k: (r1 - r, k1 - k)]
    if H == W:
        reflections += [lambda r, k: (k + r0, r + k0), lambda r, k: (r1 - k, k1 - r)]
        rotations += [lambda r, k: (k + r0, k1 - r), lambda r, k: (r1 - k, r + k0)]
    f = {'reflection agreement, greatest proportion': round(max(agreement(m) for m in reflections), 3), 'rotation agreement, greatest proportion': round(max(agreement(t) for t in rotations), 3)}
    best = None
    for dr, dk, m in ((1, 0, H), (0, 1, W)):
        for step in range(1, m // 2 + 1):
            hits = total = 0
            for (r, k), y in M.items():
                w = M.get((r + dr * step, k + dk * step))
                if w is not None:
                    total += 1
                    hits += w == y
            if total:
                v = hits / total
                best = v if best is None or v > best else best
    if best is not None:
        f['translation agreement along rows or columns, greatest proportion'] = round(best, 3)
    return f


@operator(memo=True)
def self_agreement(c, e, v, u):
    M = {}
    for r in c.rows:
        M.setdefault((r[e[v]][0], r[e[v]][2]), set()).add(r[e[u]])
    if not all(len(y) == 1 for y in M.values()):
        return {}
    return repeats({k: next(iter(y)) for k, y in M.items()})


@operator
def agreement_measure(c, e, v, u, name):
    return self_agreement(v, u)(c, e).get(name, ABSENT)


def few_rows(dom):
    def wrapped(c, e):
        return dom(c, e) if c.rows and len(c.rows) <= MAX_ROWS else ()
    return wrapped


def columns_with_few_cells(c, e):
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.cs and c.cs[col[0]][1] and len(c.cs[col[0]][1]) <= MAX_CELLS]


@operator(reads=('input',))
def is_union_of_components(c, e, v):
    G = grid_view(c)
    S = c.cs[c.cols[e[v]][0]][1] & G.cells
    return all(G.component_of[u] <= S for u in S)


@operator(reads=('input',))
def groups_are_components(c, e, v):
    import features as F
    G = grid_view(c)
    groups = c.grouped(e[v])
    if not groups:
        return ABSENT
    cells = [u & G.cells for u in groups.values()]
    cells = [u for u in cells if u]
    if not cells:
        return ABSENT
    return proportion(frozenset(u) in G.component_set for u in cells)


def box_columns_of_input_size(c, e):
    G = grid_view(c)
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.box_sets() and c.box_sets()[col[0]][1] and len(c.box_sets()[col[0]][1]) <= 200 and c.sizes.get(c.box_sets()[col[0]][0]) == (G.H, G.W)]


@operator(memo=True, reads=('input',))
def boxes_inside_input(c, e, v):
    """The boxes of a column that lie wholly in the input, as first row, last row, first column, last column."""
    H, W = len(c.gi), len(c.gi[0])
    spans = [(t, H - 1 - d, l, W - 1 - r) for t, d, l, r in c.box_sets()[c.cols[e[v]][0]][1]]
    real = [s for s in spans if 0 <= s[0] <= s[1] < H and 0 <= s[2] <= s[3] < W]
    return real if real and sum((s[1] - s[0] + 1) * (s[3] - s[2] + 1) for s in real) <= 20000 else ABSENT


@operator(reads=('input',))
def boxes_with_unique_color(c, e, v):
    real = boxes_inside_input(v)(c, e)
    if real is ABSENT:
        return ABSENT
    return proportion(len({c.gi[r][k] for r in range(s[0], s[1] + 1) for k in range(s[2], s[3] + 1)}) == 1 for s in real)


@operator(reads=('input',))
def boxes_with_unique_border_color(c, e, v):
    real = boxes_inside_input(v)(c, e)
    if real is ABSENT:
        return ABSENT
    return proportion(len({c.gi[r][k] for r in range(s[0], s[1] + 1) for k in range(s[2], s[3] + 1) if r in (s[0], s[1]) or k in (s[2], s[3])}) == 1 for s in real)


@operator(reads=('input',))
def boxes_are_component_boxes(c, e, v):
    real = boxes_inside_input(v)(c, e)
    if real is ABSENT:
        return ABSENT
    G = grid_view(c)
    return proportion(s in G.component_boxes for s in real)


def declare_input():
    cells = few_rows(lib_output_cell_columns)
    for name in ('reflection agreement, greatest proportion', 'rotation agreement, greatest proportion', 'translation agreement along rows or columns, greatest proportion'):
        BASE_STAGE.define('{n},{x} ' + name, agreement_measure(n, x, name), n=few_rows(columns_with_few_cells), x=columns(('Color',)))
    BASE_STAGE.define('{n} is a union of input components', is_union_of_components(n), n=cells)
    BASE_STAGE.define('{n} groups of %s that are input components, proportion' % GROUPS, groups_are_components(n), n=cells)
    boxes = few_rows(box_columns_of_input_size)
    BASE_STAGE.define('{b} boxes of one input color, proportion', boxes_with_unique_color(b), b=boxes)
    BASE_STAGE.define('{b} boxes whose border is one input color, proportion', boxes_with_unique_border_color(b), b=boxes)
    BASE_STAGE.define('{b} boxes that are the box of an input component, proportion', boxes_are_component_boxes(b), b=boxes)


def lib_output_cell_columns(c, e):
    return RO.cell_columns_of(INPUT)(c, e)


declare_input()


def claims(tab, ex, sizes, gi):
    """{feature: value}: what the table's rows at example ex state about the input grid gi."""
    import features as F
    import vocabulary as LB
    rows = F.rows_at(tab, ex)
    if not rows or len(rows) > MAX_ROWS:
        return {}
    sizes = dict(sizes)
    return BASE_STAGE.run(LB.Context(tab, rows, ex, gi, None, sizes, F.cellsets(tab, rows, sizes)))
