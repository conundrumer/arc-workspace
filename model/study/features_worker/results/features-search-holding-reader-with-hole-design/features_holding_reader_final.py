"""The table of design.md: net bits per form by kind at 25 bits or more, and the last cover reads. Reads edge-rows.jsonl and per-form-held.jsonl. Writes final-read.json beside this file and prints it."""
import collections
import json
import math
import os
import random
import statistics as st

W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
FB = W + 'features-worker/results/features-backward-from-out-content-heldout37/'
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
FIT = {'RULE': (11.3, .30), 'DET': (6.0, .50), 'INIT': (11.9, .12)}
COST12 = {'RULE': 15.0, 'DET': 12.0, 'INIT': 13.4}
STEEP = {'RULE': .78, 'DET': .78, 'INIT': .26}
edges = {(e['task'], e['form']): e for e in map(json.loads, open(HERE + 'edge-rows.jsonl'))}
forms = [json.loads(x) for x in open(FB + 'per-form-held.jsonl')]
forms = [f for f in forms if f['bits'] is not None and f['kind'] in FIT]
sav = lambda f: f.get('t1 full', 0.0)  # noqa: E731


def boot(rows, seed=7, n=4000):
    by = collections.defaultdict(list)
    for t, v in rows:
        by[t].append(v)
    ts = sorted(by)
    s = [sum(by[t]) for t in ts]
    c = [len(by[t]) for t in ts]
    rng = random.Random(seed)
    m = []
    for _ in range(n):
        a = b = 0
        for _ in ts:
            i = rng.randrange(len(ts))
            a += s[i]
            b += c[i]
        m.append(a / max(b, 1))
    m.sort()
    return [round(sum(s) / sum(c), 2), round(m[int(.025 * n)], 2), round(m[int(.975 * n)], 2), sum(c)]


def drawable(f, H=18):
    e = edges.get((f['task'], f['form']))
    return bool(e and e.get('reader_open_bits') is not None and e['reader_open_bits'] < H)


OUT = {}
tab = {}
for k in ('RULE', 'DET', 'INIT', 'ANY'):
    fs = [f for f in forms if f['bits'] >= 25 and (k == 'ANY' or f['kind'] == k)]
    r = dict(forms=len(fs), mean_gross=boot([(f['task'], sav(f)) for f in fs]), median_gross=round(st.median(sav(f) for f in fs), 2))
    for M in (1, 2, 13, 170):
        r['hard M%d' % M] = boot([(f['task'], sav(f) - math.log2(M)) for f in fs])
        r['soft M%d' % M] = boot([(f['task'], math.log2(1 + (2 ** sav(f) - 1) / M)) for f in fs])
        r['soft drawable M%d' % M] = boot([(f['task'], math.log2(1 + (2 ** sav(f) - 1) / M) if drawable(f) else 0.0) for f in fs])
        r['hard drawable M%d' % M] = boot([(f['task'], (sav(f) - math.log2(M)) if drawable(f) else 0.0) for f in fs])
    r['drawable share'] = round(sum(drawable(f) for f in fs) / len(fs), 2)
    r['saved share from forms at 60 bits or more'] = round(sum(sav(f) for f in fs if f['bits'] >= 60) / max(sum(sav(f) for f in fs), 1e-9), 2)
    r['forms at 60 bits or more'] = sum(f['bits'] >= 60 for f in fs)
    tab[k] = r
OUT['net_by_kind_at25'] = tab


def hz(k, b, sl):
    a, s = FIT[k]
    if sl:
        s, a = sl[k], COST12[k] - sl[k] * 12
    return 2 ** -(a + s * b)


def p(k, b, n, sl):
    return 1 - math.exp(-n * hz(k, b, sl))


rows = {}
for nm, n in (('600 s', 4522), ('60 s', 1200)):
    for sn, sl in (('fit s', None), ('steep s', STEEP)):
        # OUT only: the one free goal
        d = sum(p(f['kind'], f['bits'] - sav(f), n, sl) - p(f['kind'], f['bits'], n, sl) for f in forms if edges.get((f['task'], f['form']), {}).get('reader') == 'OUT' and f['kind'] != 'DET')
        # one goal per task, the best in hindsight, soft, with every proposal tilted to it
        by = collections.defaultdict(list)
        for f in forms:
            by[f['task']].append(p(f['kind'], f['bits'] - sav(f), n, sl) - p(f['kind'], f['bits'], n, sl))
        rows[nm + ' ' + sn] = dict(out_only_nonDET=round(d, 2), one_goal_per_task_hindsight=round(sum(max(v) for v in by.values()), 1), base_nonDET=round(sum(p(f['kind'], f['bits'], n, sl) for f in forms if f['kind'] != 'DET'), 1))
OUT['cover_extra'] = rows
OUT['slope_to_log2_proposals'] = {k: dict(gross=round(st.mean(sav(f) for f in forms if f['bits'] >= 25 and f['kind'] == k), 2), fit_s=FIT[k][1], steep_s=STEEP[k], fit=round(st.mean(sav(f) for f in forms if f['bits'] >= 25 and f['kind'] == k) * FIT[k][1], 2), steep=round(st.mean(sav(f) for f in forms if f['bits'] >= 25 and f['kind'] == k) * STEEP[k], 2)) for k in FIT}
json.dump(OUT, open(HERE + 'final-read.json', 'w'), indent=1)
print(json.dumps(OUT))
