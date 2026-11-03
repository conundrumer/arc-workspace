"""A table score for a RULE prefix: log-odds from a tree fit on non-held ground truth forms. A pure function of the prefix's table, its atoms and the tables of the forms in scope. It reads no ground truth and no test output.

  install()       once, before a Run makes a scope: keeps each scope form's table on the Run, in `ptab`
  score(tb, ctx)  ctx: dict(run=Run, task=task JSON, text=atom strings so far, atoms=atom count)

FEATURES_PREFIX_MODEL names the fit file. A failure raises nothing: `score` returns 0.0 and adds 1 to `failed`.
"""
import json
import os
import pickle
import numpy as np
import live
from nodefeat import Pair, features
from outfeat import out_features
import features_second as SECOND
import superdag as D
S = live.S
HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = None
PAIRS = {}
KEYS = None
failed = [0]


def bundle():
    global BUNDLE
    if BUNDLE is None:
        BUNDLE = pickle.load(open(os.environ.get('FEATURES_PREFIX_MODEL', HERE + '/features_prefix_model.pkl'), 'rb'))
        BUNDLE['ix'] = {k: i for i, k in enumerate(BUNDLE['names'])}
        m = BUNDLE['model']
        BUNDLE['base'] = float(np.ravel(m._baseline_prediction)[0])
        BUNDLE['trees'] = [[(bool(n['is_leaf']), float(n['value']), int(n['feature_idx']), float(n['num_threshold']), bool(n['missing_go_to_left']), int(n['left']), int(n['right'])) for n in p[0].nodes] for p in m._predictors]
    return BUNDLE


def predict(b, x):
    """The tree model's raw score for one row, as `decision_function` gives it, with no input checks."""
    total = b['base']
    for nodes in b['trees']:
        n = nodes[0]
        while not n[0]:
            v = x[n[2]]
            n = nodes[n[5] if (n[4] if v != v else v <= n[3]) else n[6]]
        total += n[1]
    return total


def install():
    o_close, o_scope = live.Run.close, live.Run.scope

    def close(self, pg, f):
        got = o_close(self, pg, f)
        try:
            tb = S.parse_table(pg.before, with_rows=False)
            for s in pg.new:
                self.ptab[s] = dict(types=[str(x) for x in tb['types']], labels=list(tb['labels']), x_rows=S.rows_with_models(S.full(tb), 200))
        except Exception:  # noqa: BLE001
            pass
        return got

    def scope(self, forms):
        if getattr(self, 'ptab_forms', None) != forms:
            self.ptab, self.ptab_forms = {}, forms
        return o_scope(self, forms)
    live.Run.close, live.Run.scope = close, scope


def keep_key(s, atoms):
    """The score as a z value among junk prefixes of equal atom count, so that a keep rule doesn't favor long prefixes."""
    global KEYS
    if KEYS is None:
        KEYS = {int(k): v for k, v in json.load(open(os.environ.get('FEATURES_KEEP_KEY', HERE + '/features_prefix_keep_key.json'))).items()}
    m, sd = KEYS[max(1, min(atoms, 6))]
    return (s - m) / sd


def pairs_of(task):
    key = id(task)
    if key not in PAIRS:
        PAIRS[key] = [Pair(p['input'], p['output']) for p in task['train']]
    return PAIRS[key]


def score(tb, ctx):
    kept = 'full' in tb
    try:
        b, pairs = bundle(), ctx.get('pairs') or pairs_of(ctx['task'])
        full = S.full(tb)
        r = dict(types=[], table_types=[str(x) for x in tb['types']], arity=len(tb['types']), depth=1, parents=[], clause='', n_clauses=1, x_rows=S.rows_with_models(full, S.X_ROWS_CAP), examples=D.table_key(full)[1])
        f = features(r, pairs)
        f.update(out_features(r, pairs)[0])
        f.update(SECOND.features(r, ctx['text'], ctx['ptab'] if 'ptab' in ctx else ctx['run'].ptab, pairs))
        ix = b['ix']
        x = np.full((1, len(ix) + 6), np.nan, np.float32)
        x[0, -1] = ctx['atoms']; x[0, -2] = False
        x[0, -3 - b['places'].index('RULE')] = 1
        for k, v in f.items():
            j = ix.get(k)
            if j is not None and v is not None:
                x[0, j] = v
        return predict(b, x[0].tolist())
    except Exception:  # noqa: BLE001
        failed[0] += 1
        return 0.0
    finally:
        if not kept:
            tb.pop('full', None)  # a table in the search's memo must not keep its parsed rows
