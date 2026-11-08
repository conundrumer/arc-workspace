"""rule_vs_skeleton.py --skeleton DIR --graphs DIR [--maps engine|graph] [--tasks T,T,...] [--limit N] [--shard k/N] [--out FILE] [--anywhere]

Compares, for each sample of each task's skeleton file in DIR, the sample's `target_queries` (skeleton.py's) with the targets that `points_write.target_rule` gives for the sample's state, and lists each query that
only one side has. It checks the rule against skeleton.py; the extractor does not run it. It prints one JSON line a task, as it goes, and a last line with the totals.

--graphs DIR is the folder of the union graph files that the skeleton was made from (`graph-prods-SET.jsonl`, `graph-tables-SET.jsonl`); a task whose lines of them are not those that its skeleton records is skipped.
--maps says where the maps of the state's tables come from:
- `engine`: the engine computes the scope of each sample (the extractor's own scope_maps). Run it as the extractor is run (the runtime python, with PYTHONPATH holding the kit's extractor folder and the
  engine wheel's site folder). It also counts, for the union queries of each state, whether the table's map in the scope equals the map of its graph table (`member tables`).
- `graph`: each member's map is the map of the graph table that skeleton.py gave the member's table (graph_member_maps). No engine runs. The rule then differs from skeleton.py only where its parts decide
  otherwise on the graph files alone, so this shows which disagreements do not depend on the engine.
--limit N takes the first N tasks. --shard k/N takes the tasks with crc32(task) % N == k (one --out file for each shard). --anywhere makes the rule's progress part compare a TableHash with the TableHashes of all assignments of all member tables, in place of the member tables' TableHashes at that assignment (the contract's wording);
`rule differs when anywhere` counts the samples whose targets change.

With --out FILE (`.jsonl`, written as a zstd stream) it writes one line for each query that only one side has: task, sample, `side` (`only rule`: the rule has it and skeleton.py lacks it; `only skeleton`: skeleton.py
has it and the rule lacks it), the query, the `part` of the rule that decided it (for `only skeleton`: BY_* of points_write; for `only rule`: skeleton.py's `no_progress_queries` and `refused_target_queries` of the
sample are on the line), and `detail`: the graph tables the query reads that no member's table stands for, and the count, for each graph table it computes, of its (assignment, TableHash) pairs that no member's map has. A restart skips the tasks that FILE holds a `done` line for."""
import argparse
import collections
import json
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # model/study
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # model/study/samples
import study_zst as Z  # noqa: E402
from points_write import GraphMismatch, Reject, UNHASHED, load_engine, new_run, scope_maps, scope_of, target_rule, task_graph  # noqa: E402
from union_forms import LineIndex  # noqa: E402


def graph_member_maps(state, union, graph):
    """One map for each graph table that skeleton.py can give a member's table, for the tables that have a map. The rule reads only the set of the maps. One QueryHash can be made by several graph queries
    (`graph_queries`) with different heads, and skeleton.py's `producers` take the heads of the graph query that made the member in the state; a query with one Name is given the head of each of them, else the
    table that the record's `graph_tables` names."""
    out = {}
    for q in state:
        r = union[q]
        for name, t in r['graph_tables'].items():
            ts = {t}
            if len(r['graph_tables']) == 1:
                ts |= {x for g in r['graph_queries'] for x in graph.heads.get(g, ())}
            for x in sorted(ts):
                if graph.maps.get(x) is not None:
                    out[q, f'{name}@{x}'] = graph.maps[x]
    return out


def detail(h, union, graph, member_maps):
    """Why a union query h is or is not a target, in the graph's terms: the graph tables it reads that no member's table stands for, and its computed graph tables with their count of (assignment, TableHash) pairs that no member's map has."""
    maps = set(member_maps.values())
    here = {e for m in maps for e in m}
    out = []
    for g in union[h]['graph_queries']:
        if g not in graph.reads:
            out.append({'graph query': g, 'in the graph files': False})
            continue
        unstood = {t: ('no map' if graph.maps.get(t) is None else 'no member table has that map') for t in graph.reads[g] if graph.maps.get(t) is None or graph.maps[t] not in maps}
        new = {t: sum(1 for e in (graph.maps.get(t) or ()) if e[1] != UNHASHED and e not in here) for t in graph.heads[g]}
        out.append({'graph query': g, 'reads not stood for': unstood, 'pairs of the computed graph tables that no member map has': new})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('--skeleton', type=Path, required=True)
    ap.add_argument('--graphs', type=Path, required=True)
    ap.add_argument('--maps', choices=('engine', 'graph'), default='engine')
    ap.add_argument('--tasks')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--anywhere', action='store_true')
    ap.add_argument('--plan', default='ordered', help='the writer plan of the engine process (engine maps only)')
    args = ap.parse_args()
    tasks = sorted(p.stem for p in args.skeleton.glob('*.jsonl'))
    if args.tasks:
        tasks = [t for t in tasks if t in set(args.tasks.split(','))]
    k, n = map(int, args.shard.split('/'))
    tasks = [t for t in tasks if zlib.crc32(t.encode()) % n == k]
    if args.limit:
        tasks = tasks[:args.limit]
    done: set[str] = set()
    if args.out is not None and Z.exists(args.out):
        with Z.open_text(args.out) as f:
            done = {rec['done'] for rec in map(json.loads, f) if 'done' in rec}
    out = Z.open_text(args.out, 'a', line_buffering=True) if args.out is not None else None
    split = json.loads(open(args.skeleton / f'{tasks[0]}.jsonl').readline())['set'] if tasks else 'train'
    idx = {'prods': LineIndex(args.graphs / f'graph-prods-{split}.jsonl'), 'tables': LineIndex(args.graphs / f'graph-tables-{split}.jsonl')}
    env_base = smp = None
    if args.maps == 'engine':
        env_base, _, smp = load_engine(args.plan)
    total: collections.Counter = collections.Counter()
    t0 = time.time()
    todo = [t for t in tasks if t not in done]
    for i, task in enumerate(todo, 1):
        records = [json.loads(line) for line in open(args.skeleton / f'{task}.jsonl')]
        head = records[0]
        union = {r['hash']: r for r in records if r['record'] == 'query'}
        try:
            graph = task_graph(idx, task, head)
        except GraphMismatch as e:
            print(json.dumps(dict(task=task, skipped=str(e))), flush=True)
            total['tasks skipped: the graph files are not the skeleton\'s'] += 1
            continue
        run = new_run(env_base, smp, task) if env_base is not None else None
        c: collections.Counter = collections.Counter()
        for s in (r for r in records if r['record'] == 'sample'):
            state = frozenset(s['state']['queries'])
            c['samples'] += 1
            if run is not None:
                assert env_base is not None
                try:
                    texts, _ = scope_of(sorted(state), union)
                    _, pg = run.scope(tuple(texts))
                    maps = scope_maps(env_base['wr'], pg)
                except Exception as e:  # a refusal of the engine, or a scope that cannot be made: the sample is left out and counted
                    c['samples left out: ' + (str(e) if isinstance(e, Reject) else type(e).__name__)[:60]] += 1
                    continue
                for q in state:
                    for name, t in union[q]['graph_tables'].items():
                        have, want = maps.get((q, name)), graph.maps.get(t)
                        c['member tables: ' + ('no table in the scope' if have is None else 'graph table has no map' if want is None else 'map equal' if have == want else 'map differs')] += 1
            else:
                maps = graph_member_maps(state, union, graph)
            verdict = target_rule(state, maps, graph, union, args.anywhere)
            if args.anywhere and set(verdict.targets) != set(target_rule(state, maps, graph, union).targets):
                c['rule differs when anywhere'] += 1
            got, want = set(verdict.targets), set(s['target_queries'])
            c['unwritten'] += verdict.unwritten
            if got == want:
                c['equal'] += 1
                continue
            c['differ'] += 1
            for side, qs in (('only rule', got - want), ('only skeleton', want - got)):
                for h in sorted(qs):
                    part = verdict.why.get(h, 'a target') if side == 'only skeleton' else 'a target'
                    c[f'{side}: {part}'] += 1
                    if out is not None:
                        extra = dict(skeleton_no_progress=s['no_progress_queries'], skeleton_refused=s['refused_target_queries']) if side == 'only rule' else {}
                        out.write(json.dumps(dict(task=task, sample=s['id'], side=side, query=h, part=part, detail=detail(h, union, graph, maps), **extra)) + '\n')
        if out is not None:
            out.write(json.dumps(dict(done=task)) + '\n')
        total.update(c)
        print(json.dumps(dict(task=task, **c)), flush=True)
        el = time.time() - t0
        print(f'{i}/{len(todo)} tasks, {i / max(el, 1e-9):.2f} tasks/s, ETA {el / i * (len(todo) - i):.0f}s', file=sys.stderr, flush=True)
    if out is not None:
        out.close()
    print(json.dumps(dict(task='all', **total)), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
