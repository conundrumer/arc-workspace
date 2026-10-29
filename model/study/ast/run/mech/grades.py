"""Settled grade policy over checked evidence; contains no replay or comparator.

Input is mech-grade-evidence-v1, produced by an authenticated evidence adapter.
Legacy producer labels/witnesses alone are deliberately insufficient positives.
See README for the contract. This function does not authenticate caller evidence.
"""
SCHEMA = 'mech-grade-evidence-v1'
CLAUSE_OUTCOMES = {'recovery verified', 'partial source verified',
                   'continuation passed', 'refused by the engine',
                   'did not verify', 'unknown'}


def checked(check):
    """Complete train+test target check, with full replay as test authority."""
    return (isinstance(check, dict) and check.get('train') is True
            and check.get('test') is True and check.get('complete') is True
            and check.get('kept_contexts_complete') is True
            and check.get('test_target') == 'gold_full_replay'
            and bool(check.get('receipt_ref')))


def contributed_rows(provenance,required):
    """An actual native successful-path receipt, never syntactic X presence."""
    proof=provenance.get('row_contribution',{})
    return (provenance.get('X_contributes_rows') is True
            and proof.get('complete') is True and proof.get('X_contributes_rows') is True
            and proof.get('source')=='original_complete_native_candidate_replay'
            and bool(proof.get('artifact')) and bool(proof.get('nonempty_contexts'))
            and type(required) is int and required>0
            and proof.get('required_train_test_contexts')==required)


def reduce_grade(evidence):
    if evidence.get('schema') != SCHEMA:
        raise ValueError('expected ' + SCHEMA)
    clauses = evidence.get('clauses', [])
    for clause in clauses:
        if clause.get('outcome') not in CLAUSE_OUTCOMES:
            raise ValueError('unknown clause outcome')
    # Exploration is never an answer and never establishes that a judge ran.
    answers = [c for c in clauses if c.get('purpose') == 'answer']
    continuations = [c['outcome'] for c in answers
                     if c.get('role') == 'continuation' or c.get('mode') == 'alternative'
                     or c['outcome'] == 'continuation passed']
    attributes = {key: evidence.get(key) for key in ('redundant', 'sibling')}
    attributes['continuation'] = continuations or None
    program = evidence.get('program', {})
    is_det = evidence.get('kind','').upper() == 'DET'
    target = evidence.get('target_catalog', {})
    catalog_complete = target.get('complete') is True and bool(target.get('receipt_ref'))
    comparisons = evidence.get('comparisons', {})
    point = comparisons.get('point', {})
    empty = comparisons.get('X_empty', {})
    # An authenticated global-empty certificate is a filter result, even if
    # OUT fits or an unrelated union branch reproduces a target. No successful
    # path can supply an X row when every kept train/test model is empty.
    if (empty.get('empty') is True and empty.get('complete') is True
            and empty.get('train') is True and empty.get('test') is True
            and empty.get('kept_contexts_complete') is True
            and bool(empty.get('receipt_ref'))):
        return dict(grade='empty', grade_reason='X is empty in every kept train/test model',
                    attributes=attributes, filter_class='empty', missing_steps=[])
    if empty and empty.get('complete') is not True:
        return dict(grade='Unknown',grade_reason='original X filter evidence incomplete',
                    attributes=attributes,filter_class=None,missing_steps=list(evidence.get('missing_steps',[])))
    # Every positive target check must cover train/test; grade order is explicit.
    equal = [c for c in comparisons.get('targets', []) if checked(c) and c.get('equal') is True]
    if equal:
        grade, reason = 'equivalent', 'complete target equality on train and test'
    else:
        recovery = []
        partial = []
        for c in answers + evidence.get('mechanical_clauses', []):
            if not checked(c.get('check')):
                continue
            provenance = c.get('provenance', {})
            if c.get('outcome') == 'recovery verified':
                from_x = (provenance.get('target_columns') == 'X_or_single_row_lib_from_X'
                          and provenance.get('lib_single_row_per_X') is True
                          and provenance.get('restrictions_only') is True)
                union_ok = (not provenance.get('union') or
                            (provenance.get('X_supplies_needed_rows') is True
                             and provenance.get('X_nonredundant') is True))
                if from_x and union_ok:
                    recovery.append(c)
            elif (c.get('outcome') == 'partial source verified'
                  and provenance.get('partial_source') is True
                  and contributed_rows(provenance,c['check'].get('required_train_test_contexts'))):
                partial.append(c)
        if recovery:
            grade, reason = 'Recovery', 'verified target and admitted X provenance'
        elif partial:
            grade, reason = 'Partial source', 'verified target with an actual X-contributing path'
        elif (not is_det and program.get('fits_train') is True and program.get('fits_test') is True
              and program.get('complete') is True and program.get('receipt_ref')):
            read = comparisons.get('reader_difference', {})
            if (read.get('complete') is True and read.get('receipt_ref')
                    and read.get('read_difference') in (True, False)):
                grade = 'fits' if read['read_difference'] else 'extension'
                reason = 'program fits train/test; reader-visible difference checked'
                attributes['continuation'] = 'mutant program fits'
            else:
                grade, reason = 'Unknown', 'reader-visible difference incomplete'
        elif program.get('refused') is True and program.get('receipt_ref'):
            grade, reason = 'Refused', 'mutant program refused by engine'
        else:
            nonfit = (is_det or (program.get('complete') is True and bool(program.get('receipt_ref'))
                      and (program.get('fits_train') is False or program.get('fits_test') is False)))
            # Lossy needs the settled projected point comparison, never a legacy
            # label against a different body/target or an incomplete family.
            support = comparisons.get('recovery_support', {})
            lossy = (catalog_complete and support.get('complete') is True
                     and bool(support.get('receipt_ref'))
                     and support.get('all_targets_lossy') is True)
            search = evidence.get('search', {})
            exhausted = (catalog_complete and search.get('status') == 'covered_space_no_recovery'
                         and search.get('complete') is True and search.get('unvisited') == 0
                         and search.get('settled_space') is True and bool(search.get('receipt_ref')))
            judge_run = evidence.get('judge_run', {})
            judge_ran = ((judge_run.get('complete') is True
                          and judge_run.get('answered') is True
                          and bool(judge_run.get('receipt_ref')))
                         or any(c.get('engine_ran') is True
                                and c.get('judgment_complete') is True
                                and c.get('outcome') != 'unknown'
                                and c.get('receipt_ref') for c in answers))
            # Do not interpret an unconsumed positive tool claim as a negative.
            unvalidated_positive = any(c.get('outcome') in
                                      ('recovery verified', 'partial source verified')
                                      for c in answers + evidence.get('mechanical_clauses', []))
            if lossy:
                grade, reason = 'Reject', 'complete mechanical lossy comparison against every target'
            elif nonfit and (exhausted or (judge_ran and not unvalidated_positive)):
                grade, reason = 'Reject', 'non-fit and exhausted search or judge ran without verified recovery/partial source'
            else:
                grade, reason = 'Unknown', 'missing, bounded or incomplete settled evidence'
    missing_steps = list(evidence.get('missing_steps', [])) if grade == 'Unknown' else []
    if missing_steps:
        reason += '; owed: ' + ', '.join(missing_steps)
    return dict(grade=grade, grade_reason=reason, attributes=attributes,
                filter_class=evidence.get('filter_class'), missing_steps=missing_steps)


def judge_eligible(evidence):
    """Final admission, never inferred from legacy labels alone."""
    program = evidence.get('program', {})
    if (evidence.get('kind', '').upper() == 'DET'
            or (program.get('fits_train') is True and program.get('fits_test') is True)
            or reduce_grade(evidence)['grade'] != 'Unknown'):
        return False
    point = evidence.get('comparisons', {}).get('point', {})
    support = evidence.get('comparisons', {}).get('recovery_support', {})
    search = evidence.get('search', {})
    possible = ((point.get('complete') is True and bool(point.get('receipt_ref'))
                 and point.get('X_holds_every_gold_row') is True)
                or (support.get('any_target_contains') is True and bool(support.get('receipt_ref'))))
    return (possible
            and support.get('all_targets_lossy') is not True
            and program.get('complete') is True and bool(program.get('receipt_ref'))
            and (program.get('fits_train') is False or program.get('fits_test') is False)
            and search.get('status') in ('bound_unknown', 'not_covered')
            and bool(search.get('receipt_ref')))
