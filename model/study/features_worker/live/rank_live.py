"""A policy's scores on the Kaggle nodes: each gold node's rank among all nodes of its depth band in that task, with ties at the middle. Streams one file per task to rank/<tag>/; a rerun skips finished tasks. Scores read no label.

  rank_live.py POLICY_DIR TAG RECORD_DIR K N
"""
import glob, importlib, json, os, subprocess, sys, time, types
HERE = os.path.dirname(os.path.abspath(__file__))
pol, tag, rec, K, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/model/study', pol]
from policy import Policy  # noqa: E402
OUT = f'{HERE}/rank/{tag}'
os.makedirs(OUT, exist_ok=True)
files = sorted(glob.glob(HERE + '/labels/*.json'))[K::N]
B = [(1, 1, '1'), (2, 3, '2-3'), (4, 6, '4-6'), (7, 99, '7+')]
bucket = lambda x: next(n for a, b, n in B if a <= x <= b)
t0 = time.time()
for i, lab in enumerate(files, 1):
    v = json.load(open(lab)); task = v['task']; o = f'{OUT}/{task}.json'
    f = glob.glob(f'{rec}/{task}*.zst')
    if os.path.exists(o) or not f:
        continue
    p = Policy(json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{task}.json')))
    src = subprocess.Popen(['zstd', '-dcq', f[0]], stdout=subprocess.PIPE)
    band = {}
    for raw in src.stdout:
        try:
            r = json.loads(raw)
        except ValueError:
            continue
        n = types.SimpleNamespace(id=int(r['token']), types=r['types'], table_types=r['table_types'], arity=r['arity'], depth=r['depth'], parents=[int(x) for x in r['parents']],
                                  clause=r['clause'] or '', rows=r['x_rows'], examples=r['examples'], n_clauses=1, n_readers=0)
        p.add(n)
        band[n.id] = bucket(r['depth'])
    gold = {int(h['token']) for h in v['hits']}
    out = []
    for g in gold:
        if g not in p.score:
            continue
        pool = [p.score[x] for x, b in band.items() if b == band[g]]
        s = p.score[g]
        out.append(dict(token=g, band=band[g], n=len(pool), rank=1 + sum(x > s for x in pool) + (sum(x == s for x in pool) - 1) / 2))
    json.dump(dict(task=task, nodes=len(band), gold=out, score={str(k): round(x, 4) for k, x in p.score.items()}, band=band), open(o + '.new', 'w')); os.replace(o + '.new', o)
    el = time.time() - t0
    print(f'{i}/{len(files)} {task} nodes {len(band)} gold {len(out)} | {el:.0f} s | ETA {el / i * (len(files) - i):.0f} s', flush=True)
print('done', round(time.time() - t0), 's', flush=True)
