"""Structural ceiling of a top-down build from OUT, on gold text and the covers of 600 s pool runs.

A chain is OUT -> R1 -> ... -> Rk along gold's read edges. It is buildable when, for each Ri, every read other than R(i+1) is a form the run covered
(or input, ex_input, ex_output, lib), and Rk's reads are all covered. Every form on a buildable chain that the run didn't cover counts as reachable.
No table is read here: determination and bits are left out, so this is a ceiling.

  python3 reach_probe.py POINTS RUN_OUT_DIR ARM...
"""
import collections, json, re, sys
NAME = re.compile(r'&r\d+')
points, out, arms = sys.argv[1], sys.argv[2], sys.argv[3:]
gold = {x['task']: x['gold_sexp'] for x in json.load(open(points))}
tasks = sorted(t for t in __import__('os').listdir('%s/%s' % (out, arms[0])))
tot = collections.Counter()
for arm in arms:
    c = collections.Counter()
    for t in tasks:
        lines = [x for x in gold[t].strip().split('\n')]
        forms = [x for x in lines if not x.startswith('(OUT')]
        outl = [x for x in lines if x.startswith('(OUT')]
        head = [NAME.search(x)[0] for x in forms]
        idx = {h: i for i, h in enumerate(head)}
        kind = [x[1:x.index(' ')] for x in forms]
        reads = [sorted({idx[m] for m in NAME.findall(x) if m in idx and m != h}) for x, h in zip(forms, head)]
        try:
            cov = {json.loads(l)['gold'] for l in open('%s/%s/%s/work/%s.out.jsonl.cover' % (out, arm, t, t))}
        except FileNotFoundError:
            continue
        top = sorted({idx[m] for x in outl for m in NAME.findall(x) if m in idx})
        # ready[i]: every read of i is covered (i can be drawn forward). side(i, j): every read of i other than j is covered.
        ready = [all(r in cov for r in reads[i]) for i in range(len(forms))]
        reach = set()
        memo = {}
        def build(i, seen):
            """Forms of a buildable chain below i, i included, or None."""
            if i in memo:
                return memo[i]
            if i in seen:
                return None
            got = None
            if ready[i]:
                got = {i}
            for j in reads[i]:
                if j in cov:
                    continue
                if all(r in cov for r in reads[i] if r != j):
                    sub = build(j, seen | {i})
                    if sub is not None:
                        got = (got or {i}) | sub
            memo[i] = got
            return got
        for i in top:
            if i in cov:
                continue
            got = build(i, frozenset())
            if got:
                reach |= got
        new = [i for i in reach if i not in cov]
        c['tasks'] += 1
        c['covered'] += len(cov)
        c['forms'] += len(forms)
        c['reachable new'] += len(new)
        c['reachable new INIT'] += sum(kind[i] == 'INIT' for i in new)
        c['reachable new non-DET'] += sum(kind[i] != 'DET' for i in new)
        c['tasks with any'] += bool(new)
        c['OUT reads covered'] += sum(i in cov for i in top)
        c['OUT reads'] += len(top)
    print(arm, dict(c))
