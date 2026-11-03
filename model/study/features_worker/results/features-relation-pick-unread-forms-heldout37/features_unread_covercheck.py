"""Checks that a cover event's `gold` is a line of the run's gold with OUT taken out: the kind of the covering node's clause against the kind of that line. Stdlib and the zstd command.

  python3 features_unread_covercheck.py KIT_POINTS

Writes cover-index-check.json in this folder: counts over the first tasks of each arm, by the pair of kinds.
"""
import collections
import json
import os
import subprocess
import sys

import features_unread_lib as L

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
kit = {p['task']: L.lines_of(p['gold_sexp']) for p in json.load(open(sys.argv[1]))}
out = collections.Counter()
same = collections.Counter()
ex = []
for arm in L.ARMS:
    for task in [t for t in L.held_tasks() if t not in L.NOT_IN_RUN][:8]:
        base = '%s%s/%s' % (L.RUN, arm, task)
        ev = [json.loads(x) for x in open(base + '.events.jsonl')]
        cov = {str(e['node']): e['gold'] for e in ev if e.get('event') == 'cover'}
        p = subprocess.run(['zstd', '-dc', base + '.nodes.jsonl.zst'], capture_output=True, check=False).stdout.decode(errors='replace')
        for line in p.splitlines():
            head = line[:40]
            r = json.loads(line)
            if r['token'] in cov:
                i = cov[r['token']]
                k1 = r['clause'].split(' ')[0].lstrip('(')
                g = kit[task][i]
                k2 = g.split()[0].lstrip('(')
                out['%s, %s' % (k1, k2)] += 1
                a = ' '.join(r['clause'].split()[2:])[:40]
                b = ' '.join(g.split()[2:])[:40]
                same[a == b] += 1
                if len(ex) < 6:
                    ex.append((r['clause'][:100], g[:100]))
res = dict(kinds=dict(out), text_start_equal={str(k): v for k, v in same.items()}, examples=ex)
json.dump(res, open(HERE + 'cover-index-check.json', 'w'), indent=1)
print(res)
