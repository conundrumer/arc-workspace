import sys, json
sys.dont_write_bytecode = True
SW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker'
sys.path[:0] = [SW + '/refit-tools', SW]
import search_node_score_parity as PA
RUN = SW + '/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out'
arm, task = sys.argv[1], sys.argv[2]
w = '%s/%s/%s/work/%s' % (RUN, arm, task, task)
b = PA.load_bank(w + '.out.jsonl.bank')
print(type(b), list(b.keys()))
pol = b['policy']; print('policy', type(pol), list(pol.keys()) if isinstance(pol, dict) else pol)
for k, v in pol.items():
    print(' ', k, type(v), (len(v) if hasattr(v, '__len__') else v))
n0 = b['nodes'][0]; print('node', type(n0), n0.__dict__.keys() if hasattr(n0,'__dict__') else n0)
for k, v in n0.__dict__.items(): print('  ', k, repr(v)[:200])
fk = list(b['forms'])[:2]
for f in fk:
    print('form', f, {k: repr(v)[:150] for k, v in b['forms'][f].__dict__.items()})
print('draws', b['draws'], 'nodes', len(b['nodes']), 'forms', len(b['forms']))
print('lineage', b['lineage'][:2])
for k in b:
    if k not in ('nodes','forms','policy','lineage'): print('key', k, repr(b[k])[:200])
