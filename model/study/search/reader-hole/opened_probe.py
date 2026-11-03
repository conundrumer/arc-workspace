"""For the INITs in scope (uncovered at 600 s, ready, with a reader whose only uncovered read is that INIT): the readers that a find makes ready at once,
by kind. Gold text and .cover only.
  python3 opened_probe.py POINTS RUN_OUT_DIR ARM..."""
import collections, json, re, sys, os
NAME = re.compile(r'&r\d+')
points, out, arms = sys.argv[1], sys.argv[2], sys.argv[3:]
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
        cov = {json.loads(l)['gold'] for l in open('%s/%s/%s/work/%s.out.jsonl.cover' % (out, arm, t, t))}
        outr = {idx[m] for x in lines if x.startswith('(OUT') for m in NAME.findall(x) if m in idx}
        for x in range(len(forms)):
            if kind[x] != 'INIT' or x in cov or not reads[x] <= cov:
                continue
            one = {r for r in readers[x] if r not in cov and reads[r] - {x} <= cov}
            if not one:
                continue
            tasks.add(t)
            c['INIT in scope'] += 1
            for r in one:
                c['opened ' + kind[r]] += 1
                c['opened that OUT reads'] += r in outr
    print(arm, dict(sorted(c.items())), 'tasks', len(tasks))
