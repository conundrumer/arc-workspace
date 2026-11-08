"""Dev labeling layer: the novelty of each table, from the worlds that judge_worlds.py writes. Not model input.

    python novelty.py OUT_DIR [JOBS] [TASKS_FILE]

Every derived table is a function of the evidence, so no table adds Shannon information to it. What a table can add is usable information:
what a bounded observer, which sees each table only through its features, could not compute from what it saw before. A table's novelty is
the share of the variance of its features, across the task's worlds, that a bounded predictor does not recover from the features of the
input grid and of every table upstream of it.

- Worlds: the task's own examples and its input variants. A world counts for a table where the table and each table its query reads have
  rows: existence, the one precondition every query has.
- A table's reads: the tables and the input grid that its form reads, and for an output port of an instance, the instance's input ports.
  Upstream: the reads, through any number of reads, and the input grid.
- Observations: input features, descriptions and features that read the train output left out. A feature of the table counts where it
  varies in at least MINORITY worlds.
- Predictors: ridge regression and an extra-trees ensemble, each scored by 5-fold cross-validation; per feature, the better R².
- Novelty: the mean, over the table's features, of 1 - max(0, R²). The null: the same predictors with the worlds shuffled.

So novelty is relative to the feature library: a query that computes what the features already perceive, such as the components of a cell
set, is not novel, and one whose result shows what its inputs' features do not show is novel to that degree.

Writes OUT_DIR/novelty.jsonl, one line per task; a restart skips the tasks written.
"""
import json
import random
import sys
import time
import warnings
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import analyze as A  # noqa: E402
import jsonl as J  # noqa: E402

MIN_WORLDS, MAX_WORLDS, MAX_CATS, MINORITY = 30, 300, 12, 10


def obs_of(world):
    """{owner: {feature: value}}: each table's input features, and the input grid's."""
    out = {}
    for k, v in world['features'].items():
        o, _, f = k.partition('|')
        if f.endswith(' describe') or A.is_output(k):
            continue
        out.setdefault(o, {})[f] = v
    out['input'] = {f: v for f, v in world['base']['input'].items() if not A.is_output('input|' + f)}
    return out


def reads_of(t, rd, names, ports):
    node, _, port = t.partition('.')
    form = {u for u in rd.get(node, ()) if u in names and u != t} | ({'input'} if 'input' in rd.get(node, ()) else set())
    ins = set(ports.get(node, ()))
    if port and port not in ins:
        return form | {u for u in names if u.startswith(node + '.') and u.partition('.')[2] in ins}
    return form


def upstream_of(t, rd, names, ports):
    seen, todo = set(), [t]
    while todo:
        for u in reads_of(todo.pop(), rd, names, ports):
            if u not in seen and u != t:
                seen.add(u)
                if u != 'input':
                    todo.append(u)
    return seen | {'input'}


def matrix(dicts):
    """(array, names): numbers and bools as floats, None as NaN, a category as indicator columns of its most frequent values."""
    keys = sorted({k for d in dicts for k in d})
    cols, names = [], []
    for k in keys:
        vals = [d.get(k) for d in dicts]
        if all(v is None or isinstance(v, (bool, int, float)) for v in vals):
            cols.append([np.nan if v is None else float(v) for v in vals])
            names.append(k)
        else:
            for c, _ in Counter(v for v in vals if isinstance(v, str)).most_common(MAX_CATS):
                cols.append([1.0 if v == c else 0.0 for v in vals])
                names.append('%s=%s' % (k, c))
    return (np.array(cols, dtype=float).T, names) if cols else (np.zeros((len(dicts), 0)), [])


def varying(X, names, minority=1):
    keep = []
    for i in range(X.shape[1]):
        col = X[:, i]
        if np.isfinite(col).sum() < 5 or np.nanstd(col) <= 1e-9:
            continue
        _, counts = np.unique(np.where(np.isfinite(col), col, -9e9), return_counts=True)
        if len(col) - counts.max() >= minority:
            keep.append(i)
    return X[:, keep], [names[i] for i in keep]


def cv_r2(X, Y, seed=0):
    """Per column of Y, the better held-out R² of ridge regression and extra trees, and each one's."""
    from sklearn.ensemble import ExtraTreesRegressor
    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import KFold
    Xl = np.nan_to_num(X, nan=0.0)
    miss = np.isnan(X).astype(float)
    Xr = np.hstack([Xl, np.sign(Xl) * np.log1p(np.abs(Xl)), miss[:, miss.std(axis=0) > 0]])
    sd = Xr.std(axis=0)
    sd[sd == 0] = 1
    Xr = (Xr - Xr.mean(axis=0)) / sd
    Xt = np.nan_to_num(X, nan=-1e6)
    Yf = np.where(np.isnan(Y), np.nanmean(Y, axis=0), Y)
    ys = Yf.std(axis=0)
    ys[ys == 0] = 1
    Ys = (Yf - Yf.mean(axis=0)) / ys
    pr, pt = np.zeros_like(Ys), np.zeros_like(Ys)
    for tr, te in KFold(5, shuffle=True, random_state=seed).split(Xr):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            pr[te] = RidgeCV(alphas=np.logspace(-2, 3, 11)).fit(Xr[tr], Ys[tr]).predict(Xr[te]).reshape(pr[te].shape)
            if Xt.shape[1]:
                e = ExtraTreesRegressor(n_estimators=60, min_samples_leaf=3, max_features=0.3, random_state=seed, n_jobs=1).fit(Xt[tr], Ys[tr])
                pt[te] = e.predict(Xt[te]).reshape(pt[te].shape)
    ss = ((Ys - Ys.mean(axis=0)) ** 2).sum(axis=0)
    ss[ss == 0] = 1
    r2r = 1 - ((Ys - pr) ** 2).sum(axis=0) / ss
    r2t = 1 - ((Ys - pt) ** 2).sum(axis=0) / ss
    return np.maximum(r2r, r2t), r2r, r2t


def task_rows(args):
    out_dir, task = args
    recs = list(J.records(Path(out_dir) / (task + '.worlds.jsonl')))
    base = next((r for r in recs if r['id'] == 'base'), None)
    if base is None:
        return None
    rd = {k: set(v) for k, v in base['reads'].items()}
    ports = base.get('instance_inputs', {})
    names = {n for n in base['tables'] if n not in ('ex_input', 'ex_output')}
    own = [obs_of(w) for w in base['examples'].values()]
    worlds = [r for r in recs if r['id'] != 'base' and 'error' not in r]
    random.Random(task).shuffle(worlds)
    wobs = [obs_of(r) for r in worlds]
    rows = []
    for t in sorted(names):
        reads = reads_of(t, rd, names, ports)
        rec = dict(t=t, reads=sorted(reads))
        if not reads:
            rows.append(dict(rec, status='reads no table'))
            continue

        def counted(o):
            return t in o and o[t].get('rows', 0) > 0 and all(u == 'input' or o.get(u, {}).get('rows', 0) > 0 for u in reads)
        ws = [o for o in own if t in o] + [o for o in wobs if counted(o)][:MAX_WORLDS]
        rec['worlds'] = len(ws)
        if len(ws) < MIN_WORLDS:
            rows.append(dict(rec, status='too few worlds'))
            continue
        Y, yn = varying(*matrix([o[t] for o in ws]), minority=MINORITY)
        rec['targets'] = len(yn)
        if not yn:
            rows.append(dict(rec, status='no feature varies'))
            continue
        ups = upstream_of(t, rd, names, ports)
        X, xn = varying(*matrix([{'%s|%s' % (u, f): v for u in sorted(ups) for f, v in o.get(u, {}).items()} for o in ws]))
        rec.update(upstream=len(ups), inputs=len(xn))
        if xn:
            r2, r2r, r2t = cv_r2(X, Y)
            r2n = cv_r2(X[np.random.RandomState(1).permutation(len(ws))], Y)[0]
        else:
            r2 = r2r = r2t = r2n = np.zeros(len(yn))
        fvu = 1 - np.clip(r2, 0, 1)
        rec.update(status='tested', novelty=float(fvu.mean()), novelty_max=float(fvu.max()), null_novelty=float((1 - np.clip(r2n, 0, 1)).mean()),
                   linear_share=float((r2r >= r2t).mean()), unpredicted=[[yn[i], float(fvu[i])] for i in np.argsort(-fvu)[:5]])
        rows.append(rec)
    return dict(task=task, tables=rows)


def main(out_dir, jobs=4, tasks_file=None):
    out = Path(out_dir) / 'novelty.jsonl'
    done = {json.loads(l)['task'] for l in out.read_text().splitlines()} if out.exists() else set()
    tasks = open(tasks_file).read().split() if tasks_file else sorted({p.name.split('.')[0] for p in Path(out_dir).glob('*.worlds.jsonl*')})
    todo = [t for t in tasks if t not in done]
    t0 = time.time()
    with Pool(jobs) as pool, open(out, 'a') as f:
        for i, res in enumerate(pool.imap_unordered(task_rows, [(out_dir, t) for t in todo]), 1):
            if res:
                f.write(json.dumps(res) + '\n')
                f.flush()
            el = time.time() - t0
            print('%s [%d/%d, %.0f s, eta %.0f s]' % (res and res['task'], i, len(todo), el, el / i * (len(todo) - i)), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 4, sys.argv[3] if len(sys.argv) > 3 else None)
