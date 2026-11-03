"""Cross-fit whole-pick bits of today, M1, M2 and M2 acting only where today's steer acts (rel_off picks left as P has them), by pick type and by steered / rel_off."""
import sys
import numpy as np
sys.path.insert(0, '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37/cal')
from calcore import C  # noqa: E402
TAG = sys.argv[1]
c = C(TAG)
sg = np.load(sys.path[0] + '/sigma_oof_%s.npy' % TAG)
off, m1, m2 = c.off_bits, c.m1_bits(), c.m2_bits(sg)
ro = c.ro == 1
m2s = np.where(ro, off, m2)
m1s = np.where(ro, off, m1)
print('check rel_off picks: options with rf != 1 at rel_off rows: %d of %d; max |ZB - TB| at rel_off rows %.2e; rows %d' % (
    int(((c.orf != 1.0) & ro[c.rid]).sum()), int(ro[c.rid].sum()), float(np.abs(c.ZB - c.TB)[ro].max()), int(ro.sum())))
print('cross-fit bits (weighted means) | rows | today | M1 | M1 steered only | M2 | M2 steered only')
for pk, mp in (('all picks', np.ones(c.NR, bool)), ('read picks', c.read), ('builtin picks', c.gtype == 1), ('op picks', c.gtype == 2)):
    for nm, mr in (('all', np.ones(c.NR, bool)), ('steered', ~ro), ('rel_off', ro)):
        m = mp & mr
        if m.sum():
            print('%-14s %-8s | %6d | %.3f | %.3f | %.3f | %.3f | %.3f' % (pk, nm, m.sum(), c.wmean(off, m), c.wmean(m1, m), c.wmean(m1s, m), c.wmean(m2, m), c.wmean(m2s, m)))
print('saved vs today (today - arm), all picks: M1 %.3f, M1 steered only %.3f, M2 %.3f, M2 steered only %.3f' % tuple(c.wmean(off - a) for a in (m1, m1s, m2, m2s)))
r = c.read
print('read rows: gate cost -log2(sigma) mean %.3f; M1 within-D bits %.3f' % (c.wmean(-np.log2(np.where(c.TBpos, sg, 1.0)), r), c.wmean(-c.log2_inD, r)))
