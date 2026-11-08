#!/usr/bin/env python3
"""Follow finished corpus tasks and reread every stored mutant stream.

Uses exactly CURRENT's interpreter and wheel. Two independent task sessions
run concurrently; native from_stream releases the GIL. No OUT evaluation.
The output is a resumable, flushed JSONL journal, including every failure.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[2]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
AST = ROOT.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', type=Path, default=DATA_ROOT / 'ast/run/CURRENT.json')
    parser.add_argument('--runtime-manifest', type=Path, help='Explicit candidate selection; CURRENT is unchanged')
    parser.add_argument('--corpus', type=Path, default=DATA_ROOT / 'ast/run/corpus-v6')
    parser.add_argument('--output', type=Path, default=DATA_ROOT / 'ast/run/kept-streams-canonical-v6.jsonl')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--poll', type=float, default=5)
    parser.add_argument('--task', action='append', help='Restrict to named finished tasks')
    parser.add_argument('--once', action='store_true', help='Drain available tasks and exit')
    args = parser.parse_args()
    if args.workers < 1 or args.poll <= 0:
        parser.error('workers and poll must be positive')
    for key in ('ARCLOG_THREADS', 'RAYON_NUM_THREADS', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
        os.environ[key] = '1'
    from provenance import select_runtime
    selected = select_runtime(args.current, args.runtime_manifest)
    runtime, python, build = (selected[k] for k in ('runtime', 'python', 'build'))
    import arclog
    config = json.loads((args.corpus / 'run.json').read_text())
    corpus_build = json.loads((args.corpus / 'build.json').read_text())
    for key in ('engine_commit', 'wheel_sha256', 'native_binary_sha256'):
        if args.runtime_manifest is None and corpus_build[key] != build[key]:
            parser.error('CURRENT runtime differs from corpus ' + key)
    tasks_dir = Path(config['tasks'])
    expected = set(args.task or [p.parent.name for p in (Path(config['export']) / 'tasks').glob('*/cases.npz')])
    journal_config = dict(corpus=str(args.corpus.resolve()), engine_commit=build['engine_commit'],
                          wheel_sha256=build['wheel_sha256'], native_binary_sha256=build['native_binary_sha256'],
                          policy='all-stored-pairs-exact-stream-and-canonical-sexp-v2')
    if args.runtime_manifest is not None:
        journal_config.update(candidate_replay=True, source_engine_commit=corpus_build['engine_commit'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lock = args.output.with_suffix(args.output.suffix + '.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    completed = set()
    totals = Counter()
    end = 0
    if args.output.exists():
        with args.output.open('rb') as source:
            for line in source:
                try:
                    row = json.loads(line)
                except ValueError:
                    if line.endswith(b'\n'):
                        raise
                    break
                if row.get('journal_config') != journal_config:
                    parser.error('output provenance/config differs; use a new output')
                if not line.endswith(b'\n'):
                    # Recheck the last uncommitted/torn row after restart.
                    break
                end = source.tell()
                if row.get('type') == 'task' and row.get('completed'):
                    if row['task'] in completed:
                        raise ValueError('duplicate terminal task in checkpoint')
                    completed.add(row['task'])
                    totals.update(row['counts'])
        with args.output.open('r+b') as dst:
            dst.truncate(end)
    initial_done = len(completed & expected)
    started = time.monotonic()
    mutex = threading.Lock()
    counts = Counter()
    attempted = set()
    with args.output.open('a', buffering=1) as dst:
        def emit(row):
            row['journal_config'] = journal_config
            text = json.dumps(row, separators=(',', ':'))
            with mutex:
                dst.write(text + '\n')
                dst.flush()
                print(text, flush=True)

        def progress():
            elapsed = time.monotonic() - started
            done = len(completed & expected)
            rate = (done - initial_done) / max(elapsed, 1e-9)
            with mutex:
                pairs = counts['pairs']
            print(json.dumps(dict(event='progress', done=done, total=len(expected),
                                  elapsed=round(elapsed, 2), rate=round(rate, 4),
                                  eta=round((len(expected) - done) / rate, 2) if rate else None,
                                  pairs_this_run=pairs, pairs_per_second=round(pairs / max(elapsed, 1e-9), 3),
                                  active=len(futures))), file=sys.stderr, flush=True)

        def check(task):
            tick = time.monotonic()
            local = Counter()
            row = None
            stage = 'task_setup'
            taskdir = args.corpus / task
            try:
                manifest = json.loads((taskdir / 'manifest.json').read_text())
                for key in ('engine_commit', 'wheel_sha256', 'native_binary_sha256'):
                    if manifest['provenance'][key] != corpus_build[key]:
                        raise ValueError('task runtime differs: ' + key)
                task_obj = arclog.Task.from_json((tasks_dir / (task + '.json')).read_text(), arclog.World.Closed)
                settings = arclog.DecodeSettings(rule_tests=False)
                session = arclog.Session(task_obj, settings, session_bytes=arclog.STUDY_SESSION_BYTES)
                stage = 'read_pairs'
                with gzip.open(taskdir / 'pairs.jsonl.gz', 'rt') as source:
                    for index, line in enumerate(source):
                        row = json.loads(line)
                        local['pairs'] += 1
                        with mutex:
                            counts['pairs'] += 1
                        try:
                            stream = row.get('mutant_stream')
                            if stream is None:
                                raise ValueError('stored pair has no mutant_stream')
                            # This API checks grammar, binding, whole-program
                            # checks, and exact replay ids/flags internally.
                            program = arclog.StudyProgram.from_stream(session, stream['ids'], stream['model'])
                            stored_program = arclog.StudyProgram.from_sexp(row['mutant_sexp'], settings, session=session)
                            canonical = stored_program.decode_stream()
                            if canonical[0] != stream['ids'] or list(canonical[1]) != stream['model']:
                                raise ValueError('stored mutant_sexp canonical ids/model differ from stored mutant_stream')
                            local['verified'] += 1
                        except Exception as exc:
                            local['failures'] += 1
                            emit(dict(type='failure', task=task, case=row.get('case'), point=row.get('point'),
                                      index=index, identity=row.get('identity'), message=f'{type(exc).__name__}: {exc}'))
                stage = 'pair_count'
                promised = json.loads((taskdir / 'summary.json').read_text())['counts']['totals'].get('pairs', 0)
                if promised != local['pairs']:
                    raise ValueError(f'pair count differs: read {local["pairs"]}, task summary {promised}')
                return dict(type='task', task=task, completed=True, status='failed' if local['failures'] else 'verified',
                            counts=dict(local), seconds=round(time.monotonic() - tick, 6))
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                # Native PanicException is a BaseException. Record it as an
                # unsuccessful task; the task is eligible on the next restart.
                local['task_failures'] += 1
                emit(dict(type='failure', task=task, case=row.get('case') if row else None,
                          point=row.get('point') if row else None, phase=stage, message=f'{type(exc).__name__}: {exc}'))
                return dict(type='task', task=task, completed=False, status='fault', counts=dict(local),
                            seconds=round(time.monotonic() - tick, 6))

        emit(dict(type='start', runtime=str(runtime), python=str(python), workers=args.workers, resumed_tasks=initial_done))
        futures = {}
        last_progress = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            while True:
                available = [p.name for p in args.corpus.iterdir()
                             if not p.name.startswith('.') and p.is_dir() and (p / 'summary.json').is_file()
                             and p.name in expected and p.name not in completed and p.name not in attempted]
                for task in sorted(available):
                    if len(futures) >= args.workers:
                        break
                    attempted.add(task)
                    futures[pool.submit(check, task)] = task
                if futures:
                    finished, _ = wait(futures, timeout=1, return_when=FIRST_COMPLETED)
                    for future in finished:
                        futures.pop(future)
                        result = future.result()
                        emit(result)
                        if result['completed']:
                            completed.add(result['task'])
                            totals.update(result['counts'])
                if time.monotonic() - last_progress >= 2:
                    progress()
                    last_progress = time.monotonic()
                if not futures and not available:
                    if args.once or (args.corpus / 'summary.json').exists():
                        break
                    time.sleep(args.poll)
        progress()
        emit(dict(type='summary', done=len(completed & expected), total=len(expected), counts=dict(totals),
                  elapsed=round(time.monotonic() - started, 3), failed_tasks=sorted(attempted - completed)))
    return int(bool(totals['failures'] or attempted - completed))


if __name__ == '__main__':
    raise SystemExit(main())
