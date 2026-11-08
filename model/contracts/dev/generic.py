"""Dev labeling layer: the verdicts of the query-generic postconditions alone, by reading, over tasks.

    python3 generic.py TASK [TASK ...]

A query-generic postcondition is one that every query of its shape makes, whatever the task: its result is not empty (`empty`), and within its rows
one column determines another (`X determines Y`). A postcondition is falsifiable where it is new or redundant: it fails on a variant whose preconditions hold.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

OUTDIR = Path(os.environ.get('CONTRACTS_OUT', Path(__file__).parent / 'out'))
KINDS = {'empty': lambda f: f == 'empty', 'a column determines another': lambda f: ' determines ' in f, 'any feature': lambda f: True}
c = Counter()
cases = {}
for task in sys.argv[1:]:
    p = OUTDIR / (task + '.verdicts.post.json')
    if not p.exists():
        continue
    for t, r in json.load(open(p)).items():
        if r['reading'] is None:
            continue
        reading = 'claim' if r['reading'] == 'claim' else 'plumbing'
        for kind, pick in KINDS.items():
            vs = [v['verdict'] for k, v in r['postconditions'].items() if pick(k.split('|', 1)[1])]
            tested = [v for v in vs if v != 'untested']
            if not tested:
                c[kind, reading, 'untested'] += 1
                continue
            fals = any(v in ('new', 'redundant') for v in tested)
            c[kind, reading, 'falsifiable' if fals else 'not falsifiable'] += 1
            if fals and kind == 'empty':
                cases.setdefault(reading, []).append('%s %s' % (task, t))
for kind in KINDS:
    line = []
    for reading in ('claim', 'plumbing'):
        f, n, u = c[kind, reading, 'falsifiable'], c[kind, reading, 'not falsifiable'], c[kind, reading, 'untested']
        line.append('%s %d of %d falsifiable (%.0f%%), %d untested' % (reading, f, f + n, 100 * f / max(1, f + n), u))
    print('%-24s %s' % (kind, ';  '.join(line)))
for reading, xs in cases.items():
    print('empty falsifiable, %s: %s' % (reading, ', '.join(xs)))
