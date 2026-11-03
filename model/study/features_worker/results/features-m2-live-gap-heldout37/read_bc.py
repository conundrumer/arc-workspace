"""Parts (b) and (c): chance of the C list forms under the live held-with-kind scopes, expected covers from tries x chance, and where the tries went.

    python -I read_bc.py

Reads held/*.json (held_live.py) and walks*.jsonl (walk_live.py), the worker logs of the run (last counts line of each process), and c-split.json. Writes bc_summary.json.
Chance of an opening: 2^-S of the walk where the target maps and the walk is valid; 0 where gold's read relation has no table in the scope (status not mapped).
lam = sum over a form's held-with-kind openings of slot tries x chance (all openings, or for a form with more than K: its tries total x the mean chance over the PPS draws).
Expected covers of a form: 1 - exp(-lam).
"""
import collections, glob, json, math, os, statistics, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SWR = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker'
sys.path[:0] = [SWR + '/refit-tools']
import search_node_score_read as RD
import numpy as np

RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-pool-m2-600s'
KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-m2-48211b300'
OFF = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-derived-pick-model-heldout37/m2cal/forms.tsv'
JOBS = ['m2c_s0', 'm2s_s0', 'm2c_s1', 'm2s_s1']
OWN = {'m2c_s0': 'off', 'm2c_s1': 'off', 'm2s_s0': 'M2', 'm2s_s1': 'M2'}
tasks = json.load(open(KIT + '/refit-tasks.json'))['heldout37']


def load():
    held = {j: {t: json.load(open('%s/held/%s__%s.json' % (HERE, j, t))) for t in tasks} for j in JOBS}
    walks = {}
    for p in glob.glob(HERE + '/walks*.jsonl'):
        for l in open(p):
            try:
                y = json.loads(l)
            except ValueError:
                continue
            walks[(y['job'], y['task'], y['g'], y['i'])] = y
    return held, walks


def chance(y, arm):
    if y['status'] != 'mapped':
        return 0.0, 'unmapped'
    w = (y.get('S') or {}).get(arm) or {}
    if not w.get('valid') or w.get('total') is None:
        return None, 'invalid'
    return 2.0 ** -w['total'], 'ok'


def forms_of(held, walks):
    """{job: {(task, g): dict}} for C forms with held-with-kind tries above 0."""
    out = {}
    for j in JOBS:
        out[j] = {}
        for t in tasks:
            for f in held[j][t]['forms']:
                ops = [x for x in f['hk'] if x['tries'] > 0]
                if not ops:
                    continue
                tot = sum(x['tries'] for x in ops)
                rows = [(x, walks.get((j, t, f['g'], x['i']))) for x in ops]
                rows = [(x, y) for x, y in rows if y is not None]
                rec = dict(kind=f['kind'], n_hk=len(ops), tries=tot, walked=len(rows), covered=f['cover_s'] is not None and f['cover_s'] <= 600, lam={}, bits={}, status=collections.Counter())
                if not rows:
                    rec['missing'] = True
                    out[j][(t, f['g'])] = rec
                    continue
                pps = rows[0][1]['mode'] == 'pps'
                for arm in ('off', 'M2'):
                    acc, wsum, n_ok = 0.0, 0.0, 0
                    for x, y in rows:
                        p, st = chance(y, arm)
                        if arm == 'off':
                            rec['status'][st] += y['draws'] if pps else 1
                        if p is None:
                            continue
                        if pps:
                            acc += y['draws'] * p
                            wsum += y['draws']
                        else:
                            acc += x['tries'] * p
                            wsum += x['tries']
                    if wsum == 0:
                        rec['lam'][arm] = None
                    else:
                        rec['lam'][arm] = (acc / wsum) * tot  # walked tries or draws stand for all the form's held-with-kind tries
                # bits saved, tries-weighted (draw-weighted for pps) over openings where both walks are valid and mapped
                num = den = 0.0
                for x, y in rows:
                    if y['status'] != 'mapped':
                        continue
                    a, b = y['S'].get('off') or {}, y['S'].get('M2') or {}
                    if not (a.get('valid') and b.get('valid')):
                        continue
                    wt = y['draws'] if pps else x['tries']
                    num += wt * (a['total'] - b['total'])
                    den += wt
                rec['bits']['delta'] = num / den if den else None
                rec['mapped_share'] = 1 - rec['status']['unmapped'] / max(1, sum(rec['status'].values()))
                out[j][(t, f['g'])] = rec
    return out


def ecov(lam):
    return 0.0 if lam is None else 1.0 - math.exp(-lam)


def logs_counts(j):
    tot = collections.Counter()
    for t in tasks:
        p = '%s/out/%s/%s/work/%s.log' % (RUN, j, t, t)
        if os.path.exists(p):
            tot.update(RD.last_counts(open(p, errors='replace').read()))
    return tot


def main():
    held, walks = load()
    F = forms_of(held, walks)
    res = dict(b={}, c={})
    # ---- (b)
    print('== (b) C forms held with kind, under live scopes (chance per try from the walk; lam = sum tries x chance)')
    print('%-8s %5s %6s %7s %10s %9s %9s %8s %8s %8s %8s %6s' % ('job', 'forms', 'walked', 'mapped', 'hk tries', 'lam off', 'lam M2', 'E off', 'E M2', 'E own', 'seen', 'bits'))
    for j in JOBS:
        d = F[j]
        lo = sum(v['lam'].get('off') or 0 for v in d.values())
        lm = sum(v['lam'].get('M2') or 0 for v in d.values())
        eo = sum(ecov(v['lam'].get('off')) for v in d.values())
        em = sum(ecov(v['lam'].get('M2')) for v in d.values())
        deltas = [v['bits']['delta'] for v in d.values() if v['bits'].get('delta') is not None]
        st = collections.Counter()
        for v in d.values():
            st.update(v['status'])
        seen = json.load(open(RUN + '/c-split.json'))['jobs'][j]['c']
        r = dict(forms=len(d), forms_walked=sum(1 for v in d.values() if not v.get('missing')), status=dict(st), hk_tries=sum(v['tries'] for v in d.values()), lam_off=lo, lam_m2=lm, E_off=eo, E_m2=em,
                 E_own=eo if OWN[j] == 'off' else em, seen=seen, bits_mean=statistics.mean(deltas) if deltas else None, bits_median=statistics.median(deltas) if deltas else None, n_bits=len(deltas),
                 log2_lam_ratio=math.log2(lm / lo) if lo > 0 and lm > 0 else None,
                 forms_detail={'%s:%d' % k: dict(kind=v['kind'], tries=v['tries'], n_hk=v['n_hk'], walked=v['walked'], covered=v['covered'], lam_off=v['lam'].get('off'), lam_m2=v['lam'].get('M2'),
                                                   delta=v['bits'].get('delta'), mapped_share=v.get('mapped_share')) for k, v in d.items()})
        res['b'][j] = r
        print('%-8s %5d %6d %7s %10d %9.4f %9.4f %8.3f %8.3f %8.3f %8d %+6.2f' % (j, r['forms'], r['forms_walked'], '%d/%d' % (st['ok'], sum(st.values())), r['hk_tries'], lo, lm, eo, em, r['E_own'], seen, r['bits_mean'] or 0))
    # forms with the largest lam
    print('largest lam forms (job, form, kind, tries, lam off, lam M2, delta bits, covered):')
    allf = [(j, k, v) for j in JOBS for k, v in F[j].items() if not v.get('missing')]
    for j, k, v in sorted(allf, key=lambda x: -max(x[2]['lam'].get('off') or 0, x[2]['lam'].get('M2') or 0))[:10]:
        print('  %s %s:%d %s tries %d lam off %.4f M2 %.4f delta %s covered %s' % (j, k[0], k[1], v['kind'], v['tries'], v['lam'].get('off') or 0, v['lam'].get('M2') or 0,
              None if v['bits'].get('delta') is None else round(v['bits']['delta'], 2), v['covered']))
    # covered forms and their lam
    print('covered C forms (job, form, lam own):')
    for j in JOBS:
        cov = []
        for t in tasks:
            for f in held[j][t]['forms']:
                if f['cover_s'] is not None and f['cover_s'] <= 600:
                    v = F[j].get((t, f['g']))
                    cov.append('%s:%d hk %d lam %s' % (t, f['g'], f['hk_n'], None if v is None else '%.4f' % (v['lam'].get(OWN[j]) or 0)))
        print('  %s: %s' % (j, '; '.join(cov)))
        res['b'][j]['covered_forms'] = cov
    # bits pooled over jobs, per form, and against the offline read on the same forms
    off = collections.defaultdict(list)
    for l in open(OFF):
        p = l.rstrip('\n').split('\t')
        if p[0] == 'C' and p[1] == 'M2':
            off[(p[3], int(p[4]))].append(float(p[7]))
    pooled = collections.defaultdict(list)
    for j in JOBS:
        for k, v in F[j].items():
            if v['bits'].get('delta') is not None:
                pooled[k].append(v['bits']['delta'])
    both = [(statistics.mean(pooled[k]), statistics.mean(off[k])) for k in pooled if k in off]
    res['b']['bits_pooled'] = dict(forms=len(pooled), mean=statistics.mean([statistics.mean(x) for x in pooled.values()]), median=statistics.median([statistics.mean(x) for x in pooled.values()]),
                                   same_forms=len(both), live_on_same=statistics.mean([a for a, b in both]) if both else None, offline_on_same=statistics.mean([b for a, b in both]) if both else None)
    print('bits saved by M2 a form under live scopes, mean over forms (each form averaged over jobs): %.2f (median %.2f, %d forms); on the %d forms of the offline read: live %.2f, offline %.2f' % (
        res['b']['bits_pooled']['mean'], res['b']['bits_pooled']['median'], len(pooled), len(both), res['b']['bits_pooled']['live_on_same'] or 0, res['b']['bits_pooled']['offline_on_same'] or 0))
    # ---- (c)
    print('== (c) tries')
    a_sum = json.load(open(HERE + '/a_summary.json'))['summary']
    for s in ('0', '1'):
        c, m = 'm2c_s' + s, 'm2s_s' + s
        tc, tm = a_sum['tries_by_kind'][c], a_sum['tries_by_kind'][m]
        Tc, Tm = sum(tc.values()), sum(tm.values())
        kinds = sorted(set(tc) | set(tm))
        byk = {k: dict(control=tc.get(k, 0), arm=tm.get(k, 0), change=(tm.get(k, 0) - tc.get(k, 0))) for k in kinds}
        cc, cm = logs_counts(c), logs_counts(m)
        secs = {k: (round(cc.get(k, 0), 1), round(cm.get(k, 0), 1)) for k in sorted(set(cc) | set(cm)) if k.startswith('search:seconds')}
        vis = {k: (cc.get(k, 0), cm.get(k, 0)) for k in sorted(set(cc) | set(cm)) if k.startswith('search:visits') or k.startswith('kept:') or k in ('search:new scope', 'search:failed tries')}
        # expected C covers with the arm's own scopes and chance, at its own hk tries and at hk tries scaled by the job's try ratio (control / arm), per kind
        ratio_k = {k: (tc.get(k, 0) / tm[k]) if tm.get(k) else 1.0 for k in kinds}
        E_arm = sum(ecov(v['lam'].get('M2')) for v in F[m].values())
        E_arm_scaled = sum(ecov((v['lam'].get('M2') or 0) * (Tc / Tm)) for v in F[m].values())
        E_arm_scaled_k = sum(ecov((v['lam'].get('M2') or 0) * ratio_k.get(v['kind'], 1.0)) for v in F[m].values())
        E_ctrl = sum(ecov(v['lam'].get('off')) for v in F[c].values())
        E_ctrl_m2 = sum(ecov(v['lam'].get('M2')) for v in F[c].values())
        E_arm_off = sum(ecov(v['lam'].get('off')) for v in F[m].values())
        hk_c = sum(v['tries'] for v in F[c].values())
        hk_m = sum(v['tries'] for v in F[m].values())
        r = dict(tries=dict(control=Tc, arm=Tm, change=(Tm - Tc) / Tc), by_kind=byk, seconds=secs, counts=vis, hk_tries=dict(control=hk_c, arm=hk_m, change=(hk_m - hk_c) / hk_c if hk_c else None),
                 E=dict(control_own=E_ctrl, control_scopes_M2=E_ctrl_m2, arm_scopes_off=E_arm_off, arm_own=E_arm, arm_at_control_tries=E_arm_scaled, arm_at_control_tries_by_kind=E_arm_scaled_k,
                        tries_effect=E_arm - E_arm_scaled, tries_effect_by_kind=E_arm - E_arm_scaled_k))
        res['c']['seed' + s] = r
        print('seed %s: tries %d -> %d (%+.1f%%); by kind %s' % (s, Tc, Tm, 100 * r['tries']['change'], {k: '%d -> %d' % (v['control'], v['arm']) for k, v in byk.items()}))
        print('  search seconds (control, arm): %s' % secs)
        print('  counts (control, arm): %s' % vis)
        print('  C hk tries %d -> %d; E covers: control own %.3f, control scopes with M2 %.3f, arm scopes with off %.3f, arm own %.3f, arm at control tries %.3f (by kind %.3f): tries effect %+.3f (by kind %+.3f)' % (
            hk_c, hk_m, E_ctrl, E_ctrl_m2, E_arm_off, E_arm, E_arm_scaled, E_arm_scaled_k, r['E']['tries_effect'], r['E']['tries_effect_by_kind']))
    json.dump(res, open(HERE + '/bc_summary.json', 'w'), indent=1, default=str)


main()
