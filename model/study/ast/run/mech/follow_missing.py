#!/usr/bin/env python3
"""Label the 16 missing v11 tasks as v12 publishes them; ingest durable rows."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import fcntl
import json
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time

from run import SCHEMA, canonical, connect, digest, published_task, setup

HERE = Path(__file__).resolve().parent
TASKS = (
    '9f41bd9c', '9f8de559', 'a096bf4d', 'a09f6c25', 'a1570a43', 'a1aa0c1e',
    'a251c730', 'a25697e4', 'a2d730bd', 'a32d8b75', 'a395ee82', 'a3f84088',
    'a416fc5b', 'a47bf94d', 'a48eeaf7', 'a57f2f04',
)


def ingest(source_db, target_db, cursor):
    """Copy only authenticated, disjoint task rows; never replace a valid row."""
    rows = source_db.execute('SELECT rowid,pair_id,source_sha256,code_sha256,config_sha256,result_sha256,record_json '
                             'FROM pairs WHERE rowid>? ORDER BY rowid', (cursor,))
    copied = 0
    for rowid, pair_id, source, code, config, result_hash, payload in rows:
        record = json.loads(payload)
        if (digest(record) != result_hash or record.get('schema') != SCHEMA
                or record.get('task') not in TASKS or record.get('pair_id') != pair_id
                or record.get('source_sha256') != source or record.get('code_sha256') != code
                or record.get('config_sha256') != config or digest(record['code_manifest']) != code
                or digest(record['config']) != config):
            raise ValueError('invalid missing-task receipt: ' + pair_id)
        existing = target_db.execute('SELECT result_sha256,record_json FROM pairs WHERE pair_id=?', (pair_id,)).fetchone()
        if existing is not None:
            if existing[0] != result_hash and not json.loads(existing[1]).get('error'):
                raise ValueError('would overwrite a different valid pair: ' + pair_id)
            if existing[0] == result_hash:
                cursor = rowid
                continue
        with target_db:
            target_db.execute('INSERT OR REPLACE INTO pairs VALUES (?,?,?,?,?,?)',
                              (pair_id, source, code, config, result_hash, payload))
        copied += 1; cursor = rowid
    return cursor, copied


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus', type=Path, default=DATA_ROOT / 'ast/run/corpus-v12-body-full')
    ap.add_argument('--output', type=Path, default=DATA_ROOT / 'ast/run/mech/labels.sqlite3')
    ap.add_argument('--journal', type=Path, default=DATA_ROOT / 'ast/run/mech/missing-v12.sqlite3')
    ap.add_argument('--workers', type=int, default=1)
    a = ap.parse_args()
    if a.workers < 1 or a.output.resolve() == a.journal.resolve():
        ap.error('positive workers and distinct journal/output required')
    a.output = a.output.resolve(); a.journal = a.journal.resolve(); a.corpus = a.corpus.resolve()
    lock = open(str(a.journal) + '.follower.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    setup(a.journal); setup(a.output)
    journal = connect(a.journal); output = connect(a.output)
    start = time.monotonic(); completed = set(); cursor = 0; copied = 0
    stopping = False; child = None
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
        if child is not None and child.poll() is None:
            child.terminate()
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    cursor, count = ingest(journal, output, cursor); copied += count
    last_report = 0
    while not stopping and len(completed) < len(TASKS):
        ready = [task for task in TASKS if task not in completed
                 and published_task(a.corpus / task)
                 and (a.corpus / task / 'pairs.jsonl.gz').is_file()
                 and (a.corpus / task / 'recoverable.jsonl.gz').is_file()]
        if ready:
            task = ready[0]
            print(f'published missing task {task}; starting resumable labeler', file=sys.stderr, flush=True)
            child = subprocess.Popen([sys.executable, '-B', str(HERE / 'run.py'), str(a.corpus), str(a.journal),
                                      '--workers', str(a.workers), '--tasks', task])
            while child.poll() is None:
                cursor, count = ingest(journal, output, cursor); copied += count
                time.sleep(1)
            cursor, count = ingest(journal, output, cursor); copied += count
            code = child.returncode; child = None
            if code != 0 and not stopping:
                raise SystemExit(f'missing task {task} failed ({code}); its durable rows remain; restart to retry')
            if code == 0:
                completed.add(task)
        else:
            time.sleep(1)
        if time.monotonic() - last_report >= 5:
            elapsed = time.monotonic() - start; rate = len(completed) / max(elapsed, .001)
            eta = f'{(len(TASKS)-len(completed))/rate:.1f}s' if rate else 'unknown'
            print(f'missing-tasks done={len(completed)}/{len(TASKS)} elapsed={elapsed:.1f}s '
                  f'rate={rate:.4f} tasks/s ETA={eta} copied_pairs={copied} '
                  f'awaiting_publication={sum(not published_task(a.corpus / task) for task in TASKS)}', file=sys.stderr, flush=True)
            last_report = time.monotonic()
    elapsed = time.monotonic() - start
    print(f'missing-tasks done={len(completed)}/{len(TASKS)} elapsed={elapsed:.1f}s '
          f'rate={len(completed)/max(elapsed,.001):.4f} tasks/s ETA=0s copied_pairs={copied}', file=sys.stderr, flush=True)
    output.close(); journal.close()
    if stopping:
        raise SystemExit(130)


if __name__ == '__main__':
    main()
