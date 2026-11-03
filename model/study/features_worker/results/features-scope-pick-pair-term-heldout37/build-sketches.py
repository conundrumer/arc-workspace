"""A sketch of the tables of each leaf form of each scope drawn on the base arms. A leaf form is a form of the scope that no form of the scope reads.

A bank file holds no rows, so each table is computed again: the forms replay on the task's own data in the kit's session, on the engine's python. No search runs and no gold is read. Test outputs are removed from the task as in the run.

Per run it writes sketches/<arm>-<task>.pkl: {form id: [sketch of one relation]}. A sketch is dict(types=[column type], cols=[{example: (distinct values, sorted bytes of the smallest K hashes)}]), defined in pair_facts.py. A finished run is skipped on a rerun. sketch-runs.tsv has one line per run.

  py.sh build-sketches.py SECONDS [ARM TASK]
"""
import collections
import glob
import json
import os
import pickle
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
BATCH_FORMS = 64
BATCH_DET = 3
ARMS = ('base_s0', 'base_s1')
tasks = open(C.W + 'held/tasks.txt').read().split()
limit = float(sys.argv[1])
os.makedirs(HERE + 'sketches', exist_ok=True)
sampler = live.Sampler(KIT + 'models-base')


def load_slots(arm, t):
    d = '%s%s/%s' % (C.A, arm, t)
    base = float(open(d + '/start').read())
    work = d + '/work/'
    st = C.bank(glob.glob(work + '*.out.jsonl.bank')[0])
    visits = []
    for p in glob.glob(work + '*.visits'):
        for l in open(p):
            try:
                visits.append(json.loads(l))
            except ValueError:
                continue
    visits.sort(key=lambda v: v['time'])
    seen, slots = set(), []
    for v in visits:
        k = (tuple(v['fids']), v['kind'])
        if k not in seen and v['time'] - base <= CUT:
            seen.add(k)
            slots.append(v['fids'])
    return st, slots


def session_run(t):
    task = json.load(open(KIT + 'data/tasks/%s.json' % t))
    for x in task['test']:
        x.pop('output', None)
    settings = arclog.DecodeSettings(relations=D.RELATIONS, **D.SETTINGS)
    session = arclog.Session(arclog.Task.from_json(json.dumps(task), arclog.World.Open), settings, session_bytes=1 << 31)
    return D.Run(sampler.pri, session, 0, time.monotonic() + 3600, task, live.Limits())


def replay(run, forms, order, need, got, cnt):
    """Replays the forms of order, and sketches those in need. Gives the forms of order that didn't replay."""
    run.collect, run.scoped = [], None
    try:
        run.scope([forms[f].text for f in order])
    except Exception as e:  # noqa: BLE001
        cnt['replay stopped: ' + type(e).__name__] += 1
    cts, run.collect, run.scoped = run.collect, None, None
    cnt['replays'] += 1
    cnt['replayed forms'] += len(cts)
    for f, ct in zip(order, cts):
        if f in need and f not in got:
            out = []
            for _, j in D.relation_tables(ct):
                try:
                    out.append(P.sketch_table(S.parse_table(D.OneTable(ct, j))))
                except M.Fail:
                    cnt['table not finished'] += 1
            got[f] = out
    return order[len(cts):]


def one(arm, t):
    t0 = time.time()
    st, slots = load_slots(arm, t)
    forms = st['forms']
    run = session_run(t)
    cnt = collections.Counter()
    need, leafs = set(), []
    for fids in slots:
        if all(f in forms for f in fids):
            q = P.leaves(forms, fids)
            leafs.append((fids, q))
            need |= set(q)
        else:
            cnt['slots with a form not in the bank'] += 1
    got = {}

    def closure(fs):
        out, todo = set(), list(fs)
        while todo:
            f = todo.pop()
            if f not in out:
                out.add(f)
                todo += forms[f].parents
        return out

    def flush(batch):
        order = sorted(batch, key=lambda f: (forms[f].depth, f))
        return replay(run, forms, order, need, got, cnt)
    batch, later = set(), []
    for fids, q in leafs:
        todo = [f for f in q if f not in got]
        if not todo:
            continue
        add = closure(todo)
        both = batch | add
        if batch and (len(both) > BATCH_FORMS or sum(forms[f].kind in ('DET', 'RIGID_DET') for f in both) > BATCH_DET):
            flush(batch)
            add = closure([f for f in q if f not in got])
            batch = set()
            both = add
        batch = both
    if batch:
        flush(batch)
    for fids, q in leafs:  # what a batch left out: the slot's own scope ran in the search
        if any(f not in got for f in q):
            replay(run, forms, sorted(fids, key=lambda f: (forms[f].depth, f)), need, got, cnt)
    for f in need:
        if f not in got:
            cnt['form with no sketch'] += 1
    tmp = HERE + 'sketches/%s-%s.tmp' % (arm, t)
    with open(tmp, 'wb') as f:
        pickle.dump(got, f, protocol=5)
    os.replace(tmp, HERE + 'sketches/%s-%s.pkl' % (arm, t))
    return len(slots), len(need), cnt, time.time() - t0


def main():
    wr = open(HERE + 'sketch-runs.tsv', 'a')
    todo = [(a, t) for a in ARMS for t in tasks if not os.path.exists(HERE + 'sketches/%s-%s.pkl' % (a, t))]
    if len(sys.argv) > 3:
        todo = [(sys.argv[2], sys.argv[3])]
    t0, n, spent = time.time(), 0, collections.Counter()
    for arm, t in todo:
        if time.time() - t0 > limit:
            break
        ns, nf, cnt, sec = one(arm, t)
        wr.write('\t'.join(map(str, (arm, t, ns, nf, round(sec, 2), json.dumps(cnt)))) + '\n')
        wr.flush()
        n += 1
        spent.update(cnt)
        rate = n / (time.time() - t0)
        print('%d of %d runs, %.2f runs per s, eta %.0f s; %s %s %d slots %d forms %.1f s %s' % (n, len(todo), rate, (len(todo) - n) / rate, arm, t, ns, nf, sec, dict(cnt)), flush=True)


main()
