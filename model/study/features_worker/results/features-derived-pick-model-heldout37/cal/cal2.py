"""More calibration views of the old gate, and candidate fixes by cross-fit (training rows only)."""
import sys
import warnings
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37/cal')
from calcore import C, NF, sig  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else 'cache'
c = C(TAG)
sg = np.load(sys.path[0] + '/sigma_oof_%s.npy' % TAG + '')
y = c.y.astype(float)
z = np.log(sg / (1 - sg))
def ll(p, m=None):
    l = -(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1)))
    return c.wmean(l, m)
print('old gate logloss %.4f; by fold:' % ll(sg), [round(ll(sg, c.fold == f), 4) for f in range(NF)])
print('by fold mean sigma - rate:', [round(c.wmean(sg, c.fold == f) - c.wmean(y, c.fold == f), 4) for f in range(NF)])
# deciles of continuous features (weighted quantiles by rows is fine)
for nm in ('lse', 'mx', 'lnD', 'lnf'):
    v = c.G[:, c.ix[nm]]
    qs = np.unique(np.quantile(v, np.linspace(0, 1, 9)))
    print('\n%s decile bins: lo..hi | rows | mean sigma | rate' % nm)
    for lo, hi in zip(qs[:-1], qs[1:]):
        m = (v >= lo) & (v <= hi if hi == qs[-1] else v < hi)
        if m.sum():
            print('  %7.3f..%7.3f | %6d | %.3f | %.3f' % (lo, hi, m.sum(), c.wmean(sg, m), c.wmean(y, m)))
# temperature and bias on OOF logit, itself cross-fit by folds
pa = np.zeros(c.NR)
for f in range(NF):
    m = LogisticRegression(C=1e6, max_iter=1000).fit(z[c.fold != f, None], c.y[c.fold != f], sample_weight=c.W[c.fold != f])
    pa[c.fold == f] = m.predict_proba(z[c.fold == f, None])[:, 1]
mm = LogisticRegression(C=1e6, max_iter=1000).fit(z[:, None], c.y, sample_weight=c.W)
print('\ntemperature/bias on the OOF logit: slope %.4f intercept %.4f; logloss %.4f -> %.4f (cross-fit)' % (mm.coef_[0][0], mm.intercept_[0], ll(sg), ll(pa)))
print('bits M2 old', {k: round(v, 3) for k, v in c.tab(c.m2_bits(sg)).items()}, '\nbits M2 temp/bias', {k: round(v, 3) for k, v in c.tab(c.m2_bits(np.clip(pa, 1e-6, 1 - 1e-6))).items()})
