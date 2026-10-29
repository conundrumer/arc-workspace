"""Consume judge3 review metadata, without granting admission or coverage.

Uses the shared tool source loader. All projection, graph and equality work
stays with judgetool/ and judge3/; no native rows are compared here.
"""
import hashlib
import json
from pathlib import Path
import sys

from outcomes import canonical

STUDY = Path(__file__).resolve().parents[3]


def load_review_metadata(manifest_path, record):
    """Bind review metadata to an exact decoded source record.

    Hash validation establishes source content agreement only. It does NOT
    authenticate native target identities, comparison coverage or admission.
    The renderer's record_sha256 hashes the raw JSONL line, a different digest
    from the mechanical canonical source hash. Do not compare those digests.
    """
    sys.path.insert(0, str(STUDY))
    from judgetool.evaluator import open_source
    path = Path(manifest_path).resolve()
    raw = path.read_bytes()
    manifest = json.loads(raw)
    adapter = manifest['adapter']
    if adapter.get('schema') != 'judge3-review-evidence-v3' or adapter.get('review_only') is not True:
        raise ValueError('expected review-only judge3-review-evidence-v3')
    digest = hashlib.sha256(canonical(record).encode()).hexdigest()
    source, source_receipt = open_source(adapter['source']['record_path'], expected_sha256=digest)
    if source['task'] != manifest['task'] or source['case'] != manifest['case']:
        raise ValueError('review manifest task/case differs from source')
    full = adapter['comparison_target'].get('full_replay_body')
    issues = ['review-only metadata: no authenticated mechanical/native admission receipt',
              'target catalog incomplete: all other-case native tables not yet qualified',
              'target catalog incomplete: omitted ports unresolved',
              'stored full-replay point BODY absent in v11; fresh shared observer needed']
    if not full:
        issues.append('stored gold full-replay body reference unavailable; fresh shared observer required')
    return dict(schema='mech-review-metadata-v1',
                source_sha256=digest, source_receipt=source_receipt,
                manifest_ref=dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest()),
                input=adapter['input'], comparison_target=adapter['comparison_target'],
                availability=adapter.get('availability'),
                comparison_tables=adapter.get('alternative', {}).get('comparison_tables', []),
                all_case_targets=adapter.get('all_case_targets'),
                target_catalog=dict(complete=False, receipt_ref=None, issues=issues),
                admission=dict(status='unavailable', authenticated=False),
                # Preserve the adapter, including scopes/keys/program receipts;
                # downstream shared tool consumes it without reconstructing policy.
                adapter=adapter)
