"""Item 10: the card and the checks of a final model, after its fit (features_node_fit.py ... --fold all) is done.

  python -I features_node_final.py ARM SECONDS [cost-nodes]       (ARM: M-H M-TS M-T C-shuffle C-depth; on the engine venv Python, sklearn 1.6.1)

Writes final-models/NAME.json: sha256 of the state file, features, sources, rounds, t, label, a, the fit command and the number of trees.
Prints: the banned-word check on the feature names; the top 30 features by permutation gain (loss of a sample of about 35 pools, true labels, rows of the
feature shuffled over the sample); the cost of one scored node on about 500 R120 nodes, features and one-row call together
(sklearn: 150 predict calls; forest: the same trees walked together, forest.py), against the budget of 8 ms mean and 60 ms q99.
Nothing here reads a held label or a held task. FINAL_PREFIX=pilot- makes the arm names pilot-mts and so on, for a test with a short fit.
"""
import json, os, pickle, sys, time, types as _types
T0 = time.time()
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'  # the data folder
sys.path.insert(0, HERE)
import numpy as np
import final_arms as FA, forest as FO
import features_node_data as DT, features_node_io as IO, features_node_feats as FE

ARM, SECONDS = sys.argv[1], float(sys.argv[2])
NCOST = int(sys.argv[3]) if len(sys.argv) > 3 else 500
A = FA.ARMS[ARM]
BANNED = ('gold', 'gold_atom', 'point', 'd_out', 'task', 'case', 'author', 'tags', 'is_gold', 'gold_sexp', 'output_test', 'test_output', 'age', 'uses', 'token', 'draw', 'scope', 'score', 'link_')
os.makedirs(HERE + 'final-models/', exist_ok=True)
sp = FA.state_path(ARM)
if not os.path.exists(sp):
    sys.exit('no state file %s: run the fit first: %s' % (sp, FA.fit_command(ARM)))
models, done = pickle.load(open(sp, 'rb'))
if done != A['rounds']:
    sys.exit('fit not finished: %d of %d rounds. Rerun the fit command, it resumes.' % (done, A['rounds']))
F = FO.Forest(models)

# feature names and a small sample of pools
FOLD0 = DT.folds(5)[0]
pools_s = sorted(IO.s120_tasks(int(os.environ.get('S120_N', 200))))[::8][:25] + sorted(DT.N600_TASKS)[::5][:10]
D = DT.load(['n600', 's120'], A['features'], only_tasks=set(pools_s))
names = D['names']
assert D['X'].shape[1] == len(names)
bad = [n for n in names if any(w in str(n) for w in BANNED)]
print('arm', ARM, 'features', A['features'], 'n', len(names), 'trees', len(models), 'used by a split', len(F.used))
print('banned-word check on feature names: %d names, with a banned word: %s' % (len(names), bad))
card = dict(arm=ARM, name=A['name'], state=os.path.basename(sp), sha256=FA.sha256(sp), features=A['features'], n_features=len(names), feature_names=[str(n) for n in names], sources=A['sources'], rounds=done, t=A['t'],
            label=A['label'], a=A['a'], objective=A['objective'], fold='all', fit_command=FA.fit_command(ARM), banned_in_names=bad, trees=len(models))
print('sha256', card['sha256'])

# permutation gain: loss = mean over positives of log(1 + sum over the pool's negatives e^(s_n - s_p)), a 0
X, y, pool = D['X'], D['y'], D['pool']
use = (y == 0) | (y == 1)
X, y, pool = X[use], y[use], pool[use]
starts = np.r_[0, np.nonzero(np.diff(pool))[0] + 1]
pos = y == 1


def loss(s):
    m = np.maximum.reduceat(s, starts)[pool]
    ez = np.exp(s - m)
    neg = np.add.reduceat(np.where(pos, 0.0, ez), starts)[pool]
    return float(np.log1p(neg[pos] / np.maximum(ez[pos], 1e-300)).mean())


base = loss(F.predict(X))
rng = np.random.default_rng(3)
gains = []
used = F.used
for k, j in enumerate(used):
    if time.time() - T0 > SECONDS:
        print('permutation stopped at the limit after', k, 'of', len(used), 'features; rerun with more seconds')
        break
    Xp = X.copy()
    Xp[:, j] = Xp[rng.permutation(len(Xp)), j]
    gains.append((loss(F.predict(Xp)) - base, str(names[j])))
gains.sort(reverse=True)
print('rows', len(X), 'positives', int(pos.sum()), 'pools', len(starts), 'loss %.4f' % base)
print('top 30 features by permutation gain (loss increase):')
for g, n in gains[:30]:
    print('   %.4f  %s' % (g, n))
card['permutation_top30'] = [(float(g), n) for g, n in gains[:30]]
card['permutation_features_checked'] = len(gains)

# cost of one scored node: about NCOST R120 nodes, features and one-row call together
if A['features'] == 'H':
    KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-dag-nodes-train50-final-8be414670/'
    sys.path.insert(0, KIT + 'policy')
    import policy as HP
ex = IO.excluded()
fs = sorted(f[:8] for d in IO.R120 for f in os.listdir(d) if f.endswith('.nodes.jsonl.zst'))
fs = [t for t in fs if t not in ex and os.path.exists(IO.TASKDIR + t + '.json')][::23]
want_names = [str(n) for n in names]
ms_sk, ms_fo, n = [], [], 0
import re
for t in fs:
    if time.time() - T0 > SECONDS or n >= NCOST:
        break
    path = next(d + t + '.nodes.jsonl.zst' for d in IO.R120 if os.path.exists(d + t + '.nodes.jsonl.zst'))
    N = [r for r in IO.read_nodes(path) if r.get('x_rows')]
    if not N:
        continue
    task = IO.load_task(t)
    ctx = FE.TaskCtx(task)
    hp = HP.Policy(task) if A['features'] == 'H' else None
    k = max(1, len(N) // (NCOST // len(fs) + 1))
    for r in N[::k][:NCOST // len(fs) + 1]:
        cl = r['clause'] or ''
        kind = cl[1:cl.index(' ')] if cl.startswith('(') and ' ' in cl else 'none'
        reads = len(re.findall(r'\(&f\d+', cl))
        t1 = time.perf_counter()
        if A['features'] == 'H':
            sn = _types.SimpleNamespace(id=r['token'], types=r['types'], table_types=r['table_types'], arity=r['arity'], depth=r['depth'], parents=r['parents'], clause=cl, rows=r['x_rows'], examples=r['examples'])
            hd = hp.feats(sn)
            x = np.array([hd.get(nm, np.nan) for nm in names], np.float32)
        else:
            d = FE.node_features(r['table_types'], r['x_rows'], cl, kind, r['depth'], reads, ctx, with_shape=(A['features'] == 'TS'))
            x = np.array([d[nm] for nm in want_names], np.float32)
        t2 = time.perf_counter()
        FO.Forest.predict_one(F, x)
        t3 = time.perf_counter()
        s = sum(float(m.predict(x[None])[0]) for m in models)
        t4 = time.perf_counter()
        ms_sk.append((t2 - t1 + t4 - t3) * 1000)
        ms_fo.append((t3 - t1) * 1000)
        n += 1
        if time.time() - T0 > SECONDS or n >= NCOST:
            break


def q(v):
    v = sorted(v)
    return 'mean %.2f ms, q50 %.2f, q99 %.2f, max %.1f' % (sum(v) / len(v), v[len(v) // 2], v[int(.99 * len(v))], v[-1]) if v else 'none'


print('cost of one scored node (features + one-row call), %d R120 nodes:' % n)
print('   sklearn, %d predict calls:  %s' % (len(models), q(ms_sk)))
print('   forest, trees walked together: %s' % q(ms_fo))
print('   budget: mean 8 ms, q99 60 ms (features and model together)')
card['cost'] = dict(nodes=n, sklearn=q(ms_sk), forest=q(ms_fo))
json.dump(card, open(FA.card_path(ARM), 'w'), indent=1)
print('wrote', FA.card_path(ARM), 'seconds', round(time.time() - T0, 1))
