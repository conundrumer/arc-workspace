"""Read-time target evidence views over authoritative journal facts."""
from run import digest


def checked_clause(raw,base,ref,axis):
    """Invoke n-mech's sole policy using authenticated source identity/axes.

    Case axes and base source identity were checked by load_targets. No source
    program or another pass's results are copied into this journal.
    """
    try:
        from clause_evidence import clause_evidence_from_identity
    except ImportError:
        return dict(purpose='answer',role='recovery',outcome='unknown',receipt_ref=ref,
            reason='canonical read-time clause identity adapter not merged')
    return clause_evidence_from_identity(raw,base['source_sha256'],len({a for a,k,i in axis}),ref,
        ntrain=len({i for a,k,i in axis if k==1}),ntest=len({i for a,k,i in axis if k==2}))


def pair_view(facts,base,resolve,*,source_groups=None):
    """Return a legacy-compatible ephemeral view; never write it back."""
    legacy=facts.get('schema')!='mech-target-facts-v2'
    refs=facts.get('comparison_refs',[])
    view=dict(schema='mech-target-pair-v1',pair_id=base['pair_id'],source_sha256=base['source_sha256'],
        base_result_sha256=digest(base),kind=base['kind'],table_only=base['kind'].casefold()=='det',
        case_refs=facts.get('case_refs',[]),grade_comparisons=[],mechanical_clauses=[],
        searches=facts.get('searches',[]),gaps=list(facts.get('gaps',[])),bounded=bool(facts.get('stopped')))
    cases=[]
    if facts.get('axis_ref'):
        axis=resolve(facts['axis_ref'])['axis'];own=[]
    else:
        cases=[resolve(r) for r in view['case_refs']]
        own=[v for v in cases if v.get('case')==base['case']]
        axis=None
    if axis is None:axis=(own[0].get('axis') if own else None)
    if axis is None and own:
        axis=next((i['grouped']['required'] for i in own[0]['tables']+own[0]['bodies'] if i.get('grouped')),[])
    axis=axis or []
    contains=[]
    if refs:
        for item in refs:
            ref=item['reference'];value=resolve(ref);target=value.get('target',item.get('target',{}))
            eq=value['equality'];include=value['containment'];equal=eq['status']=='equal'
            view['grade_comparisons'].append(dict(target_id=target.get('target_id',target.get('table_id','G')),
                equal=equal,train=equal,test=equal,complete=equal,kept_contexts_complete=equal,
                test_target='gold_full_replay',receipt_ref=ref,comparison=eq))
            if include['status']=='unknown' or eq['status']=='unknown':
                view['gaps'].append(dict(stage='comparison',reason=eq.get('reason') or include.get('reason','bounded comparison')))
            contains.append(include['status'])
            if target.get('role')=='point':
                view['point']=dict(complete=include['status']!='unknown',
                    X_holds_every_gold_row=True if include['status']=='contains' else False if include['status']=='mismatch' else None,
                    receipt_ref=ref,comparison=include)
    elif legacy:
        # Completed legacy payloads stay readable. Pair grades/outcome are
        # deliberately ignored; comparison/verification facts remain usable.
        view['grade_comparisons']=facts.get('grade_comparisons',[])
        if 'point' in facts:view['point']=facts['point']
        contains=[('contains' if facts.get('support',{}).get('any_target_contains') else 'unknown')]
    for ref in view['searches']:
        search=resolve(ref)
        view['bounded'] |= search.get('proof',{}).get('reason_code')=='search_bound'
        if search.get('candidate_ref'):
            raw=resolve(search['candidate_ref'])
            view['mechanical_clauses'].append(checked_clause(raw,base,search['candidate_ref'],axis))
        if search.get('status')=='unknown':view['gaps'].append(dict(stage='search',reason=search.get('reason','unavailable search')))
    if legacy and not view['mechanical_clauses']:
        view['mechanical_clauses']=facts.get('mechanical_clauses',[])
    view['complete']=bool(cases) and bool(view['grade_comparisons']) and not view['gaps']
    view['support']=dict(complete=view['complete'],all_targets_lossy=None,any_target_contains='contains' in contains)
    view['missing_steps']=[]
    if not view['complete']:view['missing_steps'].append('step_3_incomplete_target_catalog_or_comparison')
    if legacy and facts.get('no_recovery_certificate'):view['no_recovery_certificate']=facts['no_recovery_certificate']
    if source_groups is not None:
        from .certificates import no_x_rows
        from case_collector import decode_grouped
        targets=[]
        if not cases:cases=[resolve(r) for r in view['case_refs']]
        for link in refs:
            target=resolve(link['reference']).get('target',link.get('target',{}))
            for bundle in cases:
                if bundle['case']!=target.get('case'):continue
                expected=bundle.get('axis')
                if expected is None and bundle.get('axis_ref'):expected=resolve(bundle['axis_ref'])['axis']
                items=[i for i in bundle.get('tables',[])+bundle.get('bodies',[])
                    if (i.get('table_id')==target.get('table_id') if target.get('table_id') else i.get('body_path')==target.get('body_path'))]
                for item in items:
                    g=dict(item['grouped'])
                    if expected is not None:
                        present={tuple(v['context']) for v in g['groups']}
                        g.update(required=expected,missing=[k for k in expected if tuple(k) not in present])
                    targets.append((decode_grouped(g),[],target,item.get('receipt',{})))
        # Consumers with canonical X groups may derive the conservative empty
        # certificate without storing a duplicate of the source table.
        view['no_recovery_certificate']=no_x_rows(source_groups,targets,complete=view['complete'],
            inputs={k:view[k] for k in ('pair_id','source_sha256','base_result_sha256')},case_refs=view['case_refs'],
            ntrain=len({i for a,k,i in axis if k==1}),ntest=len({i for a,k,i in axis if k==2}),
            assignment_count=len({a for a,k,i in axis}))
    return view
