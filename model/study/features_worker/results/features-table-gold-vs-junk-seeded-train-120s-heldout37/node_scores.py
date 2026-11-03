"""Writes the ship7 node score of every node of a pool to OUT/<task>.json, from the fold that left the task out. A rerun skips finished tasks.

  node_scores.py NODES_DIR POLICY_DIR OUT STEP OFFSET
"""
import json, os, subprocess, sys, time, types
base, pol, out, step, offset = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
sys.path.insert(0, pol)
import policy
os.makedirs(out, exist_ok=True)
files = sorted(e.name for e in os.scandir(base) if e.name.endswith('.nodes.jsonl.zst'))[offset::step]
t0, ran = time.time(), 0
for i, f in enumerate(files, 1):
    task = f.split('.')[0]
    o = '%s/%s.json' % (out, task)
    if os.path.exists(o):
        continue
    recs = []
    for raw in subprocess.run(['zstd', '-dcq', base + '/' + f], capture_output=True).stdout.splitlines():
        try:
            recs.append(json.loads(raw))
        except ValueError:
            pass
    p = policy.Policy(json.load(open('/Users/davidlu/code/arc-workspace/data/tasks/%s.json' % task)))
    t1 = time.time()
    for r in recs:
        p.add(types.SimpleNamespace(id=int(r['token']), types=r['types'], table_types=r['table_types'], arity=r['arity'], depth=r['depth'], parents=[int(x) for x in r['parents']], clause=r['clause'] or '', rows=r['x_rows'], examples=r['examples'], n_clauses=1, n_readers=0))
    json.dump(p.score, open(o + '.new', 'w'))
    os.replace(o + '.new', o)
    ran += 1
    print('%d/%d %s %d nodes %.1f s | ETA %.0f s' % (i, len(files), task, len(recs), time.time() - t1, (time.time() - t0) / ran * (len(files) - i)), flush=True)
print('done', round(time.time() - t0), 's', flush=True)
