"""Lists the covered gold forms of the bundle arms with the opening that covered them, from the records only (no engine).

  /Users/davidlu/code/arc-workspace/.venv/bin/python -I covered_list.py [OUTFILE]

Writes covered-list.tsv: arm, task, g, kind, cover visit, visit kind, kind_ok, covering opening o_v, slot_tries, lost, scope_n (fids of the covering visit), ready_before, held_o, status.
Status `scope` means job.py --covered can start from it (it still checks the covering visit's fids against the opening's scope, then the map).
"""
import collections
import csv
import json
import os
import sys

RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943'
OLD = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad'
HERE = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1] if len(sys.argv) > 1 else HERE + '/covered-list.tsv'
rows = [x for x in csv.DictReader(open(RUN + '/scope-loss/forms.tsv'), delimiter='\t') if x['class'] == 'covered' and x['arm'] in ('bundle_s0', 'bundle_s1')]
cache = {}
res = []
for x in rows:
    k = (x['arm'], x['task'])
    if k not in cache:
        cache[k] = (json.load(open('%s/scope-loss/cache/%s__%s.json' % (OLD, *k))), json.load(open('%s/r1-forms/cache/%s__%s.json' % (OLD, *k))))
    sl, r1 = cache[k]
    g = int(x['g'])
    G = next(y for y in sl['golds'] if y['g'] == g)
    ck = G.get('cover_check') or {}
    ops = {o['i']: o for o in sl['ops']}
    vs = sorted(r1['visits'], key=lambda v: v['time'])
    v = vs[ck['visit']] if ck.get('visit') is not None else None
    o = ops.get(ck.get('o_v'))
    if v is None:
        st = 'no covering visit'
    elif not ck.get('kind_ok'):
        st = 'covering visit of another kind'
    elif o is None:
        st = 'no covering opening'
    else:
        st = 'scope'
    res.append([x['arm'], x['task'], g, G['kind'], ck.get('visit'), v['kind'] if v else '', ck.get('kind_ok'), ck.get('o_v'), o['slot_tries'] if o else '', o['lost'] if o else '', len(v['fids']) if v else '',
                ck.get('ready_before'), ck.get('held_o'), st])
with open(out, 'w') as fh:
    fh.write('\t'.join(['arm', 'task', 'g', 'kind', 'cover_visit', 'visit_kind', 'kind_ok', 'o_v', 'slot_tries', 'lost', 'scope_n', 'ready_before', 'held_o', 'status']) + '\n')
    for r in res:
        fh.write('\t'.join(str(c) for c in r) + '\n')
print('covered forms', len(res))
for a in ('bundle_s0', 'bundle_s1'):
    print(a, dict(collections.Counter(r[-1] for r in res if r[0] == a)))
print('all', dict(collections.Counter(r[-1] for r in res)))
sc = [r for r in res if r[-1] == 'scope']
print('with scope: held_o', dict(collections.Counter(r[12] for r in sc)), 'ready_before', dict(collections.Counter(r[11] for r in sc)), 'lost>0', sum(1 for r in sc if r[9]), 'tasks', len({r[1] for r in sc}))
