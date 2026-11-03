#!/usr/bin/env python
"""ONE marks added to a finished program whose OUT test refuses it, or that reads several rows on a test input where the train pairs read one. It draws nothing, so a draw's bits are those of the program without marks.

    for forms, added, got in one_repair.repairs(session, forms, deadline): ...    # forms: the text of each form of the program, OUT last

A program has a trigger in one of these cases:
- Its OUT test ends SeveralValues.
- It ends NotConsistent, and the relation that OUT reads holds, in a train example, two rows with the same Position and different Colors, and the rows of an entry
  cover every cell that its train pair wants; or a DET that OUT reads, directly or not, has a value of several rows (then only that DET is tried).
- It ends Consistent, and a test input has no attempt.
- It ends Consistent with an attempt on every test input, and a clause's table has a column whose values differ within each train entry (one entry at least has
  several rows) and repeat in a test entry, or has one row in each train entry and several in a test entry. Only the test inputs are read, never their outputs.

repairs yields, for each way of adding marks to one RULE or DET clause that makes the program pass, the forms with the marks, (the index of the form, its marks)
and the Probe of the changed program. A program passes where its OUT test ends Consistent and every test input has an attempt; for the last trigger the attempts
must also differ from those of the program without marks. Distinct attempts are yielded once, up to MAX_FOUND of them.

The clauses go in order of their reads from OUT, the nearest first. A clause tries marks of its table's columns that hold a value in more than one row of an entry
(a key of one column each; all of them as separate marks; keys of up to KEY_COLUMNS of them; all of them in one key; two separate marks of one column each),
and then the empty key, which keeps one row. For the last trigger the columns are those that it names, and the empty key is tried where it names it. A DET tries the
empty key alone. A table past the work cap holds counts, and its clause tries the empty key alone.
"""
import collections
import dataclasses
import itertools
import re
import time

import numpy as np

import live
import sample2_col as S
import table_adapter as TA
from sample2_col import M, arclog

NAME = re.compile(r'&[A-Za-z_0-9]+')
KEY_COLUMNS = 3  # the most columns of one key that a try names, apart from the key of all of them
MAX_FOUND = 3  # the most repairs that repairs yields
TRAIN, TEST = 1, 2  # the example_kind of a train pair's entry, and of a test input's


@dataclasses.dataclass
class Probe:
    """One run of a program's text."""
    kind: str = 'NoOut'  # the kind of the OUT test; 'Refused' where the decoder refuses the program, 'NoOut' where it has no OUT
    dec: object = None  # the decoder at the end of the run
    last: object = None  # the Consistency of the OUT test
    attempts: object = None  # the decoder's attempts for each test input; None where it has not ended
    tables: dict = dataclasses.field(default_factory=dict)  # form index -> step_tables result, for the RULE and DET forms, where run with tables
    snaps: dict = dataclasses.field(default_factory=dict)  # form index -> (index of its first model token, a decoder before it), where run with snaps


def kind_of(consistency):
    return str(getattr(consistency, 'kind', None)).rsplit('.', 1)[-1]


def probe(session, forms, tables=False, snaps=False, base=None, at=None):
    """The Probe of the program of forms. With tables, it keeps the tables of the RULE and DET forms; with snaps, a decoder before each form. With base, a Probe with
    snaps of a program that differs from forms at form at and after it, the run goes on from base's decoder before form at."""
    got = Probe()
    before = None
    try:
        ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join(forms), session.settings).decode_stream()
        steps = [(t, m, p[0]) for t, m, p in zip(ids, model, paths)]
        start, dec = (base.snaps[at][0], base.snaps[at][1].fork()) if base is not None and at in base.snaps else (0, session.decoder())
        for j in range(start, len(steps)):
            t, m, form = steps[j]
            if m:
                if snaps and form not in got.snaps:
                    got.snaps[form] = j, dec.fork()
                step = dec.step(t)
                if step[1] is not None:
                    got.last = step[1]
                if tables and before is None:  # a program's first model step has step_tables' first result
                    before = TA.export(dec, *live.TABLES, None)
            if tables and (j + 1 == len(steps) or steps[j + 1][2] != form) and before is not None and not forms[form].startswith('(OUT'):
                before = TA.export(dec, *live.TABLES, before)
                got.tables[form] = before
    except (arclog.Refusal, arclog.Fault):
        got.kind = 'Refused'
        return got
    got.dec = dec
    if got.last is not None:
        got.kind = kind_of(got.last)
        got.attempts = dec.attempts() if dec.ended else None
    return got


def passes(got):
    return got.kind == 'Consistent' and got.attempts is not None and all(got.attempts)


def repeated(ct):
    """(the labels of the columns of the one new table of step_tables result ct that hold a value in more than one row of an entry, the most rows of an
    entry); the rows are None for a table that holds counts."""
    try:
        tb = S.parse_table(ct, with_rows=False)
    except M.Fail:
        return [], None
    labels = [str(x) for x in tb['labels']]
    at = list(itertools.accumulate(tb['widths'], initial=0))
    cells = [c for c in S.entry_cells(tb) if len(c) > 1]
    got = {lab for i, lab in enumerate(labels) if lab and any(has_equal_rows(c[:, at[i]:at[i + 1]]) for c in cells)}
    return [x for x in labels if x in got], max((len(en[2]) for en in tb['entries']), default=0)


def two_colors(ct, columns, masks=None):
    """Whether, in a train entry of the one new table of step_tables result ct, two rows have the same value in a Position or Box column of the labels columns
    and different values in a Color column of them. With masks, the cell_masks of each train pair, the rows of some entry of each train pair must also hold every cell
    that the pair wants, since a mark only takes rows away. Of a Position or Box column, cell 0 is the top and cell 2 the left."""
    try:
        tb = S.parse_table(ct, with_rows=False)
    except M.Fail:
        return False
    labels, types = [str(x) for x in tb['labels']], [str(t) for t in tb['types']]
    pos = [labels.index(c) for c in columns if c in labels and types[labels.index(c)] in ('Position', 'Box')]
    col = [labels.index(c) for c in columns if c in labels and types[labels.index(c)] == 'Color']
    if not pos or not col:
        return False
    at = list(itertools.accumulate(tb['widths'], initial=0))
    p, k = at[pos[0]], at[col[0]]
    twice, covers = False, collections.defaultdict(bool)
    for en, c in zip(tb['entries'], S.entry_cells(tb)):
        ex = en[0]
        if ex[0] != TRAIN:
            continue
        i, j, v = c[:, p], c[:, p + 2], c[:, k]
        if not twice and len(c) > 1:
            o = np.lexsort((v, j, i))
            si, sj, sv = i[o], j[o], v[o]
            twice = bool(((si[1:] == si[:-1]) & (sj[1:] == sj[:-1]) & (sv[1:] != sv[:-1])).any())
        if masks is None:
            if twice:
                return True
        elif not covers[ex[1]]:
            ok = (i >= 0) & (i < 30) & (j >= 0) & (j < 30) & (v >= 0) & (v < 10)
            cells = 300 * i[ok].astype(np.int64) + 10 * j[ok] + v[ok]
            covers[ex[1]] = bool(np.isin(np.flatnonzero(masks[ex[1]][9000][0]), cells).all())
    return twice and (masks is None or all(covers[i] for i in range(len(masks))))


def has_equal_rows(a):
    """Whether two rows of a, an int32 array of shape (rows, cells), are equal. The rows of a column of several cells are packed into one int64 where the ranges of
    its cells fit in 62 bits, else compared as bytes. Every sort is on a copy: a view of a CaseTables' values is read-only."""
    n, w = a.shape
    if n < 2:
        return False
    if w == 1:
        key = a[:, 0].copy()
    else:
        lo, hi = a.min(axis=0).astype(np.int64), a.max(axis=0).astype(np.int64)
        bits = [int(s).bit_length() for s in hi - lo]
        if sum(bits) <= 62:
            key = a[:, 0].astype(np.int64)
            key -= lo[0]
            for j in range(1, w):
                key <<= bits[j]
                key += a[:, j]
                key -= lo[j]
        else:
            key = a.copy().view(np.dtype((np.void, a.itemsize * w))).ravel()
    key.sort()
    return bool((key[1:] == key[:-1]).any())


def facts(ct):
    """(cols, empty, rows, several) of the one new table of step_tables result ct. cols: the labels of the columns whose values differ within each train entry, one at
    least having several rows, and repeat in a test entry. empty: whether each train entry has one row at most and a test entry has several. rows: the most rows of
    an entry. several: whether a task-wide entry, the value of a DET, has several rows."""
    try:
        tb = S.parse_table(ct, with_rows=False)
    except M.Fail:
        return [], False, None, False
    labels = [str(x) for x in tb['labels']]
    at = list(itertools.accumulate(tb['widths'], initial=0))
    kinds = [en[0][0] for en in tb['entries']]
    cells = S.entry_cells(tb)
    train = [c for k, c in zip(kinds, cells) if k == TRAIN]
    test = [c for k, c in zip(kinds, cells) if k == TEST and len(c) > 1]
    top = max((len(c) for c in cells), default=0)
    cols = []
    if any(len(c) > 1 for c in train) and test:
        cols = [lab for i, lab in enumerate(labels) if lab and not any(has_equal_rows(c[:, at[i]:at[i + 1]]) for c in train if len(c) > 1)
                and any(has_equal_rows(c[:, at[i]:at[i + 1]]) for c in test)]
    empty = bool(train) and all(len(c) <= 1 for c in train) and bool(test)
    return cols, empty, top, any(k == 0 and len(c) > 1 for k, c in zip(kinds, cells))


def keys(cols, rows, det, empty=True):
    """The lists of marks (a mark is a tuple of key labels) that a clause with repeated columns cols tries, in order."""
    if det or not rows or rows < 2:
        return [[()]] * empty
    out = [[(c,)] for c in cols]
    if len(cols) > 1:
        out.append([(c,) for c in cols])
        out += [[k] for n in range(2, min(len(cols), KEY_COLUMNS) + 1) for k in itertools.combinations(cols, n)]
        out.append([tuple(cols)])
        out += [[(a,), (b,)] for a, b in itertools.combinations(cols, 2)]
    return out + [[()]] * empty


def nearest(forms):
    """The indexes of the forms that OUT reads, directly or not, the nearest first, and the later one first among those as near."""
    heads = {NAME.search(f)[0]: i for i, f in enumerate(forms) if f.startswith(('(RULE', '(DET', '(INIT'))}
    out = next(i for i, f in enumerate(forms) if f.startswith('(OUT'))
    dist, todo = {out: 0}, [out]
    while todo:
        i = todo.pop(0)
        for name in NAME.findall(forms[i])[0 if forms[i].startswith('(OUT') else 1:]:
            j = heads.get(name)
            if j is not None and j < i and j not in dist:
                dist[j] = dist[i] + 1
                todo.append(j)
    return sorted((i for i in dist if i != out and forms[i].startswith(('(RULE', '(DET'))), key=lambda i: (dist[i], -i))


def out_columns(out):
    """The labels that the OUT form out names for its columns."""
    return re.findall(r'\^(\w+)', out)


def reads_two_colors(forms, got, masks=None):
    """Whether the relation that the OUT form of forms reads, a RULE or DET form with a table in the Probe got, holds two Colors for one Position in a train entry."""
    out = next(i for i, f in enumerate(forms) if f.startswith('(OUT'))
    head = NAME.search(forms[out])
    at = next((i for i, f in enumerate(forms) if f.startswith(('(RULE', '(DET')) and head and NAME.search(f)[0] == head[0]), None)
    return at in got.tables and two_colors(got.tables[at], out_columns(forms[out]), masks)


def plans(forms, got, masks=None):
    """[(form index, lists of marks)] to try on the program of forms whose Probe with tables is got, in order; none where the program has no trigger. A program that
    ends NotConsistent has the second trigger, or a DET in its reads whose value has several rows, and then tries the DET alone."""
    if got.kind == 'Consistent' and got.attempts is None or got.kind not in ('Consistent', 'NotConsistent', 'SeveralValues'):
        return []
    near = [i for i in nearest(forms) if i in got.tables]
    only = None  # the clauses that a NotConsistent program tries, where it lacks the second trigger
    if got.kind == 'NotConsistent' and not reads_two_colors(forms, got, masks):
        only = [i for i in near if forms[i].startswith('(DET') and facts(got.tables[i])[3]]
        if not only:
            return []
    quiet = got.kind == 'Consistent' and all(got.attempts)
    out = []
    for i in near if only is None else only:
        det = forms[i].startswith('(DET')
        if quiet:
            cols, empty, rows, _ = facts(got.tables[i])
            marks = [] if det else keys(cols, rows, False, empty) if cols or empty else []
        else:
            cols, rows = repeated(got.tables[i])
            marks = keys(cols, rows, det)
        if marks:
            out.append((i, marks))
    return out


def marked(form, marks):
    """The form with the marks at its end."""
    return form[:-1] + ''.join(' (ONE%s)' % ''.join(' ' + k for k in mark) for mark in marks) + ')'


def repairs(session, forms, deadline=None, masks=None, plan=None):
    """Yields (forms with marks added to one clause, (its index, its marks), the Probe of those forms) for each such change that makes the program pass,
    in the order above. Nothing is yielded for a program with no trigger. masks are the cell_masks of the train pairs (live.py), which narrow the second trigger.
    plan, [(form index, lists of marks)] in the order of plans, stands in for the program's tables, which a run without it takes to find the trigger and the plan."""
    base = probe(session, forms, plan is None, True)
    found = []
    for i, tries in plans(forms, base, masks) if plan is None else plan:
        for marks in tries:
            if deadline is not None and time.monotonic() >= deadline:
                return
            changed = [*forms[:i], marked(forms[i], marks), *forms[i + 1:]]
            got = probe(session, changed, base=base, at=i)
            if passes(got) and got.attempts != base.attempts and got.attempts not in found:
                found.append(got.attempts)
                yield changed, (i, marks), got
                if len(found) >= MAX_FOUND:
                    return
