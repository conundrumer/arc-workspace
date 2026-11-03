"""The union of one set as an AND-OR graph. Writes graph-tables-SET.jsonl (one line per graph table), graph-prods-SET.jsonl (one line per query) and graph-tasks-SET.jsonl (one line per task) in work/lm/data-study/gold/gold-union.

  <runtime python> gold_union_graph.py SET
  <runtime python> gold_union_graph.py SET K N    takes the tasks at positions K, K + N, ... of the union and writes graph-*-SET-K.jsonl; concatenate the N files of each kind for the set

  Each output has a file <output>.code.json, {"code": {"sha", "dirty"}}: the commit of the code that wrote it (gold_union_code.py).

- A query is one QueryHash of the engine's export (gold_union_tables.py): union queries of one QueryHash are one query, with their Python identities in `idents` and the least of them in `ident`. A query that the row store lacks keeps its Python identity.
- A table is (QueryHash, Name), and a graph table is the class of tables of one map {Assignment → TableHash} (gold_union_tables.py gives the rule). A query's heads are the graph tables of every output the export gives it; the graph tables it uses are those of the tables its body uses. A graph table with more than one query is an OR. Roots are made by queries that use no table. The goal is an OR over options, one for each distinct set of graph tables that a kept case's OUT (or the pinned program's) uses; an option is an AND over its tables, with depth the most over them and cost the sum.
- A graph table has `members`, the union names of its tables ("key" for a query that isn't INIT, "key.name" for an INIT output), `tables`, its (QueryHash, Name) pairs, `map` and `capped`, and `exported`, false where the row store has no query for it (the engine refused the program, or the text didn't match), so the graph table has no map. `kit_unreachable` marks a graph table with a member in the `left` of synth-worker's maps-SET.jsonl: a union output whose replay in the search kit doesn't finish or isn't collected. `kit_unreachable_reason` is that `left` entry's reason. search-worker's outmap-SET.jsonl names the outputs of `left`.
- The queries and the tables they use come from the `text` of each kept case in union-keys-SET.jsonl.
- Depth: depth(T) = min over T's queries of 1 + max over the tables each uses of depth, roots at 0, as the least fixed point from infinity, so a cycle gives the right result. `depth_cases` is the union file's depth of the union table, the least over the cases.
- Query bits: the least bits of the query, joined by Python identity, over the rows of reread-kit/merged.jsonl, where the row's base_sha is the text of gold-export/flat/<task>.arclog, and the rows of reread5-all and reread6-all (whole lines only, so rows that stream in are taken as they land), one per union program (stem `<task>~<program sha>`), where the row's base_sha is the program's text (or_q.walk at b8e52e249 in both). Other queries have no bits. A graph table's `bits` is the least over its queries that have bits.
- Tree cost: cost(T) = min over queries of (query bits + sum of cost over the tables it uses), roots at 0, where a table that two queries use counts twice. `cost_known` counts a query without bits as unusable; `cost_low` counts it as 0 bits.
- Hyperpath: a set of queries that makes the goal, and each table that a chosen query uses, each query's bits counted once. `path` is the hyperpath of least bits, on known bits where one exists, else on low bits. `within_2` is the count of hyperpaths within 2 bits of it, up to CAP. A search pushes each set of chosen queries once, and at most STATES partial hyperpaths (10 times that for the cheapest path); past that it stops and `capped` is set. Where the cheapest-path search stops before a path, `path` is the tree-cost path (tree_path), an upper bound, with `exact` false. `within_2` is null where the count stopped before any path. `max_production` is the query on it with the most bits, with that query's depth (1 + the most depth of the tables it uses). `minimax_path` is the hyperpath whose largest query bits are least, and among those the one of least sum. Each path lists its queries' Python identities in `idents` and their QueryHashes in `queries`.
- Some output field names keep older terms: `productions` counts queries, `reads` lists the graph tables a query uses, `max_production` is the query with the most bits, and `bits_productions` counts queries with bits.
"""
import collections, glob, hashlib, heapq, json, os, re, sys
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-combined-cut/dedup-final')
import gold_case_counts as G
import gold_union_code
from gold_union import OUT, forms_of, union_rows
from gold_cheapest_common import D, program_lines
from gold_union_tables import Tables, tables_of

INF = float('inf')
CAP = 1000
STATES = 100000  # partial hyperpaths pushed per search; past this the search stops and says so
FLAT = D + 'gold/gold-export/flat/'
R = '/Users/davidlu/code/arc-workspace/'
MAPS = '/Users/davidlu/code/arc-workspace/work/synth-kaggle/kit-union-read/maps-%s.jsonl'
OUTMAP = D + 'sampler/search-worker/runs/search-union-reach-ramp22-heldout37/outmap-%s.jsonl'


def query_bits(t, merged):
    """{Python identity: bits} of the pinned queries that the bits record covers."""
    try:
        text = open(FLAT + t + '.arclog').read()
    except FileNotFoundError:
        return {}
    m = merged.get(t)
    if not m or m.get('base_sha') != hashlib.sha256('\n'.join(text.strip().splitlines()).encode()).hexdigest()[:16]:
        return {}
    qs, _ = forms_of(program_lines(text))
    got = {}
    for f in m['forms']:
        if f.get('bits') is not None and f['line'] < len(qs) and qs[f['line']]['kind'] == f['kind']:
            got[qs[f['line']]['ident']] = min(f['bits'], got.get(qs[f['line']]['ident'], INF))
    return got


def program_bits(t, u, cases, rows):
    """{Python identity: bits} of the queries of the task's union programs in the reread5 rows (stem `<task>~<program sha>`), where the row's base_sha is the program's text."""
    text = {}
    for c in cases:
        text.setdefault(u['cases'].get(c['case']), c['text'])
    got = {}
    for r in rows.get(t, []):
        qt = [x for x in text.get(r['task'].split('~')[1], '').splitlines() if x.strip()]
        if not qt or hashlib.sha256('\n'.join(qt).encode()).hexdigest()[:16] != r['base_sha']:
            continue
        starts = [i for i, x in enumerate(qt) if G.HEAD.match(x)]
        qs, _ = forms_of(qt)
        at = dict(zip(starts, qs))
        for f in r['forms']:
            g = at.get(int(f['line']))
            if g and f.get('bits') not in (None, 'None') and g['kind'] == f['kind']:
                got[g['ident']] = min(float(f['bits']), got.get(g['ident'], INF))
    return got


def ports():
    """{component: [port name]} from engine/lib/registry.sexpr: its outputs in order, then its inputs in order, which is the order of the engine's sub-relation index."""
    text = re.sub(r';[^\n]*', '', open(R + 'engine/lib/registry.sexpr').read())
    toks = re.findall(r'[()]|[^\s()]+', text)
    i, got = 0, {}

    def sexpr():
        nonlocal i
        if toks[i] != '(':
            i += 1
            return toks[i - 1]
        i += 1
        out = []
        while toks[i] != ')':
            out.append(sexpr())
        i += 1
        return out
    while i < len(toks):
        x = sexpr()
        if isinstance(x, list) and x[:1] == ['component']:
            part = {y[0]: [z[0] for z in y[1:] if isinstance(z, list)] for y in x if isinstance(y, list) and y[:1] in (['inputs'], ['outputs'])}
            got[x[1]] = part.get('outputs', []) + part.get('inputs', [])
    return got


def name(key, out):
    return '%d.%s' % (key, out) if out else str(key)


def graph(u, cases, T):
    """({QueryHash: dict(heads, uses, kind, ident, idents, keys)}, [goal option: [graph table]], {graph table: {(union key, Name)}}) from the kept cases' texts. Union queries with one QueryHash are one query. A use of an INIT is a use of one of its outputs. A query's heads are the graph tables of every output that the export gives it."""
    kept = {c for c, h in u['cases'].items() if h not in (u.get('left_out') or {})}
    queries, outs, goal, members = {}, collections.defaultdict(set), [], collections.defaultdict(set)
    texts = [(c['case'], c['text'], c['keys']) for c in cases if c['case'] in kept or c['case'] == 'pinned']
    key_of = {f['ident']: t['key'] for t in u['tables'] for f in t['forms']}
    for case, text, keys in texts:
        qt = program_lines(text)
        qs, _ = forms_of([x for x in qt if not x.startswith('(OUT')])
        keys = [key_of.get(f['ident'], k) for f, k in zip(qs, keys)]
        label = {f['label']: (k, f['kind'], f['ident']) for f, k in zip(qs, keys)}

        def used(n):
            rk, kind, ri = label[n[1]]
            out = n[2].lstrip('.').split('.')[0] if kind == 'INIT' else ''
            g = T.table(ri, out)
            if rk is not None and g not in T.maps:  # a graph table from the row store takes its members from its queries' outputs, below
                members[g].add((rk, out))
            if kind == 'INIT':
                outs[ri].add(out)
            return g
        for f, k in zip(qs, keys):
            body = f['line'][G.HEAD.match(f['line']).end():]
            uses = {used(n) for n in G.NAME.finditer(body) if n[1] in label}
            q = T.query.get(f['ident'], f['ident'])
            p = queries.setdefault(q, dict(key=k, kind=f['kind'], uses=uses, idents=set(), keys=set()))
            p['idents'].add(f['ident'])
            if k is not None:
                p['keys'].add(k)
        out_text = next(x for x in qt if x.startswith('(OUT'))
        goal.append([used(n) for n in G.NAME.finditer(out_text) if n[1] in label])
    for q, p in queries.items():
        p['ident'] = min(p['idents'])
        if q in T.names:
            p['heads'] = sorted({T.graph[q, n] for n in T.names[q]})
            for n in T.names[q]:
                members[T.graph[q, n]].update((k, n) for k in p['keys'])
        else:
            names = sorted({o for i in p['idents'] for o in outs[i]}) if p['kind'] == 'INIT' else []
            p['heads'] = sorted({T.table(p['ident'], o) for o in names or ['']})
            for o in names or ['']:
                members[T.table(p['ident'], o)].update((k, o) for k in p['keys'])
        p['uses'] = sorted(p['uses'])
        p['idents'] = sorted(p['idents'])
    return queries, goal, members


def fix(made, queries, value):
    """{table: value} at the least fixed point of min over the queries that make it of value(query, current values), from INF."""
    v = {k: INF for k in made}
    while True:
        new = {k: min((value(queries[p], v) for p in ps), default=INF) for k, ps in made.items()}
        if new == v:
            return v
        v = new


def hyperpaths(goals, made, queries, cost, bound, free=frozenset(), first=False):
    """[(bits, frozenset of queries)] of the hyperpaths for any goal option with bits <= bound, least first, up to CAP; and whether CAP or STATES stopped it. A table in `free` needs no query. The heap is ordered by a lower bound, so with `first` the one path returned is a cheapest one."""
    least = {k: min((cost(queries[p]) / len(queries[p]['heads']) for p in ps), default=INF) for k, ps in made.items()}  # a lower bound: a query's bits spread over its heads
    got, n, seen = [], len(goals), set()  # a set of chosen queries is pushed once, whatever the order it was reached in
    heap = [(sum(least[g] for g in o if g not in free), i, 0.0, tuple(o), frozenset(), frozenset(free)) for i, o in enumerate(goals)]
    heapq.heapify(heap)
    while heap:
        _, _, spent, todo, chosen, done = heapq.heappop(heap)
        todo = tuple(k for k in todo if k not in done)
        if not todo:
            got.append((spent, chosen))
            if first or len(got) >= CAP:
                return got, True
            continue
        k, rest = todo[0], todo[1:]
        for p in made[k]:
            c = cost(queries[p])
            if c == INF:
                continue
            nd = done | set(queries[p]['heads'])
            nt = tuple(dict.fromkeys(x for x in rest + tuple(queries[p]['uses']) if x not in nd))
            s = spent + c
            lb = s + sum(least[x] for x in nt)
            nc = chosen | {p}
            if lb <= bound + 1e-9 and nc not in seen:
                seen.add(nc)
                n += 1
                if n > (STATES * 10 if first else STATES):
                    return got, True
                heapq.heappush(heap, (lb, n, s, nt, nc, nd))
    return got, False


def cheapest(goals, made, queries, cost, free=frozenset()):
    """(bits, frozenset of queries) of the cheapest hyperpath for any goal option, with the tables in `free` made at no cost; None where there is none."""
    tree = fix(made, queries, lambda p, v: cost(p) + sum(0 if r in free else v[r] for r in p['uses']))
    bound = min(sum(0 if g in free else tree[g] for g in o) for o in goals)
    if bound == INF:
        return None
    got, _ = hyperpaths(goals, made, queries, cost, bound, free, first=True)
    return min(got, key=lambda x: x[0]) if got else None  # None also where the search stopped at STATES before a path


def tree_path(goals, made, queries, cost):
    """(bits, frozenset of queries): the path that takes, from the goal option of least tree cost down, each table's query of least tree cost, each query's bits counted once. Its bits are at or over the cheapest hyperpath's; None where the goal has no finite tree cost."""
    tree = fix(made, queries, lambda p, v: cost(p) + sum(v[r] for r in p['uses']))
    o = min(goals, key=lambda o: sum(tree[g] for g in o))
    if sum(tree[g] for g in o) == INF:
        return None
    chosen, todo = set(), list(o)
    while todo:
        k = todo.pop()
        p = min(made[k], key=lambda p: cost(queries[p]) + sum(tree[r] for r in queries[p]['uses']))
        if p not in chosen:
            chosen.add(p)
            todo.extend(queries[p]['uses'])
    return sum(cost(queries[p]) for p in chosen), frozenset(chosen)


def max_query(chosen, queries):
    """The query with the most bits among `chosen`: dict(ident, query, kind, bits, depth), or None."""
    if not chosen:
        return None
    i = max(chosen, key=lambda p: (queries[p]['bits'] or 0, p))
    return dict(ident=queries[i]['ident'], query=i, kind=queries[i]['kind'], bits=queries[i]['bits'], depth=queries[i]['depth'])


def minimax_path(goals, made, queries):
    """The minimax path: the hyperpath whose largest query bits are least, and among those the one of least sum: (bits, frozenset of queries), or None. Queries without bits are left out."""
    cuts = sorted({p['bits'] for p in queries.values() if p['bits'] is not None})

    def ok(c):
        v = fix(made, queries, lambda p, w: (0 if p['bits'] is not None and p['bits'] <= c else INF) + sum(w[r] for r in p['uses']))
        return min(sum(v[g] for g in o) for o in goals) < INF
    lo, hi = 0, len(cuts) - 1
    if not cuts or not ok(cuts[hi]):
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        lo, hi = (lo, mid) if ok(cuts[mid]) else (mid + 1, hi)
    return cheapest(goals, made, queries, lambda p: p['bits'] if p['bits'] is not None and p['bits'] <= cuts[lo] else INF)


def height(goals, made, queries, chosen):
    """The height of the hyperpath: the least over the goal options it makes of the most depth along its queries."""
    made_by = {h for p in chosen for h in queries[p]['heads']}
    memo = {}

    def h(k):
        if k not in memo:
            memo[k] = 0
            p = next(p for p in made[k] if p in chosen)
            memo[k] = 1 + max((h(r) for r in queries[p]['uses']), default=-1)
        return memo[k]
    return min(max(h(g) for g in o) for o in goals if all(g in made_by for g in o))


def one(u, cases, merged, T, rows5):
    t = u['task']
    tables = {x['key']: x for x in u['tables']}
    bits = query_bits(t, merged)
    for i, b in program_bits(t, u, cases, rows5).items():
        bits[i] = min(b, bits.get(i, INF))
    queries, goal, members = graph(u, cases, T)
    for p in queries.values():
        p['bits'] = min((bits[i] for i in p['idents'] if i in bits), default=None)
    goals = sorted({tuple(sorted(set(o))) for o in goal})
    goal = sorted({k for o in goals for k in o})
    made = collections.defaultdict(list)
    for i, p in queries.items():
        for h in p['heads']:
            made[h].append(i)
    for p in queries.values():
        for r in p['uses']:
            made.setdefault(r, [])
    depth = fix(made, queries, lambda p, v: 1 + max((v[r] for r in p['uses']), default=-1))
    known = fix(made, queries, lambda p, v: (p['bits'] if p['bits'] is not None else INF) + sum(v[r] for r in p['uses']))
    low = fix(made, queries, lambda p, v: (p['bits'] or 0) + sum(v[r] for r in p['uses']))
    rnd = lambda x: None if x == INF else round(x, 2)
    for p in queries.values():
        p['depth'] = 1 + max((depth[r] for r in p['uses']), default=-1)
    first = lambda k: min(members[k])
    rows = [dict(task=t, set=u['set'], table=k, members=sorted(name(*m) for m in members[k]), kind=tables[first(k)[0]]['kind'], productions=len(made[k]), depth=None if depth[k] == INF else depth[k],
                 depth_cases=min(tables[m[0]]['depth'] for m in members[k]), bits=min((queries[p]['bits'] for p in made[k] if queries[p]['bits'] is not None), default=None), cost_known=rnd(known[k]), cost_low=rnd(low[k]),
                 goal=k in (goal or ()), pinned=any(tables[m[0]]['pinned'] for m in members[k]), cases=len(set().union(*(tables[m[0]]['cases'] for m in members[k]))) + any(tables[m[0]]['pinned'] for m in members[k]),
                 root_det=tables[first(k)[0]]['kind'] == 'DET' and all(not queries[p]['uses'] for p in made[k]),
                 tables=sorted([q, n] for (q, n), g in T.graph.items() if g == k), map=T.maps.get(k), capped=T.capped.get(k, False), exported=k in T.maps) for k in sorted(made)]
    per = {}
    for r in rows:
        d = per.setdefault(str(min(r['depth'], 7) if r['depth'] is not None else None), dict(tables=0, productions=0, or_tables=0, shared=0, root_dets=0))
        d['tables'] += 1
        d['productions'] += r['productions']
        d['or_tables'] += r['productions'] > 1
        d['shared'] += r['cases'] >= 2
        d['root_dets'] += r['root_det']
    task = dict(task=t, set=u['set'], tables=len(rows), productions=len(queries), multi_head=sum(len(p['heads']) > 1 for p in queries.values()), goal=goal,
                lower=sum(r['depth'] is not None and r['depth'] < r['depth_cases'] for r in rows), per_depth=per, bits_productions=sum(p['bits'] is not None for p in queries.values()))
    if not goals:
        return rows, dict(task, error='goal table not found'), queries
    task.update(goals=[list(o) for o in goals], goal_depth=min(max(depth[g] for g in o) for o in goals), goal_depth_cases=min(max(min(tables[m[0]]['depth'] for m in members[g]) for g in o) for o in goals),
                cost_known=rnd(min(sum(known[g] for g in o) for o in goals)), cost_low=rnd(min(sum(low[g] for g in o) for o in goals)))
    on_known = any(all(known[g] < INF for g in o) for o in goals)
    cost = (lambda p: p['bits'] if p['bits'] is not None else INF) if on_known else (lambda p: p['bits'] or 0)
    best, stopped = hyperpaths(goals, made, queries, cost, min(sum(known[g] if on_known else low[g] for g in o) for o in goals), first=True)
    exact = bool(best)
    if not best:
        best = [tree_path(goals, made, queries, cost)] if tree_path(goals, made, queries, cost) else []
    if not best:
        return rows, dict(task, error='no hyperpath'), queries
    b, chosen = min(best, key=lambda x: x[0])
    near, capped = hyperpaths(goals, made, queries, cost, b + 2)
    on = sorted({h for p in chosen for h in queries[p]['heads']})
    task.update(path=dict(on='known bits' if on_known else 'low bits', bits=round(b, 2), height=height(goals, made, queries, chosen), productions=len(chosen), tables=on,
                          unknown=sum(queries[p]['bits'] is None for p in chosen), within_2=len({c for _, c in near}) or None, capped=capped, exact=exact, max_production=max_query(chosen, queries), idents=sorted(queries[p]['ident'] for p in chosen), queries=sorted(chosen)))
    flat = minimax_path(goals, made, queries)
    if flat:
        task.update(minimax_path=dict(bits=round(flat[0], 2), productions=len(flat[1]), height=height(goals, made, queries, flat[1]), max_production=max_query(flat[1], queries), idents=sorted(queries[p]['ident'] for p in flat[1]), queries=sorted(flat[1])))
    return rows, task, queries


def main():
    s = sys.argv[1]
    k, n = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, 1)
    tag = '%s-%d' % (s, k) if len(sys.argv) > 3 else s
    merged = {r['task']: r for r in map(json.loads, open(D + 'gold/gold-v3-dag-bits/reread-kit/merged.jsonl'))}
    rows5 = collections.defaultdict(list)
    for f in glob.glob(D + 'gold/gold-v3-dag-bits/reread[56]-all/rows-*.jsonl'):
        for l in open(f):
            if l.endswith('\n'):
                r = json.loads(l)
                if '~' in r['task']:
                    rows5[r['task'].split('~')[0]].append(r)
    cases = collections.defaultdict(list)
    for l in open(OUT + 'union-keys-%s.jsonl' % s):
        c = json.loads(l)
        cases[c['task']].append(c)
    outname, registry = {}, ports()
    if os.path.exists(OUTMAP % s):
        for r in map(json.loads, open(OUTMAP % s)):
            port = r['name'] or (lambda ps: ps[int(r['engine_index'])] if r['engine_index'] != '' and int(r['engine_index']) < len(ps) else None)(registry.get(r['component'], []))
            outname[r['task'], r['key'], r['output']] = (name(r['key'], port) if port else None) if r['component'] else str(r['key'])
    left = collections.defaultdict(dict)
    if os.path.exists(MAPS % s):
        for r in map(json.loads, open(MAPS % s)):
            for key, out, why in r.get('left') or []:
                left[r['task']][outname.get((r['task'], key, out)) or str(key)] = why
    part = '.part%d' % os.getpid()
    with open(OUT + 'graph-tables-%s.jsonl' % tag + part, 'w') as ft, open(OUT + 'graph-tasks-%s.jsonl' % tag + part, 'w') as fk, open(OUT + 'graph-prods-%s.jsonl' % tag + part, 'w') as fp:
        for u in union_rows(s)[k::n]:
            if not u.get('tables'):
                fk.write(json.dumps(dict(task=u['task'], set=u.get('set'), error=u.get('error', 'no tables'))) + '\n')
                continue
            T = tables_of(s, u)
            rows, task, queries = one(u, cases[u['task']], merged, T or Tables(), rows5)
            task.update(tables_source='row store' if T else 'none', shared_value_sets=T.shared_value_sets if T else None, unmatched=len(T.unmatched) if T else None)
            for r in rows:
                why = [left[u['task']][m] for m in r['members'] if m in left[u['task']]]
                r['kit_unreachable'] = bool(why)
                r['kit_unreachable_reason'] = why[0] if why else None
            ft.writelines(json.dumps(r) + '\n' for r in rows)
            fp.writelines(json.dumps(dict(task=u['task'], ident=p['ident'], query=i, idents=p['idents'], kind=p['kind'], heads=p['heads'], reads=p['uses'], bits=p['bits'], depth=p.get('depth'))) + '\n' for i, p in queries.items())
            fk.write(json.dumps(task) + '\n')
            fk.flush()
            print(u['task'], task.get('path', task.get('error')), flush=True)

    for f in ('tables', 'tasks', 'prods'):
        os.replace(OUT + 'graph-%s-%s.jsonl' % (f, tag) + part, OUT + 'graph-%s-%s.jsonl' % (f, tag))
        gold_union_code.write_sidecar(OUT + 'graph-%s-%s.jsonl' % (f, tag))


if __name__ == '__main__':
    main()
