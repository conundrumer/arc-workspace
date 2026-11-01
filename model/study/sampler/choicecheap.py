"""choicecheap: a harness for a cheap model of gold's column, column-stop, value, field and operand picks (choices.jsonl.zst rows of
sample2_choice.py CHOICE_ROWS=1), with pluggable features.  The row fields and the mask are in choicefeat.py's docstring.

score(option) = beta * decision function of sklearn HistGradientBoostingClassifier (is-gold) over the option's features, which include
'logp' (log of P's share).  A pick is a softmax over its row's options (the STOP of a column pick is one of them).
Features are functions fn(row, option) -> {name: float}; a plugin file (--plugin f.py) defines FEATURE_FUNCS = {'set': fn}, and a set is
used by listing it in --feats (default base cols val).

  choicecheap.py --train runC3_dev --test runC3_holdout --save-model choice.pkl
  choicecheap.py --train runC3_dev --test runC3_holdout --phases cols fcol val fval op stop --save-model choice_stop.pkl
  choicecheap.py --train runC2_dev --test runC2_holdout --feats base cols val dag --plugin dag.py --save-bits bits_dag.npz
  choicecheap.py --merge bits_a.npz bits_b.npz --test runC2_holdout    # one table from saved test bits
The report: mean test bits per gold pick under P and under the model, by phase, point group and k; and, at RULE depth 3+, the mean
bits per clause (the sum over its picks) and the bits the model saves per clause.  Use from the sampler:  choicefeat.Scorer(path).f(row).
"""
import argparse
import collections
import json
import os
import pickle
import random
import sys
import time
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sampler_paths as P  # noqa: E402
sys.path.append(P.CODE)
from judge3.framed_jsonl import iter_json  # noqa: E402

import choicefeat as CF  # noqa: E402

LN2 = np.log(2)
HERE = os.path.dirname(os.path.abspath(__file__))
GROUPS = ['DET', 'RULE depth 1', 'RULE depth 2', 'RULE depth 3+', 'INIT port', 'output']
PHASES = list(CF.DEFAULT_PHASES)  # the phases to train on and report (--phases)


EXCLUDE = set()  # tasks whose rows are left out of train and test (--exclude)
KEEP = CF.relfeat.name_filter('')  # the feature names a fit may use (--keep-names)


def rows_of(d):
    p = d if d.endswith('.zst') else os.path.join(d, 'choices.jsonl.zst')
    for r in iter_json(p):
        if r.get('task') not in EXCLUDE:
            yield r


class Data:
    """Rows streamed from run dirs: the masked rows' option features as a dense matrix (an option a line)."""

    def __init__(self, fnames):
        self.fnames = fnames
        self.dicts, self.start, self.gold, self.meta = [], [0], [], []

    def add(self, row):
        if CF.phase_of(row) not in PHASES:
            return False
        toks = [o['tok'] for o in row['options']]
        if row['gold'] not in toks:
            return False
        ds = CF.option_dicts(CF.mask_row(row), self.fnames)
        self.dicts += ds
        self.start.append(self.start[-1] + len(ds))
        self.gold.append(toks.index(row['gold']))
        self.meta.append(dict(task=row['task'], phase=CF.phase_of(row), grp=(row.get('point_group') or {}).get('point_group'), k=row['k'],
                              where=row.get('where'), place=row.get('place'), kind=(row.get('point_group') or {}).get('kind'), gold_stop=row['gold'] == 'STOP', clause='%s|%s|%s' % (row['task'], row['case'], row['point'])))
        return True

    def finish(self, names=None, min_count=1):
        """names: the dense columns (a test set takes the train set's); else every name seen in >= min_count options, 'logp' first."""
        if names is None:
            cnt = collections.Counter(n for d in self.dicts for n in d)
            names = ['logp'] + sorted(n for n, c in cnt.items() if n != 'logp' and c >= min_count and KEEP(n))
        ix = {n: j for j, n in enumerate(names)}
        X = np.zeros((len(self.dicts), len(names)), np.float32)
        for i, d in enumerate(self.dicts):
            for n, v in d.items():
                j = ix.get(n)
                if j is not None:
                    X[i, j] = v
        self.names, self.X = names, X
        self.start = np.array(self.start)
        self.nopt = np.diff(self.start)
        self.row_of = np.repeat(np.arange(len(self.nopt)), self.nopt)
        self.y = np.zeros(len(X), bool)
        self.y[self.start[:-1] + np.array(self.gold)] = True
        self.dicts = None
        return self

    @property
    def n(self):
        return len(self.nopt)


def n_lines(d):
    """The rows in a run directory's choices file, from its frame index, else None."""
    p = d if d.endswith('.zst') else os.path.join(d, 'choices.jsonl.zst')
    try:
        with open(p + '.idx.jsonl') as f:
            next(f)
            return sum(json.loads(x)['line_count'] for x in f if x.endswith('\n'))
    except (OSError, StopIteration, ValueError):
        return None


def stream(dirs, fnames, label, max_rows=0):
    D = Data(fnames)
    t0, done = time.time(), 0
    total = sum(n_lines(d) or 0 for d in dirs)
    for d in dirs:
        for r in rows_of(d):
            done += 1
            if max_rows and done > max_rows:
                break
            D.add(r)
            if done % 10000 == 0:
                rate = done / (time.time() - t0)
                print('%s: %d rows, %.0f rows/s%s' % (label, done, rate, ', eta %.0fs' % ((total - done) / rate) if total > done else ''), flush=True)
    print('%s: %d picks in %.0fs' % (label, len(D.meta), time.time() - t0), flush=True)
    return D


def bits(D, s, rows=None):
    """Bits of each pick's gold under the softmax of scores s (one per option line); rows: the picks to score, else all."""
    mx = np.full(D.n, -np.inf)
    np.maximum.at(mx, D.row_of, s)
    e = np.exp(s - mx[D.row_of])
    z = np.zeros(D.n)
    np.add.at(z, D.row_of, e)
    lg = s[D.start[:-1] + np.array(D.gold)] - mx - np.log(z)
    return -lg / LN2


def is_dev(task):
    return zlib.crc32(('dev' + task).encode()) % 6 == 0


def dev_rows(meta):
    """The picks of the dev tasks (a sixth, by hash); where the train tasks hold none, a random sixth of them."""
    dev = np.array([is_dev(m['task']) for m in meta])
    if not dev.any() or dev.all():
        tasks = sorted({m['task'] for m in meta})
        pick = set(random.Random(0).sample(tasks, max(1, len(tasks) // 6)))
        dev = np.array([m['task'] in pick for m in meta])
    return dev


def fit(Dtr, a):
    from sklearn.ensemble import HistGradientBoostingClassifier
    dev_row = dev_rows(Dtr.meta)
    in_dev = dev_row[Dtr.row_of]
    m = HistGradientBoostingClassifier(max_iter=a.hgb_iters, learning_rate=a.hgb_lr, max_depth=a.hgb_depth, min_samples_leaf=a.hgb_leaf,
                                       early_stopping=False, l2_regularization=1.0, random_state=0)
    t0 = time.time()
    m.fit(Dtr.X[~in_dev], Dtr.y[~in_dev])
    sub = SubData(Dtr, dev_row)
    best = (1e9, 0, 1.0)
    for st, d in enumerate(m.staged_decision_function(sub.X), 1):
        if st % 10 and st != a.hgb_iters:
            continue
        for beta in (0.5, 1.0):
            v = bits(sub, d * beta).mean()
            if v < best[0]:
                best = (v, st, beta)
    print('hgb: %d options x %d features fit, dev %.3f bits at stage %d beta %.1f (P %.3f) (%.0fs)' % (
        (~in_dev).sum(), Dtr.X.shape[1], best[0], best[1], best[2], bits(sub, sub.X[:, 0]).mean(), time.time() - t0), flush=True)
    return m, best


class SubData:
    """The picks of D in `rows` (a bool mask), as a Data."""

    def __init__(self, D, rows):
        keep = np.nonzero(rows)[0]
        sel = np.isin(D.row_of, keep)
        self.X, self.y = D.X[sel], D.y[sel]
        self.nopt = D.nopt[keep]
        self.start = np.concatenate([[0], np.cumsum(self.nopt)])
        self.row_of = np.repeat(np.arange(len(keep)), self.nopt)
        self.gold = [int(np.argmax(self.y[self.start[i]:self.start[i + 1]])) for i in range(len(keep))]
        self.meta = [D.meta[i] for i in keep]
        self.n = len(keep)


def test_scores(m, D, stage, beta):
    for st, d in enumerate(m.staged_decision_function(D.X), 1):
        if st == stage:
            return d * beta


def subsets(meta):
    """(name, mask) of the report's rows."""
    out = [('all', np.ones(len(meta), bool))]
    for ph in PHASES:
        out.append(('phase ' + ph, np.array([m['phase'] == ph for m in meta])))
    out += [('cols, gold column', np.array([m['phase'] == 'cols' and not m['gold_stop'] for m in meta])),
            ('cols, gold STOP', np.array([m['phase'] == 'cols' and m['gold_stop'] for m in meta])),
            ('stop, gold GO', np.array([m['phase'] == 'stop' and not m['gold_stop'] for m in meta])),
            ('stop, gold STOP', np.array([m['phase'] == 'stop' and m['gold_stop'] for m in meta]))]
    for g in GROUPS:
        out.append(('group ' + g, np.array([m['grp'] == g for m in meta])))
    for kd in ('RULE', 'DET', 'INIT'):
        out.append(('form ' + kd, np.array([m['kind'] == kd for m in meta])))
    for w in ('body', 'branch', 'nested', 'ALL'):  # where in the clause, for rows that live_rows.py writes
        out.append(('where ' + w, np.array([m['where'] == w for m in meta])))
    for pl in ('key', 'port'):
        out.append(('place ' + pl, np.array([m['place'] == pl for m in meta])))
    for k in (1, 2, 3):
        out.append(('k %d%s' % (k, '+' if k == 3 else ''), np.array([m['k'] >= k if k == 3 else m['k'] == k for m in meta])))
    d3 = np.array([m['grp'] == 'RULE depth 3+' for m in meta])
    for ph in PHASES:
        out.append(('RULE depth 3+, ' + ph, d3 & np.array([m['phase'] == ph for m in meta])))
    return out


def table(meta, cols, title):
    names = list(cols)
    print('\n' + title)
    print('%-28s %6s ' % ('subset', 'n') + ' '.join('%12s' % n[:12] for n in names))
    for name, mk in subsets(meta):
        if mk.sum():
            print('%-28s %6d ' % (name, mk.sum()) + ' '.join('%12.2f' % cols[n][mk].mean() for n in names))
    d3 = [i for i, m in enumerate(meta) if m['grp'] == 'RULE depth 3+']
    cl = collections.defaultdict(list)
    for i in d3:
        cl[meta[i]['clause']].append(i)
    if cl:
        tot = {n: np.mean([cols[n][ix].sum() for ix in cl.values()]) for n in names}
        print('RULE depth 3+ clauses: %d, mean bits per clause (sum over its picks): ' % len(cl) + ', '.join('%s %.1f' % (n, tot[n]) for n in names))
        for n in names:
            if n != 'P':
                print('  mean bits saved per clause vs P, %s: %.2f' % (n, tot['P'] - tot[n]))


def main():
    global KEEP
    ap = argparse.ArgumentParser()
    ap.add_argument('--train', nargs='+', default=[HERE + '/runC_dev'])
    ap.add_argument('--test', default=HERE + '/runC_holdout')
    ap.add_argument('--feats', nargs='+', default=['base', 'cols', 'val'])
    ap.add_argument('--plugin', default='')
    ap.add_argument('--exclude', default='', help='a file of tasks, one a line, whose rows are left out of train and test')
    ap.add_argument('--keep-names', default='', help='a file of feature names, one a line; a name that ends in * is a prefix. Only these names (and logp) are used')
    ap.add_argument('--phases', nargs='+', default=list(CF.DEFAULT_PHASES), choices=CF.PHASES,
                    help="the phases to train on and report; 'stop' is the atom stop. The saved model steers only these.")
    ap.add_argument('--min-count', type=int, default=20, help='a dense feature is kept when >= this many train options fire it')
    ap.add_argument('--hgb-iters', type=int, default=150)
    ap.add_argument('--hgb-lr', type=float, default=0.1)
    ap.add_argument('--hgb-depth', type=int, default=5)
    ap.add_argument('--hgb-leaf', type=int, default=40)
    ap.add_argument('--threads', type=int, default=2, help="OpenMP threads of the tree's fit (many on a loaded machine slow it)")
    ap.add_argument('--max-rows', type=int, default=0)
    ap.add_argument('--merge', nargs='+', default=[], help='print the table of saved .npz columns and exit')
    ap.add_argument('--save-bits', default='')
    ap.add_argument('--save-model', default='')
    a = ap.parse_args()
    PHASES[:] = a.phases
    KEEP = CF.relfeat.name_filter(a.keep_names)
    if a.exclude:
        EXCLUDE.update(open(a.exclude).read().split())
    from threadpoolctl import threadpool_limits
    threadpool_limits(limits=a.threads)
    if a.plugin:
        CF.load_plugin(a.plugin)
    if a.merge:
        te = stream([a.test], a.feats, 'test', a.max_rows)
        cols = {}
        for f in a.merge:
            z = np.load(f)
            for k in z.files:
                cols.setdefault(k, z[k])
        table(te.meta, cols, 'TEST (%s): mean bits per gold pick' % a.test)
        return
    Dtr = stream(a.train, a.feats, 'train', a.max_rows).finish(None, a.min_count)
    Dte = stream([a.test], a.feats, 'test', a.max_rows).finish(Dtr.names)
    print('features: %d; train %d options, test %d' % (len(Dtr.names), len(Dtr.X), len(Dte.X)), flush=True)
    m, (v, st, beta) = fit(Dtr, a)
    cols = {'P': bits(Dte, Dte.X[:, 0])}
    cols['hgb'] = bits(Dte, test_scores(m, Dte, st, beta))
    table(Dte.meta, cols, 'TEST (%s): mean bits per gold pick' % a.test)
    if a.save_bits:
        np.savez(a.save_bits, **cols)
    if a.save_model:
        m._predictors = m._predictors[:st]  # keep the stage that dev chose, so decision_function is that stage
        old = pickle.load(open(a.save_model, 'rb')) if os.path.exists(a.save_model) else {}
        old.update(hgb=dict(groups_used=a.feats, model=m, names=Dtr.names, beta=beta, stage=st), plugin=a.plugin or None, phases=list(a.phases))
        with open(a.save_model, 'wb') as f:
            pickle.dump(old, f)
        print('saved', a.save_model)


if __name__ == '__main__':
    main()
