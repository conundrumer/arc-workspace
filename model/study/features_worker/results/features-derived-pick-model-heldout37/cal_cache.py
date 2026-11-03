"""Caches the arrays that the gate calibration needs: the rows of X/rows (training only, as fit.py loads them) and the out-of-fold rank scores of the chosen lambda (x1.0).

    bash REC/env.sh ../features-derived-pick-model-heldout37/cal_cache.py

Runs fit.py up to its cross-fit section (same loading, same folds, same rank-model code), fits the 5 out-of-fold rank models, writes X/cal/cache.npz.
"""
import sys
import time

X = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37'
src = open(X + '/fit.py').read()
src = src[:src.index('# ---------------------------------------------------------------- cross-fit: rank model')]
sys.argv = ['fit.py', '--out', X + '/cal', '--no-hgb']
ns = dict(__name__='fitmod', __file__=X + '/fit.py')
exec(compile(src, X + '/fit.py', 'exec'), ns)
import numpy as np  # noqa: E402

log = ns['log']
W_read = ns['W_read'] if 'W_read' in ns else float(ns['W'][ns['read']].sum())
lam = 1.0 * W_read / 1000.0
log('oof rank model, lambda', lam)
s = ns['oof_logit'](lam)
log('done oof')
G = ns['GATE'].dense(ns['GATE_RAW'])
np.savez(X + '/cal/cache.npz', s=s, G=G, n=ns['n'], W=ns['W'], fold=ns['fold'], gtype=ns['gtype'], src=ns['src'], TB=ns['TB'], ZB=ns['ZB'], gws=ns['gws'], grf=ns['grf'],
         place=ns['place'], ro=ns['ro'], ows=ns['ows'], orf=ns['orf'], opos=ns['opos'], ogold=ns['ogold'], hk=np.array(ns['R']['hk']), ph=np.array(ns['R']['ph']),
         task=np.array(ns['R']['task']), kind=np.array(ns['R']['kind']), gate_names=np.array(ns['GATE'].names))
log('wrote cache')
