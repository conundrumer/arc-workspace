"""Time of building a sketch on one thread, per relation, and a check that the Mac engine gives the run's tables: row counts per example against the node's record in the bank, for a form with one relation and one node.

cost-sketch-rows.tsv: arm, task, form, rows (all rows of the table), ms (pair_facts.sketch_table), bytes, check (1 same row counts, 0 differ, empty not checked). A finished run is skipped on a rerun.

  py.sh cost-sketch.py SECONDS
"""
import csv
import glob
import json
import os
import sys
import time

HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-pick-pair-term-heldout37/'
KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-extended-text-pass1-8be414670/'
BASE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-base-cost-read-heldout37/'
sys.path.insert(0, KIT + 'model/study/sampler')
sys.path.insert(1, BASE)
sys.path.insert(2, HERE)
import superdag as D  # noqa: E402
import superdag_search as Q  # noqa: E402
D.table_key = Q.table_key
import read_common as C  # noqa: E402
import pair_facts as P  # noqa: E402
live, arclog, S, M = D.live, D.arclog, D.S, D.M
CUT = 600.0
limit = float(sys.argv[1])
tasks = open(C.W + 'held/tasks.txt').read().split()
sampler = live.Sampler(KIT + 'models-base')
path = HERE + 'cost-sketch-rows.tsv'
done = {(r['arm'], r['task']) for r in csv.DictReader(open(path), delimiter='\t')} if os.path.exists(path) else set()
new = not os.path.exists(path)
f_ = open(path, 'a', newline='')
w = csv.writer(f_, delimiter='\t')
if new:
    w.writerow(['arm', 'task', 'form', 'rows', 'ms', 'bytes', 'check'])


def one(arm, t):
    d = '%s%s/%s' % (C.A, arm, t)
    base = float(open(d + '/start').read())
    work = d + '/work/'
    st = C.bank(glob.glob(work + '*.out.jsonl.bank')[0])
    forms, nodes = st['forms'], st['nodes']
    seen, slots = set(), []
    for p in glob.glob(work + '*.visits'):
        for l in open(p):
            try:
                v = json.loads(l)
            except ValueError:
                continue
            k = tuple(v['fids'])
            if k not in seen and v['time'] - base <= CUT and all(x in forms for x in k):
                seen.add(k)
                slots.append(v['fids'])
    task = json.load(open(KIT + 'data/tasks/%s.json' % t))
    for x in task['test']:
        x.pop('output', None)
    settings = arclog.DecodeSettings(relations=D.RELATIONS, **D.SETTINGS)
    session = arclog.Session(arclog.Task.from_json(json.dumps(task), arclog.World.Open), settings, session_bytes=1 << 31)
    run = D.Run(sampler.pri, session, 0, time.monotonic() + 3600, task, live.Limits())
    got, n = set(), 0
    for fids in slots:
        leaf = P.leaves(forms, fids)
        if all(f in got for f in leaf):
            continue
        order = sorted(fids, key=lambda f: (forms[f].depth, f))
        run.collect, run.scoped = [], None
        try:
            run.scope([forms[f].text for f in order])
        except Exception:  # noqa: BLE001
            pass
        cts, run.collect, run.scoped = run.collect, None, None
        for f, ct in zip(order, cts):
            if f in got or f not in leaf:
                continue
            got.add(f)
            rel = D.relation_tables(ct)
            for _, j in rel:
                try:
                    tb = S.parse_table(D.OneTable(ct, j))
                except M.Fail:
                    continue
                t0 = time.perf_counter()
                sk = P.sketch_table(tb)
                ms = (time.perf_counter() - t0) * 1000
                check = ''
                if len(rel) == 1 and len(forms[f].nodes) == 1 and forms[f].nodes[0] in nodes:
                    a = sorted((x[0], x[1], x[2]) for x in D.table_key(tb)[1])
                    b = sorted((x[0], x[1], x[2]) for x in nodes[forms[f].nodes[0]].examples)
                    check = int(a == b)
                w.writerow([arm, t, f, sum(len(e[2]) for e in tb['entries']), round(ms, 4), P.sketch_bytes(sk), check])
                n += 1
    f_.flush()
    return n


t0 = time.time()
todo = [('base_s0', t) for t in tasks[::3]] + [('base_s1', t) for t in tasks[1::3]]
todo = [x for x in todo if x not in done]
for i, (a, t) in enumerate(todo):
    if time.time() - t0 > limit:
        break
    n = one(a, t)
    rate = (i + 1) / (time.time() - t0)
    print('%d of %d runs, %.2f runs per s, eta %.0f s, %s %s %d relations' % (i + 1, len(todo), rate, (len(todo) - i - 1) / rate, a, t, n), flush=True)
