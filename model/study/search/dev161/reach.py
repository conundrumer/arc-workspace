"""Reach per depth of the union graph's tables by the jobs of dev_run.py runs, with the arms paired by task.

    reach.py RUN_FOLDER [RUN_FOLDER ...] [--graph FILE] [--rows DIR] [--skip-file JSON] [--arms tree,hand] [--by qh|tables] [--check]

A job reaches a graph table where it drew a query that gives that table. The graph table of a query output is named as
gold/reads/union/gold_union_tables.py names it: "t" and 16 hex digits of a digest of its map {assignment -> TableHash}, with each DET
value written as the TableHash of the DET's table at that value, each DET as the digest of its set of those TableHashes, and each DET of
one value left out. Only "t" tables of --graph count, and none of a kind in --skip-kinds (default DEMONSTRATED, which is out of
scope).

  --by qh      a lower bound: the job's drawn QueryHashes, each named through the task's row store (--rows), so a drawn query reaches the
               graph tables of the row store's query of the same QueryHash. A query of another QueryHash with equal tables is not counted.
  --by tables  the tables that the job's 'new' draws recorded (sampler/draw_record.py, field tables), named from those records alone.

Only the job folders that results.jsonl names count, and each task counts where every arm of --arms has a job and the out-of-scope
list (OUT_OF_SCOPE) does not name it. --skip-file is a JSON file
whose A_tasks and B_tasks list tasks to leave out. Depths are grouped as 0, 1 and 2 and deeper. For each depth it prints the graph tables,
the reached tables per arm, the paired difference (first arm less second) summed over tasks, its mean and standard deviation per task, and
the bound 1.96 times the square root of the sum of squared per-task differences; --per-task adds the tasks whose difference is not 0. With --by tables it also checks the naming from the
draw records: each graph table that a drawn query of a gold QueryHash gives must be named alike from the job's records. --check names the row store's tables both ways and stops
at the first difference from gold_union_tables.tables_of.
"""
import argparse
import collections
import gzip
import hashlib
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import draw_file  # noqa: E402
from study_paths import DATA_ROOT as DATA  # noqa: E402
import study_zst as Z  # noqa: E402  the union files are zstd streams or plain files, whichever is on disk
UNION = Path(os.environ['GOLD_UNION_DIR']) if os.environ.get('GOLD_UNION_DIR') else DATA / 'gold/gold-union-exp46'  # GOLD_UNION_DIR: another union folder
GRAPH = UNION / 'graph-tables-dev.jsonl'
OUT_OF_SCOPE = UNION / 'out-of-scope.jsonl'  # dataset-worker's list of the tasks that are out of scope, one {task, set, reason} a line
ROWS = DATA / 'samples/dev/rows'


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()[:16]


def graph_names(outputs, entries):
    """{(function, name): graph table} for outputs [(function, name)], from entries [(function, name, assignment [[DET, value]], hash)], as
    gold_union_tables.tables_of names them: a table with no TableHash at some assignment is its own graph table."""
    tables_at = {}
    for f, _, asg, h in entries:
        for d, v in asg:
            if d == f:
                tables_at.setdefault((d, v), set()).add(h or 'none')
    table_of = {k: min(v) if len(v) == 1 else digest(sorted(v)) for k, v in tables_at.items()}
    values = {}
    for _, _, asg, _ in entries:
        for d, v in asg:
            values.setdefault(d, set()).add(table_of.get((d, v), v))
    value_set = {d: digest(sorted(v)) for d, v in values.items()}
    one_value = {d for d, v in values.items() if len(v) == 1}
    raw = {}
    for f, n, asg, h in entries:
        a = sorted([value_set[d], table_of.get((d, v), v)] for d, v in asg if d not in one_value)
        raw.setdefault((f, n), []).append([a, h or 'none'])
    def name(f, n):
        m = sorted(raw.get((f, n), []))
        if any(h == 'none' or any(v == 'none' for _, v in a) for a, h in m):
            return 't' + digest(['no TableHash', f, n])
        return 't' + digest(m)
    return {(f, n): name(f, n) for f, n in outputs}


def row_store(rows, task):
    """(outputs, entries) of the task's row store, or None where it has none."""
    p = rows / (task + '.jsonl.gz')
    if not p.exists():
        return None
    outputs, entries = [], []
    for r in map(json.loads, gzip.open(p, 'rt')):
        if r['t'] == 'function' and r.get('union_key') is not None and r['outputs']:
            outputs += [(r['id'], o['name']) for o in r['outputs']]
        elif r['t'] == 'entry':
            entries.append((r['function'], r['name'], [tuple(x) for x in r['assignment']], r.get('hash')))
    return outputs, entries


def job_tables(w):
    """(drawn QueryHashes, outputs, entries) of a job folder's draw records."""
    qhs, outputs, entries = set(), [], []
    for r in draw_file.draws(w):
        if 'steps' not in r:
            continue
        q = r['steps'][-1]['query_hash']
        if q:
            qhs.add(q)
        for o in r.get('tables') or ():
            outputs.append((q, o['name']))
            for row in o['at']:
                entries.append((q, o['name'], list(zip(o['dets'], row[:-1])), row[-1]))
    return qhs, outputs, entries


def check(rows, tasks):
    sys.path.insert(0, str(ROOT / 'gold/reads/union'))
    os.environ.setdefault('ROWS_VERSION', 'engine@site-exp50')
    import gold_union_tables as G
    G.ROWS = str(rows.parent.parent) + '/%s/rows/%s.jsonl.gz'
    for t in tasks:
        T = G.tables_of(rows.parent.name, dict(task=t, tables=[]))
        got = row_store(rows, t)
        if T is None or got is None:
            continue
        mine = graph_names(*got)
        bad = [k for k, v in T.graph.items() if mine.get(k) != v]
        print(t, len(T.graph), 'tables,', len(bad), 'differ', flush=True)
        if bad:
            sys.exit('names differ at %s' % (bad[0],))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', nargs='+')
    ap.add_argument('--graph', default=str(GRAPH))
    ap.add_argument('--rows', default=str(ROWS))
    ap.add_argument('--skip-file')
    ap.add_argument('--arms', default='tree,hand')
    ap.add_argument('--by', choices=('qh', 'tables'), default='qh')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--per-task', action='store_true', help='also print, per depth, the tasks whose paired difference is not 0')
    ap.add_argument('--skip-kinds', default='DEMONSTRATED', help='graph tables of these kinds do not count (out of scope)')
    a = ap.parse_args()
    rows, arms = Path(a.rows), a.arms.split(',')
    skip = {json.loads(l)['task'] for l in open(OUT_OF_SCOPE)} if OUT_OF_SCOPE.exists() else set()
    if a.skip_file:
        d = json.load(open(a.skip_file))
        skip |= set(d.get('A_tasks', [])) | set(d.get('B_tasks', []))
    depth = collections.defaultdict(dict)  # task -> graph table -> depth
    for r in map(json.loads, Z.open_text(a.graph)):
        if r['table'].startswith('t') and r.get('kind') not in a.skip_kinds.split(','):
            depth[r['task']][r['table']] = r['depth']
    jobs = collections.defaultdict(dict)  # task -> arm -> job folder
    for run in map(Path, a.runs):
        for r in map(json.loads, open(run / 'results.jsonl')):
            if r['arm'] in arms and r['task'] not in skip:
                jobs[r['task']][r['arm']] = run / 'jobs' / r.get('job', '%s.%s.s%d.0' % (r['task'], r['arm'], r['seed']))
    tasks = sorted(t for t, by in jobs.items() if all(x in by for x in arms) and t in depth)
    if a.check:
        check(rows, tasks)
    band = lambda d: '0' if d == 0 else '1' if d == 1 else '2+'  # noqa: E731
    tot = collections.Counter()
    reach = collections.defaultdict(collections.Counter)  # (task, arm) -> band -> reached
    agree = collections.Counter()  # the graph tables of the drawn queries of a gold QueryHash, and those of them that the draw records name alike
    for t in tasks:
        g = depth[t]
        for x in g.values():
            tot[band(x)] += 1
        got = row_store(rows, t)
        names = graph_names(*got) if got else {}
        for arm in arms:
            qhs, outputs, entries = job_tables(jobs[t][arm])
            by_qh = {v for (f, _), v in names.items() if f in qhs} & set(g)
            hit = by_qh if a.by == 'qh' else set(graph_names(outputs, entries).values())
            if a.by == 'tables':
                agree['graph tables of drawn gold QueryHashes'] += len(by_qh)
                agree['of them named alike from the draw records'] += len(by_qh & hit)
            for x in hit & set(g):
                reach[t, arm][band(g[x])] += 1
    print('%d tasks paired (%s), by %s%s; graph %s' % (len(tasks), ' less '.join(arms), a.by, ', a lower bound' if a.by == 'qh' else '', a.graph))
    if a.by == 'tables':  # a drawn query of a gold QueryHash gives gold's tables, so the draw records must name each of its graph tables as the row store does
        print('check: %d of %d graph tables of drawn gold QueryHashes are named alike from the draw records' % (
            agree['of them named alike from the draw records'], agree['graph tables of drawn gold QueryHashes']))
    for b in ('0', '1', '2+'):
        d = [reach[t, arms[0]][b] - reach[t, arms[1]][b] for t in tasks]
        n = len(d)
        mean = sum(d) / n if n else 0.0
        sd = math.sqrt(sum((x - mean) ** 2 for x in d) / (n - 1)) if n > 1 else 0.0
        print('depth %-2s  tables %5d  %s %4d  %s %4d  difference %+d (mean %+.2f, sd %.2f per task, bound %.1f)' % (
            b, tot[b], arms[0], sum(reach[t, arms[0]][b] for t in tasks), arms[1], sum(reach[t, arms[1]][b] for t in tasks), sum(d), mean, sd,
            1.96 * math.sqrt(sum(x * x for x in d))))
        if a.per_task:
            print('  ' + ', '.join('%s %+d (%d/%d)' % (t, x, reach[t, arms[0]][b], reach[t, arms[1]][b]) for t, x in sorted(zip(tasks, d), key=lambda p: -abs(p[1])) if x))


if __name__ == '__main__':
    main()
