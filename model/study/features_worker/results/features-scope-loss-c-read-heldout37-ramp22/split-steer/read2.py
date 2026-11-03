"""Reads walks-<set>.*of2.jsonl and writes forms.tsv and summary.json in this folder, and prints the tables.
Per form: S_today (the switch off), S_new (on), delta = S_today - S_new, and the delta at read-atom and builtin relation picks (read.py's split of
parts into places). Medians with a 95% task bootstrap (2000 resamples, numpy default_rng(0); a task brings all its forms of both seeds)."""
import collections
import glob
import json
import re
import statistics

import numpy as np

HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22/split-steer'
ORDER_PART = 'orders: entropy credit'
ATOM = re.compile(r'^(\S+) atom: (.+)$')


def reads(text):
    t = text.strip()
    while t.startswith('(NOT '):
        t = t[5:].strip()
    m = re.match(r'\(\s*(\S+)', t)
    return bool(m and re.match(r'&[rf]\d+', m.group(1)))


def relp(w):
    """(read, builtin) bits of the relation pick of a walk record, as read.py splits them."""
    out = dict(read=0.0, builtin=0.0)
    atoms, detail = w.get('atoms') or [], w.get('detail') or []
    for name, v in (w.get('parts') or {}).items():
        m = ATOM.match(name)
        if not m or m.group(2) != 'relation':
            continue
        ctx, phase = m.groups()
        rows = [(a, d) for a, d in zip(atoms, detail) if phase in d['cur']]
        use = [r for r in rows if r[0][0] == ctx] or rows
        tot = sum(d['cur'][phase] for _, d in use)
        rd = 0.0 if not use or abs(tot) < 1e-9 else v * sum(d['cur'][phase] for a, d in use if reads(a[1])) / tot
        out['read'] += rd
        out['builtin'] += v - rd
    return out


def valid(w):
    return bool(w) and w.get('total') is not None and not w.get('bad') and not w.get('dead') and not w.get('left')


def boot_median(rows, key, n=2000):
    tasks = sorted({r['task'] for r in rows})
    by = collections.defaultdict(list)
    for r in rows:
        by[r['task']].append(r[key])
    rng = np.random.default_rng(0)
    meds = []
    for _ in range(n):
        pick = rng.integers(0, len(tasks), len(tasks))
        xs = [x for i in pick for x in by[tasks[i]]]
        meds.append(statistics.median(xs))
    return statistics.median([r[key] for r in rows]), float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def main():
    allrows, summary, checks = [], {}, {}
    for st in ('C', 'covered'):
        recs = [json.loads(l) for f in sorted(glob.glob('%s/walks-%s.*of2.jsonl' % (HERE, st))) for l in open(f)]
        ok = [r for r in recs if r['status'] == 'ok']
        off_eq = [r for r in ok if r['S_off']['total'] == r['S_rec']]
        checks[st] = dict(forms=len(recs), ok=len(ok), errors=[(r['task'], r['g'], r.get('error')) for r in recs if r['status'] != 'ok'],
                          off_equals_recorded=len(off_eq), off_differs=[(r['arm'], r['task'], r['g'], r['S_rec'], r['S_off']['total']) for r in ok if r not in off_eq],
                          on_invalid=[(r['arm'], r['task'], r['g'], r['S_on'].get('bad'), r['S_on'].get('dead')) for r in ok if not valid(r['S_on'])],
                          on_estimates=sum(1 for r in ok if not (r['S_on'].get('orders') or {}).get('exact', True)))
        rows = []
        for r in ok:
            if not valid(r['S_on']) or not valid(r['S_off']):
                continue
            a, b = relp(r['S_off']), relp(r['S_on'])
            x = dict(set=st, arm=r['arm'], task=r['task'], g=r['g'], S_today=r['S_off']['total'], S_new=r['S_on']['total'],
                     delta=round(r['S_off']['total'] - r['S_on']['total'], 3), d_read=round(a['read'] - b['read'], 3), d_builtin=round(a['builtin'] - b['builtin'], 3),
                     DB=r['DB'] if r['DB_status'] in ('exact', 'one', 'bound') else None, regrouped_picks=r.get('switch_regrouped'))
            x['chance_factor'] = round(2 ** x['delta'], 3)
            x['gap_today'] = None if x['DB'] is None else round(x['S_today'] - x['DB'], 3)
            x['gap_new'] = None if x['DB'] is None else round(x['S_new'] - x['DB'], 3)
            x['gap_kept'] = None if x['DB'] is None or abs(x['gap_today']) < 1e-9 else round(x['gap_new'] / x['gap_today'], 3)
            rows.append(x)
        allrows += rows
        s = dict(n=len(rows), tasks=len({r['task'] for r in rows}))
        for key in ('delta', 'd_read', 'd_builtin'):
            m, lo, hi = boot_median(rows, key)
            s[key] = dict(median=round(m, 3), lo=round(lo, 3), hi=round(hi, 3), sum=round(sum(r[key] for r in rows), 2), mean=round(statistics.mean(r[key] for r in rows), 3))
        s['chance_factor_median'] = round(statistics.median(r['chance_factor'] for r in rows), 3)
        s['forms_better_by_1bit'] = sum(r['delta'] >= 1 for r in rows)
        s['forms_worse_by_1bit'] = sum(r['delta'] <= -1 for r in rows)
        db = [r for r in rows if r['DB'] is not None]
        mt, mn = statistics.median(r['gap_today'] for r in db), statistics.median(r['gap_new'] for r in db)
        s['db'] = dict(n=len(db), median_gap_today=round(mt, 3), median_gap_new=round(mn, 3), share_kept=round(mn / mt, 3) if mt else None,
                       per_form_share_kept_median=round(statistics.median(r['gap_kept'] for r in db if r['gap_kept'] is not None), 3))
        summary[st] = s
    cols = ['set', 'arm', 'task', 'g', 'S_today', 'S_new', 'delta', 'd_read', 'd_builtin', 'chance_factor', 'DB', 'gap_today', 'gap_new', 'gap_kept', 'regrouped_picks']
    with open(HERE + '/forms.tsv', 'w') as fh:
        fh.write('\t'.join(cols) + '\n')
        for r in allrows:
            fh.write('\t'.join('' if r[c] is None else str(r[c]) for c in cols) + '\n')
    json.dump(dict(summary=summary, checks=checks), open(HERE + '/summary.json', 'w'), indent=1)
    print(json.dumps(dict(summary=summary, checks=checks), indent=1))
    for r in sorted(allrows, key=lambda r: (r['set'], -r['delta'])):
        print(r['set'], r['arm'][-2:], r['task'], 'g%d' % r['g'], 'today %.2f new %.2f delta %+.2f read %+.2f builtin %+.2f gap %s -> %s' % (r['S_today'], r['S_new'], r['delta'], r['d_read'], r['d_builtin'], r['gap_today'], r['gap_new']))


main()
