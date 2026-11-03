"""Candidate gates by cross-fit (training rows only): extra facts, interactions, and a boosted gate as an upper bound."""
import sys
import time
import warnings
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37/cal')
from calcore import C, NF, sig  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

T0 = time.time()
TAG = sys.argv[1] if len(sys.argv) > 1 else 'cache'
c = C(TAG)
y = c.y.astype(float)
G = c.G
ix = c.ix
SD = c.SD
SDr = np.add.reduceat(c.ows * c.orf, c.starts)
def lg(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))
sh_ws = lg(SD / (SD + c.TB + 1e-12))           # P's derived share before the steer
sh_rf = lg(SDr / (SDr + c.ZB + 1e-12))         # today's derived share after the steer
print('derived share (ws) mean read %.3f / not %.3f; today %.3f / %.3f' % (c.wmean(SD / (SD + c.TB), c.read), c.wmean(SD / (SD + c.TB), ~c.read), c.wmean(SDr / (SDr + c.ZB), c.read), c.wmean(SDr / (SDr + c.ZB), ~c.read)))
pls = ['pl:RULE', 'pl:DET', 'pl:port', 'pl:key']
def cols(*names):
    return np.column_stack([G[:, ix[n]] for n in names])
base = G
def bitsfor(p):
    return {k: round(v, 3) for k, v in c.tab(c.m2_bits(np.clip(p, 1e-6, 1 - 1e-6))).items()}
def ll(p):
    return -c.wmean(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1)))
def cvfit(F, C_=1.0, label=''):
    F = (F - F.mean(0)) / np.where(F.std(0) < 1e-9, 1, F.std(0))
    p = np.zeros(c.NR)
    for f in range(NF):
        m = LogisticRegression(C=C_, max_iter=3000).fit(F[c.fold != f], c.y[c.fold != f], sample_weight=c.W[c.fold != f])
        p[c.fold == f] = m.predict_proba(F[c.fold == f])[:, 1]
    print('%-34s C=%-4s logloss %.4f  bits %s  [%.0fs]' % (label, C_, ll(p), bitsfor(p), time.time() - T0), flush=True)
    return p
sq = np.column_stack([G[:, ix[n]] ** 2 for n in ('lse', 'mx', 'lnD', 'lnf')])
inter = np.column_stack([G[:, ix[p]] * G[:, ix[n]] for p in pls for n in ('lse', 'mx', 'dd', 'bd', 'r2')])
cvfit(base, label='old')
cvfit(np.column_stack([base, sq]), label='+squares')
cvfit(np.column_stack([base, sh_ws, sh_rf]), label='+logit share (ws), (rf)')
cvfit(np.column_stack([base, sh_ws]), label='+logit share (ws)')
cvfit(np.column_stack([base, sh_rf]), label='+logit share (rf)')
cvfit(np.column_stack([base, inter]), label='+place x facts')
cvfit(np.column_stack([base, sq, inter, sh_ws, sh_rf]), label='+all')
from sklearn.ensemble import HistGradientBoostingClassifier as HGB  # noqa: E402
F = np.column_stack([base, sh_ws, sh_rf])
p = np.zeros(c.NR)
for f in range(NF):
    m = HGB(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=100, random_state=0).fit(F[c.fold != f], c.y[c.fold != f], sample_weight=c.W[c.fold != f])
    p[c.fold == f] = m.predict_proba(F[c.fold == f])[:, 1]
print('%-34s logloss %.4f  bits %s  [%.0fs]' % ('HGB on base+shares (upper bound)', ll(p), bitsfor(p), time.time() - T0))
