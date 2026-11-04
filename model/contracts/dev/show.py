"""Dev labeling layer: the tested postconditions of the named tables, from <out dir>/<task>.verdicts.post.json.

    python3 show.py TASK TABLE [TABLE ...]
"""
import json
import os
import sys
from pathlib import Path

OUTDIR = Path(os.environ.get('CONTRACTS_OUT', Path(__file__).parent / 'out'))
d = json.load(open(OUTDIR / (sys.argv[1] + '.verdicts.post.json')))
for t in sys.argv[2:]:
    r = d[t]
    print('== %s %s %s' % (t, r['verdict'], r['counts']))
    for k, v in r['postconditions'].items():
        if v['verdict'] in ('new', 'redundant'):
            print('   %-9s %s  failed %s of %s changed (counted %s)  e.g. %s  %s' % (v['verdict'], k.split('|', 1)[1], v['failed'], v['changed'], v['counted'], v.get('example'), v.get('same_as', [])[:2]))
