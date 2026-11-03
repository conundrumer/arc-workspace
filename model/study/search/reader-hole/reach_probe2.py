"""Beside reach_probe.py: for each gold form not covered by the run, its count of uncovered reads (its holes, were it a held reader), and the
ceiling of a top-down build that lets each reader hold up to H holes. Same inputs as reach_probe.py, then H."""
import collections, json, re, sys, os
NAME = re.compile(r'&r\d+')
points, out, H, arms = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4:]
gold = {x['task']: x['gold_sexp'] for x in json.load(open(points))}
for arm in arms:
    holes_top, holes_all, c = collections.Counter(), collections.Counter(), collections.Counter()
    for t in sorted(os.listdir('%s/%s' % (out, arm))):
        lines = gold[t].strip().split('\n')
        forms = [x for x in lines if not x.startswith('(OUT')]
        head = [NAME.search(x)[0] for x in forms]
        idx = {h: i for i, h in enumerate(head)}
        kind = [x[1:x.index(' ')] for x in forms]
        reads = [sorted({idx[m] for m in NAME.findall(x) if m in idx and m != h}) for x, h in zip(forms, head)]
        cov = {json.loads(l)['gold'] for l in open('%s/%s/%s/work/%s.out.jsonl.cover' % (out, arm, t, t))}
        top = sorted({idx[m] for x in lines if x.startswith('(OUT') for m in NAME.findall(x) if m in idx})
        unc = [[r for r in reads[i] if r not in cov] for i in range(len(forms))]
        for i in range(len(forms)):
            if i not in cov:
                holes_all[min(len(unc[i]), 4)] += 1
        for i in top:
            holes_top[min(len(unc[i]), 4)] += 1
        memo = {}
        def build(i):
            if i in memo:
                return memo[i]
            memo[i] = None
            if len(unc[i]) > H:
                return None
            got = {i}
            for j in unc[i]:
                sub = build(j)
                if sub is None:
                    return None
                got |= sub
            memo[i] = got
            return got
        reach = set()
        for i in top:
            if i not in cov and (g := build(i)):
                reach |= g
        c['reachable new'] += len(reach)
        c['INIT'] += sum(kind[i] == 'INIT' for i in reach)
        c['tasks'] += bool(reach)
    print(arm, 'H', H, dict(c), 'uncovered reads of OUT readers', sorted(holes_top.items()), 'of all uncovered forms', sorted(holes_all.items()))
