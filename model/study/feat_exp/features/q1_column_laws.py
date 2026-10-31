"""Q1 Properties of the columns of X that hold on every row.

Each key is one test, 1 where it holds and 0 where it does not, and None where it cannot apply (the columns it
reads are not in X, or X has too few rows). Every test reads X, the train grids and, for the atom-level tests,
the candidate's form with `Pair.clause.x_columns`; none reads gold. The type restrictions are the ones the studies
found necessary: a pair of equal columns is a fault only for the types named, since gold has equal Box, Offset,
Number and Axis columns (copies of a component's key).
"""
import collections as C
import itertools

from featlib import feature

BOXLIKE = ('Position', 'Box', 'Offset')
MAX_ROWS = 3000


# ------------------------------------------------------------------------------------------------ table series

class _Extents:
    """ext[i] of a `_Series`: the (extent, status) of each row of column i, made on first use."""

    def __init__(self, cells):
        self._cells, self._made = cells, {}

    def __getitem__(self, i):
        if i not in self._made:
            self._made[i] = [(c.get('extent'), c.get('extent_status')) for c in self._cells[i]]
        return self._made[i]


class _Series:
    """The values of X column by column, over every row of every entry.

    vals[i]: the value tuples of column i, one per row; ext[i]: (extent, status) per row; train[k]:
    the train index of the entry of row k, None for a row of a test entry; test[k]: its test index, None for a row
    of a train entry. n: the number of rows. The series holds the rows of the test entries too: the tests of this module
    read X's own content, and a test input's rows are rows of X."""

    def __init__(self, x):
        cols = x.columns()
        self.cols = cols
        self.vals = [[] for _ in cols]
        self._cells = [[] for _ in cols]
        self.train, self.test = [], []
        n = len(cols)
        for e in x.all_entries:
            rows = e['rows']
            tr, te = e.get('train'), e.get('test') if 'train' not in e else None
            if all(len(r) == n for r in rows):  # by column: a row of another length takes the loop below
                self.train.extend([tr] * len(rows))
                self.test.extend([te] * len(rows))
                for i in range(n):
                    cells = [r[i] for r in rows]
                    self._cells[i].extend(cells)
                    self.vals[i].extend([tuple(c.get('value') or ()) for c in cells])
                continue
            for r in rows:
                self.train.append(tr)
                self.test.append(te)
                for i, c in enumerate(r):
                    self._cells[i].append(c)
                    self.vals[i].append(tuple(c.get('value') or ()))
        self.n = len(self.train)
        self.ext = _Extents(self._cells)

    def idx(self, pred):
        return [i for i, c in enumerate(self.cols) if pred(c)]


def _series(p):
    x = p.x
    s = getattr(x, '_q1_series', None)
    if s is None:
        s = x._q1_series = _Series(x)
    return s


def _equal(s, i, j):
    a, b = s.vals[i], s.vals[j]
    return all(u == v for u, v in zip(a, b))


def _tied(p):
    """The pairs of X column indices that the form makes equal: two columns that hold one label, or two labels that a positive `=` compares
    (directly or through other `=` atoms). Two columns of such a pair are equal by construction, not through the table's content."""
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    body = p.clause.body
    if body is not None:
        for a in body.atoms:
            if a.operator == '=' and not a.negated and a.first is not None and a.second is not None:
                if a.first.label is not None and a.second.label is not None:
                    parent[find(a.first.label)] = find(a.second.label)
    label = {}
    for name, v in p.clause.x_columns.items():
        col = p.x.column(name)
        if v is not None and col is not None:
            label[col.index] = find(v.label)
    return label


def _pairs(s, cols, tied=None):
    for i, j in itertools.combinations(cols, 2):
        if tied is not None and i in tied and j in tied and tied[i] == tied[j]:
            continue
        yield i, j


# ------------------------------------------------------------------------------------------------ equal columns

@feature
def q1_equal_cols(p):
    """Two columns of one type that hold the same value in every row. `pos_equal`: two Position columns (any frame), the value not constant
    over the rows. `dir_equal`, `diagdir_equal`, `color_equal`: two columns of that type (constant columns included);
    `dir_diag_color_equal` is 1 when any of the three is. `ident_equal`: two Ident columns. `pos_input_equal`, `box_input_equal`: two Position (Box)
    columns with the frame tag `input`. Two columns that the form ties (one label, or labels compared by a positive `=`) do not count. A key is None
    without two columns of its kind left or (for Ident, the input-frame keys) without 2 rows."""
    s = _series(p)
    if s.n == 0:
        return None
    out = {}
    tied = _tied(p)

    def test(name, pred, constant_ok=True, min_rows=1):
        cols = s.idx(pred)
        if len(cols) < 2 or s.n < min_rows:
            out[name] = None
            return
        hit = 0
        for i, j in _pairs(s, cols, tied):
            if _equal(s, i, j) and (constant_ok or len(set(s.vals[i])) > 1):
                hit = 1
                break
        out[name] = hit

    test('pos_equal', lambda c: c.type == 'Position', constant_ok=False)
    test('dir_equal', lambda c: c.type == 'Dir')
    test('diagdir_equal', lambda c: c.type == 'DiagDir')
    test('color_equal', lambda c: c.type == 'Color')
    test('ident_equal', lambda c: c.type == 'Ident', min_rows=2)
    test('pos_input_equal', lambda c: c.type == 'Position' and c.frame == 'input', min_rows=2)
    test('box_input_equal', lambda c: c.type == 'Box' and c.frame == 'input', min_rows=2)
    parts = [out[k] for k in ('dir_equal', 'diagdir_equal', 'color_equal')]
    out['dir_diag_color_equal'] = None if all(v is None for v in parts) else int(any(parts))
    return out


# ------------------------------------------------------------------------------------------------ off the grid

@feature
def q1_off_grid(p):
    """A cell outside its grid. `pos_off2`: a Position column has a margin of -2 or less. `pos_off30`: a Position column has a margin
    below 0 in 30% or more of the rows. `frame_bad`: a Position or Box column with the frame tag `input` (`output`) whose resolved
    extent is not the example's input (output) grid size (a row of a test entry is compared with the test input's size, and only in the frame `input`: a test output is not known); None at an INIT point (its ports can have a frame tag of `input` over a strip of the grid), at a Det point (X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row's extent would be compared with another example's grid) and where X has an Example column. `num_neg`: a Number cell is negative.
    A key is None without a column of its kind."""
    s = _series(p)
    out = {'pos_off2': None, 'pos_off30': None, 'frame_bad': None, 'num_neg': None}
    if s.n == 0:
        return None
    pos = s.idx(lambda c: c.type == 'Position')
    if pos:
        out['pos_off2'] = out['pos_off30'] = 0
        for i in pos:
            vals = [v for v in s.vals[i] if len(v) == 4]
            if not vals:
                continue
            if any(m <= -2 for v in vals for m in v):
                out['pos_off2'] = 1
            if sum(1 for v in vals if min(v) < 0) * 10 >= 3 * len(vals):
                out['pos_off30'] = 1
    framed = s.idx(lambda c: c.type in ('Position', 'Box') and c.frame in ('input', 'output'))
    if framed and not p.kind.startswith('INIT') and p.kind != 'Det' and not s.idx(lambda c: c.type == 'Example'):
        examples = p.examples()
        size = {}
        for e in examples:
            size[e.index] = {'input': e.input.size, 'output': e.output.size}
        test_size = [g.size for g in p.test_inputs]
        out['frame_bad'] = 0
        for i in framed:
            frame = s.cols[i].frame
            for t, u, (ext, status) in zip(s.train, s.test, s.ext[i]):
                if not (status == 'resolved' and ext and len(ext) == 2):
                    continue
                if u is not None:  # a test row: only the input grid is known
                    want = test_size[u] if frame == 'input' and u < len(test_size) else None
                else:
                    want = size[t][frame] if t in size else None
                if want is not None and tuple(ext) != want:
                    out['frame_bad'] = 1
                    break
    nums = s.idx(lambda c: c.type == 'Number')
    if nums:
        out['num_neg'] = int(any(v[0] < 0 for i in nums for v in s.vals[i] if len(v) == 1))
    return out


# ------------------------------------------------------------------------------------------------ box algebra

@feature
def q1_neg_pair(p):
    """`neg_pair`: two Position, Box or Offset columns i and j with j = minus i (every margin negated) and i nonzero in every row,
    over the first 3000 rows. None without two such columns."""
    s = _series(p)
    cols = s.idx(lambda c: c.type in BOXLIKE)
    if len(cols) < 2 or s.n == 0:
        return None
    n = min(s.n, MAX_ROWS)
    for i, j in _pairs(s, cols):
        a, b = s.vals[i][:n], s.vals[j][:n]
        if all(len(u) == 4 and any(u) and tuple(-t for t in u) == v for u, v in zip(a, b)):
            return 1
    return 0


def _label_columns(p):
    """{label: index of the X column that holds it}, for the candidate body's labels."""
    out = {}
    for name, v in p.clause.x_columns.items():
        col = p.x.column(name)
        if v is not None and col is not None and v.label not in out:
            out[v.label] = col.index
    return out


def _atom_columns(p, relation):
    """For each positive atom of the candidate body that reads `relation`: {column name: index of the X column of its label}."""
    body = p.clause.body
    if body is None:
        return []
    held = _label_columns(p)
    out = []
    for a in body.atoms:
        if a.relation != relation or a.negated or a.quantifier or a.interface is None:
            continue
        cols = {}
        for arg in a.arguments:
            if arg.label is not None and arg.label in held and arg.name not in cols:
                cols[arg.name] = held[arg.label]
        out.append(cols)
    return out


def _any(results):
    results = [r for r in results if r is not None]
    return None if not results else int(any(results))


@feature
def q1_atom_laws(p):
    """Laws of a `compose` or `apply` atom's columns, in X. Over the positive atoms of the candidate's body whose columns are held by
    X (any atom firing gives 1; None without such an atom). `compose_ab_equal`: A equals B on some row. `compose_c_eq_a`: C equals A on every
    row. `compose_c_const`: C has one value over all rows. `apply_pout_eq_p`: P_out equals P on every row. `apply_pout_const`: P_out has one value
    over all rows."""
    s = _series(p)
    out = dict.fromkeys(('compose_ab_equal', 'compose_c_eq_a', 'compose_c_const', 'apply_pout_eq_p', 'apply_pout_const'))
    if s.n == 0:
        return None
    ab, ca, cc = [], [], []
    for cols in _atom_columns(p, 'compose'):
        if 'A' in cols and 'B' in cols:
            ab.append(any(u == v for u, v in zip(s.vals[cols['A']], s.vals[cols['B']])))
        if 'C' in cols and 'A' in cols:
            ca.append(_equal(s, cols['C'], cols['A']))
        if 'C' in cols:
            cc.append(len(set(s.vals[cols['C']])) == 1)
    pe, pc = [], []
    for cols in _atom_columns(p, 'apply'):
        if 'P_out' in cols and 'P' in cols:
            pe.append(_equal(s, cols['P_out'], cols['P']))
        if 'P_out' in cols:
            pc.append(len(set(s.vals[cols['P_out']])) == 1)
    out['compose_ab_equal'] = _any(ab)
    out['compose_c_eq_a'] = _any(ca)
    out['compose_c_const'] = _any(cc)
    out['apply_pout_eq_p'] = _any(pe)
    out['apply_pout_const'] = _any(pc)
    return out


# ------------------------------------------------------------------------------------------------ box measures

@feature
def q1_divide_degenerate(p):
    """A `divide` atom that splits nothing, in X (over the positive divide atoms of the candidate's body, a label that X does not
    hold is skipped; any atom firing gives 1; None without a testable atom). `divide_rem_const`: Remainder has one value over all rows.
    `divide_rem_eq_t`: Remainder equals T on every row. `divide_part_const`: Part has one value. `divide_t_const`: T has one value.
    `divide_degenerate` is 1 when one of the four is."""
    s = _series(p)
    keys = ('divide_rem_const', 'divide_rem_eq_t', 'divide_part_const', 'divide_t_const')
    got = {k: [] for k in keys}
    if s.n == 0:
        return None
    for cols in _atom_columns(p, 'divide'):
        if 'Remainder' in cols:
            got['divide_rem_const'].append(len(set(s.vals[cols['Remainder']])) == 1)
            if 'T' in cols:
                got['divide_rem_eq_t'].append(_equal(s, cols['Remainder'], cols['T']))
        if 'Part' in cols:
            got['divide_part_const'].append(len(set(s.vals[cols['Part']])) == 1)
        if 'T' in cols:
            got['divide_t_const'].append(len(set(s.vals[cols['T']])) == 1)
    out = {k: _any(v) for k, v in got.items()}
    out['divide_degenerate'] = _any([v for k in keys for v in got[k]])
    return out


# ------------------------------------------------------------------------------------------------ components

@feature
def q1_zero_number(p):
    """`number_all_zero`: at an INIT point, a Number column that is 0 in every row of every context (gold has such a column, next to a
    nonzero one, in Rule tables; None at other points). `number_all_zero_only`: X has at least 2 rows and every Number column is 0 in every row.
    None without a Number column or without rows."""
    s = _series(p)
    nums = s.idx(lambda c: c.type == 'Number')
    if not nums or s.n == 0:
        return None
    zero = [all(v == (0,) for v in s.vals[i]) for i in nums]
    return {'number_all_zero': int(any(zero)) if p.kind.startswith('INIT') else None,
            'number_all_zero_only': int(all(zero)) if s.n >= 2 else None}


# ------------------------------------------------------------------------------------------------ count agreement

def _background(cells):
    c = C.Counter(v for row in cells for v in row)
    top = max(c.values())
    return min(k for k, n in c.items() if n == top)


def _components(cells, bg, eight):
    h, w = len(cells), len(cells[0])
    seen = set()
    n = 0
    for r in range(h):
        for c in range(w):
            if cells[r][c] == bg or (r, c) in seen:
                continue
            n += 1
            seen.add((r, c))
            stack = [(r, c)]
            while stack:
                y, x = stack.pop()
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if (dy or dx) and (eight or not (dy and dx)):
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < h and 0 <= xx < w and cells[yy][xx] != bg and (yy, xx) not in seen:
                                seen.add((yy, xx))
                                stack.append((yy, xx))
    return n


def _grid_counts(e):
    """The counts read off one train example: sides, areas, cells off the background, colors, 4- and 8-connected components of
    the input, and (on equal sizes) the changed cells."""
    i, o = e.input.cells, e.output.cells
    bi, bo = _background(i), _background(o)
    d = {'Hi': e.input.height, 'Wi': e.input.width, 'Ho': e.output.height, 'Wo': e.output.width,
         'Ai': e.input.height * e.input.width, 'Ao': e.output.height * e.output.width,
         'fg_i': sum(v != bi for row in i for v in row), 'fg_o': sum(v != bo for row in o for v in row),
         'col_i': len({v for row in i for v in row}), 'col_o': len({v for row in o for v in row}),
         'ncol_i': len({v for row in i for v in row if v != bi}), 'ncol_o': len({v for row in o for v in row if v != bo}),
         'cc8_i': _components(i, bi, True), 'cc8_o': _components(o, bo, True), 'cc4_i': _components(i, bi, False)}
    if e.same_size:
        d['chg'] = len(e.changed())
    return d


@feature
def q1_count_agree(p):
    """Gold-positive: a count of X equals a count read off the train grids in every example. The examples are the entries of X with
    rows (model 0), at least 2; the count is X's row count (`rows_match`) or the number of distinct values of one column other than
    an Example column (`distinct_match`), and it must take 2 or more values over the examples. The grid counts are the sides, areas, cells off the
    most common color, colors, 4- and 8-connected components, and on equal-size examples the changed cells. `count_match` is 1 when one of the two holds;
    `area_match` and `chg_match` when the matching grid count is an area (Ai or Ao), or the changed cells. The entries are the train entries: the counts are read off the train outputs too. None without 2 entries with rows. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    cols = x.columns()
    ctx = {k: ms[0] for k, ms in x.contexts().items() if ms and ms[0]}
    if len(ctx) < 2:
        return None
    exs = {e.index: e for e in p.examples()}
    if any(k[1] not in exs for k in ctx):
        return None
    counts = {}
    stats = {'rows': {k: len(rows) for k, rows in ctx.items()}}
    for i, c in enumerate(cols):
        if c.type != 'Example':
            stats[i] = {k: len({r[i] for r in rows}) for k, rows in ctx.items()}
    hits = {'rows': set(), 'distinct': set()}
    for name, st in stats.items():
        if len(set(st.values())) < 2:
            continue
        for gname in _grid_counts(exs[next(iter(ctx))[1]]):
            ok = True
            for k, v in st.items():
                t = k[1]
                if t not in counts:
                    counts[t] = _grid_counts(exs[t])
                if gname not in counts[t] or counts[t][gname] != v:
                    ok = False
                    break
            if ok:
                hits['rows' if name == 'rows' else 'distinct'].add(gname)
    both = hits['rows'] | hits['distinct']
    return {'rows_match': int(bool(hits['rows'])), 'distinct_match': int(bool(hits['distinct'])),
            'count_match': int(bool(both)), 'area_match': int(bool(both & {'Ai', 'Ao'})),
            'chg_match': int('chg' in both)}
