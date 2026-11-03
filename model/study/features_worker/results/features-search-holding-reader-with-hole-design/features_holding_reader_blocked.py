"""Two last reads. Forms at 25 bits or more on the new text at the end of the 600 s arms: covered, ready, blocked. Expected table recall if the kind pick and the column picks add to the saving. Writes blocked-read.json beside this file and prints it."""
import collections
import csv
import json
import math
import os
import re

W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
FB = W + 'features-worker/results/features-backward-from-out-content-heldout37/'
CR = W + 'sampler/sampler-worker/sampler-base-cost-read-heldout37/'
KIT = W + 'sampler/sampler-worker/kits/sampler-pool-extended-text-pass1-8be414670/'
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
NEW = {x['task']: x['gold_sexp'] for x in json.load(open(KIT + 'points-eval.json'))}
HELD = set(open(W + 'sampler/sampler-worker/held/tasks.txt').read().split())


def reads_of(t):
    lines = [x for x in NEW[t].strip().split('\n') if not x.startswith('(OUT')]
    head, out = {}, []
    for i, x in enumerate(lines):
        names = re.findall(r'&r\d+', x)
        out.append(sorted({head[m] for m in names[1:] if m in head and m != names[0]}))
        head[names[0]] = i
    return out


READS = {t: reads_of(t) for t in HELD}
rows = collections.defaultdict(dict)
for r in csv.DictReader(open(CR + 'form-rows.tsv'), delimiter='\t'):
    rows[r['arm'], r['task']][int(r['form'])] = r
OUT = {}
for arm in ('base_s0', 'base_s1'):
    c = collections.Counter()
    for t in HELD:
        fs = rows[arm, t]
        done = {i for i, r in fs.items() if r['draw']}
        for i, rs in enumerate(READS[t]):
            r = fs[i]
            b = float(r['bits']) if r['bits'] not in ('', 'None') else 999
            band = 'at 25 or more' if b >= 25 else 'under 25'
            st = 'covered' if i in done else 'ready' if all(x in done for x in rs) else 'blocked'
            c[band + ' ' + st] += 1
    OUT[arm] = dict(sorted(c.items()))

FIT = {'RULE': (11.3, .30), 'DET': (6.0, .50), 'INIT': (11.9, .12)}
COST12 = {'RULE': 15.0, 'DET': 12.0, 'INIT': 13.4}
STEEP = {'RULE': .78, 'DET': .78, 'INIT': .26}
forms = [json.loads(x) for x in open(FB + 'per-form-held.jsonl')]
forms = [f for f in forms if f['bits'] is not None and f['kind'] in FIT]


def h(k, b, sl):
    a, s = FIT[k]
    if sl:
        s, a = sl[k], COST12[k] - sl[k] * 12
    return 2 ** -(a + s * b)


def recall(n, sl, plus, M):
    t = 0.0
    for f in forms:
        if f['kind'] == 'DET':
            continue
        k, b = f['kind'], f['bits']
        x = f.get('t1 full', 0.0) + plus
        base = h(k, b, sl)
        t += 1 - math.exp(-n * (h(k, b - x, sl) / M + (M - 1) / M * base))
    return t


v = {}
for sn, sl in (('fit s', None), ('steep s', STEEP)):
    b0 = recall(4522, sl, 0, 1) if False else sum(1 - math.exp(-4522 * h(f['kind'], f['bits'], sl)) for f in forms if f['kind'] != 'DET')
    for plus, lab in ((.42, 'kind pick .42'), (1.84, 'kind .42 and columns 1.42')):
        for M in (1, 13):
            v['%s, %s, M%d soft' % (sn, lab, M)] = round(recall(4522, sl, plus, M) - b0, 1)
OUT['recall_with_more_saving_600s_nonDET'] = v
json.dump(OUT, open(HERE + 'blocked-read.json', 'w'), indent=1)
print(json.dumps(OUT))
