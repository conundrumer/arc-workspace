#!/usr/bin/env python3
"""DEV-only prefix-U cost trial. Operator artifacts only; no feature publication."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT
sys.path[:0] = [str(CODE_ROOT / 'judge3'), str(CODE_ROOT / 'judgetool'),
                str(CODE_ROOT / 'ast/run'), str(CODE_ROOT / 'ast/run/mech')]
from dataset_format import write_json
from det_full_body_run import file_sha, digest, read, exclusive, manifest_for, verify_manifest


def summarize(value):
    """Retain status and provenance, not a second copy of packet rows."""
    return {key: value[key] for key in ('schema', 'status', 'complete', 'reason',
        'body_table', 'receipt', 'report_ref') if key in value}


def worker(args):
    operation = read(args.operation)
    # Native runtime supplies arclog; the project environment supplies optional
    # table transport dependencies after the runtime's own site-packages.
    sys.path.append(str(MAIN_ROOT / '.venv/lib/python3.12/site-packages'))
    from evaluator import ReplayEvaluator
    from provenance import load_build
    from export_by_pair_id import PairSource
    from source_read import SourceReader
    from prefix_universe import PrefixPoint
    build = read(args.runtime / 'ready.json')
    labels = sqlite3.connect(args.labels.resolve().as_uri() + '?mode=ro', uri=True)
    reader = SourceReader(CODE_ROOT)
    ev = None
    try:
        base = PairSource.base(SimpleNamespace(labels=labels), operation['pair_id'])
        record = reader.record(base)
        if list(record['point']) != operation['body_path']:
            raise ValueError('representative source point differs from selected body path')
        if base['task'] != operation['task'] or base['case'] != operation['case']:
            raise ValueError('representative source differs from selected DEV point')
        ev = ReplayEvaluator(deadline=args.deadline, artifacts=args.point_output / 'native-replays')
        load_build(ev.arclog, SimpleNamespace(build_receipt=None,
            engine_commit=build['revision'], wheel=Path(build['wheel'])))
        started = time.monotonic()
        with PrefixPoint(ev, record, max_assignments=args.max_assignments,
                         artifacts=args.point_output / 'native') as point:
            opening = point.report
            write_json(args.point_output / 'opening.json', opening)
            begin = time.monotonic()
            gold = point.acquire()
            gold_seconds = time.monotonic() - begin
            write_json(args.point_output / 'gold.json', gold)
            gold_summary = summarize(gold)
            del gold
            begin = time.monotonic()
            mutant = point.acquire(mutant_record=record)
            mutant_seconds = time.monotonic() - begin
            write_json(args.point_output / 'mutant.json', mutant)
            result = dict(status='measured' if point._opening_complete() else 'unavailable', opening=opening,
                gold=gold_summary, mutant=summarize(mutant),
                gold_seconds=gold_seconds, mutant_seconds=mutant_seconds,
                acquisition_seconds=time.monotonic() - started,
                source_sha256=base['source_sha256'], runtime=build['revision'],
                point=operation, scope='gold plus one representative mutant on shared U')
            write_json(args.point_output / 'acquisition.json', result)
        return 0
    finally:
        if ev is not None:
            ev.close()
        reader.close()
        labels.close()


def run_child(args, operation, directory):
    """One adapter process per measurement; child RSS does not accumulate."""
    write_json(directory / 'operation.json', operation)
    command = [sys.executable, '-B', str(Path(__file__).resolve()), '--worker',
        '--operation', str(directory / 'operation.json'), '--runtime', str(args.runtime),
        '--labels', str(args.labels), '--point-output', str(directory),
        '--deadline', str(args.deadline)]
    if args.max_assignments is not None:command += ['--max-assignments',str(args.max_assignments)]
    # A separate monitor ensures RUSAGE_CHILDREN covers exactly this adapter
    # process and its descendants, including native import/serialization cost.
    monitor = '''import json,resource,subprocess,sys,time
t=time.monotonic()
p=subprocess.run(json.loads(sys.argv[1]))
r=resource.getrusage(resource.RUSAGE_CHILDREN)
open(sys.argv[2],'w').write(json.dumps(dict(returncode=p.returncode,wall_seconds=time.monotonic()-t,peak_rss_bytes=int(r.ru_maxrss*(1 if sys.platform=='darwin' else 1024)))))
'''
    with (directory / 'process.log').open('w') as log:
        subprocess.run([sys.executable, '-B', '-c', monitor, json.dumps(command),
                        str(directory / 'process.json')], stdout=log, stderr=log, check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selection', type=Path)
    p.add_argument('--splits', type=Path, default=DATA_ROOT / 'feat-exp/stream/splits.json')
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--expected-revision', help='Optional assertion of the selected native build revision')
    p.add_argument('--output', type=Path, default=DATA_ROOT / 'judgetool/prefix-dev-trial/9173dfe2')
    p.add_argument('--labels', type=Path, default=DATA_ROOT / 'ast/run/mech/labels.sqlite3')
    p.add_argument('--deadline', type=float, default=30)
    p.add_argument('--max-assignments', type=int, default=None,
                   help='Optional assertion of the native session assignment cap; omitted uses that session setting')
    p.add_argument('--worker', action='store_true')
    p.add_argument('--operation', type=Path)
    p.add_argument('--point-output', type=Path)
    args = p.parse_args()
    if args.worker:
        return worker(args)
    selection = read(args.selection)
    splits = read(args.splits)
    operations = selection['points']
    if len({x['point_id'] for x in operations}) != len(operations):
        raise ValueError('duplicate trial point')
    if any(splits.get(x['task']) != 'dev' for x in operations):
        raise ValueError('trial selection contains a task not explicitly DEV')
    # Refuse a stale or absent adapter before starting any candidate work.
    source_files = [Path(__file__), CODE_ROOT / 'prefix_universe.py',
        CODE_ROOT / 'native_correspondence.py', CODE_ROOT / 'evaluator_train.py',
        CODE_ROOT / 'judgetool/evaluator.py']
    code = {str(x.relative_to(CODE_ROOT)): file_sha(x) for x in source_files}
    build = read(args.runtime / 'ready.json')
    if args.expected_revision is not None and not build['revision'].startswith(args.expected_revision):
        raise ValueError('trial runtime differs from the coordinator-pinned revision')
    import arclog
    if not hasattr(arclog.StudyTaskEvaluator,'assignment_cap'):
        raise ValueError('trial requires cap-fixed native runtime with authoritative session assignment_cap')
    scope = dict(selection_sha256=file_sha(args.selection), runtime=build,
        code=code, deadline=args.deadline, max_assignments=args.max_assignments)
    rows = []
    with exclusive(args.output / 'trial.lock'):
        write_json(args.output / 'scope.json', scope)
        for operation in operations:
            key = digest(dict(runtime=build, code=code, deadline=args.deadline,
                              max_assignments=args.max_assignments, operation=operation))
            directory = args.output / 'points' / operation['point_id'] / key
            done = read(directory / 'artifact-manifest.json')
            if done is not None:
                if done['key'] != key or done['point_id'] != operation['point_id']:
                    raise ValueError('stored point measurement identity differs')
                verify_manifest(directory, done['files'])
                rows.append(done)
                continue
            directory.mkdir(parents=True, exist_ok=True)
            run_child(args, operation, directory)
            files = manifest_for(directory)
            acquisition = read(directory / 'acquisition.json', {})
            done = dict(point_id=operation['point_id'], kind=operation['kind'], key=key,
                process=read(directory / 'process.json'),
                status=acquisition.get('status', 'process_failed'),
                opening=acquisition.get('opening', read(directory / 'opening.json')), gold=acquisition.get('gold'),
                mutant=acquisition.get('mutant'),
                gold_seconds=acquisition.get('gold_seconds'),
                mutant_seconds=acquisition.get('mutant_seconds'),
                output_bytes=sum(x['bytes'] for x in files.values()), files=files)
            write_json(directory / 'artifact-manifest.json', done)
            rows.append(done)
            print(json.dumps({k:done[k] for k in ('point_id','kind','process','status','output_bytes')}), flush=True)
            write_json(args.output / 'summary.json', dict(scope=scope, points=rows,
                count=len(rows), total=len(operations), publication=False,
                counts=dict(Counter(x['status'] for x in rows))))
    return int(any(x['process']['returncode'] != 0 for x in rows))


if __name__ == '__main__':
    raise SystemExit(main())
