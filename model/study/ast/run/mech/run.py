#!/usr/bin/env python3
"""Stream retained and recovered corpus pairs into the durable mech-v1 store."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import concurrent.futures
import fcntl
import gzip
import hashlib
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import queue
import re
import signal
import sqlite3
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
SCHEMA = 'mech-pair-v1'
SEMANTICS = 'mechanical-labels-v2'
DEPENDENCIES = ('native_storage.py', 'filters.py', 'native_tables.py', 'recovery.py',
                'next_revision/family_recovery.py')


def published_task(path):
    """The corpus publishes eight-hex task directories by atomic rename.

    pathlib glob includes hidden staging paths such as .a57f2f04.tmp; these
    contain open gzip writers and are never source records of this pass.
    """
    return re.fullmatch(r'[0-9a-f]{8}', path.name) is not None and path.is_dir()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def code_manifest(study_run, algorithm_path=None):
    paths = {'mech/algorithm.py': HERE / 'algorithm.py', '../../study_paths.py': CODE_ROOT / 'study_paths.py'}
    if algorithm_path is not None and Path(algorithm_path).resolve() != (HERE / 'algorithm.py'):
        paths['mech/labeler-entrypoint.py'] = Path(algorithm_path).resolve()
    paths.update({name: Path(study_run) / name for name in DEPENDENCIES})
    files = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    return dict(semantics=SEMANTICS, files=files)


def pair_key(rec):
    return {k: rec[k] for k in ('task', 'case', 'point', 'clause', 'K', 'operation')} | {
        'edits': rec['identity']['edits']}


class Reads:
    """Read-only connections that one reader opens once and reuses for every call.

    A loader given none uses ONE_SHOT: it opens its own connection and closes it.
    """

    def __init__(self, keep=True):
        self.keep = keep
        self.databases = {}

    def open(self, path, **options):
        path = Path(path).resolve()
        db = self.databases.get(path)
        if db is None:
            db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, **options)
            if self.keep:
                db.execute('PRAGMA cache_size=-32768')
                self.databases[path] = db
        return db

    def done(self, db):
        if not self.keep:
            db.close()
        elif db.in_transaction:
            db.rollback()

    def close(self):
        for db in self.databases.values():
            db.close()
        self.databases.clear()


ONE_SHOT = Reads(keep=False)


def connect(path):
    db = sqlite3.connect(path, timeout=120)
    db.execute('PRAGMA busy_timeout=120000')
    db.execute('PRAGMA synchronous=FULL')
    return db


def setup(path):
    db = connect(path)
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pairs (
            pair_id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL,
            code_sha256 TEXT NOT NULL, config_sha256 TEXT NOT NULL,
            result_sha256 TEXT NOT NULL, record_json TEXT NOT NULL);
    ''')
    existing = db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
    if existing and existing[0] != SCHEMA:
        raise ValueError('output schema mismatch')
    db.execute("INSERT OR IGNORE INTO metadata VALUES ('schema', ?)", (SCHEMA,))
    db.commit(); db.close()


def initialize(study_run, manifest, output, config, relabel, events, stopping, algorithm_path=None):
    global ALGORITHM, DB, CONFIG, MANIFEST, CODE_HASH, CONFIG_HASH, RELABEL, EVENTS, RUNNER_HASH, STOPPING
    # Never let a speed edit silently change a running process's receipts.
    if code_manifest(study_run, algorithm_path) != manifest:
        raise ValueError('labeling code changed before worker import; restart')
    os.environ['STUDY_RUN'] = study_run
    sys.dont_write_bytecode = True
    if algorithm_path is None or Path(algorithm_path).resolve() == HERE / 'algorithm.py':
        import algorithm
    else:
        spec = importlib.util.spec_from_file_location('mech_labeler_entrypoint', algorithm_path)
        algorithm = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = algorithm; spec.loader.exec_module(algorithm)
    if code_manifest(study_run, algorithm_path) != manifest:
        raise ValueError('labeling code changed during worker import; restart')
    ALGORITHM = algorithm; DB = connect(output); CONFIG = config; MANIFEST = manifest
    CODE_HASH = digest(manifest); CONFIG_HASH = digest(config); RELABEL = relabel
    EVENTS = events
    STOPPING = stopping
    RUNNER_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def records(base, sources, *, include_filtered=False):
    for source in sources:
        filename = 'pairs.jsonl.gz' if source == 'kept' else 'recoverable.jsonl.gz'
        path = base / filename
        if not path.exists():
            continue
        with gzip.open(path, 'rt') as stream:
            lineno = 0
            try:
                for lineno, line in enumerate(stream, 1):
                    if globals().get('STOPPING') is not None and STOPPING.is_set():
                        return
                    rec = json.loads(line)
                    if source == 'kept' and not include_filtered and rec.get('retained') is not True:
                        continue
                    yield source, filename, lineno, rec
            except (EOFError, OSError, ValueError) as exc:
                raise ValueError(f'{path}: source read near line {lineno}: {type(exc).__name__}: {exc}') from exc


def valid(row, source_hash):
    """A stored row resumes when it is the intact, error-free result for this source record.

    Producer code and configuration hashes are provenance; no code change
    invalidates a row. `--relabel` recomputes every row.
    """
    if row is None:
        return False
    old_source, result_hash, payload = row
    if old_source != source_hash:
        return False
    try:
        rec = json.loads(payload)
        return (digest(rec) == result_hash and rec['schema'] == SCHEMA
                and not rec.get('error') and rec['source_sha256'] == source_hash)
    except (ValueError, KeyError, TypeError):
        return False


def task_job(job):
    base, sources, limit = job; base = Path(base)
    seen = {}; processed = 0
    for source, filename, lineno, rec in records(base, sources):
        if STOPPING.is_set():
            return dict(task=base.name, processed=processed, stopped=True)
        key = pair_key(rec); pair_id = digest(key); source_hash = digest(rec)
        if pair_id in seen:
            if seen[pair_id] != source_hash:
                raise ValueError(f'{base.name}: conflicting source records for {pair_id}')
            continue
        seen[pair_id] = source_hash
        if rec['task'] != base.name:
            raise ValueError(f'task identity differs from directory: {base}')
        row = DB.execute('SELECT source_sha256, result_sha256, record_json '
                         'FROM pairs WHERE pair_id=?', (pair_id,)).fetchone()
        if not RELABEL and valid(row, source_hash):
            EVENTS.put(('skip', 1))
        else:
            result = ALGORITHM.one_pair(rec, str(base), CONFIG['seconds'], CONFIG['baseline_seconds'])
            result.update(key)
            result.update(schema=SCHEMA, pair_id=pair_id, source_sha256=source_hash,
                          pool_pair_id=hashlib.sha256(json.dumps(rec['identity'], ensure_ascii=False,
                                                                separators=(',', ':')).encode()).hexdigest(),
                          code_sha256=CODE_HASH, code_manifest=MANIFEST, config=CONFIG,
                          config_sha256=CONFIG_HASH, runner_sha256=RUNNER_HASH,
                          source=dict(corpus=str(base.parent), stream=source, file=filename, line=lineno),
                          kind=rec['kind'], old=rec.get('code_label'), reasons=rec['rejection_reasons'],
                          retained=rec.get('retained'), completed_at=time.time(), reused_from=None)
            # Errors are durable diagnostics, retried on the next start. Bounded
            # unknown is a valid completed search outcome and is resumed normally.
            payload = canonical(result)
            with DB:
                DB.execute('INSERT OR REPLACE INTO pairs VALUES (?,?,?,?,?,?)',
                           (pair_id, source_hash, CODE_HASH, CONFIG_HASH, digest(result), payload))
            EVENTS.put(('error' if result.get('error') else 'write', 1))
        processed += 1
        if limit and processed >= limit:
            break
    return dict(task=base.name, processed=processed, stopped=STOPPING.is_set())


def task_total(base, sources, limit):
    # Completed producer summaries avoid decompressing every enormous pairs file
    # solely to count retained rows. Verify each task's observed total afterwards.
    total = 0
    for source in sources:
        filename = 'pairs.jsonl.gz' if source == 'kept' else 'recoverable.jsonl.gz'
        path = base / filename
        if not path.exists():
            continue
        if source == 'kept':
            summary_path = base / 'summary.json'
            summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
            count = summary.get('counts', {}).get('totals', {}).get('retained')
            if summary.get('completed') and type(count) is int:
                total += count
                continue
        count = 0
        with gzip.open(path, 'rt') as stream:
            lineno = 0
            try:
                for lineno, line in enumerate(stream, 1):
                    if source == 'recovered' or json.loads(line).get('retained') is True:
                        count += 1
                        if limit and count >= limit:
                            break
            except (EOFError, OSError, ValueError) as exc:
                raise ValueError(f'{path}: inventory read near line {lineno}: {type(exc).__name__}: {exc}') from exc
        total += count
    return min(total, limit) if limit else total


def progress(start, done, total, counts, phase):
    elapsed = time.monotonic() - start; rate = done / max(elapsed, .001)
    eta = (total - done) / rate if rate else None
    print(f'{phase} done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.3f}/s '
          f'ETA={eta:.1f}s' if eta is not None else
          f'{phase} done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.3f}/s ETA=unknown',
          ' '.join(f'{k}={v}' for k, v in sorted(counts.items())), file=sys.stderr, flush=True)


def parse():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('corpus', type=Path); ap.add_argument('output', type=Path)
    ap.add_argument('--study-run', type=Path, default=HERE.parent)
    ap.add_argument('--sources', nargs='+', choices=('kept', 'recovered'), default=['kept', 'recovered'])
    ap.add_argument('--tasks', nargs='+')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--seconds', type=float, default=1.0)
    ap.add_argument('--baseline-seconds', type=float, default=.5)
    ap.add_argument('--limit-per-task', type=int, default=0)
    ap.add_argument('--compatibility', type=Path,
                    help='ignored; accepted for command compatibility (stored rows resume regardless of code hash)')
    ap.add_argument('--relabel', action='store_true',
                    help='recompute every pair even where a valid stored row exists; use after a change '
                         'that alters what a label means')
    ap.add_argument('--algorithm', type=Path, default=HERE / 'algorithm.py',
                    help='owned labeling entrypoint; included in code_manifest')
    a = ap.parse_args()
    if a.workers < 1 or a.seconds <= 0 or a.baseline_seconds <= 0 or a.limit_per_task < 0:
        ap.error('workers and seconds must be positive; limit must be nonnegative')
    a.sources = list(dict.fromkeys(a.sources))
    return a


def main():
    a = parse(); a.output = a.output.resolve(); a.corpus = a.corpus.resolve()
    a.study_run = a.study_run.resolve(); a.output.parent.mkdir(parents=True, exist_ok=True)
    lock = open(str(a.output) + '.lock', 'a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('another runner owns this output; stop it before takeover')
    a.algorithm = a.algorithm.resolve()
    manifest = code_manifest(a.study_run, a.algorithm); code_hash = digest(manifest)
    config = dict(seconds=a.seconds, baseline_seconds=a.baseline_seconds, semantics=SEMANTICS)
    setup(str(a.output))
    tasks = a.tasks or sorted({p.parent.name for source in a.sources
                             for p in a.corpus.glob('*/' + ('pairs.jsonl.gz' if source == 'kept' else 'recoverable.jsonl.gz'))
                             if published_task(p.parent)})
    for task in tasks:
        if not published_task(a.corpus / task):
            raise ValueError(f'not a published eight-hex task directory: {a.corpus / task}')
    # Smallest tasks first; no file-size exclusion (including the four >300 MB).
    tasks.sort(key=lambda t: sum(p.stat().st_size for p in (a.corpus / t).glob('*.jsonl.gz')))
    start = time.monotonic(); counts = {}; totals = {}; last_print = 0
    print(f'schema={SCHEMA} code_sha256={code_hash} config_sha256={digest(config)} output={a.output}', file=sys.stderr, flush=True)
    inventory_stop = threading.Event()
    inventory_state = {'total': 0, 'tasks': 0}
    def inventory_heartbeat():
        while not inventory_stop.wait(5):
            progress(start, inventory_state['tasks'], len(tasks),
                     {'selected_pairs_so_far': inventory_state['total']}, 'inventory-tasks')
    heartbeat = threading.Thread(target=inventory_heartbeat, daemon=True)
    heartbeat.start()
    try:
        for task in tasks:
            totals[task] = task_total(a.corpus / task, a.sources, a.limit_per_task)
            inventory_state.update(total=sum(totals.values()), tasks=len(totals))
    finally:
        inventory_stop.set(); heartbeat.join()
    total = sum(totals.values()); done = 0
    ctx = multiprocessing.get_context('spawn'); events = ctx.Queue(); stopping = ctx.Event()
    interrupted = False
    def stop(signum, frame):
        nonlocal interrupted
        interrupted = True
        stopping.set()
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    pool = concurrent.futures.ProcessPoolExecutor(max_workers=a.workers, mp_context=ctx,
              initializer=initialize, initargs=(str(a.study_run), manifest, str(a.output), config, a.relabel, events, stopping, str(a.algorithm)))
    pending = {}; task_iter = iter(tasks); failed = []
    def fill():
        while not interrupted and len(pending) < a.workers:
            task = next(task_iter, None)
            if task is None: break
            pending[pool.submit(task_job, (str(a.corpus / task), a.sources, a.limit_per_task))] = task
    fill()
    try:
        while pending:
            try:
                kind, count = events.get(timeout=1)
                counts[kind] = counts.get(kind, 0) + count; done += count
                while True:
                    kind, count = events.get_nowait()
                    counts[kind] = counts.get(kind, 0) + count; done += count
            except queue.Empty:
                pass
            for future in list(pending):
                if not future.done(): continue
                task = pending.pop(future)
                try:
                    result = future.result()
                    if not result.get('stopped') and result['processed'] != totals[task]:
                        raise ValueError(f'count differs: observed {result["processed"]}, summary {totals[task]}')
                except Exception as exc:
                    failed.append(task)
                    print(f'TASK ERROR {task}: {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
            fill()
            if time.monotonic() - last_print >= 5:
                progress(start, done, total, counts, 'draining' if interrupted else 'label')
                last_print = time.monotonic()
        # Queue feeder events may arrive just after the final future.
        pool.shutdown(wait=True)
        while True:
            try:
                kind, count = events.get(timeout=.2)
                counts[kind] = counts.get(kind, 0) + count; done += count
            except queue.Empty: break
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    progress(start, done, total, counts, 'stopped' if interrupted else 'finished')
    if failed or counts.get('error'):
        raise SystemExit(1)
    if interrupted:
        raise SystemExit(130)


if __name__ == '__main__':
    main()
