"""One row per scope drawn on the base arms: the pair facts of pair_facts.py and first-order facts. It reads the bank's forms and the policy's scores, .visits and the sketches. It reads no cover file: labels are in label-rows.tsv, from build-label-rows.py.

A scope drawn is a slot: the first visit of a (scope, kind) within 600 s. Visits are numbered as in build-map-rows.py of features-kind-pick-given-scope-contents-heldout37: sorted by time, from 0.

  scope-rows.tsv        arm, task, slot (number of its first visit), order (place among the run's slots), d0 (proposals before the slot), kind, forms, size (bucket), leaves, tries, visits, missing, score_mean, score_max, depth, pair_ms, then <fact>_mean and <fact>_max
  visit-slot-rows.tsv   arm, task, visit, slot: the visits of each slot within 600 s

score_mean and score_max are over the leaf forms; a form's score is the largest score of its nodes, and a score is fixed when a node is new. Fields that change after the draw, as uses, n_clauses and n_readers, aren't read. pair_ms is the time of scope_facts on one thread with no memo.

It streams, and a rerun skips finished runs.
"""
import csv
import glob
import json
import os
import pickle
import sys
import time

HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-pick-pair-term-heldout37/'
BASE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-base-cost-read-heldout37/'
sys.path.insert(0, BASE)
sys.path.insert(1, HERE)
sys.setrecursionlimit(20000)
import read_common as C  # noqa: E402
import pair_facts as P  # noqa: E402
CUT = 600.0
ARMS = ('base_s0', 'base_s1')
tasks = open(C.W + 'held/tasks.txt').read().split()
SIZES = ((0, '0'), (1, '1'), (2, '2'), (4, '3-4'), (8, '5-8'), (16, '9-16'), (1 << 40, '17+'))
FCOLS = [k + x for k in P.FACTS for x in ('_mean', '_max')]
HEAD = ['arm', 'task', 'slot', 'order', 'd0', 'kind', 'forms', 'size', 'leaves', 'tries', 'visits', 'missing', 'score_mean', 'score_max', 'depth', 'pair_ms'] + FCOLS


def one(arm, t, wr, wv):
    d = '%s%s/%s' % (C.A, arm, t)
    base = float(open(d + '/start').read())
    work = d + '/work/'
    st = C.bank(glob.glob(work + '*.out.jsonl.bank')[0])
    forms, nodes, score = st['forms'], st['nodes'], st['policy']['score']
    sk = {f: [P.loaded(x) for x in v] for f, v in pickle.load(open(HERE + 'sketches/%s-%s.pkl' % (arm, t), 'rb')).items()}
    fscore = {f: max((score[n] for n in forms[f].nodes if n in score), default=float('nan')) for f in forms}
    anc = {}

    def ancestors(f):
        got = anc.get(f)
        if got is None:
            got = {f}
            for p in forms[f].parents:
                got |= ancestors(p)
            anc[f] = got
        return got
    visits = []
    for p in glob.glob(work + '*.visits'):
        for l in open(p):
            try:
                visits.append(json.loads(l))
            except ValueError:
                continue
    visits.sort(key=lambda v: v['time'])
    slots, order = {}, []
    cum = 0
    for j, v in enumerate(visits):
        k = (tuple(v['fids']), v['kind'])
        if v['time'] - base <= CUT:
            if k not in slots:
                slots[k] = dict(slot=j, order=len(order), d0=cum, fids=v['fids'], kind=v['kind'], tries=0, visits=0)
                order.append(k)
            q = slots[k]
            q['tries'] += v['tries']
            q['visits'] += 1
            wv.writerow([arm, t, j, q['slot']])
        cum += v['tries']
    for k in order:
        q = slots[k]
        fids = q['fids']
        miss = sum(f not in forms for f in fids)
        size = len(fids)
        sb = next(n for lim, n in SIZES if size <= lim)
        row = [arm, t, q['slot'], q['order'], q['d0'], q['kind'], size, sb]
        if miss:
            wr.writerow(row + ['', q['tries'], q['visits'], miss, '', '', '', ''] + [''] * len(FCOLS))
            continue
        leaf = P.leaves(forms, fids)
        have = [f for f in leaf if f in sk]
        sc = [fscore[f] for f in leaf if fscore[f] == fscore[f]]
        t0 = time.perf_counter()
        fx = P.scope_facts([sk[f] for f in have], [ancestors(f) - {f} for f in have]) if len(have) == len(leaf) else None
        ms = (time.perf_counter() - t0) * 1000
        wr.writerow(row + [len(leaf), q['tries'], q['visits'], 0, round(sum(sc) / len(sc), 4) if sc else '', round(max(sc), 4) if sc else '', max((forms[f].depth for f in fids), default=0), round(ms, 4)] + ([round(fx[c], 5) for c in FCOLS] if fx else [''] * len(FCOLS)))


def main():
    files = HERE + 'scope-rows.tsv', HERE + 'visit-slot-rows.tsv'
    done_path = HERE + 'scope-done.txt'
    done = set(open(done_path).read().split('\n')) if os.path.exists(done_path) else set()
    new = not os.path.exists(files[0])
    if not new:  # a killed run may have left rows: keep only the rows of finished runs
        for p in files:
            with open(p) as f:
                keep = [l for i, l in enumerate(f) if i == 0 or ' '.join(l.split('\t')[:2]) in done]
            with open(p, 'w') as f:
                f.writelines(keep)
    fh = [open(p, 'a', newline='') for p in files]
    wr, wv = (csv.writer(f, delimiter='\t') for f in fh)
    if new:
        wr.writerow(HEAD)
        wv.writerow(['arm', 'task', 'visit', 'slot'])
    log = open(done_path, 'a')
    todo = [(a, t) for a in ARMS for t in tasks if '%s %s' % (a, t) not in done and os.path.exists(HERE + 'sketches/%s-%s.pkl' % (a, t))]
    t0, n = time.time(), 0
    for arm, t in todo:
        one(arm, t, wr, wv)
        for f in fh:
            f.flush()
        log.write('%s %s\n' % (arm, t))
        log.flush()
        n += 1
        rate = n / (time.time() - t0)
        print('%d of %d runs, %.2f runs per s, eta %.0f s, %s %s' % (n, len(todo), rate, (len(todo) - n) / rate, arm, t), flush=True)


main()
