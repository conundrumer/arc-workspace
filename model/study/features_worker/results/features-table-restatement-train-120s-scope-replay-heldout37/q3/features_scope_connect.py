"""Scope rule: a scope built from candidate parent sets, pairs and triples of pool nodes whose columns fit a join, with the node score ordering the sets. `picks` follows the pool arm's hook; an empty return leaves the visit to the policy.

Environment: SCOPE_FILL 1 takes sets until k picks, 0 stops at one set; SCOPE_TOP is how many nodes by key can enter a set; SCOPE_PAIR_USES is the score taken off a set per earlier scope that held one of its pairs; POLICY_USES as in the policy.
"""
import collections, itertools, math, os
USES = float(os.environ.get('POLICY_USES', 1))
FILL = int(os.environ.get('SCOPE_FILL', 1))
TOP = int(os.environ.get('SCOPE_TOP', 40))
PAIR = float(os.environ.get('SCOPE_PAIR_USES', 0))
SKIP = {'Example'}


def fits(a, b):
    return bool((set(a.table_types) - SKIP) & (set(b.table_types) - SKIP))


def connected(nodes):
    got, todo = {0}, [0]
    while todo:
        i = todo.pop()
        for j in range(len(nodes)):
            if j not in got and fits(nodes[i], nodes[j]):
                got.add(j); todo.append(j)
    return len(got) == len(nodes)


def picks(pool, k, rng):
    p = pool.policy
    if not p.ids:
        return []
    key = {i: p.score[i] - USES * p.uses[i] - math.log(-math.log(rng.random() or 1e-12)) for i in p.ids}
    top = sorted(p.ids, key=lambda i: -key[i])[:TOP]
    held = pool.__dict__.setdefault('held_pairs', collections.Counter())
    chosen = []
    while len(chosen) < k:
        left = [i for i in top if i not in chosen]
        size = min(rng.choice((2, 3)), k - len(chosen), len(left))
        if not size:
            break
        best, value = None, -math.inf
        for s in itertools.combinations(left, size):
            v = sum(key[i] for i in s) - PAIR * sum(held[x] for x in itertools.combinations(sorted(s), 2))
            if v > value and connected([pool.nodes[i] for i in s]):
                best, value = s, v
        if best is None:
            best = left[:1]
        chosen += best
        if not FILL:
            break
    for i in chosen:
        p.uses[i] += 1
    held.update(itertools.combinations(sorted(chosen), 2))
    return chosen
