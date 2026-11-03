"""Loads the feature rows of N600 and S120 into one table of pools. Shared by the fit, tune and read scripts.

  D = load(['n600', 's120'], feats='T'|'TS'|'H'|'D')   # D['X'] float32, D['y'] int8, D['pool'] int, D['task'] str per pool, ...
Feature sets: T all groups but form shape, TS all, H the hand reader's 87, D the Depth group only.
A fold's tasks leave every source: pass exclude=set of task ids.
"""
import glob, json, os, sys
import numpy as np

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'  # the data folder
sys.path.insert(0, HERE)
import features_node_feats as FE

N600_TASKS = json.load(open('/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-dag-nodes-train50-final-8be414670/manifest.json'))['task_set']


def folds(k=5):
    """Task folds of N600: the sorted task list, task i in fold i % k."""
    ts = sorted(N600_TASKS)
    return [ts[i::k] for i in range(k)]


def s120_fold_map(k=5):
    """S120 task -> fold. A task that is also an N600 task keeps its N600 fold. The others, sorted by task id, go to fold i % k."""
    from features_node_io import s120_tasks
    nf = {t: i for i, f in enumerate(folds(k)) for t in f}
    ts = s120_tasks(int(os.environ.get('S120_N', 200)))
    m = {t: nf[t] for t in ts if t in nf}
    for i, t in enumerate(sorted(t for t in ts if t not in nf)):
        m[t] = i % k
    return m


def cols_of(feats, names, hand_names=None):
    if feats == 'H':
        return None
    sel = {'T': FE.names_T(), 'TS': list(FE.NAMES), 'D': FE.names_depth()}[feats]
    ix = {n: i for i, n in enumerate(names)}
    return [ix[n] for n in sel], sel


def load_task(src, task, feats):
    """(X, meta dict) of one task, or None if it has no rows."""
    if src == 'n600':
        ps = sorted(glob.glob(HERE + 'n600-rows/%s.part*.npz' % task))
        if not ps:
            return None
        zs = [np.load(p) for p in ps]
        meta = np.vstack([z['meta'] for z in zs])
        names = list(zs[0]['names'])
        Xf = np.vstack([z['X'] for z in zs])
        Hf = np.vstack([z['H'] for z in zs])
        cols = {c: meta[:, i] for i, c in enumerate(zs[0]['meta_cols'])}
        m = dict(node=cols['node'].astype(np.int64), y=cols['y'].astype(np.int8), kind=cols['kind'].astype(np.int8), depth=cols['form_depth'].astype(np.int16), plain=cols['plain'].astype(np.int64),
                 score=cols['score'], rowcheck=cols['rowcheck'].astype(np.int8), form=cols['form'].astype(np.int64), age=cols['age'].astype(np.int64))
        m['gold'] = sum((json.loads(str(z['gold'][0])) for z in zs), [])
    else:
        p = HERE + '%s-rows/%s.npz' % (src, task)
        if not os.path.exists(p):
            return None
        z = np.load(p)
        names = list(z['names'])
        Xf, Hf = z['X'], z['H']
        c = {k: z['meta'][:, i] for i, k in enumerate(z['meta_cols'])}
        m = dict(node=c['token'].astype(np.int64), y=c['y'].astype(np.int8), kind=c['kind'].astype(np.int8), depth=c['depth'].astype(np.int16), plain=c['plain'].astype(np.int64),
                 score=np.full(len(Xf), np.nan), rowcheck=np.zeros(len(Xf), np.int8), form=np.zeros(len(Xf), np.int64), age=c['draw'].astype(np.int64))
    if feats == 'H':
        X = Hf
        sel = list(zs[0]['hand_names']) if src == 'n600' else list(z['hand_names'])
    else:
        ci, sel = cols_of(feats, names)
        X = Xf[:, ci]
    return X, m, sel


def load(srcs, feats, exclude=(), only_tasks=None, tasks_by_src=None, exclude_src=None):
    """Concatenated rows of the sources. Pools are (source, task). exclude: task ids left out of every source. exclude_src: {source: task ids left out of that source}."""
    Xs, M, pools, sel = [], [], [], None
    from features_node_io import s120_tasks
    for src in srcs:
        ts = sorted(N600_TASKS) if src == 'n600' else s120_tasks(int(os.environ.get('S120_N', 200)))
        for t in ts:
            if t in exclude or (exclude_src and t in exclude_src.get(src, ())) or (only_tasks is not None and t not in only_tasks):
                continue
            r = load_task(src, t, feats)
            if r is None:
                continue
            X, m, sel = r
            pools.append((src, t, len(X)))
            Xs.append(X.astype(np.float32, copy=False))
            M.append(m)
    pool = np.concatenate([np.full(n, i, np.int32) for i, (_, _, n) in enumerate(pools)]) if pools else np.zeros(0, np.int32)
    out = dict(X=np.vstack(Xs) if Xs else np.zeros((0, 0), np.float32), pool=pool, pools=pools, names=sel)
    for k in ('node', 'y', 'kind', 'depth', 'plain', 'score', 'rowcheck', 'form', 'age'):
        out[k] = np.concatenate([m[k] for m in M]) if M else np.zeros(0)
    out['gold'] = sum((m['gold'] if 'gold' in m else [[]] * len(m['y']) for m in M), [])
    return out
