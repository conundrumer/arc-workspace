"""Prints every fixed form's measures, with Clopper-Pearson 95% limits on the positive rate, for the record and the results text.

  features_table.py
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'


def tail(k, n, p):
    """P(X <= k) for X binomial."""
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def cp(k, n):
    lo = 0.0
    if k:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = (a + b) / 2
            if 1 - tail(k - 1, n, m) < .025:
                a = m
            else:
                b = m
        lo = a
    hi = 1.0
    if k < n:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = (a + b) / 2
            if tail(k, n, m) > .025:
                a = m
            else:
                b = m
        hi = a
    return round(lo, 3), round(hi, 3)


def show(path):
    d = json.load(open(HERE + path))
    print(d['meta'])
    for n, e in d['forms'].items():
        r = e['rate']
        p = e['pos']
        pk, pn = r['positive']
        print(n, {g: v for g, v in r.items()}, 'same', {g: v[0] for g, v in e['same'].items()}, 'apart', e['apart'], 'ctrl', e['control'], 'ctrl same', e['control_same'], 'CP', cp(pk, pn) if pn else None)
        print('   pos', {k: v for k, v in p.items()})
        print('   all', {k: v for k, v in e['all'].items() if k in ('score', 'auc_ci', 'r5', 'r3', 'r3_ci', 'control_auc')})


show('read-train.json')
print('--- chosen')
show('read-chosen-train.json')
print('--- held')
show('read-held.json')
