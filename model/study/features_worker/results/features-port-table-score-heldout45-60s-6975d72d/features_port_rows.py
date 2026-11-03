#!/usr/bin/env python
"""Tables of INIT port prefixes, replayed as RULE bodies on a shadow decoder, for one form of a program. No draw reads a shadow result.

  <runtime python> port_shadow.py TASK LINE [--budget 15] [--out DIR]

SAMPLER_CODE names the sampler code. The scope is every gold form before the line. Three modes run: gold's walk, independent sampling, and best-first search.
A prefix of a keyed port is the key's atoms and then the port's. Each prefix path gets one table. A group is one (component, port, key path), the place where
two equal tables could merge. A job writes one JSON file with its counts.
"""
import collections, copy, json, math, os, re, sys, time
sys.path.insert(0, os.environ['SAMPLER_CODE'])
sys.path[:0] = os.environ.get('FEATS', '').split(':')
import live, live_try, or_q  # noqa: E401,E402
import search_gold as G  # noqa: E402
import superdag as D  # noqa: E402
from nodefeat import Pair, features  # noqa: E402
from outfeat import out_features  # noqa: E402
S, arclog = live.S, live.arclog
st = dict(mode=None)
MAPS = {}  # a relation token -> {INIT column token: RULE column token, or None for the Example column}
PATHS, SEEN = {}, collections.defaultdict(set)  # path -> record; (mode, group) -> merge keys
C = collections.defaultdict(collections.Counter)  # mode -> counts
GOLD, ROWS = [], []
ATOM = re.compile(r'\((NOT \()?(\S+)((?: \(:\w+ [^()]*\))*)')
COLN = re.compile(r'\(:(\w+)')


def sig(text):
    m = ATOM.match(text)
    return (m[1] is not None, m[2], tuple(sorted(COLN.findall(text)))) if m else (False, text, ())


cost = [0.0, 0]
o_open, o_body, o_lt, o_or, o_clause = live.Run.open_form, live.Run.body, live.Run.label_types, live.Run.or_atom, live.Run.clause


def place_key(dr):
    return dr.place == 'key'


def admitted(dec, V, t):
    """The column tokens that the decoder admits right after relation token t."""
    f = dec.fork()
    f.step(t)
    out = []
    for i in COLS(V):
        try:
            f.forced(i)
            out.append(i)
        except arclog.Refusal:
            pass
    return out


def COLS(V, memo={}):
    if not memo:
        memo['c'] = [i for _, i in sorted((int(V.name(i)[1:]), i) for i in range(len(V)) if V.kind(i) == 'column' and V.name(i)[1:].isdigit())][:16]
    return memo['c']


def rule_path(run, dec, toks):
    """(tokens of a RULE body for INIT tokens, whether they read an Example column). A declared relation's column tokens in an INIT count an Example
    column that a RULE's leave out. A token after a column token is a field of a record until its END, and keeps its number."""
    V, sh, out, rel, prev, rec, read = run.V, run._sh, [], None, False, False, False
    for t in toks:
        k = V.kind(t)
        if k == 'relation':
            rel, prev, rec = t, False, False
        elif k == 'column' and not prev and not rec and rel is not None:
            m = MAPS.get(rel)
            if m is None:
                a = admitted(dec, V, rel)
                try:
                    b = admitted(o_open(run, copy.copy(sh['pg']), sh['dec'], 'RULE'), V, rel)
                except arclog.Refusal:
                    b = []
                m = MAPS[rel] = dict(zip(a[1:], b)) | {a[0]: None} if a and len(a) == len(b) + 1 else {x: x for x in a}
            t2 = m.get(t, t)
            read |= t2 is None
            out.append(t if t2 is None else t2)
            prev = True
            continue
        elif k == 'column':
            rec = True
        elif t == live.M.END:
            rec = False
        prev = False
        out.append(t)
    return tuple(out), read


def table_of(run, dr, path):
    """The record of a prefix path: its table's state on the shadow decoder."""
    sh = run._sh
    t0 = time.process_time()
    pg = copy.copy(sh['pg'])
    rec = dict(atoms=None)
    try:
        g = o_open(run, pg, sh['dec'], 'RULE')
        for t in path:
            g.step(t)
    except arclog.Refusal as e:
        why = str(e)
        rec['state'] = 'empty' if 'no row satisfies' in why else 'repeat' if 'repeats an existing' in why else 'pooled' if 'PooledAndLiftedReads' in why else 'refused'
        rec['why'] = why[:80]
    else:
        tb, err = S.body_table(dr.fr, *live.TABLES, g, pg.before)
        if tb is None and err == 'no probe token':  # a next token completes the last atom, so a refusal of that atom refuses each next token
            try:
                g.fork().step(live.M.END)
            except arclog.Refusal as e:
                err = str(e)
            tb = None
        if tb is None and 'no row satisfies' in (err or ''):
            rec['state'] = 'empty'; rec['why'] = err[:80]
        elif tb is None and 'repeats an existing' in (err or ''):
            rec['state'] = 'repeat'; rec['why'] = err[:80]
        elif tb is None:
            rec['state'] = 'no table'; rec['why'] = (err or '')[:80]
        else:
            sm = S.summary(tb)
            inputs = [n for k, _, n in sm['entries'] if k in (1, 2)] or [n for _, _, n in sm['entries']]
            rec['state'] = 'empty' if sm['empty_inputs'] else 'some empty' if not all(inputs) else 'full'
            rec['rows'] = sum(inputs)
            full = S.full(tb)
            rec['key'] = hash(D.table_key(full)[0])
            r = dict(types=[], table_types=[str(x) for x in tb['types']], arity=len(tb['types']), depth=1, parents=[], clause='', n_clauses=1, x_rows=S.rows_with_models(full, S.X_ROWS_CAP), examples=D.table_key(full)[1])
            f = features(r, st['pairs'])
            f.update(out_features(r, st['pairs'])[0])
            rec['f'] = f
    cost[0] += time.process_time() - t0; cost[1] += 1
    return rec


def shadow(run, dr, keyed, toks, up, text):
    """Counts one accepted prefix of a key or a port, in frame up of Run.body."""
    sh, mode = run._sh, st['mode']
    keyed = keyed and dr.place != 'key'
    body = up.f_back
    who = (body.f_locals.get('comp'), body.f_locals.get('name')) if body is not None and body.f_code.co_name == 'port' else ('key', 'key')
    nlab = up.f_locals['nlab']
    nkey = sh['key'].count(live.M.STAR) if keyed else 0  # sh['key'] has the whole key once the key body ends
    if nlab > nkey:  # an earlier port's labels hold numbers in the INIT, and a RULE's body has none of them
        back = {t: j for j, t in run.ff0.label_tok.items()}
        toks = [run.ff0.label_tok[back[t] - nlab + nkey] if back.get(t, -1) >= nlab else t for t in toks]
    if place_key(dr):
        sh['ikey'] = tuple(toks)
    path, read = rule_path(run, up.f_locals['dec'], (sh.get('ikey', ()) if keyed and not place_key(dr) else ()) + tuple(toks))
    rec = PATHS.get(path)
    if rec is None:
        rec = PATHS[path] = dict(state='pooled', why='reads an Example column') if read else table_of(run, dr, path)
    place, k = dr.place, up.f_locals['k']
    if 'f' in rec and (st['mode'], path) not in st.setdefault('rowed', set()):
        st['rowed'].add((st['mode'], path))
        at = list(sh.get('ktext', ())) * (keyed and place != 'key') + list(text)
        ROWS.append(dict(src=st['mode'], place=place, atoms=k, keyed=bool(keyed), logq=-math.log(2) * sum(run.rng.parts.values()) if st['mode'] == 'gold' else getattr(run.rng, 'logp', None), sigs=[sig(x) for x in at], own=[sig(x) for x in text], f=rec['f']))
    c = C[mode]
    c[f'visits {place}'] += 1
    if not sh['dead'].get(id(up)):  # a body counts up to its first empty prefix: an atom more can't fill it, and a gate would have stopped there
        c[f'alive {place} {min(k, 6)}'] += 1
        if rec['state'] == 'empty':
            c[f'empty {place} {min(k, 6)}'] += 1
            sh['dead'][id(up)] = True
            sh['bad'] = True
        elif rec['state'] == 'repeat':
            c[f'repeat {place} {min(k, 6)}'] += 1
            sh['dead'][id(up)] = True
            sh['rep'] = True
    if mode == 'gold':
        GOLD.append(dict(place=place, k=k, state=rec['state'], rows=rec.get('rows'), why=rec.get('why')))
    done = st.setdefault('done', set())
    if (mode, path) not in done:
        done.add((mode, path))
        c[f'paths {place}'] += 1
        c[f'paths {rec["state"]}'] += 1
        c[f'state {place} {"keyed" if keyed else "free"} {rec["state"]}'] += 1
        if rec.get('why'):
            c['why ' + rec['state'] + ': ' + re.sub(r'\d+', 'N', rec['why'])[:60]] += 1
        if 'key' in rec and rec['state'] != 'empty':
            g = (mode, who, sh.get('ikey', ()) if keyed else ())
            c['nonempty'] += 1
            c['equal'] += rec['key'] in SEEN[g]
            SEEN[g].add(rec['key'])


def open_form(self, pg, dec, kind):
    if kind == 'INIT' and st['mode']:
        self._sh = dict(dec=dec, pg=copy.copy(pg), key=(), dead={}, bad=False)
    return o_open(self, pg, dec, kind)


def body(self, pg, dr, dec, kind, nlab, need=(), keys=()):
    got = o_body(self, pg, dr, dec, kind, nlab, need, keys)
    if kind == 'INIT' and st['mode'] and dr.place == 'key':
        self._sh['key'] = tuple(got[1])
        self._sh['ktext'] = list(got[2])
    return got


def label_types(self, dr, atoms):
    got = o_lt(self, dr, atoms)
    up = sys._getframe(1)
    if st['mode'] and up.f_code.co_name == 'body' and up.f_locals['kind'] == 'INIT':
        shadow(self, dr, bool(up.f_locals['keys']), up.f_locals['toks'], up, up.f_locals['text'])
    return got


def or_atom(self, pg, dr, cur, toks, text, scope, nlab, k):
    got = o_or(self, pg, dr, cur, toks, text, scope, nlab, k)
    up = sys._getframe(1)
    if got is not None and st['mode'] and up.f_locals.get('kind') == 'INIT':
        shadow(self, dr, bool(up.f_locals['keys']), list(toks) + list(got[1]), up, list(text) + [got[2]])
    return got


def clause(self, seed, deadline, forms, kind):
    got = o_clause(self, seed, deadline, forms, kind)
    if st['mode'] == 'sampling':
        C['sampling']['draws'] += 1
        if got is not None:
            C['sampling']['clauses'] += 1
            C['sampling']['clean clauses'] += not self._sh['bad']
            C['sampling']['clean clauses, repeats too'] += not (self._sh['bad'] or self._sh.get('rep'))
    return got


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('task'); ap.add_argument('line', type=int)
    ap.add_argument('--budget', type=float, default=15); ap.add_argument('--out', default='out'); a = ap.parse_args()
    path = f'{a.out}/{a.task}.{a.line}.pkl'
    if os.path.exists(path):
        return
    live.Run.open_form, live.Run.body, live.Run.label_types, live.Run.or_atom, live.Run.clause = open_form, body, label_types, or_atom, clause
    lines = [x for x in G.golds()[a.task].splitlines() if x.strip()]
    scope, target = lines[:a.line], lines[a.line]
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    G.gold_of = lambda t, c, p: (t, scope + [target])
    res = dict(task=a.task, line=a.line, target=target)
    tj = json.load(open(f'{S.TASKS}{a.task}.json'))
    st['pairs'] = [Pair(p['input'], p['output']) for p in tj['train']]
    st['mode'] = 'gold'
    q = or_q.one(sampler, a.task, 'INIT', [len(scope), 0], 'INIT')
    res.update(bits=q.get('total'), bad=q.get('bad'), dead=q.get('dead'), match=q.get('match'), gold=GOLD, walk=q.get('atoms'))
    PATHS.clear()
    sess, task_json, _ = live_try.session_of(a.task)
    PATHS.clear()
    st['mode'] = 'search'
    c0 = time.process_time()
    try:
        box = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, 'INIT', eager=True)
        while time.process_time() - c0 < a.budget:
            for _ in box:
                pass
            if box.exhausted or not box.heap:
                break
            box = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, 'INIT', eager=True)
        res['runs'] = box.stats['runs']
    except Exception as e:  # noqa: BLE001
        res['error search'] = f'{type(e).__name__}: {str(e)[:160]}'
    res['cpu search'] = round(time.process_time() - c0, 1)
    st['mode'] = None
    res.update(counts={m: dict(c) for m, c in C.items()}, shadow_cpu=round(cost[0], 2), shadow_n=cost[1])
    os.makedirs(a.out, exist_ok=True)
    res['rows'] = ROWS
    import pickle
    with open(path + '.new', 'wb') as f:
        pickle.dump(res, f)
    os.replace(path + '.new', path)
    print(a.task, a.line, 'bits', res['bits'], 'match', res['match'], 'rows', len(ROWS), 'walk rows', sum(x['src'] == 'gold' for x in ROWS), 'cpu', res['cpu search'], flush=True)


if __name__ == '__main__':
    main()
