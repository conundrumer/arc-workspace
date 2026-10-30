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
from paused_storage import write_gzip_json

# Bump only for an acquisition/status-contract change, not serialization.
ACQUISITION_POLICY = 'prefix-dev-gold-representative-mutant-v1'
STORAGE_PREDECESSORS = {'3d3f4ca96b366e7616f14e3427194eb8bc8398120b749f54d7488d8da4ba2ba9'}
from det_full_body_run import file_sha, digest, read, exclusive, manifest_for, verify_manifest


def summarize(value):
    """Retain status and provenance, not a second copy of packet rows."""
    return {key: value[key] for key in ('schema', 'status', 'complete', 'reason',
        'body_table', 'receipt', 'report_ref', 'receipt_ref') if key in value}


def opening_summary(report, reference):
    """Bulk parent values/frontier remain once in the native opening report."""
    keys = ('schema','status','reason','task','body_path','universe_ref',
            'ident_namespace','coverage','fanout','timings','receipt_reserved_bytes',
            'raw_reuse','settings','admission','model_contract')
    value = {key:report[key] for key in keys if key in report}
    value['report_ref'] = reference
    value['parameter_count'] = len(report.get('parameters', []))
    value['frontier'] = {key:report.get('frontier', {}).get(key)
                         for key in ('status','reason')}
    return value


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
            opening = opening_summary(point.report, point.opening_ref)
            begin = time.monotonic()
            gold = point.acquire()
            gold_seconds = time.monotonic() - begin
            write_gzip_json(args.point_output / 'gold.json.gz', gold)
            gold_summary = summarize(gold)
            del gold
            begin = time.monotonic()
            mutant = point.acquire(mutant_record=record)
            mutant_seconds = time.monotonic() - begin
            write_gzip_json(args.point_output / 'mutant.json.gz', mutant)
            result = dict(status='measured' if point._opening_complete() else 'unavailable', opening=opening,
                gold=gold_summary, mutant=summarize(mutant),
                gold_seconds=gold_seconds, mutant_seconds=mutant_seconds,
                acquisition_seconds=time.monotonic() - started,
                opening_ref=point.opening_ref, source_sha256=base['source_sha256'], runtime=build['revision'],
                point=operation, scope='gold plus one representative mutant on shared U')
            write_json(args.point_output / 'acquisition.json', result, compact=True)
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


def measurement_summary(done, directory):
    value = {key:item for key,item in done.items() if key != 'files'}
    report = value.get('opening')
    if isinstance(report, dict) and 'parent_assignments' in report:
        path = directory / 'native/universe.json'
        if not path.is_file():
            raise ValueError('bulk legacy opening lacks its authoritative native report')
        value['opening'] = opening_summary(report, dict(path=str(path),sha256=file_sha(path)))
    value['measurement_ref'] = dict(path=str(directory / 'artifact-manifest.json'),
        sha256=file_sha(directory / 'artifact-manifest.json'))
    return value


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
        CODE_ROOT / 'judgetool/evaluator.py', CODE_ROOT / 'judge3/paused_storage.py']
    code = {str(x.relative_to(CODE_ROOT)): file_sha(x) for x in source_files}
    build = read(args.runtime / 'ready.json')
    if args.expected_revision is not None and not build['revision'].startswith(args.expected_revision):
        raise ValueError('trial runtime differs from the coordinator-pinned revision')
    import arclog
    if not hasattr(arclog.StudyTaskEvaluator,'assignment_cap'):
        raise ValueError('trial requires cap-fixed native runtime with authoritative session assignment_cap')
    previous_scope = read(args.output / 'scope.json', {})
    acquisition_code = {name:value for name,value in code.items() if name not in ('judge3/prefix_dev_trial.py','judge3/paused_storage.py')}
    previous_code = previous_scope.get('code', {})
    legacy_reusable = (previous_code.get('judge3/prefix_dev_trial.py') in STORAGE_PREDECESSORS
        and {name:value for name,value in previous_code.items() if name not in ('judge3/prefix_dev_trial.py','judge3/paused_storage.py')} == acquisition_code
        and previous_scope.get('runtime') == build
        and previous_scope.get('deadline') == args.deadline
        and previous_scope.get('max_assignments') == args.max_assignments)
    scope = dict(acquisition_policy=ACQUISITION_POLICY, selection_sha256=file_sha(args.selection), runtime=build,
        code=code, deadline=args.deadline, max_assignments=args.max_assignments)
    rows = []
    with exclusive(args.output / 'trial.lock'):
        write_json(args.output / 'scope.json', scope)
        for operation in operations:
            key = digest(dict(runtime=build, acquisition_policy=ACQUISITION_POLICY, code=acquisition_code, deadline=args.deadline,
                              max_assignments=args.max_assignments, operation=operation))
            directory = args.output / 'points' / operation['point_id'] / key
            done = read(directory / 'artifact-manifest.json')
            if done is None and legacy_reusable:
                legacy_key = digest(dict(runtime=build, code=previous_code, deadline=args.deadline,
                    max_assignments=args.max_assignments, operation=operation))
                legacy_directory = args.output / 'points' / operation['point_id'] / legacy_key
                legacy = read(legacy_directory / 'artifact-manifest.json')
                if legacy is not None and legacy['key'] == legacy_key and legacy['point_id'] == operation['point_id']:
                    verify_manifest(legacy_directory, legacy['files'])
                    # Save only a small reuse pointer, not another copy of rows.
                    write_json(directory / 'reused-measurement.json', dict(
                        source=str(legacy_directory / 'artifact-manifest.json'),
                        sha256=file_sha(legacy_directory / 'artifact-manifest.json')), compact=True)
                    rows.append(measurement_summary(legacy, legacy_directory))
                    continue
            pointer = read(directory / 'reused-measurement.json')
            if done is None and pointer is not None:
                if file_sha(pointer['source']) != pointer['sha256']:
                    raise ValueError('reused measurement receipt changed')
                legacy = read(Path(pointer['source']))
                verify_manifest(Path(pointer['source']).parent, legacy['files'])
                rows.append(measurement_summary(legacy, Path(pointer['source']).parent))
                continue
            if done is not None:
                if done['key'] != key or done['point_id'] != operation['point_id']:
                    raise ValueError('stored point measurement identity differs')
                verify_manifest(directory, done['files'])
                rows.append(measurement_summary(done, directory))
                continue
            directory.mkdir(parents=True, exist_ok=True)
            run_child(args, operation, directory)
            files = manifest_for(directory)
            acquisition = read(directory / 'acquisition.json', {})
            done = dict(point_id=operation['point_id'], kind=operation['kind'], key=key,
                process=read(directory / 'process.json'),
                status=acquisition.get('status', 'process_failed'),
                opening=acquisition.get('opening', read(directory / 'opening.json')),
                opening_ref=acquisition.get('opening_ref'), gold=acquisition.get('gold'),
                mutant=acquisition.get('mutant'),
                gold_seconds=acquisition.get('gold_seconds'),
                mutant_seconds=acquisition.get('mutant_seconds'),
                output_bytes=sum(x['bytes'] for x in files.values()), files=files)
            write_json(directory / 'artifact-manifest.json', done)
            rows.append(measurement_summary(done, directory))
            print(json.dumps({k:done[k] for k in ('point_id','kind','process','status','output_bytes')}), flush=True)
            write_json(args.output / 'summary.json', dict(scope=scope, points=rows,
                count=len(rows), total=len(operations), publication=False,
                counts=dict(Counter(x['status'] for x in rows))))
    write_json(args.output / 'summary.json', dict(scope=scope, points=rows,
        count=len(rows), total=len(operations), publication=False,
        counts=dict(Counter(x['status'] for x in rows))), compact=True)
    return int(any(x['process']['returncode'] != 0 for x in rows))


if __name__ == '__main__':
    raise SystemExit(main())
