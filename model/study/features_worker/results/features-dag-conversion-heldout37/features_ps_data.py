#!/usr/bin/env python
"""Arrays of the relation picks of walks over a points file, in the form of features_perrel_data.py: the same keys and facts, with the form of a scope slot read from the point's own scope.

  python features_ps_data.py [--crossfit] NAME POINTS WALK_FILE...     writes scratch/data-NAME.npz

A key and a fact read only what the search has at the pick. A pool form's head &fN reads as &r(1000000 + N), so the keys of features_perrel_keys.py apply to it. The slots of a form come from the walk's `decoded` list. `gold` holds gold's index for the fit and the tables alone.
"""
import collections
import glob
import json
import os
import re
import sys
import time

import numpy as np

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')
import features_perrel_data as PD  # noqa: E402
import features_perrel_keys as K  # noqa: E402
import features_rel_data as FD  # noqa: E402

OUT = PD.OUT
TYPES, COLS, FORM, ATOMH = PD.TYPES, PD.COLS, PD.FORM, PD.ATOMH
RN = re.compile(r'&f(\d+)')


def rn(x):
    return RN.sub(lambda m: '&r%d' % (1000000 + int(m[1])), x)


class PF(K.Forms):
    def __init__(self, scope, target, decoded):
        super().__init__([rn(x) for x in scope] + [rn(target)])
        self.decoded = decoded

    def slots(self, kept):
        out, ds = {}, self.decoded
        for i, s in enumerate(ds):
            for j in range(ds[i + 1] - s if i + 1 < len(ds) else 64):
                out[s + j] = (i, j)
        return out, 0


def main():
    swap = None
    if sys.argv[1] == '--crossfit':
        sys.argv.pop(1)
        swap = FD.Swap()
    name, points, paths = sys.argv[1], sys.argv[2], [x for p in sys.argv[3:] for x in sorted(glob.glob(p))]
    pts = {}
    for x in open(points):
        p = json.loads(x)
        pts[p['line']] = p
    keys = PD.Keys(K.lib_sections(), PD.registry_ports())
    fam, comp, rel, heads = PD.Vocab(), PD.Vocab(), PD.Vocab(), PD.Vocab()
    S, Co, X, starts, gold, fi, ci, ri, last = [], [], [], [0], [], [], [], [], []
    ph_p, ph_k, sc_p, sc_k, scnt = [], [], [], [], []
    meta = {k: [] for k in ('task', 'line', 'ord', 'phase', 'k', 'gold_kind', 'own', 'gold_dead', 'q_bits', 'orf', 'nopts', 'where')}
    forms, buf = [], []
    gold_is_scope = collections.Counter()
    t0 = time.time()
    for d in FD.records(paths):
        if d['rec'] != 'form':
            buf.append(d)
            continue
        forms.append({k: d[k] for k in ('task', 'line', 'natoms', 'total', 'bad', 'dead', 'error', 'cpu', 'content_cpu', 'picks', 'aligned', 'orf')})
        if d['error'] or d['dead'] or d['bad'] or not d['aligned']:  # a valid form, as the census counts one
            buf = []
            continue
        pt = pts[d['line']]
        f = PF(pt['scope'], pt['target'], d['decoded'])
        kept = list(range(len(pt['scope'])))
        sl, _n = f.slots(kept)
        rd = collections.Counter()
        for L in kept:
            for h in set(ATOMH.findall(f.lines[L])):
                rd[keys.text_head(f, h)] += 1
        fl = [L for L in kept if L in f.num]
        order, nf, prevs = {L: i for i, L in enumerate(fl)}, len(fl), [f.key(L, 0, keys.ports)[1] for L in fl[-2:]]
        for p in buf:
            task = p['task']
            if swap is not None:
                swap.apply(p)
            a, b, tok, la = FD.matrix(p)
            n = len(a)
            pid = len(gold)
            S.append(a), Co.append(b), starts.append(starts[-1] + n)
            g = p['gold_idx']
            gold.append(-1 if g is None else g)
            seen = set()
            scope = p['scope']
            cnt = {t: scope.count(t) for t in set(scope)}
            x = np.full((n, COLS), -1.0, np.float32)
            x2 = np.full((n, len(FORM)), -1.0, np.float32)
            for j, (o, r) in enumerate(zip(p['opts'], p['rowopts'])):
                nm, kd = o[0], o[1]
                k3 = keys.derived(f, sl, nm) if kd == 'relation' else keys.lib(nm, kd)
                fi.append(fam(k3[0])), ci.append(comp(k3[1])), ri.append(rel(k3[2]))
                x2[j, 5] = rd.get(k3[2], 0)
                if kd == 'relation':
                    t_ = int(nm[2:])
                    if t_ in sl:
                        L = sl[t_][0]
                        back = nf - 1 - order[L]
                        tx = f.lines[L]
                        x2[j, :5] = back, back / max(nf - 1, 1), len(ATOMH.findall(tx)), '(NOT' in tx, '(OR' in tx
                    if k3[1] not in seen:
                        seen.add(k3[1])
                        sc_p.append(pid), sc_k.append(heads('scope:' + k3[1]))
                for c, t in enumerate((r.get('types') or [])[:COLS]):
                    x[j, c] = cnt.get(t, 0)
            X.append(np.hstack([x, x2]))
            for i_, h_ in enumerate(reversed(prevs)):
                sc_p.append(pid), sc_k.append(heads('prevform%d:%s' % (i_ + 1, h_)))
            for h_ in rd:
                sc_p.append(pid), sc_k.append(heads('scopereads:' + h_))
            hs = [keys.head(f, sl, a_) for a_ in p.get('prefix') or []]
            hs = [h for h in hs if h]
            for h in set(hs):
                ph_p.append(pid), ph_k.append(heads('prefix:' + h))
            last.append(heads('last:' + (hs[-1] if hs else 'none')))
            scnt.append([cnt.get(t, 0) for t in TYPES])
            for k, v in dict(task=task, line=p['line'], ord=p['ord'], phase=p['phase'], k=p['k'], gold_kind=p['gold_kind'], own=p['own'], gold_dead=bool(g is None or p['opts'][g][3]), q_bits=p['q_bits'], orf=p['orf'], nopts=n, where=p.get('where') or '').items():
                meta[k].append(v)
        buf = []
    np.savez(OUT + 'data-%s.npz' % name, S=np.vstack(S), C=np.vstack(Co).astype(np.float32), X=np.vstack(X), starts=np.array(starts), gold=np.array(gold), fam=np.array(fi, np.int32), comp=np.array(ci, np.int32), rel=np.array(ri, np.int32), last=np.array(last, np.int32),
             ph_p=np.array(ph_p, np.int32), ph_k=np.array(ph_k, np.int32), sc_p=np.array(sc_p, np.int32), sc_k=np.array(sc_k, np.int32), scnt=np.array(scnt, np.float32),
             v_fam=np.array(fam.list()), v_comp=np.array(comp.list()), v_rel=np.array(rel.list()), v_heads=np.array(heads.list()), forms=np.array(json.dumps(forms)), **{'m_' + k: np.array(v) for k, v in meta.items()})
    print(name, len(gold), 'picks', starts[-1], 'option rows', len(forms), 'forms, %.0fs' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
