"""Slices of finished reads, with no new model read. Writes slices.json and pool-gap-heads.tsv.

  gold_tables_env.sh 1 slices.py [STEERS]

- by_depth, by_kind: the held per-form rows of the need+foundset tier, by dependency depth band (measures.md, "Dependency depth": 1, 2-3, 4-6, 7+) and by kind. A form's depth is 1 for a form that reads no found form, else 1 + the greatest depth among the forms it reads.
- comp DET rows at 25 bits or more.
- pool heads: gold's marginal on fit tasks against the pool's share, per kind, from fit rows and junk nodes only. The junk node rows are those of the source record, as they stand.
The slices that read the order of the program (the share of forms that read the form written just before, the moves of the need counts from one written form to the next, thirds of the program) are gone.
"""
import collections
import json
import math
import sys

import final_read as R
import next_form_facts as F

JUNK = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-next-form-content-given-task-heldout37/junk-node-rows.jsonl'
STEERS = sys.argv[1] if len(sys.argv) > 1 else 'live'
BANDS = ((1, '1'), (3, '2-3'), (6, '4-6'), (10 ** 9, '7+'))


def band(d):
    return next(name for lim, name in BANDS if d <= lim)


def depths(forms):
    """{key: depth} of the forms of a task."""
    out = {}

    def go(k):
        if k not in out:
            out[k] = 1 + max((go(x[2]) for x in forms[k]['reads'] if x[2] is not None and x[2] in forms), default=0)
        return out[k]
    for k in forms:
        go(k)
    return out


out = {}
tf = F.load('fit')
ts = F.load('held')
dep = {}
for t, d in ts.items():
    dd = depths(d['forms'])
    for k, f in d['forms'].items():
        dep[t, f['form']] = dd[k]
per = [json.loads(x) for x in open(F.R + 'per-form-held-%s.jsonl' % STEERS)]
key = 't1 need+foundset'
bd, kd = collections.defaultdict(list), collections.defaultdict(list)
for p in per:
    if key in p and (p['task'], p['form']) in dep:
        bd[band(dep[p['task'], p['form']])].append((p['task'], p[key]))
        kd[p['kind']].append((p['task'], p[key]))
out['by_depth ' + key] = {k: R.boot(v, None) for k, v in sorted(bd.items())}
out['by_kind ' + key] = {k: R.boot(v, None) for k, v in sorted(kd.items())}
out['comp_det_at25'] = R.boot([(p['task'], p['saved comp DET need+foundset']) for p in per if 'saved comp DET need+foundset' in p and p['bits'] >= 25], None)
out['bits_of_forms_at25'] = dict(forms=sum(1 for p in per if p['bits'] is not None and p['bits'] >= 25), mean=round(sum(p['bits'] for p in per if p['bits'] is not None and p['bits'] >= 25) / max(1, sum(1 for p in per if p['bits'] is not None and p['bits'] >= 25)), 2))
json.dump(out, open(F.R + 'slices.json', 'w'), indent=1)
print(json.dumps(out)[:2500])
fit = F.rows_of(tf)
junk = [json.loads(x) for x in open(JUNK)]
with open(F.R + 'pool-gap-heads.tsv', 'w') as f:
    f.write('kind\thead columns\tgold forms\tgold share\tpool share\tlog2 ratio\n')
    for k in ('RULE', 'DET', 'INIT'):
        p = collections.Counter(r['y']['t_coarse'] for r in fit if r['kind'] == k)
        q = collections.Counter(j['coarse'] for j in junk if j['kind'] == k)
        np_, nq = sum(p.values()), sum(q.values())
        rows = []
        for a, v in p.items():
            if v >= 30:
                x, y = v / np_, (q[a] + .5) / (nq + 1)
                rows.append((math.log2(x / y), a, v, x, y))
        rows.sort(reverse=True)
        for g, a, v, x, y in rows[:8] + rows[-4:]:
            f.write('%s\t%s\t%d\t%.3f\t%.4f\t%.2f\n' % (k, a, v, x, y, g))
