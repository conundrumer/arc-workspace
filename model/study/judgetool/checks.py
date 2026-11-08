"""Clause policy over results of the ONE ReplayEvaluator, never lib semantics."""
from collections import defaultdict
import json
from pathlib import Path

from surface import prepare,atoms,tokens,site_bindings,output_projection,InvalidSubmission
from tables import TargetStore,Incomplete,kept_groups,compare,axis_receipt,comparison_type
import catalog
import live_targets


def counts_table(groups,columns,limit=100,*,offset=0):
    """Judge-safe bounded TRAIN/TASK view. Test rows are never printed."""
    shown=[];total=0;remaining=max(0,limit);skip=max(0,offset)
    for key,family in sorted(groups.items()):
        assignment,kind,index=key
        if kind==2:continue
        for model,rows in enumerate(sorted(family,key=repr)):
            ordered=sorted(rows);start=min(skip,len(ordered));skip-=start
            take=ordered[start:start+remaining];remaining-=len(take);total+=len(ordered)
            shown.append(dict(assignment=assignment,example=('task' if kind==0 else f'train{index+1}'),
                              model=model,row_count=len(ordered),rows=take,omitted_rows=len(ordered)-len(take)))
    return dict(columns=columns,groups=shown,total_rows=total,shown_rows=total- sum(g['omitted_rows'] for g in shown),
                omitted_rows=sum(g['omitted_rows'] for g in shown),limit=limit,offset=offset,test_rows='withheld')


def _replay_groups(ev,record,program,form,ntrain,ntest,candidate):
    from program_metadata import type_identity
    result=ev.replay_program(record,program,form,candidate=candidate)
    if result['engine']!='ran':return result,None,None
    n=ev.captures[-1]['native'];t=result['kept_coverage']['table'];ts=n['tables']
    groups=kept_groups(ev.legacy,n,t,record,ntrain,ntest,
                       unheld=result['kept_coverage'].get('unheld_det_relations',()))
    columns=[(name,type_identity(ev,record,ty)[0]) for name,ty in zip(ts['column_names'][t],ts['column_types'][t])]
    return result,groups,columns


def _relation_reads(canonical):
    return {t for t in tokens(canonical[2:]) if t.startswith('&') and t!='&X'}


def _made(atom):
    return {t.lstrip('*^') for t in tokens(atom[1:]) if t.startswith(('*','^'))}


def multiplicity(ev,record,adapter,canonical,ntrain,ntest,output):
    """Measure lib output multiplicity through prefix queries in the same engine.
    Computed-output libraries are never evaluated in Python. Complete one-model
    prefix contexts are supported; unresolved model correspondence stays unknown.
    """
    L=ev.legacy;body=canonical[2:];binding=adapter['input']['binding']
    xatoms=[a for a in body if isinstance(a,list) and a and a[0]=='&X']
    if len(xatoms)!=1:return dict(status='unknown',reason='computed lib provenance needs one top-level X witness')
    x=xatoms[0];spec=site_bindings(L,x,binding['callable_template'])
    augmented=L.parse(binding['callable_template'])
    mapping={f'V{i}':spec.get(i,'*JudgeRow'+str(i)) for i in range(len(binding['projected_schema']))}
    augmented=L.rename_labels(augmented,lambda label:mapping[label.lstrip('*^')])
    keylabels=[mapping[f'V{i}'].lstrip('*^') for i in range(len(mapping))]
    workbody=[augmented if a is x else a for a in body]
    direct=set(t.lstrip('*^') for t in spec.values() if t!='0')
    derived=set(direct);proofs=[]
    wanted=set(output)-direct
    for at,atom in enumerate(workbody):
        if not isinstance(atom,list) or not atom or not isinstance(atom[0],str):continue
        relation=atom[0];made=_made(atom)
        if relation=='&X' or not made:continue
        if relation.startswith('&') or relation in ('input','ex_input','ex_output'):
            if made&wanted:return dict(status='partial',reason='target column made by an available atom',producer=relation)
            continue
        if relation in ('OR','IF','ALL','NOT','ONE'):
            if wanted:return dict(status='unknown',reason='computed lib branch provenance unresolved')
            continue
        # Only a library whose produced value is needed by a mapped output
        # (or a subsequent grounded lib) needs this multiplicity certificate.
        inputs={t for t in tokens(atom[1:]) if t not in made and not t.startswith((':','*','^')) and t!='0'}
        if not (inputs&derived):
            if made&wanted:return dict(status='partial',reason='lib output has no X-column input',producer=relation)
            continue
        before=['RULE','&fix']+workbody[:at]
        after=['RULE','&fix']+workbody[:at+1]
        contexts=[]
        for stage,formtree in (('before',before),('after',after)):
            try:program,index,_=prepare(L,record,L.unparse(formtree),adapter)
            except Exception as error:return dict(status='unknown',reason=f'lib instrumentation unavailable: {error}')
            r,g,cols=_replay_groups(ev,record,program,index,ntrain,ntest,dict(kind='lib-multiplicity',stage=stage,relation=relation,clause=L.unparse(formtree)))
            proofs.append(dict(stage=stage,relation=relation,artifact=r['artifact']))
            if g is None or g['missing']:return dict(status='unknown',reason='lib multiplicity replay lacks required contexts',queries=proofs)
            try:indices=[next(i for i,c in enumerate(cols) if c[0]==label) for label in keylabels]
            except StopIteration:return dict(status='unknown',reason='instrumented X key label absent',queries=proofs)
            bygroup={}
            for key,family in g['groups'].items():
                if len(family)!=1:return dict(status='unknown',reason='lib model correspondence unresolved',queries=proofs)
                rows=next(iter(family));buckets=defaultdict(set)
                for row in rows:buckets[tuple(row[i] for i in indices)].add(row)
                bygroup[key]=buckets
            contexts.append(bygroup)
        for key,buckets in contexts[0].items():
            afterb=contexts[1].get(key,{})
            for xrow in buckets:
                if len(afterb.get(xrow,()))!=1:
                    return dict(status='partial',reason='lib does not give exactly one row per X row',
                                producer=relation,multiplicity=len(afterb.get(xrow,())),queries=proofs)
        derived.update(made);wanted-=made
    if wanted:return dict(status='partial',reason='mapped column is not derived from X by certified single-row libs',labels=sorted(wanted),queries=proofs)
    return dict(status='single_row_lib',queries=proofs,one_row_per_X=True,restrictions_only=True)


def evaluate(ev,record,clause,target,columns=None,*,explore=False,row_limit=100,include_table=True):
    """Check a clause; include_table=False skips only the display table."""
    from evaluator import sha
    adapter=target['adapter'];ntrain=target['ntrain'];ntest=target['ntest']
    result=dict(schema='judgetool-clause-v2',outcome='unknown',verified=False,
                source_sha256=sha(record),adapter_sha256=sha(adapter),
                candidate_sha256=sha(dict(kind=target.get('mode','recovery'),clause=clause,columns=columns)),
                target_id=target.get('target_id','G'),
                kind=target.get('mode','recovery'),submitted_clause=clause,route='replay_search_then_kept_filter',graded=not explore,
                kept_context_sha256=sha(record['evaluation']['kept_assignments']))
    if target.get('source',{}).get('source_sha256') not in (None,sha(record)):
        result['reason']='source record hash mismatch';return result
    try:
        program,form,proof=prepare(ev.legacy,record,clause,adapter)
        allowed={d['definition']['display_name'] for d in adapter['availability']['definitions']}
        unavailable=_relation_reads(proof['canonical'])-allowed
        if unavailable:raise Incomplete('unavailable/G-dependent relations: '+', '.join(sorted(unavailable)))
        replay,grouped,actual_columns=_replay_groups(ev,record,program,form,ntrain,ntest,dict(clause=clause,columns=columns,target=result['target_id'],explore=explore))
    except InvalidSubmission as error:
        result.update(outcome='did not verify',engine='not run',reason=str(error),
                      submission_validation=dict(status='invalid_submission',stage='clause_syntax',
                                                 native_operations=0))
        return result
    except (ValueError,KeyError,IndexError,TypeError) as error:
        result['reason']='adapter/context unavailable: '+str(error);return result
    result.update(engine=replay['engine'],replay_artifact=replay['artifact'],seconds=replay['seconds'],
                  executed_clause=proof['inserted'],or_rewritten=proof['or_rewritten'],receipt=ev.receipt)
    if replay['engine']=='refused':
        result.update(outcome='refused by the engine',reason=replay['reason']);return result
    if grouped is None or grouped['missing']:
        result.update(reason=(replay.get('reason') or 'replay produced no comparison groups') if grouped is None
                      else 'no complete compatible kept train/test entries',
                      native_status=replay.get('engine_report',{}).get('status'),
                      missing_contexts=None if grouped is None else grouped['missing']);return result
    # INIT adapter-private witnesses are existential details of virtual X.
    # They must never become query outputs or candidate target columns.
    exported={t.lstrip('*^') for t in tokens(proof['canonical']) if t.startswith(('*','^'))}
    visible=[i for i,c in enumerate(actual_columns) if c[0] in exported]
    grouped=dict(grouped,groups={key:{frozenset(tuple(row[i] for i in visible) for row in rows) for rows in family}
                                 for key,family in grouped['groups'].items()})
    actual_columns=[actual_columns[i] for i in visible]
    aliases=proof.get('output_aliases',{})
    if any(a in exported for a in aliases):
        labels=[c[0] for c in actual_columns]+[a for a in aliases if a in exported]
        indices=output_projection([c[0] for c in actual_columns],labels,aliases)
        grouped=dict(grouped,groups={k:{frozenset(tuple(row[i] for i in indices) for row in rows) for rows in family}
                                    for k,family in grouped['groups'].items()})
        actual_columns=[(label,actual_columns[index][1]) for label,index in zip(labels,indices)]
    if target.get('mode')=='alternative' and columns is not None:
        try:selected=[next(i for i,c in enumerate(actual_columns) if c[0]==name) for name in columns]
        except StopIteration:
            result.update(outcome='did not verify',reason='explicit continuation output label absent');return result
        grouped=dict(grouped,groups={k:{frozenset(tuple(row[i] for i in selected) for row in rows) for rows in family}
                                    for k,family in grouped['groups'].items()})
        actual_columns=[actual_columns[i] for i in selected]
    result['projection_aliases']=proof.get('output_aliases',{})
    if include_table:
        result['table']=counts_table(grouped['groups'],actual_columns,row_limit)
    result['context_receipt']=dict(complete=True,required=len(grouped['required']),
        **axis_receipt(grouped),
        compatible_entry_ids=[e['entry'] for e in grouped['contexts']],
        other_assignment_entry_ids=[e['entry'] for e in grouped['other_contexts']],test_rows='internal artifact only')
    if explore:
        result.pop('outcome');result.pop('verified');return result
    if len({c[0] for c in actual_columns})!=len(actual_columns):
        result.update(reason='ambiguous exported label spelling across native scopes');return result
    if not any(a[0]=='&X' for a in atoms(proof['canonical'][2:])):
        result.update(outcome='did not verify',reason='answer clause does not read X');return result
    if ev.target_store is None:ev.target_store=TargetStore(ev.legacy,ev.run.parent.parent)
    store=ev.target_store
    binding=target.get('binding',adapter['comparison_target']['binding'])
    try:
        gold,goldreceipt=observe_gold(ev,record,adapter,binding,ntrain,ntest)
        equality=(dict(status='mismatch',reason='output column count differs',candidate_columns=len(columns if columns is not None else actual_columns),target_columns=len(binding['projected_schema']))
                  if len(columns if columns is not None else actual_columns)!=len(binding['projected_schema'])
                  else compare(grouped['groups'],actual_columns,gold['groups'],binding['projected_schema'],explicit=columns))
    except (ValueError,KeyError,TypeError) as error:
        gold=None;goldreceipt=dict(status='unavailable',reason=str(error))
        equality=dict(status='unknown',reason='G train/test evidence unavailable: '+str(error))
    comparisons=[dict(target_id='G',comparison=equality)]
    train_target_match=('G' if equality.get('train')=='equal' else None)
    gaps=[];matched_fields=binding['projected_schema']
    # G is tried first; every other authenticated target uses the same native
    # values, comparator, and row-source policy. Target tables are never reads.
    targets,replay_gaps,case_receipts,available=(live_targets.acquire(ev,record,adapter,ntrain,ntest)
        if equality['status']!='equal' else ([],[],[],[]))
    catalog_complete=not replay_gaps;catalog_gaps=replay_gaps
    result['gold_case_receipts']=case_receipts
    if equality['status']!='equal':
        for other,fields,ref,receipt in targets:
            eq=(dict(status='mismatch',reason='output column count differs',candidate_columns=len(columns if columns is not None else actual_columns),target_columns=len(fields))
                if len(columns if columns is not None else actual_columns)!=len(fields)
                else catalog.equality(grouped['groups'],actual_columns,other,fields,ref,explicit=columns))
            comparisons.append(dict(target_id=ref['target_id'],comparison=eq,
                reference=dict(case=ref['case'],role=ref['role'],
                               native_selector=dict(ref['native_selector']))))
            if eq.get('train')=='equal':train_target_match=ref['target_id']
            if eq['status']=='equal':
                equality,gold,goldreceipt,matched_fields=eq,other,receipt,fields
                result['target_id']=ref['target_id'];break
            if eq['status']=='unknown':gaps.append(ref['target_id'])
    result['comparisons']=comparisons
    result['comparison']=equality
    # Preserve the selected target's OWN axes. Cross-case Cartesian expansion
    # is a comparator detail, never the target's native assignment namespace.
    result['target_receipt']=(dict(goldreceipt,**axis_receipt(gold))
                              if gold is not None else goldreceipt)
    if equality['status']!='equal':
        if target.get('mode')=='alternative' and train_target_match:
            result.update(outcome='unknown' if not catalog_complete or gaps or any(c['comparison']['status']=='unknown' and c['target_id']==train_target_match for c in comparisons) else 'did not verify',
                          reason='continuation matches target on train but recovery lacks equal test evidence',matched_target=train_target_match)
            return result
        if target.get('mode')=='alternative':
            return alternative(ev,result,record,adapter,grouped,actual_columns,store,ntrain,ntest,
                               dict(target,live_available=available,catalog_complete=catalog_complete and not gaps and all(c['comparison']['status']!='unknown' for c in comparisons)))
        incomplete=bool(gaps) or not catalog_complete or any(c['comparison']['status']=='unknown' for c in comparisons)
        result.update(outcome='unknown' if incomplete else 'did not verify',
                      reason='target comparison incomplete' if incomplete else 'candidate differs from every target',
                      comparison_gaps=gaps+list(catalog_gaps));return result
    output=equality['columns']
    outer_x=[a for a in proof['canonical'][2:] if isinstance(a,list) and a and a[0]=='&X']
    outer_direct=any(set(output)<={v.lstrip('*^') for v in site_bindings(ev.legacy,x,adapter['input']['binding']['callable_template']).values() if v!='0'} for x in outer_x)
    branches=execution_branches(proof['canonical'][2:])
    if outer_direct:
        provenance=(union_proof(ev,record,adapter,proof,output,gold,actual_columns,ntrain,ntest,matched_fields)
                    if any(isinstance(a,list) and a and a[0]=='OR' for a in proof['canonical'][2:])
                    else dict(status='direct_X',restrictions_only=True,one_row_per_X=True))
    elif branches is None:
        provenance=dict(status='unknown',reason='nested ALL/IF source provenance is not yet supported')
    else:
        source_branches=[]
        for branch in branches:
            xs=[a for a in branch if isinstance(a,list) and a and a[0]=='&X']
            if not xs:continue
            direct=any(set(output)<={v.lstrip('*^') for v in site_bindings(ev.legacy,x,adapter['input']['binding']['callable_template']).values() if v!='0'} for x in xs)
            bp=dict(status='direct_X',restrictions_only=True,one_row_per_X=True) if direct else multiplicity(
                ev,record,adapter,[proof['canonical'][0],'&fix']+branch,ntrain,ntest,output)
            source_branches.append(bp)
        if not source_branches:
            result.update(outcome='did not verify',reason='verified target table has no positive X row source');return result
        if any(b['status']=='unknown' for b in source_branches):
            provenance=dict(status='unknown',reason='X branch source proof incomplete',branches=source_branches)
        elif any(b['status']=='partial' for b in source_branches):
            provenance=dict(status='partial',reason='target columns are not all supplied by X/single-row lib',branches=source_branches)
        elif len(branches)>1:
            provenance=union_proof(ev,record,adapter,proof,output,gold,actual_columns,ntrain,ntest,matched_fields)
            provenance['branches']=source_branches
        else:provenance=source_branches[0]
    result['provenance']=provenance
    if provenance['status']=='unknown':
        result['reason']=provenance['reason'];return result
    if provenance['status']=='union_X_redundant':
        result.update(outcome='did not verify',reason=provenance['reason'])
        return result
    if provenance['status']=='partial':
        contribution=partial_source_rows(proof,grouped,replay)
        provenance['row_contribution']=contribution
        if contribution.get('X_contributes_rows') is not True:
            # An empty result or an unsupported path is no completed negative
            # proof, and a syntactic X read cannot certify a partial positive.
            result['reason']=contribution['reason'];return result
        provenance['X_contributes_rows']=True
    result.update(verified=True,outcome='partial source verified' if provenance['status']=='partial' else 'recovery verified',
                  checks=dict(train='equal',test='equal',test_target='gold_full_replay',complete=True))
    return result


def observe_gold(ev,record,adapter,binding,ntrain,ntest):
    """Fresh original BODY at native gold FITS choices, with full TEST guards.

    Original lexical/owner scope and native full-kept entry maps are retained;
    no reconstructed RULE or historical TRAIN receipt supplies target rows.
    """
    from evaluator import sha
    key=sha(dict(source=sha(record),binding=binding,settings=ev.receipt))
    if key in ev.target_cache:return ev.target_cache[key]
    from gold_body import capture,projection
    from tables import read_table,kept_entries
    with capture(ev,record) as body:
        indices=projection(body,record,binding)
        native=body['native'];table=body['table'];ts=native['tables']
        chosen={e for e,assignments in body['held_entries'].items() if assignments}
        entries=read_table(ev.legacy,native,table,entry_ids=chosen)
        result=kept_entries(ev.legacy,entries,ts['det_relations'][table],ts['det_types'][table],
                            record,ntrain,ntest,indices,held_entries=body['held_entries'])
        if result['missing']:raise Incomplete('original gold BODY lacks compatible train/test contexts')
        receipt=dict(body['receipt'],fields=binding['projected_schema'],
            projection=[f['source_body_column'] for f in binding['projected_schema']],
            original_body_projection=indices,train_complete=True,test_complete=True,
            required_train_test_contexts=len(result['required']),**axis_receipt(result))
    ev.target_cache[key]=(result,receipt)
    return result,receipt


def execution_branches(body,limit=256):
    branches=[[]]
    for atom in body:
        if not isinstance(atom,list) or not atom:return None
        if atom[0] in ('IF','ALL','ONE'):return None
        if atom[0]=='OR':
            choices=[]
            for branch in atom[1:]:
                expanded=execution_branches(branch,limit)
                if expanded is None:return None
                choices.extend(expanded)
            if len(branches)*len(choices)>limit:return None
            branches=[prefix+choice for prefix in branches for choice in choices]
        else:branches=[prefix+[atom] for prefix in branches]
    return branches


def partial_source_rows(proof,grouped,replay):
    """Certify an actual X row on a successful original native clause path.

    A positive outer X is a mandatory conjunct; otherwise every supported OR
    execution branch must contain one. Nonempty rows from the ORIGINAL complete
    candidate replay then witness a successful path with X. No row is inferred
    from syntax, a prefix query, model union, or the disabled-X counterfactual.
    Branch-dependent X participation remains unknown without native path proof.
    This check adds no native operations to ordinary/lib/union partial checks.
    """
    unknown=dict(complete=False,X_contributes_rows=None)
    required=grouped.get('required',set())
    groups=grouped.get('groups',{})
    if (replay.get('engine')!='ran' or not replay.get('artifact')
            or not required or grouped.get('missing') or set(groups)!=set(required)
            or any(not family for family in groups.values())):
        return dict(unknown,reason='partial source original native TRAIN/TEST contexts incomplete')
    body=proof['canonical'][2:]
    def positive_x(branch):
        return any(isinstance(atom,list) and atom and atom[0]=='&X' for atom in branch)
    mandatory=positive_x(body)
    if not mandatory:
        branches=execution_branches(body)
        mandatory=bool(branches) and all(positive_x(branch) for branch in branches)
    if not mandatory:
        return dict(unknown,reason='partial source needs native successful-path evidence for branch-dependent X')
    contexts=[list(context) for context,family in sorted(groups.items()) if any(rows for rows in family)]
    if not contexts:
        return dict(unknown,reason='partial source has no actual successful X row in the native result')
    return dict(complete=True,X_contributes_rows=True,
        source='original_complete_native_candidate_replay',artifact=replay['artifact'],
        proof='positive X is mandatory on every successful result path',
        required_train_test_contexts=len(required),nonempty_contexts=contexts,
        additional_native_operations=0)


def header_type_certificate(column,definition):
    """A checked native field type need not have a local BODY label.

    Declared component headers certify a physical field's type/layout even
    when no source BODY binds a local label. This is only a schema certificate;
    it provides no rows, projection from a BODY, or kept-context evidence.
    """
    if (column.get('relation')!=definition['relation']
            or column.get('definition_path')!=definition['definition_path']):
        return False
    selected=column.get('selected_header_binding')
    if column.get('status')=='resolved':
        return isinstance(selected,dict) and selected.get('status')=='resolved'
    return (column.get('status')=='declared_without_local_label'
            and column.get('proof')=='declared_layout' and selected is None
            and isinstance(column.get('row_path'),list)
            and type(column.get('logical_slot')) is int and column['logical_slot']>=0)


def union_nonredundancy_result(nonredundancy):
    """Distinguish a verified counterexample from incomplete negative proof."""
    positives=[s for s in nonredundancy.get('searches',[])
        if s.get('proof',{}).get('status')=='determined'
        and s['proof'].get('recoverable') is True and s['proof'].get('verified') is True]
    if nonredundancy.get('redundant') is True and positives:
        names=', '.join(sorted({s['source']['name'] for s in positives}))
        return dict(status='union_X_redundant',redundant=True,nonredundant=False,
            reason='Union recovery did not verify: X is redundant; available source '+names+' has a verified recovery of X.',
            nonredundancy=nonredundancy)
    if nonredundancy.get('complete') is not True or nonredundancy.get('redundant') is not False:
        return dict(status='unknown',reason=nonredundancy.get('reason','union requires complete X-not-redundant evidence'),
                    nonredundancy=nonredundancy)
    return None


def union_nonredundancy(ev,record,adapter,ntrain,ntest):
    """Recheck the current readable inventory in the canonical redundancy grammar.

    An old base False can cover fewer ports than today's public interface. A
    bare adapter bit therefore cannot establish this gate. Search failures,
    missing tables/models and bounds remain unknown; only determined negatives
    for every source at every kept assignment establish nonredundancy.
    """
    import hashlib
    import sys
    from evaluator import sha
    from study_paths import CODE_ROOT
    from evaluator_train import acquire_train_table,acquire_input_train
    sys.path.insert(0,str(CODE_ROOT/'ast/run'))
    from mech import algorithm
    key=('union-nonredundancy',sha(record),sha(adapter['availability']),ntrain,ntest)
    if key in ev.target_cache:return ev.target_cache[key]
    receipt=dict(schema='judgetool-union-nonredundancy-v1',complete=False,redundant=None,
        source_sha256=sha(record),kept_context_sha256=sha(record['evaluation']['kept_assignments']),
        availability_sha256=sha(adapter['availability']),
        grammar='mech.algorithm.solve: typed projection/selection with comparison and semijoin/antijoin restrictions',
        computed_lib_columns=False,union_sources=False,searches=[])
    paths=[Path(algorithm.__file__),Path(algorithm.recovery.__file__)]
    receipt['implementation_dependencies']={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    try:
        x,fields=ev.target_store.mutant_input(record,adapter,ntrain,ntest)
        required=sorted(k for k in x['required'] if k[1]==1)
        receipt.update(required_axes=[list(k) for k in required],X_native_ref=record['native']['mutant'],
                       X_binding=adapter['input']['binding'])
        types=tuple(comparison_type(f['type']) for f in fields)
        if 'Ident' in types:
            raise Incomplete('cross-replay redundancy Ident correspondence is not certified')
        # One original-program replay, through the shared executor. Its exact
        # native selectors authenticate today's inventory, including recursive
        # ports omitted from older mechanical inventories.
        own=dict(record,mutant_sexp=record['gold_sexp'])
        replay=ev.replay_program(own,record['gold_sexp'],0,
            candidate=dict(kind='union-current-available-inventory',availability_sha256=receipt['availability_sha256']),
            retain_all=True)
        cases=[dict(case=record['case'],artifact=replay['artifact'],engine=replay['engine'],
                    program_sha256=sha(record['gold_sexp']),seconds=replay['seconds'],receipt=replay['receipt'])]
        receipt['native_operations']=cases
        if replay['engine']!='ran':
            raise Incomplete('current available-table replay incomplete')
        native=ev.captures[-1]['native'];ts=native['tables'];selected=[];omitted=[]
        for definition in adapter['availability']['definitions']:
            d=definition['definition'];selector=d['native_selector']
            matches=[i for i in range(len(ts['form'])) if all(str(ts[k][i])==str(v)
                for k,v in selector.items() if k in ('form','point','relation','fact'))]
            if len(matches)>1:raise Incomplete('current readable selector ambiguous: '+d['display_name'])
            if not matches:
                omitted.append(d);continue
            selected.append((d['display_name'],matches[0],selector))
        facts=adapter['availability'].get('fact_relations',[])
        for fact in facts:
            native_fact='ex_input' if fact=='input' else fact
            matches=[i for i,value in enumerate(ts['fact']) if value==native_fact]
            if len(matches)!=1:raise Incomplete('current readable fact absent or ambiguous: '+fact)
            selected.append((fact,matches[0],dict(fact=native_fact)))
        if not selected:raise Incomplete('current readable inventory is empty or unavailable')
        packets=[]
        for name,table,selector in selected:
            acquire=acquire_input_train if name=='input' else acquire_train_table
            packet=acquire(ev,native,table,record,ntrain=ntrain,
                source=dict(artifact=cases[0]['artifact'],native_selector=selector))
            if packet['missing']:raise Incomplete('available source lacks kept TRAIN contexts: '+name)
            packets.append((name,selector,packet))
        headers=[]
        if omitted:
            # Some readable INIT ports are deliberately not materialized by
            # gold_tables. Their complete native selected header can still
            # prove a row-independent typed-projection impossibility. Never
            # synthesize rows, substitute another table or infer an alias.
            from program_metadata import type_identity
            checked=ev.arclog.StudyProgram.from_sexp(record['gold_sexp'],ev.settings)
            exported=json.loads(ev.arclog.study_program_export_json(checked))
            for admitted in omitted:
                selector=admitted['native_selector']
                definitions=[d for d in exported['definitions']['native_relations']
                    if d['native_selector']==selector and d['definition_path']==admitted['definition_path']]
                if len(definitions)!=1:raise Incomplete('omitted source lacks exact checked definition: '+admitted['display_name'])
                definition=definitions[0];columns=definition['column_witnesses']
                if (definition['column_witness_status']!='complete'
                        or [c['physical_column'] for c in columns]!=list(range(len(columns)))
                        or any(not header_type_certificate(c,definition) for c in columns)
                        or adapter['relation_tokens'].get(definition['display_name'])!=admitted['display_name']):
                    raise Incomplete('omitted source lacks complete authenticated checked header: '+admitted['display_name'])
                source_types=tuple(comparison_type(type_identity(ev,record,c['type'])[0]) for c in columns)
                choices=algorithm.recovery.typed_projection_choices(types,source_types)
                if not any(not positions for positions in choices):
                    raise Incomplete('omitted source needs native rows for nonredundancy: '+admitted['display_name'])
                headers.append(dict(types=source_types,rows=None,
                    identity=dict(name=admitted['display_name'],native_selector=selector),
                    receipt=dict(source='original_checked_native_selected_header',
                        source_sha256=sha(record),gold_program_sha256=sha(record['gold_sexp']),
                        export_sha256=sha(exported),definition=definition,X_types=types,
                        typed_projection_choices=choices,rows_acquired=False),
                    obstruction=dict(status='determined',recoverable=False,states=0,
                                     nonrecoverable_proof='no typed projection exists')))
        receipt['header_only_source_count']=len(headers)
        for assignment in range(len(record['evaluation']['kept_assignments'])):
            axes=[(assignment,1,i) for i in range(ntrain)]
            if any(k not in x['groups'] for k in axes):raise Incomplete('X lacks required TRAIN contexts')
            target=tuple(frozenset(x['groups'][k]) for k in axes)
            available=[]
            for name,selector,packet in packets:
                groups=defaultdict(list)
                for entry in packet['entries']:
                    groups[(entry['assignment'],entry['example_kind'],entry['example_index'])].append(
                        frozenset(tuple(tuple(cell['value']) for cell in row) for row in entry['rows']))
                # The settled baseline source interface is one row set per
                # TRAIN input. Do not combine or pair multiple native models.
                if any(len(groups[k])!=1 for k in axes):
                    raise Incomplete('redundancy source has unresolved native model families: '+name)
                available.append(dict(types=tuple(comparison_type(f['type']) for f in packet['fields']),
                    rows=tuple(groups[k][0] for k in axes),identity=dict(name=name,native_selector=selector),
                    receipt=packet['receipt']))
            available.extend(headers)
            for index,table in enumerate(available):
                unknown_companions=[i for i,t in enumerate(available) if i!=index and t['rows'] is None]
                companions=[t for i,t in enumerate(available) if i!=index and t['rows'] is not None]
                if table['rows'] is None:
                    proof=table['obstruction']
                else:
                    family=tuple(frozenset((rows,)) for rows in table['rows'])
                    proof=algorithm.solve(types,target,table['types'],family,companions,.5)
                # Missing companion rows cannot justify an exhaustive-search
                # negative: extra semijoin/antijoin restrictions might help.
                # These canonical necessary obstructions are independent of
                # ALL row restrictions, including unmaterialized companions.
                independent=(proof.get('proof_kind') in ('row_cardinality','row_support') or
                    proof.get('nonrecoverable_proof') in ('no typed projection exists',
                        'a deterministic transform cannot increase model-family cardinality'))
                if unknown_companions and proof.get('recoverable') is False and not independent:
                    proof=dict(status='unknown',recoverable=None,
                        reason='unmaterialized companion values prevent a complete restriction search',
                        restricted_search=proof)
                receipt['searches'].append(dict(assignment=assignment,source=table['identity'],
                    source_receipt=table['receipt'],companion_indices=[i for i in range(len(available)) if i!=index],
                    unmaterialized_companion_indices=unknown_companions,
                    row_restriction_independent_obstruction=independent,
                    proof=proof))
        proofs=[item['proof'] for item in receipt['searches']]
        complete=(len(proofs)==(len(packets)+len(headers))*len(record['evaluation']['kept_assignments'])
                  and all(p.get('status')=='determined' and p.get('recoverable') is False for p in proofs))
        receipt.update(complete=complete,redundant=algorithm.truth_of_searches(proofs,complete),
            source_count=len(packets)+len(headers),assignment_count=len(record['evaluation']['kept_assignments']))
        if receipt['redundant'] is True:
            receipt['reason']='current redundancy search found a verified recovery of X from an available source'
        elif not complete:
            receipt['reason']='current nonredundancy proof has an incomplete or bounded source search'
    except (ev.arclog.Refusal,ValueError,KeyError,IndexError,TypeError,OSError) as error:
        receipt['reason']='current nonredundancy evidence unavailable: '+str(error)
    ev.target_cache[key]=receipt
    return receipt


def union_proof(ev,record,adapter,proof,output,gold,columns,ntrain,ntest,fields):
    nonredundancy=union_nonredundancy(ev,record,adapter,ntrain,ntest)
    failure=union_nonredundancy_result(nonredundancy)
    if failure is not None:return failure
    L=ev.legacy;canonical=json.loads(json.dumps(proof['canonical']));found=False
    def disable(body):
        nonlocal found
        out=[]
        for atom in body:
            out.append(atom)
            if atom[0]=='&X':
                labels=site_bindings(L,atom,adapter['input']['binding']['callable_template'])
                available=[v.lstrip('*^') for v in labels.values() if v!='0']
                if not available:raise Incomplete('zero-column X-branch contribution unavailable')
                out.append(['!=',available[0],available[0]]);found=True
            elif atom[0]=='OR':
                atom[1:]=[disable(branch) for branch in atom[1:]]
        return out
    try:canonical[2:]=disable(canonical[2:])
    except Incomplete as error:return dict(status='unknown',reason=str(error))
    if not found:return dict(status='unknown',reason='union has no positive X-reading branch')
    program,form,_=prepare(L,record,L.unparse(canonical),adapter)
    replay,groups,cols=_replay_groups(ev,record,program,form,ntrain,ntest,dict(kind='union-counterfactual',clause=L.unparse(canonical)))
    if groups is None or groups['missing']:return dict(status='unknown',reason='union counterfactual lacks kept contexts',artifact=replay['artifact'])
    equality=(catalog.equality(groups['groups'],cols,gold,fields,gold['catalog_reference'],explicit=output)
              if 'catalog_reference' in gold else compare(groups['groups'],cols,gold['groups'],fields,explicit=output))
    if equality['status']=='unknown':return dict(status='unknown',reason='union contribution comparison incomplete',artifact=replay['artifact'])
    # Equality here only says X was unnecessary. It supplies no evidence that
    # an X-reading branch actually ran; evaluate applies the common partial gate.
    return dict(status='union_X_contributes' if equality['status']=='mismatch' else 'partial',
                needed_rows=equality['status']=='mismatch',nonredundant=True,redundant=False,
                nonredundancy=nonredundancy,
                one_row_per_X=True,restrictions_only=True,artifact=replay['artifact'])


def alternative(ev,result,record,adapter,candidate,columns,store,ntrain,ntest,target):
    if not any(a[0]=='&X' for a in atoms(ev.legacy.parse(result['submitted_clause'])[2:])):
        result.update(outcome='did not verify',reason='continuation must read X');return result
    train={k:v for k,v in candidate['groups'].items() if k[1]==1}
    if any(not rows for family in train.values() for rows in family):
        result.update(outcome='did not verify',reason='continuation has an empty train table');return result
    unknown=[]
    references=list(target['live_available'])
    for groups,fields,ref,receipt in list(references):
        if ref['target_id'].endswith(': ex_input'):
            indices=[i for i,f in enumerate(fields) if f['type']!='Example']
            projected={k:{frozenset(tuple(row[i] for i in indices) for row in rows) for rows in family}
                       for k,family in groups['groups'].items()}
            references.append((dict(groups,groups=projected),[fields[i] for i in indices],dict(ref,target_id='input'),receipt))
    for groups,fields,ref,receipt in references:
        if len(fields)!=len(columns):continue
        axis={k:v for k,v in groups['groups'].items() if k[1]==1}
        required={k for k in groups['required'] if k[1]==1}
        eq=compare(train,columns,axis if set(axis)==required else {},fields)
        if eq['status']=='equal':
            result.update(outcome='did not verify',reason='continuation equals available table '+ref['target_id']);return result
        if eq['status']=='unknown':unknown.append('available replay has no compatible kept entry: '+ref['target_id'])
    try:
        mutant=dict(record,gold_sexp=record['mutant_sexp'])
        x,receipt=observe_gold(ev,mutant,adapter,adapter['input']['binding'],ntrain,ntest)
        fields=adapter['input']['binding']['projected_schema']
        if len(fields)==len(columns):
            eq=compare(train,columns,{k:v for k,v in x['groups'].items() if k[1]==1},fields)
            if eq['status']=='equal':result.update(outcome='did not verify',reason='continuation equals X');return result
            if eq['status']=='unknown':unknown.append('X replay has no compatible kept entry')
    except (ValueError,KeyError,TypeError) as error:unknown.append(str(error))
    if not target.get('catalog_complete',False):unknown.append('gold-case replay stopped or has no compatible kept entry')
    if unknown:
        result.update(outcome='unknown',reason='continuation comparison incomplete',comparison_gaps=sorted(set(unknown)));return result
    result.update(outcome='continuation passed',continuation_passed=True)
    return result
