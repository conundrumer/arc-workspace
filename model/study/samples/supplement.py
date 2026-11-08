"""Second pass of stage 3: gives the queries of stage 2 that the row store lacks their tables, and adds them to the task's existing row store and tables file.

  python supplement.py SET [--stage rows|tables|both] [--tasks T,T,...] [--shard k/N] [--jobs n] [--retry]

Stage 2 builds a query by replacing each table of a replayed query by the table of a state's member that stands for it, so that
query is in no replayed program. The rows stage replays each such query over its use closure, and appends what it writes to OUTD/SET/rows/<task>.jsonl.gz as one more gzip
member, so the first pass does not run again. Where ARC_SAMPLER_KIT names the `model/study/sampler` of a writer kit release, the replay is
`rows_replay.py --replay` on that release, the path of the first pass. Otherwise it is the union-read kit's worker in map mode (`row_store.RowSink`,
`table_export.read_export`). The tables stage appends the tables at an assignment, vectors, assignment vectors and query vectors of the queries that the row
store holds and the tables file lacks, to OUTD/SET/tables/<task>.jsonl.gz. For each table it passes `native` (whether the table's own Type has an
Example column) to `table_read.table_at` and to `build_tables.dev_features`, as `build_tables.build_task` does, so the appended records equal those of a full rebuild.

Run it with the kit's python, PYTHONPATH holding the engine wheel, and ARCLOG_IDENT_SOURCE=value.

The program of a query is the text that stage 2 hashed (`skeleton.Writer.program`): the lines of its use closure under labels &r0.., then its own
line. Stage 2 writes it into the `program` field of the query's record in the skeleton file (the closure lines, then the query's own line), and
the QueryHashes of the closure lines into `closure`. This pass reads both from the skeleton file; it computes nothing of stage 2 again. A query of
the skeleton file with no `program`, or with a closure query that has none, is counted as not reproduced and as a record with no text: the skeleton
file is older than this pass.

Names of the row store's records (the store's writer is frozen): `function` is a query's record (future name: `query`), `entry` is a table at an
assignment (future name: `table at an assignment`), `rows` is a table's TableRows (future name: `table_rows`), `given` is a base table (future name: `base`).

Lines appended to a row store, after its footer:
  function, entry, table, given   as the first pass writes them, for the queries not yet in the store. A `function` line has union_key null and
                                  supplement true: its key is not a key of the union record
  error                           as the first pass writes them, for the programs of this pass
  supplement                      wanted (QueryHashes), added, added_closure (in the store now, not in the skeleton file), refused {QueryHash:
                                  reason}, not_reproduced, reasons {reason: count}, seconds, code
A query with a `function` line, or in a `supplement` line's `refused`, is skipped; --retry replays the refused ones.

Lines appended to a tables file: vec, entry, assignment_vector (one per parameterized table of the added queries) and function as build_tables writes them,
then `supplement` with counts.
"""
import argparse
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

KIT_UNION_READ = Path('/Users/davidlu/code/arc-workspace/work/synth-kaggle/kit-union-read')
DEFAULT_SITE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/site-exp19'
# The worker replays the programs on the engine wheel that PYTHONPATH names (its folder starts with `site-`), so the rows it adds are those of the stage 2 hashes.
ENGINE_SITE = next((p for p in os.environ.get('PYTHONPATH', '').split(os.pathsep) if Path(p).name.startswith('site-')), DEFAULT_SITE)
TASK_DIR = Path('/Users/davidlu/code/arc-workspace/data/tasks')
# The row store's record types and key names, as its frozen writer spells them: `function` (future name: `query`), `id`, `table`, `entry`, `error`.
HASH_LINE = re.compile(r'^\{"t": "(function|table|error)", "(?:id|hash|function)": "([0-9a-f]{32})"')
ENTRY_LINE = re.compile(r'^\{"t": "(?:entry|error)", "function": "([0-9a-f]{32})"')
SKELETON_RECORD = 'query'


def code_sha() -> str:
    import hashlib
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]


# ---------------------------------------------------------------------- files

def append_member(path: Path, lines: list[str]) -> None:
    """Appends `lines` to the gzip file at `path` as one more gzip member, to a temp file and then a rename, so a failure leaves the file as it was."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.')
    with os.fdopen(fd, 'wb') as out:
        with open(path, 'rb') as src:
            shutil.copyfileobj(src, out, 1 << 20)
        z = zlib.compressobj(6, zlib.DEFLATED, 31)
        for line in lines:
            out.write(z.compress(line.encode()))
        out.write(z.flush())
    os.replace(tmp, path)


@dataclass
class Present:
    """What a row store holds, from the first characters of its lines: no row is decoded."""
    queries: set[str] = field(default_factory=set)  # QueryHashes with a `function` line
    tables: set[str] = field(default_factory=set)  # TableHashes with a `table` line
    refused: dict[str, str] = field(default_factory=dict)  # QueryHash -> reason, from earlier `supplement` lines


def scan_rows(path: Path) -> Present:
    got = Present()
    with gzip.open(path, 'rt') as f:
        for line in f:
            m = HASH_LINE.match(line)
            if m:
                if m[1] == 'function':  # row store record `function` (future name: `query`)
                    got.queries.add(m[2])
                elif m[1] == 'table':
                    got.tables.add(m[2])
            elif line.startswith('{"t": "supplement"'):
                got.refused.update(json.loads(line).get('refused', {}))
    return got


def read_skeleton(path: Path) -> dict[str, dict]:
    """The skeleton file's query records by QueryHash."""
    out = {}
    with open(path) as f:
        for line in f:
            if line.startswith('{"record": "' + SKELETON_RECORD + '"'):
                r = json.loads(line)
                out[r['hash']] = r
    return out


def reason_of(message: str) -> str:
    """A refusal's message without the numbers, labels and hashes that differ between queries."""
    s = re.sub(r'[0-9a-f]{32}', '<hash>', message)
    s = re.sub(r'&r\d+', '&r#', s)
    s = re.sub(r'\d+', '#', s)
    return ' '.join(s.split())[:110]


# ---------------------------------------------------------------------- the programs of stage 2

@dataclass
class Program:
    query_hash: str
    kind: str
    scope: list[str]  # the lines of the use closure, in dependency order
    scope_hashes: list[str]
    text: str
    reads: list[str]  # QueryHashes of the queries whose tables it uses


def programs_of(records: dict[str, dict]) -> tuple[dict[str, Program], int]:
    """(the programs that the skeleton file's records give, the count of records with no text). A record has no text where it has no `program`, or where a query of its closure has none."""
    programs: dict[str, Program] = {}
    for h, r in records.items():
        text = r.get('program')
        closure = r.get('closure')
        if not text or closure is None:
            continue
        assert len(text) == len(closure) + 1, h
        programs[h] = Program(h, r['kind'], text[:-1], closure, text[-1], sorted({i['query'] for i in r['inputs'] if 'query' in i}))
    complete = {h: p for h, p in programs.items() if all(d in programs for d in p.scope_hashes)}
    return complete, len(records) - len(complete)


def union_record(task: str, sset: str, split: str, src: str, wanted: list[str], programs: dict[str, Program]) -> dict:
    """A record in the layout of the kit's union gold, with one program for each wanted query. The worker's map mode replays it and the row sink
    writes the tables. A key is the position of a query in this record."""
    keys: dict[str, int] = {}
    rows: list[dict] = []

    def key_of(h: str) -> int:
        if h not in keys:
            p = programs[h]
            for d in p.scope_hashes:
                key_of(d)
            keys[h] = len(rows)
            rows.append(dict(key=keys[h], kind=p.kind, depth=0, reads=[keys[d] for d in p.reads], pinned=False, cases=[h], form=p.text))
        return keys[h]
    progs = []
    for h in wanted:
        p = programs[h]
        progs.append(dict(cases=[h], sexp='\n'.join([*p.scope, p.text]), form_keys=[key_of(d) for d in [*p.scope_hashes, h]]))
    return dict(task=task, set=sset, split=split, src=src, programs=progs, tables=rows)


# ---------------------------------------------------------------------- the rows stage

def release_of_kit() -> Path | None:
    """The writer kit release whose `model/study/sampler` ARC_SAMPLER_KIT names, or None."""
    kit = os.environ.get('ARC_SAMPLER_KIT')
    if not kit:
        return None
    release = Path(kit).resolve().parents[2]
    return release if (release / 'manifest.json').exists() else None


def replay_release(rec: dict, tmp: str, out: str, release: Path) -> dict:
    """Replays the union record rec with `rows_replay.py --replay` on the release, into the row store out; the counts, or error."""
    import rows_replay as RR
    t = rec['task']
    rec_path, log = f'{tmp}/{t}.record.json', f'{tmp}/{t}.log'
    Path(rec_path).write_text(json.dumps(rec))
    with open(log, 'w') as f:
        p = subprocess.run([sys.executable, '-u', RR.__file__, '--replay', '--record', rec_path, '--task-file', str(TASK_DIR / f'{t}.json'), '--out', out,
                            '--src', str(rec['src']), '--split', rec['split'], '--release', str(release), '--site', ENGINE_SITE,
                            '--rss-mib', str(RR.RSS_MIB), '--deadline', str(RR.DEADLINE_SECONDS), '--table-work-cap', str(RR.TABLE_WORK_CAP), '--session-share', str(RR.SESSION_SHARE)],
                           stdout=f, stderr=subprocess.STDOUT, env=dict(os.environ, **RR.CHILD_ENV))
    text = Path(log).read_text(errors='replace')
    done = [line for line in text.splitlines() if line.startswith('rows_replay: {')]
    if p.returncode or not done or not os.path.exists(out):
        return dict(task=t, error=f'exit {p.returncode}: {text[-400:]}')
    return dict(task=t, counts=json.loads(done[-1][len('rows_replay: '):]))


def merge_rows(rows_path: Path, new_path: Path, present: Present, wanted: list[str], stats: dict[str, Any], seconds: float) -> dict:
    """Appends to the row store what the worker wrote for queries the store lacks, and a `supplement` line."""
    keep_queries: set[str] = set()
    query_lines: list[str] = []
    errors: list[dict] = []
    raw: list[str] = []
    with gzip.open(new_path, 'rt') as f:
        for line in f:
            m = HASH_LINE.match(line)
            if line.startswith('{"t": "function"') and m:  # row store record `function` (future name: `query`)
                if m[2] not in present.queries and m[2] not in keep_queries:
                    keep_queries.add(m[2])
                    r = json.loads(line)
                    r.update(union_key=None, supplement=True)
                    query_lines.append(json.dumps(r) + '\n')
            elif line.startswith('{"t": "error"'):
                errors.append(json.loads(line))
                raw.append(line)
    tables_taken: set[str] = set()
    body: list[str] = []
    with gzip.open(new_path, 'rt') as f:
        for line in f:
            m = HASH_LINE.match(line)
            if m and m[1] == 'table':
                if m[2] not in present.tables and m[2] not in tables_taken:
                    tables_taken.add(m[2])
                    body.append(line)
            elif line.startswith('{"t": "entry"'):  # row store record `entry` (future name: a table at an assignment)
                e = ENTRY_LINE.match(line)
                if e and e[1] in keep_queries:
                    body.append(line)
    why: dict[str, str] = {}
    for e in errors:
        key = e.get('function') or e.get('case')  # row store `error` record, key `function` (future name: `query`)
        if key and key not in why:
            why[key] = reason_of(e['error'])
    refused = {h: why.get(h, 'no record: the program was not replayed or its QueryHash differs') for h in wanted if h not in keep_queries}
    reasons = Counter(refused.values())
    info = dict(t='supplement', wanted=wanted, added=sorted(h for h in keep_queries if h in set(wanted)), added_closure=sorted(h for h in keep_queries if h not in set(wanted)),
                refused=refused, not_reproduced=stats['not_reproduced'], reasons=dict(reasons), seconds=round(seconds, 1), code=code_sha(),
                ident_source=os.environ.get('ARCLOG_IDENT_SOURCE'))
    append_member(rows_path, [*query_lines, *body, *raw, json.dumps(info) + '\n'])
    return info


def rows_task(sset: str, task: str, base: Path, retry: bool, totals: Counter[str]) -> tuple[Path, dict, list[str], Present] | None:
    """Prepares the worker run of a task: (row store, the union record, wanted, present); None where nothing is missing. Adds the task's count of skeleton records with no program text to `totals`."""
    rows_path, sk_path = base / 'rows' / f'{task}.jsonl.gz', base / 'skeleton' / f'{task}.jsonl'
    present = scan_rows(rows_path)
    records = read_skeleton(sk_path)
    programs, no_text = programs_of(records)
    totals['records with no program text'] += no_text
    missing = set(records) - present.queries - (set() if retry else set(present.refused))
    if not missing:
        return None
    wanted = sorted(h for h in missing if h in programs)
    header = json.loads(gzip.open(rows_path, 'rt').readline())
    rec = union_record(task, sset, header.get('split') or 'dev', str(header.get('src')), wanted, programs)
    rec['not_reproduced'] = sorted(missing - set(wanted))
    return rows_path, rec, wanted, present


def run_rows(sset: str, tasks: list[str], base: Path, jobs: int, retry: bool) -> None:
    release = release_of_kit()
    sys.path.insert(0, str(KIT_UNION_READ))
    import build_map  # pyright: ignore[reportMissingImports]
    build_map.SITE = ENGINE_SITE
    t0, finished, totals = time.time(), 0, Counter()
    prepared = []
    for task in tasks:
        got = rows_task(sset, task, base, retry, totals)
        if got is None:
            totals['current'] += 1
        else:
            prepared.append((task, got))
    print(f'{sset} rows: {len(tasks)} tasks, {totals["current"]} current, {len(prepared)} to run, {totals["records with no program text"]} skeleton records with no program text', flush=True)
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(jobs) as pool:
        def work(task: str, rec: dict) -> tuple[dict, str, float]:
            out = f'{tmp}/{task}.new.jsonl.gz'
            t1 = time.time()
            m = replay_release(rec, tmp, out, release) if release else build_map.one(rec, tmp, out)
            return m, out, time.time() - t1
        futures = {}
        for task, (rows_path, rec, wanted, present) in prepared:
            if wanted:
                futures[pool.submit(work, task, rec)] = task
        by_task = dict(prepared)
        for task, (rows_path, rec, wanted, present) in prepared:
            if not wanted:  # every missing query is one with no program text
                merge_none(rows_path, rec)
                totals['not_reproduced'] += len(rec['not_reproduced'])
        for fut in as_completed(futures):
            task = futures[fut]
            rows_path, rec, wanted, present = by_task[task]
            m, out, secs = fut.result()
            finished += 1
            if 'error' in m:
                print(f'{sset} {task} FAILED {m["error"]}', flush=True)
                totals['failed'] += 1
                continue
            info = merge_rows(rows_path, Path(out), present, wanted, rec, secs)
            totals['wanted'] += len(wanted)
            totals['added'] += len(info['added'])
            totals['added_closure'] += len(info['added_closure'])
            totals['refused'] += len(info['refused'])
            totals['not_reproduced'] += len(rec['not_reproduced'])
            for r, n in info['reasons'].items():
                totals['reason: ' + r] += n
            el = time.time() - t0
            print(f'{sset} {task} {finished}/{len(futures)}: wanted {len(wanted)}, added {len(info["added"])} (+{len(info["added_closure"])} closure), refused {len(info["refused"])}, '
                  f'not reproduced {len(rec["not_reproduced"])}, {secs:.1f} s, {60 * finished / el:.1f} tasks/min, ETA {el / finished * (len(futures) - finished):.0f} s', flush=True)
    print(f'{sset} rows done in {time.time() - t0:.0f} s: {dict(totals)}', flush=True)


def merge_none(rows_path: Path, rec: dict) -> dict:
    """Records a task whose missing queries have no program text."""
    info = dict(t='supplement', wanted=[], added=[], added_closure=[], refused={}, not_reproduced=rec['not_reproduced'], reasons={}, seconds=0.0, code=code_sha(),
                ident_source=os.environ.get('ARCLOG_IDENT_SOURCE'))
    append_member(rows_path, [json.dumps(info) + '\n'])
    return info


# ---------------------------------------------------------------------- the tables stage

def tables_task(task: str, rows_path: Path, tabs_path: Path) -> dict | None:
    """Appends to the tables file the queries that the row store holds and the file lacks. None where there is none, or where the file is
    missing or older than the store (build_tables writes it whole then)."""
    import build_tables as BT
    import function_vec as FV
    import row_store as RS
    import table_hash as TH  # noqa: F401
    import table_read as TR
    import table_vec as TV
    if not tabs_path.exists():
        return None
    h, mine = RS.header_of(str(rows_path)) or {}, RS.header_of(str(tabs_path)) or {}
    if not (mine.get('src') == h.get('src') and mine.get('rows_code') == h.get('code') and mine.get('code') == BT.code_sha() and BT.current_versions(mine, h)):
        return None
    have_vecs: set[str] = set()
    have_queries: set[str] = set()
    with gzip.open(tabs_path, 'rt') as f:
        for line in f:
            if line.startswith('{"t": "vec"'):
                have_vecs.add(json.loads(line)['hash'])
            elif line.startswith('{"t": "function"'):  # tables file record `function`, a query vector (future name: `query`)
                have_queries.add(json.loads(line)['function'])
    store = RS.read_store(str(rows_path))
    new = [qid for qid, q in store.functions.items() if qid not in have_queries and any('error' not in o for o in q['outputs'])]  # store.functions: the `function` records (future name: `queries`)
    if not new:
        return None
    n_train, n_test = store.header['n_train'], store.header['n_test']
    ctx = TR.TaskCtx(json.loads((TASK_DIR / f'{task}.json').read_text()))
    pairs = TV.pairs_of(ctx)
    outfeat, _ = TV.kit()
    lines: list[str] = []
    cache: dict[Any, TR.TableAt] = {}
    new_vecs = 0
    compared = Counter()

    def table_at(t: RS.StoredTable) -> TR.TableAt:
        nonlocal new_vecs
        tab = cache.get(BT.table_key(t))
        if tab is None:
            tab = cache[BT.table_key(t)] = TR.table_at(t, n_train, n_test, BT.native_example(store, t))
            if t.hash is not None and t.hash not in have_vecs:  # a table with no TableHash has no `vec` record (build_tables.py)
                have_vecs.add(t.hash)
                v = TV.table_vec(tab, ctx)
                lines.append(json.dumps(dict(t='vec', hash=t.hash, kind='counts_only' if t.counts_only else 'content', values=BT.clean(v))) + '\n')
                new_vecs += 1
                if t.engine_features and not t.counts_only:
                    compared['compared'] += 1
                    compared['python_differs'] += BT.differs(t.engine_features[:len(TV.ENGINE_NAMES)], [v[TV.NAMES.index(n)] for n in TV.ENGINE_NAMES])
                    stopped = any(o.get('stopped') for o in store.functions.get(t.function, {}).get('outputs', []) if o['o'] == t.o)  # t.function: the table's query (future name: `query`)
                    dev = BT.dev_features(t, ctx, n_train, stopped, BT.native_example(store, t))
                    if dev is None:
                        compared['dev_missing'] += 1
                    else:
                        compared['dev_differs'] += BT.differs(t.engine_features, dev)
        return tab
    by_table: dict[FV.Ref, dict[RS.AssignKey, TR.TableAt]] = {}
    wanted = set(new)
    entries = 0
    for t in store.tables:  # StoredTable.function is the table's query (future name: `query`)
        tab = table_at(t)
        by_table.setdefault((t.function, t.name), {})[t.assignment] = tab
        if t.function in wanted:
            lines.append(json.dumps(dict(t='entry', function=t.function, name=t.name, assignment=[list(p) for p in t.assignment], hash=t.hash)) + '\n')  # tables file record `entry` (future name: a table at an assignment), key `function` (future name: `query`)
            entries += 1
    for t in store.given:  # the base tables
        by_table.setdefault(('given', t.function), {})[()] = table_at(t)  # function_vec's Ref for a base table is ('given', name)
    assignment_vectors = BT.assignment_vector_records(store, wanted)
    lines.extend(json.dumps(r) + '\n' for r in assignment_vectors)
    dets = {qid: set(q['dets']) for qid, q in store.functions.items()}
    for qid in new:
        r = FV.function_vec(store.functions[qid], by_table, dets, ctx, pairs, outfeat)
        lines.append(json.dumps(dict(t='function', **{**r, 'values': BT.clean(r['values']), 'per_use': [[u, BT.clean(x)] for u, x in r['per_use']]})) + '\n')  # tables file record `function` (future name: `query`)
    info = dict(queries=len(new), entries=entries, vectors=new_vecs, assignment_vectors=len(assignment_vectors), **compared)
    lines.append(json.dumps(dict(t='supplement', **info, code=code_sha())) + '\n')
    append_member(tabs_path, lines)
    return info


def run_tables(sset: str, tasks: list[str], base: Path) -> None:
    t0, done, totals = time.time(), 0, Counter()
    for i, task in enumerate(tasks, 1):
        t1 = time.time()
        info = tables_task(task, base / 'rows' / f'{task}.jsonl.gz', base / 'tables' / f'{task}.jsonl.gz')
        if info is None:
            totals['current or not built'] += 1
            continue
        done += 1
        totals['queries'] += info['queries']
        totals['entries'] += info['entries']
        totals['vectors'] += info['vectors']
        el = time.time() - t0
        print(f'{sset} {task} {i}/{len(tasks)}: {info["queries"]} queries, {info["entries"]} tables at an assignment, {info["vectors"]} vectors, {time.time() - t1:.1f} s, '
              f'{60 * done / el:.1f} tasks/min, ETA {el / done * (len(tasks) - i):.0f} s', flush=True)
    print(f'{sset} tables done in {time.time() - t0:.0f} s: {dict(totals)}', flush=True)


# ---------------------------------------------------------------------- the command

def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('set')
    ap.add_argument('--stage', choices=('rows', 'tables', 'both'), default='both')
    ap.add_argument('--tasks', default='')
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--retry', action='store_true', help='replay the queries that an earlier run refused')
    a = ap.parse_args()
    from split import OUTD
    k, n = map(int, a.shard.split('/'))
    base = Path(OUTD) / a.set
    only = set(filter(None, a.tasks.split(',')))
    tasks = [p.name.removesuffix('.jsonl.gz') for p in sorted((base / 'rows').glob('*.jsonl.gz'))]
    tasks = [t for t in tasks if zlib.crc32(t.encode()) % n == k and (not only or t in only) and (base / 'skeleton' / f'{t}.jsonl').exists()]
    if a.stage in ('rows', 'both'):
        run_rows(a.set, tasks, base, a.jobs, a.retry)
    if a.stage in ('tables', 'both'):
        run_tables(a.set, tasks, base)
    return 0


if __name__ == '__main__':
    sys.exit(main())
