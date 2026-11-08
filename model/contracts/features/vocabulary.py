"""Model input layer: the vocabulary of the schemas (grammar.py): the context that a term reads, the stages of the library, and the operators that the modules of schemas share."""
from collections import Counter

from grammar import ABSENT, GRIDS, INPUT, LABELINGS, OUTPUT, Stage, Var, function, operator
from grids import relabeled

MAX_ROWS = 5000
MAX_CELLS = 900
MAX_GROUPS = 60
GROUPS = 'its Ident, Color and key columns'
VALUE = ('Color', 'Nat', 'Int', 'Dir', 'Dir8', 'DiagDir', 'Axis', 'Axis4', 'DiagAxis', 'D4', 'C4', 'Sym', 'Sense')

p, x, a, b, n, d, g, q = (Var(v) for v in 'p x a b n d g q'.split())
TABLE_STAGE = Stage('what reads the table alone, at an example')
UPSTREAM_STAGE = Stage('what reads the table and the tables upstream of it, at an example')
INPUT_GRID_STAGE = Stage('what reads the input grid of an example')
GRID_STAGE = Stage('what reads the grids of an example')
OWN_STAGE = Stage('what reads the input, at a task\'s own example')
BASE_STAGE = Stage('what reads the input, at a task\'s own example or a base table')
OWN_OUTPUT_STAGE = Stage('what reads the train output, at a task\'s own example')
ALL_EXAMPLES_STAGE = Stage('what reads the table at the examples of its task')
TRAIN_EXAMPLES_STAGE = Stage('what reads the train examples of its task')


_grouped = {}


class View:
    """An upstream table as a table downstream reads it."""
    __slots__ = ('name', 'tab', 'rows', 'count', 'cells', 'boxes', 'my_boxes')

    def __init__(self, name, tab, rows, count, cells, boxes, my_boxes):
        self.name, self.tab, self.rows, self.count, self.cells, self.boxes, self.my_boxes = name, tab, rows, count, cells, boxes, my_boxes


class Context:
    """A table's rows at one example, with what the features read beside them. sizes and cs as table_features gives them."""

    def __init__(self, tab, rows, ex, gi, go, sizes=None, cs=None, task=None, grids_of=None, up_tabs=None):
        self.tab, self.rows, self.ex, self.gi, self.go = tab, rows, ex, gi, go
        self.cols = tab['columns']
        self.sizes, self.cs = sizes, cs
        self.task, self.grids_of = task, grids_of
        self.up_tabs = up_tabs or {}
        self.memo = {}
        self.views, self.shared, self.name = [], {}, None

    def memo_groups(self, name, cols, rows, col):
        """The groups of a column of a table of this example, which its tables share."""
        key = ('grouped', name, col)
        if key not in self.shared:
            import features as F
            self.shared[key] = F.grouped(cols, rows, [j for j, k in enumerate(cols) if k[0] == col][0])
        return self.shared[key]

    def strings(self, i):
        """The values of the column at index i, as strings."""
        key = ('strings', i)
        held = self.memo.get(key)
        if held is None:
            held = self.memo[key] = [str(r[i]) for r in self.rows]
        return held

    def grouped(self, i):
        """{group: cells} of the column at index i, by the table's Ident, Color and key columns, or None where the table has none."""
        key = (id(self.rows), i)
        held = _grouped.get(key)
        if held is None or held[0] is not self.rows or held[1] is not self.cols:
            import features as F
            if len(_grouped) > 4000:
                _grouped.clear()
            held = _grouped[key] = (self.rows, self.cols, F.grouped(self.cols, self.rows, i))
        return held[2]

    def upstream_rows(self):
        """[(token, table, its rows at this example)] of the tables upstream of this one."""
        held = self.memo.get('upstream')
        if held is None:
            import features as F
            held = self.memo['upstream'] = [(name, tab, F.rows_at(tab, self.ex)) for name, tab in self.up_tabs.items()]
        return held

    def upstream_cells(self, i):
        """{column: (frame, set of cells)} of the i-th upstream table."""
        key = ('upstream cells', i)
        held = self.memo.get(key)
        if held is None:
            import features as F
            _, tab, rows = self.upstream_rows()[i]
            held = self.memo[key] = F.cellsets(tab, rows, dict(self.sizes))
        return held

    def box_sets(self):
        """{column: (frame, set of boxes)} of the Box columns in a frame."""
        held = self.memo.get('boxes')
        if held is None:
            import features as F
            held = self.memo['boxes'] = F.boxes(self.tab, self.rows, self.sizes)
        return held

    def array(self, grid):
        base = self.gi if grid.grid == 'input' else self.go
        return base if grid.label == 'color' else relabeled(base, grid.label)

    def size(self, grid):
        g_ = self.gi if grid.grid == 'input' else self.go
        return len(g_), len(g_[0])

    def same(self):
        return len(self.gi) == len(self.go) and len(self.gi[0]) == len(self.go[0])

    def train(self, limit, whole):
        """The contexts of the table at its train examples, or None where it has none to compare. whole: whether every example of the table must have at most limit rows."""
        rows = self.tab['rows']
        if 'task' in rows:
            return None
        if whole and (len(rows) < 2 or any(len(r) > limit for r in rows.values())):
            return None
        out = []
        for e_, r_ in rows.items():
            if e_.startswith('train/') and len(r_) <= limit:
                gi, go = self.grids_of(self.task, e_)
                if go is not None:
                    out.append(Context(self.tab, r_, e_, gi, go))
        return out if len(out) >= 2 else None

    def every(self, limit):
        """The contexts of the table at each of its examples, or None where it has fewer than two, or more than limit rows at one."""
        rows = self.tab['rows']
        if 'task' in rows or len(rows) < 2 or any(len(r) > limit for r in rows.values()):
            return None
        return [Context(self.tab, r_, e_, None, None) for e_, r_ in rows.items()]


def is_function(pairs):
    seen = {}
    return all(seen.setdefault(u, v) == v for u, v in pairs)


def proportion(flags):
    flags = list(flags)
    return round(sum(flags) / len(flags), 3) if flags else None


# ---- pure functions of sets and numbers

@function
def compare(u, v):
    return '<' if u < v else '=' if u == v else '>'


@function
def equal(u, v):
    return u == v


@function
def maximum(u):
    return max(u)


@function
def minimum(u):
    return min(u)


@function
def total(u):
    return sum(u)


@function
def all_true(u):
    return all(u)


@function
def cardinality(u):
    return len(u)


@function
def is_subset(u, v):
    return u <= v


@function
def contains(u, v):
    return v in u


@function
def intersects(u, v):
    return bool(u & v)


@function
def all_distinct(u):
    return len(set(u)) == len(u)


@function
def all_same(u):
    return len(set(u)) == 1


@function
def set_relation(u, v):
    """How two sets stand to each other."""
    if u == v:
        return 'equal'
    if not u & v:
        return 'disjoint'
    return 'subset' if u < v else 'superset' if u > v else 'overlap'


@function
def set_relation_in(u, v, universe):
    """How two subsets of a universe stand to each other."""
    if u == v:
        return 'equal'
    if not u & v:
        return 'complement' if u | v == universe else 'disjoint'
    return 'subset' if u < v else 'superset' if u > v else 'overlap'


@function
def jaccard(u, v):
    """The Jaccard index of two sets, 1 where both are empty."""
    return round(len(u & v) / len(u | v), 3) if u | v else 1.0


@operator
def guarded(c, e, guard, term):
    """The term, where the guard holds."""
    held = guard(c, e)
    return term(c, e) if held and held is not ABSENT else ABSENT


@operator
def over(c, e, items, attribute):
    """The list of the attribute of each item."""
    held = items(c, e)
    return ABSENT if held is ABSENT else [attribute(c, e, u) for u in held]


@operator
def proportion_of(c, e, items, predicate):
    """The proportion of the items for which the predicate holds. None where there are no items."""
    held = items(c, e)
    return ABSENT if held is ABSENT else proportion(predicate(c, e, u) for u in held)


# ---- what a table holds

@operator
def row_total(c, e):
    return len(c.rows)


@operator
def values(c, e, v):
    """The set of a column's values."""
    i = e[v]
    return {r[i] for r in c.rows}


@operator
def labels(c, e, v):
    """The set of a column's values as strings, for a type of value that cannot be hashed or that only equality reads."""
    i = e[v]
    return {str(r[i]) for r in c.rows}


@operator
def value_list(c, e, v):
    i = e[v]
    return [r[i] for r in c.rows]


@operator
def frequencies(c, e, v):
    """The number of rows that hold each value of a column."""
    i = e[v]
    return list(Counter(r[i] for r in c.rows).values())


@operator
def label_frequencies(c, e, v):
    i = e[v]
    return list(Counter(str(r[i]) for r in c.rows).values())


@operator
def cells(c, e, v):
    """The set of a column's cells, in its frame."""
    return c.cs[c.cols[e[v]][0]][1]


@operator
def frame_extents(c, e, v):
    return c.sizes[c.cs[c.cols[e[v]][0]][0]]


@operator(memo=True)
def groups(c, e, v):
    """The sets of cells of a column by the table's Ident, Color and key columns (GROUP BY), or ABSENT where the table has no such column."""
    held = c.grouped(e[v])
    return ABSENT if held is None else list(held.values())


@operator
def nonempty(c, e, term):
    held = term(c, e)
    return held if held is not ABSENT and len(held) else ABSENT


@operator
def several(c, e, term):
    """The term's value, where it holds at least two elements."""
    held = term(c, e)
    return held if held is not ABSENT and len(held) > 1 else ABSENT


# ---- the columns a variable may stand for

def columns(types=None):
    def dom(c, e):
        return [(i, column[0]) for i, column in enumerate(c.cols) if types is None or column[1] in types]
    return dom


def other_than(v, types=None):
    def dom(c, e):
        return [(i, column[0]) for i, column in enumerate(c.cols) if i != e[v] and (types is None or column[1] in types)]
    return dom


POSITION = columns(('Position',))


def cell_columns(grid):
    """A column of cell values in the frame of the grid, with a cell in the grid."""
    def dom(c, e):
        if not c.rows or len(c.rows) > MAX_ROWS:
            return ()
        H, W = c.size(grid)
        out = []
        for i, column in enumerate(c.cols):
            held = c.cs.get(column[0])
            if held is not None and c.sizes.get(held[0]) == (H, W) and any(0 <= r < H and 0 <= k < W for r, k in held[1]):
                out.append((i, column[0]))
        return out
    return dom


# ---- the items

def is_cell_of(v, H, W):
    return v[0] + v[1] + 1 == H and v[2] + v[3] + 1 == W and min(v) >= 0


@operator(memo=True)
def cells_in_grid(c, e, v, grid, at_least):
    """The cells of a Position column in the grid, the rows being few enough to read each one."""
    if not c.rows or len(c.rows) > MAX_ROWS:
        return ABSENT
    H, W = c.size(grid)
    i = e[v]
    cells = {(r[i][0], r[i][2]) for r in c.rows if is_cell_of(r[i], H, W)}
    return cells if len(cells) >= at_least else ABSENT


@operator(memo=True)
def rows_in_grid(c, e, v, grid, at_least):
    """The rows whose cell lies in the grid."""
    if not c.rows or len(c.rows) > MAX_ROWS:
        return ABSENT
    H, W = c.size(grid)
    i = e[v]
    rows = [r for r in c.rows if is_cell_of(r[i], H, W)]
    return rows if len(rows) >= at_least else ABSENT


@operator
def rows_if_several(c, e):
    return c.rows if len(c.rows) > 1 else ABSENT


@operator
def rows_if_any(c, e):
    return c.rows if c.rows else ABSENT


@operator
def rows(c, e):
    return c.rows


# ---- what an item holds

@operator
def column_value(c, e, r, v):
    return str(r[e[v]])


@operator
def grid_label_of_row(c, e, r, v, grid):
    """The grid's label at the cell of column v of a row, or None off the grid."""
    g_, u = c.array(grid), r[e[v]]
    return g_[u[0]][u[2]] if 0 <= u[0] < len(g_) and 0 <= u[2] < len(g_[0]) else None


@operator
def grid_label_of_cell(c, e, cell, grid):
    return c.array(grid)[cell[0]][cell[1]]


@operator
def pair(c, e, item, f1, f2):
    return (f1(c, e, item), f2(c, e, item))


@operator(reads=('input', 'output'))
def is_changed(c, e, r, v):
    u = r[e[v]]
    return c.gi[u[0]][u[2]] != c.go[u[0]][u[2]]


def moore_neighbors(g_, r, k):
    H, W = len(g_), len(g_[0])
    return [g_[r + u][k + v] if 0 <= r + u < H and 0 <= k + v < W else -1 for u in (-1, 0, 1) for v in (-1, 0, 1) if (u, v) != (0, 0)]


def moore_neighborhood(g_, r, k):
    H, W = len(g_), len(g_[0])
    return tuple(g_[r + u][k + v] if 0 <= r + u < H and 0 <= k + v < W else None for u in (-1, 0, 1) for v in (-1, 0, 1))


@operator
def row_of(c, e, cell):
    return cell[0]


@operator
def column_of(c, e, cell):
    return cell[1]


@operator
def main_diagonal(c, e, cell):
    return cell[0] - cell[1]


@operator
def anti_diagonal(c, e, cell):
    return cell[0] + cell[1]


@operator
def border_distance(c, e, cell, grid):
    H, W = c.size(grid)
    return min(cell[0], H - 1 - cell[0], cell[1], W - 1 - cell[1])


@operator
def coordinate_parity(c, e, cell):
    return (cell[0] + cell[1]) % 2


@operator
def neighbor_color_multiset(c, e, cell, grid):
    return tuple(sorted(moore_neighbors(c.array(grid), cell[0], cell[1])))


@operator
def same_color_neighbor_count(c, e, cell, grid):
    g_ = c.array(grid)
    u = g_[cell[0]][cell[1]]
    return (u, sum(y == u for y in moore_neighbors(g_, cell[0], cell[1])))


@operator
def neighborhood_of_cell(c, e, cell, grid):
    return moore_neighborhood(c.array(grid), cell[0], cell[1])


@operator
def neighborhood_of_row(c, e, r, v, grid):
    u = r[e[v]]
    return moore_neighborhood(c.array(grid), u[0], u[2])


# ---- tests

def functional(pairs, needs):
    """Whether the (src, dst) pairs make a function. needs: 'defined', that every dst has a value; 'varied', that the dsts differ; 'two', that there are two pairs; else the test does not apply."""
    if needs:
        pairs = list(pairs)
        if 'defined' in needs and any(v is ABSENT for _, v in pairs):
            return ABSENT
        if 'varied' in needs and len({v for _, v in pairs}) < 2:
            return ABSENT
        if 'two' in needs and len(pairs) < 2:
            return ABSENT
    return is_function(pairs)


@operator
def determines(c, e, over, src, dst, *needs):
    """Whether, over the items, an item's src decides its dst."""
    items = over(c, e)
    if items is ABSENT:
        return ABSENT
    if items is c.rows and src.head == 'column_value' and dst.head == 'column_value':
        return is_function(zip(c.strings(e[src.args[0]]), c.strings(e[dst.args[0]])))  # the same test, on the columns that the features of a table share
    return functional(((src(c, e, it), dst(c, e, it)) for it in items), needs)


@operator
def disjunction(c, e, *ways):
    """Whether one of the ways holds. A class of cells that the symmetries of the square take to another class is read both ways, so the answer depends on neither."""
    got = [w(c, e) for w in ways]
    return ABSENT if ABSENT in got else any(got)


@operator(reads=('input', 'output'))
def grids_same_size(c, e):
    return c.same()


@operator
def over_examples(c, e, term, limit, whole, train=True):
    """A determines over the items of every train example together, or of every example. Absent where an example has no items."""
    ctxs = c.train(limit, whole) if train else c.every(limit)
    if ctxs is None:
        return ABSENT
    over, src, dst, *needs = term.args
    seen = []
    for k in ctxs:
        items = over(k, e)
        if items is ABSENT:
            return ABSENT
        seen.extend((src(k, e, it), dst(k, e, it)) for it in items)
    return functional(seen, needs)


@operator(reads=('input', 'output'))
def all_grids_same_size(c, e, limit, whole):
    ctxs = c.train(limit, whole)
    return ctxs is not None and all(k.same() for k in ctxs)


def own(tab, ex, sizes, gi, go, out, up_tabs):
    """The features of a table at one of its task's own examples that read the input, and the train output where there is one."""
    import features as F
    rows = F.rows_at(tab, ex)
    if rows is None:
        return
    sizes = dict(sizes)
    c = Context(tab, rows, ex, gi, go, sizes, F.cellsets(tab, rows, sizes), up_tabs=up_tabs)
    OWN_STAGE.run(c, out)
    if go is not None:
        OWN_OUTPUT_STAGE.run(c, out)
