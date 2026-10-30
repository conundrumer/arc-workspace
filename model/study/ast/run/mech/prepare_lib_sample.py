#!/usr/bin/env python3
"""Prepare authenticated no-witness requests; performs no search or relabeling."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

from outcomes import second_pass_eligible
from run import canonical, digest

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--database', type=Path, default=DATA_ROOT / 'ast/run/mech/labels.sqlite3')
    ap.add_argument('--output', type=Path, default=DATA_ROOT / 'ast/run/mech/lib-sample-requests.jsonl')
    ap.add_argument('--limit', type=int, default=128)
    a = ap.parse_args()
    if a.limit < 1 or a.output.resolve() == a.database.resolve():
        ap.error('positive limit and distinct output required')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(a.database.resolve().as_uri() + '?mode=ro', uri=True)
    db.execute('BEGIN')
    total = db.execute('SELECT count(*) FROM pairs').fetchone()[0]
    start = time.monotonic(); last = 0; scanned = 0; groups = {}; eligible = 0
    for producer_hash, payload in db.execute('SELECT result_sha256,record_json FROM pairs ORDER BY pair_id'):
        record = json.loads(payload); scanned += 1
        if digest(record) != producer_hash:
            raise ValueError('producer result integrity mismatch: ' + record.get('pair_id', '<missing>'))
        if second_pass_eligible(record):
            bounded = any(item.get('witness', {}).get('reason_code') == 'search_bound'
                          for item in record.get('per_assignment', []))
            key = (record['label'], record['operation'], 'bound' if bounded else 'not_found')
            group = groups.setdefault(key, dict(first={}, extra=[], count=0))
            group['count'] += 1; eligible += 1
            slim = {field: record[field] for field in ('pair_id', 'pool_pair_id', 'source', 'source_sha256',
                    'code_sha256', 'config_sha256', 'task', 'label', 'operation')}
            value = slim, producer_hash
            if record['task'] not in group['first'] and len(group['first']) < a.limit:
                group['first'][record['task']] = value
            elif len(group['extra']) < a.limit:
                group['extra'].append(value)
        elapsed = time.monotonic() - start
        if elapsed - last >= 5:
            rate = scanned / max(elapsed, .001)
            print(f'scan done={scanned}/{total} elapsed={elapsed:.1f}s rate={rate:.1f}/s '
                  f'ETA={(total-scanned)/rate:.1f}s eligible={eligible}', file=sys.stderr, flush=True)
            last = elapsed
    db.close()
    # Deterministic round-robin across label/operation/bound strata, with one
    # pair per task early in each stratum to avoid a single task dominating.
    counts = {key: group['count'] for key, group in groups.items()}
    groups = {key: list(group['first'].values()) + group['extra'] for key, group in groups.items()}
    selected = []; offset = 0
    while len(selected) < a.limit:
        added = False
        for key in sorted(groups):
            if offset < len(groups[key]):
                selected.append((key, groups[key][offset])); added = True
                if len(selected) == a.limit: break
        if not added: break
        offset += 1
    config = dict(schema='mech-lib-sample-selection-v1', limit=a.limit,
                  source_filter='legacy shortlist only; no fits/lossy/extension/DET; overapproximation or bounded; settled support must be rechecked',
                  selection='deterministic task-diverse round robin by label/operation/bound')
    with a.output.open('w') as out:
        for stratum, (record, producer_hash) in selected:
            source = record['source']
            request = dict(schema='mech-source-v1',
                           corpus=str(Path(source['corpus']).resolve()),
                           file=record['task'] + '/' + source['file'],
                           line=source['line'], source_sha256=record['source_sha256'],
                           mechanical_pair_id=record['pair_id'], pool_pair_id=record['pool_pair_id'],
                           prior_result_ref=dict(database=str(a.database.resolve()),
                               mechanical_pair_id=record['pair_id'], result_sha256=producer_hash))
            out.write(canonical(dict(schema='mech-lib-sample-request-v2', source=request,
                                     prior_label=record['label'], operation=record['operation'],
                                     stratum=stratum, selection_config_sha256=digest(config))) + '\n')
    elapsed = time.monotonic() - start
    summary = dict(schema='mech-lib-sample-selection-v1', config=config, config_sha256=digest(config),
                   selector_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   scanned=scanned, eligible=eligible, selected=len(selected), elapsed_seconds=elapsed,
                   strata=[dict(label=key[0], operation=key[1], kind=key[2], eligible=counts[key])
                           for key in sorted(groups)],
                   status='prepared_only; shared evaluator target adapter pending; no gains/bounds/time inferred')
    a.output.with_suffix('.summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f'prepare done={len(selected)}/{len(selected)} elapsed={elapsed:.1f}s '
          f'rate={len(selected)/max(elapsed,.001):.2f}/s ETA=0s eligible={eligible}', file=sys.stderr, flush=True)


if __name__ == '__main__':
    main()
