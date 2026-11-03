"""Part (a): the C list forms held with their kind in round 1's bundle jobs and in the live jobs, per job. Writes a_summary.json and prints a table.

    python -I read_a.py
"""
import collections, json, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SLC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/scope-loss/cache'
KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-m2-48211b300'
JOBS = ['m2c_s0', 'm2s_s0', 'm2c_s1', 'm2s_s1']
tasks = json.load(open(KIT + '/refit-tasks.json'))['heldout37']


def live(job):
    out = {}
    tries = collections.Counter()
    for t in tasks:
        r = json.load(open('%s/held/%s__%s.json' % (HERE, job, t)))
        tries.update(r['tries_all'])
        for f in r['forms']:
            out[(t, f['g'])] = dict(kind=f['kind'], hk_n=f['hk_n'], hk_tries=f['hk_tries'], held_n=f['held_n'], ready_n=f['ready_n'], covered=f['cover_s'] is not None and f['cover_s'] <= 600,
                                    scopes=len({tuple(x['fids']) for x in f['hk']}))
    return out, tries


def r1(arm, cl):
    out = {}
    for t in tasks:
        p = '%s/%s__%s.json' % (SLC, arm, t)
        if not os.path.exists(p):
            continue
        r = json.load(open(p))
        ops = r['ops']
        for g in r['golds']:
            if (t, g['g']) not in cl:
                continue
            hk = [x for x in g['rows'] if x['hk']]
            out[(t, g['g'])] = dict(kind=g['kind'], hk_n=len(hk), hk_tries=sum(ops[x['i']]['slot_tries'] for x in hk), held_n=sum(1 for x in g['rows'] if x['held']), ready_n=len(g['rows']),
                                    covered=g['covered'])
    return out


def main():
    L = {j: live(j) for j in JOBS}
    cl = set(L['m2c_s0'][0])
    R = {a: r1(a, cl) for a in ('bundle_s0', 'bundle_s1')}
    res = {}
    print('%-10s %5s %8s %8s %8s %10s %10s %8s' % ('job', 'forms', 'hk>0', 'covered', 'hk open', 'hk tries', 'med tries', 'ready>0'))
    for j, d in list(R.items()) + [(j, L[j][0]) for j in JOBS]:
        hk = [v for v in d.values() if v['hk_n'] > 0]
        s = dict(forms=len(d), forms_hk=len(hk), covered=sum(v['covered'] for v in d.values()), hk_open=sum(v['hk_n'] for v in d.values()),
                 hk_tries=sum(v['hk_tries'] for v in d.values()), med_tries_hk=statistics.median([v['hk_tries'] for v in hk]) if hk else 0,
                 forms_ready=sum(1 for v in d.values() if v['ready_n'] > 0), forms_held=sum(1 for v in d.values() if v['held_n'] > 0),
                 by_kind={k: dict(forms=sum(1 for v in d.values() if v['kind'] == k), hk=sum(1 for v in hk if v['kind'] == k), tries=sum(v['hk_tries'] for v in d.values() if v['kind'] == k)) for k in sorted({v['kind'] for v in d.values()})})
        res[j] = s
        print('%-10s %5d %8d %8d %8d %10d %10.0f %8d' % (j, s['forms'], s['forms_hk'], s['covered'], s['hk_open'], s['hk_tries'], s['med_tries_hk'], s['forms_ready']), s['by_kind'])
    # paired by form: arm against control, same seed
    for s in ('0', '1'):
        c, a = L['m2c_s' + s][0], L['m2s_s' + s][0]
        both = sum(1 for k in c if c[k]['hk_n'] and a[k]['hk_n'])
        only_c = sum(1 for k in c if c[k]['hk_n'] and not a[k]['hk_n'])
        only_a = sum(1 for k in c if a[k]['hk_n'] and not c[k]['hk_n'])
        res['pair_s' + s] = dict(both=both, only_control=only_c, only_arm=only_a)
        print('seed', s, 'hk in both', both, 'control only', only_c, 'arm only', only_a)
    res['tries_by_kind'] = {j: dict(L[j][1]) for j in JOBS}
    for j in JOBS:
        print(j, 'tries by visit kind', dict(L[j][1]), 'total', sum(L[j][1].values()))
    json.dump(dict(summary=res, live={j: {'%s:%d' % k: v for k, v in L[j][0].items()} for j in JOBS}, r1={a: {'%s:%d' % k: v for k, v in R[a].items()} for a in R}),
              open(HERE + '/a_summary.json', 'w'), indent=1)


main()
