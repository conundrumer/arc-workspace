#!/usr/bin/env python
"""Writes the gold list for the census at round 50: gold_sexp of each task in TASKS from the ast corpus of gen-v3, checked against the form heads of corpus/gen.

  features_points_round50.py TASKS_FILE [TASKS_FILE ...] OUT.json
"""
import collections
import gzip
import json
import os
import re
import sys

G = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gen-v3-11f6a212c/'
HEAD = re.compile(r'\((RULE|INIT|DET|RIGID_DET|CHOOSE)\s+(&[\w.]+)')
tasks = sorted({t for f in sys.argv[1:-1] for t in open(f).read().split()})
out, miss, same = [], [], 0
for t in tasks:
    p = f'{G}ast-corpus/{t}/pairs.jsonl.gz'
    if not os.path.exists(p):
        miss.append(t)
        continue
    with gzip.open(p, 'rt') as f:
        r = json.loads(f.readline())
    a = collections.Counter(m[2] for m in HEAD.finditer(r['gold_sexp']))
    b = collections.Counter(m[2] for m in HEAD.finditer(open(f'{G}corpus/gen/{t}.arclog').read()))
    same += a == b
    if a != b:
        print('differs from gen', t, sorted((a - b).elements())[:4], sorted((b - a).elements())[:4])
    out.append(dict(task=t, gold_sexp=r['gold_sexp']))
json.dump(out, open(sys.argv[-1], 'w'))
print('tasks', len(out), 'same heads as gen', same, 'no corpus entry', miss, 'keys', list(r))
print(collections.Counter(l.split()[0] for x in out for l in x['gold_sexp'].splitlines() if l.strip()))
