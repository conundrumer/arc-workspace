"""Times one sandwich in pure Python: goal rows G (P, C) and body rows B (P, X, C) on 4 examples give the forced hole rows L and the allowed rows U on X.
Data are made first and only the join is timed."""
import random, time, collections
random.seed(0)
P = [(i % 30, i // 30) for i in range(900)]
def data(nb, ng):
    return [(set(random.sample([(p, random.randrange(10)) for p in P], ng)),
             [(random.choice(P), random.randrange(50), random.randrange(10)) for _ in range(nb)]) for _ in range(4)]
def sandwich(exs):
    out = []
    for G, B in exs:
        by = collections.defaultdict(set)
        for p, x, c in B:
            by[p, c].add(x)
        forced, dead = set(), 0
        for g in G:
            xs = by.get(g)
            if not xs:
                dead += 1
            elif len(xs) == 1:
                forced |= xs
        bad = {x for k, xs in by.items() if k not in G for x in xs}
        U = {x for k, xs in by.items() if k in G for x in xs} - bad
        out.append((forced, U, dead))
    return out
for nb, ng in [(200, 100), (2000, 400), (2000, 900), (8000, 900)]:
    d = data(nb, ng)
    ts = []
    for _ in range(40):
        t = time.perf_counter(); sandwich(d); ts.append(time.perf_counter() - t)
    ts.sort()
    print('body rows %d, goal rows %d per example: median %.2f ms per sandwich over 4 examples' % (nb, ng, 1000 * ts[20]))
