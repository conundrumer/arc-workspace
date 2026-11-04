"""Dev labeling layer: agreement between the verdicts and the readings, over tasks, from <out dir>/<task>.verdicts.post.json.

    python3 summary.py TASK [TASK ...]

A claim agrees where it is informative; a live or dead table agrees where it is redundant. An untested table agrees with no reading.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

OUTDIR = Path(os.environ.get('CONTRACTS_OUT', Path(__file__).parent / 'out'))
tot = Counter()
for task in sys.argv[1:]:
    p = OUTDIR / (task + '.verdicts.post.json')
    if not p.exists():
        print('%s: no verdicts yet' % task)
        continue
    d = json.load(open(p))
    c = Counter()
    for t, r in d.items():
        reading, verdict = r['reading'], r['verdict']
        if reading is None:
            continue
        want = 'informative' if reading == 'claim' else 'redundant'
        key = (reading if reading == 'claim' else 'plumbing', 'untested' if verdict == 'untested' else 'agrees' if verdict == want else 'differs')
        c[key] += 1
        tot[key] += 1
    print('%s  claims: %d agree, %d differ, %d untested;  plumbing: %d agree, %d differ, %d untested' % (
        task, c['claim', 'agrees'], c['claim', 'differs'], c['claim', 'untested'], c['plumbing', 'agrees'], c['plumbing', 'differs'], c['plumbing', 'untested']))
print('all       claims: %d agree, %d differ, %d untested;  plumbing: %d agree, %d differ, %d untested' % (
    tot['claim', 'agrees'], tot['claim', 'differs'], tot['claim', 'untested'], tot['plumbing', 'agrees'], tot['plumbing', 'differs'], tot['plumbing', 'untested']))
