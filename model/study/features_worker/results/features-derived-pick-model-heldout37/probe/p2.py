"""Probe 2: pick rows from or_q.walk (summed over orders) of mapped N600 pairs from probe/p1.jsonl, as the training job would make them.

    bash ../../features-scope-loss-c-read-heldout37-ramp22/env.sh ../features-derived-pick-model-heldout37/probe/p2.py BUDGET [MAXPAIRS_PER_FORM] [n600|c120]
At each atom start (phases root and root2) of each order walk it logs: the order index, phase, place, the head kind, the relation tokens drawn so far
(a set, from p_key), the label types in scope (p_scope, a set), and per option its class, its scope relation (text head, j), the weight before the
steer (ws), the steer factor (rf) and whether gold takes it. One JSON line per pair to probe/p2.jsonl, with each order's bits.
"""
import collections
import json
import os
import sys
import time

sys.path.insert(0, '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37/probe')
T0 = time.time()
import common as C  # noqa: E402

budget = float(sys.argv[1])
per_form = int(sys.argv[2]) if len(sys.argv) > 2 else 2
SRC = sys.argv[3] if len(sys.argv) > 3 else 'n600'
SUF = '' if SRC == 'n600' else '-' + SRC
CTX = C.NCtx if SRC == 'n600' else C.CCtx
or_q, S, M = C.or_q, C.S, C.S.M
CAP = dict(log=None, order=-1, kinds=collections.Counter())

_drawer = or_q.GuidedRun.drawer


def drawer(self, pg, kind, dec, place=None, prior=None):
    dr = _drawer(self, pg, kind, dec, place, prior)
    dr._pg, dr._kind = pg, kind
    return dr


or_q.GuidedRun.drawer = drawer
_rf = S.Drawer.rel_factors


def rel_factors(self, fr, n, popts, k, scope_types, key, rel, joined, leaf):
    got = _rf(self, fr, n, popts, k, scope_types, key, rel, joined, leaf)
    self._rf_got = list(got)
    return got


S.Drawer.rel_factors = rel_factors
_pc = or_q.GuidedDrawer.pick_complete


def base_of(dr, t):
    name = dr.V.name(t)
    nm = dr.prog_names.get(name, name)
    h, _, sub = nm.partition('.')
    pg = getattr(dr, '_pg', None)
    head = pg.written.get(h, h) if pg is not None else h
    return [head, int(sub) if sub.isdigit() else (sub or None)]


def pick_complete(self, n, opts, weights, key, alt=None):
    rf = getattr(self, '_rf_got', None)
    self._rf_got = None
    o, q = _pc(self, n, opts, weights, key, alt)
    if n.phase in ('root', 'root2') and CAP['log'] is not None:
        rows = []
        for i, t in enumerate(opts):
            kd = self.fr.KIND[t]
            cls = 'op' if (t == M.NOT or t in M.CMP) else 'derived' if kd == 'relation' else 'lib'
            if kd == 'relation':
                CAP['kinds'][self.rel_name(t)] += 1
            rows.append(dict(tok=self.V.name(t), cls=cls, base=base_of(self, t) if cls == 'derived' else None, w=weights[i],
                             rf=(rf[i] if rf and len(rf) == len(opts) else None), gold=t == o))
        drawn = sorted({self.V.name(t) for t in self.p_key if (self.V.name(t) or '').startswith(('&r', '&f')) or (t in self.fr.KIND and self.fr.KIND[t] is not None and not str(self.V.name(t)).startswith((':', '*', '^')))})
        CAP['log'].append(dict(order=CAP['order'], phase=n.phase, place=getattr(self, 'place', None), kind=getattr(self, '_kind', None), rel_off=bool(self.rel_off),
                               steered=rf is not None, drawn=drawn, scope_types=sorted({str(x) for x in self.p_scope}), opts=rows))
    return o, q


or_q.GuidedDrawer.pick_complete = pick_complete
_wo = or_q.walk_order


def walk_order(*a, **k):
    CAP['order'] += 1
    rec = _wo(*a, **k)
    CAP.setdefault('bits', []).append(sum(rec['parts'].values()) if not (rec['bad'] or rec['dead'] or rec['left']) else None)
    return rec


or_q.walk_order = walk_order

OUT = C.HERE + '/probe/p2%s.jsonl' % SUF
done = {(json.loads(l)['task'], json.loads(l)['si'], json.loads(l)['g']) for l in open(OUT)} if os.path.exists(OUT) else set()
p1 = [json.loads(l) for l in open(C.HERE + '/probe/p1%s.jsonl' % SUF)]
todo = []
for r in p1:
    seen = collections.Counter()
    for si, g, kind, vkind, sn, st, target in r['pair_rows']:
        if st == 'mapped' and seen[g] < per_form:
            seen[g] += 1
            todo.append((r['task'], si, g, kind, target))
ctx = {}
n = 0
for task, si, g, kind, target in todo:
    if (task, si, g) in done:
        continue
    if time.time() - T0 > budget:
        break
    if task not in ctx:
        ctx.clear()
        c = CTX(task)
        ctx[task] = (c, C.D.session_of(task))
    c, (sess, d, _) = ctx[task]
    sc = c.scopes[si]
    srel = C.relations(sc['texts'], sess, d)
    CAP.update(log=[], order=-1, bits=[])
    t1 = time.time()
    rec = or_q.walk(C.ns['sampler'], task, 'n600', [g, 0], list(sc['texts']), target, sess, d, kind)
    picks = CAP['log']
    CAP['log'] = None
    rels = {'%s|%s' % k: dict(key=str(v['key']), labels=v['labels'], types=[s[0] for s in v['sigs']]) for k, v in srel.items()}
    out = dict(task=task, si=si, g=g, kind=kind, fids=sc['fids'], target=target, total=rec.get('total'), orders=(rec.get('orders') or {}).get('orders'),
               exact=(rec.get('orders') or {}).get('exact'), valid=not (rec.get('bad') or rec.get('dead') or rec.get('left')), order_bits=CAP['bits'], wall=round(time.time() - t1, 2), rels=rels, picks=picks)
    with open(OUT, 'a') as f:
        f.write(json.dumps(out, default=str) + '\n')
    n += 1
    print(task, si, g, kind, 'total', rec.get('total'), 'orders', out['orders'], 'picks', len(picks), '%.2fs' % out['wall'], flush=True)
print('pairs %d, rel_name of KIND relation options: %s, wall %.1fs' % (n, dict(CAP['kinds']), time.time() - T0))
