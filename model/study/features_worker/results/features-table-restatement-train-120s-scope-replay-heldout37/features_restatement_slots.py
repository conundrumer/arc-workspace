"""Two reads per task, on node records.

Slots: each distinct scope is a set of picked node tokens. A slot is redundant when its table is in the same plain class as another slot, or when a one-source relation from another slot gives it. The same count with sources' examples rotated is the chance baseline. A visit weights a scope by the nodes it made.

Soft count: tables with one Position column are partitions of the grid's cells, with a cell's label being the rest of its rows, and absent cells one label. For each pair, H(T|S) is pooled over examples and cells. Z = 1 - VI / H(T,S). The effective count is the sum over tables of 1 / (sum over tables of Z). The count is also given with Z cut to 0 or 1 at each of several levels.

  slots.py NODES_DIR OUT STEP [OFFSET]
"""
import collections, json, math, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_restatement_probe as P


def scope_sets(path):
    import subprocess
    out = collections.Counter()
    for line in subprocess.run(['zstd', '-dcq', path], capture_output=True, text=True).stdout.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get('scope'):
            out[tuple(sorted(int(x) for x in r['scope']))] += 1
    return out


def read_slots(reps, token_of, scopes):
    rep_of = {x: r.i for r in reps for x in r.ids}
    slot = {}
    for s in scopes:
        for tok in s:
            slot[tok] = rep_of.get(token_of.get(tok))
    used = {x for x in slot.values() if x is not None}
    by_key = collections.defaultdict(set)
    for i in used:
        by_key[hash(reps[i].canon)].add(i)
    edges, null = set(), set()

    def sink(store):
        def mark(rel, types, ex, sid):
            if not any(ex):
                return
            for x in by_key.get(P.plain_key(types, ex, example=False), ()):
                if x != sid:
                    store.add((sid, x))
        return mark

    domain = collections.defaultdict(lambda: [set() for _ in reps[0].ex])
    for t in reps:
        for c, ty in enumerate(t.types):
            for i, rows in enumerate(t.ex):
                domain[ty][i].update(r[c] for r in rows)
    rotated = {ty: P.rotate(v) for ty, v in domain.items()}
    real, fake = sink(edges), sink(null)
    for i in used:
        s = reps[i]
        P.one_source(s.types, s.ex, domain, i, real)
        if len(s.ex) > 1:
            ex, dom = P.wrong_examples(s, domain, rotated)
            if ex is not None:
                P.one_source(s.types, ex, dom, i, fake)
    tot = collections.Counter()
    hist = collections.Counter()
    for s, w in scopes.items():
        cl = [slot[t] for t in s]
        known = [c for c in cl if c is not None]
        seen, redundant, chance, dup = set(), 0, 0, 0
        for j, c in enumerate(known):
            others = known[:j] + known[j + 1:]
            d = c in others
            r = d or any((o, c) in edges for o in others)
            q = d or any((o, c) in null for o in others)
            dup += d
            redundant += r
            chance += q
        tot['slots'] += w * len(cl)
        tot['unknown'] += w * (len(cl) - len(known))
        tot['same class'] += w * dup
        tot['restated'] += w * redundant
        tot['chance'] += w * chance
        tot['nodes'] += w
        hist[min(redundant, 6)] += w
    return dict(scopes=len(scopes), totals=dict(tot), redundant_slots=dict((str(k), v) for k, v in hist.items()))


def soft(reps):
    T = [r for r in reps if len(P.position_columns(r.types)) == 1 and any(r.ex[1:])]
    if len(T) < 2:
        return None
    if len(T) > 300:
        T = sorted(T, key=lambda r: r.i)[:300]
    nex = len(T[0].ex)
    labels = []  # per example: tables by cells
    for e in range(nex):
        cells = sorted({r[P.position_columns(t.types)[0]] for t in T for r in t.ex[e]})
        at = {c: i for i, c in enumerate(cells)}
        M = np.zeros((len(T), len(cells)), dtype=np.int64)
        for ti, t in enumerate(T):
            p = P.position_columns(t.types)[0]
            rest = [c for c in range(len(t.types)) if c != p]
            got = collections.defaultdict(set)
            for r in t.ex[e]:
                got[r[p]].add(tuple(r[c] for c in rest))
            names = {}
            for pos, v in got.items():
                M[ti, at[pos]] = names.setdefault(frozenset(v), len(names) + 1)
        if len(cells):
            labels.append(M)

    def counts_entropy(x):
        _, c = np.unique(x, return_counts=True)
        return float(c @ np.log2(x.size / c))

    n = len(T)
    H = np.zeros(n)
    for M in labels:
        for i in range(n):
            H[i] += counts_entropy(M[i])
    J = np.zeros((n, n))
    for M in labels:
        for i in range(n):
            base = M[i] * (M.max() + 1)
            for j in range(i + 1, n):
                J[i, j] += counts_entropy(base + M[j])
    J = J + J.T
    np.fill_diagonal(J, H)
    cond = J - H[None, :]  # cond[t, s]: H(T|S), with J[t, s] - H[s]
    cond = J - H.reshape(1, -1)
    vi = cond + cond.T
    with np.errstate(divide='ignore', invalid='ignore'):
        Z = np.where(J > 0, 1 - vi / J, 1.0)
    Z = np.clip(Z, 0, 1)
    np.fill_diagonal(Z, 1)
    eff = float((1 / Z.sum(1)).sum())
    binary = (Z >= .999).astype(float)
    exact = float((1 / binary.sum(1)).sum())
    hard = {}
    for cut in (.9, .8, .5):
        b = (Z >= cut).astype(float)
        hard[str(cut)] = float((1 / b.sum(1)).sum())
    return dict(tables=n, effective=eff, exact=exact, at_cut=hard)


def main():
    base, out, step = sys.argv[1], sys.argv[2], int(sys.argv[3])
    offset = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    files = sorted(e.name for e in os.scandir(base) if e.name.endswith('.nodes.jsonl.zst'))[offset::step]
    done = {json.loads(x)['task'] for x in open(out)} if os.path.exists(out) else set()
    t0, ran = time.time(), 0
    with open(out, 'a') as w:
        for i, f in enumerate(files, 1):
            task = f.split('.')[0]
            if task in done:
                continue
            t1 = time.time()
            path = os.path.join(base, f)
            tables, token_of, info = P.load(path)
            reps, funnel = P.classes_of(tables, token_of)
            if len(reps) < 2:
                continue
            row = dict(task=task, classes=len(reps), slots=read_slots(reps, token_of, scope_sets(path)), soft=soft(reps))
            row['seconds'] = round(time.time() - t1, 1)
            w.write(json.dumps(row) + '\n')
            w.flush()
            ran += 1
            print('%d/%d %s %.1f s | ETA %.0f s' % (i, len(files), task, time.time() - t1, (time.time() - t0) / ran * (len(files) - i)), flush=True)
    print('done', round(time.time() - t0), 's', flush=True)


if __name__ == '__main__':
    main()
