"""The read of the frozen models on one split.

  gold_tables_env.sh final_read.py dev PART     tune read of one part: writes tilt weights to gamma-PART.json
  gold_tables_env.sh final_read.py held PART    the held read of one part. It refuses to run a second time while read-held-PART.json exists.
  gold_tables_env.sh final_read.py SPLIT merge  joins the parts: the sums on one census walk, the shares, the cost, the counts under 25 bits.

Every model is fit on fit tasks only, with the situation keys in frozen.json. Bits are per form. Numbers go to read-<split>-<part>.json, read-<split>.json and per-form-<split>.jsonl.

Saved bits on a target:
  comp INIT, comp DET: census paid for the part minus model bits.
  reads tilt: at each relation pick of the census walk, each option's weight is multiplied by its lift (the model's rate over the kind's rate) to the power gamma, then normalized. Saved is the sum over the form's picks. It is an exact change of the census's bits.
  the rest: bits under the target's marginal on fit tasks, in the kind, minus bits under the model.
"""
import glob
import json
import math
import os
import random
import re
import sys
import time

import numpy as np

import next_form_facts as F
import next_form_model as M

C = '/Users/davidlu/code/arc-workspace/work/lm/data-study/census/census-bands-cheapest/forms.jsonl'
TARGETS = {
    'comp INIT': ('t_comp', ('INIT',), 1),
    'comp DET': ('t_comp', ('DET',), 1),
    'cols': ('t_cols', ('RULE', 'DET', 'INIT'), 5),
    'coarse cols': ('t_coarse', ('RULE', 'DET', 'INIT'), 5),
    'geom': ('t_geom', ('RULE', 'DET', 'INIT'), 1),
    'rel': ('t_rel', ('RULE', 'DET', 'INIT'), 1),
    'shape': ('t_shape', ('RULE', 'DET', 'INIT'), 5),
    'content': ('t_content', ('RULE', 'DET', 'INIT'), 5),
}
BAGS = {'reads RULE DET': ('RULE', 'DET'), 'reads INIT': ('INIT',)}
PARTS = {'a': ('comp INIT', 'comp DET', 'geom', 'rel'), 'b': ('coarse cols', 'cols', 'shape'), 'c': ('content',), 'd': ('reads RULE DET',), 'e': ('reads INIT',)}
TIERS = ('need', 'foundset', 'need+foundset', 'all')
GAMMAS = (0, .1, .2, .3, .4, .5, .6, .8, 1.0)
HEAD = re.compile(r'\(\S+\s+&r(\d+)')
BOOT = 10000


def mask_of(rows, vocab):
    ix = {v: i for i, v in enumerate(vocab)}
    m = np.ones((len(rows), len(vocab)), dtype=bool)
    dk = [i for v, i in ix.items() if v.startswith('D:')]
    m[:, dk] = False
    for i, r in enumerate(rows):
        for k in r['open']:
            j = ix.get(k)
            if j is not None:
                m[i, j] = True
        j = ix.get(r['y'])
        if j is not None:
            m[i, j] = True
    return m


def shuffled(rows, seed=1):
    """Rows with the pairing of facts and labels shuffled inside the kind. The facts move, so that a label stays with the keys open at its own state."""
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


def boot(rows, value, n=BOOT, seed=7):
    """Rows: (task, x). The mean of x, with a 95% interval on resampled tasks."""
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


def slot_keys(forms):
    """{slot number: derived key} of a task's forms."""
    heads = []
    for f, r in enumerate(forms):
        m = HEAD.match(r['text'])
        heads.append((int(m.group(1)) if m else None, f))
    heads = [h for h in heads if h[0] is not None]
    out = {}
    for i, (s, f) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else s + 1
        for k in range(s, max(end, s + 1)):
            out[k] = (f, F.key_of(forms[f], k - s))
    return out


def load_walks(split):
    folder = F.R + ('walks-held/' if split == 'held' else 'walks/')
    out = {}
    for p in glob.glob(folder + 'walk-%s-*.jsonl' % split):
        with open(p) as f:
            for x in f:
                r = json.loads(x)
                out[r['task'], r['form']] = r
    return out


class Tilt:
    """Lifts of a read model, per form."""

    def __init__(self, model, data, rows_by_form):
        self.model = model
        self.v = {t: i for i, t in enumerate(data.v)}
        self.rows = rows_by_form
        fr = list(rows_by_form.values())
        d = M.Data([dict(r, y='<other>') for r in fr], data.v, data.kinds)
        z = np.zeros((len(fr), len(data.v)))
        for w, e in zip(model.w, model.ex):
            z += w * e.lift(d)
        self.z = {k: z[i] for i, k in enumerate(rows_by_form)}

    def lifts(self, key):
        return self.z[key]


def pick_saved(p, z, ix, slots, form, gamma):
    """The bits the tilt saves at one census pick. An option of the form's own slot or of a slot outside the scope keeps lift 1."""
    s = 0.0
    den = 0.0
    lift_g = 1.0
    for name, code, w in p['rels']:
        k = name
        if code == 'd':
            m = re.match(r'&r(\d+)', name)
            o = slots.get(int(m.group(1))) if m else None
            k = o[1] if o and o[0] < form else None
        j = ix.get(k)
        l = math.exp(gamma * z[j]) if j is not None else 1.0
        s += w
        den += w * l
        if name == p['gold']:
            lift_g = l
    den = (den + max(p['sum'] - s, 0.0)) / p['sum']
    return math.log2(lift_g) - math.log2(den)


def setup(split):
    frozen = json.load(open(F.R + 'frozen.json'))
    for p in sorted(os.listdir(F.R)):
        if p.startswith('gamma-'):
            frozen.setdefault('gamma', {}).update(json.load(open(F.R + p)))
    return frozen


def census_rows():
    census = {}
    for x in open(C):
        r = json.loads(x)
        census[r['task'], r['form']] = r
    return census


def summarize(saved, per, ok):
    """saved: {form key: bits saved}. The mean per form, on all forms with bits and on forms at 25 bits or more, of the kinds that the target covers."""
    a = [(k[0], v) for k, v in saved.items() if ok(k)]
    b = [(k[0], v) for k, v in saved.items() if ok(k) and per[k]['bits'] >= 25]
    return dict(all=boot(a, None), at25=boot(b, None))


def base_per(rows, census):
    return {(r['task'], r['form']): dict(task=r['task'], form=r['form'], kind=r['kind'], bits=(census.get((r['task'], r['form'])) or {}).get('bits'), source=r['source']) for r in rows}


def read_part(split, part):
    t00 = time.time()
    if split == 'held' and os.path.exists(F.R + 'read-held-%s.json' % part):
        sys.exit('read-held-%s.json exists: this held read is done' % part)
    frozen = setup(split)
    tf = F.load('fit')
    fit = F.attach_open(F.rows_of(tf), tf)
    ts = F.load(split)
    rows = F.attach_open(F.rows_of(ts), ts)
    census = census_rows()
    per = base_per(rows, census)
    ok = lambda k: per[k]['bits'] is not None  # noqa: E731
    out = dict(split=split, part=part, targets={})
    reads = 0
    names = PARTS[part]
    for name in names:
        if name not in TARGETS:
            continue
        col, kinds, minn = TARGETS[name]
        a = F.categorical(fit, col, kinds)
        b = F.categorical(rows, col, kinds)
        V = M.vocab_of(a, minn)
        kk = sorted({r['kind'] for r in a})
        da, db = M.Data(a, V, kk), M.Data(b, V, kk)
        res = dict(vocab=len(V), forms=len(b), other_share=round(float((db.y == len(V) - 1).mean()), 3), tiers={})
        for tier in TIERS:
            keys = [tuple(k) for k in frozen['keys'][name][tier]]
            m = M.Model(da, keys)
            mb, mm, rk = m.read(db)
            reads += 1
            sv = {(r['task'], r['form']): float(x - y) for r, x, y in zip(b, mb, mm)}
            d = dict(marginal=round(float(mb.mean()), 3), model=round(float(mm.mean()), 3), top1=round(float((rk == 0).mean()), 3), top5=round(float((rk < 5).mean()), 3), keys=['*'.join(k) for k in keys], w=[round(float(x), 3) for x in m.w])
            d['vs_marginal'] = summarize(sv, per, ok)
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
                d['vs_census'] = summarize(sc, per, ok)
                for k, v in sc.items():
                    per[k]['saved %s %s' % (name, tier)] = round(v, 3)
            for k, v in sv.items():
                per[k]['marg %s %s' % (name, tier)] = round(v, 3)
            res['tiers'][tier] = d
        keys = [tuple(k) for k in frozen['keys'][name]['need+foundset']]
        ctl = M.Model(M.Data(shuffled(a), V, kk), keys)
        cb, cm, _ = ctl.read(db)
        reads += 1
        res['control'] = summarize({(r['task'], r['form']): float(x - y) for r, x, y in zip(b, mb, cm)}, per, ok)
        out['targets'][name] = res
        print(name, json.dumps({t: (res['tiers'][t]['marginal'], res['tiers'][t]['model'], res['tiers'][t].get('census_paid'), res['tiers'][t]['vs_marginal']['at25']) for t in TIERS}), 'control', res['control'], round(time.time() - t00), flush=True)
    gammas = dict(frozen.get('gamma', {}))
    for name in names:
        if name not in BAGS:
            continue
        kinds = BAGS[name]
        walks = load_walks(split)
        a = F.bag(fit, kinds)
        b = F.bag(rows, kinds)
        V = M.vocab_of(a, 8)
        kk = sorted({r['kind'] for r in a})
        da, db = M.Data(a, V, kk, mask_of(a, V)), M.Data(b, V, kk, mask_of(b, V))
        nf = sum(1 for r in rows if r['kind'] in kinds)
        res = dict(vocab=len(V), reads=len(b), forms=nf, tiers={})
        forms = {(r['task'], r['form']): r for r in rows if r['kind'] in kinds}
        ix = {t: i for i, t in enumerate(V)}
        slots = {t: slot_keys(ts[t]) for t in ts}
        models = [(tier, M.Model(da, [tuple(k) for k in frozen['keys'][name][tier]])) for tier in TIERS]
        ctl_keys = [tuple(k) for k in frozen['keys'][name]['need+foundset']]
        models.append(('control', M.Model(M.Data(shuffled(a), V, kk, mask_of(a, V)), ctl_keys)))
        for tier, m in models:
            mb, mm, rk = m.read(db)
            reads += 1
            sv = {k: 0.0 for k in forms}
            for r, x, y in zip(b, mb, mm):
                sv[r['task'], r['form']] += float(x - y)
            tl = Tilt(m, da, forms)
            d = dict(marginal_per_read=round(float(mb.mean()), 3), model_per_read=round(float(mm.mean()), 3), top1=round(float((rk == 0).mean()), 3), top5=round(float((rk < 5).mean()), 3), keys=['*'.join(k) for k in m.keys], w=[round(float(x), 3) for x in m.w])
            d['bag_vs_marginal'] = summarize(sv, per, ok)
            base_tier = 'need+foundset' if tier == 'control' else tier
            if split == 'dev':
                best, bg = -1e9, 0
                for g in GAMMAS:
                    x = [sum(pick_saved(p, tl.lifts(k), ix, slots[k[0]], k[1], g) for p in walks[k]['picks']) for k in forms if k in walks and ok(k)]
                    v = float(np.mean(x))
                    if v > best:
                        best, bg = v, g
                if tier != 'control':
                    gammas[name + '|' + tier] = bg
                d['gamma_curve_best'] = round(best, 3)
            g = gammas[name + '|' + base_tier]
            d['gamma'] = g
            sp = {k: sum(pick_saved(p, tl.lifts(k), ix, slots[k[0]], k[1], g) for p in walks[k]['picks']) for k in forms if k in walks and not walks[k].get('error')}
            d['tilt_vs_census'] = summarize(sp, per, ok)
            d['paid_rel_picks'] = round(float(np.mean([sum(p['q_bits'] for p in walks[k]['picks']) for k in sp if ok(k)])), 3)
            for k, v in sp.items():
                per[k]['tilt ' + tier] = round(v, 3)
            for k, v in sv.items():
                per[k]['bag ' + tier] = round(v, 3)
            res['tiers'][tier] = d
        out['targets'][name] = res
        print(name, json.dumps({t: (res['tiers'][t]['bag_vs_marginal']['at25'], res['tiers'][t]['tilt_vs_census']['at25'], res['tiers'][t]['gamma']) for t in res['tiers']}), round(time.time() - t00), flush=True)
    out['model_reads'] = reads
    if split == 'dev':
        json.dump({k: v for k, v in gammas.items() if any(k.startswith(x) for x in names)}, open(F.R + 'gamma-%s.json' % part, 'w'), indent=1)
    with open(F.R + 'per-form-%s-%s.jsonl' % (split, part), 'w') as f:
        for k in sorted(per):
            f.write(json.dumps(per[k], separators=(',', ':')) + '\n')
    json.dump(out, open(F.R + 'read-%s-%s.json' % (split, part), 'w'), indent=1)
    print('part', part, 'reads', reads, 'seconds', round(time.time() - t00), flush=True)


def merge(split):
    """The sums of the census unit, read from the parts."""
    per = {}
    out = dict(split=split, targets={})
    reads = 0
    for part in PARTS:
        with open(F.R + 'per-form-%s-%s.jsonl' % (split, part)) as f:
            for x in f:
                r = json.loads(x)
                per.setdefault((r['task'], r['form']), {}).update(r)
        d = json.load(open(F.R + 'read-%s-%s.json' % (split, part)))
        out['targets'].update(d['targets'])
        reads += d['model_reads']
    ok = lambda k: per[k]['bits'] is not None  # noqa: E731
    out.update(forms=len(per), tasks=len({k[0] for k in per}), forms_with_bits=sum(ok(k) for k in per), forms_25=sum(1 for k in per if ok(k) and per[k]['bits'] >= 25), model_reads=reads)
    joint = {}
    for tier in TIERS:
        sv, sv_tilt = {}, {}
        for k, p in per.items():
            if not ok(k):
                continue
            x = p.get('tilt ' + tier, 0.0)
            sv_tilt[k] = x
            if p['kind'] == 'INIT':
                x += p.get('saved comp INIT ' + tier, 0.0)
            elif p['kind'] == 'DET':
                x += p.get('saved comp DET ' + tier, 0.0)
            sv[k] = x
            p['t1 ' + tier] = round(x, 3)
        over = [k for k in sv if per[k]['bits'] >= 25]
        under = [k for k in over if per[k]['bits'] - sv[k] < 25]
        bytask = {}
        for k in sv:
            bytask.setdefault(k[0], []).append(k)
        before = sum(all(per[k]['bits'] < 25 for k in v) for v in bytask.values())
        after = sum(all(per[k]['bits'] - sv[k] < 25 for k in v) for v in bytask.values())
        joint[tier] = dict(saved=summarize(sv, per, ok), tilt_only=summarize(sv_tilt, per, ok), forms_over=len(over), forms_taken_under=len(under), tasks_under_before=before, tasks_under_after=after, tasks=len(bytask))
    joint['control_tilt'] = summarize({k: p.get('tilt control', 0.0) for k, p in per.items() if ok(k)}, per, ok)
    out['t1_census_unit'] = joint
    shares = {}
    a, b, n = (joint[t]['saved']['at25'][0] for t in ('need+foundset', 'foundset', 'need'))
    shares['t1 census unit'] = dict(need_and_found=a, found=b, need=n, share_need_added=round((a - b) / a, 3) if a else None)
    t = out['targets']['content']['tiers']
    a, b, n = (t[x]['vs_marginal']['at25'][0] for x in ('need+foundset', 'foundset', 'need'))
    shares['content'] = dict(need_and_found=a, found=b, need=n, share_need_added=round((a - b) / a, 3) if a else None)
    out['shares'] = shares
    ts = F.load(split)
    tn = [r['t_need'] for f in ts.values() for r in f]
    tt = [r.get('t_table', 0.0) for f in ts.values() for r in f]
    t0 = time.perf_counter()
    rows = F.attach_open(F.rows_of(ts), ts)
    t_fact = (time.perf_counter() - t0) / max(len(rows), 1)
    out['cost'] = dict(need_ms_median=round(float(np.median(tn)) * 1000, 3), need_ms_max=round(float(np.max(tn)) * 1000, 3), table_facts_ms_median=round(float(np.median(tt)) * 1000, 3), table_facts_ms_max=round(float(np.max(tt)) * 1000, 3), bucket_ms_mean=round(t_fact * 1000, 3))
    out['by_source'] = {}
    for s in sorted({p['source'] for p in per.values()}):
        x = [(k[0], p['t1 need+foundset']) for k, p in per.items() if p['source'] == s and 't1 need+foundset' in p and p['bits'] >= 25]
        out['by_source'][s] = boot(x, None)
    with open(F.R + 'per-form-%s.jsonl' % split, 'w') as f:
        for k in sorted(per):
            f.write(json.dumps(per[k], separators=(',', ':')) + '\n')
    json.dump(out, open(F.R + 'read-%s.json' % split, 'w'), indent=1)
    print(json.dumps(out['t1_census_unit'], indent=0)[:3000])
    print(json.dumps(out['shares']), json.dumps(out['cost']), json.dumps(out['by_source']), 'reads', reads)


if __name__ == '__main__':
    if sys.argv[2] == 'merge':
        merge(sys.argv[1])
    else:
        read_part(sys.argv[1], sys.argv[2])
