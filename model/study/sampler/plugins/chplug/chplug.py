"""A choicecheap plugin of the round-1 explorers' features ch1a, ch1b and ch1c."""
import importlib.util
import os

C = os.path.dirname(os.path.abspath(__file__))


def _load(x):
    spec = importlib.util.spec_from_file_location(f'ch1{x}', f'{C}/features/ch1{x}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.FEATURE_FUNCS[f'ch1{x}']


FEATURE_FUNCS = {f'ch1{x}': _load(x) for x in 'abc'}
