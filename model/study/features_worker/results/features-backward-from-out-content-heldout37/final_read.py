"""The held read of the frozen models. Each model fits on all fit tasks, with the keys of keys-*.json, and reads the held tasks once.

  gold_tables_env.sh final_read.py PART    one part. It refuses to run a second time while read-held-PART.json exists.
  gold_tables_env.sh final_read.py merge   the sums on one census walk, the depths, the counts under 25 bits.

A row is the primary edge of a form. A form with no primary edge keeps the census's bits, so it saves 0.

Census unit: the component pick of an INIT or a DET, census paid minus model bits, and a tilt on each relation pick of the census walk.

Written order that stands in this read: the census walk draws a form's atoms in written order, and its steered weights read the prefix, so the baseline holds that order. The walk's scope is the forms before the form in gold's text, as the census has it. No model here reads either: a lift is one number per form and option, with no pick index and no prefix.
"""
import json
import os
import random
import subprocess
import sys
import time

import numpy as np

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-backward-from-out-content-heldout37'  # the data folder
sys.path.insert(0, HERE)
import backward_edges as E  # noqa: E402
import gamma_tune as G  # noqa: E402
import next_form_facts as F  # noqa: E402
import next_form_model as M  # noqa: E402
import tune as T  # noqa: E402

C = '/Users/davidlu/code/arc-workspace/work/lm/data-study/census/census-bands-cheapest/forms.jsonl'
PARTS = {'a': ('comp INIT', 'comp DET', 'kind', 'geom', 'rel'), 'b': ('cols',), 'd': ('reads RULE DET',), 'e': ('reads INIT',)}
TIERS = ('out', 'body', 'body+cols', 'full', 'open')
BOOT = 10000


def boot(rows, n=BOOT, seed=7):
    if not rows:
        return None
    tasks = sorted({t for t, _ in rows})
    ix = {t: i for i, t in enumerate(tasks)}
    s = np.zeros(len(tasks))
    c = np.zeros(len(tasks))
    for t, x in rows:
        s[ix[t]] += x
        c[ix[t]] += 1
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(tasks), size=(n, len(tasks)))
    m = s[pick].sum(1) / np.maximum(c[pick].sum(1), 1)
    return [round(float(s.sum() / c.sum()), 3), round(float(np.quantile(m, .025)), 3), round(float(np.quantile(m, .975)), 3), len(rows), len(tasks)]


def shuffled(rows, seed=1):
    rng = random.Random(seed)
    out = [dict(r) for r in rows]
    by = {}
    for i, r in enumerate(out):
        by.setdefault(r['kind'], []).append(i)
    for k, ix in by.items():
        fs = [out[i]['fact'] for i in ix]
        rng.shuffle(fs)
        for i, x in zip(ix, fs):
            out[i]['fact'] = x
    return out


def census_rows():
    return {(r['task'], r['form']): r for r in map(json.loads, open(C))}


def load_walks():
    p = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-next-form-content-given-task-heldout37/walks-held/walk-held-0.jsonl.zst'
    t = subprocess.run(['zstd', '-dc', p], capture_output=True, check=True).stdout.decode()
    return {(r['task'], r['form']): r for r in map(json.loads, t.splitlines())}


def by_depth(rows, base, model, rk):
    """Per depth: rows, baseline bits, model bits, top-1, top-5."""
    dp = np.array([r['depth'] for r in rows])
    out = {}
    for x in (1, 2, 3, 4):
        at = dp == x
        if at.any():
            out[str(x)] = [int(at.sum()), round(float(base[at].mean()), 3), round(float(model[at].mean()), 3), round(float((rk[at] == 0).mean()), 3), round(float((rk[at] < 5).mean()), 3)]
    return out


def summarize(saved, per):
    a = [(k[0], v) for k, v in saved.items() if per[k]['bits'] is not None]
    b = [(k[0], v) for k, v in saved.items() if per[k]['bits'] is not None and per[k]['bits'] >= 25]
    return dict(all=boot(a), at25=boot(b))


def read_part(part):
    t0 = time.time()
    if os.path.exists(HERE + '/read-held-%s.json' % part):
        sys.exit('read-held-%s.json exists: this held read is done' % part)
    tf, fit, _ = T.load_fit()
    E.open_keys_row(fit, tf)
    libs = json.load(open(HERE + '/top-libs.json'))
    ts = F.load('held')
    edges, counts = E.edge_rows('held', ts, libs)
    rows = [r for r in edges if r['primary']]
    E.open_keys_row(rows, ts)
    census = census_rows()
    per = {}
    for t, forms in ts.items():
        for r in forms:
            c = census.get((t, r['form']))
            per[t, r['form']] = dict(task=t, form=r['form'], kind=r['kind'], bits=(c or {}).get('bits'), source=r['source'])
    for r in rows:
        per[r['task'], r['form']]['depth'] = min(r['depth'], 4)
    out = dict(part=part, targets={}, counts=dict(counts), primary=len(rows))
    reads = 0
    for name in PARTS[part]:
        res = json.load(open(HERE + '/keys-%s.json' % name.replace(' ', '-')))
        keyt = {k: [tuple(x) for x in v['keys']] for k, v in res['tiers'].items()}
        if name in T.BAGS:
            kinds = T.BAGS[name]
            a = T.bag_rows(fit, kinds)
            b = T.bag_rows(rows, kinds)
            V = M.vocab_of(a, 8)
            kk = sorted({r['kind'] for r in a})
            da, db = M.Data(a, V, kk, T.mask_of(a, V)), M.Data(b, V, kk, T.mask_of(b, V))
            one = {}
            for r in rows:
                if r['kind'] in kinds:
                    one[r['task'], r['form']] = dict(task=r['task'], form=r['form'], kind=r['kind'], fact=r['fact'])
            frows = list(one.values())
            walks = load_walks()
            ix = {t: i for i, t in enumerate(V)}
            slots = {t: G.slot_keys(ts[t]) for t in ts}
            gam = json.load(open(HERE + '/gamma-%s.json' % name.replace(' ', '-')))['tiers']
            r_ = dict(vocab=len(V), reads=len(b), forms=len(frows), tiers={})
            models = [(t, M.Model(da, keyt[t])) for t in TIERS]
            models.append(('control', M.Model(M.Data(shuffled(a), V, kk, T.mask_of(a, V)), keyt['full'])))
            for tier, m in models:
                mb, mm, rk = m.read(db)
                reads += 1
                L = G.lifts(m, da, frows)
                g = gam['full' if tier == 'control' else tier]['gamma']
                sp = {}
                for k in one:
                    w = walks.get(k)
                    if w and not w.get('error'):
                        sp[k] = sum(G.pick_saved(p, L[k], ix, slots[k[0]], g) for p in w['picks'])
                d = dict(marginal_per_read=round(float(mb.mean()), 3), model_per_read=round(float(mm.mean()), 3), top1=round(float((rk == 0).mean()), 3), top5=round(float((rk < 5).mean()), 3), gamma=g, keys=['*'.join(x) for x in m.keys], w=[round(float(x), 3) for x in m.w], by_depth=by_depth(b, mb, mm, rk), tilt=summarize(sp, per), paid_rel_picks=round(float(np.mean([sum(p['q_bits'] for p in walks[k]['picks']) for k in sp])), 3))
                for k, v in sp.items():
                    per[k]['tilt ' + tier] = round(v, 3)
                r_['tiers'][tier] = d
                print(name, tier, d['marginal_per_read'], d['model_per_read'], g, d['tilt'], round(time.time() - t0), flush=True)
            out['targets'][name] = r_
            continue
        a = T.cat_rows(fit, name)
        b = T.cat_rows(rows, name)
        V = M.vocab_of(a, T.TARGETS[name][2])
        kk = sorted({r['kind'] for r in a})
        da, db = M.Data(a, V, kk), M.Data(b, V, kk)
        r_ = dict(vocab=len(V), forms=len(b), other_share=round(float((db.y == len(V) - 1).mean()), 3), tiers={})
        for tier in TIERS:
            m = M.Model(da, keyt[tier])
            mb, mm, rk = m.read(db)
            reads += 1
            sv = {(r['task'], r['form']): float(x - y) for r, x, y in zip(b, mb, mm)}
            d = dict(marginal=round(float(mb.mean()), 3), model=round(float(mm.mean()), 3), top1=round(float((rk == 0).mean()), 3), top5=round(float((rk < 5).mean()), 3), keys=['*'.join(x) for x in keyt[tier]], w=[round(float(x), 3) for x in m.w], by_depth=by_depth(b, mb, mm, rk), vs_marginal=summarize(sv, per))
            if name in ('comp INIT', 'comp DET'):
                sc = {}
                for r, y in zip(b, mm):
                    c = census.get((r['task'], r['form']))
                    if c and c.get('parts'):
                        p = c['parts']
                        paid = p.get('component', 0.0) if name == 'comp INIT' else p.get('proposer', 0.0) + p.get('proposer or atoms', 0.0)
                        sc[r['task'], r['form']] = paid - float(y)
                        per[r['task'], r['form']]['paid ' + name] = round(paid, 3)
                d['census_paid'] = round(float(np.mean([per[k]['paid ' + name] for k in sc])), 3)
                d['vs_census'] = summarize(sc, per)
                for k, v in sc.items():
                    per[k]['comp ' + tier] = round(v, 3)
            r_['tiers'][tier] = d
            print(name, tier, d['marginal'], d['model'], d['top1'], d['top5'], d.get('census_paid'), d['vs_marginal']['at25'], round(time.time() - t0), flush=True)
        ctl = M.Model(M.Data(shuffled(a), V, kk), keyt['full'])
        cb, cm, _ = ctl.read(db)
        reads += 1
        r_['control'] = summarize({(r['task'], r['form']): float(x - y) for r, x, y in zip(b, mb, cm)}, per)
        out['targets'][name] = r_
    out['model_reads'] = reads
    with open(HERE + '/per-form-held-%s.jsonl' % part, 'w') as f:
        for k in sorted(per):
            f.write(json.dumps(per[k], separators=(',', ':')) + '\n')
    json.dump(out, open(HERE + '/read-held-%s.json' % part, 'w'), indent=1)
    print('part', part, 'reads', reads, 'seconds', round(time.time() - t0), flush=True)


def merge():
    per = {}
    out = dict(targets={})
    reads = 0
    for part in PARTS:
        for x in open(HERE + '/per-form-held-%s.jsonl' % part):
            r = json.loads(x)
            per.setdefault((r['task'], r['form']), {}).update(r)
        d = json.load(open(HERE + '/read-held-%s.json' % part))
        out['targets'].update(d['targets'])
        reads += d['model_reads']
        out['counts'] = d['counts']
        out['primary'] = d['primary']
    ok = [k for k in per if per[k]['bits'] is not None]
    out.update(forms=len(per), tasks=len({k[0] for k in per}), forms_with_bits=len(ok), forms_25=sum(per[k]['bits'] >= 25 for k in ok), model_reads=reads)
    joint = {}
    for tier in TIERS + ('control',):
        sv = {}
        for k in ok:
            p = per[k]
            sv[k] = p.get('tilt ' + tier, 0.0) + (p.get('comp ' + tier, 0.0) if tier != 'control' else 0.0)
            p['t1 ' + tier] = round(sv[k], 3)
        over = [k for k in ok if per[k]['bits'] >= 25]
        under = [k for k in over if per[k]['bits'] - sv[k] < 25]
        bytask = {}
        for k in ok:
            bytask.setdefault(k[0], []).append(k)
        joint[tier] = dict(saved=summarize(sv, per), forms_over=len(over), forms_taken_under=len(under), tasks_under_before=sum(all(per[k]['bits'] < 25 for k in v) for v in bytask.values()), tasks_under_after=sum(all(per[k]['bits'] - sv[k] < 25 for k in v) for v in bytask.values()), tasks=len(bytask))
        for x in (1, 2, 3, 4):
            sub = {k: v for k, v in sv.items() if per[k].get('depth') == x}
            joint[tier]['depth %d' % x] = summarize(sub, per)
        bk = {}
        for kd in ('RULE', 'DET', 'INIT'):
            bk[kd] = summarize({k: v for k, v in sv.items() if per[k]['kind'] == kd}, per)
        joint[tier]['by kind'] = bk
    out['census_unit'] = joint
    with open(HERE + '/per-form-held.jsonl', 'w') as f:
        for k in sorted(per):
            f.write(json.dumps(per[k], separators=(',', ':')) + '\n')
    json.dump(out, open(HERE + '/read-held.json', 'w'), indent=1)
    print(json.dumps({k: {a: b for a, b in v.items() if a in ('saved', 'forms_taken_under', 'tasks_under_after', 'tasks_under_before')} for k, v in joint.items()}, indent=0), 'reads', reads)


if __name__ == '__main__':
    if sys.argv[1] == 'merge':
        merge()
    else:
        read_part(sys.argv[1])
