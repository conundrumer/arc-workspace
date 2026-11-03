"""Item 6 for S120: per-task feature rows with labels, from the node records. Streams, skips finished tasks.

  ./rt600.sh features_node_matrix.py s120 SECONDS [NTASKS [I/N]]     (I/N: every N-th task from I, to run N processes)

Tasks: the first NTASKS (default 200) of the S120 job list in its order, outside the three exclusion lists. Writes s120-rows/TASK.npz:
X (float32, features_node_feats.NAMES order, form shape empty as the design says for S120 pools), H (the hand reader's 87 features),
meta columns 'token depth kind y plain draw rows' with y 1 = seeded table, 0 = junk, -2 = gold that was found and isn't seeded (dropped
from the fit, not counted as junk). Prints rate and ETA.
"""
import json, os, re, sys, time, types as _types
T0 = time.time()
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'  # the data folder
SRC, SECONDS = sys.argv[1], float(sys.argv[2])
NT = int(sys.argv[3]) if len(sys.argv) > 3 else 200
assert SRC == 's120'
KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-dag-nodes-train50-final-8be414670/'
sys.path.insert(0, HERE); sys.path.insert(0, KIT + 'policy')
import numpy as np
import features_node_io as IO, features_node_feats as FE
import policy as HP

OUT = HERE + SRC + '-rows/'
os.makedirs(OUT, exist_ok=True)
tasks = IO.s120_tasks(NT)
if len(sys.argv) > 4:
    i_, n_ = map(int, sys.argv[4].split('/'))
    tasks = tasks[i_::n_]
KIND = {'DET': 0, 'RULE': 1, 'INIT': 2}
done = nodes_done = 0
for t in tasks:
    if os.path.exists(OUT + t + '.npz'):
        continue
    if time.time() - T0 > SECONDS:
        break
    t1 = time.time()
    task = IO.load_task(t)
    ctx = FE.TaskCtx(task)
    hp = HP.Policy(task)
    N = IO.read_nodes(IO.S120 + t + '.nodes.jsonl.zst')
    X = np.full((len(N), len(FE.NAMES)), np.nan, np.float32)
    H = np.full((len(N), len(hp.names)), np.nan, np.float32)
    M = np.zeros((len(N), 7), np.float64)
    for i, r in enumerate(N):
        cl = r['clause'] or ''
        kind = cl[1:cl.index(' ')] if cl.startswith('(') and ' ' in cl else 'none'
        xr = r['x_rows'] or []
        tt = r['table_types']
        d = FE.node_features(tt, xr, cl, kind, r['depth'], len(re.findall(r'\(&f\d+', cl)), ctx, with_shape=False)
        X[i] = [d[nm] for nm in FE.NAMES]
        sn = _types.SimpleNamespace(id=r['token'], types=r['types'], table_types=tt, arity=r['arity'], depth=r['depth'], parents=r['parents'], clause=cl, rows=xr, examples=r['examples'])
        try:
            hd = hp.feats(sn)
            for nm, v in hd.items():
                if nm in hp.ix:
                    H[i, hp.ix[nm]] = v
        except Exception:
            pass
        tg = r.get('tags') or {}
        y = 1 if tg.get('seeded') else (-2 if tg.get('kind') == 'gold' else 0)
        M[i] = [int(r['token']), r['depth'], KIND.get(kind, 3), y, FE.plain_sig(tt, xr, ctx.n_train, ctx.n_test), tg.get('draw', -1), sum(e[2] for e in xr)]
    np.savez_compressed(OUT + t + '.npz', X=X, H=H, meta=M, names=np.array(FE.NAMES), hand_names=np.array(hp.names), meta_cols=np.array('token depth kind y plain draw rows'.split()))
    done += 1
    nodes_done += len(N)
    print(t, len(N), 'nodes', 'seeded', int((M[:, 3] == 1).sum()), 'found gold dropped', int((M[:, 3] == -2).sum()), round(time.time() - t1, 1), 's', flush=True)
left = sum(not os.path.exists(OUT + t + '.npz') for t in tasks)
el = time.time() - T0
print('tasks done this call', done, 'left', left, 'of', len(tasks), 'nodes/s %.0f' % (nodes_done / el if el else 0), 'ETA s', round(left * el / done) if done else None)
