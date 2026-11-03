"""Medians over the 37 held tasks of the counts in the run logs of base_s0, sampler-pool-extended-text-pass1-600s/out-all37. Reads records only."""
import ast
import collections
import glob
import json
import statistics as st

R = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-pool-extended-text-pass1-600s/out-all37/base_s0/'
rows = []
for p in sorted(glob.glob(R + '*/work/*.log')):
    total, cur = collections.Counter(), None
    for x in open(p, errors='replace'):
        if x.startswith('generation '):
            if cur:
                total.update(cur)
            cur = None
        elif x.startswith('counts '):
            try:
                cur = json.loads(x[7:])
            except ValueError:
                pass
        elif x.startswith('{') and "'search:" in x:
            try:
                d = ast.literal_eval(x.strip())
                cur = {k: v for k, v in d.items() if isinstance(v, (int, float))}
            except (ValueError, SyntaxError):
                pass
    if cur:
        total.update(cur)
    rows.append(total)
print(len(rows), sum(bool(r) for r in rows))
names = ['draws', 'cpu seconds grow', 'search:visits', 'search:new scope', 'search:resume', 'scope_seconds', 'search:seconds visit setup', 'search:seconds next', 'search:seconds take', 'search:seconds test', 'search:seconds new', 'search:seconds equal', 'node:equal', 'kept:RULE', 'kept:DET', 'kept:INIT', 'search:equal scope-free', 'search:equal reads scope', 'search:no table tries', 'search:failed tries', 'sr:try:empty', 'sr:try:unjoined', 'sr:try:unsafe', 'search.runs', 'search.dead', 'search.seconds', 'scope:pick past the form cap']
for n in names:
    v = [r.get(n, 0) for r in rows if r]
    print('%-34s median %10.1f  sum %12.1f' % (n, st.median(v), sum(v)))
print(sorted(k for k in rows[0] if k.startswith('sr:'))[:60])
