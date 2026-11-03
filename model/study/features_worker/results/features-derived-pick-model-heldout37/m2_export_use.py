"""Reference scorer for X/m2-export.pkl in plain Python (math only), and the check that it equals the fitted model.

    scoring (no dependencies):  import m2_export_use as E; e = E.load(); s = E.scores(e, [facts of each derived option]); sigma = E.sigma(e, gate_facts, s)
    check (needs numpy and the engine-free fit code):  bash REC/env.sh ../features-derived-pick-model-heldout37/m2_export_use.py [--rows FILE] [--n 400]
        scores training picks (rows of X/rows) with the plain-number export and with hook.Model on X/fit-cal (what job3.py --cal uses); the scores and sigmas must agree to 1e-9.
"""
import math
import pickle

X = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37'


def load(path=X + '/m2-export.pkl'):
    e = pickle.load(open(path, 'rb'))
    e['_lx'] = {n: i for i, n in enumerate(e['logit_names'])}
    e['_gx'] = {n: i for i, n in enumerate(e['gate_names'])}
    return e


def vec(names_ix, n, facts, coltypes=(), ignore=()):
    """The raw vector of a sparse fact dict."""
    v = [0.0] * n
    ct = set(coltypes)
    for k, x in facts.items():
        if k in ignore:
            continue
        if k.startswith('ct:') and k[3:] not in ct and k != 'ct:other':
            v[names_ix['ct:other']] += x
        else:
            v[names_ix[k]] += x  # an unknown name is an error
    return v


def scores(e, facts_list):
    ign, ct, ix = set(e['logit_ignore']), e['coltypes'], e['_lx']
    n = len(e['logit_names'])
    out = []
    for f in facts_list:
        v = vec(ix, n, f, ct, ign)
        out.append(sum(b * (x - m) / s for b, x, m, s in zip(e['logit_beta'], v, e['logit_mean'], e['logit_scale'])))
    return out


def sigma(e, gate_facts, s):
    mx = max(s)
    lse = mx + math.log(sum(math.exp(x - mx) for x in s))
    f = dict(gate_facts)
    f['lse'], f['mx'] = lse - math.log(len(s)), mx - lse
    v = vec(e['_gx'], len(e['gate_names']), f)
    z = sum(c * (x - m) / sc for c, x, m, sc in zip(e['gate_coef'], v, e['gate_mean'], e['gate_scale'])) + e['gate_intercept']
    z = z * e['temp'] + e['bias']
    return 1.0 / (1.0 + math.exp(-z))


def main():
    import argparse
    import json
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument('--rows', default=X + '/rows/n600.0of1.jsonl')
    ap.add_argument('--n', type=int, default=400)
    a = ap.parse_args()
    sys.path.insert(0, X)
    import hook
    M = hook.Model(X + '/fit-cal')
    e = load()
    assert not any('numpy' in type(v).__module__ for v in e.values() if not isinstance(v, (list, dict, str, float, int)))
    npick, worst_s, worst_g = 0, 0.0, 0.0
    for l in open(a.rows):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        for pr in r.get('pairs', []):
            for row in pr['rows']:
                D = row['D']
                if not D or npick >= a.n:
                    continue
                facts = [d[6] for d in D]
                s1 = scores(e, facts)
                s2 = [float(x) for x in M.scores(facts)]
                g1 = sigma(e, row['gf'], s1)
                g2 = M.sigma(row['gf'], M.scores(facts))
                worst_s = max(worst_s, max(abs(x - y) for x, y in zip(s1, s2)))
                worst_g = max(worst_g, abs(g1 - g2))
                npick += 1
        if npick >= a.n:
            break
    print('picks checked %d, largest score difference %.2e, largest sigma difference %.2e' % (npick, worst_s, worst_g))
    assert npick > 0 and worst_s < 1e-9 and worst_g < 1e-9
    print('ok')


if __name__ == '__main__':
    main()
