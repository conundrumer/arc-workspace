"""The union of one set as an AND-OR graph. Writes graph-tables-SET.jsonl (one line per graph table), graph-prods-SET.jsonl (one line per query) and graph-tasks-SET.jsonl (one line per task) in work/lm/data-study/gold/gold-union.

  <runtime python> gold_union_graph.py SET
  <runtime python> gold_union_graph.py SET K N    takes the tasks at positions K, K + N, ... of the union and writes graph-*-SET-K.jsonl; concatenate the N files of each kind for the set
  With UNION_TASKS set (tasks separated by spaces), only those tasks are taken, K N name only the output file (K is 0 where not given), and the files are graph-*-SET-K.jsonl, never graph-*-SET.jsonl. GOLD_UNION_DIR is the folder of the inputs and outputs.

  Each output has a file <output>.code.json, {"code": {"sha", "dirty"}}: the commit of the code that wrote it (gold_union_code.py).

- A query is one QueryHash of the engine's export (gold_union_tables.py): union queries of one QueryHash are one query, with their Python identities in `idents` and the least of them in `ident`. A query that the row store lacks keeps its Python identity.
- A table is (QueryHash, Name), and a graph table is the class of tables of one map {Assignment → TableHash} (gold_union_tables.py gives the rule). A query's heads are the graph tables of every output the export gives it; the graph tables it uses are those of the tables its body uses, less the outputs of an INIT that its own inputs read. A read of an input block of an INIT, where the engine makes no table of that block (its body is one positive atom and any NOT atoms: `renamed`), uses the tables of those atoms. A graph table with more than one query is an OR. Roots are made by queries that use no table. The goal is an OR over options, one for each distinct set of graph tables that a kept case's OUT (or the pinned program's) uses; an option is an AND over its tables, with depth the most over them.
- A graph table has `members`, the union names of its tables ("key" for a query that is neither INIT nor RIGID_DET, "key.name" for an INIT output or a RIGID_DET table), `tables`, its (QueryHash, Name) pairs, `map` and `capped`, and `exported`, false where the row store has no query for it (the engine refused the program, or the text didn't match), so the graph table has no map.
- A task with a graph table that the row store lacks (named "u…", gold_union_tables.py) gets an error line "unmatched reads", with those tables and their members in `unmatched_reads`, and no table or query lines.
- The queries and the tables they use come from the `text` of each kept case in union-keys-SET.jsonl.
- Depth: depth(T) = min over T's queries of 1 + max over the tables each uses of depth, roots at 0, as the least fixed point from infinity, so a cycle gives the right result. `depth_cases` is the union file's depth of the union table, the least over the cases.
- Some output field names keep older terms: `productions` counts queries and `reads` lists the graph tables a query uses.
- The graph carries no bits, no cost, no cheapest or minimax path, and no kit reachability: no consumer of a target, a sample, a break point or a fit reads them. A task none of whose goal options has all its tables made gets an error line, 'goal not derivable', with its `goal_depth` infinite.
"""
import collections, functools, json, os, re, sys
import gold_case_counts as G
import gold_union_code
from gold_union import OUT, forms_of, union_rows
import study_zst as Z  # on the path since gold_union is imported
from gold_cheapest_common import program_lines
from gold_union_tables import Tables, tables_of

INF = float('inf')


def rigid_table(text, label, path):
    """The export's name of the table that the read `&label<path>` of a RIGID_DET in the program `text` takes. On an engine with arclog.rigid_slot_name (site-exp50 and later), that name: 'slot <i>' by the part's position in the form's canonical form, or 'pose'. On an older engine, 'slot N' for `.rN` and 'pose' for `.pose`. Else ''."""
    try:
        import arclog
        return arclog.rigid_slot_name(text, '&' + label + path).split('.')[0] if hasattr(arclog, 'rigid_slot_name') else old_rigid_table(path)
    except (ImportError, ValueError):
        return old_rigid_table(path)


def old_rigid_table(path):
    step = path.lstrip('.').split('.')[0]
    return 'slot ' + step[1:] if re.fullmatch(r'r\d+', step) else 'pose' if step == 'pose' else ''


FACTS = ('input', 'ex_input', 'ex_output')


def sexpr(text):
    """The nested lists of the s-expression `text`."""
    stack = [[]]
    for t in re.findall(r'[()]|[^\s()]+', text):
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop()
            stack[-1].append(x)
        else:
            stack[-1].append(t)
    return stack[0][0]


@functools.cache
def renamed(line, block):
    """None where the engine gives the input `block` of the INIT `line` a table. Else the heads of its atoms: the one positive atom, then the NOT atoms. The engine gives no table to an input block whose body is one positive atom and any number of NOT atoms, each of a fact relation or an `&rN` relation (gives_no_table in engine/arclog-tables/src/tables.rs). Its rows are those of the positive atom, less the rows of the NOT atoms."""
    def find(x):
        if isinstance(x, list):
            if x[:1] == [block] and len(x) > 2 and isinstance(x[1], list) and all(isinstance(c, list) and c[:1] and str(c[0]).startswith(':') for c in x[1]):
                return x
            return next((f for f in map(find, x) if f), None)
    found = find(sexpr(line))
    if not found:
        return None
    pos, neg = [], []
    for c in found[2:]:
        not_ = isinstance(c, list) and len(c) == 2 and c[0] == 'NOT'
        atom = c[1] if not_ else c
        if not (isinstance(atom, list) and atom and isinstance(atom[0], str) and (atom[0].startswith('&') or atom[0] in FACTS)):
            return None
        (neg if not_ else pos).append(atom[0])
    return tuple(pos + neg) if len(pos) == 1 else None


def name(key, out):
    return '%d.%s' % (key, out) if out else str(key)


def graph(u, cases, T):
    """({QueryHash: dict(heads, uses, kind, ident, idents, keys)}, [goal option: [graph table]], {graph table: {(union key, Name)}}) from the kept cases' texts. Union queries with one QueryHash are one query. A use of an INIT is a use of one of its outputs, or of the tables of the atoms of an input block that has no table, and a use of a RIGID_DET is a use of its table 'slot N' or 'pose'. A query's heads are the graph tables of every output that the export gives it."""
    kept = {c for c, h in u['cases'].items() if h not in (u.get('left_out') or {})}
    queries, outs, goal, members = {}, collections.defaultdict(set), [], collections.defaultdict(set)
    texts = [(c['case'], c['text'], c['keys']) for c in cases if c['case'] in kept]  # the pinned program is a case of u['cases'] where the union keeps it
    key_of = {f['ident']: t['key'] for t in u['tables'] for f in t['forms']}
    for case, text, keys in texts:
        qt = program_lines(text)
        qs, _ = forms_of([x for x in qt if not x.startswith('(OUT')])
        keys = [key_of.get(f['ident'], k) for f, k in zip(qs, keys)]
        label = {f['label']: (k, f['kind'], f['ident']) for f, k in zip(qs, keys)}
        lines = {f['label']: f['line'] for f in qs}

        def used(n):
            rk, kind, ri = label[n[1]]
            out = n[2].lstrip('.').split('.')[0] if kind == 'INIT' else rigid_table(text, n[1], n[2]) if kind == 'RIGID_DET' else ''
            atoms = renamed(lines[n[1]], out) if kind == 'INIT' and out and not T.has(ri, out) else None
            if atoms is not None:  # an input block that the engine makes no table of: its rows are those of its atoms
                return {g for a in atoms for m in G.NAME.finditer(a) if m[1] in label for g in used(m)}
            g = T.table(ri, out)
            if rk is not None and g not in T.maps:  # a graph table from the row store takes its members from its queries' outputs, below
                members[g].add((rk, out))
            if kind in ('INIT', 'RIGID_DET'):
                outs[ri].add(out)
            return {g}
        for f, k in zip(qs, keys):
            body = f['line'][G.HEAD.match(f['line']).end():]
            uses = {g for n in G.NAME.finditer(body) if n[1] in label for g in used(n) if not (f['kind'] == 'INIT' and n[1] == f['label'])}  # an input of an INIT that reads its outputs (reads-outputs in engine/lib/registry.sexpr) makes a fixpoint, not a use
            q = T.query.get(f['ident'], f['ident'])
            p = queries.setdefault(q, dict(key=k, kind=f['kind'], uses=uses, idents=set(), keys=set()))
            p['idents'].add(f['ident'])
            if k is not None:
                p['keys'].add(k)
        out_text = next(x for x in qt if x.startswith('(OUT'))
        goal.append([g for n in G.NAME.finditer(out_text) if n[1] in label for g in used(n)])
    for q, p in queries.items():
        p['ident'] = min(p['idents'])
        if q in T.names:
            p['heads'] = sorted({T.graph[q, n] for n in T.names[q]})
            for n in T.names[q]:
                members[T.graph[q, n]].update((k, n) for k in p['keys'])
        else:
            names = sorted({o for i in p['idents'] for o in outs[i]}) if p['kind'] in ('INIT', 'RIGID_DET') else []
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


def one(u, cases, T):
    t = u['task']
    tables = {x['key']: x for x in u['tables']}
    queries, goal, members = graph(u, cases, T)
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
    for p in queries.values():
        p['depth'] = 1 + max((depth[r] for r in p['uses']), default=-1)
    first = lambda k: min(members[k])
    rows = [dict(task=t, set=u['set'], table=k, members=sorted(name(*m) for m in members[k]), kind=tables[first(k)[0]]['kind'], productions=len(made[k]), depth=None if depth[k] == INF else depth[k],
                 depth_cases=min(tables[m[0]]['depth'] for m in members[k]),
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
                lower=sum(r['depth'] is not None and r['depth'] < r['depth_cases'] for r in rows), per_depth=per)
    if not goals:
        return rows, dict(task, error='goal table not found'), queries
    task.update(goals=[list(o) for o in goals], goal_depth=min(max(depth[g] for g in o) for o in goals), goal_depth_cases=min(max(min(tables[m[0]]['depth'] for m in members[g]) for g in o) for o in goals))
    if task['goal_depth'] == INF:
        return rows, dict(task, error='goal not derivable'), queries
    return rows, task, queries


def main():
    s = sys.argv[1]
    k, n = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, 1)
    only = os.environ.get('UNION_TASKS', '').split()
    tag = '%s-%d' % (s, k) if len(sys.argv) > 3 or only else s
    cases = collections.defaultdict(list)
    for l in Z.open_text(OUT + 'union-keys-%s.jsonl' % s):
        c = json.loads(l)
        cases[c['task']].append(c)
    part = str(os.getpid())  # the suffix of the .part files, so that two processes of one tag keep apart
    with Z.open_part(OUT + 'graph-tables-%s.jsonl' % tag, suffix=part) as ft, Z.open_part(OUT + 'graph-tasks-%s.jsonl' % tag, suffix=part) as fk, Z.open_part(OUT + 'graph-prods-%s.jsonl' % tag, suffix=part) as fp:
        for u in [u for u in union_rows(s) if u['task'] in only] if only else union_rows(s)[k::n]:
            if not u.get('tables'):
                fk.write(json.dumps(dict(task=u['task'], set=u.get('set'), error=u.get('error', 'no tables'))) + '\n')
                continue
            try:
                T = tables_of(s, u)  # a task with no row store of an accepted version gets an error line, not unmatched tables
                rows, task, queries = one(u, cases[u['task']], T or Tables())
            except Exception as e:  # noqa: BLE001  a task the graph can't build: its error line, and the run goes on
                fk.write(json.dumps(dict(task=u['task'], set=u.get('set'), error='graph: %s: %s' % (type(e).__name__, str(e)[:200]))) + '\n')
                print(u['task'], 'graph error', type(e).__name__, str(e)[:200], flush=True)
                continue
            task.update(tables_source='row store' if T else 'none', shared_value_sets=T.shared_value_sets if T else None, unmatched=len(T.unmatched) if T else None)
            u_rows = [r for r in rows if r['table'].startswith('u')]
            if u_rows:  # a read with no row store table is a fault of the union, the store or the graph, so the task gets an error line
                fk.write(json.dumps(dict(task=u['task'], set=u.get('set'), error='unmatched reads: %d tables, %s' % (len(u_rows), '; '.join('%s %s' % (r['table'], ','.join(r['members'])) for r in u_rows[:5])),
                                         unmatched_reads=[dict(table=r['table'], kind=r['kind'], members=r['members']) for r in u_rows])) + '\n')
                print(u['task'], 'unmatched reads', len(u_rows), flush=True)
                continue
            ft.writelines(json.dumps(r) + '\n' for r in rows)
            fp.writelines(json.dumps(dict(task=u['task'], ident=p['ident'], query=i, idents=p['idents'], kind=p['kind'], heads=p['heads'], reads=p['uses'], depth=p.get('depth'))) + '\n' for i, p in queries.items())
            fk.write(json.dumps(task) + '\n')
            fk.flush()
            print(u['task'], task.get('error', 'goal_depth %s' % task['goal_depth']), flush=True)

    for f in ('tables', 'tasks', 'prods'):
        Z.commit(OUT + 'graph-%s-%s.jsonl' % (f, tag), part)
        gold_union_code.write_sidecar(OUT + 'graph-%s-%s.jsonl' % (f, tag))


if __name__ == '__main__':
    main()
