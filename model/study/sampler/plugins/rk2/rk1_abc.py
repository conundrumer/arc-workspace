"""A relcheap plugin: the DAG option features (dag_options.py) and the round-1 explorer features rk1a, rk1b and rk1c,
less the keys whose prefix DROP lists (a1_ to a4_ read the point's depth or unread derived relations; b8_ reads unread
derived relations). Fit it with --hgb-feats struct b ctx dag rk1a rk1b rk1c --mask all_nogrp."""
import importlib.util
import os
import sys

R = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(R))), 'feat_exp/features')
sys.path[:0] = [F, os.path.dirname(F)]
DROP = ('a1_', 'a2_', 'a3_', 'a4_', 'b8_')


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _keep(fn):
    kept = lambda row, o: {k: v for k, v in fn(row, o).items() if not k.startswith(DROP)}  # noqa: E731
    kept.unfiltered = getattr(fn, 'unfiltered', fn)  # relsteer.Scorer calls this: a fitted model has no column for a name that DROP lists
    return kept


FEATURE_FUNCS = dict(_load(f'{F}/dag_options.py', 'dag_options').FEATURE_FUNCS)
for x in 'abc':
    FEATURE_FUNCS[f'rk1{x}'] = _keep(_load(f'{R}/features/rk1{x}.py', f'rk1{x}').FEATURE_FUNCS[f'rk1{x}'])
