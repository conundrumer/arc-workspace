"""Reads the shard outputs of job.py and applies the rule of design.md. Works on partial output.

  bash env.sh read.py [--arms refit_s0,refit_s1] [--files F ...] [--outdir DIR] [--covered]

Reads forms.*of*.jsonl (forms-<arms>.*of*.jsonl with --arms) and checks.*of*.jsonl. Writes places.tsv, parts.tsv, summary.json, results.json (the same), results.md
in --outdir (this folder by default) and prints the message.
--covered reads forms-covered.*of*.jsonl (the control, from job.py --covered) and writes into covered/ of this folder. It also reads the C rows (forms.*of*.jsonl, class C) and adds, to results.md
and summary.json, the table that sets C and covered side by side (section "C against covered"), and compare-forms.tsv with scope_n and the relation-pick gap of each form.
"""
import argparse
import collections
import csv
import glob
import json
import os
import re
import statistics
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943'
ap = argparse.ArgumentParser()
ap.add_argument('--arms', default=None)
ap.add_argument('--files', nargs='*', default=None)
ap.add_argument('--outdir', default=None)
ap.add_argument('--covered', action='store_true')
ARGS = ap.parse_args()
if ARGS.outdir is None:
    ARGS.outdir = os.path.join(HERE, 'covered') if ARGS.covered else HERE

ORDER_PART = 'orders: entropy credit'
SCOPE_PLACES = ['relation pick: read', 'relation pick: builtin', 'op pick', 'argument fill: read', 'argument fill: other', 'join coin', 'stop', 'proposer', 'OR and ALL', 'INIT structure', 'order sum', 'other']
PRIORS = 'priors and code'
PLACES = SCOPE_PLACES + [PRIORS]
BOOT, BAR, NOGAP = 2000, 0.60, 1.0
ATOM = re.compile(r'^(\S+) atom: (.+)$')
ARG_PHASES = ('column', 'column stop', 'value: label', 'value: other')


def reads(text):
    t = text.strip()
    while t.startswith('(NOT '):
        t = t[5:].strip()
    m = re.match(r'\(\s*(\S+)', t)
    return bool(m and re.match(r'&[rf]\d+', m.group(1)))


def plain_place(s):
    if s == ORDER_PART:
        return 'order sum'
    if s.endswith('br:else-NOT pick'):
        return 'op pick'
    if re.search(r'(^| )(top:stop|br:stop|br:go on)$', s):
        return 'stop'
    if s in ('proposer', 'proposer or atoms'):
        return 'proposer'
    if re.search(r'(^| )(or:|br:|top:no OR$|top:no ALL$|all:guard stops$)', s) or s == 'key: which labels an OR exports':
        return 'OR and ALL'
    if re.match(r'(component|keyed|key: count of labels|key: which labels|long body|key partly read)$', s) or re.match(r'(port|outside|head|rigid):', s):
        return 'INIT structure'
    return 'other'


def places_of(w, miss):
    """{place: bits} of a walk record, and a list of (part, bits) that went to `other`. miss counts the atom phases with no atom row."""
    out, odd = collections.defaultdict(float), []
    atoms, detail = w.get('atoms') or [], w.get('detail') or []
    for name, v in (w.get('parts') or {}).items():
        m = ATOM.match(name)
        if not m:
            p = plain_place(name)
            out[p] += v
            if p == 'other':
                odd.append((name, v))
            continue
        ctx, phase = m.groups()
        if phase == 'join mix':
            out['join coin'] += v
        elif phase == 'relation (op)':
            out['op pick'] += v
        elif phase == 'relation' or phase in ARG_PHASES:
            rows = [(a, d) for a, d in zip(atoms, detail) if phase in d['cur']]
            use = [r for r in rows if r[0][0] == ctx] or rows
            tot = sum(d['cur'][phase] for _, d in use)
            if not use or abs(tot) < 1e-9:
                if abs(v) > 1e-9:
                    miss[0] += 1
                rd = 0.0
            else:
                rd = v * sum(d['cur'][phase] for a, d in use if reads(a[1])) / tot
            if phase == 'relation':
                out['relation pick: read'] += rd
                out['relation pick: builtin'] += v - rd
            else:
                out['argument fill: read'] += rd
                out['argument fill: other'] += v - rd
        else:
            out['other'] += v
            odd.append((name, v))
    return dict(out), odd


def valid(w):
    return bool(w) and w.get('total') is not None and not w.get('bad') and not w.get('dead') and not w.get('left') and w.get('valid', True)


def med(x):
    return statistics.median(x) if x else float('nan')


def f1(x):
    return 'NA' if x is None else '%.2f' % x


# ---------------------------------------------------------------- rows

pat = 'forms-%s.*of*.jsonl' % ARGS.arms.replace(',', '+') if ARGS.arms else 'forms.*of*.jsonl'
if ARGS.covered:
    pat = 'forms-covered-%s.*of*.jsonl' % ARGS.arms.replace(',', '+') if ARGS.arms else 'forms-covered.*of*.jsonl'
files = ARGS.files if ARGS.files is not None else sorted(glob.glob(os.path.join(HERE, pat)))
rows = {}
for f in files:
    for l in open(f):
        if l.strip():
            x = json.loads(l)
            rows[(x['arm'], x['task'], x['g'])] = x
rows = [rows[k] for k in sorted(rows, key=lambda k: (k[1], k[0], k[2]))]
chk = []
for f in sorted(glob.glob(os.path.join(HERE, 'checks-covered.*of*.jsonl' if ARGS.covered else 'checks.*of*.jsonl'))) if ARGS.files is None else []:
    chk += [json.loads(l) for l in open(f) if l.strip()]

expected = None
if ARGS.covered:
    expected = sum(1 for x in csv.DictReader(open(RUN + '/scope-loss/forms.tsv'), delimiter='\t') if x['class'] == 'covered' and x['arm'] in (ARGS.arms.split(',') if ARGS.arms else ('bundle_s0', 'bundle_s1')))
elif not ARGS.arms:
    fr = list(csv.DictReader(open(RUN + '/scope-loss/forms.tsv'), delimiter='\t'))
    ex = {(x['arm'], x['task'], int(x['g'])) for x in fr if x['class'] == 'C' and x['arm'] in ('bundle_s0', 'bundle_s1')}
    ex |= {('bundle_s' + x['seed'], x['task'], int(x['g'])) for x in csv.DictReader(open(RUN + '/frontier/ready.tsv'), delimiter='\t') if x['nreads'] == '1' and x['bk_primary'] == 'proposal'}
    expected = len(ex)

def annotate(rs, miss, odd_all):
    for r in rs:
        r['_sr'] = False
        r['_measured'] = False
        if r.get('status') == 'mapped' and r.get('table_check') is True and valid(r.get('S')) and valid(r.get('R')):
            r['_sr'] = True
            r['_S'], oddS = places_of(r['S'], miss)
            r['_R'], oddR = places_of(r['R'], miss)
            for n, v in oddS + oddR:
                odd_all[n] += abs(v)
            db = (r.get('DB') or {}).get('bits')
            r['_scope'] = {p: r['_S'].get(p, 0.0) - r['_R'].get(p, 0.0) for p in SCOPE_PLACES}
            if db is not None:
                r['_measured'] = True
                r['_gap'] = {**r['_scope'], PRIORS: r['R']['total'] - db}
                r['_total_gap'] = r['S']['total'] - db


N = len(rows)
miss = [0]
odd_all = collections.Counter()
annotate(rows, miss, odd_all)
meas = [r for r in rows if r['_measured']]
srs = [r for r in rows if r['_sr']]
absent = [r for r in rows if r.get('status') == 'read relation not in the scope']
M, X = len(meas), len(absent)
Y = N - M - X


def mass(rs, key, places):
    return np.array([sum(r[key][p] for r in rs) for p in places])


def shares(m):
    pos = np.maximum(m, 0.0)
    return pos / pos.sum() if pos.sum() > 0 else np.zeros_like(pos)


def boot(rs, key, places, top):
    """Task bootstrap: the 2.5% and 97.5% points of the share of each place and of T3 over the places `top` (indices)."""
    tasks = sorted({r['task'] for r in rs})
    if not rs:
        return None
    mat = np.array([[sum(r[key][p] for r in rs if r['task'] == t) for p in places] for t in tasks])
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(tasks), size=(BOOT, len(tasks)))
    sh, t3 = np.zeros((BOOT, len(places))), np.zeros(BOOT)
    for b in range(BOOT):
        pos = np.maximum(mat[idx[b]].sum(axis=0), 0.0)
        tot = pos.sum()
        sh[b] = pos / tot if tot > 0 else 0.0
        t3[b] = sh[b][top].sum()
    return dict(share_lo=np.percentile(sh, 2.5, axis=0), share_hi=np.percentile(sh, 97.5, axis=0), t3_lo=float(np.percentile(t3, 2.5)), t3_hi=float(np.percentile(t3, 97.5)), n_tasks=len(tasks))


def analyse(rs, key, places):
    if not rs:
        return None
    m = mass(rs, key, places)
    s = shares(m)
    top = [int(i) for i in np.argsort(-s, kind='stable')[:3]]
    b = boot(rs, key, places, top)
    big = collections.Counter(max(places, key=lambda p: r[key][p]) for r in rs)
    out = dict(places=[], top3=[places[i] for i in top], T3=float(s[top].sum()), T3_lo=b['t3_lo'], T3_hi=b['t3_hi'], n_forms=len(rs), n_tasks=b['n_tasks'],
               few=b['t3_lo'] >= BAR, P=float(np.maximum(m, 0).sum()))
    for i, p in enumerate(places):
        out['places'].append(dict(place=p, sum=float(m[i]), share=float(s[i]), lo=float(b['share_lo'][i]), hi=float(b['share_hi'][i]), median=med([r[key][p] for r in rs]), n_largest=big.get(p, 0), per_form=float(m[i] / len(rs))))
    return out


A = analyse(meas, '_gap', PLACES)
B = analyse(srs, '_scope', SCOPE_PLACES)
median_gap = med([r['_total_gap'] for r in meas]) if meas else None

# ---------------------------------------------------------------- the message

head = '%d forms counted (%d measured, %d with a read relation absent from the scope, %d not measured)' % (N, M, X, Y)
if not meas:
    msg = head + '; no measured form yet.'
elif median_gap < NOGAP:
    msg = head + '; median gap %.2f bits: no gap.' % median_gap
elif not A['few']:
    msg = head + '; median gap %.2f bits over the dag bits; spread: the top 3 places hold %.2f of the gap [%.2f, %.2f].' % (median_gap, A['T3'], A['T3_lo'], A['T3_hi'])
else:
    pl = {p['place']: p for p in A['places']}
    parts = ', '.join('%s (%.1f bits a form, %d%%)' % (p, pl[p]['per_form'], round(100 * pl[p]['share'])) for p in A['top3'])
    msg = head + '; median gap %.2f bits over the dag bits; it sits in %s: T3 %.2f [%.2f, %.2f] of the gap.' % (median_gap, parts, A['T3'], A['T3_lo'], A['T3_hi'])
    if PRIORS in A['top3']:
        d = [r['R']['total'] - r['DB']['bits'] for r in meas]
        msg += '\nR - DB (priors and code): median %.2f bits, largest absolute %.2f.' % (med(d), max(abs(x) for x in d))
if expected is not None and N < expected:
    msg += '\nPARTIAL: %d of %d forms are in the shard files.' % (N, expected)

# ---------------------------------------------------------------- checks

C = {}
C['1 table check'] = dict(fails=['%s %s g%d' % (r['arm'], r['task'], r['g']) for r in rows if r.get('status') == 'table differs'], mapped=sum(r.get('status') == 'mapped' for r in rows),
                          mapped_not_passing=['%s %s g%d' % (r['arm'], r['task'], r['g']) for r in rows if r.get('status') == 'mapped' and r.get('table_check') is not True])
C['2 walks'] = dict(invalid=['%s %s g%d %s: %s' % (r['arm'], r['task'], r['g'], w, 'missing' if not r.get(w) else 'bad %s dead %s left %s' % (str((r[w].get('bad') or [''])[0])[:60], r[w].get('dead'), r[w].get('left')))
                             for r in rows if r.get('status') == 'mapped' for w in ('S', 'R') if not valid(r.get(w))])
C['3 kind'] = dict(not_gold_kind=['%s %s g%d visit %s gold %s' % (r['arm'], r['task'], r['g'], r.get('visit_kind'), r.get('kind')) for r in rows if r.get('cls') in ('C', 'covered') and r.get('kind_ok') is False],
                   k_forms=['%s %s g%d visit %s gold %s' % (r['arm'], r['task'], r['g'], r.get('visit_kind'), r.get('kind')) for r in rows if r.get('cls') not in ('C', 'covered') and r.get('visit_kind')])
bad4 = []
for r in srs:
    for w in ('S', 'R'):
        s = sum(r['_' + w].values())
        if abs(s - r[w]['total']) > 0.05:
            bad4.append('%s %s g%d %s: places %.3f total %.3f' % (r['arm'], r['task'], r['g'], w, s, r[w]['total']))
C['4 sums'] = dict(beyond_005=bad4, other_parts={k: round(v, 3) for k, v in odd_all.items()}, other_count=len(odd_all), other_bits=round(sum(odd_all.values()), 3))
C['5 read/other split'] = dict(phases_without_atom_row=miss[0])
rd = {}
for st in ('exact', 'one', 'bound'):
    d = [(r['R']['total'] - r['DB']['bits'], r) for r in rows if r.get('status') == 'mapped' and valid(r.get('R')) and (r.get('DB') or {}).get('status') == st and r['DB']['bits'] is not None]
    if d:
        v = [x for x, _ in d]
        q = np.percentile(v, [25, 75])
        rd[st] = dict(n=len(v), median=float(np.median(v)), iqr=[float(q[0]), float(q[1])], max_abs=float(max(abs(x) for x in v)), beyond_3=['%s %s g%d %.2f' % (r['arm'], r['task'], r['g'], x) for x, r in d if abs(x) > 3])
C['6 R against DB (not a gate)'] = rd
C['7 order free'] = dict(n=len(chk), failed=[c for c in chk if not c['c7_ok']], items=[(c['task'], c['g'], c['S'], c['last_order_total']) for c in chk])
C['8 determinism'] = dict(n=len(chk), failed=[c for c in chk if not c['c8_ok']], items=[(c['task'], c['g'], c['S'], c['rerun_total']) for c in chk])
C['9 exact or estimate'] = dict(estimates=['%s %s g%d %s' % (r['arm'], r['task'], r['g'], w) for r in rows if r.get('status') == 'mapped' for w in ('S', 'R') if r.get(w) and not (r[w].get('orders') or {}).get('exact', True)])

# ---------------------------------------------------------------- C against covered

RELP = ('relation pick: read', 'relation pick: builtin')
CMP = None
if ARGS.covered:
    carms = ARGS.arms.split(',') if ARGS.arms else ['bundle_s0', 'bundle_s1']
    crows = {}
    for f in sorted(glob.glob(os.path.join(HERE, ('forms-' + ARGS.arms.replace(',', '+') if ARGS.arms else 'forms') + '.*of*.jsonl'))):
        for l in open(f):
            if l.strip():
                x = json.loads(l)
                if x.get('cls') == 'C' and x['arm'] in carms:
                    crows[(x['arm'], x['task'], x['g'])] = x
    crows = [crows[k] for k in sorted(crows, key=lambda k: (k[1], k[0], k[2]))]
    annotate(crows, [0], collections.Counter())

    def relp(r, key):
        return sum(r[key][p] for p in RELP)

    def pos_share(rs, key, places, group):
        m = {p: sum(r[key][p] for r in rs) for p in places}
        pos = sum(max(v, 0.0) for v in m.values())
        return sum(max(m[p], 0.0) for p in group) / pos if pos > 0 else float('nan')

    def tboot(rs, stat, rng_seed=0, n=BOOT):
        """The 2.5% and 97.5% points of stat(forms) over task resamples (a task brings all its forms)."""
        tasks = sorted({r['task'] for r in rs})
        if not tasks:
            return None
        by = {t: [r for r in rs if r['task'] == t] for t in tasks}
        rng = np.random.default_rng(rng_seed)
        idx = rng.integers(0, len(tasks), size=(n, len(tasks)))
        v = np.array([stat([r for i in idx[b] for r in by[tasks[i]]]) for b in range(n)])
        v = v[~np.isnan(v)]
        return (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) if len(v) else None

    def rank_corr(a, b):
        if len(a) < 3:
            return None
        ra, rb = np.argsort(np.argsort(a, kind='stable'), kind='stable'), np.argsort(np.argsort(b, kind='stable'), kind='stable')
        return float(np.corrcoef(ra, rb)[0, 1])

    def setinfo(rs):
        meas_, srs_ = [r for r in rs if r['_measured']], [r for r in rs if r['_sr']]
        sn = [r['scope_n'] for r in srs_]
        q = np.percentile(sn, [25, 75]) if sn else [float('nan')] * 2
        return dict(entered=len(rs), mapped_sr=len(srs_), measured=len(meas_), tasks=len({r['task'] for r in srs_}),
                    median_S_DB=med([r['_total_gap'] for r in meas_]), median_S_R=med([r['S']['total'] - r['R']['total'] for r in srs_]),
                    median_scope_n=med(sn), scope_n_iqr=[float(q[0]), float(q[1])], meas=meas_, srs=srs_)
    CS, VS = setinfo(crows), setinfo(rows)
    CMP = dict(C=CS, covered=VS, bases=[])
    for name, key, places, use in (('S - DB (measured forms)', '_gap', PLACES, 'meas'), ('S - R (scope places, forms with S and R)', '_scope', SCOPE_PLACES, 'srs')):
        b = dict(name=name, key=key, places=[], sets={})
        for lab, Z in (('C', CS), ('covered', VS)):
            rs = Z[use]
            sh = {p: pos_share(rs, key, places, [p]) for p in places} if rs else {}
            b['sets'][lab] = dict(n=len(rs), tasks=len({r['task'] for r in rs}),
                                  sum={p: sum(r[key][p] for r in rs) for p in places}, median={p: med([r[key][p] for r in rs]) for p in places}, share=sh,
                                  relp_share=pos_share(rs, key, places, RELP) if rs else float('nan'),
                                  relp_share_ci=tboot(rs, lambda f: pos_share(f, key, places, RELP)) if rs else None,
                                  relp_read_share_ci=tboot(rs, lambda f: pos_share(f, key, places, RELP[:1])) if rs else None,
                                  relp_median=med([relp(r, key) for r in rs]), relp_mean=float(np.mean([relp(r, key) for r in rs])) if rs else float('nan'),
                                  relp_median_ci=tboot(rs, lambda f: med([relp(r, key) for r in f])) if rs else None,
                                  rho_scope_n_relp=rank_corr([r['scope_n'] for r in rs], [relp(r, key) for r in rs]))
        if CS[use] and VS[use]:
            rng = np.random.default_rng(1)
            tc, tv = sorted({r['task'] for r in CS[use]}), sorted({r['task'] for r in VS[use]})
            bc, bv = {t: [r for r in CS[use] if r['task'] == t] for t in tc}, {t: [r for r in VS[use] if r['task'] == t] for t in tv}
            ic, iv = rng.integers(0, len(tc), size=(BOOT, len(tc))), rng.integers(0, len(tv), size=(BOOT, len(tv)))
            d = np.array([pos_share([r for i in ic[k] for r in bc[tc[i]]], key, places, RELP) - pos_share([r for i in iv[k] for r in bv[tv[i]]], key, places, RELP) for k in range(BOOT)])
            dm = np.array([med([relp(r, key) for i in ic[k] for r in bc[tc[i]]]) - med([relp(r, key) for i in iv[k] for r in bv[tv[i]]]) for k in range(BOOT)])
            b['diff_share_ci'] = [float(np.nanpercentile(d, 2.5)), float(np.nanpercentile(d, 97.5))]
            b['diff_median_ci'] = [float(np.nanpercentile(dm, 2.5)), float(np.nanpercentile(dm, 97.5))]
        b['place_names'] = places
        CMP['bases'].append(b)
    os.makedirs(ARGS.outdir, exist_ok=True)
    with open(os.path.join(ARGS.outdir, 'compare-forms.tsv'), 'w') as fh:
        fh.write('set\tarm\ttask\tg\tkind\tscope_n\tslot_tries\tS\tR\tDB\tS-DB\tS-R\trelation pick: read\trelation pick: builtin\trelation pick (S-R)\n')
        for lab, Z in (('C', CS), ('covered', VS)):
            for r in Z['srs']:
                db = (r.get('DB') or {}).get('bits')
                fh.write('%s\t%s\t%s\t%d\t%s\t%s\t%s\t%.3f\t%.3f\t%s\t%s\t%.3f\t%.3f\t%.3f\t%.3f\n' % (
                    lab, r['arm'], r['task'], r['g'], r.get('kind'), r.get('scope_n'), r.get('slot_tries'), r['S']['total'], r['R']['total'], '' if db is None else '%.3f' % db,
                    '%.3f' % r['_total_gap'] if r['_measured'] else '', r['S']['total'] - r['R']['total'], r['_scope'][RELP[0]], r['_scope'][RELP[1]], relp(r, '_scope')))

summary = dict(message=msg, N=N, measured=M, absent=X, not_measured=Y, expected=expected, median_gap=median_gap, verdict_places=A, scope_only=B, checks=C, files=files,
               statuses=dict(collections.Counter(r.get('status') for r in rows)), bar=BAR, nogap=NOGAP)
if CMP:
    summary['c_against_covered'] = {k: ({a: b for a, b in v.items() if a not in ('meas', 'srs')} if k in ('C', 'covered') else v) for k, v in CMP.items()}

# ---------------------------------------------------------------- files

os.makedirs(ARGS.outdir, exist_ok=True)
with open(os.path.join(ARGS.outdir, 'places.tsv'), 'w') as fh:
    fh.write('arm\ttask\tg\tplace\tS_k\tR_k\tgap\n')
    for r in srs:
        for p in SCOPE_PLACES:
            fh.write('%s\t%s\t%d\t%s\t%.3f\t%.3f\t%.3f\n' % (r['arm'], r['task'], r['g'], p, r['_S'].get(p, 0.0), r['_R'].get(p, 0.0), r['_scope'][p]))
        if r['_measured']:
            fh.write('%s\t%s\t%d\t%s\t\t\t%.3f\n' % (r['arm'], r['task'], r['g'], PRIORS, r['_gap'][PRIORS]))
ps = collections.defaultdict(lambda: [0.0, 0.0])
for r in srs:
    for w, i in (('S', 0), ('R', 1)):
        for k, v in r[w]['parts'].items():
            ps[k][i] += v
with open(os.path.join(ARGS.outdir, 'parts.tsv'), 'w') as fh:
    fh.write('part\tS\tR\tS-R\t(forms with S and R valid: %d)\n' % len(srs))
    for k in sorted(ps):
        fh.write('%s\t%.3f\t%.3f\t%.3f\n' % (k, ps[k][0], ps[k][1], ps[k][0] - ps[k][1]))
json.dump(summary, open(os.path.join(ARGS.outdir, 'summary.json'), 'w'), indent=1, default=str)
json.dump(summary, open(os.path.join(ARGS.outdir, 'results.json'), 'w'), indent=1, default=str)


def table(header, body):
    return '\n'.join(['| ' + ' | '.join(header) + ' |', '|' + '---|' * len(header)] + ['| ' + ' | '.join(str(c) for c in b) + ' |' for b in body])


def place_table(Z):
    return table(['place', 'sum of gaps (bits)', 'share [2.5%, 97.5%]', 'median gap a form', 'forms where largest'],
                 [[p['place'], '%.1f' % p['sum'], '%.2f [%.2f, %.2f]' % (p['share'], p['lo'], p['hi']), '%.2f' % p['median'], p['n_largest']] for p in Z['places']])


md = ['# Scope loss, covered forms (control for class C): results' if ARGS.covered else '# Scope loss, class C: results', '', msg, '']
md += ['## Table 1: forms', '', 'By source and arm', '',
       table(['source', 'arm', 'forms'], [[s, a, n] for (s, a), n in sorted(collections.Counter((r.get('source'), r['arm']) for r in rows).items())]), '', 'By status', '',
       table(['status', 'forms'], [[s, n] for s, n in sorted(collections.Counter(r.get('status') for r in rows).items())]), '']
body = []
for r in rows:
    big = max(PLACES, key=lambda p: r['_gap'][p]) if r['_measured'] else ''
    db = r.get('DB') or {}
    sr = (r['S']['total'] - r['R']['total']) if r['_sr'] else None
    sdb = r['_total_gap'] if r['_measured'] else None
    body.append([r['arm'], r['task'], r['g'], r.get('kind'), r.get('source'), r.get('scope_n'), r.get('slot_tries'), f1((r.get('S') or {}).get('total')), f1((r.get('R') or {}).get('total')),
                 '%s (%s)' % (f1(db.get('bits')), db.get('status')) if db else 'NA', f1(sr), f1(sdb), big, r.get('status')])
md += ['## Table 2: per form', '', table(['arm', 'task', 'g', 'kind', 'source', 'scope_n', 'slot_tries', 'S', 'R', 'DB', 'S - R', 'S - DB', 'largest place', 'status'], body), '']
md += ['## Table 3: places (S - DB), measured forms', '']
if A:
    md += [place_table(A), '', 'Top 3: %s. T3 = %.2f [%.2f, %.2f] (%d forms, %d tasks); bar %.2f on the 2.5%% point. Median gap %.2f bits.' % (', '.join(A['top3']), A['T3'], A['T3_lo'], A['T3_hi'], A['n_forms'], A['n_tasks'], BAR, median_gap), '',
           'Verdict: **%s**' % ('no gap' if median_gap < NOGAP else 'a few named places' if A['few'] else 'spread'), '']
else:
    md += ['No measured form.', '']
md += ['## Table 4: S - R, the scope places, forms with no DB included', '']
if B:
    md += [place_table(B), '', 'Top 3: %s. T3 = %.2f [%.2f, %.2f] (%d forms, %d tasks).' % (', '.join(B['top3']), B['T3'], B['T3_lo'], B['T3_hi'], B['n_forms'], B['n_tasks']), '']
else:
    md += ['No form with S and R.', '']
md += ['## Table 5: forms whose read relation is not in the scope', '',
       table(['arm', 'task', 'g', 'gold reads', 'relations of that gold form that the scope holds'],
             [[r['arm'], r['task'], r['g'], ', '.join(r.get('absent') or []), ', '.join(n for n, h in (r.get('gold_rels') or []) if h) or 'none'] for r in absent]), '']
if CMP:
    def ci(x):
        return 'NA' if not x else '[%.2f, %.2f]' % tuple(x)
    md += ['## C against covered', '',
           'C: the C forms of the bundle arms (class C of scope-loss/forms.tsv), from forms.*of*.jsonl. Covered: this read. Both walk the gold clause under the recorded scope of one opening: C the opening with the most slot tries that held the reads with the form\'s kind and did not draw the form; covered the opening that opened the covering visit. Shares are positive mass shares as in table 3; the interval is the task bootstrap (%d resamples, a task brings all its forms).' % BOOT, '',
           table(['set', 'entered', 'S and R valid', 'measured (with DB)', 'tasks', 'median S - DB', 'median S - R', 'median scope_n [Q1, Q3]'],
                 [[lab, Z['entered'], Z['mapped_sr'], Z['measured'], Z['tasks'], f1(Z['median_S_DB']), f1(Z['median_S_R']), '%s [%s, %s]' % (f1(Z['median_scope_n']), f1(Z['scope_n_iqr'][0]), f1(Z['scope_n_iqr'][1]))] for lab, Z in (('C', CMP['C']), ('covered', CMP['covered']))]), '']
    for b in CMP['bases']:
        S_ = b['sets']
        md += ['### Places on ' + b['name'], '',
               table(['place', 'C: sum', 'C: median', 'C: share', 'covered: sum', 'covered: median', 'covered: share'],
                     [[p] + [x for lab in ('C', 'covered') for x in (('%.1f' % S_[lab]['sum'][p], '%.2f' % S_[lab]['median'][p], '%.2f' % S_[lab]['share'][p]) if S_[lab]['n'] else ('NA', 'NA', 'NA'))] for p in b['place_names']]), '',
               table(['relation pick (read + builtin)', 'C', 'covered'],
                     [['forms', S_['C']['n'], S_['covered']['n']],
                      ['share of the positive mass [2.5%, 97.5%]'] + ['%.2f %s' % (S_[l]['relp_share'], ci(S_[l]['relp_share_ci'])) for l in ('C', 'covered')],
                      ['read-atom part of that share [2.5%, 97.5%]'] + [ci(S_[l]['relp_read_share_ci']) for l in ('C', 'covered')],
                      ['median bits a form [2.5%, 97.5%]'] + ['%.2f %s' % (S_[l]['relp_median'], ci(S_[l]['relp_median_ci'])) for l in ('C', 'covered')],
                      ['mean bits a form'] + ['%.2f' % S_[l]['relp_mean'] for l in ('C', 'covered')],
                      ['rank correlation of scope_n with the relation-pick gap'] + [f1(S_[l]['rho_scope_n_relp']) for l in ('C', 'covered')]]), '']
        if 'diff_share_ci' in b:
            md += ['C minus covered: relation-pick share %s, median relation-pick gap a form %s bits (tasks resampled within each set).' % (ci(b['diff_share_ci']), ci(b['diff_median_ci'])), '']
    md += ['The per-form scope_n, slot_tries and relation-pick gaps of both sets are in compare-forms.tsv.', '']
md += ['## Checks', '']
for k, v in C.items():
    md += ['- %s: `%s`' % (k, json.dumps(v, default=str)[:1500])]
other = [r for r in rows if r.get('status') not in ('mapped', 'read relation not in the scope')]
if other:
    md += ['', '## Forms not measured, other reasons', '', table(['arm', 'task', 'g', 'status', 'how'], [[r['arm'], r['task'], r['g'], r.get('status'), '; '.join(r.get('how') or [r.get('error', '')])[:200]] for r in other])]
open(os.path.join(ARGS.outdir, 'results.md'), 'w').write('\n'.join(md) + '\n')
print(msg)
print('forms %d  measured %d  with S and R %d  absent %d  statuses %s' % (N, M, len(srs), X, dict(collections.Counter(r.get('status') for r in rows))))
if A:
    print(place_table(A))
    print('T3 %.2f [%.2f, %.2f] top3: %s' % (A['T3'], A['T3_lo'], A['T3_hi'], ', '.join(A['top3'])))
if CMP:
    for b in CMP['bases']:
        for lab in ('C', 'covered'):
            z = b['sets'][lab]
            print('%s | %s: forms %d, relation pick share %.2f %s, median relation-pick gap %.2f bits %s, rho(scope_n) %s' % (
                b['name'], lab, z['n'], z['relp_share'], ci(z['relp_share_ci']), z['relp_median'], ci(z['relp_median_ci']), f1(z['rho_scope_n_relp'])))
print('checks: table fails %d, invalid walks %d, kind %d, sums beyond 0.05 %d, other parts %d (%.3f bits), phases without atom row %d, estimates %d' % (
    len(C['1 table check']['fails']), len(C['2 walks']['invalid']), len(C['3 kind']['not_gold_kind']), len(bad4), len(odd_all), sum(odd_all.values()), miss[0], len(C['9 exact or estimate']['estimates'])))
