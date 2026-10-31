"""A choicecheap plugin of the round-1 explorers' features and the round-2 explorer modules d, e and f."""
import importlib.util
import os

C = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, f'{C}/features/{name}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.FEATURE_FUNCS[name]


FEATURE_FUNCS = {f'ch1{x}': _load(f'ch1{x}') for x in 'abc'}
for x in 'def':
    FEATURE_FUNCS[f'ch2{x}'] = _load(f'ch2{x}')
spec = importlib.util.spec_from_file_location('ch3o', f'{C}/features/ch3o.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FEATURE_FUNCS['ch3o'] = m.FEATURE_FUNCS['ch3o']
