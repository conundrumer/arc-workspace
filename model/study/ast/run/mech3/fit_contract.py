"""Stored native program fit evidence, and a pure Step 4 grade overlay.

Stored native verdicts are reused. Missing TEST evidence is acquired by the
shared whole-program evaluator in the caller, with gold's full replay as truth.
No evaluator is implemented here.
"""
from copy import deepcopy
from grades import reduce_grade


def stored_program_fit(record,ntrain,ntest):
    if record.get('kind','').upper()=='DET':
        return dict(fits_train=None,fits_test=None,complete=False,receipt_ref=None,
                    applicable=False,table_only=True,
                    reason='OUT holds gold DET values; mutant DET program fit is not evidence',missing=[])
    outputs=record['evaluation'].get('outputs',[])
    count=len(record['evaluation']['kept_assignments'])
    result=dict(fits_train=None,fits_test=None,complete=False,receipt_ref=None,
                authority='stored native accepted-output verdicts',missing=[])
    if (not count or len(outputs)!=count or {o.get('assignment') for o in outputs}!=set(range(count))):
        result['missing'].append('stored native output coverage of kept assignments');return result
    for section,size,name in (('train',ntrain,'fits_train'),('test',ntest,'fits_test')):
        flags=[];valid=size>0
        for output in outputs:
            mutant=output.get('mutant',{});values=mutant.get(section,[])
            if (mutant.get('status')!='complete' or len(values)!=size
                    or {v.get('example') for v in values}!=set(range(size))):valid=False;continue
            for value in values:
                if (type(value.get('fits')) is not bool
                        or value.get('fit_comparison')!='native_closed_candidate_set'):
                    valid=False;continue
                if section=='test':
                    grids=value.get('distinct_output_grids')
                    defined=value.get('output_set_defined')
                    if type(grids) is not int or grids<0 or type(defined) is not bool:
                        valid=False;continue
                    if value['fits'] and (not defined or not 1<=grids<=2):
                        valid=False;continue
                flags.append(value['fits'])
        if valid and len(flags)==count*size:result[name]=all(flags)
        else:result['missing'].append('complete stored native '+section+' accepted-output verdict')
    result['complete']=all(type(result[k]) is bool for k in ('fits_train','fits_test'))
    return result


def apply(evidence,result,reference):
    """Merge only the Step 4 evidence; n-mech's one reducer sets the grade.

    Caller must validate load_step4 before applying this patch. Stronger grades
    remain governed by the same reducer. This function never writes a database.
    """
    out=deepcopy(evidence)
    if out['pair_id']!=result['pair_id'] or out['source_sha256']!=result['source_sha256']:
        raise ValueError('step 4 source/pair differs')
    if out['base_result_ref']['result_sha256']!=result['base_result_sha256']:
        raise ValueError('step 4 base receipt differs')
    program=deepcopy(result['program']);program['receipt_ref']=reference
    read=deepcopy(result['reader_difference']);read['receipt_ref']=reference
    out['program']=program;out.setdefault('comparisons',{})['reader_difference']=read
    owed=[s for s in out.get('missing_steps',[]) if not s.startswith('step_4_')]
    if result.get('kind','').upper()=='DET':
        owed.append('step_3_det_table_regrade')
    else:
        if not program.get('complete'):owed.append('step_4_test_program_fit_proof')
        if not read.get('complete'):owed.append('step_4_reader_projection_or_rows')
    out['missing_steps']=owed;out['step']=4;out['step4_ref']=reference
    return out,reduce_grade(out)
