"""Normalize legacy mechanical diagnostics without changing producer records."""
import hashlib
import json

OUTCOMES = {
    'recovery_verified': 'recovery verified',
    'covered_space_no_recovery': 'search covered the space and found none',
    'bound_unknown': 'search stopped at its bound',
    'unavailable': 'search evidence unavailable',
}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def normalize(record, producer_result_sha256):
    out = dict(record)
    old = record.get('search')
    assignments = record.get('per_assignment', [])
    proofs = [item.get('witness', {}) for item in assignments]
    verified = (not record.get('error') and bool(proofs)
                and all(proof.get('recoverable') is True and proof.get('verified') is True for proof in proofs))
    negatives = [proof for proof in proofs if proof.get('status') == 'determined'
                 and proof.get('recoverable') is False and proof.get('nonrecoverable_proof')]
    bounds = [proof for proof in proofs if proof.get('status') == 'unknown'
              and proof.get('reason_code') == 'search_bound']
    if verified:
        status = 'recovery_verified'
        scope = 'saved verified train witness under each full kept assignment'
    elif negatives and not record.get('error'):
        status = 'covered_space_no_recovery'
        scope = 'structural impossibility of a row-restricting typed projection; independent of restriction grammar'
    elif bounds and not record.get('error'):
        status = 'bound_unknown'
        scope = 'configured bounded mechanical grammar; no absence proof'
    else:
        status = 'unavailable'
        scope = 'missing or incomplete evidence; neither bound nor absence inferred'
    out.update(export_schema='mech-export-v2', legacy_search=old,
               legacy_rerun=record.get('rerun'), search=status, rerun=status,
               search_outcome=OUTCOMES[status], search_scope=scope,
               memorized=(old == 'WRONG/memorized'), no_signal=(old == 'WRONG/no_signal'),
               projection_only=bool(proofs) and all(item.get('shape') == 'projection-only' for item in assignments),
               producer_result_sha256=producer_result_sha256)
    return out


def second_pass_eligible(record):
    """Legacy candidate shortlist ONLY; final admission uses grades.judge_eligible.

    This never establishes row support for the settled target projection.
    """
    if record.get('error') or record.get('selection_found') is True or record.get('label') in ('lossy', 'fits', 'extension') or record.get('kind') == 'DET':
        return False
    proofs = [item.get('witness', {}) for item in record.get('per_assignment', [])]
    # These necessary source-row/family/projection conditions do not depend on
    # whether selectors are comparisons, joins, library predicates or NOT.
    if any(proof.get('recoverable') is False and proof.get('nonrecoverable_proof') for proof in proofs):
        return False
    bounded = any(proof.get('reason_code') == 'search_bound' for proof in proofs)
    return record.get('label') == 'overapproximation' or bounded
