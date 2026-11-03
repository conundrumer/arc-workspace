"""Row check (item 7): features from rebuilt rows against features from record rows, on R120 nodes. Stops at SECONDS.

  ./rt600.sh features_node_rowcheck.py SECONDS [NODES] [TASK_STEP]
A node's ancestors are found by the &f numbers its clause reads, through the clauses of the records, and replayed in one session.
Counts: nodes checked, nodes whose rebuilt table has no match, and for matches whether all features are equal (Ident columns read as
which rows share an id, so their values may differ), by whether the table has an Ident column.
"""
import collections, json, math, os, re, sys, time
T0 = time.time()
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'  # the data folder
LIMIT = float(sys.argv[1]); NN = int(sys.argv[2]) if len(sys.argv) > 2 else 500; STEP = int(sys.argv[3]) if len(sys.argv) > 3 else 37
KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-dag-nodes-train50-final-8be414670/'
sys.path.insert(0, KIT + 'model/study/sampler'); sys.path.insert(0, HERE)
import numpy as np
import superdag as D
import superdag_search as Q
D.table_key = Q.table_key
live, arclog = D.live, D.arclog
S = D.S
import features_node_io as IO, features_node_feats as FE
sampler = live.Sampler(KIT + 'models-final')
ex = IO.excluded()
tasks = sorted(f[:8] for d in IO.R120 for f in os.listdir(d) if f.endswith('.nodes.jsonl.zst'))
tasks = [t for t in tasks if t not in ex and os.path.exists(IO.TASKDIR + t + '.json')][::STEP]
c = collections.Counter()
diffs = collections.Counter()
for t in tasks:
    if time.time() - T0 > LIMIT or c['nodes'] >= NN:
        break
    path = next(d + t + '.nodes.jsonl.zst' for d in IO.R120 if os.path.exists(d + t + '.nodes.jsonl.zst'))
    N = [r for r in IO.read_nodes(path) if r.get('x_rows')]
    head = {}
    for r in N:
        m = re.match(r'\((?:DET|RULE|INIT) &f(\d+)', r['clause'] or '')
        if m:
            head.setdefault(int(m[1]), r['clause'])
    task = IO.load_task(t)
    ctx = FE.TaskCtx(task)
    settings = arclog.DecodeSettings(relations=D.RELATIONS, **D.SETTINGS)
    session = arclog.Session(arclog.Task.from_json(json.dumps(task), arclog.World.Open), settings, session_bytes=1 << 30)
    run = D.Run(sampler.pri, session, 0, time.monotonic() + 86400, task, live.Limits())
    per = max(1, NN // len(tasks) + 1)
    for r in N[::max(1, len(N) // per)][:per]:
        if time.time() - T0 > LIMIT or c['nodes'] >= NN:
            break
        m = re.match(r'\((?:DET|RULE|INIT) &f(\d+)', r['clause'] or '')
        if not m:
            continue
        order, seen = [], set()
        def visit(f):
            if f in seen or f not in head:
                return
            seen.add(f)
            for g in re.findall(r'&f(\d+)', head[f]):
                if int(g) != f:
                    visit(int(g))
            order.append(f)
        visit(int(m[1]))
        c['nodes'] += 1
        run.collect = []; run.scoped = None
        try:
            run.scope([head[f] for f in order])
            ct = run.collect[-1]
        except Exception:
            c['replay failed'] += 1
            continue
        finally:
            run.collect = None
        want = sorted(r['table_types'])
        cnt = [e[2] for e in r['x_rows']]
        got = None
        for _, j in D.relation_tables(ct):
            try:
                tb = S.parse_table(D.OneTable(ct, j))
            except D.M.Fail:
                continue
            ty = [str(x) for x in tb['types']]
            if sorted(ty) == want:
                xr = S.rows_with_models(tb, S.X_ROWS_CAP)
                if sorted((e[0][0], e[0][1], e[2]) for e in xr) == sorted((e[0][0], e[0][1], e[2]) for e in r['x_rows']):
                    got = (ty, xr)
                    break
        if got is None:
            c['no table with the record counts'] += 1
            continue
        a = FE.node_features(r['table_types'], r['x_rows'], r['clause'], 'DET', 1, 0, ctx)
        b = FE.node_features(got[0], got[1], r['clause'], 'DET', 1, 0, ctx)
        bad = [k for k in a if (a[k] != a[k]) != (b[k] != b[k]) or (a[k] == a[k] and abs(a[k] - b[k]) > 1e-9 * max(1, abs(a[k])))]
        key = 'ident' if 'Ident' in want else 'no ident'
        c['matched ' + key] += 1
        if bad:
            c['features differ ' + key] += 1
            diffs.update(bad)
print(dict(c), 'seconds', round(time.time() - T0, 1))
print('features that differ (count of nodes):', dict(diffs.most_common(10)))
