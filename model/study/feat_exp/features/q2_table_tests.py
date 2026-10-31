"""Tests of the whole candidate table X against the train grids and the available tables (content filters).

Every key is 0 or 1 unless its description says it is a number, and None where the test cannot apply.

contains_input: X holds the whole `input` table in every example (X has the column types of `input`).
    equal: X's rows equal the table's rows in every example. strict_superset: X's rows contain them and have more.
final_vs_output: tests that hold X against the train outputs. They apply only where `OUT` reads the candidate's relation
(`p.out_reads` is True), the clause that `OUT` paints from; `OUT` picks one Position (or Box) column and one Color column
of X, and a key that depends on the pair fires only if every pair fails.
    fewer_rows: X has fewer rows than the train output has cells in some example.
    differs: for every (Position or Box, Color) column pair of X (a column counts if it admits the type), some example
    paints a position another color, holds a position the output lacks, or lacks an output position.
    same_every_example: X has rows and the same rows in every example.
available_size: tests of X against the available tables.
    equals_input: X's columns are columns of the `input` table (same name and type) and its rows equal that table's rows
    on them, in every example.
    far_larger: in some example X has at least 6 times the rows of the largest available table of that example.
    equals_available: the same as equals_input, for any available table.
    rows_per_cell: a number; the most, over examples and Position columns that lie on the input grid, of rows per distinct
    grid cell.
before_order: tests of an Order `before` table, at the Order `before` port of an INIT.
    not_strict_order: in some example and key group, a row (a, a), a pair (a, b) with its converse (b, a), or (a, b) and
    (b, c) without (a, c).
    against_dir: its columns are Boxes or Positions, it has a Dir key, and fewer than half of its rows have a's margin at
    the Dir value below b's.
negative_input_margin: an input-frame Position or Box column has a value with a negative margin.
containment: tests of a Position column against the Box column that holds it.
    interior_misses_changed_edge: the cells of a Position column all lie strictly inside their box (groups of 2 cells or
    more), and at least 90% of the ring cells of those boxes that the train output changes are not held by that column.
    box_below_frame: a Box column with no frame tag has a negative margin.
    box_edge_unreached: for some Position and Box column pair (the Box column has no frame tag or the Position's tag),
    every cell lies inside its box, none is on the box edge,
    the Box margins are not negative, and a box has 2 cells or more on average.

Test entries. A table written with test rows has entries of key `test` besides the train entries. A key that holds X against
the train outputs (`fewer_rows`, `differs`, `interior_misses_changed_edge`) reads the train entries only. A key that tests
X's own content, or X against the input grids or an earlier table, reads the test entries too (`_contexts(table, True)`,
`Table.all_entries`).
"""
import collections as C

from featlib import feature

FAR_RATIO = 6
RING_MISS = 0.9


# ------------------------------------------------------------------------------------------------ reading

def _fills(column, *types):
    """Whether the column admits one of the types, so that it could fill that role in `OUT`."""
    return bool(column.types.intersection(types))


def _cell(c):
    v, e = c.get('value'), c.get('extent')
    return tuple(v or ()), (tuple(e) if e else None)


def _contexts(table, tests=False):
    """{(assignment, train): rows of its first model}; a row is the list of its cells (dicts). With `tests`, the
    test entries are in it too, under the key (assignment, ('test', test index)); the train keys are the same."""
    best = {}
    for e in (table.all_entries if tests else table.entries):
        k = e['assignment'], (e['train'] if 'train' in e else ('test', e['test']))
        if k not in best or e.get('model', 0) < best[k][0]:
            best[k] = e.get('model', 0), e['rows']
    return {k: v[1] for k, v in best.items()}


def _input_size(p, t):
    """The size of the input grid of example t: a train index, or ('test', test index); None where it is unknown."""
    if isinstance(t, tuple):
        grids = p.test_inputs
        return grids[t[1]].size if t[1] < len(grids) else None
    examples = p.examples()
    return examples[t].input.size if t < len(examples) else None


def _rowset(rows, idx=None):
    """The set of rows, each a tuple of (value, extent) cells; idx picks the columns."""
    cols = range(len(rows[0])) if idx is None and rows else idx
    return {tuple(_cell(r[i]) for i in cols) for r in rows} if rows else set()


def _values(rows, idx):
    return {tuple(tuple(r[i].get('value') or ()) for i in idx) for r in rows}


def _types(table):
    return tuple(c.type for c in table.columns())


# ------------------------------------------------------------------------------------------------ the input table

@feature
def contains_input(p):
    """X contains the whole `input` table in every example (keys equal, strict_superset); None without that table or without a shared example, or where X's column types are not the table's. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    t = p.table('input')
    x = p.x
    if t is None or not _types(x) or _types(x) != _types(t):
        return None
    xc, tc = _contexts(x, True), _contexts(t, True)  # X's rows against the table's, test inputs too
    keys = [k for k in xc if k in tc]
    if not keys or all(not xc[k] and not tc[k] for k in keys):
        return None
    eq = sup = True
    for k in keys:
        xs, ts = _rowset(xc[k]), _rowset(tc[k])
        eq &= xs == ts
        sup &= xs >= ts
    return {'equal': int(eq), 'strict_superset': int(sup and not eq)}


# ------------------------------------------------------------------------------------------------ the train output

def _output_cell(cell, h, w):
    """The (row, col) of a Position value of the output grid, or the value itself where it is not one."""
    v, e = _cell(cell)
    if e == (h, w) and len(v) == 4 and v[0] >= 0 and v[2] >= 0 and v[0] + v[1] == h - 1 and v[2] + v[3] == w - 1:
        return v[0], v[2]
    return v, e


def _differs(p, xc, examples):
    cols = p.x.columns()
    pos = [c.index for c in cols if _fills(c, 'Position', 'Box')]
    color = [c.index for c in cols if _fills(c, 'Color')]
    if not pos or not color:
        return None
    best = None  # the fewest misses over the pairs: OUT can pick any pair, so the key is 1 only if every pair has one
    for ip in pos:
        for ic in color:
            total = n = 0
            for (a, t), rows in xc.items():
                if t >= len(examples):
                    continue
                out = examples[t].output
                h, w = out.size
                n += 1
                held = C.defaultdict(set)
                for r in rows:
                    held[_output_cell(r[ip], h, w)].add(tuple(r[ic].get('value') or ()))
                for cell, colors in held.items():
                    if not (isinstance(cell[0], int) and 0 <= cell[0] < h and 0 <= cell[1] < w):
                        total += 1
                    elif colors != {(out[cell],)}:
                        total += 1
                total += sum(1 for r in range(h) for c in range(w) if (r, c) not in held)
            if n and (best is None or total < best):
                best = total
    return None if best is None else int(best > 0)


@feature
def final_vs_output(p):
    """Where `OUT` reads the candidate's relation, X against the train outputs (keys fewer_rows, differs,
    same_every_example); None elsewhere and where `p.out_reads` is None. At a Det point `fewer_rows` and `differs` are None:
    X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if not p.out_reads:
        return None
    xc = _contexts(p.x)  # fewer_rows and differs read the train outputs: the train entries only
    examples = p.examples()
    if not xc:
        return None
    det = p.kind == 'Det'
    fewer = None if det else int(any(t < len(examples) and len(rows) < examples[t].output.height * examples[t].output.width
                                      for (a, t), rows in xc.items()))
    sets = [frozenset(_rowset(rows)) for rows in _contexts(p.x, True).values()]  # same_every_example: X's own rows, test too
    same = None if len(sets) < 2 else int(sum(len(r) for r in _contexts(p.x, True).values()) > 0 and len(set(sets)) == 1)
    return {'fewer_rows': fewer, 'differs': None if det else _differs(p, xc, examples), 'same_every_example': same}


# ------------------------------------------------------------------------------------------------ the available tables

def _available(p):
    return [t for t in p.available() if t.name not in ('ex_input', 'ex_output')]


def _equals(x, xc, t, tc):
    """Whether X's columns are columns of t (same name and type) and X's rows equal t's rows on them in every example."""
    tcols = {c.name: c for c in t.columns()}
    idx = []
    for c in x.columns():
        m = tcols.get(c.name)
        if m is None or m.type != c.type:
            return False
        idx.append((c.index, m.index))
    for k, rows in xc.items():
        if k not in tc:
            if isinstance(k[1], tuple):  # a test input that t has no entry for (a table without test rows)
                continue
            return False
        if _values(rows, [i for i, _ in idx]) != _values(tc[k], [j for _, j in idx]):
            return False
    return True


def _rows_per_cell(p, xc):
    """The most, over examples and Position columns that lie on the input grid, of rows per distinct grid cell."""
    best = None
    for c in p.x.columns():
        if c.type != 'Position':
            continue
        for (a, t), rows in xc.items():
            size = _input_size(p, t) if rows else None
            if size is None:
                continue
            h, w = size
            cells = []
            for r in rows:
                v, e = _cell(r[c.index])
                if e == (h, w) and len(v) == 4 and 0 <= v[0] < h and 0 <= v[2] < w:
                    cells.append((v[0], v[2]))
            if len(cells) < 0.9 * len(rows):
                continue
            m = len(rows) / len(set(cells))
            best = m if best is None else max(best, m)
    return best


@feature
def available_size(p):
    """X against the available tables (keys equals_input, far_larger, equals_available, rows_per_cell); None where X has no rows to compare. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so its rows would be compared with one example's rows of an earlier table."""
    if p.kind == 'Det':
        return None
    x = p.x
    xc = _contexts(x, True)  # X against the earlier tables and against the input grids: the test entries too
    if not xc or not x.columns():
        return None
    av = [(t, _contexts(t, True)) for t in _available(p)]
    eq = [t.name for t, tc in av if _equals(x, xc, t, tc)]
    ratio = 0.0
    for k, rows in xc.items():
        most = max([len(tc.get(k, [])) for _, tc in av] or [0])
        if most:
            ratio = max(ratio, len(rows) / most)
    return {'equals_input': int('input' in eq), 'far_larger': int(ratio >= FAR_RATIO),
            'equals_available': int(bool(eq)), 'rows_per_cell': _rows_per_cell(p, xc)}


# ------------------------------------------------------------------------------------------------ Order.before

def _at_before(p):
    found = p.ports_before()
    return found is not None and found[0] == 'Order' and found[1] == 'before'


def _breaks_order(cols, x):
    """Whether some example and key group has a reflexive row, a symmetric pair or an intransitive triple."""
    if len(cols) < 2 or cols[-1].type != cols[-2].type:
        return None
    for e in x.all_entries:
        groups = C.defaultdict(set)
        for r in _rowset(e['rows']):
            groups[r[:-2]].add((r[-2], r[-1]))
        for pairs in groups.values():
            succ = C.defaultdict(set)
            for a, b in pairs:
                succ[a].add(b)
            for a, b in pairs:
                if a == b or (b, a) in pairs or any((a, c) not in pairs for c in succ.get(b, ())):
                    return True
    return False


def _against_dir(cols, x):
    """Whether fewer than half of the rows have the first Box or Position's margin at the Dir value below the second's."""
    if len(cols) < 4 or cols[-1].type != cols[-2].type or cols[-1].type not in ('Box', 'Position'):
        return None
    dirs = [c.index for c in cols[:-2] if c.type == 'Dir']
    if not dirs:
        return None
    d = dirs[0]
    n = below = 0
    for e in x.all_entries:
        for r in {(tuple(r[d].get('value') or ()), tuple(r[-2].get('value') or ()), tuple(r[-1].get('value') or ()))
                  for r in e['rows']}:
            dv, a, b = r[0][0] if r[0] else None, r[1], r[2]
            if dv is None or len(a) != 4 or len(b) != 4 or not 0 <= dv < 4:
                continue
            n += 1
            below += a[dv] < b[dv]
    return None if n == 0 else int(below / n < 0.5)


@feature
def before_order(p):
    """An Order `before` table that is not a strict order (not_strict_order), or that runs against its Dir key (against_dir); None except at the Order `before` port."""
    if not _at_before(p):
        return None
    x = p.x
    cols = x.columns()
    return {'not_strict_order': (None if (v := _breaks_order(cols, x)) is None else int(v)),
            'against_dir': _against_dir(cols, x)}


# ------------------------------------------------------------------------------------------------ cells outside the grid

@feature
def negative_input_margin(p):
    """An input-frame Position or Box column of X has a value with a negative margin (a cell outside the grid); None without such a column."""
    cols = [c for c in p.x.columns() if c.type in ('Position', 'Box') and c.frame == 'input']
    if not cols:
        return None
    for e in p.x.all_entries:
        for r in e['rows']:
            for c in cols:
                v = r[c.index].get('value') or ()
                if len(v) == 4 and min(v) < 0:
                    return 1
    return 0


# ------------------------------------------------------------------------------------------------ containment

def _pair_stats(x, i, j):
    """(rows, rows inside their box, rows on the box edge, {(entry, box): cells}, any negative box margin)."""
    n = ins = edge = 0
    groups = C.defaultdict(set)
    neg = False
    for ei, e in enumerate(x.all_entries):
        for r in e['rows']:
            a, b = tuple(r[i].get('value') or ()), tuple(r[j].get('value') or ())
            if len(a) != 4 or len(b) != 4:
                continue
            n += 1
            neg |= min(b) < 0
            groups[ei, b].add(a)
            if all(a[k] >= b[k] for k in range(4)):
                ins += 1
                edge += any(a[k] == b[k] for k in range(4))
    return n, ins, edge, groups, neg


def _strictly_inside(st):
    n, ins, edge, groups, _ = st
    return n > 0 and ins == n and edge == 0 and sum(len(s) for s in groups.values()) / len(groups) >= 2


def _missed_ring(p, i, j):
    """(ring cells of X's boxes that the output changes, how many of them the Position column i does not hold), on the
    examples whose input and output have one size."""
    examples = p.examples()
    changed = missed = 0
    for e in p.x.entries:
        t = e['train']
        if t >= len(examples) or not examples[t].same_size:
            continue
        ex = examples[t]
        h, w = ex.input.size
        ch = ex.changed()
        held, boxes = set(), set()
        for r in e['rows']:
            (pv, pe), (bv, be) = _cell(r[i]), _cell(r[j])
            if pe == (h, w) and len(pv) == 4:
                held.add((pv[0], pv[2]))
            if be == (h, w) and len(bv) == 4:
                boxes.add(bv)
        for top, bottom, left, right in boxes:
            r0, r1, c0, c1 = top, h - 1 - bottom, left, w - 1 - right
            if r1 < r0 or c1 < c0 or r0 < 0 or c0 < 0 or r1 >= h or c1 >= w:
                continue
            for rr in range(r0, r1 + 1):
                for cc in range(c0, c1 + 1):
                    if (rr in (r0, r1) or cc in (c0, c1)) and (rr, cc) in ch:
                        changed += 1
                        missed += (rr, cc) not in held
    return changed, missed


@feature
def containment(p):
    """Position cells against their Box (keys interior_misses_changed_edge, box_below_frame, box_edge_unreached); each None where X has no column pair it reads. At a Det point `interior_misses_changed_edge` is None: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    x = p.x
    cols = x.columns()
    out = {'interior_misses_changed_edge': None, 'box_below_frame': None, 'box_edge_unreached': None}
    boxes = [c for c in cols if c.type == 'Box']
    untagged = [c for c in boxes if not c.frame]
    if untagged:
        out['box_below_frame'] = int(any(
            min(r[c.index].get('value') or (0,)) < 0 for e in x.all_entries for r in e['rows'] for c in untagged))
    tagged = [c for c in cols if c.type == 'Position' and c.frame]
    pairs = [(a.index, b.index) for a in tagged for b in boxes if b.frame in ('', a.frame)]
    if pairs:
        out['box_edge_unreached'] = 0
        for i, j in pairs:
            st = _pair_stats(x, i, j)
            if not st[4] and _strictly_inside(st):
                out['box_edge_unreached'] = 1
    pairs = [(a.index, b.index) for a in cols if a.type == 'Position' and a.frame == 'input'
             for b in boxes if b.frame in ('input', '')]
    if pairs and p.kind != 'Det' and any(ex.same_size for ex in p.examples()):
        out['interior_misses_changed_edge'] = 0
        for i, j in pairs:
            if _strictly_inside(_pair_stats(x, i, j)):
                changed, missed = _missed_ring(p, i, j)
                if changed >= 1 and missed >= RING_MISS * changed:
                    out['interior_misses_changed_edge'] = 1
    return out
