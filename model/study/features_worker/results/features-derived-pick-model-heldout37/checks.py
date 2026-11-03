"""Checks 6 and 8 of design.md on training pairs.

    bash REC/env.sh ../features-derived-pick-model-heldout37/checks.py --rows rows/c120.0of4.jsonl [--pairs 20] [--parity 10] [--src c120|n600] [--out FILE]

Takes pairs from a rows file (rows.py), walks each again, and
  6. drawn atoms: at each atom start of a RULE or DET body without NOT, OR or ALL, the counts of derived and builtin atoms drawn (feats.drawn_state) equal the counts of those atoms among the
     first (atom index - 1) atoms of the order's text; and their sum is the atom index - 1 on every atom start of every pair.
  8. row parity: on the first --parity pairs, the facts that hook.pick_facts (the read's path) gives equal those that rows.py stored (state, options, facts, gate facts, ws).
Writes the result to X/checks.json (merged with what is there).
"""
import argparse
import collections
import json
import os
import sys
import time

X = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37'
sys.path.insert(0, X + '/probe')
ap = argparse.ArgumentParser()
ap.add_argument('--rows', required=True)
ap.add_argument('--pairs', type=int, default=20)
ap.add_argument('--parity', type=int, default=10)
ap.add_argument('--src', default='c120')
ap.add_argument('--out', default=X + '/checks.json')
ARGS = ap.parse_args()
import common as C  # noqa: E402

feats = C.feats
sys.path.insert(0, X)
import hook  # noqa: E402

or_q, S, ns = C.or_q, C.S, C.ns
CAP = dict(log=None, call=-1, text={}, scope=None)
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


def pick_complete(self, n, opts, weights, key, alt=None):
    rf = getattr(self, '_rf_got', None)
    self._rf_got = None
    o, q = _pc(self, n, opts, weights, key, alt)
    if CAP['log'] is not None and n.phase in ('root', 'root2') and o is not None:
        rfs = rf if rf is not None and len(rf) == len(opts) else [1.0] * len(opts)
        ws = [w / r if r else 0.0 for w, r in zip(weights, rfs)]
        st, d_idx, bases, facts, gf = hook.pick_facts(self, n, opts, ws, CAP['scope'])
        CAP['log'].append(dict(call=CAP['call'], st=st, k=self.p_k, ph=n.phase, d_idx=d_idx, bases=bases, facts=facts, gf=gf, ws=[ws[i] for i in d_idx]))
    return o, q


or_q.GuidedDrawer.pick_complete = pick_complete
_wo = or_q.walk_order


def walk_order(*a, **k):
    CAP['call'] += 1
    CAP['text'][CAP['call']] = a[5]
    return _wo(*a, **k)


or_q.walk_order = walk_order


def body_atoms(text):
    """The atoms of a text in the order written, as rows of (relation name): None where the text has NOT, OR or ALL."""
    if any(w in text for w in ('(NOT', '(OR', '(ALL')):
        return None
    O = ns['O']
    tree = O.parse(text)[0]
    out = []

    def is_port(f):
        return isinstance(f, list) and bool(f) and isinstance(f[0], str) and f[0].startswith(':')

    def walk(x):
        if isinstance(x, list) and x:
            if isinstance(x[0], str) and not x[0].startswith(':') and len(x) > 1 and all(is_port(f) for f in x[1:]):
                out.append(x[0])
            else:
                for y in x:
                    walk(y)
    walk(tree)
    return out


def main():
    pairs = []
    for l in open(ARGS.rows):
        r = json.loads(l)
        if r['status'] != 'ok':
            continue
        take = [p for p in r['pairs'] if p['valid'] and p['rows']][:3]
        pairs += [(r['task'], r['src'], p) for p in take]
        if len(pairs) >= ARGS.pairs:
            break
    pairs = pairs[:ARGS.pairs]
    res = dict(pairs=len(pairs), picks=0, sum_ok=0, sum_bad=[], text_checked=0, text_ok=0, text_bad=[], parity_pairs=0, parity_picks=0, parity_bad=[])
    ctx = {}
    t0 = time.time()
    for ti, (task, src, p) in enumerate(pairs):
        if task not in ctx:
            ctx.clear()
            C.MEMO.clear()
            c = (C.NCtx if src == 'n600' else C.CCtx)(task)
            ctx[task] = (c, C.D.session_of(task))
        c, (sess, d, _) = ctx[task]
        texts = list(c.scopes[p['si']]['texts'])
        srel = C.relations_x(texts, sess, d)
        CAP.update(log=[], call=-1, text={}, scope=feats.Scope(texts, srel))
        try:
            or_q.walk(ns['sampler'], task, src, [p['g'], 0], texts, p['target'], sess, d, p['kind'], seconds=20)
        finally:
            log, CAP['log'] = CAP['log'], None
        # 6
        for row in p['rows']:
            res['picks'] += 1
            if row['_nd'] + row['_nb'] == row['_k'] - 1:
                res['sum_ok'] += 1
            else:
                res['sum_bad'].append((task, p['g'], row['o'], row['_k'], row['_nd'], row['_nb']))
            text = CAP['text'].get(row['o'])
            atoms = body_atoms(text) if text and p['kind'] in ('RULE', 'DET') else None
            if atoms is not None and row['st']['ph'] == 'root':
                res['text_checked'] += 1
                pre = atoms[:row['_k'] - 1]
                nd, nb = sum(1 for a in pre if a.startswith('&')), sum(1 for a in pre if not a.startswith('&'))
                if (nd, nb) == (row['_nd'], row['_nb']):
                    res['text_ok'] += 1
                else:
                    res['text_bad'].append((task, p['g'], row['o'], row['_k'], (nd, nb), (row['_nd'], row['_nb']), atoms))
        # 8
        if ti < ARGS.parity:
            res['parity_pairs'] += 1
            fresh = collections.defaultdict(list)
            for e in log:
                fresh[e['call']].append(e)
            stored = collections.defaultdict(list)
            for row in p['rows']:
                stored[row['o']].append(row)
            for call, rs in stored.items():
                fs = fresh.get(call, [])
                if len(fs) != len(rs):
                    res['parity_bad'].append((task, p['g'], call, 'pick count', len(fs), len(rs)))
                    continue
                for row, e in zip(rs, fs):
                    res['parity_picks'] += 1
                    D = row['D']
                    same = (row['st'] == e['st'] and [(d_[0], d_[1]) for d_ in D] == [tuple(b) for b in e['bases']] and [d_[6] for d_ in D] == e['facts'] and row['gf'] == e['gf']
                            and all(abs(d_[2] - w) <= 1e-9 * max(1.0, abs(w)) for d_, w in zip(D, e['ws'])))
                    if not same:
                        res['parity_bad'].append((task, p['g'], call, row['_k'], 'differs'))
    res['seconds'] = round(time.time() - t0, 1)
    res['sum_all_ok'] = not res['sum_bad']
    all_ = json.load(open(ARGS.out)) if os.path.exists(ARGS.out) else {}
    all_[os.path.basename(ARGS.rows)] = res
    json.dump(all_, open(ARGS.out, 'w'), indent=1, default=str)
    print(json.dumps({k: (v if not isinstance(v, list) else v[:5]) for k, v in res.items()}, default=str))


main()
