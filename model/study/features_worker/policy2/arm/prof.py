"""Replays one arm's written nodes through a policy folder under cProfile: cost of add, by function. prof.py POLICY_DIR NODES_ZST [MAX]."""
import cProfile, json, os, pstats, sys, time, types
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/model/study', sys.argv[1]]
from judge3.framed_jsonl import iter_json
from policy import Policy
f = sys.argv[2]; cap = int(sys.argv[3]) if len(sys.argv) > 3 else 400
t = os.path.basename(f)[:8]
task = json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{t}.json'))
nodes = []
for r in iter_json(f):
    nodes.append(types.SimpleNamespace(id=int(r['token']), types=r['types'], table_types=r['table_types'], arity=r['arity'], depth=r['depth'], parents=[int(x) for x in r['parents']],
                                       clause=r['clause'], rows=r['x_rows'], examples=r['examples'], n_clauses=1, n_readers=0))
    if len(nodes) >= cap:
        break
p = Policy(task); pr = cProfile.Profile(); t0 = time.time()
pr.enable()
for n in nodes:
    p.add(n)
pr.disable()
dt = time.time() - t0
print(t, 'nodes', len(nodes), f'{dt / len(nodes) * 1000:.1f} ms per add under profile', 'rows mean', sum(len(n.rows) for n in nodes) // len(nodes))
pstats.Stats(pr).sort_stats('cumulative').print_stats(22)
