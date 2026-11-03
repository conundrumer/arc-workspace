"""Need per candidate: tune the tilt weight on fit, then read held once.

  gold_tables_env.sh candidate_read.py gamma     tilt weights on the census walks of fit fold 0, models fit outside that fold
  gold_tables_env.sh candidate_read.py held      the held read. It refuses to run a second time while read-candidate-held.json exists.

Reads:
  which table: bits to name the read table among the candidates, against log2 of their count, top-1 and top-5, by depth, on primary edges
  census tilt: at a relation pick of the census walk, each derived option's weight is multiplied by lift^gamma, and the weights inside the derived options are renormalized, so the share of derived against lib options stays as the census has it. Arm out applies at every pick. Arms hole and both apply where gold's option is derived, and that reads the reader: they assume the pick is known to be that hole.

Written order that stands in this read: the census walk draws atoms in written order, and its derived options are the forms before the form in gold's text. No model reads either.
"""
import json
import os
import re
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import backward_edges as E  # noqa: E402
import candidate_model as C  # noqa: E402
import final_read as R  # noqa: E402
import gamma_tune as G  # noqa: E402
import next_form_facts as F  # noqa: E402
import next_form_model as M  # noqa: E402

GAMMAS = (.4, .6, .8, 1.0, 1.25, 1.5)
L2 = 1e-4
LIBS = json.load(open(HERE + '/top-libs.json'))


def table_index(tb):
    return {(t['form'], t['ord']): t for t in tb['tables']}


def slot_form(forms):
    """{slot number: (form, ord)}."""
    heads = sorted((int(m.group(1)), f) for f, r in enumerate(forms) for m in [G.HEAD.match(r['text'])] if m)
    out = {}
    for i, (s, f) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else s + 1
        for k in range(s, max(end, s + 1)):
            out[k] = (f, k - s)
    return out


def pick_saved_d(p, zs, gold_key, slots, gamma):
    """The bits a tilt inside the derived options saves at one pick. zs: {(form, ord): z}. An option with no z takes the mean z."""
    if gold_key is None or not zs:
        return 0.0
    mean = float(np.mean(list(zs.values())))
    den = w_all = 0.0
    zg = mean
    for name, code, w in p['rels']:
        if code != 'd':
            continue
        m = re.match(r'&r(\d+)', name)
        k = slots.get(int(m.group(1))) if m else None
        z = zs.get(k, mean)
        den += w * np.exp(gamma * z)
        w_all += w
        if k == gold_key:
            zg = z
    if w_all == 0:
        return 0.0
    return float((gamma * zg - np.log(den / w_all)) / np.log(2))


def gold_of_pick(p, slots):
    m = re.match(r'&r(\d+)$', p['gold'])
    return slots.get(int(m.group(1))) if m else None


def form_saved(task, form, walk, forms, tb, slots, arm, w, vc, by_edge, gamma):
    """The saved bits of a form's walk under one arm, from model weights w over vocabulary vc."""
    tix = table_index(tb)
    r = forms[form]
    rk_fact = dict(b_rk=r['kind'])

    def z_of(fact):
        out = {}
        for k, t in tix.items():
            if t['form'] >= form:
                continue
            ks = C.cand_keys(arm, fact, t, forms[t['form']]['kind'])
            out[k] = sum(w[vc[x]] for x in ks if x in vc)
        return out

    total = 0.0
    zout = z_of(rk_fact) if arm == 'out' else None
    for p in walk['picks']:
        g = gold_of_pick(p, slots)
        if g is None:
            continue
        if arm == 'out':
            total += pick_saved_d(p, zout, g, slots, gamma)
        else:
            facts = by_edge.get((task, form, g[0]))
            if not facts:
                continue
            zs = [z_of(f) for f in facts]
            mean = {k: float(np.mean([z[k] for z in zs])) for k in zs[0]}
            total += pick_saved_d(p, mean, g, slots, gamma)
    return total


def gamma():
    t0 = time.time()
    tasks = F.load('fit')
    rows, _ = E.edge_rows('fit', tasks, LIBS)
    prim = [r for r in rows if r['primary']]
    tables = C.load_tables('fit')
    walks = {}
    for k in range(4):
        for x in open(HERE + '/walks-fit/walk-fit-%d.jsonl' % k):
            r = json.loads(x)
            if not r.get('error'):
                walks[r['task'], r['form']] = r
    by_edge = {}
    for r in rows:
        if r['reader'] >= 0:
            by_edge.setdefault((r['task'], r['reader'], r['form']), []).append(r['fact'])
    out = {}
    for arm in ('out', 'hole', 'holeb', 'both'):
        s = C.Set(prim, tasks, tables, arm)
        X, vc = s.encode()
        w = C.fit(X, s.seg, s.start, s.y, len(vc), s.fold != 0, L2)
        print(arm, 'fit', round(time.time() - t0), flush=True)
        cur = {}
        slots = {t: slot_form(tasks[t]) for t in {k[0] for k in walks}}
        for g in GAMMAS:
            x = []
            for (t, f), wk in walks.items():
                if f < len(tasks[t]) and tables[t]['tables']:
                    x.append(form_saved(t, f, wk, tasks[t], tables[t], slots[t], arm, w, vc, by_edge, g))
            cur[str(g)] = round(float(np.mean(x)), 3)
            print(arm, g, cur[str(g)], round(time.time() - t0), flush=True)
        best = max(cur, key=cur.get)
        out[arm] = dict(gamma=float(best), curve=cur, forms=len(x))
        json.dump(out, open(HERE + '/gamma-candidate.json', 'w'), indent=1)


def read_one(name, s, X, vc, sr, w):
    Xr, _ = sr.encode(vc)
    z = C.score(w, Xr)
    bits, base, rank = C.read_bits(z, sr)
    dp = np.array([min(r['depth'], 4) for r in sr.edge])
    by = {str(d): [int((dp == d).sum()), round(float(base[dp == d].mean()), 3), round(float(bits[dp == d].mean()), 3), round(float((rank[dp == d] == 0).mean()), 3), round(float((rank[dp == d] < 5).mean()), 3)] for d in (1, 2, 3, 4) if (dp == d).any()}
    saved = [(r['task'], float(a - b)) for r, a, b in zip(sr.edge, base, bits)]
    return dict(uniform=round(float(base.mean()), 3), model=round(float(bits.mean()), 3), top1=round(float((rank == 0).mean()), 3), top5=round(float((rank < 5).mean()), 3), saved=R.boot(saved), by_depth=by, edges=sr.n, cands_mean=round(float(np.diff(sr.start).mean()), 1))


def held():
    t0 = time.time()
    path = HERE + '/read-candidate-held.json'
    if os.path.exists(path):
        sys.exit('read-candidate-held.json exists: this held read is done')
    tf = F.load('fit')
    fr, _ = E.edge_rows('fit', tf, LIBS)
    fp = [r for r in fr if r['primary']]
    tabs = C.load_tables('fit')
    tabd = C.load_tables('fit', True)
    ts = F.load('held')
    hr, _ = E.edge_rows('held', ts, LIBS)
    hp = [r for r in hr if r['primary']]
    htab = C.load_tables('held', True)
    gam = json.load(open(HERE + '/gamma-candidate.json'))
    census = R.census_rows()
    per = {k: dict(bits=(census.get(k) or {}).get('bits')) for k in ((t, r['form']) for t, f in ts.items() for r in f)}
    walks = R.load_walks()
    by_edge = {}
    for r in hr:
        if r['reader'] >= 0:
            by_edge.setdefault((r['task'], r['reader'], r['form']), []).append(r['fact'])
    slots = {t: slot_form(ts[t]) for t in ts}
    out = dict(reads=0, arms={}, tilt={})
    per_form = {}
    for arm in ('out', 'hole', 'holeb', 'both'):
        s = C.Set(fp, tf, tabs, arm)
        X, vc = s.encode()
        w = C.fit(X, s.seg, s.start, s.y, len(vc), np.ones(s.n, dtype=bool), L2)
        sr = C.Set(hp, ts, htab, arm)
        out['arms'][arm] = read_one(arm, s, X, vc, sr, w)
        out['reads'] += 1
        g = gam[arm]['gamma']
        sv = {}
        for (t, f), wk in walks.items():
            if wk.get('error') or f >= len(ts[t]) or t not in htab:
                continue
            sv[t, f] = form_saved(t, f, wk, ts[t], htab[t], slots[t], arm, w, vc, by_edge, g)
        out['tilt'][arm] = dict(gamma=g, **R.summarize(sv, per))
        for k, v in sv.items():
            per_form.setdefault(k, {})[arm] = round(v, 3)
        over = [k for k in sv if per[k]['bits'] is not None and per[k]['bits'] >= 25]
        out['tilt'][arm]['forms_taken_under'] = sum(per[k]['bits'] - sv[k] < 25 for k in over)
        print(arm, json.dumps(out['arms'][arm]), json.dumps(out['tilt'][arm]), round(time.time() - t0), flush=True)
        if arm == 'both':
            top = sorted(((abs(w[i]), k, round(float(w[i]), 2)) for k, i in vc.items()), reverse=True)[:40]
            out['top_weights'] = [(k, v) for _, k, v in top]
    # Control: labels drawn at random among the candidates at fit.
    s = C.Set(fp, tf, tabs, 'both', control=True)
    X, vc = s.encode()
    w = C.fit(X, s.seg, s.start, s.y, len(vc), np.ones(s.n, dtype=bool), L2)
    sr = C.Set(hp, ts, htab, 'both')
    out['arms']['both control'] = read_one('both control', s, X, vc, sr, w)
    out['reads'] += 1
    # Distractors: tables of other tasks' programs on this task's grids, in fit and in the read.
    for arm in ('out', 'both'):
        fpd = [r for r in fp if r['task'] in tabd]
        s = C.Set(fpd, tf, tabd, arm, distract=True)
        X, vc = s.encode()
        w = C.fit(X, s.seg, s.start, s.y, len(vc), np.ones(s.n, dtype=bool), L2)
        sr = C.Set(hp, ts, htab, arm, distract=True)
        out['arms'][arm + ' with distractors'] = read_one(arm, s, X, vc, sr, w)
        out['arms'][arm + ' with distractors']['fit_edges'] = s.n
        out['reads'] += 1
        print(arm, 'distract', json.dumps(out['arms'][arm + ' with distractors']), round(time.time() - t0), flush=True)
    ms = [x for t in htab.values() for x in t.get('ms', ())]
    out['cost'] = dict(table_need_ms_median=round(float(np.median(ms)), 3), table_need_ms_max=round(float(np.max(ms)), 3), edge_facts_ms_median=round(float(np.median([r['t_fact'] for r in hr])) * 1000, 3), edge_facts_ms_max=round(float(np.max([r['t_fact'] for r in hr])) * 1000, 3), tables_per_edge_mean=out['arms']['both']['cands_mean'])
    json.dump(out, open(path, 'w'), indent=1)
    with open(HERE + '/per-form-candidate-held.jsonl', 'w') as f:
        for k, v in sorted(per_form.items()):
            f.write(json.dumps(dict(task=k[0], form=k[1], **v)) + '\n')
    print('reads', out['reads'], round(time.time() - t0), flush=True)


if __name__ == '__main__':
    gamma() if sys.argv[1] == 'gamma' else held()
