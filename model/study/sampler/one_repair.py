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
                    before = arclog.step_tables(dec, *live.TABLES, True, None)
            if tables and (j + 1 == len(steps) or steps[j + 1][2] != form) and before is not None and not forms[form].startswith('(OUT'):
                before = arclog.step_tables(dec, *live.TABLES, True, before)
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


def view(ct):
    """(column labels, column types, the width of each column, the offset of each, the entries) of the one new table of step_tables result ct. Raises M.Fail where
    the table is a count."""
    T = ct.tables
    labels, types = [str(x) for x in T['column_labels'][0]], [str(t) for t in T['column_types'][0]]
    widths = [4 if t in M.WIDE else 1 for t in types]
    return labels, types, widths, list(itertools.accumulate(widths, initial=0)), S.parse_table(ct)['entries']


def values(row, widths, at, i):
    return tuple(row[at[i]:at[i] + widths[i]])


def repeated(ct):
    """(the labels of the columns of the one new table of step_tables result ct that hold a value in more than one row of an entry, the most rows of an
    entry); the rows are None for a table that holds counts."""
    try:
        labels, _, widths, at, entries = view(ct)
    except M.Fail:
        return [], None
    got, top = set(), 0
    for _, _, rows, _, _ in entries:
        top = max(top, len(rows))
        for i, label in enumerate(labels):
            if label and len({values(r, widths, at, i) for r in rows}) < len(rows):
                got.add(label)
    return [x for x in labels if x in got], top


def two_colors(ct, columns, masks=None):
    """Whether, in a train entry of the one new table of step_tables result ct, two rows have the same value in a Position or Box column of the labels columns
    and different values in a Color column of them. With masks, the cell_masks of each train pair, the rows of some entry of each train pair must also hold every cell
    that the pair wants, since a mark only takes rows away."""
    try:
        labels, types, widths, at, entries = view(ct)
    except M.Fail:
        return False
    pos = [labels.index(c) for c in columns if c in labels and types[labels.index(c)] in ('Position', 'Box')]
    col = [labels.index(c) for c in columns if c in labels and types[labels.index(c)] == 'Color']
    if not pos or not col:
        return False
    twice, covers = False, collections.defaultdict(bool)
    for ex, _, rows, _, _ in entries:
        if ex[0] == TRAIN:
            seen = collections.defaultdict(set)
            for r in rows:
                seen[values(r, widths, at, pos[0])[::2]].add(values(r, widths, at, col[0]))
            twice = twice or any(len(v) > 1 for v in seen.values())
            if masks is not None:
                cells = {300 * i + 10 * j + c[0] for (i, j), v in seen.items() if 0 <= i < 30 and 0 <= j < 30 for c in v if 0 <= c[0] < 10}
                covers[ex[1]] = covers[ex[1]] or all(k in cells for k in np.flatnonzero(masks[ex[1]][9000][0]))
    return twice and (masks is None or all(covers[i] for i in range(len(masks))))


def facts(ct):
    """(cols, empty, rows, several) of the one new table of step_tables result ct. cols: the labels of the columns whose values differ within each train entry, one at
    least having several rows, and repeat in a test entry. empty: whether each train entry has one row at most and a test entry has several. rows: the most rows of
    an entry. several: whether a task-wide entry, the value of a DET, has several rows."""
    try:
        labels, _, widths, at, entries = view(ct)
    except M.Fail:
        return [], False, None, False
    train, test = [e[2] for e in entries if e[0][0] == TRAIN], [e[2] for e in entries if e[0][0] == TEST]
    top = max((len(e[2]) for e in entries), default=0)

    def repeats(rows, i):
        return len({values(r, widths, at, i) for r in rows}) < len(rows)
    cols = [lab for i, lab in enumerate(labels) if lab and any(len(r) > 1 for r in train) and not any(repeats(r, i) for r in train) and any(repeats(r, i) for r in test)]
    empty = bool(train) and all(len(r) <= 1 for r in train) and any(len(r) > 1 for r in test)
    return cols, empty, top, any(e[0][0] == 0 and len(e[2]) > 1 for e in entries)


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
