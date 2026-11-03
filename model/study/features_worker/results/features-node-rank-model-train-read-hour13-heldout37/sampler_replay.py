"""Exact replay of Policy.scope for one hour run: rebuilds each opening's picks and each node's uses from the process seed, checked against the logged fids and the bank's uses.

  replay(R, base) -> dict(openings=[...], ok, bad, refused, flip, uses, seeds)

Each opening: dict(v=visit index, n=alive nodes, best=[5 node ids], rest=[node ids], d0).
The stream is Python's random.Random('<task>.task.json <seed>'); numpy's RandomState gives the same doubles in bulk.
"""
import random
import numpy as np

KBEST, K, CAP = 5, 6, 96


def stream(task, seed):
    g = random.Random('%s.task.json %d' % (task, seed))
    s = g.getstate()[1]
    rs = np.random.RandomState()
    rs.set_state(('MT19937', np.array(s[:-1], np.uint32), s[-1]))
    return rs


def anc_of(R):
    nf = max(R.forms) + 1
    anc = [None] * nf
    for f in range(nf):
        a = {f}
        for p in R.parents[f]:
            a |= anc[p]
        anc[f] = frozenset(a)
    return anc


def draw(R, anc, rs, uses, n):
    """One Policy.scope at n alive nodes. Gives (best, rest, fids, keys)."""
    r = rs.random_sample(n)
    r = np.where(r == 0, 1e-12, r)
    key = R.score[:n] - uses[:n] - np.log(-np.log(r))
    m = min(KBEST, n)
    if m < n:
        part = np.argpartition(-key, m - 1)[:m]
        best = part[np.argsort(-key[part], kind='stable')]
    else:
        best = np.argsort(-key, kind='stable')
    rest = []
    if n > m:
        u = uses[:n].astype(float).copy()
        u[best] = 1e18
        rest = [int(np.argmin(u))]
    seen = set()
    for i in list(map(int, best)) + rest:
        f = int(R.nform[i])
        got = anc[f] - seen
        if len(seen) + len(got) <= CAP:
            seen |= got
    return [int(b) for b in best], rest, seen, key


def try_block(R, anc, task, sd, bv, uses, first_block):
    rs = stream(task, sd)
    opens, badl, good, refused, flip = [], [], 0, 0, 0
    parked = not first_block
    for j, v in bv:
        r0 = rs.random_sample() if parked else 1.0
        n = int(np.searchsorted(R.age, v['d0'], side='right'))
        new_scope = not v['resume'] or r0 >= .3
        if v['resume'] and r0 >= .3:
            flip += 1
        if not v['resume'] and r0 < .3:
            badl.append((j, 'resume coin'))
            if good == 0 and len(badl) > 2:
                return dict(good=0, badl=badl, opens=[], uses=uses, refused=0, flip=0)
        if new_scope:
            if n > 0:
                st = rs.get_state()
                u0 = uses.copy()
                best, rest, seen, key = draw(R, anc, rs, uses, n)
                want = set(v['fids'])
                if seen != want:
                    # a scope the engine refused takes its picks, then no kind and no visit. Try up to three such scopes.
                    rs.set_state(st)
                    uu = u0.copy()
                    found = False
                    hidden = []
                    for k in range(3):
                        b2, r2, s2, _ = draw(R, anc, rs, uu, n)
                        uu[b2 + r2] += 1
                        hidden.append(dict(v=-1, n=n, best=b2, rest=r2, d0=v['d0']))
                        st2 = rs.get_state()
                        rs.random_sample()  # the resume coin of the next try
                        b3, r3, s3, key3 = draw(R, anc, rs, uu, n)
                        if s3 == want:
                            uses[:] = uu
                            opens += hidden
                            best, rest, seen, key = b3, r3, s3, key3
                            refused += k + 1
                            good += 1
                            found = True
                            break
                        rs.set_state(st2)
                        rs.random_sample()
                    if not found:
                        rs.set_state(st)
                        best, rest, seen, key = draw(R, anc, rs, u0, n)
                        uses[:] = u0
                        badl.append((j, 'fids'))
                        if good == 0 and len(badl) > 2:
                            return dict(good=0, badl=badl, opens=[], uses=uses, refused=0, flip=0)
                else:
                    good += 1
                opens.append(dict(v=j, n=n, best=best, rest=rest, d0=v['d0']))
                uses[best + rest] += 1
            rs.random_sample()  # the kind
        parked = True
    return dict(good=good, badl=badl, opens=opens, uses=uses, refused=refused, flip=flip)


def replay(R, base, verbose=False):
    task = R.task
    vs = [v for v in R.visits if v['d0'] < R.draws]  # visits after the last bank write have nodes the bank lacks
    anc = anc_of(R)
    uses = np.zeros(R.n, np.int64)
    blocks = sorted({v['block'] for v in vs})
    out, seeds, bad, ok, refused, flip = [], [], [], 0, 0, 0
    next_seed = base + 1
    for b in blocks:
        bv = [(j, v) for j, v in enumerate(vs) if v['block'] == b]
        chosen = None
        for sd in list(range(next_seed, next_seed + 60)) + list(range(base, next_seed)):
            res = try_block(R, anc, task, sd, bv, uses.copy(), b == blocks[0])
            if res['good'] >= max(1, len([1 for j, v in bv if not v['resume']]) // 2):
                chosen = (sd, res)
                break
        if chosen is None:
            return dict(failed=b, seeds=seeds, openings=out, ok=ok, bad=bad, refused=refused, flip=flip, uses=uses)
        sd, res = chosen
        seeds.append(sd)
        next_seed = sd + 1
        uses = res['uses']
        out += res['opens']
        ok += res['good']
        bad += res['badl']
        refused += res['refused']
        flip += res['flip']
        if verbose:
            print('block', b, 'seed', sd, 'openings', len(res['opens']), 'good', res['good'], 'bad', len(res['badl']), 'refused', res['refused'], 'flip', res['flip'], flush=True)
    return dict(openings=out, seeds=seeds, ok=ok, bad=bad, refused=refused, flip=flip, uses=uses)
