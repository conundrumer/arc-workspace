#!/usr/bin/env python
"""Rows of the prefix tables of one search job, for a fit and an offline rank of a table score. No feature reads gold; `gold` is the label only.

  <runtime python> prefix_rows.py TASK CASE POINT [--budget 30] [--out DIR]

Run from a kit's top folder, with SEARCH_GOLDS=$PWD/points-eval.json SEARCH_MODELS=models-held. The hook is on live.Run.table, so each prefix with a table
gives one row, once per decoder. A row has `src` (walk for gold's written order, search otherwise), `atoms` (the prefix's atom count), `logq` (log chance
of the path so far), `gold` (each atom of the prefix is one of gold's, by relation and column names, as a bag) and `f` (the node features of the table).
"""
import collections, json, os, pickle, re, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.getcwd(), 'model', 'study', 'sampler'))
sys.path.insert(0, os.environ.get('FEATS', HERE + '/policy'))
ATOM = re.compile(r'\((NOT \()?(\S+)((?: \(:\w+ [^()]*\))*)')
COL = re.compile(r'\(:(\w+)')


def sig(text):
    m = ATOM.match(text)
    return (m[1] is not None, m[2], tuple(sorted(COL.findall(text)))) if m else (False, text, ())


def atoms_of(line):
    """The top-level atoms of a clause or a body, as texts."""
    out, d, at = [], 0, 0
    for i, c in enumerate(line):
        if c == '(':
            if d == 1:
                at = i
            d += 1
        elif c == ')':
            d -= 1
            if d == 1:
                out.append(line[at:i + 1])
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('task'); ap.add_argument('case'); ap.add_argument('point')
    ap.add_argument('--budget', type=float, default=30); ap.add_argument('--out', default='out/prefix'); a = ap.parse_args()
    task, case, point = a.task, a.case, json.loads(a.point)
    path = f'{a.out}/{task}.{case}.{point[0]}-{point[1]}.pkl'
    if os.path.exists(path):
        return
    import live, live_try, or_q, search  # noqa: E401
    import search_gold as G
    import superdag as D
    from nodefeat import Pair, features
    from outfeat import out_features
    S = live.S
    d, lines = G.gold_of(task, case, point)
    scope, target = lines[:point[0]], lines[point[0]]
    tj = json.load(open(f'{S.TASKS}{task}.json'))
    pairs = [Pair(p['input'], p['output']) for p in tj['train']]
    st = dict(mode=None, gold=None); rows = []; cost = [0.0, 0]
    orig = live.Run.table

    def table(self, fr, dec, pg):
        got = orig(self, fr, dec, pg)
        tb = got[0]
        if tb is None or st['mode'] is None:
            return got
        t0 = time.process_time()
        try:
            full = S.full(tb)
            up = sys._getframe(1)
            while up is not None and up.f_code.co_name != 'body':
                up = up.f_back
            loc = up.f_locals if up is not None else {}
            at = list(loc.get('text') or []) + ([loc['res'][3]] if loc.get('res') else [])
            r = dict(types=[], table_types=[str(x) for x in tb['types']], arity=len(tb['types']), depth=len(at), parents=[], clause='', n_clauses=1,
                     x_rows=S.rows_with_models(full, S.X_ROWS_CAP), examples=D.table_key(full)[1])
            f = features(r, pairs)
            o, _ = out_features(r, pairs)
            f.update(o)
            logq = getattr(self.rng, 'logp', None)
            row = dict(src=st['mode'], atoms=len(at), logq=logq, sigs=[sig(x) for x in at], f=f)
            if st['mode'] == 'search' and st['gold'] is not None:
                row['gold'] = not (collections.Counter(row['sigs']) - st['gold'])
            rows.append(row)
        except Exception as e:  # noqa: BLE001
            st.setdefault('errors', collections.Counter())[f'{type(e).__name__}: {str(e)[:80]}'] += 1
        cost[0] += time.process_time() - t0; cost[1] += 1
        return got

    live.Run.table = table
    sampler = live.Sampler(G.MODELS)
    st['mode'] = 'walk'
    q = or_q.one(sampler, task, case, point)
    st['mode'] = None
    walk = q.get('atoms') or []
    res = dict(task=task, case=case, point=point, target=target, bits=q.get('total'), bad=q.get('bad'), dead=q.get('dead'), left=q.get('left'), walk=walk)
    gold_sigs = collections.Counter(sig(x[1]) for x in walk)
    st['gold'] = gold_sigs
    for r in rows:
        r['gold'] = True
    sess, task_json, _ = live_try.session_of(task)
    kind = target.split()[0].lstrip('(')
    c0 = time.process_time(); st['mode'] = 'search'; tried = 0
    try:
        box = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, kind, eager=True)
        while time.process_time() - c0 < a.budget:
            for _ in box:
                pass
            tried = box.stats['runs']
            if box.exhausted or not box.heap:
                break
            box = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, kind, eager=True)
    except Exception as e:  # noqa: BLE001
        res['error'] = f'{type(e).__name__}: {str(e)[:160]}'
    st['mode'] = None
    res.update(tried=tried, cpu=round(time.process_time() - c0, 1), rows=rows, feat_cpu=round(cost[0], 2), feat_n=cost[1], errors=dict(st.get('errors') or {}))
    os.makedirs(a.out, exist_ok=True)
    with open(path + '.new', 'wb') as f:
        pickle.dump(res, f)
    os.replace(path + '.new', path)
    print(task, case, point, 'bits', res['bits'], 'rows', len(rows), 'gold', sum(r.get('gold', False) for r in rows), 'tried', tried, 'cpu', res['cpu'], 'feat', res['feat_cpu'], res['errors'] and list(res['errors'].items())[:2], res.get('error', ''), flush=True)


if __name__ == '__main__':
    main()
