"""Mechanical observations through the shared native acquisition/comparator.

No row equality, Ident renaming, INIT projection or resolver closure is copied.
Incomplete acquisition/comparison is explicit unknown evidence.
"""
import copy
from clause_evidence import digest
from run import pair_key


def build(ev,record,metadata,*,ntrain,ntest,receipt_ref,baseline_limit=32):
    from tables import TargetStore,compare,contains,kept_groups
    from checks import observe_gold
    import catalog
    adapter=metadata['adapter'];store=TargetStore(ev.legacy,ev.run.parent.parent)
    evidence=dict(schema='mech-grade-evidence-v1',pair_id=digest(pair_key(record)),source_sha256=digest(record),
                  kind=record['kind'],program={},comparisons=dict(point={},targets=[],reader_difference={}),
                  search=dict(status='not_covered',complete=False,settled_space=False,unvisited=None,receipt_ref=receipt_ref),
                  sibling=None,redundant=None,clauses=[],mechanical_clauses=[],issues=[])
    from corpus_index import filter_labels
    evidence.update(filter_labels(record))
    refs,complete,gaps=catalog.entries(adapter)
    evidence['target_catalog']=dict(complete=complete,receipt_ref=receipt_ref,gaps=gaps)
    receipts={};x=None;gold=None;xf=None;gf=adapter['comparison_target']['binding']['projected_schema']
    def check(eq):
        return dict(train=eq.get('train')=='equal',test=eq.get('test')=='equal',complete=eq.get('status')=='equal',
                    kept_contexts_complete=True,test_target='gold_full_replay',receipt_ref=receipt_ref)
    try:
        x,xf=store.mutant_input(record,adapter,ntrain,ntest)
        gold,receipts['G']=observe_gold(ev,record,adapter,adapter['comparison_target']['binding'],ntrain,ntest)
        columns=[(f.get('field_name',str(i)),f['type']) for i,f in enumerate(xf)]
        eq=compare(x['groups'],columns,gold['groups'],gf)
        evidence['comparisons']['targets'].append(dict(target_id='G',equal=eq['status']=='equal',comparison=eq,**check(eq)))
        # Containment/lossy refers to the saved train point relation. Test gates
        # apply to positives independently; a bound is never a missing-row proof.
        xt={k:v for k,v in x['groups'].items() if k[1]==1};gt={k:v for k,v in gold['groups'].items() if k[1]==1}
        inclusion=contains(xt,columns,gt,gf)
        evidence['comparisons']['point']=dict(complete=inclusion['status']!='unknown',
            X_holds_every_gold_row=True if inclusion['status']=='contains' else False if inclusion['status']=='mismatch' else None,
            lossy=True if inclusion['status']=='mismatch' else False if inclusion['status']=='contains' else None,
            receipt_ref=receipt_ref,comparison=inclusion)
        for reference in refs:
            if reference.get('role')=='point':continue
            try:
                target,fields,proof=catalog.acquire(store,record,adapter,reference,ntrain,ntest)
                eq=catalog.equality(x['groups'],columns,target,fields,reference)
                receipts[reference['target_id']]=proof
                evidence['comparisons']['targets'].append(dict(target_id=reference['target_id'],equal=eq['status']=='equal',comparison=eq,**check(eq)))
                if eq['status']=='unknown':evidence['issues'].append('bounded target '+reference['target_id'])
            except Exception as error:
                evidence['issues'].append('target unavailable '+reference['target_id']+': '+str(error))
        # Field selection is native metadata, not a name/ordinal guess. Compare
        # whole reader-visible tuples, preserving correlations among columns.
        projection=adapter.get('reader_projection',{})
        if projection.get('status')=='complete' and projection.get('source_sha256')==digest(record):
            pairs=projection['fields'];xi=[p['mutant_physical_index'] for p in pairs];gi=[p['gold_physical_index'] for p in pairs]
            xg={k:{frozenset(tuple(r[i] for i in xi) for r in rows) for rows in family} for k,family in x['groups'].items()}
            gg={k:{frozenset(tuple(r[i] for i in gi) for r in rows) for rows in family} for k,family in gold['groups'].items()}
            fields=[gf[i] for i in gi];cols=[(f'R{i}',xf[j]['type']) for i,j in enumerate(xi)]
            eq=compare(xg,cols,gg,fields,explicit=[c[0] for c in cols])
            evidence['comparisons']['reader_difference']=dict(complete=eq['status']!='unknown',
                read_difference=eq['status']=='mismatch' if eq['status']!='unknown' else None,
                receipt_ref=receipt_ref,projection=projection,comparison=eq)
        else:evidence['issues'].append('native reader physical field projection unavailable')
    except Exception as error:evidence['issues'].append('point acquisition/comparison unavailable: '+str(error))
    evidence['program'],receipts['program']=program_fit(ev,record,adapter,ntrain,ntest,receipt_ref)
    # Bounded baselines include lossy and witness-positive pairs. A positive
    # is independently compared against complete targets. No finite miss is False.
    if x is not None and gold is not None:
        baseline=[]
        sources=[dict(name='input',atom='(input (:P *V0) (:Col *V1))'),
                 dict(name='ex_input',atom='(ex_input (:E *V0) (:P *V1) (:Col *V2))'),
                 dict(name='ex_output',atom='(ex_output (:E *V0) (:P *V1) (:Col *V2))')]
        for ref in adapter.get('availability',{}).get('definitions',[]):
            template=ref.get('table_receipt',{}).get('callable_atom')
            if template and ref.get('status')=='complete':
                atom=ev.legacy.parse(template)
                atom[0]=ref['definition']['source_name']
                sources.append(dict(name=atom[0],atom=ev.legacy.unparse(atom)))
        for source in sources[:baseline_limit]:
            proof=dict(source=source['name'],sibling=None,redundant=None)
            try:
                groups,cols,replay=baseline_observer(ev,record,source['atom'],ntrain,ntest)
                proof['replay']=replay
                if groups is None or groups['missing']:raise ValueError('baseline compatible contexts incomplete')
                for name,target,target_fields in (('sibling',gold,gf),('redundant',x,xf)):
                    eq=compare(groups['groups'],cols,target['groups'],target_fields)
                    proof[name+'_comparison']=eq
                    if eq['status']=='equal':proof[name]=True;evidence[name]=True
            except Exception as error:proof['reason']=str(error)
            baseline.append(proof)
        receipts['baselines']=dict(visited=baseline,complete=False,reason='bounded single-clause source/projection layer; broader selector/lib searches unvisited, absence not proved')
    evidence['native_receipts']=receipts
    return evidence


def program_fit(ev,record,adapter,ntrain,ntest,receipt_ref):
    """Native complete train verdict + conservative task-output equality gate.

    Exact task-grid encoding is Position's documented four margins, Color.
    Comparisons use the ONE shared comparator. Unsupported accepted-set/task
    formats remain unknown, never a false fit or a synthetic held-out output.
    """
    from tables import kept_groups,compare,task_output_rows
    L=ev.legacy;forms=L.split_forms(record['mutant_sexp'])
    point=next((i for i,f in enumerate(forms) if L.parse(f)[0]=='OUT'),None)
    result=dict(complete=False,fits_train=None,fits_test=None,refused=False,receipt_ref=receipt_ref)
    if point is None:return result,dict(reason='mutant has no OUT')
    replay=ev.replay_program(record,record['mutant_sexp'],point,candidate=dict(kind='mutant-fit-OUT'))
    if replay['engine']=='refused':
        result.update(complete=True,refused=True);return result,replay
    if replay['engine']!='ran':return result,replay
    try:
        native=ev.captures[-1]['native'];table=replay['kept_coverage']['table']
        observed=kept_groups(L,native,table,record,ntrain,ntest)
        if observed['missing']:return result,dict(replay=replay,reason='OUT compatible contexts missing')
        task=__import__('json').loads(__import__('pathlib').Path(adapter['source']['task_path']).read_text())
        expected={};missing=[]
        for kind,key in ((1,'train'),(2,'test')):
            for i,pair in enumerate(task[key]):
                rows=task_output_rows(pair.get('output'))
                if rows is None:
                    missing.append((kind,i));continue
                for a in range(len(record['evaluation']['kept_assignments'])):expected[(a,kind,i)]={rows}
        columns=list(zip(native['tables']['column_names'][table],native['tables']['column_types'][table]))
        fields=[dict(field_name='P',type='Position'),dict(field_name='Col',type='Color')]
        comparisons={}
        for kind,name in ((1,'fits_train'),(2,'fits_test')):
            required={k for k in observed['required'] if k[1]==kind}
            if not required or any(k not in expected for k in required):continue
            groups={k:observed['groups'][k] for k in required};truth={k:expected[k] for k in required}
            eq=compare(groups,columns,truth,fields)
            comparisons[name]=eq
            if eq['status']=='equal':result[name]=True
            elif eq['status']=='mismatch':
                # A test may permit a second output grid; equality failure alone
                # is not a fit failure. Native train closed-candidate verdicts
                # below handle accepted-set/tiebreak semantics for train.
                if kind==1:result[name]=False
                else:
                    # A necessary test-fit condition is that every required
                    # input has SOME model giving its expected output. Ask the
                    # shared comparator on each complete model, never decode a
                    # grid or equate Ident cells in Python.
                    absent=False
                    for key in required:
                        hits=[compare({key:{model}},columns,{key:truth[key]},fields)
                              for model in groups[key]]
                        if hits and all(h['status']=='mismatch' for h in hits):absent=True
                    if absent:result[name]=False
        outputs=record['evaluation'].get('outputs',[])
        native_train=[t for o in outputs for t in o.get('mutant',{}).get('train',[])]
        if (len(outputs)==len(record['evaluation']['kept_assignments'])
                and {o.get('assignment') for o in outputs}==set(range(len(outputs)))
                and all(o.get('mutant',{}).get('status')=='complete'
                        and {t.get('example') for t in o['mutant'].get('train',[])}==set(range(ntrain)) for o in outputs)
                and len(native_train)==ntrain*len(outputs)
                and all(type(t.get('fits')) is bool and t.get('fit_comparison')=='native_closed_candidate_set' for t in native_train)):
            result['fits_train']=all(t['fits'] for t in native_train)
        result['complete']=all(type(result[k]) is bool for k in ('fits_train','fits_test'))
        # Complete non-fit TRAIN alone suffices even where test truth is absent.
        if result['fits_train'] is False:result['complete']=True
        return result,dict(replay=replay,comparisons=comparisons,missing_task_outputs=missing,
                           authority='task file outputs; native margin encoding; shared comparator')
    except Exception as error:return result,dict(replay=replay,reason=str(error))


def baseline_observer(ev,record,atom,ntrain,ntest):
    """Single available source, mutant absent, through the same full gold replay.

    Source AST/port spelling comes from the shared callable receipt. Input facts
    execute in native per-example context, never by dropping Example in Python.
    """
    from checks import _replay_groups
    L=ev.legacy;forms=L.split_forms(record['gold_sexp'])
    at=next((i for i,f in enumerate(forms) if L.parse(f)[0]=='OUT'),None)
    if at is None:raise ValueError('gold baseline has no OUT')
    observer=L.unparse(['RULE','&fix',L.parse(atom)])
    program='\n'.join(forms[:at]+[observer]+forms[at:])
    goldrecord=dict(record,mutant_sexp=record['gold_sexp'])
    replay,groups,cols=_replay_groups(ev,goldrecord,program,at,ntrain,ntest,
                                     dict(kind='available-source-baseline',atom=atom))
    return groups,cols,replay
