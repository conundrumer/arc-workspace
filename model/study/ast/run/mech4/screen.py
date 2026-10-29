"""Batch candidate TRAIN screening through canonical prepare/replay/comparison.

Screening proposes an explicit output projection. Only a separate canonical
TRAIN+TEST evaluation with provenance can certify a recovery.
"""
from common import digest
import time


def required(record,ntrain,kind=1):
    return {(a,kind,i) for a in range(len(record['evaluation']['kept_assignments'])) for i in range(ntrain)}


def training(grouped,record,ntrain):
    wanted=required(record,ntrain)
    actual={k for k in grouped['groups'] if k[1]==1}
    declared={k for k in grouped['required'] if k[1]==1}
    if not wanted or actual!=wanted or declared!=wanted or any(k[1]==1 for k in grouped['missing']):
        raise ValueError('exact compatible TRAIN axis incomplete')
    return {k:grouped['groups'][k] for k in sorted(wanted)}


def compare_train(native,table,ev,record,adapter,candidate,proof,gold,ntrain,ntest,config,budget):
    from tables import kept_groups,compare
    from registry_plan import projection_labels
    from surface import tokens
    from planner import fields
    grouped=kept_groups(ev.legacy,native,table,record,ntrain,ntest)
    observed=training(grouped,record,ntrain);expected=training(gold,record,ntrain)
    ts=native['tables']
    names=list(ts['column_names'][table]);types=list(ts['column_types'][table])
    exported={t.lstrip('*^') for t in tokens(proof['canonical']) if t.startswith(('*','^'))}
    aliases=proof.get('output_aliases',{})
    eligible={f.get('_candidate_label',f'V{i}') for i,f in enumerate(fields(adapter,candidate))}
    # Available-table existential columns may restrict X, but never become
    # target suppliers in this recovery planner.
    eligible.update(v.lstrip('*^') for k,v in aliases.items() if k in eligible)
    visible=[i for i,name in enumerate(names) if name in exported and name in eligible]
    groups={k:{frozenset(tuple(r[i] for i in visible) for r in model) for model in family}
            for k,family in observed.items()}
    columns=[(names[i],types[i]) for i in visible]
    if len({c[0] for c in columns})!=len(columns):raise ValueError('ambiguous scoped exported label')
    targets=adapter['comparison_target']['binding']['projected_schema']
    # We are choosing an EXPLICIT output projection for a proposed clause,
    # whose fresh labels differ from G's names. The independent checker keeps
    # the original fields and validates the selected ordered output labels.
    proposal_fields=[dict(f,field_name=None) for f in targets]
    budget.check()
    equal=compare(groups,columns,expected,proposal_fields,seconds=min(config['compare_seconds'],budget.remaining()))
    # The common comparator coalesces the normal type/permutation choices in
    # one call. Explicit repeated columns also cover native projection aliases.
    alias=aliases
    def resolve(name):
        seen=set()
        while name in alias:
            if name in seen:raise ValueError('cyclic native projection alias')
            seen.add(name);name=alias[name].lstrip('*^')
        return name
    attempts=0;limit=False
    if equal['status']!='equal':
        for projection in projection_labels(fields(adapter,candidate),targets):
            attempts+=1
            if attempts>config['max_projections']:limit=True;break
            selected=[resolve(p) for p in projection]
            if len(set(selected))==len(selected):continue
            budget.check()
            trial=compare(groups,columns,expected,proposal_fields,explicit=selected,
                          seconds=min(config['compare_seconds'],budget.remaining()))
            if trial['status']=='equal':equal=trial;break
    containment=None
    if equal['status']!='equal':
        budget.check()
        containment=compare(groups,columns,expected,proposal_fields,relation='contains',
                            seconds=min(config['compare_seconds'],budget.remaining()))
    distance=sum(abs(max(map(len,groups[k]))-max(map(len,expected[k]))) for k in expected)
    return dict(status='train_match' if equal['status']=='equal' else 'screened',comparison=equal,
        columns=equal.get('columns') if equal['status']=='equal' else None,containment=containment,
        useful=True,rank=distance,
        projection_attempts=attempts,projection_bound=limit,required_train_contexts=len(expected),
        source='same shared evaluator; TRAIN proposal only',native_table=table)


def execute(ev,record,adapter,candidates,gold,ntrain,ntest,config,budget,cache,inputs,guard):
    """Yield each durably screened candidate; isolate refused combined programs."""
    from surface import prepare,tokens
    L=ev.legacy;original=L.split_forms(record['mutant_sexp']);trees=[L.parse(f) for f in original]
    if not trees or trees[-1][0]!='OUT' or sum(f[0]=='OUT' for f in trees)!=1:
        raise ValueError('batch screening requires original whole mutant with final single OUT')
    occupied=set(tokens(trees));prepared=[]
    for candidate in candidates:
        if STOPPED(budget):return
        key=digest(dict(pair=inputs['pair_id'],candidate=candidate['candidate_id']))
        old=cache.recall('screen',key,dict(inputs,candidate=candidate))
        if old is not None:
            yield candidate,old,True;continue
        try:
            program,at,proof=prepare(L,record,candidate['clause'],adapter)
            forms=L.split_forms(program)
            if L.parse(forms[at])[0]!='RULE':raise ValueError('TRAIN batch candidate is not a RULE')
            if forms[:at]+forms[at+1:]!=original:raise ValueError('canonical preparation changed original program')
            name='&Mech4_'+digest(dict(source=digest(record),candidate=key))[:24]
            while name in occupied:name+='Q'
            occupied.add(name);tree=L.parse(forms[at]);tree[1]=name
            prepared.append((candidate,at,L.unparse(tree),proof))
        except (ValueError,KeyError,IndexError,TypeError) as error:
            result=dict(status='unavailable',reason=str(error),stage='canonical preparation')
            cache.remember('screen',key,dict(inputs,candidate=candidate),result)
            yield candidate,result,False
    # Different insertion positions cannot silently share a program.
    positions=sorted({p[1] for p in prepared})
    for at in positions:
        batch=[p for p in prepared if p[1]==at]
        yield from _execute_group(ev,record,adapter,batch,original,at,gold,ntrain,ntest,config,budget,cache,inputs,guard)


def STOPPED(budget):
    budget.check()
    return False


def _execute_group(ev,record,adapter,prepared,original,at,gold,ntrain,ntest,config,budget,cache,inputs,guard):
    if not prepared:return
    identity=digest(dict(source=digest(record),candidates=[p[0]['candidate_id'] for p in prepared],at=at))
    old=cache.recall('batch',identity,inputs)
    replay=None;native=None
    if old is None:
        program='\n'.join(original[:at]+[p[2] for p in prepared]+original[at:])
        guard.check()
        replay=budget.replay(ev,record,program,at,candidate=dict(kind='lib-TRAIN-batch',candidates=[p[0]['candidate_id'] for p in prepared]),
                             retain_forms=list(range(at,at+len(prepared))))
        guard.check()
        if replay['engine']=='ran':native=ev.captures[-1]['native']
        else:cache.remember('batch',identity,inputs,replay)
    else:replay=old
    if replay['engine']!='ran':
        if len(prepared)>1:
            middle=len(prepared)//2
            yield from _execute_group(ev,record,adapter,prepared[:middle],original,at,gold,ntrain,ntest,config,budget,cache,inputs,guard)
            yield from _execute_group(ev,record,adapter,prepared[middle:],original,at,gold,ntrain,ntest,config,budget,cache,inputs,guard)
        else:
            candidate=prepared[0][0]
            result=dict(status='refused' if replay['engine']=='refused' else 'unknown',
                        engine=replay['engine'],reason=replay.get('reason'),replay=replay)
            key=digest(dict(pair=inputs['pair_id'],candidate=candidate['candidate_id']))
            cache.remember('screen',key,dict(inputs,candidate=candidate),result)
            yield candidate,result,False
        return
    for offset,(candidate,_,text,proof) in enumerate(prepared):
        try:
            matches=[t for t,f in enumerate(native['tables']['form']) if str(f)==str(at+offset)]
            if len(matches)!=1:raise ValueError('exact appended candidate form is missing or ambiguous')
            result=compare_train(native,matches[0],ev,record,adapter,candidate,proof,gold,ntrain,ntest,config,budget)
            result.update(replay_artifact=replay['artifact'],program_sha256=digest(program),
                          appended_form=at+offset,executed_clause=text,proof=proof)
        except (ValueError,KeyError,IndexError,TypeError) as error:
            result=dict(status='unavailable',reason=str(error),replay_artifact=replay['artifact'],appended_form=at+offset)
        key=digest(dict(pair=inputs['pair_id'],candidate=candidate['candidate_id']))
        cache.remember('screen',key,dict(inputs,candidate=candidate),result)
        yield candidate,result,False
