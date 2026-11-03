#!/usr/bin/env python
"""Summary of probe-cost-rows.jsonl: ms per call of each way to answer "any row", median, 95th and largest, one thread.

  python features_feasible_probe_cost_read.py [ROWS]    writes probe-cost-read.json
"""
import collections
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
PATH = sys.argv[1] if len(sys.argv) > 1 else HERE + 'probe-cost-rows.jsonl'


def line(v):
    v = sorted(v)
    n = len(v)
    return dict(calls=n, median=round(st.median(v), 3), mean=round(sum(v) / n, 3), p95=round(v[min(n - 1, int(n * .95))], 3), largest=round(v[-1], 3))


rows = [json.loads(x) for x in open(PATH)]
P = [d for d in rows if d['rec'] == 'pick']
res = dict(picks=len(P), forms=len({(d['task'], d['line']) for d in P}), tasks=len({d['task'] for d in P}))
O = [(d, i, x) for d in P for i, x in enumerate(d['o'])]
fork, tab, parse, proj = [x[1] for _, _, x in O], [x[2] for _, _, x in O], [x[3] for _, _, x in O], [x[4] for _, _, x in O]
res['fork and probe step'] = line(fork)
res['step_tables with before'] = line(tab)
res['read of row counts'] = line(parse)
res['step_tables with before, read, fork'] = line([a + b + c for a, b, c in zip(fork, tab, parse)])
if any(x[5] is not None for _, _, x in O):
    res['step_tables no before'] = line([x[5] for _, _, x in O if x[5] is not None])
    res['same options: with before'] = line([x[2] for _, _, x in O if x[5] is not None])
res['projections'] = line(proj)
res['first relation of a pick, step_tables with before'] = line([d['o'][0][2] for d in P if d['o']])
res['later relations of a pick, step_tables with before'] = line([x[2] for _, i, x in O if i > 0])
res['pick, all relations, step_tables route with no short stop'] = line([sum(x[1] + x[2] + x[3] for x in d['o']) for d in P if d['o']])
res['Decoder.fork'] = line([d['fork_ms'] for d in P])
res['Decoder.admits, per token'] = line([d['admits_ms'] / max(d['admits_n'], 1) for d in P])
res['Decoder.forced'] = line([d['forced_ms'] for d in P])
ans = collections.Counter()
for _, _, x in O:
    rows_, a = x[6], x[9]
    kind = 'stop or none' if a is None else ('raised' if isinstance(a, str) else ('projection rows' if a else 'projection empty'))
    ans[kind, 'table rows' if rows_ else 'table empty'] += 1
res['projections against table'] = {' / '.join(k): v for k, v in ans.items()}
json.dump(res, open(HERE + 'probe-cost-read.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
