"""A labeled table of live nodes: each Kaggle node with a policy folder's features, its depth and whether its table is gold. No feature reads a label. One file per task in table/TAG/; a rerun skips finished tasks.

  live_table.py POLICY_DIR TAG RECORD_DIR K N
"""
import glob, json, os, pickle, subprocess, sys, time, types
HERE = os.path.dirname(os.path.abspath(__file__))
pol, tag, rec, K, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/model/study', pol]
from policy import Policy  # noqa: E402
OUT = f'{HERE}/table/{tag}'
os.makedirs(OUT, exist_ok=True)
files = sorted(glob.glob(os.environ.get('LABELS', HERE + '/labels') + '/*.json'))[K::N]
t0 = time.time()
for i, lab in enumerate(files, 1):
    v = json.load(open(lab)); task = v['task']; o = f'{OUT}/{task}.pkl'
    f = glob.glob(f'{rec}/{task}*.zst')
    if os.path.exists(o) or not f:
        continue
    p = Policy(json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{task}.json')))
    got = {}
    if hasattr(p, 'feats'):
        inner = p.feats

        def feats(n, inner=inner):
            d = inner(n); got[n.id] = d
            return d
        p.feats = feats
    gold = {int(h['token']) for h in v['hits']}
    rows = []
    for raw in subprocess.Popen(['zstd', '-dcq', f[0]], stdout=subprocess.PIPE).stdout:
        try:
            r = json.loads(raw)
        except ValueError:
            continue
        n = types.SimpleNamespace(id=int(r['token']), types=r['types'], table_types=r['table_types'], arity=r['arity'], depth=r['depth'], parents=[int(x) for x in r['parents']],
                                  clause=r['clause'] or '', rows=r['x_rows'], examples=r['examples'], n_clauses=1, n_readers=0)
        p.add(n)
        d = got.get(n.id) or (p.nodes[n.id][1] if hasattr(p, 'nodes') else {})
        rows.append(dict(id=n.id, depth=r['depth'], draw=(r.get('tags') or {}).get('draw', 0), gold=n.id in gold, f=d))
    pickle.dump(rows, open(o + '.new', 'wb')); os.replace(o + '.new', o)
    el = time.time() - t0
    print(f'{i}/{len(files)} {task} {len(rows)} rows gold {sum(x["gold"] for x in rows)} feats {len(rows[0]["f"]) if rows else 0} | {el:.0f} s | ETA {el / i * (len(files) - i):.0f} s', flush=True)
print('done', round(time.time() - t0), 's', flush=True)
