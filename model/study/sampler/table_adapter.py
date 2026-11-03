"""The one adapter that reads the rows of a table. RelTable, S.summary, Gate.suits, cell_masks and the policy's per-table feature code get rows through it alone.

It calls the export with rows=True: the full TableRows at each assignment, no Count entry. When these features move into the engine's `arclog-features`
crate, the switch to the TableVector is in this module only.

  export(dec, task, case, before)    the step_tables result (ct) at decoder dec; each result goes to the dev row store when that is on
  tables(ct, slots)                  the AssignmentSummaries of ct (assignment_summaries.assignment_summaries), the last few kept
  parse_table(ct, js, with_rows)     the table of rows js of ct, in the parsed form that S's consumers read: labels, types, widths, frames, entries
  entries(ct, j)                     (example kind, example index, rows matrix) of each complete entry of row j
  summary(tb), rows_with_models(tb)  per entry counts, and the rows with their assignments (see S)
"""
import collections
import functools
import math

import numpy as np
from sample import M, arclog

import row_store
import assignment_summaries as TR

NOT_EXPORTED = 6  # the kind of an entry of a rows=False result: its row count alone
UNDEFINED = 2  # the kind of an entry of a model that is Undefined on its example: no rows
KEEP = 4  # the results whose AssignmentSummaries tables() keeps
_kept = []  # [(ct, rows)], the last KEEP


def export(dec, task, case, before, rows=True):
    """arclog.step_tables(dec, ...) in the layout of one row per table at an assignment. before: the result of the step before, or None. rows False gives the counts, the TableHash and
    the TableVector with no row buffers; the dev row store, where it is on, needs the rows of each result, so it makes rows True."""
    return arclog.step_tables(dec, task, case, True, before, by_assignment=True, rows=bool(rows) or bool(row_store.DIR))


@functools.cache
def index():
    """{TableVector name: its place in AssignmentSummary.features}."""
    return {n: i for i, n in enumerate(arclog.table_feature_names())}


def feature(r, name):
    """The value of TableVector entry `name` in AssignmentSummary r."""
    return float(r.features[index()[name]])


def pooled(rs, name):
    """The value of TableVector entry `name` for one table, whose AssignmentSummaries are rs (one per assignment; each assignment has every example, so each has as many entries as
    the others). lmean is the log of 1 plus the mean over the assignments of the mean rows; lmax and nt take the maximum over assignments; the rest take the mean."""
    v = [feature(r, name) for r in rs]
    if name == 'lmean':
        return math.log1p(sum(math.expm1(x) for x in v) / len(v))
    return max(v) if name in POOL_MAX else sum(v) / len(v)


POOL_MAX = frozenset({'lmax', 'nt'})


def tables(ct, slots=None):
    """assignment_summaries(ct, slots), kept for the last KEEP results by identity of ct. Each new result goes to the dev row store where it is on."""
    for c, rows in _kept:
        if c is ct:
            return rows
    rows = TR.assignment_summaries(ct, slots)
    _kept.append((ct, rows))
    del _kept[:-KEEP]
    row_store.submit(ct, rows)
    return rows


def matrix(ct, e, width):
    """The rows of entry e of ct, an array of `width` columns."""
    r, o = int(M.col(ct, 'entries', 'rows')[e]), int(M.col(ct, 'entries', 'offset')[e])
    return np.frombuffer(ct.values, np.int32)[o:o + r * width].reshape(r, width)


def widths_of(types):
    return [4 if str(t) in M.WIDE else 1 for t in types]


def complete(ct, e):
    E = ct.entries
    return not (E['stop_bound'][e] or E['value_stop_bound'][e] or E['fault'][e])


def entries(ct, j):
    """[(example kind, example index, rows)] of the complete entries of table row j of ct, rows an array with one row per table row."""
    tw = sum(widths_of(ct.tables['column_types'][j]))
    et, ex, ei, ek = (M.col(ct, 'entries', k) for k in ('table', 'example_kind', 'example_index', 'kind'))
    return [(int(ex[e]), int(ei[e]), matrix(ct, e, tw)) for e in range(len(et)) if et[e] == j and ek[e] == 0 and complete(ct, e)]


def assignments_of(ct):
    """{table row: {DET (its slot number, or its QueryHash where the wheel gives that): value hash}}."""
    got = collections.defaultdict(dict)
    A = ct.assignments
    if len(A['det']):
        for r, d, v in zip(M.col(ct, 'assignments', 'table'), A['det'], TR.wide(ct, 'assignments', 'value')):
            if isinstance(d, (bytes, bytearray, memoryview)):
                d = int.from_bytes(bytes(d), 'little')
            elif TR.slot_of(d) is not None:
                d = TR.slot_of(d)
            got[r][d] = v
    return got


def parse_table(ct, js=None, with_rows=True):
    """The table of rows js of ct (default all): labels, types, frames, and per entry its example, assignment, rows in native order, each row's extents ([h, w] or
    None per Box, Position or Offset column, in label order) and its constraint model. The assignment of an entry is {DET: value hash}, that of the table row the entry
    is in. Raises M.Fail where the rows are of more than one table, or the table or an entry is incomplete. An Undefined entry (no TableRows) is left out, as `entries` leaves it out. With with_rows False, an entry's rows are only their
    count (a range), its extents and assignment are left empty, and `full` gives the whole table. `assignment_summaries` has the AssignmentSummaries of the rows."""
    T = ct.tables
    js = list(range(len(T['form'])) if js is None else js)
    if not js:
        raise M.Fail('step gave 0 tables')
    sc = TR.accessor(TR.SLOT, T)
    slot = M.col(ct, 'tables', sc) if not isinstance(T[sc], list) else T[sc]
    if len({(int(slot[j]), T['name'][j]) for j in js}) != 1:
        raise M.Fail('step gave %d tables' % len({(int(slot[j]), T['name'][j]) for j in js}))
    for j in js:
        if T['fault'][j]:
            raise M.Fail('table fault: %s' % (T['fault'][j],))
    j0 = js[0]
    labels, types = list(T['column_labels'][j0]), list(T['column_types'][j0])
    widths = widths_of(types)
    tw = sum(widths)
    xcols = list(T['extent_columns'][j0])
    boxcols = [i for i, t in enumerate(types) if str(t) in M.WIDE]
    V = memoryview(ct.values).cast('B').cast('i')
    et, ex, ei = (M.col(ct, 'entries', k) for k in ('table', 'example_kind', 'example_index'))
    ek, er, eo = (M.col(ct, 'entries', k) for k in ('kind', 'rows', 'offset'))
    xo, em = M.col(ct, 'entries', 'extent_offset'), M.col(ct, 'entries', 'model')
    xst = ct.entries['extent_status']
    stop, vstop, efault = ct.entries['stop_bound'], ct.entries['value_stop_bound'], ct.entries['fault']
    asg_of = assignments_of(ct) if with_rows else {}
    mine = set(js)
    out = []
    for e in range(len(et)):
        if et[e] not in mine:
            continue
        if ek[e] not in (0, UNDEFINED, NOT_EXPORTED) or stop[e] or vstop[e] or efault[e]:
            raise M.Fail('entry %d incomplete (kind %d, stop %s %s, fault %s)' % (e, ek[e], stop[e], vstop[e], efault[e]))
        if ek[e] == UNDEFINED:  # the model has no TableRows (a proposer with no rows on the input): the example's Set holds none of it, and the table has a TableHash
            continue
        if ek[e] == NOT_EXPORTED and with_rows:
            raise M.Fail('entry %d has no rows: the result is of an export with rows=False' % e)
        if not with_rows:
            out.append(((int(ex[e]), int(ei[e])), {}, range(er[e]), [], int(em[e])))
            continue
        rows, exts = [], []
        for r in range(er[e]):
            o = eo[e] + r * tw
            rows.append(tuple(V[o:o + tw]))
            ext = {}
            if xcols and xo[e] >= 0:
                for j, c in enumerate(xcols):
                    st_ = xst[e][r][j] if e < len(xst) and r < len(xst[e]) and j < len(xst[e][r]) else 0
                    if st_ == 1:
                        k = xo[e] + (r * len(xcols) + j) * 2
                        ext[c] = [int(V[k]), int(V[k + 1])]
            exts.append([ext.get(c) for c in boxcols])
        out.append(((int(ex[e]), int(ei[e])), asg_of.get(int(et[e]), {}), rows, exts, int(em[e])))
    mine_rows = tables(ct)
    return dict(labels=labels, types=types, widths=widths, frames=list(T['column_frames'][j0]), entries=out, ct=None if with_rows else ct, js=js,
                assignment_summaries=[mine_rows[j] for j in js])


def rows_of(tb, cap=500):
    """x_rows: per entry [[kind, index], rows (sorted, at most cap; all where cap is None), row count, {DET: value hash}, constraint model, extents of those rows]."""
    out = []
    for ex, asg, rows, exts, model in full(tb)['entries']:
        pairs = sorted(zip(rows, exts))[:cap]
        out.append([list(ex), [list(r) for r, _ in pairs], len(rows), {str(k): '%032x' % v for k, v in asg.items()}, model, [x for _, x in pairs]])
    return out


def full(tb):
    """tb with its rows, extents and assignments, where parse_table left them out."""
    if tb is None or tb.get('ct') is None:
        return tb
    if 'full' not in tb:
        tb['full'] = parse_table(tb['ct'], tb['js'])
    return tb['full']


def summary(tb):
    """The counts of tb: labels, types, frames, the row count of each example at each assignment, and empty_all and empty_inputs, which the TableVector gives (all the
    table's assignments empty). The count of an example is its most rows over its TableRows (ExampleKey.rows). A table that the AssignmentSummaries do not describe (a port's
    X) gives the counts of its entries."""
    if tb is None:
        return None
    rows = tb.get('assignment_summaries')
    if rows:
        per = [[k[0], k[1], k[3]] for r in rows for k in r.examples]
        a, b = index()['empty_all'], index()['empty_inputs']
        empty_all, empty_inputs = all(r.features[a] for r in rows), all(r.features[b] for r in rows)
    else:
        per = [[ex[0], ex[1], len(rs)] for ex, asg, rs, *_ in tb['entries']]
        train = [n for k, _, n in per if k == 1] or [n for _, _, n in per]
        inputs = [n for k, _, n in per if k in (1, 2)] or train
        empty_all, empty_inputs = (all(n == 0 for n in train) if train else None), (all(n == 0 for n in inputs) if inputs else None)
    return dict(labels=tb['labels'], types=[str(t) for t in tb['types']], frames=tb.get('frames'), entries=per, empty_all=empty_all, empty_inputs=empty_inputs)
