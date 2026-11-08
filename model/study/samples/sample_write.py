"""Stage 4 of the sample build: joins stage 2's state samples (skeleton) with stage 3's TableVectors and QueryVectors, and writes the samples of the type contract.

  python3 sample_write.py SET [--shard k/N] [--tasks T,T,...] [--out DIR]

For each task with a skeleton file it writes OUTD/SET/samples/<task>.jsonl.gz, to a temp file and then renamed, and skips a task whose file holds the same input shas and code sha. It is not a fit: it writes every task, held-out ones included, and calls no split guard. A task with no row store or no tables file is skipped, and a task whose stages hold two `query_hash_version`s is refused.

Names of the records that stages 3 reads (their writers are frozen or are not this stage's): in the row store, `function` is a query's record (future name: `query`); in the tables file, `entry` is a table at an assignment (future name: `table at an assignment`), `function` is a query vector (future name: `query`), and `given` is a base table (future name: `base`).

What is stated once per file, by key:
- `vec`: a TableVector, keyed by its TableHash (the contract: equal hash, equal vector). Values are null for NaN.
- `query`: a QueryHash's record. It holds these fields of stage 2's `query` line: hash, kind, hash_exact, body, body_decodes, inputs, outputs, graph_tables; and the join: `depth`, `tables` (the BuiltTable of each Name and assignment: name, a (the assignment's id in the `assignments` line), hash (a TableHash and the key of its `vec`), inputs [query or null for a base table, name, assignment id]) sorted by (name, assignment), `capped` (Names past the cap, which are in no table of `tables`), `assignment_vectors` ([name, values] sorted by name, one per Name that has tables: its AssignmentVector, the names in the header), and `query_vector` (values, per_use, column_origin; the names are in the header). A member's BuiltTables and a target query's `computes`, `computes_hashes` and `computes_vectors` are `tables`; a member's QueryVector (`State.query_vectors`) and a target query's `query_vector` are `query_vector`. A query of a state or a target query is a query of its hash, so these are the same in every sample.
- `assignments`: one line, the list of Assignments ([[DET QueryHash, value hash], ...] sorted); a position in it is an assignment id. Id 0 is the empty Assignment.

A line is JSON, in this order:
- `header`: task, split, Provenance (versions, inputs, task_inputs), `names` (TableVector), `assignment_vector_names`, `query_names`, `use_names`, counts.
- `assignments`, then `base_tables` (the BaseTables: name, hash, assignment_vector), then the `vec` lines, then the `query` lines, then the `sample` lines.
- `sample`: id, task, split, eval_only, state {id, queries (the members' hashes), base_names}, target_queries (hashes sorted: the target queries that have a table in stage 3), target_tables ([hash, name] sorted: from the `tables` of the target queries), capped_target_tables, frontier_depth, no_progress_queries, and `unjoined` {members, targets}: the hashes that stage 3 holds no table for. A sample with an unjoined member has an incomplete state; an unjoined target query is in no `target_queries`.
"""
import argparse
import gzip
import hashlib
import json
import math
import os
import sys
import tempfile
import time
import zlib
from collections import Counter
from pathlib import Path

OUTD = Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/samples')
SCHEMA = 'samples-3'
BASE_NAMES = ['input', 'ex_input', 'ex_output']
ASSIGNMENT_COUNT = 0  # the position of `count` in an AssignmentVector (the writer's ASSIGNMENT_HEAD)
type Asg = tuple[tuple[str, str], ...]


def code_sha() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def header_of(path: Path) -> dict | None:
    try:
        with gzip.open(path, 'rt') as f:
            return json.loads(f.readline())
    except (OSError, EOFError, ValueError):
        return None


def num(x: float | None) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x


class Inputs:
    """The three files of one task and what they hold."""

    def __init__(self, sk: Path, rows: Path, tabs: Path):
        self.header: dict = {}
        self.queries: dict[str, dict] = {}  # stage 2: hash -> query line
        self.samples: list[dict] = []
        for line in open(sk):
            r = json.loads(line)
            if r['record'] == 'header':
                self.header = r
            elif r['record'] == 'query':
                self.queries[r['hash']] = r
            else:
                self.samples.append(r)
        self.rows_header: dict = {}
        self.dets: dict[str, list[str]] = {}  # stage 3: query hash -> the DETs in its use closure
        self.outputs: dict[tuple[str, str], dict] = {}
        with gzip.open(rows, 'rt') as f:
            for line in f:
                if line.startswith('{"t": "header"'):
                    self.rows_header = json.loads(line)
                elif line.startswith('{"t": "function"'):  # row store record `function` (future name: `query`)
                    r = json.loads(line)
                    self.dets[r['id']] = sorted(r['dets'])
                    for o in r['outputs']:
                        self.outputs[(r['id'], o['name'])] = o
        self.tab_header: dict = {}
        self.vecs: dict[str, dict] = {}
        self.tables_at: dict[tuple[str, str, Asg], str] = {}  # (query, Name, Assignment) -> TableHash
        self.base: dict[str, str] = {}
        self.query_vecs: dict[str, dict] = {}
        self.assignment_vecs: dict[tuple[str, str], list[float | None]] = {}  # (query, Name) -> its AssignmentVector
        self.base_assignment_vecs: dict[str, list[float | None]] = {}  # BaseName -> its AssignmentVector
        with gzip.open(tabs, 'rt') as f:
            for line in f:
                r = json.loads(line)
                t = r['t']
                if t == 'header':
                    self.tab_header = r
                elif t == 'vec':
                    self.vecs[r['hash']] = r
                elif t == 'entry':  # tables file record `entry` (future name: a table at an assignment), key `function` (future name: `query`)
                    self.tables_at[(r['function'], r['name'], asg_of(r['assignment']))] = r['hash']
                elif t == 'assignment_vector':
                    if 'base' in r:
                        self.base_assignment_vecs[r['base']] = r['values']
                    else:
                        self.assignment_vecs[(r['query'], r['name'])] = r['values']
                elif t == 'given':  # tables file record `given` (future name: `base`)
                    self.base[r['name']] = r['hash']
                elif t == 'function':  # tables file record `function`, a query vector (future name: `query`)
                    self.query_vecs[r['function']] = r
        self.by_query: dict[str, list[tuple[str, Asg, str]]] = {}
        for (qid, name, a), h in self.tables_at.items():
            self.by_query.setdefault(qid, []).append((name, a, h))
        for v in self.by_query.values():
            v.sort()


def asg_of(raw: list[list[str]]) -> Asg:
    return tuple(sorted((d, v) for d, v in raw))


def depths(queries: dict[str, dict]) -> dict[str, int]:
    """The depth of each query over the use edges of the queries: 0 where it uses no query's table, else 1 + the greatest depth of the queries it uses."""
    out: dict[str, int] = {}

    def go(h: str) -> int:
        if h not in out:
            ins = [i['query'] for i in queries[h]['inputs'] if 'query' in i]
            out[h] = 1 + max(go(i) for i in ins) if ins else 0
        return out[h]
    for h in queries:
        go(h)
    return out


def build(task: str, inp: Inputs, st: Counter[str]) -> tuple[list[dict], dict]:
    """The lines of the task's file after the header, and the header's counts."""
    asg_ids: dict[Asg, int] = {(): 0}

    def aid(a: Asg) -> int:
        return asg_ids.setdefault(a, len(asg_ids))

    queries = inp.queries
    depth = depths(queries)
    joined = {h for h in queries if h in inp.by_query and h in inp.query_vecs}
    used_vecs: set[str] = set(inp.base.values())
    qlines: list[dict] = []
    capped: dict[str, list[str]] = {}
    for h in sorted(queries):
        q = queries[h]
        line = {k: q[k] for k in ('hash', 'kind', 'hash_exact', 'body', 'body_decodes', 'inputs', 'outputs', 'graph_tables')}
        line['record'] = 'query'
        line['depth'] = depth[h]
        if h not in joined:
            line['joined'] = False
            qlines.append(line)
            continue
        names = [n for n in q['outputs'] if (h, n) in inp.outputs]
        capped[h] = [n for n in q['outputs'] if n in names and (inp.outputs[(h, n)].get('stopped') or inp.outputs[(h, n)]['seen'] > inp.outputs[(h, n)]['kept'])]
        if set(names) != set(q['outputs']):
            st['queries whose Names stage 3 lacks'] += 1
        tables = []
        for name, a, th in inp.by_query[h]:
            if name not in names:
                st['tables at an assignment of a Name the query does not have'] += 1
                continue
            if name in capped[h]:
                continue
            used_vecs.add(th)
            inputs = []
            for i in q['inputs']:
                if 'query' not in i:
                    inputs.append([None, i['name'], 0])
                    continue
                g = i['query']
                want = tuple(p for p in a if p[0] in set(inp.dets.get(g, [])))
                if (g, i['name'], want) not in inp.tables_at:
                    st['inputs with no table at the restricted assignment'] += 1
                    continue
                inputs.append([g, i['name'], aid(want)])
            inputs.sort(key=lambda x: (x[0] or '', x[1]))
            tables.append(dict(name=name, a=aid(a), hash=th, inputs=inputs))
        line['tables'] = tables
        line['capped'] = capped[h]
        avs = []
        for name in sorted({t['name'] for t in tables}):
            av = inp.assignment_vecs.get((h, name))
            if av is None:
                st['Names with tables and no AssignmentVector'] += 1
                continue
            st['Names whose AssignmentVector count differs from their tables'] += av[ASSIGNMENT_COUNT] != sum(t['name'] == name for t in tables)
            avs.append([name, av])
        line['assignment_vectors'] = avs
        qv = inp.query_vecs[h]
        # in the tables file's per_use and column_origin, a base table is written ('given', name)
        line['query_vector'] = dict(values=qv['values'], per_use=[[[None if t[0] == 'given' else t[0], t[1]], v] for t, v in qv['per_use']],
                                    column_origin=[[n, [[ty, [[None if t[0] == 'given' else t[0], t[1]] for t in ts]] for ty, ts in cols]] for n, cols in qv['column_origin']])
        line['joined'] = True
        qlines.append(line)
        st['joined queries'] += 1
    st['queries'] = len(queries)
    vlines = [dict(record='vec', hash=h, kind=inp.vecs[h]['kind'], values=inp.vecs[h]['values']) for h in sorted(used_vecs)]
    st['counts-only vectors'] += sum(v['kind'] != 'content' for v in vlines)
    by_hash = {q['hash']: q for q in qlines}
    samples = []
    for s in inp.samples:
        members = s['state']['queries']
        tg_ok = [h for h in s['target_queries'] if by_hash[h]['joined'] and by_hash[h]['tables']]
        um = [h for h in members if not by_hash[h]['joined']]
        ut = [h for h in s['target_queries'] if h not in tg_ok]
        tt = sorted({(h, t['name']) for h in tg_ok for t in by_hash[h]['tables']})
        cap = len({(h, n) for h in s['target_queries'] if h in capped for n in capped[h]})
        st['samples'] += 1
        st['samples with every member joined'] += not um
        st['samples with every target query joined'] += not ut
        st['target queries'] += len(tg_ok)
        st['target tables'] += len(tt)
        st['members'] += len(members)
        samples.append(dict(record='sample', id=s['id'], task=task, split=s['split'], eval_only=s['eval_only'],
                            state=dict(id=s['state']['id'], queries=members, base_names=BASE_NAMES), target_queries=tg_ok,
                            target_tables=[list(x) for x in tt], capped_target_tables=cap, frontier_depth=s['frontier_depth'],
                            no_progress_queries=s['no_progress_queries'], unjoined=dict(members=um, targets=ut)))
    asg_line = dict(record='assignments', assignments=[[list(p) for p in a] for a, _ in sorted(asg_ids.items(), key=lambda kv: kv[1])])
    base = dict(record='base_tables', base_tables=[dict(name=n, hash=inp.base[n], assignment_vector=inp.base_assignment_vecs[n]) for n in BASE_NAMES])
    return [asg_line, base, *vlines, *qlines, *samples], {}


def join_counts(inp: Inputs) -> dict[str, int]:
    """Stage 2's members and target queries against stage 3's queries."""
    mem = {h for s in inp.samples for h in s['state']['queries']}
    tgt = {h for s in inp.samples for h in s['target_queries']}
    s3 = set(inp.query_vecs) & set(inp.by_query)
    return {'members without stage 3': len(mem - s3), 'target queries without stage 3': len(tgt - s3),
            'stage 3 queries in no member and no target query': len(s3 - mem - tgt), 'distinct members': len(mem), 'distinct target queries': len(tgt), 'stage 3 queries': len(s3)}


def run_task(sset: str, task: str, base: Path, out: Path, code: str) -> tuple[Counter[str], str] | None:
    """Writes the task's file; returns (its counts, 'done') or None where the file is current. Raises ValueError where the task cannot be joined."""
    sk, rows, tabs = base / 'skeleton' / f'{task}.jsonl', base / 'rows' / f'{task}.jsonl.gz', base / 'tables' / f'{task}.jsonl.gz'
    if not rows.exists() or not tabs.exists():
        raise ValueError('no row store or no tables file')
    inputs = {'skeleton': file_sha(sk), 'rows': file_sha(rows), 'tables': file_sha(tabs)}
    path = out / f'{task}.jsonl.gz'
    old = header_of(path)
    if old and old.get('provenance', {}).get('inputs') == inputs and old.get('provenance', {}).get('versions', {}).get('sample_write') == code and old.get('schema') == SCHEMA:
        return None
    inp = Inputs(sk, rows, tabs)
    vers = {'skeleton': inp.header['query_hash_version'], 'row store': inp.rows_header.get('query_hash_version'), 'tables': inp.tab_header['query_hash_version']}
    if len(set(vers.values())) != 1:
        raise ValueError(f'hash versions differ: {vers}')
    if inp.rows_header.get('hash_version') != inp.tab_header['hash_version']:
        raise ValueError('table hash versions differ')
    if 'assignment_vector_names' not in inp.tab_header or set(BASE_NAMES) - set(inp.base_assignment_vecs):
        raise ValueError('the tables file has no AssignmentVectors: run build_tables')
    st: Counter[str] = Counter()
    lines, _ = build(task, inp, st)
    schemas = inp.tab_header['schema'].split('+')
    prov = dict(versions={'query_hash': vers['skeleton'], 'table_hash': inp.tab_header['hash_version'], 'table_vector': schemas[0], 'query_vector': schemas[1], 'assignment_vector': schemas[2],
                          'canon_text': inp.header['canon_version'], 'skeleton': inp.header['schema'], 'row_store': inp.rows_header.get('version', ''), 'sample_write': code},
                inputs=inputs, task_inputs={task: inputs})
    header = dict(record='header', schema=SCHEMA, set=sset, task=task, split=inp.header['split'], provenance=prov, names=inp.tab_header['names'],
                  assignment_vector_names=inp.tab_header['assignment_vector_names'],
                  query_names=inp.tab_header['function_names'],  # the tables file header's key is `function_names` (future name: `query_names`)
                  use_names=inp.tab_header['use_names'], nan='null',
                  counts=dict(sorted((st + Counter(join_counts(inp))).items())))
    out.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out, prefix=f'{task}.jsonl.gz.')
    with os.fdopen(fd, 'wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=6) as z:
        for rec in [header, *lines]:
            z.write((json.dumps(rec) + '\n').encode())
    os.replace(tmp, path)
    return Counter(header['counts']), 'done'


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('set')
    ap.add_argument('--shard', default='0/1', help='k/N: the tasks with crc32(task) %% N == k')
    ap.add_argument('--tasks', default='')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    k, n = map(int, a.shard.split('/'))
    base = OUTD / a.set
    out = a.out or base / 'samples'
    only = set(filter(None, a.tasks.split(',')))
    tasks = [p.stem for p in sorted((base / 'skeleton').glob('*.jsonl')) if zlib.crc32(p.stem.encode()) % n == k and (not only or p.stem in only)]
    code = code_sha()
    t0, done, skipped, refused = time.time(), 0, 0, 0
    tot: Counter[str] = Counter()
    for i, task in enumerate(tasks, 1):
        t1 = time.time()
        try:
            got = run_task(a.set, task, base, out, code)
        except ValueError as e:
            refused += 1
            print(f'{a.set} {task} {i}/{len(tasks)} refused: {e}', flush=True)
            continue
        if got is None:
            skipped += 1
            continue
        done += 1
        c = got[0]
        for key in ('samples', 'target queries', 'target tables', 'members', 'members without stage 3', 'target queries without stage 3', 'stage 3 queries in no member and no target query',
                    'samples with every target query joined', 'queries whose Names stage 3 lacks', 'tables at an assignment of a Name the query does not have', 'inputs with no table at the restricted assignment'):
            tot[key] += c[key]
        el = time.time() - t0
        print(f'{a.set} {task} {i}/{len(tasks)} samples {c["samples"]} target queries {c["target queries"]} target tables {c["target tables"]} {time.time() - t1:.1f}s '
              f'{done / el * 60:.1f} tasks/min ETA {el / done * (len(tasks) - i):.0f}s', flush=True)
    print(f'{a.set} shard {a.shard}: {done} written, {skipped} current, {refused} refused, {dict(tot)} in {time.time() - t0:.1f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
