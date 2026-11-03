"""Per task: the single-node policy score of every pool node (the fold that did not train on the task). Cached in cache/<task>.score.json.
Usage: build_scores.py [--budget SECONDS] [--procs N]"""
import argparse, json, os, sys, time, hashlib, pickle
from multiprocessing import Pool
from common import *
import numpy as np
from nodefeat import Pair, features, TASKS
from outfeat import link_one, out_features

B = pickle.load(open(SCOPE + '/kit/kit20/policy/policy_model.pkl', 'rb'))
NAMES = B['names']; IX = {n: i for i, n in enumerate(NAMES)}


def one(task):
    out = f'{SCR}/cache/{task}.score.json'
    if os.path.exists(out):
        return task, 0.0
    t0 = time.time()
    T = json.load(open(f'{TASKS}/{task}.json'))
    key = hashlib.sha1(json.dumps(T['train'], sort_keys=True).encode()).hexdigest()
    model = next((m for trained, m in B['folds'] if key not in trained), B['folds'][0][1])
    pairs = [Pair(p['input'], p['output']) for p in T['train']]
    nodes = read_nodes(task)
    st = {}; X = np.full((len(nodes), len(NAMES)), np.nan, np.float32)
    for r, n in enumerate(nodes):
        row = dict(types=n['types'], table_types=n['table_types'], arity=n['arity'], depth=n['depth'], parents=n['parents'], clause=n['clause'], n_clauses=1, x_rows=n['x_rows'], examples=n['examples'])
        d = features(row, pairs)
        o, s = out_features(row, pairs)
        d.update(o)
        link_one(n['parents'], d, s, st)
        st[n['token']] = (n['parents'], d, s)
        for k, v in d.items():
            if k in IX:
                X[r, IX[k]] = v
    sc = model.decision_function(X)
    tmp = out + '.tmp%d' % os.getpid()
    json.dump({n['token']: float(s) for n, s in zip(nodes, sc)}, open(tmp, 'w'))
    os.replace(tmp, out)
    return task, time.time() - t0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--budget', type=float, default=120); ap.add_argument('--procs', type=int, default=3)
    a = ap.parse_args()
    todo = [t for t in done_tasks() if not os.path.exists(f'{SCR}/cache/{t}.score.json')]
    print('todo', len(todo), flush=True)
    t0 = time.time(); n = 0
    with Pool(a.procs) as p:
        for task, dt in p.imap_unordered(one, todo[:a.procs * 3] if False else todo, chunksize=1):
            n += 1
            el = time.time() - t0
            print(f'{n}/{len(todo)} {task} {dt:.1f}s  rate {n/el:.2f}/s eta {(len(todo)-n)*el/n:.0f}s', flush=True)
            if el > a.budget:
                p.terminate(); break
