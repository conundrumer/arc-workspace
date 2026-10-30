"""Mechanical caller for the tool's ONE fresh gold observer acquisition.

No native evaluator, projector, train comparator or INIT expansion lives here.
Returned groups contain private test data: never send them to judge documents.
"""
from pathlib import Path
import sys
import time

from outcomes import canonical
import hashlib

STUDY = Path(__file__).resolve().parents[3]


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def acquire_main_target(ev, record, metadata, *, ntrain, ntest):
    """Use shared observe_gold, returning private groups plus a receipt.

    `metadata` comes from load_review_metadata. This is target DATA acquisition,
    not target-catalog completeness, pair admission, or a recovery claim.
    Caller uses the same ReplayEvaluator instance as its candidate replays.
    Failures are unknown and cannot become a source-row absence proof.
    """
    start = time.monotonic()
    result = dict(schema='mech-target-acquisition-v1', status='unknown',
                  source_sha256=digest(record), target='main_G',
                  target_catalog_complete=False, admission_authenticated=False)
    try:
        if metadata.get('source_sha256') != result['source_sha256']:
            raise ValueError('review metadata source differs')
        if ntrain < 1 or ntest < 0:
            raise ValueError('invalid expected train/test input counts')
        adapter = metadata['adapter']
        binding = adapter['comparison_target']['binding']
        # Shared tool modules currently use local imports. Match its documented
        # import environment without importing a second copy of its source.
        tool = STUDY / 'judgetool'
        if str(tool) not in sys.path:
            sys.path.insert(0, str(tool))
        from checks import observe_gold
        groups, shared_receipt = observe_gold(ev, record, adapter, binding, ntrain, ntest)
        if (shared_receipt.get('source') != 'gold_full_replay'
                or shared_receipt.get('train_complete') is not True
                or shared_receipt.get('test_complete') is not True
                or not shared_receipt.get('artifact') or groups.get('missing')):
            raise ValueError('fresh observer train/test evidence incomplete')
        # Fresh replay is target authority. Saved projected train snapshots are
        # not a comparison/gate; completeness is checked on the fresh axes.
        expected_hashes = dict(
            original_source_sha256=result['source_sha256'],
            gold_program_sha256=digest(record['gold_sexp']),
            kept_context_sha256=digest(record['evaluation']['kept_assignments']),
            layout_sha256=digest(binding['projected_schema']))
        for name, expected in expected_hashes.items():
            if shared_receipt.get(name) != expected:
                raise ValueError('shared observer receipt binding differs: ' + name)
        nassign = len(record['evaluation']['kept_assignments'])
        expected_axis = {(a,kind,i) for a in range(nassign)
                         for kind,count in ((1,ntrain),(2,ntest)) for i in range(count)}
        if not expected_axis or groups.get('required') != expected_axis:
            raise ValueError('shared observer required input axis differs')
        if not shared_receipt.get('observer_program_sha256'):
            raise ValueError('shared observer program identity missing')
        receipt = dict(schema='mech-fresh-gold-target-receipt-v1',
                       acquisition='shared_replay_program_gold_projected_body_observer',
                       original_source_sha256=result['source_sha256'],
                       original_gold_program_sha256=digest(record['gold_sexp']),
                       kept_context_sha256=digest(record['evaluation']['kept_assignments']),
                       layout_sha256=expected_hashes['layout_sha256'],
                       binding_sha256=digest(binding),
                       metadata_manifest_ref=metadata['manifest_ref'],
                       expected_inputs=dict(train=ntrain, test=ntest),
                       shared_receipt=shared_receipt,
                       artifact=shared_receipt['artifact'],
                       test_target='gold_full_replay',
                       authority='fresh replay; not a stored corpus native reference')
        result.update(status='acquired', receipt=receipt, receipt_sha256=digest(receipt))
    except Exception as error:
        result.update(reason=str(error), error_type=type(error).__name__)
        groups = None
    result['seconds'] = time.monotonic()-start
    return groups, result
