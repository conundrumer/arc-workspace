#!/usr/bin/env python
"""A CHOOSE form added to a finished program for a RULE whose table holds keys with several rows. It draws nothing, so a draw's bits are those of the program without it.

    for forms, (index, key, shape), got in choose_lift.lifts(session, forms, tables, deadline): ...    # forms: the text of each form of the program, OUT last

cover(ct, masks, new) reads the tables of a form end: the live Run lifts only at a form end whose cover is at least its choose_cover.

key_facts(ct, masks) reads a RULE's table when its clause closes: for each key of columns under which a train or test entry has a value of several rows, the count of keys
with several rows, of keys with one row (solo), over those entries, of cells that a train pair wants and no row holds (empty, for a key of one cell column), and the bits (the sum of log2 of
the rows of each key with several rows). The keys go in this order: one column, then more; no empty cell, then some; a cell column, then another; more solo keys first. A key whose rows leave no
candidate column (every other column is a function of the key) is left out.

lifts yields, for each CHOOSE that makes the program pass, the forms with the CHOOSE, (the index of the RULE, its key, the name of the `never` shape) and the Probe of
the changed program. The CHOOSE stands after the RULE: `for` is the key (with the columns that the key decides, so the chosen relation holds every column of the RULE),
`from` the RULE's rows, and every later form reads the chosen relation where it read the RULE. A program passes where its OUT test ends Consistent and every test input has
an attempt. The pairs of a RULE and a key go in the order of the fewest key columns, the fewest columns that the key decides, a cell column first, and the fewest bits (the nearest RULE, then
key_facts's order, where these tie), and a pair tries each shape of `nevers` in its order (overlap, then cover, rival, line, exclusive; a shape that reads another
relation of the program once for each such relation, a pair of its columns for rival), then the overlap with each other shape, then all the shapes at once. Distinct attempts
are yielded once, up to MAX_FOUND of them.
"""
import collections
import itertools
import math
import re

import numpy as np

import live
import one_repair as O
import table_adapter as TA
from sample2_col import M

NAME = O.NAME
KEY_COLUMNS = 2  # the most columns of a key of several columns
KEY_TRIES = 12  # the most keys of a table
ROW_CAP = 5000  # the most train rows of a table that key_facts reads
MAX_FOUND = 3  # the most lifts that lifts yields
CELLS = 'Position', 'Box'  # the column types of a cell
IDENT = re.compile(r'[A-Za-z_][A-Za-z_0-9]*\Z')


def key_facts(ct, masks=None):
    """(labels, types, keys) of the one new table of step_tables result ct, or None where it cannot be read. A key is (the column indexes, several, solo, empty, the column indexes
    that its values decide, the bits), for the keys under which a train entry has a value of several rows, in the order that lifts tries them."""
    try:
        labels, types, widths, at, entries = O.view(ct)
    except M.Fail:
        return None
    used = [e for e in entries if e[0][0] in (O.TRAIN, O.TEST)]  # the train and test entries
    seen = [e[2] for e in used]
    train = [(e[0][1], at_) for at_, e in enumerate(used) if e[0][0] == O.TRAIN]  # (the pair, the entry's place in seen)
    names = [i for i, x in enumerate(labels) if x]
    if not train or len(names) < 2 or len(names) != len(labels) or len(set(labels)) != len(labels) or not all(map(IDENT.match, labels)) or sum(map(len, seen)) > ROW_CAP:
        return labels, types, []
    types = [str(t) for t in types]

    cv = [[[O.values(r, widths, at, i) for r in rows] for i in range(len(labels))] for rows in seen]  # entry -> column -> the value of each row

    def keys_of(e, cols):
        return list(zip(*[cv[e][i] for i in cols]))

    def counts(cols):
        return [collections.Counter(keys_of(e, cols)) for e in range(len(seen))]
    repeating = [i for i in names if any(max(c.values(), default=0) > 1 for c in counts((i,)))]
    tries = ([(i,) for i in repeating] + [k for n in range(2, KEY_COLUMNS + 1) for k in itertools.combinations(repeating, n)])[:KEY_TRIES]
    out = []
    for cols in tries:
        per = counts(cols)
        several, solo = sum(v > 1 for c in per for v in c.values()), sum(v == 1 for c in per for v in c.values())
        if not several:
            continue
        ks = [keys_of(e, cols) for e in range(len(seen))]

        def decides(d):
            for e in range(len(seen)):
                first = {}
                for k, v in zip(ks[e], cv[e][d]):
                    if first.setdefault(k, v) != v:
                        return False
            return True
        decided = tuple(d for d in names if d not in cols and decides(d))
        if len(cols) + len(decided) == len(names):
            continue
        empty = 0
        if masks is not None and len(cols) == 1 and types[cols[0]] in CELLS:
            best = {}
            for ex, e in train:
                cells = {30 * i + j for i, j in (v[::2] for v in set(cv[e][cols[0]])) if 0 <= i < 30 and 0 <= j < 30}
                lost = sum(int(k) not in cells for k in range(900) if masks[ex][900][0][k])
                best[ex] = min(best.get(ex, lost), lost)
            empty = sum(best.values())
        out.append((cols, several, solo, empty, decided, sum(math.log2(v) for c in per for v in c.values() if v > 1)))
    out.sort(key=lambda k: (len(k[0]) > 1, k[3] > 0, types[k[0][0]] not in CELLS, -k[2]))
    return labels, types, out


def cover(ct, masks, new):
    """The most that one pair of a Position or Box column and a Color column covers, as a fraction of the cells that the train pairs want, over the relations of slots new
    in step_tables result ct; 0.0 where no such pair exists. A cell is wanted as live.cell_masks says (a train output's cell that differs from the input, or any cell where the
    sizes differ), and a pair covers it where a row of the train pair's entry holds the cell's Position and its output color. A task-wide table is read against every train pair,
    and its entry of most cover stands."""
    summaries = TA.tables(ct)
    entries = collections.defaultdict(list)  # table row -> its train entries (example kind, example index, rows)
    for j, r in enumerate(summaries):
        if r.slot in new:
            entries[j] = [x for x in TA.entries(ct, j) if x[0] in (live.EXAMPLE_TASK, live.EXAMPLE_TRAIN)]
    best = 0.0
    for j, es in entries.items():
        if not es:
            continue
        types = list(summaries[j].types)
        at = list(itertools.accumulate((4 if t in M.WIDE else 1 for t in types), initial=0))
        if es[0][0] == live.EXAMPLE_TASK:  # each entry is read against every pair
            reads = [[(rs, m[9000][0]) for m in masks] for _, _, rs in es]
        else:
            reads = [[(rs, masks[k][9000][0]) for k, rs in {pair: rs for _, pair, rs in es}.items()]]
        for p in (a for a, t in zip(at, types) if t in CELLS):
            for c in (a for a, t in zip(at, types) if t == 'Color'):
                for read in reads:
                    hit = total = 0
                    for rs, want in read:
                        i, k, color = rs[:, p], rs[:, p + 2], rs[:, c]
                        ok = (i >= 0) & (i < 30) & (k >= 0) & (k < 30) & (color >= 0) & (color < 10)
                        seen = np.zeros(9000, bool)
                        seen[(10 * (30 * i + k) + color)[ok]] = True
                        hit, total = hit + int((seen & want).sum()), total + int(want.sum())
                    best = max(best, hit / total if total else 1.0)
    return best


class Names:
    """Variable names for a CHOOSE's `never`, that are no label of the relations it reads."""

    def __init__(self, taken):
        self.taken = set(taken)

    def __call__(self, label, tag):
        name = label + tag
        while name in self.taken:
            name += '_'
        self.taken.add(name)
        return name


def atom(rel, binds):
    return '(%s %s)' % (rel, ' '.join('(:%s %s)' % b for b in binds))


def differ(a, b, labels):
    """The test that two reads give different values in some one of labels."""
    if len(labels) == 1:
        return '(!= %s %s)' % (a[labels[0]], b[labels[0]])
    return '(OR %s)' % ' '.join('((!= %s %s))' % (a[x], b[x]) for x in labels)


def nevers(forms, i, lifts, cols, decided):
    """[(shape name, the text of its `never` clause)] for the RULE form i of forms with key columns cols (indexes), the columns that its key decides, and lifts."""
    labels, types, _ = lifts[NAME.search(forms[i])[0][2:]]
    rel, key = NAME.search(forms[i])[0], [labels[c] for c in cols]
    row = [labels[c] for c in sorted(cols + decided)]
    cand = [x for x in labels if x not in row]
    names = Names(labels)
    out = []

    def fresh(ls, tag):
        return {x: names(x, tag) for x in ls}
    a, b, q = fresh(cand, 'a'), fresh(cand, 'b'), fresh(row, 'q')
    out.append(('overlap', '(never %s %s %s %s)' % (atom(rel, [(x, '*' + a[x]) for x in cand]), atom(rel, [(x, '*' + b[x]) for x in cand] + [(x, '*' + q[x]) for x in row]),
                                                 atom(rel, [(x, a[x]) for x in cand] + [(x, q[x]) for x in row]), differ(a, b, cand))))
    for j, form in enumerate(forms[:i]):
        other = NAME.search(form)
        got = lifts.get(other[0][2:]) if other and form.startswith('(RULE') else None
        if got is None:
            continue
        ols, ots, _ = got
        names.taken |= set(ols)
        join = [x for x in labels if x in ols and types[labels.index(x)] == ots[ols.index(x)]]
        if all(x in join for x in cand):  # the cells that two candidates cover, read in the relation that holds them
            for z in ols:
                if ots[ols.index(z)] in CELLS and z not in cand:
                    on = [x for x in join if x != z]
                    c1, c2 = fresh(on, 'c'), fresh(on, 'd')
                    cell = names(z, 'z')
                    out.append(('cover', '(never %s %s %s %s %s)' % (atom(rel, [(x, '*' + c1[x]) for x in on]), atom(rel, [(x, '*' + c2[x]) for x in on]),
                                                                    atom(other[0], [(x, c1[x]) for x in on] + [(z, '*' + cell)]), atom(other[0], [(x, c2[x]) for x in on] + [(z, cell)]),
                                                                    differ(c1, c2, on))))
        if len(cand) == 1:  # two columns of a relation that hold candidates, as pairs of candidates that clash
            for u, v in itertools.combinations([x for x, t in zip(ols, ots) if t == types[labels.index(cand[0])]], 2):
                r1, r2 = names(cand[0], 'r'), names(cand[0], 's')
                out.append(('rival', '(never %s %s %s)' % (atom(rel, [(cand[0], '*' + r1)]), atom(rel, [(cand[0], '*' + r2)]), atom(other[0], [(u, r1), (v, r2)]))))
    if len(cols) == 1 and types[cols[0]] in CELLS:  # one candidate at two keys of a line
        k2, k3, ax = names(key[0], 'm'), names(key[0], 'n'), names('A', 'x')
        c = fresh(cand, 'l')
        out.append(('line', '(never %s %s (!= %s %s) (axis_elem (:A *%s)) (same_line (:A %s) (:P %s) (:Q %s)))' % (
            atom(rel, [(key[0], '*' + k2)] + [(x, '*' + c[x]) for x in cand]), atom(rel, [(key[0], '*' + k3)] + [(x, c[x]) for x in cand]), k2, k3, ax, ax, k2, k3)))
    if len(cand) > 1:  # two candidates that agree in the first candidate column and differ in another are never chosen together
        a, b = fresh(cand, 'e'), fresh(cand, 'f')
        out.append(('exclusive', '(never %s %s %s)' % (atom(rel, [(x, '*' + a[x]) for x in cand]), atom(rel, [(cand[0], a[cand[0]])] + [(x, '*' + b[x]) for x in cand[1:]]), differ(a, b, cand[1:]))))
    return out


def choose(forms, i, lifts, cols, decided, nevers_text):
    """(the CHOOSE form after the RULE form i of forms, with key columns cols, and its name)."""
    labels = lifts[NAME.search(forms[i])[0][2:]][0]
    rel = NAME.search(forms[i])[0]
    row = [labels[c] for c in sorted(cols + decided)]
    cand = [x for x in labels if x not in row]
    new = '&r%d' % (1 + max(int(n[2:]) for f in forms for n in NAME.findall(f) if re.fullmatch(r'&r\d+', n)))
    return '(CHOOSE %s (for (%s) (from %s)) %s)' % (new, atom(rel, [(x, '^' + x) for x in row]), atom(rel, [(x, x) for x in row] + [(x, '*' + x) for x in cand]), ' '.join(nevers_text)), new


def lifted(forms, i, text, new):
    """forms with the CHOOSE text after form i, and the forms after it reading the chosen relation new where they read form i's."""
    old = NAME.search(forms[i])[0]
    pat = re.compile(re.escape(old) + r'(?![A-Za-z_0-9])')
    return [*forms[:i + 1], text, *(pat.sub(new, f) for f in forms[i + 1:])]


def plans(forms, tables):
    """[(index of a RULE form that OUT reads, directly or not, its (labels, types, keys))], the nearest first, for the RULEs that have a key; tables: slot -> key_facts."""
    out = []
    for i in O.nearest(forms):
        got = tables.get(NAME.search(forms[i])[0][2:])
        if forms[i].startswith('(RULE') and '(ONE' not in forms[i] and got and got[2]:
            out.append((i, got))
    return out


def lifts(session, forms, tables, deadline=None, tally=None):
    """Yields (forms with a CHOOSE added, (index of the RULE, its key labels, the shape), the Probe of those forms) for each such change that makes the program pass, in the
    order above. Nothing is yielded for a program with no RULE that has a key. tally, a Counter, takes a count for each (shape, outcome) of a try."""
    import time
    todo = plans(forms, tables)
    if not todo:
        return
    base = O.probe(session, forms, False, True)
    found = []
    pairs = sorted(((i, got, key) for i, got in todo for key in got[2]), key=lambda p: (len(p[2][0]), len(p[2][4]), p[1][1][p[2][0][0]] not in CELLS, p[2][5]))
    for i, (labels, _, _), (cols, _, _, _, decided, _) in pairs:
        shapes = nevers(forms, i, tables, list(cols), list(decided))
        first = {s: t for s, t in reversed(shapes)}  # the first never of each shape
        tries = [(s, [t]) for s, t in shapes] + [('overlap+' + s, [first['overlap'], t]) for s, t in first.items() if s != 'overlap'] + ([('all', list(first.values()))] if len(first) > 2 else [])
        for shape, texts in tries:
            if deadline is not None and time.monotonic() >= deadline:
                return
            text, new = choose(forms, i, tables, list(cols), list(decided), texts)
            changed = lifted(forms, i, text, new)
            got = O.probe(session, changed, base=base, at=i + 1)  # a text that does not type gives kind 'Refused'
            if tally is not None:
                tally[shape + ' ' + got.kind] += 1
            if got.kind == 'Stopped':  # the other shapes of this key read the same table, and stop too
                break
            if O.passes(got) and got.attempts != base.attempts and got.attempts not in found:
                found.append(got.attempts)
                yield changed, (i, tuple(labels[c] for c in cols), shape), got
                if len(found) >= MAX_FOUND:
                    return
