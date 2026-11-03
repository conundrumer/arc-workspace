"""Prints the setup of the kit's relation steer model (relR4_o.pkl): mask, plugin, groups, beta, feature names."""
import pickle
import sys

KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943'
sys.path[:0] = [KIT + '/model/study/sampler']
ck = pickle.load(open(KIT + '/models-tk/relR4_o.pkl', 'rb'))
print('keys', sorted(ck))
print('mask', ck.get('mask'), 'plugin', ck.get('plugin'))
m = ck['hgb']
print('hgb keys', sorted(m))
print('groups', m['groups_used'], 'beta', m['beta'])
names = m['names']
print('n names', len(names))
print([n for n in names if not n.startswith(('x:', 't_', 's_'))])
print('t_/s_ count', sum(n.startswith(('t_', 's_')) for n in names), 'x: count', sum(n.startswith('x:') for n in names))
mod = m['model']
try:
    imp = getattr(mod, 'feature_importances_', None)
    print('importances', imp)
except Exception as e:  # noqa: BLE001
    print('no importances', e)
# split counts per feature over the trees
import collections
cnt = collections.Counter()
for p in mod._predictors:
    nd = p[0].nodes
    for r in nd:
        if not r['is_leaf']:
            cnt[names[r['feature_idx']]] += 1
print('splits by feature (top 40):', cnt.most_common(40))
for k in ('cfg', 'config', 'args', 'meta'):
    if k in ck:
        print(k, ck[k])
