"""Feature rows from the nodes the loop itself drew: sampled gold against sampled junk, each node seeing its own ancestors. Seeded nodes stay in the DAG as ancestors and get no row. One file per run dump in rows/; a rerun skips finished files.

  live_rows.py K N DUMP_DIR ...
"""
import glob, json, os, pickle, sys, time, types
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/model/study', os.path.dirname(os.path.abspath(__file__)) + '/../policy4']
from judge3.framed_jsonl import iter_json
from policy import Policy
K, N = int(sys.argv[1]), int(sys.argv[2])
OUT = os.path.dirname(os.path.abspath(__file__)) + '/rows'
os.makedirs(OUT, exist_ok=True)
files = sorted(f for d in sys.argv[3:] for f in glob.glob(d + '/*.nodes.jsonl.zst'))[K::N]
t0 = time.time(); done = 0
for i, f in enumerate(files):
    name = os.path.basename(os.path.dirname(f)) + '.' + os.path.basename(f)[:8]
    o = f'{OUT}/{name}.pkl'
    if os.path.exists(o):
        continue
    t = os.path.basename(f)[:8]
    p = Policy(json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{t}.json')))
    rows = []
    for r in iter_json(f):
        n = types.SimpleNamespace(id=int(r['token']), types=r['types'], table_types=r['table_types'], arity=r['arity'], depth=r['depth'], parents=[int(x) for x in r['parents']],
                                  clause=r['clause'], rows=r['x_rows'], examples=r['examples'], n_clauses=1, n_readers=0)
        d = p.feats(n); tags = r.get('tags') or {}
        if not tags.get('seeded'):
            rows.append(dict(f=d, gold=tags.get('kind') == 'gold', depth=r['depth'], draw=tags.get('draw', 0), kind=r['clause'].split(' ', 1)[0].strip('(')))
    pickle.dump(rows, open(o + '.new', 'wb')); os.replace(o + '.new', o)
    done += 1
    el = time.time() - t0
    print(f'{i + 1}/{len(files)} {name} {len(rows)} rows gold {sum(x["gold"] for x in rows)} | {el:.0f} s | ETA {el / done * (len(files) - i - 1):.0f} s', flush=True)
print('done', round(time.time() - t0), 's', flush=True)
