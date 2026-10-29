"""Map shared evaluator receipts to mechanical grade evidence, never judge prose.

Only call this on a result returned by ReplayEvaluator.evaluate, or a result
loaded from the digest-checked candidate journal with matching source/config.
This module interprets receipt statuses; it does not execute or compare tables.
"""
from grades import CLAUSE_OUTCOMES,contributed_rows
from outcomes import canonical
import hashlib


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def clause_evidence(result, record, receipt_ref, *, purpose='answer', role='recovery', ntrain, ntest):
    return clause_evidence_from_identity(result,digest(record),len(record['evaluation']['kept_assignments']),
        receipt_ref,purpose=purpose,role=role,ntrain=ntrain,ntest=ntest)


def clause_evidence_from_identity(result,source_sha256,kept_count,receipt_ref,*,
                                  purpose='answer',role='recovery',ntrain,ntest):
    """Same adapter for compact journals that retain source identity and axes."""
    if (not isinstance(source_sha256,str) or len(source_sha256)!=64
            or type(kept_count) is not int or kept_count<0):
        raise ValueError('source identity/kept count invalid')
    if purpose not in ('answer', 'exploration'):
        raise ValueError('invalid clause purpose')
    out = dict(purpose=purpose, role=role, receipt_ref=receipt_ref,
               outcome=result.get('outcome', 'unknown'), engine_ran=result.get('engine') == 'ran',
               judgment_complete=False, tool_result_sha256=digest(result),
               target_id=result.get('target_id'))
    if purpose == 'exploration' or result.get('graded') is False:
        out.update(purpose='exploration', outcome='unknown')
        return out
    if (result.get('schema') != 'judgetool-clause-v2'
            or result.get('source_sha256') != source_sha256
            or result.get('route') != 'replay_search_then_kept_filter'
            or out['outcome'] not in CLAUSE_OUTCOMES):
        out.update(outcome='unknown', reason='tool source/route/schema binding incomplete')
        return out
    contexts = result.get('context_receipt', {})
    required = kept_count * (ntrain + ntest)
    full = (required > 0 and contexts.get('complete') is True
            and contexts.get('required') == required
            and not result.get('missing_contexts'))
    checks = result.get('checks', {})
    target = result.get('target_receipt', {})
    check = dict(train=checks.get('train') == 'equal', test=checks.get('test') == 'equal',
                 complete=checks.get('complete') is True,
                 kept_contexts_complete=full,
                 test_target=checks.get('test_target'), receipt_ref=receipt_ref,required_train_test_contexts=required)
    # Fresh target receipts bind the original record, schema and exact train axis.
    if target.get('source') == 'gold_full_replay' and target.get('observer_program_sha256'):
        full = (full and target.get('original_source_sha256') == source_sha256
                and target.get('train_complete') is True
                and target.get('test_complete') is True)
        check['kept_contexts_complete'] = full
    elif target.get('source') == 'gold_full_replay':
        full = (full and target.get('complete') is True and bool(target.get('native_ref'))
                and target.get('target_id') == result.get('target_id'))
        check['kept_contexts_complete'] = full
    positive_check = (full and check['train'] and check['test'] and check['complete']
                      and check['test_target'] == 'gold_full_replay'
                      and result.get('verified') is True and bool(target))
    provenance = result.get('provenance', {})
    status = provenance.get('status')
    out['check'] = check
    if out['outcome'] == 'recovery verified':
        direct = status == 'direct_X' and provenance.get('restrictions_only') is True
        single = (status == 'single_row_lib' and provenance.get('one_row_per_X') is True
                  and provenance.get('restrictions_only') is True)
        union = (status == 'union_X_contributes' and provenance.get('needed_rows') is True
                 and provenance.get('redundant') is False
                 and provenance.get('one_row_per_X') is True
                 and provenance.get('restrictions_only') is True)
        out['provenance'] = dict(target_columns='X_or_single_row_lib_from_X',
            lib_single_row_per_X=direct or single or union,
            restrictions_only=direct or single or union,
            union=status == 'union_X_contributes',
            X_supplies_needed_rows=union, X_nonredundant=union)
        if not (positive_check and (direct or single or union)):
            out.update(outcome='unknown', reason='target test/context or X-row provenance proof incomplete')
    elif out['outcome'] == 'partial source verified':
        contributes = contributed_rows(provenance,required)
        out['provenance'] = dict(partial_source=status == 'partial',
                                 X_contributes_rows=contributes,row_contribution=provenance.get('row_contribution',{}))
        if not (positive_check and status == 'partial' and contributes):
            out.update(outcome='unknown', reason='partial source target check or actual X-row contribution incomplete')
    elif out['outcome'] == 'continuation passed':
        if not (full and result.get('continuation_passed') is True):
            out.update(outcome='unknown', reason='continuation context check incomplete')
    # Candidate refusal is never mutant program refusal. Unknown is not a
    # completed negative answer; exploratory calls never count as answers.
    out['judgment_complete'] = (out['outcome'] != 'unknown'
                                and (full or out['outcome'] == 'refused by the engine'))
    return out
