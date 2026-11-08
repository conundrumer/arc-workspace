"""Model input layer: what a table's Idents, colors and numbers say about the tables upstream of it and about its own cells: which objects a table
keeps of an upstream table, which colors lie under an upstream cell set, how a number stands to a cell's place, what a cell's direction meets, the shape of a graph of two columns, and what a number's parity fixes. An
Ident is compared by the object it stands for, a color only with colors, and a place only through a relation that a symmetry of the square keeps.
"""
from collections import Counter

from grammar import ABSENT, Var, operator
from vocabulary import MAX_ROWS, OWN_STAGE, columns, other_than, proportion

STEP = {'DIR_T': (-1, 0), 'DIR_B': (1, 0), 'DIR_L': (0, -1), 'DIR_R': (0, 1), 'DIAG_TL': (-1, -1), 'DIAG_TR': (-1, 1), 'DIAG_BL': (1, -1), 'DIAG_BR': (1, 1)}
NUM = ('Nat', 'Int')
GRAPHS = ('Ident', 'Position', 'Color', 'Nat', 'Int')
DIRECTIONS = ('Dir', 'Dir8', 'DiagDir')
MARGIN_OF_EDGE = {'DIR_T': 0, 'DIR_B': 1, 'DIR_L': 2, 'DIR_R': 3}

p, n, d, k, a, b, t, u = (Var(v) for v in 'p n d k a b t u'.split())


def objects(tab, rows, i):
    """The objects that the Ident column i of the rows stands for, or None where the table does not say."""
    names = tab.get('ident_values')
    if not names:
        return None
    held = {names.get(str(r[i])) for r in rows}
    return None if None in held else held


def monotone(pairs):
    """Whether, over pairs of two numbers, the second never falls or never rises as the first rises, and equal firsts have equal seconds."""
    ordered = sorted(set(pairs))
    if any(x[0] == y[0] for x, y in zip(ordered, ordered[1:])):
        return False
    steps = [y[1] - x[1] for x, y in zip(ordered, ordered[1:])]
    return all(s >= 0 for s in steps) or all(s <= 0 for s in steps)


def graph_kind(pairs):
    """(whether the undirected graph of the pairs of values, without its loops, is one path; whether it has a cycle), or None where it has no edge."""
    near = {}
    for x, y in pairs:
        if x != y:
            near.setdefault(x, set()).add(y)
            near.setdefault(y, set()).add(x)
    if not near:
        return None
    seen, parts = set(), 0
    for s in near:
        if s not in seen:
            parts += 1
            todo = [s]
            seen.add(s)
            while todo:
                for y in near[todo.pop()]:
                    if y not in seen:
                        seen.add(y)
                        todo.append(y)
    cycle = sum(len(v) for v in near.values()) // 2 > len(near) - parts
    return parts == 1 and not cycle and max(len(v) for v in near.values()) <= 2, cycle


def few_rows(dom):
    def wrapped(c, e):
        return dom(c, e) if c.rows and len(c.rows) <= MAX_ROWS else ()
    return wrapped


@operator
def parity_determines(c, e, v, w):
    """Whether a number's parity gives one value of another column at the even numbers and another at the odd numbers. Absent where the numbers have one parity."""
    i, j = e[v], e[w]
    if len({r[i] % 2 for r in c.rows}) != 2:
        return ABSENT
    at = ({str(r[j]) for r in c.rows if r[i] % 2 == 0}, {str(r[j]) for r in c.rows if r[i] % 2})
    return len(at[0]) == 1 and len(at[1]) == 1 and at[0] != at[1]


@operator(memo=True)
def undirected_graph_kind(c, e, v, w):
    return graph_kind({(str(r[e[v]]), str(r[e[w]])) for r in c.rows})


@operator
def graph_is_path(c, e, v, w):
    held = undirected_graph_kind(v, w)(c, e)
    return ABSENT if held is None else held[0]


@operator
def graph_has_cycle(c, e, v, w):
    held = undirected_graph_kind(v, w)(c, e)
    return ABSENT if held is None else held[1]


def same_type_after(v):
    """A column of a type that gives a graph, of the type of v's column, after it in the table."""
    def dom(c, e):
        i = e[v]
        ty = c.cols[i][1]
        return [(j, c.cols[j][0]) for j in range(i + 1, len(c.cols)) if c.cols[j][1] == ty] if ty in GRAPHS else ()
    return dom


def declared_cells(c, e):
    return [(i, col[0]) for i, col in enumerate(c.cols) if col[0] in c.cs]


def place_pairs(c, e, v, w):
    return {(tuple(r[e[v]]), r[e[w]]) for r in c.rows}


@operator
def number_is_margin(c, e, v, w):
    return any(all(x[m] == y for x, y in place_pairs(c, e, v, w)) for m in range(4))


def several_numbers(c, e, v, w):
    return len({y for _, y in place_pairs(c, e, v, w)}) > 1


@operator
def number_monotone_along_axis(c, e, v, w):
    if not several_numbers(c, e, v, w):
        return ABSENT
    pairs = place_pairs(c, e, v, w)
    return any(monotone((x[m], y) for x, y in pairs) for m in range(4))


@operator
def one_line_per_number(c, e, v, w):
    if not several_numbers(c, e, v, w):
        return ABSENT
    lines = {}
    for x, y in place_pairs(c, e, v, w):
        lines.setdefault(y, set()).add(x)
    return all(len({x[0] for x in s}) == 1 or len({x[2] for x in s}) == 1 for s in lines.values())


@operator
def number_is_margin_toward(c, e, v, w, m):
    usable = [(x, y, z) for x, y, z in {(tuple(r[e[v]]), r[e[w]], r[e[m]]) for r in c.rows} if y in MARGIN_OF_EDGE]
    return proportion(x[MARGIN_OF_EDGE[y]] == z for x, y, z in usable) if usable else ABSENT


# ---- a table's values against an upstream table

def upstream_tables(c, e):
    """Another table upstream of this one, with few enough rows at this example to read each one."""
    out = []
    for i, (name, tab, rows) in enumerate(c.upstream_rows()):
        if rows and len(rows) <= MAX_ROWS:
            out.append((i, name))
    return out


def upstream_columns(types=None, table=t):
    def dom(c, e):
        _, tab, _ = c.upstream_rows()[e[table]]
        return [(j, col[0]) for j, col in enumerate(tab['columns']) if types is None or col[1] in types]
    return dom


def upstream_cell_columns(table=t, frame_of=None):
    """A column of cells of the upstream table; with frame_of, in the frame of that column of this table."""
    def dom(c, e):
        name, tab, rows = c.upstream_rows()[e[table]]
        ucs = c.upstream_cells(e[table])
        want = None if frame_of is None else c.cs[c.cols[e[frame_of]][0]][0]
        return [(j, col[0]) for j, col in enumerate(tab['columns']) if col[0] in ucs and (want is None or (ucs[col[0]][0] == want and ucs[col[0]][1]))]
    return dom


@operator
def objects_relation(c, e, v, table, w):
    import features as F
    mine = objects(c.tab, c.rows, e[v])
    if mine is None:
        return ABSENT
    _, ut, urows = c.upstream_rows()[e[table]]
    theirs = objects(ut, urows, e[w])
    return F.setrel2(mine, theirs) if theirs else ABSENT


@operator
def objects_proportion(c, e, v, table, w):
    mine = objects(c.tab, c.rows, e[v])
    if mine is None:
        return ABSENT
    _, ut, urows = c.upstream_rows()[e[table]]
    theirs = objects(ut, urows, e[w])
    return round(len(mine & theirs) / len(theirs), 3) if theirs else ABSENT


def input_framed_upstream(c, e, table=t):
    """An upstream column of cells in the input's frame, with a cell in the input."""
    _, ut, _ = c.upstream_rows()[e[table]]
    out = []
    for j, col in enumerate(ut['columns']):
        held = c.upstream_cells(e[table]).get(col[0])
        if held is not None and held[0] == 'input' and colors_under_cells(c, held[1]):
            out.append((j, col[0]))
    return out


def colors_under_cells(c, U):
    H, W = len(c.gi), len(c.gi[0])
    return Counter(c.gi[r][q] for r, q in U if 0 <= r < H and 0 <= q < W)


def upstream_column_cells(c, e, table, w):
    _, ut, _ = c.upstream_rows()[e[table]]
    return c.upstream_cells(e[table])[ut['columns'][e[w]][0]][1]


@operator
def colors_vs_colors_under(c, e, v, table, w):
    import features as F
    return F.setrel2({r[e[v]] for r in c.rows}, set(colors_under_cells(c, upstream_column_cells(c, e, table, w))))


@operator
def contains_most_frequent_color_under(c, e, v, table, w):
    under = colors_under_cells(c, upstream_column_cells(c, e, table, w))
    top = max(under.values())
    return any(under[y] == top for y in {r[e[v]] for r in c.rows})


@operator
def ray_meets(c, e, v, w, table, y):
    """The proportion of the row's pairs of a cell and a direction whose ray from the cell meets the upstream cell set."""
    if len(c.rows) > 1000:
        return ABSENT
    Hf, Wf = c.sizes.get(c.cs[c.cols[e[v]][0]][0], (0, 0))
    U = upstream_column_cells(c, e, table, y)
    seen = []
    for cell, way in {((r[e[v]][0], r[e[v]][2]), r[e[w]]) for r in c.rows}:
        s = STEP[way]
        a_, b_ = cell[0] + s[0], cell[1] + s[1]
        hit = False
        while 0 <= a_ < Hf and 0 <= b_ < Wf:
            if (a_, b_) in U:
                hit = True
                break
            a_, b_ = a_ + s[0], b_ + s[1]
        seen.append(hit)
    return proportion(seen)


def declare_values():
    OWN_STAGE.define('{a} its parity determines {b}', parity_determines(a, b), a=few_rows(columns(NUM)), b=other_than(a))
    OWN_STAGE.define('{a}-{b} graph is one path', graph_is_path(a, b), also='{b}-{a} graph is one path', a=few_rows(columns()), b=same_type_after(a))
    OWN_STAGE.define('{a}-{b} graph has a cycle', graph_has_cycle(a, b), also='{b}-{a} graph has a cycle', a=few_rows(columns()), b=same_type_after(a))
    OWN_STAGE.define("{p},{n} is the cell's margin toward one edge", number_is_margin(p, n), p=few_rows(declared_cells), n=columns(NUM))
    OWN_STAGE.define('{p},{n} is monotone along one axis', number_monotone_along_axis(p, n), p=few_rows(declared_cells), n=columns(NUM))
    OWN_STAGE.define('{p},{n} holds one line per value', one_line_per_number(p, n), p=few_rows(declared_cells), n=columns(NUM))
    OWN_STAGE.define("{p},{d},{k} is the cell's margin toward it, proportion", number_is_margin_toward(p, d, k), p=few_rows(declared_cells), d=columns(DIRECTIONS), k=columns(NUM))
    tables = few_rows(upstream_tables)
    OWN_STAGE.define('{a} objects vs {t}.{u}', objects_relation(a, t, u), t=tables, a=columns(('Ident',)), u=upstream_columns(('Ident',)))
    OWN_STAGE.define('{a} objects proportion of {t}.{u}', objects_proportion(a, t, u), t=tables, a=columns(('Ident',)), u=upstream_columns(('Ident',)))
    OWN_STAGE.define('{a} vs the colors under {t}.{u}', colors_vs_colors_under(a, t, u), t=tables, a=columns(('Color',)), u=input_framed_upstream)
    OWN_STAGE.define('{a} includes the most frequent color under {t}.{u}', contains_most_frequent_color_under(a, t, u), t=tables, a=columns(('Color',)), u=input_framed_upstream)
    OWN_STAGE.define('{p},{d} meets {t}.{u}, proportion', ray_meets(p, d, t, u), t=tables, p=declared_cells, d=columns(DIRECTIONS), u=upstream_cell_columns(frame_of=p))


declare_values()
