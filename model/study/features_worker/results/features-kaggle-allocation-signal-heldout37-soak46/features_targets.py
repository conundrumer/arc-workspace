#!/usr/bin/env python
"""Writes the target file that features_signal_read.py takes as its input: one row per task with gold's total bits and worst form.

  features_targets.py NAME OUT.jsonl CENSUS.jsonl [CENSUS.jsonl ...]

Rows of the context `parents` are read. A form is valid when it has `total` and empty `bad`, `dead` and `left`. Any census gives the same fields.
A task whose gold holds a form with no valid record, or a form of a kind with no walk (CHOOSE, RIGID_DET), has undrawable > 0. Its total and worst are over its valid forms and are lower bounds.
The read ranks such a task above every other task on total bits and counts it as negative on worst form under 25 bits.
"""
import collections
import json
import os
import re
import sys

name, out, files = sys.argv[1], sys.argv[2], sys.argv[3:]
rows = collections.defaultdict(dict)
for f in files:
    for l in open(f):
        r = json.loads(l)
        if r.get('scope') == 'parents':
            rows[r['task'][:8]][r['line']] = r


def valid(r):
    return 'total' in r and not r.get('bad') and not r.get('dead') and not r.get('left')


points = os.environ.get('GOLD_POINTS')
gold = {x['task']: [l for l in x['gold_sexp'].splitlines() if l.strip()] for x in json.load(open(points))} if points else {}
with open(out + '.new', 'w') as g:
    for t, v in sorted(rows.items()):
        good = [r for r in v.values() if valid(r)]
        bad = len(v) - len(good)
        # Forms of gold that the census has no row for, other than OUT: kinds with no walk.
        lines = gold.get(t, [])
        nowalk = sum(not l.startswith('(OUT') for i, l in enumerate(lines)) - len(v) if lines else 0
        g.write(json.dumps(dict(task=t, target=name, forms=len(v), valid=len(good), undrawable=bad + nowalk, no_walk=nowalk, total=round(sum(float(r['total']) for r in good), 2), worst=max((float(r['total']) for r in good), default=None), under_18=sum(float(r['total']) < 18 for r in good), under_25=sum(float(r['total']) < 25 for r in good))) + '\n')
os.replace(out + '.new', out)
print(name, len(rows), 'tasks')
