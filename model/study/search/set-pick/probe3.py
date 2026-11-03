import sys, collections
sys.dont_write_bytecode = True
SW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker'
sys.path[:0] = [SW + '/refit-tools', SW]
import search_node_score_parity as PA
w = sys.argv[1]
b = PA.load_bank(w)
N = b['nodes']; F = b['forms']
print(type(F), list(F)[:3] if isinstance(F, dict) else None)
k = 0
for i in sorted(N):
    n = N[i]
    if F[n.form].kind != 'INIT' and 'Ident' in n.table_types and k < 4:
        print(i, n.form, F[n.form].kind, n.table_types, n.parents, n.clause[:200]); k += 1
        for p in n.parents: print('   parent', p, N[p].table_types if p in N else None, N[p].clause[:120] if p in N else None)
print('forms parents sample', [(f, F[f].parents) for f in list(F)[100:103]])
print('policy keys', list(b['policy'].keys()))
