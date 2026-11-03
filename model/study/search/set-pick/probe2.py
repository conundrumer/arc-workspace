import sys, json, collections
sys.dont_write_bytecode = True
SW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker'
sys.path[:0] = [SW + '/refit-tools', SW]
import search_node_score_parity as PA
RUN = SW + '/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out'
arm, task = sys.argv[1], sys.argv[2]
w = '%s/%s/%s/work/%s' % (RUN, arm, task, task)
b = PA.load_bank(w + '.out.jsonl.bank')
N = b["nodes"]; print(type(N)); N = [N[i] for i in sorted(N)] if isinstance(N, dict) else N
print('rows None', sum(n.rows is None for n in N), 'of', len(N), 'frames None', sum(n.frames is None for n in N))
print('ids==range', b['policy']['ids'] == list(range(len(N))))
picks = PA.read_lines(w + '.out.jsonl.picks')
print('pick lens', collections.Counter(len(p['picks']) for p in picks).most_common(8))
print('first picks', picks[:3])
print('scores', collections.Counter(p.get('score') for p in picks))
ages = [n.age for n in N]; print('age monotone', all(a <= b2 for a, b2 in zip(ages, ages[1:])))
tt = collections.Counter(tuple(sorted(n.table_types)) for n in N); print('distinct type sets', len(tt), tt.most_common(5))
kinds = collections.Counter(b['forms'][n.form].kind for n in N); print(kinds)
print('Ident nodes', sum('Ident' in n.table_types for n in N))
print([n.clause for n in N if 'Ident' in n.table_types][:3])
