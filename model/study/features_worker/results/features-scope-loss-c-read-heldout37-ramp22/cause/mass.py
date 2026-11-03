"""Where the relation-pick mass goes, S against R, for the forms given.

    bash ../env.sh cause/mass.py ARM:TASK:G[,ARM:TASK:G...] [--budget S] [--all]

Reuses ../job.py (its code up to main) for the opening, the scope, the target and R's inputs. Walks the target as written (one order) with
or_q.walk_order over the recorded scope (S) and over gold's ancestors (R), and logs each atom-start pick (phases root and root2) of the walk:
each option's final weight (the steered q weight the pick reads), P's share and the relation steer's factor, the option's class (derived, lib, op)
and, for a derived option, its scope relation and whether its table equals a relation of one of gold's ancestors of g. The gold option's
relation-steer features are kept. One JSON line per form and walk to cause/mass.jsonl; forms already there are skipped.
"""
import collections
import json
import math
import os
import sys
import time

T0 = time.time()
REC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22'
argv = sys.argv[1:]
COV = '--covered' in argv
OUT = REC + ('/cause/mass-covered.jsonl' if COV else '/cause/mass.jsonl')
BUDGET = float(argv[argv.index('--budget') + 1]) if '--budget' in argv else None
WANT = argv[0]
src = open(REC + '/job.py').read()
src = src[:src.rindex('\nmain()')]
sys.argv = ['job.py'] + (['--covered'] if COV else [])
ns = dict(__name__='jobmod', __file__=REC + '/job.py')
exec(compile(src, REC + '/job.py', 'exec'), ns)
or_q, live, D = ns['or_q'], ns['live'], ns['D']
S = live.S
M = S.M
import relfeat  # noqa: E402

_rel = ns['relations']
MEMO = {}


def relations(texts, sess, d):
    k = tuple(texts)
    if k not in MEMO:
        MEMO[k] = _rel(texts, sess, d)
    return MEMO[k]


ns['relations'] = relations

CAP = dict(log=None, anc=None)
_drawer = or_q.GuidedRun.drawer


def drawer(self, pg, kind, dec, place=None, prior=None):
    dr = _drawer(self, pg, kind, dec, place, prior)
    dr._pg = pg
    return dr


or_q.GuidedRun.drawer = drawer
_rf = S.Drawer.rel_factors


def rel_factors(self, fr, n, popts, k, scope_types, key, rel, joined, leaf):
    got = _rf(self, fr, n, popts, k, scope_types, key, rel, joined, leaf)
    pre = None if self.rel_off else self.rel_prefix(fr, key, k)
    self._row = self.rel_row(fr, n, popts, k, scope_types, key, rel, joined, leaf, pre) if pre is not None else None
    self._rf_got = got
    return got


S.Drawer.rel_factors = rel_factors
_pc = or_q.GuidedDrawer.pick_complete


def cls_of(dr, t):
    if t == M.NOT or t in M.CMP:
        return 'op'
    return 'derived' if dr.fr.KIND[t] == 'relation' else 'lib'


def base_of(dr, t):
    name = dr.V.name(t)
    nm = dr.prog_names.get(name, name)
    h, _, sub = nm.partition('.')
    pg = getattr(dr, '_pg', None)
    head = pg.written.get(h, h) if pg is not None else h
    return head, (int(sub) if sub.isdigit() else (sub or None))


def pick_complete(self, n, opts, weights, key, alt=None):
    o, q = _pc(self, n, opts, weights, key, alt)
    if n.phase in ('root', 'root2') and CAP['log'] is not None:
        tot = sum(weights) or 1.0
        row = getattr(self, '_row', None) if n.phase in ('root', 'root2') else None
        rf = getattr(self, '_rf_got', None)
        pshare = {x['tok']: x['p'] for x in row['options']} if row else {}
        items = []
        for t, w in zip(opts, weights):
            c = cls_of(self, t)
            b = base_of(self, t) if c == 'derived' else None
            anc = CAP['anc'](b) if b is not None else None
            items.append(dict(tok=self.V.name(t), cls=c, base=list(b) if b else None, anc=anc, share=w / tot, p=pshare.get(self.V.name(t)),
                              f=(math.log(rf[opts.index(t)]) if rf and len(rf) == len(opts) else None), gold=t == o))
        feats = None
        if row:
            sc = S.rel_scorer()
            X, _ = sc.matrix(relfeat.mask_row(row, sc.mask))
            inv = {j: nm for nm, j in sc.col.items()}
            gi = [x['tok'] for x in row['options']].index(self.V.name(o)) if self.V.name(o) in [x['tok'] for x in row['options']] else None
            if gi is not None:
                feats = {inv[j]: round(float(v), 4) for j, v in enumerate(X[gi]) if v}
        CAP['log'].append(dict(phase=n.phase, k=self.p_k, ctx=self.rng.ctx, place=getattr(self, 'place', None), group=(getattr(self, 'rel_pg', None) or {}).get('point_group'),
                               rel_off=bool(getattr(self, 'rel_off', False)), tilt=bool(self.tilt), gold=self.V.name(o), gold_cls=cls_of(self, o), opts=items, gold_feats=feats))
    return o, q


or_q.GuidedDrawer.pick_complete = pick_complete


def anc_keys(c, g, sess, d):
    """The merge keys of the relations of gold's ancestors of g."""
    forms = live.S.strata.sexprs('\n'.join(c.lines))
    idx = set(live.S.ancestor_order(forms, g)) - {g}
    grel = relations(c.lines, sess, d)
    return {v['key'] for k, v in grel.items() if v['form'] in idx}, {v['key'] for k, v in grel.items() if v['form'] == g}


def one(item):
    arm, task, g = item[:3]
    row, x = ns['prepare'](item)
    if x is None or row['status'] != 'mapped':
        return [dict(arm=arm, task=task, g=g, status=row['status'])]
    c, sess, d = x['c'], x['sess'], x['d']
    akeys, _ = anc_keys(c, g, sess, d)
    srel = relations(x['scope'], sess, d)
    out = []
    for walk in ('S', 'R'):
        if walk == 'S':
            scope, target = x['scope'], x['target']
            CAP['anc'] = lambda b: (srel.get(tuple(b)) or {}).get('key') in akeys if tuple(b) in srel else None
        else:
            scope, target = ns['r_inputs'](c, g, sess)
            CAP['anc'] = lambda b: True
        CAP['log'] = []
        t1 = time.time()
        rec = or_q.walk_order(ns['sampler'], task, arm, [g, 0 if walk == 'S' else 1], scope, target, sess, x['d'], x['kind'])
        out.append(dict(arm=arm, task=task, g=g, walk=walk, status='mapped', kind=x['kind'], scope_n=len(scope), target=target, total=rec['total'], bad=rec['bad'], dead=rec['dead'],
                        left=rec['left'], atoms=rec['atoms'], parts=rec['parts'], picks=CAP['log'], wall=round(time.time() - t1, 2),
                        anc_rel_n=sum(1 for k, v in srel.items() if v['key'] in akeys) if walk == 'S' else None, scope_rel_n=len(srel) if walk == 'S' else None))
        CAP['log'] = None
    return out


def main():
    items = {(a, t, g): (a, t, g, s, f) for a, t, g, s, f in ns['build_items']()}
    if WANT == 'all':
        rows = [json.loads(l) for f in (('forms-covered.0of2.jsonl', 'forms-covered.1of2.jsonl') if COV else ('forms.0of2.jsonl', 'forms.1of2.jsonl')) for l in open('%s/%s' % (REC, f))]
        want = [(r['arm'], r['task'], r['g']) for r in rows if r['status'] == 'mapped' and r.get('S') and r['S']['valid'] and r['R']['valid']]
    else:
        want = [(x.split(':')[0], x.split(':')[1], int(x.split(':')[2])) for x in WANT.split(',')]
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            y = json.loads(l)
            done.add((y['arm'], y['task'], y['g']))
    todo = [k for k in want if k not in done]
    print('forms %d, done %d, todo %d' % (len(want), len(want) - len(todo), len(todo)), flush=True)
    n = 0
    for k in todo:
        if BUDGET is not None and time.time() - T0 > BUDGET:
            break
        t1 = time.time()
        try:
            recs = one(items[k])
        except Exception as e:  # noqa: BLE001
            recs = [dict(arm=k[0], task=k[1], g=k[2], status='error', error='%s: %s' % (type(e).__name__, str(e)[:300]))]
        with open(OUT, 'a') as fh:
            for r in recs:
                fh.write(json.dumps(r, default=str) + '\n')
        n += 1
        print('%s %s g%d %.1fs %s' % (k[0], k[1], k[2], time.time() - t1, [(r.get('walk'), r.get('total')) for r in recs]), flush=True)
    print('done %d todo %d, %.1fs since start' % (len(want) - len(todo) + n, len(todo) - n, time.time() - T0), flush=True)


main()
