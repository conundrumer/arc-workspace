"""Policy scores of a saved pool's nodes, one JSON per task; a rerun skips written tasks.

  features_policy_scores.py NODES_DIR POLICY_DIR OUT K N
"""
import glob, json, os, subprocess, sys, types
nodes, pol, out, K, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
sys.path[:0] = [pol]
import policy  # noqa: E402
os.makedirs(out, exist_ok=True)
for f in sorted(glob.glob(nodes + '/*.nodes.jsonl.zst'))[K::N]:
    t = os.path.basename(f).split('.')[0]; o = f'{out}/{t}.json'
    if os.path.exists(o):
        continue
    p = policy.Policy(json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{t}.json')))
    depth = {}
    for raw in subprocess.run(['zstd', '-dcq', f], capture_output=True).stdout.splitlines():
        try:
            r = json.loads(raw)
        except ValueError:
            continue
        depth[r['token']] = r['depth']
        p.add(types.SimpleNamespace(id=int(r['token']), types=r['types'], table_types=r['table_types'], arity=r['arity'], depth=r['depth'], parents=[int(x) for x in r['parents']], clause=r['clause'] or '', rows=r['x_rows'], examples=r['examples'], n_clauses=1, n_readers=0))
    json.dump(dict(score=p.score, depth=depth), open(o + '.new', 'w')); os.replace(o + '.new', o)
    print(t, len(p.score), flush=True)
