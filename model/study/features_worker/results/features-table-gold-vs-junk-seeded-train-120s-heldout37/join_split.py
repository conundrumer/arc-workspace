"""Splits non-DET tables that read two or more tables by what the join does to the parent it keeps most of. Gold is a label only.

For each parent class, columns of T with the parent's types are tried. The input grid counts as a parent where the clause reads it. Model columns are dropped first, so a DET choice doesn't count as a change. same: T equals a parent in rows. keeps: T's projection equals the parent, with one row of T per parent row (adds columns) or several (widens). narrows: T's projection is a strict subset of the parent. mixed: neither, for every parent.

  join_split.py NODES_DIR TASKS_DIR OUT STEP OFFSET
"""
import collections, itertools, json, os, sys, time, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe2 as P
import census as C

COMBOS = 40


def strip(t):
    keep = [c for c, x in enumerate(t.types) if x != 'Model']
    if len(keep) == len(t.types):
        return t
    return types.SimpleNamespace(types=tuple(t.types[c] for c in keep), ex=P.project(t.ex, keep))


def canon_of(t):
    return P.canon(t.types, t.ex)


def grid_tables(data, names, n):
    """The input grid as tables: cells with colors, and cells alone. Entries [1, i] are train and [2, i] are test."""
    ex = [frozenset() for _ in range(n)]
    for kind, key in ((1, 'train'), (2, 'test')):
        for i, pair in enumerate(data[key]):
            k = names.get((kind, i))
            if k is None:
                continue
            g = pair['input']
            h, w = len(g), len(g[0])
            ex[k] = frozenset((((r, h - 1 - r, c, w - 1 - c), g[r][c])) for r in range(h) for c in range(w))
    a = types.SimpleNamespace(types=('Position', 'Color'), ex=tuple(ex))
    return a, types.SimpleNamespace(types=('Position',), ex=P.project(tuple(ex), [0]))


def relate(t, p):
    """The best relation of T to parent P over column choices: 3 adds, 2 widens, 1 narrows, 0 none. Share kept is the rows of P that T's projection holds."""
    t, p = strip(t), strip(p)
    if len(p.types) > len(t.types):
        return 0, 0.0
    if canon_of(t) == canon_of(p):
        return 4, 1.0
    need = collections.Counter(p.types)
    have = collections.Counter(t.types)
    if need - have:
        return 0, 0.0
    best, kept = 0, 0.0
    slots = [[c for c, x in enumerate(t.types) if x == ty] for ty in p.types]
    tried = 0
    total = max(sum(map(len, p.ex)), 1)
    for cols in itertools.product(*slots):
        if len(set(cols)) != len(cols):
            continue
        tried += 1
        if tried > COMBOS:
            break
        ex = P.project(t.ex, cols)
        if all(x <= y for x, y in zip(ex, p.ex)):
            n = sum(map(len, ex))
            if ex == p.ex:
                one = all(len(a) == len(b) for a, b in zip(t.ex, ex))
                return (3 if one else 2), 1.0
            if n / total > kept:
                best, kept = 1, n / total
    return best, kept


def main():
    base, tasks_dir, out, step, offset = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    files = sorted(e.name for e in os.scandir(base) if e.name.endswith('.nodes.jsonl.zst'))[offset::step]
    done = {json.loads(x)['task'] for x in open(out)} if os.path.exists(out) else set()
    t0, ran = time.time(), 0
    with open(out, 'a') as w:
        for i, f in enumerate(files, 1):
            task = f.split('.')[0]
            if task in done:
                continue
            path = os.path.join(base, f)
            tables, token_of, _ = P.load(path)
            reps, _ = P.classes_of(tables, token_of)
            if len(reps) < 2:
                continue
            nodes = C.raw_nodes(path)
            src = C.sources(nodes)
            data = json.load(open(os.path.join(tasks_dir, task + '.json')))
            names = {n: k for k, n in enumerate(sorted({tuple(e[0]) for r in nodes.values() for e in r['x_rows'] or ()}))}
            grid = grid_tables(data, names, len(reps[0].ex))
            for r in reps:
                n = nodes[min(r.ids)]
                cf = C.clause_facts(n['clause'])
                if cf['kind'] == 'DET' or cf['kind'] == 'INIT' or (cf.get('distinct_reads', 0) < 2 and not cf['negated']):
                    continue
                s = src(min(r.ids))
                if s == {'shape'} or not s or C.product_split(r):
                    continue
                res = [relate(r, reps[p]) for p in r.parents]
                if '(input ' in (n['clause'] or ''):
                    res += [relate(r, g) for g in grid]
                kind = max((x[0] for x in res), default=0)
                kept = max((x[1] for x in res if x[0] == kind), default=0.0)
                w.write(json.dumps(dict(task=task, gold=int(r.gold), join=kind, kept=round(kept, 3), negated=cf['negated'], fixed=cf['fixed'], reads=cf.get('distinct_reads', 0), columns=len(r.types), parents=len(r.parents), clause=(n['clause'] or '')[:160])) + '\n')
            w.flush()
            ran += 1
            print('%d/%d %s | %.0f s | ETA %.0f s' % (i, len(files), task, time.time() - t0, (time.time() - t0) / ran * (len(files) - i)), flush=True)
    print('done', round(time.time() - t0), 's', flush=True)


if __name__ == '__main__':
    main()
