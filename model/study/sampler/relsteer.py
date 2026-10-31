"""relsteer: the runtime scorer of relcheap's models.  Imports numpy, sklearn (to unpickle the tree) and relfeat only.

    from relsteer import Scorer
    sc = Scorer('/path/relcheap.pkl', model='hgb')       # 'hgb' (tree) or 'logit'
    f = sc.f(row)    # list[float], one per row['options']: model score - log(P's share); a steer multiplies weight i by exp(beta * f[i])

A model whose feature sets include a plugin's (ck['plugin'], the --plugin path of relcheap) loads that plugin here; a row then carries the
fields the plugin reads (dag_options: prefix_bases, prefix_depth and each derived option's dag).
row: the fields a relrows row carries: k, phase, scope, prefix (gold's atoms so far, as strings in body_atoms format), point_group
({'point_group', 'depth', 'd_out'}) and options (tok, kind, name, p, types, columns).  The derived-name mask the model was trained
with (ck['mask']) is applied here, so a row may carry the author's names.
"""
import array
import importlib.util
import math
import os
import pickle
import sys

import numpy as np

import relfeat



def one_thread():
    """Limit OpenMP to one thread in every loaded library (call after sklearn is imported): a draw worker is one process, and the
    tree's OpenMP threads cost 1 s a call (against 1 ms) on a loaded machine."""
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(limits=1)
    except ImportError:
        pass


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sampler_paths as P  # noqa: E402
def load_plugin(path):
    """Add the feature functions of a relcheap --plugin file to relfeat.FEATURE_FUNCS (as relcheap.load_plugin does, without torch)."""
    sys.path += [P.STUDY, P.STUDY + '/features']
    spec = importlib.util.spec_from_file_location('relcheap_plugin', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    relfeat.FEATURE_FUNCS.update(mod.FEATURE_FUNCS)


class Columns(dict):
    """A feature set's {feature name: column of the model}, filled as names come; -1 for a name that has no column, and for 'logp',
    which option_dicts takes from no set."""

    def __init__(self, col, group):
        super().__init__(logp=-1)
        self.col, self.group = col, group

    def __missing__(self, name):
        j = self[name] = self.col.get(relfeat.qualify(self.group, name), -1)
        return j


class Scorer:
    def __init__(self, path, model='hgb'):
        with open(path, 'rb') as f:
            ck = pickle.load(f)
        one_thread()
        self.mask = ck.get('mask', 'all')
        self.kind = model
        m = ck[model]
        self.groups = m['groups_used']
        if ck.get('plugin') and any(g not in relfeat.FEATURE_FUNCS for g in self.groups):  # a model trained with a plugin's feature set
            load_plugin(os.path.join(P.HERE, ck['plugin']))
        if model == 'logit':
            self.index, self.w = m['index'], m['weights']
        else:
            self.model, self.beta = m['model'], m['beta']
            self.col = {n: j for j, n in enumerate(m['names'])}
            self.nd = len(self.col)
            self.sets = [(getattr(relfeat.FEATURE_FUNCS[g], 'unfiltered', relfeat.FEATURE_FUNCS[g]), Columns(self.col, g)) for g in self.groups]

    def matrix(self, row):
        """(the model's input, the log shares) of a masked row: option_dicts' values by column, with no names kept. X is float32, as
        the model was fit."""
        opts, nd, sets = row['options'], self.nd, self.sets
        X = array.array('f', bytes(4 * len(opts) * nd))
        logp = [math.log(max(o['p'], 1e-9)) for o in opts]
        lc, base = self.col.get('logp', -1), 0
        for o, lp in zip(opts, logp):
            if lc >= 0:
                X[lc + base] = lp
            for fn, col in sets:
                for n, v in (fn(row, o) or {}).items():
                    if v:
                        j = col[n]
                        if j >= 0:
                            X[j + base] = v
            base += nd
        return np.frombuffer(X, np.float32).reshape(len(opts), nd), logp

    def f(self, row):
        row = relfeat.mask_row(row, self.mask)
        if self.kind == 'logit':
            ds = relfeat.option_dicts(row, self.groups)
            idx, w = self.index, self.w
            return [sum(w[idx[n]] * v for n, v in d.items() if n in idx) - d['logp'] for d in ds]
        X, logp = self.matrix(row)
        return (self.beta * self.model.decision_function(X) - np.array(logp)).tolist()


_RT = {}


def score_options(row, model='hgb', path=None):
    key = (model, path)
    if key not in _RT:
        _RT[key] = Scorer(path or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'relcheap.pkl'), model)
    return _RT[key].f(row)
