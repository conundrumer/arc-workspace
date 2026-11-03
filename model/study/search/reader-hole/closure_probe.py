"""Ceiling of forms a held-reader search adds over a 600 s run's cover, with the chain it opens. Round by round: every uncovered form that is ready
(its reads all covered) and has a reader whose only uncovered read it is gets covered; then every uncovered form that became ready through those gets
covered too, as a forward draw could now reach it. Repeats to a fixed point. Gold text and .cover only, so a ceiling: every such form is taken as found.
With ONLY=INIT, only INIT forms are taken through a held reader (the forward-ready step still takes any kind).
  python3 closure_probe.py POINTS RUN_OUT_DIR ONLY ARM..."""
import collections, json, re, sys, os
NAME = re.compile(r'&r\d+')
points, out, only, arms = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
gold = {x['task']: x['gold_sexp'] for x in json.load(open(points))}
for arm in arms:
    c = collections.Counter(); tasks = set()
    for t in sorted(os.listdir('%s/%s' % (out, arm))):
        lines = gold[t].strip().split('\n')
        forms = [x for x in lines if not x.startswith('(OUT')]
        head = [NAME.search(x)[0] for x in forms]
        idx = {h: i for i, h in enumerate(head)}
        kind = [x[1:x.index(' ')] for x in forms]
        reads = [{idx[m] for m in NAME.findall(x) if m in idx and m != h} for x, h in zip(forms, head)]
        readers = collections.defaultdict(set)
        for i, rs in enumerate(reads):
            for r in rs:
                readers[r].add(i)
        cov0 = {json.loads(l)['gold'] for l in open('%s/%s/%s/work/%s.out.jsonl.cover' % (out, arm, t, t))}
        cov, rounds = set(cov0), 0
        while True:
            held = {x for x in range(len(forms)) if x not in cov and reads[x] <= cov and (only == 'ALL' or kind[x] == only)
                    and any(r not in cov and reads[r] - {x} <= cov for r in readers[x])}
            if not held:
                break
            cov |= held
            rounds += 1
            c['held, round %d' % rounds] += len(held)
            for x in held:
                c['held ' + kind[x]] += 1
            opened = {r for x in held for r in readers[x] if r not in cov and reads[r] <= cov}
            while opened:
                cov |= opened
                for r in opened:
                    c['opened ' + kind[r]] += 1
                opened = {q for r in opened for q in readers[r] if q not in cov and reads[q] <= cov}
        new = cov - cov0
        c['new'] += len(new); c['new non-DET'] += sum(kind[i] != 'DET' for i in new)
        if any(kind[i] != 'DET' for i in new):
            tasks.add(t)
    print(arm, only, dict(sorted(c.items())), 'tasks with a new non-DET form', len(tasks))
