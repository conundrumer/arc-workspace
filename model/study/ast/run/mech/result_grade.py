"""The public pure grade function over pass results; no stores or evaluation.

Arguments are authenticated results loaded by read_grades. Optional pass inputs
are load-result envelopes (valid/record/reference); absent or stale evidence is
not a negative. No grade or joined evidence is persisted.
"""
from copy import deepcopy
from run import digest
from step1_reduce import adapt
from witness_test import train_witness,stored_result
from grades import reduce_grade,judge_eligible


def grade_results(base,*,witness_tests=(),fit_split=None,lib_search=None,
                  target_comparison=None,judge_outcomes=(),base_reference=None,program_result=None):
    ref=base_reference or dict(result_sha256=digest(base))
    evidence=adapt(base,ref)
    items=[i for i in base.get('per_assignment',[]) if train_witness(i)]
    tests={r['assignment']:r for r in witness_tests}
    checks=[]
    for item in items:
        value=tests.get(item['assignment'])
        if value is None:
            stored,origin=stored_result(base,item)
            value=dict(test_verified=stored,origin=origin)
        checks.append(value)
    if items and all(type(c.get('test_verified')) is bool for c in checks):
        evidence['missing_steps']=[s for s in evidence['missing_steps'] if s!='step_2_witness_test_check']
    if (not base.get('error') and items and len(items)==len(base['per_assignment'])
            and sorted(i['assignment'] for i in items)==list(range(len(items)))
            and all(c.get('test_verified') is True for c in checks)):
        ordinary=(str(base['kind']).lower()=='rule'
                  and all(len(i['witness'].get('selection_any',[]))<=1 for i in items))
        if ordinary and base.get('label')!='equivalent':
            evidence['mechanical_clauses'].append(dict(outcome='recovery verified',purpose='answer',
                check=dict(train=True,test=True,complete=True,kept_contexts_complete=True,
                           test_target='gold_full_replay',receipt_ref=[c.get('reference',ref) for c in checks]),
                provenance=dict(target_columns='X_or_single_row_lib_from_X',lib_single_row_per_X=True,
                                restrictions_only=True,union=False)))
        elif not ordinary:evidence['missing_steps'].append('step_3_point_projection_and_witness_admission')
    if target_comparison and target_comparison.get('_source_error'):
        evidence['comparisons']['X_empty']=dict(complete=False)
        evidence['missing_steps'].append('step_3_original_X_filter_evidence')
    if target_comparison and target_comparison.get('_source_groups') is not None:
        groups=target_comparison['_source_groups'];required=set(groups.get('required',()))
        families=groups.get('groups',{})
        complete=(bool(required) and not groups.get('missing') and set(families)==required
                  and all(families.values()) and {k[1] for k in required}>={1,2})
        evidence['comparisons']['X_empty']=dict(complete=complete,
            empty=all(not rows for family in families.values() for rows in family) if complete else None,
            train=complete,test=complete,kept_contexts_complete=complete,
            receipt_ref=dict(source_sha256=base['source_sha256'],base_reference=ref,table='original mutant_kept'))
    if target_comparison and target_comparison.get('valid') is True:
        from mech5.evidence import apply_targets
        evidence=apply_targets(evidence,target_comparison)
    if fit_split and fit_split.get('valid') is True:
        result=fit_split['record'];reference=fit_split['reference']
        if 'program' in result:  # legacy reader result
            evidence['program']=dict(deepcopy(result['program']),receipt_ref=reference)
            read=deepcopy(result['reader_difference'])
        else:
            program=dict(evidence['program']);program['fits_test']=result.get('fits_test')
            program['complete']=all(type(program.get(k)) is bool for k in ('fits_train','fits_test'))
            program['receipt_ref']=reference;evidence['program']=program
            difference=result.get('read_difference')
            read=dict(read_difference=difference,complete=type(difference) is bool)
        evidence['comparisons']['reader_difference']=dict(read,receipt_ref=reference)
        evidence['missing_steps']=[s for s in evidence['missing_steps'] if not s.startswith('step_4_')]
        if not evidence['program'].get('complete'):evidence['missing_steps'].append('step_4_test_program_fit_proof')
        if not read.get('complete'):evidence['missing_steps'].append('step_4_reader_projection_or_rows')
    if lib_search and lib_search.get('valid') is True:
        evidence['mechanical_clauses'].extend(deepcopy(lib_search.get('mechanical_clauses',[])))
        # A bounded finite library pass supplies no exhaustive negative.
    if (program_result and program_result.get('valid') is True
            and program_result.get('pair_id')==base['pair_id']
            and program_result.get('source_sha256')==base['source_sha256']):
        evidence['program'].update({k:deepcopy(program_result[k]) for k in
            ('fits_train','train_nonfit_complete','train_nonfit_receipt') if k in program_result})
    for judge in judge_outcomes:
        evidence['clauses'].extend(deepcopy(judge.get('clauses',[])))
        if judge.get('judge_run'):evidence['judge_run']=deepcopy(judge['judge_run'])
    result=reduce_grade(evidence)
    return dict(result,judge_eligible=judge_eligible(evidence),evidence=evidence)
