"""scope_diag.py --skeleton DIR --graphs DIR --rows DIR --tasks T,T,... [--draws GLOB|DIR] [--out FILE] [--limit N]

Shows, for the engine's scope of a state, what the target rule reads. It is a one-time diagnosis next to rule_vs_skeleton.py; run it as the extractor is run (the runtime python, with PYTHONPATH holding the kit's
extractor folder and the engine wheel's site folder). It writes one JSON line for each thing it finds, to stdout, and to --out (`.jsonl`, a zstd stream) too:

- `map differs`: a union query's table (QueryHash, Name) whose map in the scope of a skeleton sample is not the map of its graph table (`graph_tables` of its query record). Once for each table of a task. It has the column
  types of the table; the engine's (assignment, TableHash) pairs as the engine gives them (`engine`: DET QueryHash and value hash cut to 8 hex digits, TableHash cut to 8) and normalized (`engine map`); the row store's pairs of
  the same table (`row store`, from --rows DIR/<task>.jsonl.gz, the file that the graph files were made from); and the graph table's pairs (`graph map`). `same TableHashes` says whether the engine and the row
  store give one set of TableHashes for the table.
- `member without table`: a state (a skeleton sample, or with --draws a state that the extractor would add, points_write.plan_added) has a member that no table of the scope has the QueryHash of: its QueryHash and text, the QueryHashes of the
  scope's tables, and whether it is a union query. Once for each state.
- `no target`: a state (a skeleton sample, or with --draws an added state) for which the rule gives no target: its members, the count of union queries by the part of the rule that decided each, the count of target
  queries through a stand-in and of the choices that no query record can write, and the members' tables that stand for a graph table (the graph table, the member).
--limit N takes the first N lines of each kind for each task. It prints the progress with a rate and an ETA on stderr; a restart skips the tasks that FILE holds a `done` line for."""
import argparse
import collections
import gzip
import json
import sys
import time
from collections import ChainMap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # model/study
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # model/study/samples
import study_zst as Z  # noqa: E402
from points_write import (Reject, draw_files, load_engine, new_run, plan_added, read_draws, scope_maps, scope_of, table_maps,  # noqa: E402
                          target_rule, task_graph, GraphMismatch)
from stand_in import read_index  # noqa: E402
from union_forms import LineIndex  # noqa: E402


def short(x) -> str:
    return x[:8] if isinstance(x, str) else str(x)


def pairs(m, n=6):
    """A map's pairs as (assignment, TableHash) cut for reading: the first n in sorted order, and the count."""
    ps = sorted(m, key=repr)
    return dict(count=len(ps), first=[[[[short(a), short(b)] for a, b in at], short(h)] for at, h in ps[:n]])


def engine_entries(wr, pg):
    """{(QueryHash, Name): [(assignment, TableHash)] as the engine gives them (hex), types} of the scope's tables."""
    out: dict = {}
    types: dict = {}
    for ct in pg.closed:
        for r in wr.AS.assignment_summaries(ct, pg.queries):
            if isinstance(r.table, tuple):
                k = ('%032x' % r.table[0], r.table[1])
                at = tuple(('%032x' % d if d >= 0 else d, '%032x' % v) for d, v in r.at)
                out.setdefault(k, set()).add((at, None if r.hash is None else '%032x' % r.hash))
                types[k] = list(r.types)
    return out, types


def row_store_entries(path: Path):
    """{(function, name): [(assignment, hash)]} of the row store's entries."""
    out: dict = {}
    for line in gzip.open(path, 'rt'):
        r = json.loads(line)
        if r['t'] == 'entry':
            out.setdefault((r['function'], r['name']), set()).add((tuple((d, v) for d, v in r['assignment']), r.get('hash')))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('--skeleton', type=Path, required=True)
    ap.add_argument('--graphs', type=Path, required=True)
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--tasks', required=True)
    ap.add_argument('--draws')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--limit', type=int, default=8)
    ap.add_argument('--plan', default='ordered')
    args = ap.parse_args()
    tasks = args.tasks.split(',')
    done: set[str] = set()
    if args.out is not None and Z.exists(args.out):
        with Z.open_text(args.out) as f:
            done = {rec['done'] for rec in map(json.loads, f) if 'done' in rec}
    out = Z.open_text(args.out, 'a', line_buffering=True) if args.out is not None else None

    def emit(rec: dict) -> None:
        text = json.dumps(rec)
        print(text, flush=True)
        if out is not None:
            out.write(text + '\n')

    split = json.loads(open(args.skeleton / f'{tasks[0]}.jsonl').readline())['set']
    idx = {'prods': LineIndex(args.graphs / f'graph-prods-{split}.jsonl'), 'tables': LineIndex(args.graphs / f'graph-tables-{split}.jsonl')}
    env_base, _, smp = load_engine(args.plan)
    wr = env_base['wr']
    t0 = time.time()
    todo = [t for t in tasks if t not in done]
    for i, task in enumerate(todo, 1):
        records = [json.loads(line) for line in open(args.skeleton / f'{task}.jsonl')]
        union = {r['hash']: r for r in records if r['record'] == 'query'}
        samples = [r for r in records if r['record'] == 'sample']
        try:
            graph = task_graph(idx, task, records[0])
        except GraphMismatch as e:
            emit(dict(task=task, skipped=str(e)))
            continue
        run = new_run(env_base, smp, task)
        templates = read_index(union, graph.reads)
        rows = row_store_entries(args.rows / f'{task}.jsonl.gz')
        n: collections.Counter = collections.Counter()
        seen: set = set()

        def look(sample: dict, queries) -> None:
            state = frozenset(h for h in sample['state']['queries'])
            texts, _ = scope_of(sample['state']['queries'], queries)
            _, pg = run.scope(tuple(texts))
            maps = scope_maps(wr, pg)
            engine, types = engine_entries(wr, pg)
            for q in state:
                if q not in union:
                    continue
                for name, t in union[q]['graph_tables'].items():
                    key = (q, name)
                    if key in seen or key not in maps or graph.maps.get(t) is None or maps[key] == graph.maps[t]:
                        continue
                    seen.add(key)
                    n['map differs'] += 1
                    if n['map differs'] > args.limit:
                        continue
                    eng, row = engine.get(key, set()), rows.get(key, set())
                    emit(dict(task=task, kind='map differs', query=short(q), name=name, query_kind=union[q]['kind'], graph_table=t, types=types.get(key),
                              engine=pairs(eng), row_store=pairs(row), engine_map=pairs(maps[key]), graph_map=pairs(graph.maps[t]),
                              same_TableHashes=sorted({h for _, h in eng}, key=str) == sorted({h for _, h in row}, key=str)))
            tabled = {k[0] for k in maps}
            lacking = [h for h in state if h not in tabled]
            if lacking and n['member without table'] < args.limit:
                n['member without table'] += 1
                emit(dict(task=task, kind='member without table', sample=sample['id'][:8], members=len(state), without=[dict(query=short(h), union=h in union, text=(queries[h]['program'][-1] if h in queries else None)) for h in lacking][:6],
                          scope_table_queries=sorted(short(k[0]) for k in maps)[:40]))
            v = target_rule(state, maps, graph, union, templates)
            if not v.targets and not v.stand_ins and n['no target'] < args.limit:
                n['no target'] += 1
                reasons = collections.Counter(v.why.values())
                stand = [[t, short(k[0]) + '.' + k[1]] for t, m in sorted(graph.maps.items()) if m is not None for k, mm in maps.items() if mm == m]
                emit(dict(task=task, kind='no target', sample=sample['id'][:8], members=len(state), off_path=sum(h not in union for h in state), reasons=dict(reasons), stand_ins=len(v.stand_ins), lost=dict(v.lost),
                          stand_for=stand[:20], skeleton_targets=len(sample.get('target_queries', []))))

        for s in samples[:args.limit * 40]:
            try:
                look(s, union)
            except Exception as e:
                n['samples left out: ' + (str(e) if isinstance(e, Reject) else type(e).__name__)[:50]] += 1
        if args.draws:
            draws = read_draws(draw_files(str(Path(args.draws) / f'{task}.tok.s0.0')))
            have = {frozenset(s['state']['queries']) for s in samples}
            added, extra, _ = plan_added(task, draws, union, have)
            for a in added:
                try:
                    look(a, ChainMap(extra[a['id']], union))
                except Exception as e:
                    n['added states left out: ' + (str(e) if isinstance(e, Reject) else type(e).__name__)[:50]] += 1
            n['added states'] = len(added)
        emit(dict(task=task, done=task, counts=dict(n)))
        el = time.time() - t0
        print(f'{i}/{len(todo)} tasks, ETA {el / i * (len(todo) - i):.0f}s', file=sys.stderr, flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
