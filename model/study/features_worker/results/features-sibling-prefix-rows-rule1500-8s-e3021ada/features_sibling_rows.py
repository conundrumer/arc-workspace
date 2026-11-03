#!/usr/bin/env python
"""Rows for ranking a gold prefix among prefixes of its own tables. For each gold prefix of 1 to 3 atoms of a RULE form, makes variants that read the same relations: another column set, a broken or a new join, a NOT, a swapped neighbor relation, and keeps each variant's table and features. Labels come only from which text is gold's; no feature reads them.

  <python> features_sibling_rows.py FORMS K N --budget 8 --out DIR
"""
import collections, gzip, json, math, os, pickle, random, re, signal, sys, time
sys.path.insert(0, os.environ['SAMPLER_CODE'])
sys.path[:0] = os.environ.get('FEATS', '').split(':')
import live, live_try, search, search_gold as G  # noqa: E401,E402
import superdag as D  # noqa: E402
from nodefeat import Pair, features  # noqa: E402
from outfeat import out_features  # noqa: E402
import features_second as SECOND  # noqa: E402
import features_context as CTX  # noqa: E402
S = live.S
NAME = re.compile(r'&[A-Za-z_0-9.]+')
ROWS = 120; PER = 30; TRIES = 150
SCHEMA = json.load(open(os.environ['FEATURES_RELATION_COLUMNS']))
LIBRARY = [r for r, _ in SCHEMA['uses'][:24]]


def show(x):
    return x if isinstance(x, str) else '(' + ' '.join(show(y) for y in x) + ')'


def labels_of(atoms):
    out = []
    for t in search.flat(atoms):
        if t.startswith('*') and t[1:] not in out:
            out.append(t[1:])
    return out


def columns_by_relation(lines):
    c = collections.defaultdict(set)
    for ln in lines:
        for a in walk(search.parse(ln)[0]):
            c[a[0]].update(x[0] for x in a[1:] if isinstance(x, list) and x and str(x[0]).startswith(':'))
    return c


def walk(x):
    if isinstance(x, list):
        if x and isinstance(x[0], str) and len(x) > 1 and all(isinstance(y, list) and y and str(y[0]).startswith(':') for y in x[1:]):
            yield x
        for y in x:
            yield from walk(y)


def variants(atoms, cols, near, rng):
    """{kind: [atom list]} of texts that read the same relations as atoms, or add or swap in a neighbor."""
    out = collections.defaultdict(list); last = atoms[-1]
    neg = isinstance(last, list) and last and last[0] == 'NOT'
    core = last[1] if neg else last
    if not isinstance(core, list) or not core or not isinstance(core[0], str):
        return out
    wrap = (lambda a: ['NOT', a]) if neg else (lambda a: a)
    args = [x for x in core[1:] if isinstance(x, list)]
    seen = labels_of(atoms[:-1]); bound = labels_of(atoms); head = atoms[:-1]
    for i, a in enumerate(args):
        if len(args) > 1:
            out['drop column'].append(head + [wrap([core[0]] + args[:i] + args[i + 1:])])
        for c in cols.get(core[0], ()):
            if all(c != b[0] for b in args):
                out['other column'].append(head + [wrap([core[0]] + args[:i] + [[c] + a[1:]] + args[i + 1:])])
                out['add column'].append(head + [wrap([core[0]] + args + [[c, f'*add{i}']])])
        v = a[1] if len(a) > 1 else None
        if isinstance(v, str) and v in seen:
            out['break join'].append(head + [wrap([core[0]] + args[:i] + [[a[0], '*' + v + '9']] + args[i + 1:])])
        if isinstance(v, str) and v.startswith('*'):
            for s in seen:
                out['make join'].append(head + [wrap([core[0]] + args[:i] + [[a[0], s]] + args[i + 1:])])
    if head:
        free = [a for a in args if not (len(a) > 1 and isinstance(a[1], str) and a[1].startswith('*'))]
        if neg:
            out['sign'].append(head + [core])
        elif free:
            out['sign'].append(head + [['NOT', [core[0]] + free]])
    for r in near:
        cs = cols.get(r, ())
        if r != core[0] and all(a[0] in cs for a in args):
            out['neighbor relation'].append(head + [wrap([r] + args)])
        for c in cs:
            for s in bound:
                rest = [[x, f'*{x[1:]}j'] for x in cs if x != c][:2]
                out['neighbor join'].append(atoms + [[r, [c, s]] + rest])
                out['neighbor NOT'].append(atoms + [['NOT', [r, [c, s]]]])
    for v in out.values():
        rng.shuffle(v)
    return out


def interleave(by_kind):
    kinds = sorted(by_kind); i = 0
    while any(by_kind.values()):
        k = kinds[i % len(kinds)]; i += 1
        if by_kind[k]:
            yield k, by_kind[k].pop()


def row(run, sess, scope, task_pairs, atoms, slots, tabs):
    labels = labels_of(atoms)
    if not labels:
        return None
    text = show(['RULE', '&prefix_stage'] + atoms)
    run.collect = []
    run.scoped = None
    run.scope(scope + [text])
    ct = run.collect[-1]
    tbs = [S.parse_table(D.OneTable(ct, j)) for _, j in D.relation_tables(ct)]
    if len(tbs) != 1:
        return None
    tb = tbs[0]; full = S.full(tb)
    r = dict(types=[], table_types=[str(x) for x in tb['types']], arity=len(tb['types']), depth=1, parents=[], clause='', n_clauses=1, x_rows=S.rows_with_models(full, S.X_ROWS_CAP), examples=D.table_key(full)[1])
    at = [NAME.sub(lambda m: f'&r{slots[m[0]]}' if m[0] in slots else m[0], show(a)) for a in atoms]
    f = features(r, task_pairs); f.update(out_features(r, task_pairs)[0]); f.update(SECOND.features(r, at, tabs, task_pairs)); f.update(CTX.features(r, at, task_pairs))
    return dict(text=at, key=D.table_key(full)[0], f=f, atoms=len(atoms), table=dict(types=r['table_types'], labels=list(tb['labels']), x_rows=S.rows_with_models(full, ROWS)))


def one(sampler, specs, task, line, budget, path):
    t0 = time.process_time()
    lines = [x for x in specs[task].strip().split('\n') if not x.startswith('(OUT')]
    if not lines[line].startswith('(RULE'):
        return
    sess, task_json, _ = live_try.session_of(task)
    run = D.Run(sampler.pri, sess, 0, 1e12, task_json, live.Limits())
    pairs = [Pair(p['input'], p['output']) for p in task_json['train']]
    scope = lines[:line]
    heads = {NAME.search(x)[0]: i for i, x in enumerate(scope) if NAME.search(x)}
    run.collect = []; run.scope(scope)
    tabs = {}
    for i, ct in enumerate(run.collect):
        try:
            tb = [S.parse_table(D.OneTable(ct, j)) for _, j in D.relation_tables(ct)]
            if len(tb) == 1:
                tabs[i] = dict(types=[str(x) for x in tb[0]['types']], labels=list(tb[0]['labels']), x_rows=S.rows_with_models(S.full(tb[0]), 200))
        except Exception:  # noqa: BLE001
            pass
    form = search.parse(lines[line])[0]; atoms = form[2:]
    cols = columns_by_relation(lines)
    for r, cs in SCHEMA['columns'].items():
        cols[r].update(cs)
    near = sorted(set(LIBRARY) | {NAME.search(x)[0] for x in scope if NAME.search(x)} | {a for a in cols if not a.startswith('&') and any(a in ln for ln in lines)})
    rng = random.Random(f'{task} {line}')
    res = []; bad = collections.Counter(); cut = 0
    for s in range(1, min(3, len(atoms) - 1) + 1):
        if any(isinstance(a, list) and a and a[0] == 'OR' for a in atoms[:s]):
            continue
        try:
            g = row(run, sess, scope, pairs, atoms[:s], heads, tabs)
        except Exception as e:  # noqa: BLE001
            bad[f'gold: {str(e)[:70]}'] += 1; g = None
        if g is None:
            continue
        g['gold'] = True; g['split'] = s; res.append(g)
        seen = {g['key']}; n = 0; miss = collections.Counter()
        for kind, v in interleave(variants(atoms[:s], cols, near, rng)):
            if n >= PER:
                break
            if time.process_time() - t0 > budget * s / min(3, len(atoms) - 1):
                cut += 1; break
            if miss[kind] >= TRIES:  # a kind whose texts keep failing the checks
                continue
            try:
                x = row(run, sess, scope, pairs, v, heads, tabs)
            except Exception as e:  # noqa: BLE001
                bad[f'{kind}: {str(e)[:12]}'] += 1; miss[kind] += 1; continue
            if x is None or x['key'] in seen:
                continue
            seen.add(x['key']); x['gold'] = False; x['split'] = s; x['kind'] = kind; res.append(x); n += 1
    with gzip.open(path + '.new', 'wb', 4) as g:
        pickle.dump(dict(task=task, line=line, rows=res, bad=dict(bad), cut=cut, cpu=time.process_time() - t0), g)
    os.replace(path + '.new', path)
    print(task, line, 'prefixes', sum(x['gold'] for x in res), 'siblings', sum(not x['gold'] for x in res), 'cut', cut, 'cpu', round(time.process_time() - t0, 1), bad.most_common(3), flush=True)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('forms'); ap.add_argument('k', type=int); ap.add_argument('n', type=int)
    ap.add_argument('--budget', type=float, default=8); ap.add_argument('--out', default='out/siblings'); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sampler = live.Sampler(os.environ['SEARCH_MODELS'])
    specs = {x['task']: x['gold_sexp'] for x in json.load(open(os.environ['SEARCH_GOLDS']))}
    forms = [l.split() for l in open(a.forms)][a.k::a.n]; done = 0
    for t, ln, kind in forms:
        path = f'{a.out}/{t}.{ln}.pkl.gz'
        if kind != 'RULE' or os.path.exists(path):
            continue
        pid = os.fork()
        if pid == 0:
            signal.alarm(int(2 * a.budget + 60))
            try:
                one(sampler, specs, t, int(ln), a.budget, path)
            except Exception as e:  # noqa: BLE001
                print(t, ln, 'failed', type(e).__name__, str(e)[:120], flush=True)
            os._exit(0)
        os.waitpid(pid, 0); done += 1
    print('finished', done, flush=True)
