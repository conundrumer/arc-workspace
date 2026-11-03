"""Expected table recall on the census text under the fitted cost, for the arms of the design. Reads edge-rows.jsonl and records. Writes cover-read.json beside this file and prints it.

Hazard of a form per proposal, h(b) = 2^-(a + s * b). A goal arm gives a form the rate n * [lam * h(b) + (1 - lam) * (h(b - x) / M + keep * (M - 1) / M * h(b))], where x is the form's saved bits (t1 full), and keep is 0 where a draw under another goal has no chance at the form (the rule "subtract log2 M") and 1 where it keeps the form's base chance (a soft tilt, the generous end).
"""
import collections
import csv
import json
import math
import os
import re
import statistics as st

W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
FB = W + 'features-worker/results/features-backward-from-out-content-heldout37/'
CR = W + 'sampler/sampler-worker/sampler-base-cost-read-heldout37/'
KIT = W + 'sampler/sampler-worker/kits/sampler-pool-extended-text-pass1-8be414670/'
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
FIT = {'RULE': (11.3, .30), 'DET': (6.0, .50), 'INIT': (11.9, .12)}
COST12 = {'RULE': 15.0, 'DET': 12.0, 'INIT': 13.4}
STEEP = {'RULE': .78, 'DET': .78, 'INIT': .26}
edges = {(e['task'], e['form']): e for e in map(json.loads, open(HERE + 'edge-rows.jsonl'))}
forms = [json.loads(x) for x in open(FB + 'per-form-held.jsonl')]
forms = [f for f in forms if f['bits'] is not None and f['kind'] in FIT]
cand = {}
for x in open(FB + 'per-form-candidate-held.jsonl'):
    r = json.loads(x)
    cand[r['task'], r['form']] = r


def h(kind, b, slope):
    a, s = FIT[kind]
    if slope:
        s, a = slope[kind], COST12[kind] - slope[kind] * 12
    return 2 ** -(a + s * b)


def recall(n, slope, gain, lam=0.0, M=1, keep=0.0):
    """Expected forms covered, non-DET and DET. gain(f) is the saved bits of form f, or None where the form has no held goal."""
    g = collections.Counter()
    for f in forms:
        k, b = f['kind'], f['bits']
        x = gain(f)
        base = h(k, b, slope)
        rate = base if x is None else lam * base + (1 - lam) * (h(k, b - x, slope) / M + keep * (M - 1) / M * base)
        g['DET' if k == 'DET' else 'nonDET'] += 1 - math.exp(-n * rate)
    return round(g['nonDET'], 1), round(g['DET'], 1)


sav = lambda f: f.get('t1 full', 0.0)  # noqa: E731
OUT = {}
tab = {}
for nm, n in (('600 s', 4522), ('60 s', 1200)):
    for sn, sl in (('fit s', None), ('steep s', STEEP)):
        base = recall(n, sl, lambda f: None)
        row = dict(base=base)
        for M in (1, 2, 4, 13, 32, 200):
            for lam, keep, lab in ((0, 0, 'hard'), (0, 1, 'soft'), (.5, 0, 'hard, lam .5'), (.8, 0, 'hard, lam .8'), (.5, 1, 'soft, lam .5')):
                got = recall(n, sl, sav, lam, M, keep)
                row['M%d %s' % (M, lab)] = (round(got[0] - base[0], 1), round(got[1] - base[1], 1))
        tab[nm + ' ' + sn] = row
OUT['goal_arm_gain_over_base'] = tab

# only forms whose reader is drawable hold a goal
reach = {}
for H in (12, 14, 18, 21.5):
    def gain(f, H=H):
        e = edges.get((f['task'], f['form']))
        if not e or e.get('reader_open_bits') is None or e['reader_open_bits'] >= H:
            return None
        return sav(f)
    r = dict(forms_at25=sum(f['bits'] >= 25 and gain(f) is not None for f in forms), forms_all=sum(gain(f) is not None for f in forms))
    for nm, n in (('600 s', 4522),):
        for sn, sl in (('fit s', None), ('steep s', STEEP)):
            base = recall(n, sl, lambda f: None)
            for M in (1, 13):
                got = recall(n, sl, gain, 0, M, 1)
                r['%s %s M%d soft' % (nm, sn, M)] = (round(got[0] - base[0], 1), round(got[1] - base[1], 1))
            for k in ('RULE', 'DET', 'INIT'):
                xs = [sav(f) for f in forms if f['kind'] == k and f['bits'] >= 25 and gain(f) is not None]
                r['mean saved at25 ' + k] = (round(st.mean(xs), 2) if xs else None, len(xs))
    reach[str(H)] = r
OUT['reachable_reader'] = reach

# goals picked by realized gain, the most a pick of goals could do
top = {}
for k_goals in (1, 2, 4):
    def pick_gain(f, chosen={}):
        return sav(f) if (f['task'], f['form']) in chosen else None
    chosen = set()
    by = collections.defaultdict(list)
    for f in forms:
        by[f['task']].append(f)
    for t, fs in by.items():
        for f in sorted(fs, key=lambda f: -sav(f))[:k_goals]:
            chosen.add((t, f['form']))
    for sn, sl in (('fit s', None), ('steep s', STEEP)):
        base = recall(4522, sl, lambda f: None)
        got = recall(4522, sl, lambda f: sav(f) if (f['task'], f['form']) in chosen else None, 0, k_goals, 1)
        top['top %d per task, %s' % (k_goals, sn)] = (round(got[0] - base[0], 1), round(got[1] - base[1], 1))
OUT['goals_by_realized_gain_soft'] = top

# rest of the reader
rest = collections.Counter()
for e in edges.values():
    if e['bits'] is not None and e['bits'] >= 25 and e['reader'] != 'OUT':
        rest[min(e['rest_atoms'], 4)] += 1
OUT['rest_atoms_at25'] = dict(sorted(rest.items()))

# the reader's own derived picks given a hole: per-form-candidate-held is keyed by the form that has the pick
cd = {}
for arm in ('hole', 'holeb', 'both', 'out'):
    for k in ('RULE', 'DET', 'INIT', 'ANY'):
        for lab, f0 in (('at25', lambda f: f['bits'] >= 25), ('all', lambda f: True)):
            xs = [cand[f['task'], f['form']][arm] for f in forms if (k == 'ANY' or f['kind'] == k) and f0(f) and (f['task'], f['form']) in cand]
            cd['%s %s %s' % (arm, k, lab)] = (round(st.mean(xs), 2), round(st.median(xs), 2), len(xs))
OUT['candidate_tilt_by_kind'] = cd
for sn, sl in (('fit s', None), ('steep s', STEEP)):
    for nm, n in (('600 s', 4522), ('60 s', 1200)):
        base = recall(n, sl, lambda f: None)
        for arm in ('holeb', 'hole', 'both'):
            got = recall(n, sl, lambda f: cand.get((f['task'], f['form']), {}).get(arm, 0.0))
            OUT['candidate tilt cover %s %s %s' % (arm, nm, sn)] = (round(got[0] - base[0], 1), round(got[1] - base[1], 1))

# ready forms at the end of the base runs, new text
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
ready = {}
for arm in ('base_s0', 'base_s1', 'cover_s0', 'cover_s1'):
    out = collections.Counter()
    for t in HELD:
        fs = rows[arm, t]
        done = {i for i, r in fs.items() if r['draw']}
        for i, rs in enumerate(READS[t]):
            if i in done or not rs or any(x not in done for x in rs):
                continue
            r = fs[i]
            k = r['kind']
            b = float(r['bits']) if r['bits'] not in ('', 'None') else 999
            band = 'under 12' if b < 12 else 'under 18' if b < 18 else 'under 25' if b < 25 else '25 or more'
            out[k + ' ' + band] += 1
            out[k] += 1
            out['one read' if len(rs) == 1 else 'two or more reads'] += 1
    ready[arm] = dict(sorted(out.items()))
OUT['ready_with_reads_end_600s_new_text'] = ready
json.dump(OUT, open(HERE + 'cover-read.json', 'w'), indent=1)
print(json.dumps(OUT, indent=0).replace('\n', ' ')[:12000])
