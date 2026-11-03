"""Which table does a hole read? A conditional logit over the candidate tables, with weights on binned facts per situation.

  gold_tables_env.sh candidate_model.py tune

Candidates of an edge: the tables of gold's forms outside the reader and outside the forms that read the reader, directly or not. That scope is a fact of the DAG. It reads no form's place in gold's text. Every candidate is a gold table, so a pool's junk is absent.

Arms, by the keys they read:
  out         the candidate's cover of the output need, per reader kind. Reads no reader body, so a forward search has it
  hole        the candidate's fit to the masked atom, from the reader's body and columns
  holeb       the same with hole types from the lib signature alone, with no reader column
  hole+out    both, with the output cover crossed with whether the hole carries OUT's position or color

Baseline: uniform over the candidates, log2 of their count.
"""
import collections
import glob
import json
import math
import os
import sys
import time

import numpy as np
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import backward_edges as E  # noqa: E402
import next_form_facts as F  # noqa: E402
import next_form_model as M  # noqa: E402

LOG2 = math.log(2)
OUTKEYS = ('posj', 'pcj', 'colc', 'xg')
HOLEKEYS = ('fitl', 'fitc', 'arity', 'ckind')
HOLEB = ('fitl', 'arity', 'ckind')


def downstream(forms):
    rd = collections.defaultdict(set)
    for i, r in enumerate(forms):
        for x in r['reads']:
            if x[1] == 'relation' and x[2] is not None:
                rd[x[2]].add(i)
    out = {}
    for f in range(len(forms)):
        seen, todo = {f}, [f]
        while todo:
            for g in rd.get(todo.pop(), ()):
                if g not in seen:
                    seen.add(g)
                    todo.append(g)
        out[f] = seen
    return out


def bin4(x):
    return '0' if x <= 0 else '<.5' if x < .5 else '<1' if x < 1 else '1'


def gbin(x):
    return '<0' if x < 0 else '0' if x == 0 else '<.25' if x < .25 else '>=.25'


def fit_of(want, have):
    """Whether the known types of a hole fit in the candidate's column types, as multisets."""
    w = collections.Counter(t for t in want if t not in ('?', 'none'))
    if not w:
        return 'unknown'
    h = collections.Counter(E.norm_type(t) for t in have)
    miss = sum((w - h).values())
    return 'all' if miss == 0 else 'part' if miss < sum(w.values()) else 'none'


def table_bins(t, kind):
    return dict(posj=bin4(t['pos_rec']) + '/' + bin4(t['pos_prec']), pcj=bin4(t['pc_rec']) + '/' + bin4(t['pc_prec']), colc=bin4(t['col_cov']), xg=gbin(t['x_gain']), ckind=kind)


def cand_keys(arm, f, c, kind):
    """The key strings of candidate table c at an edge with facts f. Arm out reads only the reader's kind from f."""
    b = table_bins(c, kind)
    rk = f['b_rk']
    keys = dict(out=OUTKEYS, hole=HOLEKEYS, holeb=HOLEB, both=OUTKEYS + HOLEKEYS)[arm]
    if arm != 'out':
        carry = ('P' if f['b_outP'] == 'yes' else '') + ('C' if f['b_outC'] == 'yes' else '')
        dp = f['b_depth']
        nh = int(sum(1 for x in f['c_htypes'].split('+') if x != 'none'))
        b['fitl'] = fit_of(f['b_htypes'].split('+'), c['types'])
        b['fitc'] = fit_of(f['c_htypes'].split('+'), c['types'])
        a = len(c['types']) - nh
        b['arity'] = '<0' if a < 0 else str(min(a, 3))
    out = []
    for k in keys:
        if arm == 'out':
            out.append(k + '=' + rk + '|' + b[k])
        elif k in OUTKEYS:
            out.append(k + '=' + carry + '|' + rk + '|' + b[k])
        else:
            out.append(k + '=' + rk + '|' + dp + '|' + b[k])
    return out


def load_tables(split, distract=False):
    out = {}
    pat = '/candidates/candidate-rows-distract-%s-*.jsonl' if distract else '/candidates/candidate-rows-%s-*.jsonl'
    for p in glob.glob(HERE + pat % split):
        with open(p) as f:
            for x in f:
                r = json.loads(x)
                out[r['task']] = r
    return out


class Set:
    """Edges with their candidates. With distract, a task's foreign tables join the candidates."""

    def __init__(self, rows, tasks, tables, arm, distract=False, control=None):
        self.arm = arm
        self.keys = dict(out=OUTKEYS, hole=HOLEKEYS, holeb=HOLEB, both=OUTKEYS + HOLEKEYS)[arm]
        self.start = [0]
        self.y = []
        self.edge = []
        self.table = []
        strs = []
        down = {t: downstream(tasks[t]) for t in {r['task'] for r in rows}}
        rng = np.random.default_rng(3)
        for r in rows:
            tb = tables.get(r['task'])
            if not tb or not tb['tables']:
                continue
            nf = len(tasks[r['task']])
            ban = down[r['task']][r['reader']] if r['reader'] >= 0 else set()
            cand = [t for t in tb['tables'] if t['form'] < nf and t['form'] not in ban]
            gold = [i for i, t in enumerate(cand) if t['form'] == r['form'] and (t['ord'] == r['ord'] or r['ord'] is None)]
            if not gold:
                continue
            kinds = [tasks[r['task']][t['form']]['kind'] for t in cand]
            if distract:
                ex = tb.get('distract', [])
                cand = cand + ex
                kinds = kinds + [t.get('kind') or 'RULE' for t in ex]
            for c, k in zip(cand, kinds):
                strs.append(cand_keys(arm, r['fact'], c, k))
                self.table.append((c['form'], c['ord']))
            self.start.append(self.start[-1] + len(cand))
            self.y.append(int(rng.integers(len(cand))) if control else gold[0])
            self.edge.append(r)
        self.strs = strs
        self.start = np.array(self.start)
        self.y = np.array(self.y)
        self.n = len(self.y)
        self.seg = np.repeat(np.arange(self.n), np.diff(self.start))
        self.fold = np.array([M.fold_of(r['task']) for r in self.edge])

    def encode(self, vocab=None):
        grow = vocab is None
        vocab = vocab if vocab is not None else {}
        X = np.zeros((len(self.strs), len(self.keys)), dtype=np.int64)
        for i, row in enumerate(self.strs):
            for j, key in enumerate(row):
                g = vocab.get(key)
                if g is None:
                    if grow:
                        g = vocab[key] = len(vocab)
                    else:
                        g = -1
                X[i, j] = g
        return X, vocab


def seg_logp(z, seg, start):
    n = len(start) - 1
    m = np.full(n, -np.inf)
    np.maximum.at(m, seg, z)
    e = np.exp(z - m[seg])
    s = np.zeros(n)
    np.add.at(s, seg, e)
    return z - m[seg] - np.log(s)[seg], e / s[seg]


def fit(X, seg, start, y, nv, keep, l2):
    """Weights by L-BFGS, on the edges in keep."""
    sel = keep[seg]
    Xs = X[sel]
    new = np.full(len(keep), -1)
    new[keep] = np.arange(keep.sum())
    sg = new[seg[sel]]
    counts = np.diff(start)[keep]
    st = np.concatenate([[0], np.cumsum(counts)])
    gold = st[:-1] + y[keep]
    ok = Xs >= 0
    n = int(keep.sum())

    def f(w):
        z = (w[np.maximum(Xs, 0)] * ok).sum(1)
        lp, p = seg_logp(z, sg, st)
        loss = -lp[gold].sum() / n + l2 * (w ** 2).sum()
        g = np.zeros(nv)
        for j in range(Xs.shape[1]):
            np.add.at(g, Xs[ok[:, j], j], p[ok[:, j]])
            np.add.at(g, Xs[gold, j][ok[gold, j]], -1.0)
        return loss, g / n + 2 * l2 * w

    return minimize(f, np.zeros(nv), jac=True, method='L-BFGS-B', options=dict(maxiter=80)).x


def score(w, X):
    return (w[np.maximum(X, 0)] * (X >= 0)).sum(1)


def read_bits(z, s):
    lp, _ = seg_logp(z, s.seg, s.start)
    gold = s.start[:-1] + s.y
    bits = -lp[gold] / LOG2
    base = np.log2(np.diff(s.start))
    g = z[gold]
    rank = np.zeros(s.n)
    np.add.at(rank, s.seg, z > g[s.seg])
    return bits, base, rank


def fit_rows():
    tasks = F.load('fit')
    libs = json.load(open(HERE + '/top-libs.json'))
    rows, _ = E.edge_rows('fit', tasks, libs)
    return tasks, [r for r in rows if r['primary']]


def tune():
    t0 = time.time()
    tasks, rows = fit_rows()
    tables = load_tables('fit')
    print('rows', len(rows), 'task tables', len(tables), round(time.time() - t0, 1), flush=True)
    out = {}
    for arm in ('out', 'hole', 'both'):
        s = Set(rows, tasks, tables, arm)
        X, vc = s.encode()
        print(arm, 'edges', s.n, 'candidates', len(s.seg), 'keys', len(vc), round(time.time() - t0, 1), flush=True)
        best = None
        for l2 in (1e-4, 1e-3):
            z = np.zeros(len(s.seg))
            for k in range(5):
                w = fit(X, s.seg, s.start, s.y, len(vc), s.fold != k, l2)
                at = s.fold[s.seg] == k
                z[at] = score(w, X[at])
            bits, base, rank = read_bits(z, s)
            d = dict(l2=l2, uniform=round(float(base.mean()), 3), model=round(float(bits.mean()), 3), top1=round(float((rank == 0).mean()), 3), top5=round(float((rank < 5).mean()), 3))
            print(arm, d, round(time.time() - t0, 1), flush=True)
            if best is None or d['model'] < best['model']:
                best = d
        dp = np.array([min(r['depth'], 4) for r in s.edge])
        out[arm] = dict(best=best, edges=s.n)
        json.dump(out, open(HERE + '/candidate-tune.json', 'w'), indent=1)


if __name__ == '__main__':
    tune()
