"""Calibration of the fitted gate in the training cross-fit (task folds), training rows only."""
import sys
import numpy as np
sys.path.insert(0, '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37/cal')
from calcore import C, NF, sig  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else 'cache'
c = C(TAG)
Gs = (c.G - c.G.mean(0)) / np.where(c.G.std(0) < 1e-9, 1, c.G.std(0))
sg = np.zeros(c.NR)
for f in range(NF):
    m = LogisticRegression(C=1.0, max_iter=2000).fit(Gs[c.fold != f], c.y[c.fold != f], sample_weight=c.W[c.fold != f])
    sg[c.fold == f] = m.predict_proba(Gs[c.fold == f])[:, 1]
sg = np.clip(sg, 1e-6, 1 - 1e-6)
np.save(sys.path[0] + '/sigma_oof_%s.npy' % TAG + '', sg)
print('bits old gate (all/read/builtin/op):', {k: round(v, 3) for k, v in c.tab(c.m2_bits(sg)).items()}, 'today', {k: round(v, 3) for k, v in c.tab(c.off_bits).items()})
ll = -(c.y * np.log(sg) + (1 - c.y) * np.log(1 - sg))
print('gate log loss (nats, weighted) %.4f, base rate %.4f, entropy of base %.4f' % (c.wmean(ll), c.wmean(c.y.astype(float)), 0))
print('\nreliability: sigma bin | rows | weight | mean sigma | observed read rate')
edges = [0, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0001]
for lo, hi in zip(edges[:-1], edges[1:]):
    m = (sg >= lo) & (sg < hi)
    if m.sum():
        print('%.2f-%.2f | %6d | %7.1f | %.3f | %.3f' % (lo, hi, m.sum(), c.W[m].sum(), c.wmean(sg, m), c.wmean(c.y.astype(float), m)))
print('\nslice | rows | weight | mean sigma | observed rate | gap')
def row(nm, m):
    if m.sum():
        a, b = c.wmean(sg, m), c.wmean(c.y.astype(float), m)
        print('%-28s | %6d | %7.1f | %.3f | %.3f | %+.3f' % (nm, m.sum(), c.W[m].sum(), a, b, a - b))
row('all', np.ones(c.NR, bool))
row('read picks (y=1)', c.read)
row('not read (y=0)', ~c.read)
row('  builtin', c.gtype == 1)
row('  op', c.gtype == 2)
for pl in ['RULE', 'DET', 'key', 'port']:
    m = c.place == pl
    row('place %s' % pl, m)
    row('  %s, read' % pl, m & c.read)
    row('  %s, not read' % pl, m & ~c.read)
for nm, m in (('steered', c.ro == 0), ('rel_off', c.ro == 1)):
    row(nm, m); row('  %s, read' % nm, m & c.read); row('  %s, not read' % nm, m & ~c.read)
for ph in ['root', 'root2']:
    m = c.ph == ph
    row('phase ' + ph, m); row('  %s, read' % ph, m & c.read)
for hk in ['DET', 'INIT', 'RULE']:
    m = c.hk == hk
    row('head ' + hk, m); row('  %s, read' % hk, m & c.read)
for sname, v in (('c120', 0), ('n600', 1)):
    row(sname, c.src == v); row('  %s, read' % sname, (c.src == v) & c.read)
dd = c.G[:, c.ix['dd']]
for nm, m in (('derived drawn', dd > 0.5), ('no derived drawn', dd <= 0.5)):
    row(nm, m); row('  %s, read' % nm, m & c.read)
bd = c.G[:, c.ix['bd']]
for nm, m in (('builtin drawn', bd > 0.5), ('no builtin drawn', bd <= 0.5)):
    row(nm, m); row('  %s, read' % nm, m & c.read)
