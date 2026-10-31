"""A relcheap plugin: rk1_abc.py's features and the round-2 explorer modules d, e and f."""
import importlib.util
import os
import sys

R = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, R + '/features')


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


FEATURE_FUNCS = dict(_load(f'{R}/rk1_abc.py', 'rk1_abc').FEATURE_FUNCS)
for x in ['d', 'e', 'f']:
    FEATURE_FUNCS[f'rk2{x}'] = _load(f'{R}/features/rk2{x}.py', f'rk2{x}').FEATURE_FUNCS[f'rk2{x}']
