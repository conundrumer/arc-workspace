#!/usr/bin/env python3
"""Parallel runtime replay/reprint of old export streams; no synthetic tests.

Each JSONL row records one case; no source data or historical tables are edited.
--tables also evaluates full native relation tables and rejects Unit schemas.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
import threading
import time

from check_stage1_all import inventory

AST = Path(__file__).resolve().parents[3]


def main():
    import arclog
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', type=Path, default=Path('/Users/davidlu/code/arc-workspace/work/lm/data-full-9fac8128'))
    parser.add_argument('--tasks', type=Path, default=AST / 'engine/data/tasks')
    parser.add_argument('--jobs', type=int, default=12)
    parser.add_argument('--case-manifest', type=Path)
    parser.add_argument('--tables', action='store_true')
    parser.add_argument('--output', type=Path, default=AST / 'unit-old-streams.jsonl')
    args = parser.parse_args()
    selected = None
    if args.case_manifest:
        selected = {}
        for row in json.loads(args.case_manifest.read_text())['fault_cases']:
            selected.setdefault(row['task'], set()).add(row['case'])
    tasks = sorted(selected if selected is not None else [p.parent.name for p in (args.export / 'tasks').glob('*/cases.npz')])
    total = sum(len(names) if selected is None else sum(n in selected[task] for n in names)
                for task in tasks for names in [inventory(args.export, task)])
    started = time.monotonic()
    lock = threading.Lock()
    counts = Counter()
    done = threading.Event()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as dst:
        def progress():
            elapsed = time.monotonic() - started
            print(f"done {counts['case']}/{total} cases, elapsed={elapsed:.1f}s, rate={counts['case']/max(elapsed,1e-9):.2f}/s, outcomes={dict(counts)}", file=sys.stderr, flush=True)

        def emit(row):
            with lock:
                dst.write(json.dumps(row) + '\n')
                dst.flush()
                if row['type'] == 'case':
                    counts['case'] += 1
                    counts[row['status']] += 1

        def heartbeat():
            while not done.wait(1):
                with lock:
                    progress()

        def run(task):
            names, offsets, ids, flags = inventory(args.export, task, True)
            settings = arclog.DecodeSettings(rule_tests=False)
            evaluator = arclog.StudyTaskEvaluator(task, str(args.tasks), settings)
            for i, case in enumerate(names):
                if selected is not None and case not in selected[task]:
                    continue
                tick = time.monotonic()
                row = dict(type='case', task=task, case=case, status='complete')
                try:
                    lo, hi = offsets[i:i+2]
                    original = (ids[lo:hi], [int(v) for v in flags[lo:hi]])
                    gold = evaluator.from_stream(*original)
                    written = gold.decode_stream()
                    if list(written[0]) != original[0] or list(written[1]) != original[1]:
                        raise ValueError('old stream ids/model flags differ after replay/reprint')
                    reparsed = arclog.StudyProgram.from_sexp(gold.sexp(), settings=settings)
                    reprinted = reparsed.decode_stream()
                    if list(reprinted[0]) != original[0] or list(reprinted[1]) != original[1]:
                        raise ValueError('old stream differs after sexp print/read/reprint')
                    row['stream_tokens'] = len(original[0])
                    if args.tables:
                        # Static schema decoding does not run continuation.
                        static = json.loads(arclog.study_frame_sources_json(gold))
                        row['static_schema'] = static.get('schema')
                        report, native = evaluator.gold_tables(gold)
                        report = json.loads(report)
                        if any('Unit' in types for types in native.tables['column_types']):
                            raise ValueError('new native relation schema contains Unit')
                        if any('Unit' in types for dets in native.tables['det_types'] for types in dets):
                            raise ValueError('new native DET schema contains Unit')
                        row['native_status'] = report
                        if report['status'] != 'complete':
                            row['status'] = report['status']
                            row['reason'] = report.get('reason')
                except Exception as exc:
                    row.update(status='fault', reason=f'{type(exc).__name__}: {exc}')
                finally:
                    evaluator.finish_case()
                row['elapsed'] = time.monotonic()-tick
                emit(row)

        reporter = threading.Thread(target=heartbeat, daemon=True)
        reporter.start()
        try:
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                futures = {pool.submit(run, task): task for task in tasks}
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as exc:
                        counts['task_fault'] += 1
                        emit(dict(type='task_fault', task=futures[future], status='fault', reason=str(exc)))
        finally:
            done.set()
            reporter.join()
        progress()
        emit(dict(type='summary', done=counts['case'], total=total, elapsed=time.monotonic()-started, counts=dict(counts), streams_digest=arclog.streams_digest()))
    return int(counts['fault'] != 0 or counts['task_fault'] != 0)


if __name__ == '__main__':
    raise SystemExit(main())
