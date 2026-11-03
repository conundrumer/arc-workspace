"""The tilt weight of each reads model, on fit tasks only.

  gold_tables_env.sh gamma_tune.py "reads RULE DET"|"reads INIT"

Models fit on fit tasks outside task fold 0. Saved bits read on the census walks of fold 0, teacher-forced on the cover view, in `walks-fit/`. Written to gamma-TARGET.json. The steered prior was fit on these tasks too, so its picks here cost less than on held, and a tilt weight here runs low if anything.
"""
import glob
import json
import os
import re
import sys
import time

import numpy as np

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-backward-from-out-content-heldout37'  # the data folder
sys.path.insert(0, HERE)
import backward_edges as E  # noqa: E402
import next_form_facts as F  # noqa: E402
import next_form_model as M  # noqa: E402
import tune as T  # noqa: E402

GAMMAS = (0, .2, .4, .6, .8, 1.0, 1.25, 1.5, 2.0)
HEAD = re.compile(r'\(\S+\s+&r(\d+)')


def slot_keys(forms):
    """{slot number: (form, derived key)} of a task's forms, from the heads' slot numbers."""
    heads = []
    for f, r in enumerate(forms):
        m = HEAD.match(r['text'])
        heads.append((int(m.group(1)) if m else None, f))
    heads = sorted(h for h in heads if h[0] is not None)
    out = {}
    for i, (s, f) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else s + 1
        for k in range(s, max(end, s + 1)):
            out[k] = (f, F.key_of(forms[f], k - s))
    return out


def pick_saved(p, z, ix, slots, gamma):
    """Bits a tilt saves at one census pick. An option with no key keeps lift 1. The census's scope sets the options, so the walk's own written order stands in the baseline; the lift reads no pick index and no prefix."""
    s = den = 0.0
    lift_g = 1.0
    for name, code, w in p['rels']:
        k = name
        if code == 'd':
            m = re.match(r'&r(\d+)', name)
            o = slots.get(int(m.group(1))) if m else None
            k = o[1] if o else None
        j = ix.get(k)
        l = float(np.exp(gamma * z[j])) if j is not None else 1.0
        s += w
        den += w * l
        if name == p['gold']:
            lift_g = l
    den = (den + max(p['sum'] - s, 0.0)) / p['sum']
    return float(np.log2(lift_g) - np.log2(den))


def lifts(model, data, rows):
    """{(task, form): z over the vocabulary} for one row per form."""
    d = M.Data([dict(r, y='<other>') for r in rows], data.v, data.kinds)
    z = np.zeros((len(rows), len(data.v)))
    for w, e in zip(model.w, model.ex):
        z += w * e.lift(d)
    return {(r['task'], r['form']): z[i] for i, r in enumerate(rows)}


def main():
    name = sys.argv[1]
    path = HERE + '/gamma-%s.json' % name.replace(' ', '-')
    t0 = time.time()
    tasks, prim, _ = T.load_fit()
    E.open_keys_row(prim, tasks)
    res = json.load(open(HERE + '/keys-%s.json' % name.replace(' ', '-')))
    walks = {}
    for p in glob.glob(HERE + '/walks-fit/walk-fit-*.jsonl'):
        for x in open(p):
            r = json.loads(x)
            if not r.get('error'):
                walks[r['task'], r['form']] = r
    a, d = T.data_of(name, prim)
    trn = np.nonzero(d.fold != 0)[0]
    sub = M.Data([a[i] for i in trn], d.v, d.kinds, d.mask[trn])
    te = [dict(task=r['task'], form=r['form'], kind=r['kind'], fact=r['fact']) for r in prim if M.fold_of(r['task']) == 0 and r['kind'] in T.BAGS[name] and (r['task'], r['form']) in walks]
    ix = {t: i for i, t in enumerate(d.v)}
    slots = {t: slot_keys(tasks[t]) for t in {r['task'] for r in te}}
    out = dict(target=name, forms=len(te), tiers={})
    done = json.load(open(path))['tiers'] if os.path.exists(path) else {}
    out['tiers'].update(done)
    for tier, v in res['tiers'].items():
        if tier in done:
            continue
        keys = [tuple(k) for k in v['keys']]
        if any(keys == [tuple(x) for x in res['tiers'][o]['keys']] for o in out['tiers']):
            same = next(o for o in out['tiers'] if keys == [tuple(x) for x in res['tiers'][o]['keys']])
            out['tiers'][tier] = out['tiers'][same]
            continue
        m = M.Model(sub, keys)
        L = lifts(m, sub, te)
        cur = {}
        for g in GAMMAS:
            cur[str(g)] = round(float(np.mean([sum(pick_saved(p, L[r['task'], r['form']], ix, slots[r['task']], g) for p in walks[r['task'], r['form']]['picks']) for r in te])), 3)
        best = max(cur, key=cur.get)
        out['tiers'][tier] = dict(gamma=float(best), curve=cur)
        print(name, tier, cur, 'best', best, round(time.time() - t0), flush=True)
        json.dump(out, open(path, 'w'), indent=1)


if __name__ == '__main__':
    main()
