#!/usr/bin/env python
"""Rows of the prefix tables of gold forms, for a fit of a table score. A form's rows are gold's walk and a search over the form's kind, with every gold form before it in scope. No feature reads gold; `src` and the walk are the label only.

  <python> features_corpus_rows.py FORMS K N --budget 8 --out DIR

FORMS has lines of task, line and kind. This process takes every Nth form from K, loads the priors once, and forks a child per form, so a panic or a stall loses one form. A form writes one .pkl.gz file when it ends, and a rerun skips written forms. A prefix of an INIT form takes the engine's table of the body in progress (`ports=True`), where the runtime has it. SAMPLER_CODE, FEATS (paths, `:`) and SEARCH_GOLDS, SEARCH_MODELS name the inputs.
"""
import collections, gzip, json, math, os, pickle, re, signal, sys, time
sys.path.insert(0, os.environ['SAMPLER_CODE'])
sys.path[:0] = os.environ.get('FEATS', '').split(':')
import live, live_try, or_q  # noqa: E401,E402
import search_gold as G  # noqa: E402
import superdag as D  # noqa: E402
from nodefeat import Pair, features  # noqa: E402
from outfeat import out_features  # noqa: E402
try:
    import features_second as SECOND  # second-order features, where the kit has them
except ImportError:
    SECOND = None
S, arclog = live.S, live.arclog
LN2 = math.log(2)
ATOM = re.compile(r'\((NOT \()?(\S+)((?: \(:\w+ [^()]*\))*)')
COLN = re.compile(r'\(:(\w+)')
st = dict(mode=None, pairs=None, seen=set(), rows=[], cost=[0.0, 0], errors=collections.Counter(), ports=True, tables={})
o_table, o_lt, o_or, o_close = live.Run.table, live.Run.label_types, live.Run.or_atom, live.Run.close
DUMP = os.environ.get('FEATURES_DUMP')  # rows also keep each prefix's table and its scope's tables, for feature work


def sig(text):
    m = ATOM.match(text)
    return (m[1] is not None, m[2], tuple(sorted(COLN.findall(text)))) if m else (False, text, ())


def add(run, tb, place, keyed, k, text):
    """One row per mode and prefix."""
    key = (st['mode'], place, tuple(text))
    if key in st['seen']:
        return
    st['seen'].add(key)
    t0 = time.process_time()
    try:
        full = S.full(tb)
        r = dict(types=[], table_types=[str(x) for x in tb['types']], arity=len(tb['types']), depth=1, parents=[], clause='', n_clauses=1, x_rows=S.rows_with_models(full, S.X_ROWS_CAP), examples=D.table_key(full)[1])
        f = features(r, st['pairs'])
        f.update(out_features(r, st['pairs'])[0])
        if SECOND is not None:
            f.update(SECOND.features(r, text, st.get('ptab', {}), st['pairs']))
        logq = -LN2 * sum(run.rng.parts.values()) if st['mode'] == 'gold' else getattr(run.rng, 'logp', None)
        st['rows'].append(dict(src=st['mode'], place=place, atoms=k, keyed=keyed, logq=logq, sigs=[sig(x) for x in text], f=f))
        if place == 'RULE':
            import features_prefix_score as SCORE, numpy as np
            t1 = time.process_time(); v = SCORE.score(tb, dict(pairs=st['pairs'], ptab=st.get('ptab', {}), text=list(text), atoms=k)); dt = time.process_time() - t1
            b = SCORE.bundle(); x = np.full((1, len(b['ix']) + 6), np.nan, np.float32); x[0, -1] = k; x[0, -2] = False; x[0, -3 - b['places'].index('RULE')] = 1
            for n, w in f.items():
                j = b['ix'].get(n)
                if j is not None and w is not None:
                    x[0, j] = w
            print('CHECK', round(dt * 1000, 3), round(v, 5), round(float(b['model'].decision_function(x)[0]), 5), round((time.process_time() - t0) * 1000, 3), SCORE.failed[0], flush=True)
        if DUMP:
            st['rows'][-1].update(text=list(text), table=dict(types=r['table_types'], labels=list(tb['labels']), x_rows=S.rows_with_models(full, 200)))
    except Exception as e:  # noqa: BLE001
        st['errors'][f'{type(e).__name__}: {str(e)[:80]}'] += 1
    st['cost'][0] += time.process_time() - t0; st['cost'][1] += 1


def port_table(run, dr, dec, pg):
    f = dec.fork()
    p = dr.fr.probe(f)
    if p is None:
        return None
    try:
        f.step(p)
        return S.parse_table(arclog.step_tables(f, *live.TABLES, True, pg.before, ports=True), with_rows=False)
    except TypeError:  # a runtime with no port tables
        st['ports'] = False
        return None
    except (Exception, BaseException) as e:  # noqa: BLE001
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        st['errors'][f'port: {str(e)[:60]}'] += 1
        return None


def frame_body():
    up = sys._getframe(2)
    while up is not None and up.f_code.co_name != 'body':
        up = up.f_back
    return up


def close(self, pg, f):
    """Keeps the table of a finished form that gives one table, for second-order features: slot -> (types, x_rows)."""
    got = o_close(self, pg, f)
    try:
        tb = S.parse_table(pg.before, with_rows=False)
        for s in pg.new:
            st.setdefault('ptab', {})[s] = dict(types=[str(x) for x in tb['types']], labels=list(tb['labels']), x_rows=S.rows_with_models(S.full(tb), 200))
    except Exception:  # noqa: BLE001
        pass
    return got


def table(self, fr, dec, pg):
    got = o_table(self, fr, dec, pg)
    if got[0] is not None and st['mode']:
        up = frame_body()
        if up is not None:
            loc = up.f_locals
            at = list(loc.get('text') or []) + ([loc['res'][3]] if loc.get('res') else [])
            add(self, got[0], loc['kind'], False, len(at), at)
    return got


def init_prefix(run, dr, dec, up, text):
    loc = up.f_locals
    keyed = bool(loc['keys'])
    if dr.place == 'key':
        run._ktext = list(text)
    tb = port_table(run, dr, dec, loc['pg']) if st['ports'] else None
    if tb is not None:
        add(run, tb, dr.place, keyed, loc['k'], (getattr(run, '_ktext', []) if keyed and dr.place != 'key' else []) + list(text))


def label_types(self, dr, atoms):
    got = o_lt(self, dr, atoms)
    up = sys._getframe(1)
    if st['mode'] and up.f_code.co_name == 'body' and up.f_locals['kind'] == 'INIT':
        init_prefix(self, dr, up.f_locals['cur'], up, up.f_locals['text'])
    return got


def or_atom(self, pg, dr, cur, toks, text, scope, nlab, k):
    got = o_or(self, pg, dr, cur, toks, text, scope, nlab, k)
    up = sys._getframe(1)
    if got is not None and st['mode'] and up.f_locals.get('kind') == 'INIT':
        init_prefix(self, dr, got[0], up, list(text) + [got[2]])
    return got


def one(sampler, task, line, kind, budget, path):
    live.Run.table, live.Run.label_types, live.Run.or_atom, live.Run.close = table, label_types, or_atom, close
    lines = [x for x in G.golds_cached()[task].splitlines() if x.strip()]
    scope, target = lines[:line], lines[line]
    G.gold_of = lambda t, c, p: (t, scope + [target])
    tj = json.load(open(f'{S.TASKS}{task}.json'))
    st['pairs'] = [Pair(p['input'], p['output']) for p in tj['train']]
    res = dict(task=task, line=line, kind=kind, target=target)
    st['mode'] = 'gold'
    q = or_q.one(sampler, task, kind, [len(scope), 0], kind)
    res.update(bits=q.get('total'), bad=q.get('bad'), dead=q.get('dead'), match=q.get('match'), walk=q.get('atoms'))
    sess, task_json, _ = live_try.session_of(task)
    st['mode'] = 'search'
    c0 = time.process_time()
    st['box'] = None
    try:
        box = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, kind, eager=True)
        st['box'] = box
        while time.process_time() - c0 < budget:
            for _ in box:
                pass
            if box.exhausted or not box.heap:
                break
            box = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, kind, eager=True)
        res['runs'] = box.stats['runs']
    except Exception as e:  # noqa: BLE001
        res['error'] = f'{type(e).__name__}: {str(e)[:160]}'
    st['mode'] = None
    if DUMP:
        res['scope'] = {k: v for k, v in st.get('ptab', {}).items()}
    res.update(cpu=round(time.process_time() - c0, 1), rows=st['rows'], feat_cpu=round(st['cost'][0], 2), feat_n=st['cost'][1], errors=dict(st['errors']), ports=st['ports'])
    with gzip.open(path + '.new', 'wb', compresslevel=3) as f:
        pickle.dump(res, f, protocol=5)
    os.replace(path + '.new', path)
    print(task, line, kind, 'bits', res['bits'], 'rows', len(st['rows']), 'gold', sum(x['src'] == 'gold' for x in st['rows']), 'cpu', res['cpu'], 'feat', res['feat_cpu'], res.get('error', ''), list(st['errors'].items())[:1], flush=True)


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('forms'); ap.add_argument('k', type=int); ap.add_argument('n', type=int)
    ap.add_argument('--budget', type=float, default=8); ap.add_argument('--out', default='out/rows'); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    forms = [l.split() for l in open(a.forms) if l.strip()][a.k::a.n]
    data = G.golds()
    G.golds_cached = lambda: data
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    limit = 2 * a.budget + 90; t0 = time.time(); done = 0
    for i, (task, line, kind) in enumerate(forms, 1):
        path = f'{a.out}/{task}.{line}.pkl.gz'
        if os.path.exists(path):
            continue
        pid = os.fork()
        if pid == 0:
            signal.alarm(int(limit))
            try:
                one(sampler, task, int(line), kind, a.budget, path)
            except BaseException as e:  # noqa: BLE001
                print(task, line, kind, 'fail', type(e).__name__, str(e)[:120], flush=True)
                os._exit(1)
            os._exit(0)
        os.waitpid(pid, 0)
        done += 1
        if done % 20 == 0:
            el = time.time() - t0
            print(f'progress {i}/{len(forms)} {done / el:.2f} forms/s ETA {(len(forms) - i) / max(done / el, 1e-9):.0f} s', flush=True)
    print('finished', a.k, flush=True)


if __name__ == '__main__':
    main()
