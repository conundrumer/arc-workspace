#!/usr/bin/env python3
"""Recall of a pool arm's first pass against gold's forms, per kind. first_pass_report.py POINTS.json OUT_DIR ...

For each kind: gold forms with a relation in the cover check that read no gold form (`free`, the forms that a pass over the empty scope can make), and all;
covered in the pass; covered at the task's end; the pass's mean seconds and CPU seconds per task.
"""
import collections
import glob
import json
import os
import re
import sys

NAME = re.compile(r'&[A-Za-z_0-9]+')
golds = {x['task']: x['gold_sexp'] for x in json.load(open(sys.argv[1]))}


def forms_of(sexp):
    forms = [str(f) for f in sexp.strip().split('\n') if not f.startswith('(OUT')]
    heads = {NAME.search(f)[0]: i for i, f in enumerate(forms) if NAME.search(f)}
    return [(f.split()[0].lstrip('('), not any(heads.get(n, i) != i for n in NAME.findall(f))) for i, f in enumerate(forms)]


for out in sys.argv[2:]:
    n, c, secs, cpu, tasks = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter(), 0
    for path in glob.glob(out + '/*.events.jsonl'):
        task = os.path.basename(path).split('.')[0]
        ev = [json.loads(x) for x in open(path)]
        fp = [e for e in ev if e['event'] == 'first pass']
        done = [e for e in ev if e['event'] == 'done']
        if not done:
            continue
        tasks += 1
        fs = forms_of(golds[task])
        passed = set(fp[-1]['covered']) if fp else set()
        final = {e['gold'] for e in ev if e['event'] == 'cover'}
        for i, (kind, free) in enumerate(fs):
            for tag in (kind + ' all', kind + ' free'):
                if tag.endswith('free') and not free:
                    continue
                n[tag] += 1
                c[tag, 'pass'] += i in passed
                c[tag, 'end'] += i in final
        for e in fp:
            secs[e['kind']] += e['seconds']
            cpu[e['kind']] += e['cpu']
    print(out, 'tasks done', tasks)
    for tag in sorted(n):
        print('  %-10s forms %4d  covered in the pass %4d  at the end %4d' % (tag, n[tag], c[tag, 'pass'], c[tag, 'end']))
    for k in secs:
        print('  pass %s: mean %.1f s, %.1f CPU s per task' % (k, secs[k] / max(tasks, 1), cpu[k] / max(tasks, 1)))
