"""Compare replay statuses by exact record identity, excluding Deadline shifts."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys


TYPES = {'pair', 'historical_refusal', 'gold_relations', 'native_stream_gold', 'case', 'task_fault'}


def load(path):
    records, digest, summary = {}, hashlib.sha256(), None
    with path.open('rb') as source:
        for number, line in enumerate(source, 1):
            digest.update(line)
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f'{path}:{number}: incomplete or malformed replay') from exc
            kind = row.get('type')
            if kind == 'summary':
                summary = row
            if kind not in TYPES:
                continue
            identity = row.get('identity') if kind in ('pair', 'historical_refusal') else None
            key = (kind, row['task'], row.get('case'), json.dumps(identity, sort_keys=True))
            if key in records:
                raise ValueError(f'{path}:{number}: duplicate replay identity')
            records[key] = dict(line=number, type=kind, task=row['task'], case=row.get('case'),
                                identity=identity, status=row.get('status'), reason=row.get('reason'),
                                gold_fits=(row.get('evaluation') or {}).get('gold_fits') if kind == 'pair' else None)
    return records, dict(path=str(path.resolve()), sha256=digest.hexdigest(), summary=summary)


def outcome(record):
    return record['status'], record['reason'], record['gold_fits']


def deadline_shift(old, new):
    # A timed-out side cannot establish the untimed outcome: it may mask any
    # work/memory stop, and may leave gold FITS unavailable. Faults remain
    # actionable even if their message happens to mention Deadline.
    return (old['status'] != 'fault' and new['status'] != 'fault'
            and any(r['status'] == 'stopped' and 'Deadline' in str(r['reason']) for r in (old, new)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('old', type=Path)
    parser.add_argument('new', type=Path)
    parser.add_argument('--output', type=Path, help='write exact identities, line references and input hashes as JSON')
    args = parser.parse_args()
    a, old_receipt = load(args.old)
    b, new_receipt = load(args.new)
    common = a.keys() & b.keys()
    changes, deadlines = [], []
    for key in sorted(common):
        if outcome(a[key]) == outcome(b[key]):
            continue
        item = dict(old=a[key], new=b[key])
        (deadlines if deadline_shift(a[key], b[key]) else changes).append(item)
    # Missing rows are never silently discarded: a case fault can abort the
    # rest of that case's identities, including records with no Deadline.
    only_old = [a[key] for key in sorted(a.keys() - b.keys())]
    only_new = [b[key] for key in sorted(b.keys() - a.keys())]
    report = dict(old=old_receipt, new=new_receipt, common=len(common),
                  changed=len(changes), deadline_shifts_excluded=len(deadlines),
                  only_old=len(only_old), only_new=len(only_new),
                  changes=changes, missing_from_new=only_old, added_in_new=only_new,
                  deadline_shifts=deadlines)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'common={len(common)} changed={len(changes)} deadline_shifts_excluded={len(deadlines)} only_old={len(only_old)} only_new={len(only_new)}')
    moves = Counter((item['old']['type'], outcome(item['old']), outcome(item['new'])) for item in changes)
    for move, count in moves.most_common():
        print(count, move)
    for item in changes:
        print(json.dumps(dict(type='change', **item), sort_keys=True))
    for label, records in [('missing_from_new', only_old), ('added_in_new', only_new)]:
        for record in records:
            print(json.dumps(dict(type=label, record=record), sort_keys=True))
    print('sha256', old_receipt['sha256'], new_receipt['sha256'])


if __name__ == '__main__':
    try:
        main()
        sys.stdout.flush()
    except BrokenPipeError:
        # A downstream reader such as head can finish before this report.
        # Redirect the final interpreter flush to an open stream as well.
        with open(os.devnull, 'w') as sink:
            os.dup2(sink.fileno(), sys.stdout.fileno())
