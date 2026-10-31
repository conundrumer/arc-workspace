"""Round 6, explorer Q: what the search can see of a table with extra rows that tells extras that leave the program
fitting from extras that break it.

Q1: rows where two columns of one type agree (self-pairs), and whether the rest of the relation between those two
    columns keeps one direction (no row has its mirror).
Q2: for a table keyed by an object (an Ident or Box column) with a cell column, how the keys' cell sets lie against the
    cell sets of the earlier tables: wholly inside, apart from, or across them.
"""
import itertools

import featlib
from featlib import feature

MAX_TABLE_ROWS = 20000
PAIR_TYPES = ('Color', 'Ident', 'Box', 'Position', 'Dir', 'Axis')
KEY_TYPES = ('Ident', 'Box')


def _train_list(p):
    tr = p.train
    return tr['train'] if isinstance(tr, dict) and 'train' in tr else tr


def _first(table):
    """(assignment, train) -> rows of the first model, each row a tuple of cell value tuples."""
    out = {}
    for e in table.entries:
        k = (e['assignment'], e['train'])
        if k not in out:
            out[k] = [tuple(tuple(c['value']) for c in r) for r in e['rows']]
    return out


@feature
def q1_diag_stratum(p):
    """Q1: over every pair of X columns of one type (Color, Ident, Box, Position, Dir, Axis; Position and Box also need
    one frame tag), on the distinct (a, b) value pairs of each model: `diag` (the largest share of pairs with a = b),
    `mirror` (the largest share of the pairs with a != b whose reverse (b, a) is also a pair), `clean_diag` (column
    pairs with a = b rows, some a != b row and no mirrored pair), `mirror_cols` (column pairs with a mirrored pair),
    `diag_rows` (the largest share of X's rows with a = b). None without such a pair of columns or below 2 rows."""
    t = p.x
    fields = t.fields
    cols = [j for j, f in enumerate(fields) if f['type'] in PAIR_TYPES]
    pairs = [(a, b) for a, b in itertools.combinations(cols, 2)
             if fields[a]['type'] == fields[b]['type']
             and (fields[a]['type'] not in ('Position', 'Box') or fields[a].get('frame', '') == fields[b].get('frame', ''))]
    if not pairs:
        return None
    models = [[tuple(tuple(c['value']) for c in r) for r in e['rows']] for e in t.entries]
    if sum(len(m) for m in models) < 2:
        return None
    diag = mirror = diag_rows = 0.0
    clean = mcols = 0
    for a, b in pairs:
        n_pair = n_diag = n_off = n_mir = n_rows = n_row_diag = 0
        for rows in models:
            ps = {(r[a], r[b]) for r in rows}
            n_rows += len(rows)
            n_row_diag += sum(1 for r in rows if r[a] == r[b])
            n_pair += len(ps)
            d = sum(1 for x, y in ps if x == y)
            n_diag += d
            off = [(x, y) for x, y in ps if x != y]
            n_off += len(off)
            n_mir += sum(1 for x, y in off if (y, x) in ps)
        if not n_pair:
            continue
        diag = max(diag, n_diag / n_pair)
        diag_rows = max(diag_rows, n_row_diag / n_rows if n_rows else 0.0)
        if n_off:
            mirror = max(mirror, n_mir / n_off)
        if n_diag and n_off and not n_mir:
            clean += 1
        if n_mir:
            mcols += 1
    return {'diag': diag, 'mirror': mirror, 'clean_diag': clean, 'mirror_cols': mcols, 'diag_rows': diag_rows}


def _cells(table, j):
    """(assignment, train) -> set of the column's values, in the first model."""
    return {k: {r[j] for r in rows} for k, rows in _first(table).items()}


@feature
def q2_key_split(p):
    """Q2: for each X key column (Ident or Box, at least 2 values in some context) and each X Position column with frame
    `input`, the cell set of every (context, key) against the input-frame Position column of each earlier table that
    does not hold every cell of the grid: `contained` (the largest share of the keys whose cells all lie in that
    column), `disjoint` (the largest share with no cell in it), `split` (the largest of min(contained, 1 - contained)),
    `n_split` (triples of key, cell column and earlier column with a key inside and a key not inside), `triples`, and
    `small_in` and `small_apart` (the shares of keys inside and apart from the earlier column with the fewest
    distinct cells over all contexts, the most specific earlier cell set). First model of each table per context. None
    without a key column, a cell column or an earlier cell column.

    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so its rows would be compared with one example's rows of an earlier table.
    """
    if p.kind == 'Det':
        return None
    t = p.x
    fields = t.fields
    keys = [j for j, f in enumerate(fields) if f['type'] in KEY_TYPES]
    cellcols = [j for j, f in enumerate(fields) if f['type'] == 'Position' and f.get('frame', '') == 'input']
    if not keys or not cellcols:
        return None
    train = _train_list(p)
    area = {i: len(ex['input']) * len(ex['input'][0]) for i, ex in enumerate(train)}
    xfirst = _first(t)
    earlier = []
    for tb in p.available():
        if sum(len(e['rows']) for e in tb.entries) > MAX_TABLE_ROWS:
            continue
        for j, f in enumerate(tb.fields):
            if f['type'] == 'Position' and f.get('frame', '') == 'input':
                cs = _cells(tb, j)
                full = all(len(s) >= area.get(k[1], 1 << 30) for k, s in cs.items() if s)
                if cs and not full:
                    earlier.append(cs)
    if not earlier:
        return None
    best_in = best_out = best_split = 0.0
    n_split = triples = 0
    size = [sum(len(v) for v in cs.values()) or 1 << 30 for cs in earlier]
    small = min(range(len(earlier)), key=lambda i: size[i])
    small_in = small_apart = None
    for k in keys:
        for c in cellcols:
            if k == c:
                continue
            units = []
            for ctx, rows in xfirst.items():
                by = {}
                for r in rows:
                    by.setdefault(r[k], set()).add(r[c])
                if len(by) >= 1:
                    units.extend((ctx, s) for s in by.values())
            if len(units) < 2:
                continue
            for ei, cs in enumerate(earlier):
                n = inside = apart = 0
                for ctx, s in units:
                    ref = cs.get(ctx)
                    if ref is None:
                        continue
                    n += 1
                    inter = len(s & ref)
                    inside += inter == len(s)
                    apart += inter == 0
                if n < 2:
                    continue
                triples += 1
                share = inside / n
                best_in = max(best_in, share)
                best_out = max(best_out, apart / n)
                best_split = max(best_split, min(share, 1 - share))
                n_split += 0 < inside < n
                if ei == small:
                    small_in = max(small_in or 0.0, share)
                    small_apart = max(small_apart or 0.0, apart / n)
    if not triples:
        return None
    out = {'contained': best_in, 'disjoint': best_out, 'split': best_split, 'n_split': n_split, 'triples': triples}
    if small_in is not None:
        out['small_in'] = small_in
        out['small_apart'] = small_apart
    return out
