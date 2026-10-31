"""A logit for the atom stop (choices rows of phase `atom stop`) with structural features: P's log odds, the atom
index, the point's kind, and the fresh labels of the clause so far that no other site reads. Trained on TRAIN, scored on
TEST in bits per stop against P. python stopfit.py TRAIN_CHOICES_RUN TEST_CHOICES_RUN"""
import math
import re
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sampler_paths  # noqa: E402,F401
from judge3.framed_jsonl import iter_json  # noqa: E402

NAMES = ['p_logodds', 'bias', 'k', 'k1', 'output', 'det', 'port', 'unread', 'unread0', 'labels']


def unread(text):
    fresh = re.findall(r'\*(\w+)', text)
    return sum(1 for lab in fresh if len(re.findall(r'(?<![\w*])%s\b' % re.escape(lab), text)) == 0)


def load(run):
    out = []
    for r in iter_json(run + '/choices.jsonl.zst'):
        if r['phase'] != 'atom stop':
            continue
        ps = {o['tok']: o['p'] for o in r['options']}
        if not 0 < ps['STOP'] < 1:
            continue
        pg = r.get('point_group') or {}
        text = ' '.join(r['prefix'] + [r['gold_atom'] or ''])
        u = unread(text)
        f = [math.log(ps['STOP'] / ps['GO']), 1.0, r['k'], r['k'] == 1, bool(pg.get('output')), pg.get('kind') == 'Det',
             pg.get('point_group') == 'INIT port', u, u == 0, len(re.findall(r'\*\w+', text))]
        out.append((np.array(f, dtype=float), r['gold'] == 'STOP'))
    return out


def bits(w, rows):
    tot = 0.0
    for x, y in rows:
        z = x @ w
        p = 1 / (1 + math.exp(-z))
        tot += -math.log2(p if y else 1 - p)
    return tot / len(rows)


def fit(rows, steps=500, lr=0.3, l2=1e-3):
    w = np.zeros(len(NAMES))
    w[0] = 1.0
    X = np.array([x for x, _ in rows])
    Y = np.array([y for _, y in rows], dtype=float)
    for _ in range(steps):
        p = 1 / (1 + np.exp(-(X @ w)))
        w -= lr * (X.T @ (p - Y) / len(rows) + l2 * w)
    return w


train, test = load(sys.argv[1]), load(sys.argv[2])
p_only = np.zeros(len(NAMES))
p_only[0] = 1.0
print('atom stops: train %d, test %d (%.0f%% STOP)' % (len(train), len(test), 100 * sum(y for _, y in test) / len(test)))
print('P alone: train %.3f, test %.3f bits per stop' % (bits(p_only, train), bits(p_only, test)))
w = fit(train)
print('fit:     train %.3f, test %.3f bits per stop' % (bits(w, train), bits(w, test)))
print(' '.join('%s=%.2f' % (n, x) for n, x in zip(NAMES, w)))
