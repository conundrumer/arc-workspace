"""Pure overlay of authenticated target results; central reducer owns grades."""
import copy
from ._paths import CODE_ROOT
from run import digest


def certified_empty(result):
    """Validate the complete typed certificate before exposing empty evidence."""
    c=result.get('no_recovery_certificate',{})
    if (c.get('schema')!='mech-no-x-rows-v1' or c.get('complete') is not True
            or c.get('no_recovery') is not True or result.get('complete') is not True
            or c.get('all_X_families_present') is not True or c.get('every_X_rowset_empty') is not True
            or c.get('target_catalog_complete') is not True or c.get('case_refs')!=result.get('case_refs')):
        return False
    expected_inputs={k:result[k] for k in ('pair_id','source_sha256','base_result_sha256')}
    if c.get('inputs')!=expected_inputs:return False
    try:
        ntrain,ntest,count=(c[k] for k in ('ntrain','ntest','assignment_count'))
        if not all(type(n) is int and n>=0 for n in (ntrain,ntest,count)) or not ntrain or not count:return False
        expected={(a,k,i) for a in range(count) for k,n in ((1,ntrain),(2,ntest)) for i in range(n)}
        required=[tuple(k) for k in c['required_contexts']]
        families={tuple(f['context']):f['count'] for f in c['family_counts']}
        if (len(required)!=len(expected) or set(required)!=expected or set(families)!=expected
                or len(c['family_counts'])!=len(expected)
                or not all(type(n) is int and n>0 for n in families.values())):return False
        targets=c['targets']
        if not targets or len(targets)!=len(result.get('grade_comparisons',[])):return False
        return all(t['nonempty']['row_count']>0 and t['nonempty']['model_sha256'] for t in targets)
    except (KeyError,TypeError,ValueError):return False


def apply_targets(evidence,loaded):
    """Apply load_targets' valid result, preserving other evidence producers.

    The durable reference is retained for central grade validity. This function
    authenticates internal binding; the caller must use load_targets to validate
    current files, base inputs and child journals before calling it.
    """
    if loaded.get('valid') is not True or loaded.get('status')!='done':
        raise ValueError('target overlay is open')
    result=loaded['record'];ref=loaded['reference']
    if digest(result)!=loaded['result_sha256'] or ref['result_sha256']!=loaded['result_sha256']:
        raise ValueError('target overlay digest differs')
    if (result['pair_id']!=evidence['pair_id'] or result['source_sha256']!=evidence['source_sha256']
            or result['base_result_sha256']!=evidence['base_result_ref']['result_sha256']):
        raise ValueError('target overlay source/base binding differs')
    out=copy.deepcopy(evidence)
    out['target_pass_ref']=ref
    out['target_catalog']=dict(complete=result.get('complete') is True,receipt_ref=ref,gaps=result.get('gaps',[]))
    comparisons=out.setdefault('comparisons',{})
    if certified_empty(result):
        comparisons['X_empty']=dict(complete=True,empty=True,train=True,test=True,
            kept_contexts_complete=True,receipt_ref=ref)
    comparisons['targets']=copy.deepcopy(result.get('grade_comparisons',[]))
    if 'point' in result:comparisons['point']=copy.deepcopy(result['point'])
    # Raw containment/count diagnostics do not cover computed libraries/unions.
    comparisons['recovery_support']=dict(result.get('support',{}),receipt_ref=ref,all_targets_lossy=None)
    out['mechanical_clauses']=[c for c in out.get('mechanical_clauses',[]) if c.get('producer')!='mech5']
    out['mechanical_clauses'].extend(dict(copy.deepcopy(c),producer='mech5') for c in result.get('mechanical_clauses',[]))
    # Keep an independently authenticated settled-space result if already held.
    if out.get('search',{}).get('settled_space') is not True:
        out['search']=dict(status='bound_unknown' if result.get('bounded') else 'not_covered',
            complete=False,settled_space=False,unvisited=None,receipt_ref=ref,
            searched_other_targets=result.get('searches',[]))
    missing=[s for s in out.get('missing_steps',[]) if not s.startswith('step_3_')]
    missing.extend(result.get('missing_steps',[]))
    out['missing_steps']=list(dict.fromkeys(missing))
    return out
