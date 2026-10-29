#!/usr/bin/env python3
"""Export a consistent SQLite snapshot as one JSON line per pair."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
from outcomes import canonical, normalize


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('database', type=Path); ap.add_argument('jsonl', type=Path)
    a = ap.parse_args()
    if a.database.resolve() == a.jsonl.resolve():
        ap.error('output must differ from database')
    db = sqlite3.connect(a.database.resolve().as_uri() + '?mode=ro', uri=True)
    db.execute('BEGIN')
    total = db.execute('SELECT count(*) FROM pairs').fetchone()[0]
    started = time.monotonic(); last = 0; done = 0
    with a.jsonl.open('w') as out:
        exporter = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        normalizer = hashlib.sha256((Path(__file__).parent / 'outcomes.py').read_bytes()).hexdigest()
        for payload, producer_hash in db.execute('SELECT record_json, result_sha256 FROM pairs ORDER BY pair_id'):
            record = json.loads(payload)
            if hashlib.sha256(canonical(record).encode()).hexdigest() != producer_hash:
                raise ValueError('producer result integrity mismatch: ' + record.get('pair_id', '<missing>'))
            normalized = normalize(record, producer_hash)
            normalized.update(exporter_sha256=exporter, normalizer_sha256=normalizer)
            normalized['export_sha256'] = hashlib.sha256(canonical(normalized).encode()).hexdigest()
            out.write(canonical(normalized) + '\n'); done += 1
            elapsed = time.monotonic() - started
            if elapsed - last >= 5:
                print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={done/elapsed:.2f}/s '
                      f'ETA={(total-done)*elapsed/done:.1f}s', file=sys.stderr, flush=True)
                last = elapsed
    elapsed = time.monotonic() - started
    print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={done/max(elapsed,.001):.2f}/s ETA=0s',
          file=sys.stderr, flush=True)
    db.close()


if __name__ == '__main__':
    main()
