"""Check that Policy's live features equal the fit's features on one dump, and print the cost of add and scope."""
import json, os, pickle, random, sys, time, types
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/model/study', os.path.dirname(os.path.abspath(__file__))]
from judge3.framed_jsonl import iter_json
from policy import Policy
P = sys.argv[1]; HERE = os.path.dirname(os.path.abspath(__file__))
for t in sys.argv[2:]:
    task = json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{t}.json'))
    fit = pickle.load(open(f'{HERE}/cache2/{t}.pkl', 'rb'))
    p = Policy(task); bad = n = 0; t0 = time.time()
    for r, (d, _, _) in zip(iter_json(f'{P}/{t}.nodes.jsonl.zst'), fit):
        node = types.SimpleNamespace(id=int(r['token']), types=r['types'], table_types=r['table_types'], arity=r['arity'], depth=r['depth'], parents=[int(x) for x in r['parents']],
                                     clause=r['clause'], rows=r['x_rows'], examples=r['examples'], n_clauses=1, n_readers=0)
        p.add(node); n += 1
        live = p.nodes[node.id][1]
        a = {k: v for k, v in d.items() if not k.startswith('kid_')}
        if a != live:
            bad += 1
            if bad == 1:
                print('differs', {k: (a.get(k), live.get(k)) for k in set(a) | set(live) if a.get(k) != live.get(k)})
    dt = time.time() - t0; t0 = time.time(); rng = random.Random(0)
    picks = [p.scope(6, rng) for _ in range(100)]
    print(t, 'nodes', n, 'differ', bad, f'add {dt / n * 1000:.2f} ms, scope {(time.time() - t0) * 10:.2f} ms', 'score range', round(min(p.score.values()), 1), round(max(p.score.values()), 1), 'first scope', picks[0])
