"""Exact-join features for every seeded pair, per task; plus timing on a 40-node visit. cache/<task>.exact.pkl. Usage: build_exact.py [--budget S] [--procs N]"""
import argparse, json, os, sys, time, random, pickle, itertools
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import *
from nodefeat import Pair, TASKS
import features_pair_exact as X


def one(task):
    out = f'{SCR}/cache/{task}.exact.pkl'
    if os.path.exists(out):
        return task, 0
    t0 = time.time()
    T = json.load(open(f'{TASKS}/{task}.json'))
    pairs = [Pair(p['input'], p['output']) for p in T['train']]
    nodes = read_nodes(task)
    seeded = [n for n in nodes if n['tags']['seeded']]
    tab = {n['token']: X.tables(n, pairs) for n in seeded}
    feats = {}
    for a, b in itertools.combinations(seeded, 2):
        feats[(a['token'], b['token'])] = X.features_exact(tab[a['token']], tab[b['token']])
    # timing: a visit of 40 random nodes of the pool
    rng = random.Random(1)
    vis = rng.sample(nodes, min(40, len(nodes)))
    t1 = time.time()
    tv = [X.tables(n, pairs) for n in vis]
    t2 = time.time()
    for x, y in itertools.combinations(tv, 2):
        X.features_exact(x, y)
    t3 = time.time()
    pickle.dump(dict(feats=feats, t_tables=(t2 - t1), t_pairs=(t3 - t2), nvis=len(vis)), open(out + '.tmp%d' % os.getpid(), 'wb'))
    os.replace(out + '.tmp%d' % os.getpid(), out)
    return task, time.time() - t0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--budget', type=float, default=120); ap.add_argument('--procs', type=int, default=3)
    a = ap.parse_args()
    todo = [t for t in done_tasks() if not os.path.exists(f'{SCR}/cache/{t}.exact.pkl')]
    print('todo', len(todo), flush=True)
    t0 = time.time(); n = 0
    with Pool(a.procs) as p:
        for task, dt in p.imap_unordered(one, todo, chunksize=1):
            n += 1; el = time.time() - t0
            print(f'{n}/{len(todo)} {task} {dt:.1f}s rate {n/el:.2f}/s eta {(len(todo)-n)*el/n:.0f}s', flush=True)
            if el > a.budget:
                p.terminate(); break
