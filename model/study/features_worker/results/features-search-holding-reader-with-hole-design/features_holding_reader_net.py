"""Cost tables of the design, from edge-rows.jsonl and per-form-held.jsonl. Reads records only. Writes net-read.json beside this file and prints it.

Sections:
  reader: bits to draw the primary reader with the read left open, by read form kind, at 25 bits or more and on all forms
  check: what the rest of a reader's body offers a table check
  split: net bits per form at M goals, even split, with and without a share of draws left to the current search (lam), 95% task bootstrap
  link: forms whose bits cross 18 or 25 at M = 1 with a free reader, and tasks whose worst form moves
  cover: expected table recall over the 37 tasks at n proposals under the fitted cost 2^(a + s * bits), with the bits less the saving, at M
  right_goals: for each base run, uncovered forms whose reads are covered but for one: the count of true one-hole goals at 60 s and 600 s
"""
import collections
import csv
import json
import math
import os
import random
import re
import statistics as st

W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
FB = W + 'features-worker/results/features-backward-from-out-content-heldout37/'
CR = W + 'sampler/sampler-worker/sampler-base-cost-read-heldout37/'
KIT = W + 'sampler/sampler-worker/kits/sampler-pool-extended-text-pass1-8be414670/'
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
KINDS = ('RULE', 'DET', 'INIT')
FIT = {'RULE': (11.3, .30), 'DET': (6.0, .50), 'INIT': (11.9, .12)}  # results.md, Where the base of the proposal cost goes
COST12 = {'RULE': 15.0, 'DET': 12.0, 'INIT': 13.4}  # cost at 12 bits, all forms; DET has none in that table, so a + s * 12 of its row
STEEP = {'RULE': .78, 'DET': .78, 'INIT': .26}  # right cell slopes, same section
N = 4522  # median proposals at 600 s of base_s0, form-rows.tsv

edges = [json.loads(x) for x in open(HERE + 'edge-rows.jsonl')]
forms = [json.loads(x) for x in open(FB + 'per-form-held.jsonl')]
forms = [f for f in forms if f['bits'] is not None]
tasks = sorted({f['task'] for f in forms})
OUT = {}


def q(x, p):
    x = sorted(x)
    return x[min(len(x) - 1, int(p * len(x)))] if x else None


def boot(rows, seed=7, n=4000):
    """Mean of (task, value) with a 95% task bootstrap."""
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


# reader cost
rd = {}
for lab, f in (('at25', lambda e: e['bits'] is not None and e['bits'] >= 25), ('all', lambda e: e['bits'] is not None)):
    for k in KINDS + ('ANY',):
        es = [e for e in edges if f(e) and (k == 'ANY' or e['kind'] == k)]
        known = [e for e in es if e.get('reader_open_bits') is not None]
        x = [e['reader_open_bits'] for e in known]
        rd[lab + ' ' + k] = dict(forms=len(es), known=len(known), out_reader=sum(e['reader'] == 'OUT' for e in es), median=q(x, .5), q25=q(x, .25), q75=q(x, .75), under12=sum(v < 12 for v in x), under18=sum(v < 18 for v in x), under25=sum(v < 25 for v in x),
                                 cheaper_than_form=sum(e['reader_open_bits'] < e['bits'] for e in known), median_pick=q([e['pick'] for e in known if e['pick'] is not None], .5), mean_pick=round(st.mean([e['pick'] for e in known if e['pick'] is not None] or [0]), 2), mean_class=round(st.mean([e['class_bits'] for e in known if e.get('class_bits') is not None] or [0]), 2),
                                 reader_one_read=sum(e['reader_reads'] == 1 for e in es), reader_kinds=dict(collections.Counter(e['reader_kind'] for e in es)))
OUT['reader'] = rd

# what a check can read
es = [e for e in edges if e['reader'] != 'OUT']
at = [e for e in es if e['bits'] is not None and e['bits'] >= 25]
OUT['check'] = {lab: dict(edges=len(x), reader_init=sum(e['reader_kind'] == 'INIT' for e in x), hole_in_port=sum(bool(e.get('in_port')) for e in x), hole_in_or=sum(bool(e.get('in_or')) for e in x), rest_empty=sum(e['rest_atoms'] == 0 for e in x), no_shared_label=sum(e['rest_atoms'] > 0 and not e.get('shared') for e in x), table_check=sum(e['reader_kind'] in ('RULE', 'DET') and not e.get('in_port') and not e.get('in_or') and e['rest_atoms'] > 0 and bool(e.get('shared')) for e in x)) for lab, x in (('all', es), ('at25', at))}

# saved bits by form
sav = {(f['task'], f['form']): f.get('t1 full', 0.0) for f in forms}
open_b = {(e['task'], e['form']): e.get('reader_open_bits') for e in edges}
rows25 = [f for f in forms if f['bits'] >= 25]
split = {}
for k in KINDS + ('ANY',):
    fs = [f for f in rows25 if k == 'ANY' or f['kind'] == k]
    split[k] = {}
    for M in (1, 2, 4, 8, 32, 200, 2000):
        for lam in (0, .5, .8):
            # wrong goals give nothing, as the even-split rule assumes
            r0 = [(f['task'], math.log2(lam + (1 - lam) * 2 ** sav[f['task'], f['form']] / M)) if lam or sav[f['task'], f['form']] > -999 else 0 for f in fs]
            # wrong goals give the form its base chance, the generous end
            r1 = [(f['task'], math.log2(1 + (1 - lam if lam else 1) * (2 ** sav[f['task'], f['form']] - 1) / M)) for f in fs]
            split[k]['M%d lam%.1f' % (M, lam)] = dict(wrong_zero=boot(r0), wrong_base=boot(r1))
OUT['split'] = split

# bars
cross = {}
for bar in (14, 18, 21.5, 25):
    cross[str(bar)] = dict(over=sum(f['bits'] >= bar for f in forms), taken_under=sum(f['bits'] >= bar and f['bits'] - sav[f['task'], f['form']] < bar for f in forms), put_over=sum(f['bits'] < bar and f['bits'] - sav[f['task'], f['form']] >= bar for f in forms))
OUT['cross'] = cross
worst = {}
for t in tasks:
    fs = [f for f in forms if f['task'] == t]
    a = max(f['bits'] for f in fs)
    b = max(f['bits'] - max(sav[f['task'], f['form']], 0) for f in fs)
    w = max(fs, key=lambda f: f['bits'])
    worst[t] = dict(before=a, after=round(b, 2), kind=w['kind'], reader_open=open_b.get((t, w['form'])))
OUT['worst'] = dict(median_before=st.median(v['before'] for v in worst.values()), median_after=st.median(v['after'] for v in worst.values()), tasks_under_25_before=sum(v['before'] < 25 for v in worst.values()), tasks_under_25_after=sum(v['after'] < 25 for v in worst.values()), worst_read_by_reader_under_18=sum((v['reader_open'] or 999) < 18 for v in worst.values()), worst_kinds=dict(collections.Counter(v['kind'] for v in worst.values())))


# expected table recall under the fitted cost
def p(kind, b, n, slope=None):
    if kind not in FIT:
        return 0.0
    a, s = FIT[kind]
    if slope:
        s, a = slope[kind], COST12[kind] - slope[kind] * 12
    return 1 - math.exp(-n * 2 ** -(a + s * b))


cover = {}
for name, n in (('n4522', N), ('n1200 about 60 s', 1200), ('n14000 Kaggle hour', 14000), ('n29000 Kaggle 2.1 h', 29000)):
    for sname, slope in (('fit s', None), ('steep s', STEEP)):
        row = {}
        for gname, frac in (('base', None), ('M1 free reader', 1), ('M2 even', 2), ('M4 even', 4), ('M8 even', 8)):
            g = collections.Counter()
            for f in forms:
                k = f['kind']
                if k not in FIT:
                    continue
                b = f['bits']
                x = 0.0 if frac is None else sav[f['task'], f['form']]
                nn = n if frac is None else n / frac
                g['DET' if k == 'DET' else 'nonDET'] += p(k, b - x, nn, slope)
            row[gname] = {k: round(v, 1) for k, v in g.items()}
        cover[name + ' ' + sname] = row
OUT['cover'] = cover

# true one-hole goals in the base runs, new text
NEW = {x['task']: x['gold_sexp'] for x in json.load(open(KIT + 'points-eval.json'))}
HELD = set(open(W + 'sampler/sampler-worker/held/tasks.txt').read().split())
cov = collections.defaultdict(dict)
meta = {}
props = collections.defaultdict(dict)
for r in csv.DictReader(open(CR + 'form-rows.tsv'), delimiter='\t'):
    cov[r['arm']].setdefault(r['task'], {})[int(r['form'])] = int(r['draw']) if r['draw'] else None
    meta[r['task'], int(r['form'])] = r
    props[r['arm']][r['task']] = int(r['proposals_600'])


def reads_of(t):
    lines = [x for x in NEW[t].strip().split('\n') if not x.startswith('(OUT')]
    head, out = {}, []
    for i, x in enumerate(lines):
        names = re.findall(r'&r\d+', x)
        out.append(sorted({head[m] for m in names[1:] if m in head and m != names[0]}))
        head[names[0]] = i
    return out


READS = {t: reads_of(t) for t in HELD}
goals = {}
for arm in ('base_s0', 'base_s1', 'cover_s0', 'cover_s1'):
    for lab, frac in (('at 600 s', 1.0), ('at 1/10 of proposals, about 60 s', .1)):
        c = []
        rdy = []
        one = []
        byk = collections.Counter()
        two = []
        for t in HELD:
            if t not in cov[arm]:
                continue
            cut = props[arm][t] * frac
            done = {f for f, d in cov[arm][t].items() if d is not None and d <= cut}
            ready = 0
            hole = 0
            for i, rs in enumerate(READS[t]):
                if i in done or not rs:
                    continue
                un = [x for x in rs if x not in done]
                if not un:
                    ready += 1
                elif len(un) == 1 and len(rs) >= 2:
                    hole += 1
                    byk[meta[t, i]['kind']] += 1
                elif len(un) == 1:
                    hole += 1
                    byk[meta[t, i]['kind']] += 1
            c.append(hole)
            rdy.append(ready)
            one.append(sum(1 for i, rs in enumerate(READS[t]) if i not in done and len(rs) == 1 and rs[0] not in done))
        goals[arm + ' ' + lab] = dict(tasks=len(c), median_goals=st.median(c), q25=q(c, .25), q75=q(c, .75), mean=round(st.mean(c), 1), median_ready_with_reads=st.median(rdy), goals_by_reader_kind=dict(byk), median_goals_reader_of_one_read=st.median(one))
OUT['right_goals'] = goals
nr = collections.Counter(len(rs) for t in HELD for rs in READS[t])
OUT['reads_per_form_new_text'] = dict(sorted(nr.items()))
json.dump(OUT, open(HERE + 'net-read.json', 'w'), indent=1)
for k in ('reader', 'check', 'cross', 'worst', 'cover', 'right_goals', 'reads_per_form_new_text'):
    print(k, json.dumps(OUT[k], indent=0)[:6000].replace('\n', ' '))
for k in KINDS + ('ANY',):
    print(k, {m: v['wrong_zero'][:3] + ['|'] + v['wrong_base'][:3] for m, v in split[k].items()})
