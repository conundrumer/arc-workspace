"""Per task: sketches of all pool nodes, labels, and pair features for (all seeded pairs + a uniform sample of pool pairs).
Cached in cache/<task>.pairs.<tag>.pkl. Usage: build_pairs.py --tag v1 [--budget S] [--procs N] [--nsample 3000]"""
import argparse, json, os, sys, time, random, pickle, itertools
from multiprocessing import Pool
sys.path.insert(0, SCOPE_DIR := os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import *
from nodefeat import Pair, TASKS
import importlib

MOD = None
SPECS = None


def init(tag, nsample):
    global MOD, SPECS, TAG, NS
    TAG, NS = tag, nsample
    sys.path.insert(0, SCOPE)
    MOD = importlib.import_module(os.environ.get('PAIR_MODULE', 'features_pair'))
    SPECS = specs()


def labels(task, nodes):
    kinds, reads, fid, ready, lines = gold(SPECS[task])
    cv = covers(task)
    node_of = {g: str(nd) for g, (nd, dr) in cv.items()}
    anyp, readyp = set(), set()
    for i, r in enumerate(reads):
        for x, y in itertools.combinations(r, 2):
            a, b = node_of.get(x), node_of.get(y)
            if a and b and a != b:
                anyp.add(frozenset((a, b)))
                if i in ready:
                    readyp.add(frozenset((a, b)))
    return anyp, readyp


def one(task):
    out = f'{SCR}/cache/{task}.pairs.{TAG}.pkl'
    if os.path.exists(out) or not os.path.exists(f'{SCR}/cache/{task}.score.json'):
        return task, 0, 0, 0
    t0 = time.time()
    T = json.load(open(f'{TASKS}/{task}.json'))
    pairs = [Pair(p['input'], p['output']) for p in T['train']]
    nodes = read_nodes(task)
    score = json.load(open(f'{SCR}/cache/{task}.score.json'))
    anyp, readyp = labels(task, nodes)
    t1 = time.time()
    anc = {}
    for n in nodes:
        a_ = set()
        for q in n['parents']:
            a_ |= anc.get(q, set()) | {q}
        anc[n['token']] = a_
        n['anc'] = sorted(a_)
    sk = [MOD.sketch(n, pairs) for n in nodes]
    t2 = time.time()
    seeded = [i for i, n in enumerate(nodes) if n['tags']['seeded']]
    idx = {n['token']: i for i, n in enumerate(nodes)}
    rng = random.Random(hash(task) & 0xffff)
    N = len(nodes)
    sel = set(frozenset(c) for c in itertools.combinations(seeded, 2))
    tries = 0
    while len(sel) < len(list(itertools.combinations(seeded, 2))) + NS and tries < NS * 5:
        a, b = rng.randrange(N), rng.randrange(N); tries += 1
        if a != b:
            sel.add(frozenset((a, b)))
    rows = []
    for s in sel:
        a, b = sorted(s)
        ta, tb = nodes[a]['token'], nodes[b]['token']
        key = frozenset((ta, tb))
        f = MOD.features(sk[a], sk[b])
        rows.append((a, b, key in anyp, key in readyp, f))
    t3 = time.time()
    info = [dict(tok=n['token'], seeded=n['tags']['seeded'], score=score[n['token']], depth=n['depth'], arity=n['arity'], rows=sk_['rows'])
            for n, sk_ in zip(nodes, sk)]
    sz = [len(pickle.dumps({k: v for k, v in s_.items() if k != 'tm'})) for s_ in sk[:200]]
    tmp = out + '.tmp%d' % os.getpid()
    pickle.dump(dict(task=task, info=info, rows=rows, t_sketch=(t2 - t1) / N, t_pair=(t3 - t2) / max(len(rows), 1), sk_bytes=sum(sz) / len(sz), n_nodes=N), open(tmp, 'wb'))
    os.replace(tmp, out)
    return task, N, len(rows), time.time() - t0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--tag', required=True); ap.add_argument('--budget', type=float, default=120)
    ap.add_argument('--procs', type=int, default=3); ap.add_argument('--nsample', type=int, default=3000)
    a = ap.parse_args()
    todo = [t for t in done_tasks() if not os.path.exists(f'{SCR}/cache/{t}.pairs.{a.tag}.pkl') and os.path.exists(f'{SCR}/cache/{t}.score.json')]
    print('todo', len(todo), flush=True)
    t0 = time.time(); n = 0
    with Pool(a.procs, initializer=init, initargs=(a.tag, a.nsample)) as p:
        for task, N, R, dt in p.imap_unordered(one, todo, chunksize=1):
            n += 1; el = time.time() - t0
            print(f'{n}/{len(todo)} {task} nodes {N} pairs {R} {dt:.1f}s  rate {n/el:.2f}/s eta {(len(todo)-n)*el/n:.0f}s', flush=True)
            if el > a.budget:
                p.terminate(); break
