#!/usr/bin/env python3
"""Pieces hit and clauses finished for rewrite pieces, from tp_end.py results. It reads partial output. A clause is one task, and it finishes when each of its pieces has a hit in some folder.

  python3 search_rewrite_pieces_report.py CENSUS.jsonl LIST.json DIR [DIR ...]

CENSUS.jsonl gives each piece's bits (rows with scope `before`), and LIST.json gives the pieces. A piece with no result in a DIR shows `-`.
"""
import collections
import glob
import json
import os
import sys

census, _, *dirs = sys.argv[1:]
bits = {}
for line in open(census):
    r = json.loads(line)
    if r.get('scope', 'before') == 'before':
        p = json.loads(r['point']) if isinstance(r['point'], str) else r['point']
        bits[(r['task'], p[0])] = r['total']
got = collections.defaultdict(dict)
for d in dirs:
    for path in glob.glob(d + '/*.json'):
        r = json.load(open(path))
        got[(r['task'], r['point'][0])][os.path.basename(os.path.dirname(os.path.dirname(d)))+'/'+os.path.basename(os.path.dirname(d))] = (r.get('budget'), r.get('hit'), r.get('hit_cpu'), r.get('error'))
tasks = collections.defaultdict(list)
for k in sorted(bits):
    tasks[k[0]].append(k)
done = 0
for t, ks in sorted(tasks.items()):
    hits = [any(v[1] for v in got[k].values()) for k in ks]
    done += all(hits)
    print(t, 'FINISHED' if all(hits) else '%d of %d' % (sum(hits), len(ks)), ' '.join('%d:%.1f:%s' % (k[1], bits[k], ','.join(('%g=%s' % (v[0], ('%.0f' % v[2]) if v[1] else ('err' if v[3] else 'no'))) for v in got[k].values()) or '-') for k in ks))
print('clauses finished', done, 'of', len(tasks))
