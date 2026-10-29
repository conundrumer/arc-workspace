#!/usr/bin/env python3
"""Write normal-form facts from stored streams; no replay or stored summaries."""
import argparse
from collections import defaultdict
import fcntl
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from study_paths import DATA_ROOT
import facts
import normal_policy as policy


def same_policy(previous, current):
    return (policy.dependency_identity(previous) == policy.dependency_identity(current) and
            all(previous.get(k) == current.get(k) for k in
                ('normal_policy', 'constraint_set', 'numpy', 'pandas')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=DATA_ROOT / 'ast/run/mech/labels.sqlite3')
    parser.add_argument('--output', type=Path, default=DATA_ROOT / 'ast/run/mech2/normal.sqlite3')
    parser.add_argument('--retry-unavailable', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != DATA_ROOT / 'ast/run/mech2':
        parser.error('output must be in DATA_ROOT/ast/run/mech2')
    with output.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = policy.policy_manifest(); code = facts.digest(manifest)
        base = sqlite3.connect(args.base.resolve().as_uri() + '?mode=ro', uri=True)
        db = sqlite3.connect(output)
        stop = threading.Event(); thread = None
        try:
            db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA synchronous=FULL')
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='metadata'").fetchone():
                facts.initialize(db); db.commit()
            elif db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()[0] != facts.SCHEMA:
                from compact_normal import compact
                compact(db, manifest)
            producers = {key:json.loads(text) for key, text in db.execute('SELECT * FROM producers')}
            accepted = {key for key, prior in producers.items()
                        if facts.digest(prior) == key and same_policy(prior, manifest)} | {code}
            db.execute('INSERT OR IGNORE INTO producers VALUES (?,?)', (code, facts.canonical(manifest)))
            db.commit()
            total = base.execute('SELECT count(*) FROM pairs').fetchone()[0]
            state = dict(done=0, skipped=0, phase='index')
            start = time.monotonic()
            def progress():
                elapsed = time.monotonic() - start
                rate = state['done'] / max(elapsed, .001)
                eta = (total-state['done']) / rate if rate else None
                print(f"done={state['done']}/{total} elapsed={elapsed:.1f}s rate={rate:.3f}/s "
                      f"ETA={eta if eta is not None else 'unknown'}s skipped={state['skipped']} phase={state['phase']}", flush=True)
            def heartbeat():
                while not stop.wait(5):
                    progress()
            thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
            wanted = defaultdict(dict)
            for pid, source, base_hash, text in base.execute(
                    'SELECT pair_id,source_sha256,result_sha256,record_json FROM pairs'):
                old = db.execute('SELECT * FROM pairs WHERE pair_id=?', (pid,)).fetchone()
                valid = old is not None and old[1] == source and old[2] in accepted
                if valid:
                    facts.validate('pairs', old)
                    gp = db.execute('SELECT * FROM gold_points WHERE point_id=?', (old[3],)).fetchone()
                    valid = gp is not None and gp[3] in accepted
                    if valid:
                        facts.validate('gold_points', gp)
                if valid and not (args.retry_unavailable and old[4] is None):
                    state['done'] += 1; state['skipped'] += 1
                    continue
                if args.retry_unavailable and not valid:
                    raise ValueError('retry requires a valid existing fact for ' + pid)
                record = json.loads(text)
                if (facts.digest(record) != base_hash or record['pair_id'] != pid or
                        record['source_sha256'] != source):
                    raise ValueError('invalid base row ' + pid)
                locator = record['source']; corpus = Path(locator['corpus']).resolve()
                path = corpus / record['task'] / locator['file']
                wanted[str(path)].setdefault(locator['line'], []).append(
                    dict(pair_id=pid, source_sha256=source, **{k:record[k] for k in
                         ('task', 'case', 'point', 'clause')}))
            def write(item, result):
                point = facts.digest({k:item[k] for k in ('task', 'case', 'point', 'clause')})
                prior = db.execute('SELECT * FROM gold_points WHERE point_id=?', (point,)).fetchone()
                if prior is not None and prior[3] in accepted:
                    facts.validate('gold_points', prior)
                    if (prior[4] is not None and result['gold']['normal'] is not None and
                            bool(prior[4]) != result['gold']['normal']):
                        raise ValueError('inconsistent stored gold verdict ' + point)
                if prior is None or prior[3] not in accepted or prior[4] is None:
                    facts.insert(db, 'gold_points',
                                 (point, item['pair_id'], item['source_sha256'], code), result['gold'])
                facts.insert(db, 'pairs', (item['pair_id'], item['source_sha256'], code, point), result['mutant'])
                db.commit(); state['done'] += 1
            for file, lines in sorted(wanted.items()):
                path = Path(file); state['phase'] = file
                context = None; remaining = set(lines)
                try:
                    with gzip.open(path, 'rt') as source_file:
                        for line, text in enumerate(source_file, 1):
                            if line not in remaining:
                                continue
                            source = json.loads(text); remaining.remove(line)
                            for item in lines[line]:
                                try:
                                    if (facts.digest(source) != item['source_sha256'] or
                                            facts.digest(policy.pair_key(source)) != item['pair_id']):
                                        raise ValueError('source receipt differs')
                                    if context is None:
                                        context = policy.Context(path.parent.parent, item['task'])
                                    result = context.classify(source, path.parent)
                                except Exception as error:
                                    unknown = dict(normal=None, writer_pass=None,
                                                   reason=f'{type(error).__name__}: {error}')
                                    result = dict(mutant=unknown, gold=unknown)
                                write(item, result)
                            if not remaining:
                                break
                    if remaining:
                        raise ValueError('source file ended before requested lines')
                except (OSError, EOFError) as error:
                    for line in sorted(remaining):
                        for item in lines[line]:
                            unknown = dict(normal=None, writer_pass=None,
                                           reason=f'{type(error).__name__}: {error}')
                            write(item, dict(mutant=unknown, gold=unknown))
            state['phase'] = 'complete'; progress()
        finally:
            stop.set()
            if thread is not None:
                thread.join()
            db.close(); base.close()


if __name__ == '__main__':
    main()
