#!/usr/bin/env python
"""Markdown tables from the OUT.json of features_signal_read.py.

  features_signal_table.py READ.json
"""
import json
import sys

R = json.load(open(sys.argv[1]))
CUTS = '60', '300', '600'
OBS = 'nodes', 'forms', 'proposals', 'best_out', 'shape_forms'


def f(x):
    return f'{x:.2f}'.lstrip('0') if x >= 0 else '-' + f'{-x:.2f}'.lstrip('0')


def ci(e, key):
    v = e.get(key)
    if not v or v[0] is None:
        return 'none'
    return f'{f(v[0])} ({f(v[1])} to {f(v[2])})' if v[1] is not None else f(v[0])


def plain(e, key):
    v = e.get(key)
    return f(v[0]) if v and v[0] is not None else 'none'


def best(c):
    got = [(c[o]['auc_third'][0], o) for o in OBS if o in c and c[o].get('auc_third')]
    return max(got) if got else (0.5, 'no positive task')


s = R['sets']
print('target', R['target'], 'third bar', R['third_bar'], 'undrawable', R['undrawable'])
for name, v in s.items():
    h = v['header']
    print(f"\n#### {name}: {h}")
    print('| Observable | ' + ' | '.join(f'{c} s: Spearman, AUC' for c in CUTS) + ' |')
    print('|---|---|---|---|')
    names = [o for o in v['cuts']['60']]
    for o in names:
        print(f'| {o} | ' + ' | '.join(f"{ci(v['cuts'][c][o], 'rho')}; {ci(v['cuts'][c][o], 'auc_third')}" for c in CUTS) + ' |')
print('\n#### Arms')
print('| Arm | Tasks | Positive, negative | ' + ' | '.join(f'{c} s: best observable, joint, area, same size, covered' for c in CUTS) + ' |')
print('|---|---|---|---|---|---|')
for name, v in R['arms'].items():
    h = v['header']
    cells = []
    for c in CUTS:
        e = v['cuts'][c]
        b = best(e)
        ref = e.get('covered (needs gold)')
        cells.append(f"{b[1]} {f(b[0])}, {plain(e['joint'], 'auc_third')}, {plain(e['area'], 'auc_third')}, {plain(e['same_size'], 'auc_third')}, {plain(ref, 'auc_third') if ref else 'none'}")
    print(f"| {name} | {h['tasks']} | {h['low_third_pos']}, {h['low_third_neg']} | " + ' | '.join(cells) + ' |')
