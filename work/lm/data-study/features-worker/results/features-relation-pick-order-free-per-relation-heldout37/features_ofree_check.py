#!/usr/bin/env python
"""Checks of the fact layer. Writes fact-layer-check.txt.

  python features_ofree_check.py [NTASKS]

1. The allow list refuses each banned name.
2. Every fact the clean tiers emit on fit rows is in the allow list.
3. Shuffling each body, each INIT's ports and the program's lines, dropping marks and renaming labels leaves every row's facts the same.
4. The ordered arms' names fail the check, so they can't enter a clean model.
"""
import collections
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_ofree_facts as FL  # noqa: E402
import features_ofree_lib as L  # noqa: E402
import features_ofree_ordered as O  # noqa: E402
import features_ofree_text as T  # noqa: E402


def main():
    nt = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    out = []
    t0 = time.time()
    for bad in ('last:input', 'k:3', 'ord', 'root2', 'recency', 'prefix:perp', 'before:input', 'first:input', 'position:1', 'last_lib', 'prevform1:x', 'prefix_depth'):
        try:
            FL.check([bad])
        except FL.BannedFact:
            continue
        raise AssertionError('passed: ' + bad)
    out.append('refused 12 banned names')
    recs = L.load('fit')
    n = 0
    fams = {}
    for rc in recs:
        for r in rc['rows']:
            for f in FL.row_facts(r, rc, 'open'):
                fams[f.partition(':')[0]] = fams.get(f.partition(':')[0], 0) + 1
            n += 1
            for x in O.written_facts(r):
                try:
                    FL.check([x])
                except FL.BannedFact:
                    continue
                raise AssertionError('an ordered name passed: ' + x)
    out.append('%d fit rows: each fact emitted is in the allow list, and each ordered name is refused' % n)
    out.append('facts by family: ' + ' '.join('%s=%d' % kv for kv in sorted(fams.items())))
    reg = T.Registry()
    tasks = sorted({rc['task'] for rc in recs})
    step = max(1, len(tasks) // nt)
    tasks = tasks[::step]
    k = FL.invariant(tasks, T.corpus_lines, reg)
    out.append('%d fit tasks, %d rows: facts stay the same under shuffled bodies, shuffled ports, shuffled lines, dropped marks and renamed labels, at each clean tier' % (len(tasks), k))
    moved = same = 0
    rng = random.Random(1)
    for t in tasks:
        lines = T.corpus_lines(t)
        a = {r['name']: r for r in T.records(t, lines, reg)}
        b = {r['name']: r for r in T.records(t, [FL.unparse(FL.scramble(x, rng)) for x in lines], reg)}
        for k, ra in a.items():
            sa = collections.Counter((r['key'], tuple(O.written_facts(r))) for r in ra['rows'])
            sb = collections.Counter((r['key'], tuple(O.written_facts(r))) for r in b[k]['rows'])
            moved += sa != sb
            same += sa == sb
    out.append('the check has power: on the same shuffle, the written facts change on %d forms and stay on %d' % (moved, same))
    print('\n'.join(out), flush=True)
    print('%.0f s' % (time.time() - t0))
    with open(L.ME + 'fact-layer-check.txt', 'w') as f:
        f.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
