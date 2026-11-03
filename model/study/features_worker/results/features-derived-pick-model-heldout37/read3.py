"""Reads X/walks-<set>.*of*.jsonl (job3.py), X/fit/cv.json (fit.py) and X/checks.json (checks.py, if there), and writes results.md, summary.json and forms.tsv in X.

    python3 read3.py [--dir D] [--cv FILE] [--extra FILE]     (the venv python of REC/env.sh has numpy; no engine needed)

--dir D     the folder of the walks files walks-<set>.<I>of<N>.jsonl, where results.md, summary.json and forms.tsv are written (default X; the calibrated reread uses X/m2cal)
--cv FILE   the cross-fit json of the fit that the walks used (default X/fit/cv.json; the calibrated model: X/fit-cal/cv.json)
--extra FILE  a text file that results.md carries at its end in a code block (for example X/cal/crossfit-tables.txt)
Arms read: M1, M2 and, where the walks have it, M2s (M2 that acts only where today's steer acts; at rel_off picks P's weights stay). The M2 against M2s difference is the saving at rel_off picks (and what it changes later in the walk).

Per form and arm (M1, M2): delta = S_off - S_arm, and the delta at read-atom relation picks, at builtin relation picks and at op picks (REC/split-steer/read2.py:relp, with the op pick of
REC/design.md: phase `relation (op)` and `br:else-NOT pick`). Per set and arm: mean and median of the delta with a 95% task bootstrap (2,000 resamples, numpy default_rng(0); a task brings all
its forms of both seeds), the saved bits at rel_off picks, the share of the S - DB gap, and the mean against the .78 line.
"""
import collections
import glob
import json
import os
import re
import argparse
import statistics

import numpy as np

X = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37'
REC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22'
LINE = 0.78
BOOT = 2000
ATOM = re.compile(r'^(\S+) atom: (.+)$')
ARMS_ALL = ('M1', 'M2', 'M2s')
ARMS = ARMS_ALL
ap = argparse.ArgumentParser()
ap.add_argument('--dir', default=X)
ap.add_argument('--cv', default=X + '/fit/cv.json')
ap.add_argument('--extra', default=None)
ARGS = ap.parse_args()
DIR = ARGS.dir


def reads(text):
    t = text.strip()
    while t.startswith('(NOT '):
        t = t[5:].strip()
    m = re.match(r'\(\s*(\S+)', t)
    return bool(m and re.match(r'&[rf]\d+', m.group(1)))


def relp3(w):
    """bits of the relation pick of a walk record: at read atoms, at builtin atoms, and op picks."""
    out = dict(read=0.0, builtin=0.0, op=0.0)
    atoms, detail = w.get('atoms') or [], w.get('detail') or []
    for name, v in (w.get('parts') or {}).items():
        if name.endswith('br:else-NOT pick'):
            out['op'] += v
            continue
        m = ATOM.match(name)
        if not m:
            continue
        ctx, phase = m.groups()
        if phase == 'relation (op)':
            out['op'] += v
        elif phase == 'relation':
            rows = [(a, d) for a, d in zip(atoms, detail) if phase in d['cur']]
            use = [r for r in rows if r[0][0] == ctx] or rows
            tot = sum(d['cur'][phase] for _, d in use)
            rd = 0.0 if not use or abs(tot) < 1e-9 else v * sum(d['cur'][phase] for a, d in use if reads(a[1])) / tot
            out['read'] += rd
            out['builtin'] += v - rd
    return out


def valid(w):
    return bool(w) and w.get('total') is not None and not w.get('bad') and not w.get('dead') and not w.get('left') and w.get('valid', True)


def boot(rows, stat, n=BOOT):
    """stat(list of rows) with a 95% task bootstrap: (value, lo, hi)."""
    by = collections.defaultdict(list)
    for r in rows:
        by[r['task']].append(r)
    tasks = sorted(by)
    rng = np.random.default_rng(0)
    vals = []
    for _ in range(n):
        pick = rng.integers(0, len(tasks), len(tasks))
        vals.append(stat([r for i in pick for r in by[tasks[i]]]))
    return stat(rows), float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def fmt(t, d=2):
    return '%.*f [%.*f, %.*f]' % (d, t[0], d, t[1], d, t[2])


def load(st):
    return [json.loads(l) for f in sorted(glob.glob('%s/walks-%s.*of*.jsonl' % (DIR, st))) for l in open(f)]


def main():
    global ARMS
    summary, checks, allrows, md = {}, {}, [], []
    ARMS = tuple(a for a in ARMS_ALL if any(a in r.get('S', {}) for st in ('C', 'covered') for r in load(st)))
    os.makedirs(DIR, exist_ok=True)
    for st in ('C', 'covered'):
        recs = load(st)
        ok = [r for r in recs if r['status'] == 'ok']
        # 1. off equals recorded
        off_bad = [(r['arm'], r['task'], r['g'], r['S_rec'], r['S']['off']['total']) for r in ok if abs(r['S']['off']['total'] - r['S_rec']) > 0.005]
        # 2. regroup
        old = {}
        for f in glob.glob('%s/split-steer/walks-%s.*of2.jsonl' % (REC, st)):
            for l in open(f):
                y = json.loads(l)
                if y['status'] == 'ok':
                    old[(y['arm'], y['task'], y['g'])] = y['S_on']['total']
        reg = [(r['arm'], r['task'], r['g'], r['S']['G']['total'], old.get((r['arm'], r['task'], r['g']))) for r in ok if 'G' in r['S']]
        reg_bad = [x for x in reg if x[4] is None or abs(x[3] - x[4]) > 0.01]
        # 3. valid, estimates
        inval = {a: [(r['arm'], r['task'], r['g']) for r in ok if a in r['S'] and not valid(r['S'][a])] for a in ('off',) + ARMS}
        est = {a: sum(1 for r in ok if a in r['S'] and valid(r['S'][a]) and not (r['S'][a].get('orders') or {}).get('exact', True)) for a in ('off',) + ARMS}
        # 4. order free
        oc = [(r['arm'], r['task'], r['g'], r['order_check']) for r in ok if r.get('order_check')]
        reused = sum(1 for r in ok if r.get('reused_off'))
        oc_bad = [x for x in oc if abs(x[3]['M1'] - x[3]['M1_last_order']) > 0.01]
        pickstats = {a: dict(non_declared=sum(r['S'][a]['pick_stats']['non_declared'] for r in ok if a in r['S']), alt_extra=sum(r['S'][a]['pick_stats']['alt_extra'] for r in ok if a in r['S']),
                             miss=sum(r['S'][a]['pick_stats']['miss'] for r in ok if a in r['S'])) for a in ARMS}
        checks[st] = dict(reused_off=reused, forms=len(recs), ok=len(ok), errors=[(r['arm'], r['task'], r['g'], r.get('error')) for r in recs if r['status'] != 'ok'], off_differs=off_bad,
                          regroup_forms=len(reg), regroup_differs=reg_bad, invalid=inval, estimates=est, order_checks=len(oc), order_check_differs=oc_bad, pick_stats=pickstats)
        summary[st] = {}
        for arm in ARMS:
            rows = []
            for r in ok:
                if arm not in r['S'] or not valid(r['S']['off']) or not valid(r['S'][arm]):
                    continue
                a, b = relp3(r['S']['off']), relp3(r['S'][arm])
                db = r['DB'] if r['DB_status'] in ('exact', 'one', 'bound') else None
                so, sa = r['S']['off']['total'], r['S'][arm]['total']
                ro_o, ro_a = r['S']['off']['ro'], r['S'][arm]['ro']
                x = dict(set=st, arm_name=arm, arm=r['arm'], task=r['task'], g=r['g'], S_off=so, S_arm=sa, delta=so - sa, d_read=a['read'] - b['read'], d_builtin=a['builtin'] - b['builtin'],
                         d_op=a['op'] - b['op'], d_ro=ro_o['bits'] - ro_a['bits'], ro_picks=ro_o['picks'], DB=db)
                rows.append(x)
            allrows += rows
            if not rows:
                continue
            s = dict(forms=len(rows), tasks=len({r['task'] for r in rows}))
            for key in ('delta', 'd_read', 'd_builtin', 'd_op'):
                s[key] = dict(mean=boot(rows, lambda rs, k=key: float(np.mean([r[k] for r in rs]))), median=boot(rows, lambda rs, k=key: float(np.median([r[k] for r in rs]))))
            ro_rows = [r for r in rows if r['ro_picks'] > 0]
            s['rel_off'] = dict(sum=sum(r['d_ro'] for r in rows), forms=len(ro_rows), per_form_mean_over_those=float(np.mean([r['d_ro'] for r in ro_rows])) if ro_rows else None)
            dbr = [r for r in rows if r['DB'] is not None]
            if dbr:
                s['gap'] = dict(forms=len(dbr), median_S_off_minus_DB=statistics.median(r['S_off'] - r['DB'] for r in dbr), median_S_arm_minus_DB=statistics.median(r['S_arm'] - r['DB'] for r in dbr),
                                share_closed=boot(dbr, lambda rs: sum(r['delta'] for r in rs) / sum(r['S_off'] - r['DB'] for r in rs)))
            s['vs_line'] = boot(rows, lambda rs: float(np.mean([r['delta'] for r in rs])) - LINE)
            s['verdict'] = 'above' if s['vs_line'][1] > 0 else 'below' if s['vs_line'][2] < 0 else 'within'
            summary[st][arm] = s
        if 'M2' in summary[st] and 'M2s' in summary[st]:  # the rel_off picks' part of M2: per form, the saving of M2 minus that of M2s (paired)
            a = {(r['arm'], r['task'], r['g']): r for r in allrows if r['set'] == st and r['arm_name'] == 'M2'}
            b = {(r['arm'], r['task'], r['g']): r for r in allrows if r['set'] == st and r['arm_name'] == 'M2s'}
            both = [dict(task=a[k]['task'], diff=a[k]['delta'] - b[k]['delta'], diff_read=a[k]['d_read'] - b[k]['d_read'], diff_builtin=a[k]['d_builtin'] - b[k]['d_builtin'], diff_op=a[k]['d_op'] - b[k]['d_op'])
                    for k in a if k in b]
            if both:
                summary[st]['M2_minus_M2s'] = dict(forms=len(both), **{kk: boot(both, lambda rs, kk=kk: float(np.mean([r[kk] for r in rs]))) for kk in ('diff', 'diff_read', 'diff_builtin', 'diff_op')})
    cols = ['set', 'arm_name', 'arm', 'task', 'g', 'S_off', 'S_arm', 'delta', 'd_read', 'd_builtin', 'd_op', 'd_ro', 'ro_picks', 'DB']
    with open(DIR + '/forms.tsv', 'w') as fh:
        fh.write('\t'.join(cols) + '\n')
        for r in allrows:
            fh.write('\t'.join('' if r[c] is None else (('%.3f' % r[c]) if isinstance(r[c], float) else str(r[c])) for c in cols) + '\n')
    cv = json.load(open(ARGS.cv)) if os.path.exists(ARGS.cv) else None
    chk = json.load(open(X + '/checks.json')) if os.path.exists(X + '/checks.json') else None
    json.dump(dict(summary=summary, checks=checks, extra_checks=chk, crossfit=cv), open(DIR + '/summary.json', 'w'), indent=1, default=str)

    md.append('# Derived pick model: results\n')
    parts = []
    for arm in ARMS:
        seg = []
        for st in ('C', 'covered'):
            s = summary.get(st, {}).get(arm)
            if s:
                extra = ' (read picks %.2f, builtin picks %.2f)' % (s['d_read']['mean'][0], s['d_builtin']['mean'][0]) if st == 'C' else ''
                seg.append('%.2f on %s %s%s' % (s['delta']['mean'][0], st, '[%.2f, %.2f]' % s['delta']['mean'][1:], extra))
        parts.append('%s saves %s a form' % (arm, ' and '.join(seg)))
    gaps = []
    for arm in ARMS:
        for st in ('C', 'covered'):
            s = summary.get(st, {}).get(arm)
            if s and 'gap' in s:
                g = s['gap']
                gaps.append('%s %s closes %.2f %s of the S - DB gap (median gap %.2f to %.2f)' % (arm, st, g['share_closed'][0], '[%.2f, %.2f]' % g['share_closed'][1:], g['median_S_off_minus_DB'], g['median_S_arm_minus_DB']))
    lines = ['%s %s: %s' % (arm, st, summary[st][arm]['verdict']) for st in ('C', 'covered') for arm in ARMS if arm in summary.get(st, {})]
    md.append('; '.join(parts) + '; ' + '; '.join(gaps) + '; against the %.2f line: ' % LINE + ', '.join(lines) + '.\n')
    md.append('## Saved bits a form (S_off - S_arm), mean and median with a 95% task bootstrap\n')
    md.append('| set | arm | forms (tasks) | total mean | total median | read picks mean | builtin picks mean | op picks mean | rel_off picks: sum (forms) | mean - %.2f |' % LINE)
    md.append('|---|---|---|---|---|---|---|---|---|---|')
    for st in ('C', 'covered'):
        for arm in ARMS:
            s = summary.get(st, {}).get(arm)
            if s:
                md.append('| %s | %s | %d (%d) | %s | %s | %s | %s | %s | %.1f (%d) | %s |' % (st, arm, s['forms'], s['tasks'], fmt(s['delta']['mean']), fmt(s['delta']['median']), fmt(s['d_read']['mean']),
                                                                                        fmt(s['d_builtin']['mean']), fmt(s['d_op']['mean']), s['rel_off']['sum'], s['rel_off']['forms'], fmt(s['vs_line'])))
    hdr = False
    for st in ('C', 'covered'):
        d = summary.get(st, {}).get('M2_minus_M2s')
        if d:
            if not hdr:
                hdr = True
                md.append('\n## M2 against M2s: the saving that comes from acting at rel_off picks too (mean over forms of the saving of M2 minus that of M2s, 95% task bootstrap)\n')
                md.append('| set | forms | total | read picks | builtin picks | op picks |')
                md.append('|---|---|---|---|---|---|')
            md.append('| %s | %d | %s | %s | %s | %s |' % (st, d['forms'], fmt(d['diff']), fmt(d['diff_read']), fmt(d['diff_builtin']), fmt(d['diff_op'])))
    md.append('\n## Against the S - DB gap (forms with DB)\n')
    md.append('| set | arm | forms | median S_off - DB | median S_arm - DB | sum delta / sum gap |')
    md.append('|---|---|---|---|---|---|')
    for st in ('C', 'covered'):
        for arm in ARMS:
            s = summary.get(st, {}).get(arm)
            if s and 'gap' in s:
                g = s['gap']
                md.append('| %s | %s | %d | %.2f | %.2f | %s |' % (st, arm, g['forms'], g['median_S_off_minus_DB'], g['median_S_arm_minus_DB'], fmt(g['share_closed'])))
    md.append('\n## Checks\n')
    for st in ('C', 'covered'):
        c = checks[st]
        md.append('- %s: forms %d, ok %d, errors %d. (1) S_off differs from the recorded S on %d forms. (2) Regroup arm G on %d forms, differs from split-steer S_on on %d. (3) invalid walks: %s; estimates (orders.exact false): %s. (4) order check on %d forms, differs on %d. Non-declared relation options at picks %s, alt-only options %s.' % (
            st, c['forms'], c['ok'], len(c['errors']), len(c['off_differs']), c['regroup_forms'], len(c['regroup_differs']), {k: len(v) for k, v in c['invalid'].items()}, c['estimates'],
            c['order_checks'], len(c['order_check_differs']), {a: v['non_declared'] for a, v in c['pick_stats'].items()}, {a: v['alt_extra'] for a, v in c['pick_stats'].items()}))
        for key in ('errors', 'off_differs', 'regroup_differs', 'order_check_differs'):
            if c[key]:
                md.append('    - %s: %s' % (key, c[key][:6]))
    if chk:
        md.append('- facts, drawn atoms and row parity (checks.py): ' + json.dumps(chk, default=str)[:1500])
    if cv:
        md.append('\n## Cross-fit on the training rows (pick level, in bits; weighted means)\n')
        rw = cv['read_within']
        md.append('Read-pick rows, within the derived options (positives\' share): even split %.3f, today %.3f, rank model (%s) %.3f; a positive has the largest score: today %.3f, model %.3f. Ablation (boosted ranker): %s. Rows %d.\n' % (
            rw['even'], rw['today'], cv['rank_kind'], rw['logit'], rw['top1_today'], rw['top1_logit'], rw.get('hgb'), rw['rows']))
        md.append('| rows | count | today | M1 | M2 |')
        md.append('|---|---|---|---|---|')
        for k, v in cv['whole_pick'].items():
            md.append('| %s | %d | %.3f | %.3f | %.3f |' % (k, v['rows'], v['off'], v['M1'], v['M2']))
        md.append('\nLambda grid: ' + json.dumps(cv['lam']) + '. Gate C grid: ' + json.dumps(cv['gate']) + '.\n')
        md.append('Training counts: ' + json.dumps(cv['counts'], default=str) + '\n')
        md.append('Largest coefficients: ' + json.dumps(cv.get('top_beta')) + '\n')
    if ARGS.extra and os.path.exists(ARGS.extra):
        md.append('\n## Training cross-fit by pick type and by steered / rel_off (X/cal)\n\n```\n' + open(ARGS.extra).read() + '```\n')
    open(DIR + '/results.md', 'w').write('\n'.join(md) + '\n')
    print('\n'.join(md))


main()
