#!/usr/bin/env python3
"""Measure OUT after freshly deriving mutant DETs through the shared evaluator."""
import argparse
from collections import Counter
from contextlib import closing
import fcntl
import hashlib
from itertools import groupby
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time

# Load one qualified backend closure, including study_paths and metadata.
# The unmerged consumer itself remains at this script's path.
_bootstrap = argparse.ArgumentParser(add_help=False)
_bootstrap.add_argument('--evaluator-code-root', type=Path,
                        default=Path(__file__).resolve().parents[3])
_backend = _bootstrap.parse_known_args()[0].evaluator_code_root.resolve()
sys.path.insert(0, str(_backend))
from study_paths import CODE_ROOT, DATA_ROOT
if CODE_ROOT.resolve() != _backend:
    raise RuntimeError('shared evaluator study_paths imported from another checkout')
for path in (CODE_ROOT / 'ast/run', CODE_ROOT / 'ast/run/mech', CODE_ROOT / 'judgetool'):
    sys.path.append(str(path))
from det_fit_store import Store, canonical, digest, inputs, semantic_facts
from mech.source_read import SourceReader

OUTPUT = DATA_ROOT / 'ast/run/mech/det-later-fit'
BAD = '0571e3bc196a7b1298723e1015c406b42d38afff45dc933045945fbd819990e0'
GOOD = '0b6e5ff487e137255a8f9b6a249f60ba0af012b2c0eeb6d28c890c12d87faac7'


def label_pair(pair_id, *, base, output, source_reader, evaluator,
               remeasure=False, retry_unknown=False):
    """Commit one population DET result using the caller's shared evaluator.

    The evaluator supplies the population task directory through its config;
    this function never selects a corpus-v11 config. The source comes from
    mech.SourceReader and the durable result goes to ``output``.
    """
    base=Path(base).resolve();output=Path(output).resolve()
    with closing(sqlite3.connect(base.as_uri()+'?mode=ro',uri=True)) as source_db:
        row=source_db.execute('SELECT source_sha256,result_sha256,record_json FROM pairs '
                              'WHERE pair_id=?',(pair_id,)).fetchone()
    if row is None:raise KeyError('population base pair absent: '+pair_id)
    source_hash,base_hash,text=row;item=json.loads(text)
    if (digest(item)!=base_hash or item.get('pair_id')!=pair_id or
            item.get('source_sha256')!=source_hash):
        raise ValueError('population base pair integrity differs: '+pair_id)
    if item.get('kind','').upper()!='DET':
        raise ValueError('derived later-fit requires a DET pair: '+pair_id)
    task_file=Path(evaluator.cfg['tasks']).resolve()/(item['task']+'.json')
    task_sha=hashlib.sha256(task_file.read_bytes()).hexdigest()
    identity=digest(inputs(source_hash,task_sha))
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        store=Store(output)
        try:
            old=None if remeasure else store.load(pair_id,identity)
            if old is not None and not (retry_unknown and old['status']=='unknown'):
                return old
            record=source_reader.record(item)
            if digest(record)!=source_hash:
                raise ValueError('population source receipt differs: '+pair_id)
            native_base=Path(item['source']['corpus']).resolve()/item['task']
            result=evaluator.det_later_fit(record,native_base=native_base)
            store.write(pair_id,identity,source_hash,result)
            return result
        finally:
            store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluator-code-root', type=Path, default=_backend)
    parser.add_argument('--base', type=Path, default=DATA_ROOT / 'ast/run/mech/labels.sqlite3')
    parser.add_argument('--output', type=Path, default=OUTPUT / 'results.sqlite3')
    parser.add_argument('--config', type=Path, default=DATA_ROOT / 'ast/run/corpus-v11/run.json')
    parser.add_argument('--scope', choices=('smoke', 'figure', 'points', 'all'), default='smoke')
    parser.add_argument('--point-file', type=Path, default=DATA_ROOT / 'feat-exp/study/round-6/det-points.json')
    parser.add_argument('--deadline', type=float, default=30)
    parser.add_argument('--batch-size', type=int, default=128)
    parser.add_argument('--pair-id', action='append', default=[])
    parser.add_argument('--parity-baseline', type=Path)
    parser.add_argument('--retry-unknown', action='store_true')
    parser.add_argument('--remeasure', action='store_true')
    parser.add_argument('--remeasure-pair', action='append', default=[],
                        help='explicitly remeasure only named pairs in the selected scope')
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error('--batch-size must be positive')
    parity = {}
    if args.parity_baseline:
        parity = {r['pair_id']:r['semantics'] for r in json.loads(args.parity_baseline.read_text())['records']}
        if not args.pair_id:
            args.pair_id = list(parity)
    args.output = args.output.resolve()
    if not args.output.is_relative_to(OUTPUT):
        parser.error('outputs must stay under DATA_ROOT/ast/run/mech/det-later-fit')
    # Fail startup if a stale evaluator lacks the agreed mode; never publish a
    # population of unknown facts for a deployment/API mismatch.
    from evaluator import ReplayEvaluator
    if not callable(getattr(ReplayEvaluator, 'det_later_fit', None)):
        raise RuntimeError('shared ReplayEvaluator.det_later_fit is not deployed; merge n-eval first')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lock = args.output.with_suffix('.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    cfg = json.loads(args.config.read_text())
    task_dir = Path(cfg['tasks']).resolve()
    base = sqlite3.connect(args.base.resolve().as_uri() + '?mode=ro', uri=True)
    points = json.loads(args.point_file.read_text()) if args.scope == 'points' else []
    print('phase=index selecting stored DET pairs', flush=True)
    candidates = []
    query = "SELECT pair_id,source_sha256,result_sha256,record_json FROM pairs"
    params = []
    if args.pair_id:
        query += ' WHERE pair_id IN (' + ','.join('?' for _ in args.pair_id) + ')'
        params = args.pair_id
    else:
        query += " WHERE upper(json_extract(record_json,'$.kind'))='DET'"
    for pid, source, sha, text in base.execute(query, params):
        row = json.loads(text)
        if digest(row) != sha or row['pair_id'] != pid or row['source_sha256'] != source:
            raise ValueError('base fact integrity failure: ' + pid)
        selected = args.scope == 'all'
        if args.scope == 'smoke':
            selected = pid in (BAD, GOOD)
        elif args.scope == 'figure':
            selected = row['task'] == '6e02f1e3' and row['case'] == '$Figure $Fixed' and row['point'] == [6, 0]
        elif args.scope == 'points':
            selected = any(all(row[k] == point[k] for k in ('task', 'case', 'point')) for point in points)
        if selected:
            if row.get('kind', '').upper() != 'DET':
                raise ValueError('requested pair is not DET: ' + pid)
            candidates.append(row)
    # One native task/case/point at a time; batch source reads stay sequential.
    anchors = {}
    for row in candidates:
        case = (row['source']['corpus'], row['task'], row['case'])
        position = (row['source']['file'], row['source']['line'])
        anchors[case] = min(anchors.get(case, position), position)
    candidates.sort(key=lambda b:(b['source']['corpus'], b['task'],
                                  anchors[(b['source']['corpus'], b['task'], b['case'])],
                                  tuple(b['point']), b['source']['file'], b['source']['line']))
    if args.pair_id and {b['pair_id'] for b in candidates} != set(args.pair_id):
        raise ValueError('requested DET pair is missing from selected scope')
    if args.scope == 'smoke' and {b['pair_id'] for b in candidates} != {BAD, GOOD}:
        raise ValueError('required smoke pair is absent from base')
    total = len(candidates)
    state = dict(done=0, skipped=0, evaluated=0, phase='setup')
    start = time.monotonic(); stop = threading.Event()
    elapsed_samples = []; counts = Counter(); outcomes = {}
    def progress():
        elapsed = time.monotonic() - start
        rate = state['done'] / max(elapsed, .001)
        eta = (total-state['done'])/rate if rate else None
        print(f"done={state['done']}/{total} elapsed={elapsed:.1f}s rate={rate:.3f}/s "
              f"ETA={eta if eta is not None else 'unknown'}s skipped={state['skipped']} phase={state['phase']}", flush=True)
    def heartbeat():
        while not stop.wait(5):
            progress()
    thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
    source = SourceReader(CODE_ROOT); store = None; ev = None
    task_hashes = {}
    try:
        store = Store(args.output)
        for _, task_rows in groupby(candidates, key=lambda b:(b['source']['corpus'], b['task'])):
            task_rows = list(task_rows)
            task = task_rows[0]['task']
            if task not in task_hashes:
                task_hashes[task] = hashlib.sha256((task_dir / (task + '.json')).read_bytes()).hexdigest()
            for begin in range(0, len(task_rows), args.batch_size):
                batch = task_rows[begin:begin + args.batch_size]
                loaded = {}; identities = {}; pending = []
                for row in batch:
                    pid = row['pair_id']
                    identity = identities[pid] = digest(inputs(row['source_sha256'], task_hashes[task]))
                    result = None if args.remeasure or pid in args.remeasure_pair else store.load(pid, identity)
                    if result is None or (args.retry_unknown and result['status'] == 'unknown'):
                        pending.append(row)
                    else:
                        loaded[pid] = result
                # Only a bounded batch of source records is retained. Resume
                # hits never open their original gzip or initialize the engine.
                state['phase'] = task + '/source-batch'
                records = {row['pair_id']:source.record(row) for row in
                           sorted(pending, key=lambda b:(b['source']['file'], b['source']['line']))}
                for row in batch:
                    pid = row['pair_id']; state['phase'] = task + '/' + pid[:12]
                    result = loaded.get(pid)
                    if result is not None:
                        state['skipped'] += 1
                    else:
                        if ev is None:
                            ev = ReplayEvaluator(config=args.config, deadline=args.deadline,
                                                 artifacts=OUTPUT / 'artifacts')
                        record = records.pop(pid)
                        began = time.monotonic()
                        result = ev.det_later_fit(record, native_base=Path(row['source']['corpus']) / task)
                        elapsed = time.monotonic() - began
                        if pid in parity and semantic_facts(result) != parity[pid]:
                            raise RuntimeError('performance parity differs: ' + pid + ': ' + canonical(semantic_facts(result)))
                        store.write(pid, identities[pid], row['source_sha256'], result)
                        elapsed_samples.append(elapsed); state['evaluated'] += 1
                        print(canonical(dict(pair_id=pid, seconds=elapsed,
                              fits_train=result['fits_train'], fits_test=result['fits_test'],
                              status=result['status'], first_later_difference=result.get('first_later_difference'),
                              reason=result.get('reason'),
                              diagnostic_work=result.get('receipt', {}).get('diagnostic_work'),
                              phase_wall_seconds=result.get('receipt', {}).get('phase_wall_seconds'))), flush=True)
                    if pid in parity and semantic_facts(result) != parity[pid]:
                        raise RuntimeError('stored performance parity differs: ' + pid)
                    if args.scope in ('smoke', 'figure'):
                        outcomes[pid] = result
                    counts[(result['status'], result['fits_train'], result['fits_test'])] += 1
                    state['done'] += 1
        state['phase'] = 'complete'; progress()
        # These are run-time reports, not stored grades or summary copies.
        print(canonical(dict(evaluated=state['evaluated'], skipped=state['skipped'],
              evaluated_seconds=sum(elapsed_samples),
              seconds_per_evaluated_pair=sum(elapsed_samples)/len(elapsed_samples) if elapsed_samples else None,
              counts=[dict(status=s, fits_train=t, fits_test=u, count=n) for (s,t,u),n in counts.items()])), flush=True)
        if args.scope in ('smoke', 'figure'):
            for pid, expected in ((BAD, False), (GOOD, True)):
                if pid not in outcomes or outcomes[pid]['fits_train'] is not expected:
                    raise RuntimeError('derived-DET smoke expectation failed for ' + pid)
            if outcomes[GOOD]['status'] != 'complete' or outcomes[GOOD]['fits_test'] is not True:
                raise RuntimeError('passing smoke requires complete TEST evidence for the same TRAIN-fit assignments')
            failed = outcomes[BAD].get('first_later_difference') or {}
            if failed.get('reason') != 'empty' or 'fig_diag' not in str(failed.get('relation', '')):
                raise RuntimeError('expected first later empty relation fig_diag in failing smoke')
            if args.scope == 'figure':
                fits = [outcomes[b['pair_id']] for b in candidates if b.get('label') == 'fits']
                if len(fits) < 53 or any(r['fits_train'] is not False for r in fits):
                    raise RuntimeError('Figure expected all 53 legacy fits pairs to fail TRAIN')
    finally:
        stop.set(); thread.join()
        source.close(); base.close()
        if store is not None:
            store.close()
        if ev is not None:
            ev.close()
        lock.close()


if __name__ == '__main__':
    main()
