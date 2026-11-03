"""The read of the frozen models on one split.

  gold_tables_env.sh 1 final_read.py dev PART [STEERS]     tune read of one part: writes tilt weights to gamma-STEERS-PART.json
  gold_tables_env.sh 1 final_read.py held PART [STEERS]    the held read of one part. It refuses to run a second time while read-held-STEERS-PART.json exists or held-reads.jsonl of the record has a line of that name.
  gold_tables_env.sh 1 final_read.py SPLIT merge [STEERS]  joins the parts: the sums on one walk, the shares, the cost, the counts under 25 bits.

STEERS is `off` (the offset a model reads) or `live` (the comparator); the default is `live`.

Every model is fit on fit tasks only, with the situation keys in frozen.json. A state is a set S of found forms, the `cut` of a target form for a seed; a target form has one state per seed, and a number per form is the mean over its seeds. Bits are per form.
The bits of a form are the mean over its valid orders of the walk total, from the `cut` parts of the walks of the record (walks/dev-cut-*, walks/held-cut-*), where the form's scope is the state's scope. A form's 25-bit cut reads the bits under `live`. Pick rows are read for their options, weights, gold option and q_bits alone: no read takes `under`, `form_atoms`, `nsize`, `form_not` or `form_or`.
Numbers go to read-<split>-<steers>-<part>.json, read-<split>-<steers>.json and per-form-<split>-<steers>.jsonl.

Saved bits on a target:
  comp INIT, comp DET: the walk's paid part minus model bits.
  reads tilt: at each relation pick of the walk, each option's weight is multiplied by its lift (the model's rate over the kind's rate) to the power gamma, then normalized. Saved is the sum over the form's picks. It is an exact change of the walk's bits. A derived option is `D:<content key of a form of S>[.port]`, and its lift is that of the derived key of that form.
  the rest: bits under the target's marginal on fit tasks, in the kind, minus bits under the model.
"""
import collections
import glob
import io
import json
import math
import os
import random
import re
import sys
import time

import numpy as np
import zstandard

import next_form_facts as F
import next_form_model as M

RECORD = F.R.rsplit('/next/', 1)[0] + '/'
WALKS = RECORD + 'walks/'
LEDGER = RECORD + 'held-reads.jsonl'
RELKINDS = ('lib relation', 'relation macro', 'fact relation', 'relation')
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
TIERS = ('need', 'foundset', 'need+foundset')
GAMMAS = (0, .1, .2, .3, .4, .5, .6, .8, 1.0)
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


def stream(path):
    with open(path, 'rb') as f:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f), encoding='utf-8'):
            if line.strip():
                yield json.loads(line)


def read_walks(split, steers, picks=True):
    """{(task, form, scope_id): dict(totals, parts, picks)} from the `cut` part of the walks. A walk counts when its form line has ok; its pick rows are kept as (opts, gold_idx, q_bits) of the phases root and root2, and nothing else of a pick row."""
    part = 'held-cut' if split == 'held' else 'dev-cut'
    got = {}
    pend = collections.defaultdict(list)
    for p in sorted(glob.glob(WALKS + '%s-%s-*.jsonl.zst' % (part, steers))):
        for r in stream(p):
            if r['rec'] == 'pick':
                if picks:
                    pend[r['task'], r['form'], r['scope_id'], r['order_id']].append((r['opts'], r['gold_idx'], r['q_bits']))
            elif r['rec'] == 'form' and r.get('ok') and r.get('total') is not None:
                g = got.setdefault((r['task'], r['form'], r['scope_id']), dict(totals=[], parts=[], picks=[]))
                g['totals'].append(r['total'])
                g['parts'].append(r.get('parts') or {})
                g['picks'].append(pend.pop((r['task'], r['form'], r['scope_id'], r['order_id']), []))
    return got


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def form_means(rows, values):
    """{(task, form): mean over the rows of the form, its seeds, of the values}"""
    acc = collections.defaultdict(list)
    for r, v in zip(rows, values):
        if v is not None:
            acc[r['task'], r['form']].append(v)
    return {k: sum(v) / len(v) for k, v in acc.items()}


def skey(r):
    return r['task'], r['form'], r['seed']


class Tilt:
    """Lifts of a read model, per state."""

    def __init__(self, model, data, rows_by_state):
        self.model = model
        self.v = {t: i for i, t in enumerate(data.v)}
        keys = list(rows_by_state)
        d = M.Data([dict(rows_by_state[k], y='<other>') for k in keys], data.v, data.kinds)
        z = np.zeros((len(keys), len(data.v)))
        for w, e in zip(model.w, model.ex):
            z += w * e.lift(d)
        self.z = {k: z[i] for i, k in enumerate(keys)}

    def lifts(self, key):
        return self.z[key]


def owner_fn(ts, r):
    """name -> the derived key of a derived option `D:<content key of a form of the state's set>[.port]`; None for another name."""
    d = ts[r['task']]
    by_content = {}
    for k in d['states'][r['key'], r['seed']]['scope']:
        by_content.setdefault(d['forms'][k]['form'], d['forms'][k])

    def f(name):
        m = re.match(r'D:([0-9a-f]+)(?:\.(\d+))?$', name)
        o = by_content.get(m.group(1)) if m else None
        return F.key_of(o, int(m.group(2) or 0)) if o else None
    return f


def pick_saved(p, z, ix, owner, gamma):
    """The bits the tilt saves at one pick of the walk. An option that is not a relation, and a derived option outside the set, keep lift 1."""
    opts, gi, _ = p
    tot = sum(o[2] for o in opts)
    s = den = 0.0
    lift_g = 1.0
    for n, (name, kind, w, *_) in enumerate(opts):
        if kind not in RELKINDS:
            continue
        k = owner(name) if kind == 'relation' else name
        j = ix.get(k)
        l = math.exp(gamma * z[j]) if j is not None else 1.0
        s += w
        den += w * l
        if n == gi:
            lift_g = l
    den = (den + max(tot - s, 0.0)) / tot
    return math.log2(lift_g) - math.log2(den)


def state_saved(g, z, ix, owner, gamma):
    """The mean over the valid orders of a state of the bits that the tilt saves on the walk."""
    return mean(sum(pick_saved(p, z, ix, owner, gamma) for p in order) for order in g['picks']) if g and g['picks'] else None


def setup(split, steers):
    frozen = json.load(open(F.R + 'frozen.json'))
    for p in sorted(os.listdir(F.R)):
        if p.startswith('gamma-%s-' % steers):
            frozen.setdefault('gamma', {}).update(json.load(open(F.R + p)))
    return frozen


def summarize(saved, per, ok):
    """saved: {form key: bits saved}. The mean per form, on all forms with bits and on forms at 25 bits or more, of the kinds that the target covers."""
    a = [(k[0], v) for k, v in saved.items() if ok(k)]
    b = [(k[0], v) for k, v in saved.items() if ok(k) and per[k]['bits'] >= 25]
    return dict(all=boot(a, None), at25=boot(b, None))


def base_per(rows, live):
    """Per form (task, form): its kind, source, and the mean over its seeds of the mean over valid orders of the `live` walk total."""
    bits = form_means(rows, [mean((live.get((r['task'], r['form'], r['scope_id'])) or {}).get('totals') or []) for r in rows])
    return {(r['task'], r['form']): dict(task=r['task'], form=r['form'], kind=r['kind'], bits=bits.get((r['task'], r['form'])), source=r['source']) for r in rows}


def paid(g, name):
    if not g or not g['parts']:
        return None
    if name == 'comp INIT':
        return mean(p.get('component', 0.0) for p in g['parts'])
    return mean(p.get('proposer', 0.0) + p.get('proposer or atoms', 0.0) for p in g['parts'])


def held_gate(split, steers, part):
    name = 'next-held-%s-%s' % (steers, part)
    if split != 'held':
        return
    if os.path.exists(F.R + 'read-held-%s-%s.json' % (steers, part)):
        sys.exit('read-held-%s-%s.json exists: this held read is done' % (steers, part))
    if os.path.exists(LEDGER) and any(json.loads(l).get('name') == name for l in open(LEDGER) if l.strip()):
        sys.exit('held-reads.jsonl has a line %s: this held read is done' % name)
    with open(LEDGER, 'a') as f:
        f.write(json.dumps(dict(name=name, group='next form', arm='frozen', tier='need+foundset', steers=steers, control=False, time=time.strftime('%Y-%m-%dT%H:%M:%S'))) + '\n')


def read_part(split, part, steers='live'):
    t00 = time.time()
    held_gate(split, steers, part)  # before a held row is loaded
    frozen = setup(split, steers)
    tf = F.load('fit')
    fit = F.rows_of(tf)
    ts = F.load(split)
    rows = F.rows_of(ts)
    names = PARTS[part]
    live = read_walks(split, 'live', picks=False)
    walks = read_walks(split, steers, picks=any(n in BAGS for n in names)) if steers != 'live' else None
    if walks is None and any(n in BAGS for n in names):
        walks = read_walks(split, 'live', picks=True)
    elif walks is None:
        walks = live
    per = base_per(rows, live)
    ok = lambda k: per[k]['bits'] is not None  # noqa: E731
    out = dict(split=split, part=part, steers=steers, targets={})
    reads = 0
    for name in names:
        if name not in TARGETS:
            continue
        col, kinds, minn = TARGETS[name]
        a = F.categorical(fit, col, kinds)
        b = F.categorical(rows, col, kinds)
        V = M.vocab_of(a, minn)
        kk = sorted({r['kind'] for r in a})
        da, db = M.Data(a, V, kk), M.Data(b, V, kk)
        res = dict(vocab=len(V), forms=len({(r['task'], r['form']) for r in b}), states=len(b), other_share=round(float((db.y == len(V) - 1).mean()), 3), tiers={})
        for tier in TIERS:
            keys = [tuple(k) for k in frozen['keys'][name][tier]]
            m = M.Model(da, keys)
            mb, mm, rk = m.read(db)
            reads += 1
            sv = form_means(b, [float(x - y) for x, y in zip(mb, mm)])
            d = dict(marginal=round(float(mb.mean()), 3), model=round(float(mm.mean()), 3), top1=round(float((rk == 0).mean()), 3), top5=round(float((rk < 5).mean()), 3), keys=['*'.join(k) for k in keys], w=[round(float(x), 3) for x in m.w])
            d['vs_marginal'] = summarize(sv, per, ok)
            if name in ('comp INIT', 'comp DET'):
                pd = [paid(walks.get((r['task'], r['form'], r['scope_id'])), name) for r in b]
                sc = form_means(b, [None if x is None else x - float(y) for x, y in zip(pd, mm)])
                pf = form_means(b, pd)
                for k, v in pf.items():
                    per[k]['paid ' + name] = round(v, 3)
                d['census_paid'] = round(float(np.mean(list(pf.values()))), 3)
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
        res['control'] = summarize(form_means(b, [float(x - y) for x, y in zip(mb, cm)]), per, ok)
        out['targets'][name] = res
        print(name, json.dumps({t: (res['tiers'][t]['marginal'], res['tiers'][t]['model'], res['tiers'][t].get('census_paid'), res['tiers'][t]['vs_marginal']['at25']) for t in TIERS}), 'control', res['control'], round(time.time() - t00), flush=True)
    gammas = dict(frozen.get('gamma', {}))
    for name in names:
        if name not in BAGS:
            continue
        kinds = BAGS[name]
        a = F.bag(fit, kinds)
        b = F.bag(rows, kinds)
        V = M.vocab_of(a, 8)
        kk = sorted({r['kind'] for r in a})
        da, db = M.Data(a, V, kk, mask_of(a, V)), M.Data(b, V, kk, mask_of(b, V))
        states = [r for r in rows if r['kind'] in kinds]
        nf = len({(r['task'], r['form']) for r in states})
        res = dict(vocab=len(V), reads=len(b), forms=nf, states=len(states), tiers={})
        by_state = {skey(r): r for r in states}
        ix = {t: i for i, t in enumerate(V)}
        owners = {skey(r): owner_fn(ts, r) for r in states}
        models = [(tier, M.Model(da, [tuple(k) for k in frozen['keys'][name][tier]])) for tier in TIERS]
        ctl_keys = [tuple(k) for k in frozen['keys'][name]['need+foundset']]
        models.append(('control', M.Model(M.Data(shuffled(a), V, kk, mask_of(a, V)), ctl_keys)))
        for tier, m in models:
            mb, mm, rk = m.read(db)
            reads += 1
            sst = collections.defaultdict(float)
            for r, x, y in zip(b, mb, mm):
                sst[skey(r)] += float(x - y)
            sv = form_means(states, [sst.get(skey(r), 0.0) for r in states])
            tl = Tilt(m, da, by_state)
            d = dict(marginal_per_read=round(float(mb.mean()), 3), model_per_read=round(float(mm.mean()), 3), top1=round(float((rk == 0).mean()), 3), top5=round(float((rk < 5).mean()), 3), keys=['*'.join(k) for k in m.keys], w=[round(float(x), 3) for x in m.w])
            d['bag_vs_marginal'] = summarize(sv, per, ok)
            base_tier = 'need+foundset' if tier == 'control' else tier
            if split == 'dev':
                best, bg = -1e9, 0
                for g in GAMMAS:
                    x = [v for v in form_means(states, [state_saved(walks.get((r['task'], r['form'], r['scope_id'])), tl.lifts(skey(r)), ix, owners[skey(r)], g) for r in states]).values()]
                    v = float(np.mean(x))
                    if v > best:
                        best, bg = v, g
                if tier != 'control':
                    gammas[name + '|' + tier] = bg
                d['gamma_curve_best'] = round(best, 3)
            g = gammas[name + '|' + base_tier]
            d['gamma'] = g
            sp = form_means(states, [state_saved(walks.get((r['task'], r['form'], r['scope_id'])), tl.lifts(skey(r)), ix, owners[skey(r)], g) for r in states])
            d['tilt_vs_census'] = summarize(sp, per, ok)
            pq = form_means(states, [mean(sum(p[2] for p in order) for order in (walks.get((r['task'], r['form'], r['scope_id'])) or {'picks': []})['picks']) if (walks.get((r['task'], r['form'], r['scope_id'])) or {}).get('picks') else None for r in states])
            d['paid_rel_picks'] = round(float(np.mean([v for k, v in pq.items() if ok(k)])), 3)
            for k, v in sp.items():
                per[k]['tilt ' + tier] = round(v, 3)
            for k, v in sv.items():
                per[k]['bag ' + tier] = round(v, 3)
            res['tiers'][tier] = d
        out['targets'][name] = res
        print(name, json.dumps({t: (res['tiers'][t]['bag_vs_marginal']['at25'], res['tiers'][t]['tilt_vs_census']['at25'], res['tiers'][t]['gamma']) for t in res['tiers']}), round(time.time() - t00), flush=True)
    out['model_reads'] = reads
    if split == 'dev':
        json.dump({k: v for k, v in gammas.items() if any(k.startswith(x) for x in names)}, open(F.R + 'gamma-%s-%s.json' % (steers, part), 'w'), indent=1)
    with open(F.R + 'per-form-%s-%s-%s.jsonl' % (split, steers, part), 'w') as f:
        for k in sorted(per):
            f.write(json.dumps(per[k], separators=(',', ':')) + '\n')
    json.dump(out, open(F.R + 'read-%s-%s-%s.json' % (split, steers, part), 'w'), indent=1)
    print('part', part, 'reads', reads, 'seconds', round(time.time() - t00), flush=True)


def merge(split, steers='live'):
    """The sums of the census unit, read from the parts."""
    per = {}
    out = dict(split=split, steers=steers, targets={})
    reads = 0
    for part in PARTS:
        with open(F.R + 'per-form-%s-%s-%s.jsonl' % (split, steers, part)) as f:
            for x in f:
                r = json.loads(x)
                per.setdefault((r['task'], r['form']), {}).update(r)
        d = json.load(open(F.R + 'read-%s-%s-%s.json' % (split, steers, part)))
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
    tn = [st['t_need'] for d in ts.values() for st in d['states'].values()]
    tt = [r.get('t_table', 0.0) for d in ts.values() for r in d['forms'].values()]
    t0 = time.perf_counter()
    rows = F.rows_of(ts)
    t_fact = (time.perf_counter() - t0) / max(len(rows), 1)
    out['cost'] = dict(need_ms_median=round(float(np.median(tn)) * 1000, 3), need_ms_max=round(float(np.max(tn)) * 1000, 3), table_facts_ms_median=round(float(np.median(tt)) * 1000, 3), table_facts_ms_max=round(float(np.max(tt)) * 1000, 3), bucket_ms_mean=round(t_fact * 1000, 3))
    out['by_source'] = {}
    for s in sorted({p['source'] for p in per.values()}):
        x = [(k[0], p['t1 need+foundset']) for k, p in per.items() if p['source'] == s and 't1 need+foundset' in p and p['bits'] >= 25]
        out['by_source'][s] = boot(x, None)
    with open(F.R + 'per-form-%s-%s.jsonl' % (split, steers), 'w') as f:
        for k in sorted(per):
            f.write(json.dumps(per[k], separators=(',', ':')) + '\n')
    json.dump(out, open(F.R + 'read-%s-%s.json' % (split, steers), 'w'), indent=1)
    print(json.dumps(out['t1_census_unit'], indent=0)[:3000])
    print(json.dumps(out['shares']), json.dumps(out['cost']), json.dumps(out['by_source']), 'reads', reads)


if __name__ == '__main__':
    if sys.argv[2] == 'merge':
        merge(sys.argv[1], *sys.argv[3:4])
    else:
        read_part(sys.argv[1], sys.argv[2], *sys.argv[3:4])
