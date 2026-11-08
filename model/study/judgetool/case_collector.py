"""Additive Step 3 case cache. Does not modify Step 2 modules or their globals.

One gold replay per case/program/kept/settings identity. Observers are appended
before OUT, leaving every original declaration's form index unchanged. The
returned JSON transport is unscoped; selection/projection is a separate step.
No evaluation is launched by importing this module.
"""
from copy import deepcopy
from functools import partial
import hashlib
import importlib.util
import json
from pathlib import Path
from types import FunctionType,SimpleNamespace
from weakref import WeakKeyDictionary

import sys as _study_sys
_study_sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT
from evaluator import sha
from tables import Incomplete,kept_groups,compare,projected_rows
from surface import prepare,tokens
from program_metadata import export_named_program,typed_fields,type_identity,bind_native_column_names
import catalog
import checks

_CACHE=WeakKeyDictionary()


def clear_cache(ev):
    """Release this evaluator's case bundles after the driver persists them."""
    return len(_CACHE.pop(ev,{}))


def _code_receipt():
    return dict(path=str(Path(__file__).resolve()),sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def encode_grouped(grouped):
    """Lossless JSON transport; no model union or cross-assignment flattening."""
    return dict(groups=[dict(context=list(k),models=[[[list(cell) for cell in row] for row in sorted(rows)]
            for rows in sorted(family,key=repr)]) for k,family in sorted(grouped['groups'].items())],
        required=[list(k) for k in sorted(grouped['required'])],missing=[list(k) for k in grouped['missing']],
        det_relations=list(grouped.get('det_relations',[])))


def decode_grouped(value):
    return dict(groups={tuple(g['context']):{frozenset(tuple(tuple(cell) for cell in row) for row in rows)
                for rows in g['models']} for g in value['groups']},
        required={tuple(k) for k in value['required']},missing=[tuple(k) for k in value['missing']],
        det_relations=value.get('det_relations',[]))


def _policy():
    path=CODE_ROOT/'judge3/catalog.py';spec=importlib.util.spec_from_file_location('_case_collector_scope',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def case_program(ev,record,context):
    """Canonical case source only; no kept acquisition, FITS or replay."""
    case=context.get('case',context.get('name',record['case']))
    text=context.get('gold_sexp') or context.get('source_program')
    if text is None and case==record['case']:text=record['gold_sexp']
    if text is None:
        import sys
        sys.path.insert(0,str(CODE_ROOT/'ast'))
        from check_stage1_all import inventory
        path=Path(context['catalogue_path'])
        path=(path if path.is_absolute() else DATA_ROOT/path).resolve()
        names,offsets,ids,flags=inventory(path.parents[2],record['task'],True)
        i=names.index(case);lo,hi=offsets[i:i+2]
        text=ev.task_evaluator(record['task']).from_stream(ids[lo:hi],[int(f) for f in flags[lo:hi]]).sexp()
    names=context.get('relation_source_names')
    if names is None and case==record['case']:names=record.get('relation_source_names')
    return case,text,names


def _context(ev,record,context,*,with_receipt=False):
    case,text,names=case_program(ev,record,context)
    values=context.get('kept_assignments')
    if values is None:values=(context.get('reference') or {}).get('evaluation',{}).get('kept_assignments')
    if values is None and case==record['case']:values=record['evaluation']['kept_assignments']
    observation=context.get('_gold_kept_receipt')
    if values is None:
        acquired=ev.acquire_gold_kept(record,case=case,program=text)
        observation=dict(acquired['receipt'],python_cached=acquired['python_cached'],
                         current_native_gold_kept_calls=acquired['native_gold_kept_calls'])
        if acquired['engine']!='ran':
            error=Incomplete('case own gold kept acquisition: '+acquired['reason']+'; artifact='+acquired['artifact'])
            error.receipt=observation
            raise error
        values=acquired['kept_assignments']
    resolved=(case,text,values,names)
    return resolved+(observation,) if with_receipt else resolved


def _body_binding(view):
    columns=sorted(view['columns'],key=lambda c:c['body_column'])
    if [c['body_column'] for c in columns]!=list(range(len(columns))):
        raise Incomplete('native BODY physical columns are not a complete indexed schema')
    spellings=[c['label_spelling'] for c in columns]
    if any(not isinstance(n,str) for n in spellings) or len(set(spellings))!=len(spellings):
        raise Incomplete('BODY scalar names have no unique native scoped binding')
    schema=[];fields=[];sites=[]
    for i,c in enumerate(columns):
        identity=dict(label_id=c['label_id'],source_label_spelling=c['label_spelling'],
                      body_path=view['body_path'],owner_path=view['owner_path'])
        schema.append(dict(index=i,type=c['type'],native_label_identity=identity))
        fields.append(dict(physical_index=i,field_name=c['label_spelling'],type=c['type'],
            source_body_column=i,native_label_identity=identity,
            callable_row_path=[dict(kind='written',name=c['label_spelling'])]))
        sites.append([':'+c['label_spelling'],'*V'+str(i)])
    return dict(kind=view['kind'],input_port=view['input_port'],body_path=view['body_path'],
        owner_path=view['owner_path'],source_body_schema=schema,projected_schema=fields),sites


def _observed_bindings(ev,source_export,observed):
    """Use exact replay-program witnesses for unchanged original definitions.

    Re-decoding a parsed program discards its named Layout. It is not the
    representation replay_program evaluates. Added observers also have their
    own reader bindings, so export the exact augmented checked program and
    authenticate original relation identities before taking its witnesses.
    The original source-name map cannot be attached to the augmented stream.
    """
    program=ev.arclog.StudyProgram.from_sexp(observed,ev.settings)
    actual=json.loads(ev.arclog.study_program_export_json(program))
    def identity(definition):
        selector=definition['native_selector']
        return tuple(str(selector[key]) for key in ('form','point','relation'))
    indexed={}
    for definition in actual['definitions']['native_relations']:
        indexed.setdefault(identity(definition),[]).append(definition)
    export=deepcopy(source_export)
    for definition in export['definitions']['native_relations']:
        matches=indexed.get(identity(definition),[])
        if (len(matches)!=1 or matches[0]['relation']!=definition['relation']
                or matches[0]['definition_path']!=definition['definition_path']):
            raise Incomplete('observed program changed an original native relation identity')
        witness=matches[0]
        definition['column_witnesses']=deepcopy(witness['column_witnesses'])
        definition['column_witness_status']=witness['column_witness_status']
    return export


def _supported_observers(ev,forms,observers,plans,source_export,gaps):
    """A refused observer cannot make unrelated original tables unavailable.

    Native checking/export owns all scope, pooled/lifted and column rules.
    Valid combined programs take one metadata pass. On failure, retain a
    supported prefix, checking each addition in the actual combined context.
    This compiles metadata only; the caller still performs just ONE replay.
    """
    def assembled(items):
        return '\n'.join(forms[:-1]+items+[forms[-1]])
    observed=assembled(observers)
    try:
        return observed,plans,_observed_bindings(ev,source_export,observed)
    except (ev.arclog.Refusal,ValueError,KeyError,IndexError,TypeError):
        pass
    supported=[];kept=[];export=source_export
    for observer,plan in zip(observers,plans):
        candidate=assembled(supported+[observer])
        try:
            candidate_export=_observed_bindings(ev,source_export,candidate)
        except (ev.arclog.Refusal,ValueError,KeyError,IndexError,TypeError) as error:
            gaps.append(dict(kind='body',body_path=plan['body_path'],
                phase='native_observer_validation',reason=str(error),error_type=type(error).__name__))
            continue
        kept.append(dict(plan,observer_form=len(forms)-1+len(supported)))
        supported.append(observer);export=candidate_export
    return assembled(supported),kept,export


def acquire_case(ev,record,case_context,ntrain,ntest,*,include_bodies=True,acquire_values=True):
    """Return JSON-serializable unscoped case tables/export/own-kept receipt.

    case_context: case/name, gold_sexp/source_program, kept_assignments (or
    reference.evaluation.kept_assignments), optional relation_source_names.
    Missing kept values require a complete native gold_kept TRAIN FITS walk
    with complete DET coverage; its separately charged receipt is retained.
    Other cases may supply catalogue_path instead of source text. Cache never
    includes the pair id, mutation point, adapter or later-table selection.
    A bounded/failed collection is cached too; it is not silently retried.
    include_bodies=False collects original native tables only, for exporters
    that acquire their point G independently. acquire_values=False returns only
    original table metadata; typed consumers select and decode their own TRAIN
    entries. No grouped-value completeness is certified. Both scope flags are
    part of cache identity.
    """
    if type(include_bodies) is not bool:raise ValueError('include_bodies must be boolean')
    if type(acquire_values) is not bool:raise ValueError('acquire_values must be boolean')
    if include_bodies and not acquire_values:
        raise ValueError('metadata-only case inventory cannot include BODY observers')
    case,text,values,names,kept_observation=_context(ev,record,case_context,with_receipt=True)
    identity=dict(task=record['task'],case=case,program=sha(text),kept=sha(values),
                  settings=sha(ev.receipt),ntrain=ntrain,ntest=ntest,
                  include_bodies=include_bodies,acquire_values=acquire_values,collector=_code_receipt()['sha256'])
    key=sha(identity);cache=_CACHE.setdefault(ev,{})
    if key in cache:return cache[key]
    if names is not None and (names.get('task'),names.get('case'))!=(record['task'],case):
        raise Incomplete('case source-name map belongs to another task/case')
    L=ev.legacy
    # Keep the same parsed named Layout as replay_program, rather than a
    # separately decoded anonymous-slot AST with positional column headers.
    program=ev.arclog.StudyProgram.from_sexp(text,ev.settings)
    naming=json.dumps(names) if names is not None else program.relation_source_names_json(
        str(MAIN_ROOT/'work/arclog/gen'),record['task'],case)
    export=export_named_program(ev,program,naming)
    forms=L.split_forms(text);parsed=[L.parse(f) for f in forms]
    outs=[i for i,f in enumerate(parsed) if f[0]=='OUT']
    if outs!=[len(forms)-1]:raise Incomplete('case collection requires a final single OUT form')
    observers=[];plans=[];gaps=[];occupied=set(tokens(parsed))
    own=dict(record,case=case,gold_sexp=text,mutant_sexp=text,
             evaluation=dict(record['evaluation'],kept_assignments=values))
    for view in (export['body_views'] if include_bodies else ()):
        try:
            binding,sites=_body_binding(view)
            clause=L.unparse(['RULE','&fix',['&X']+sites])
            binding['callable_template']=L.unparse(['&X']+sites)
            body_record=dict(own,point=view['body_path'])
            adapter=dict(input=dict(binding=binding),relation_tokens={})
            _,_,proof=prepare(L,body_record,clause,adapter)
            name='&JudgeCaseBody'+str(len(plans))
            while name in occupied:name+='Q'
            occupied.add(name);observer=L.parse(proof['inserted']);observer[1]=name
            form=len(forms)-1+len(observers)
            observers.append(L.unparse(observer))
            plans.append(dict(body_path=view['body_path'],view=view,fields=binding['projected_schema'],
                              observer_name=name,observer_form=form))
        except (ValueError,KeyError,IndexError,TypeError) as error:
            gaps.append(dict(kind='body',body_path=view['body_path'],phase='observer_preparation',
                             reason=str(error),error_type=type(error).__name__))
    if observers:
        observed,plans,export=_supported_observers(ev,forms,observers,plans,export,gaps)
    else:
        observed=text
    if L.split_forms(observed)[:len(forms)-1]!=forms[:-1]:
        raise Incomplete('case observer changed an original source form')
    replay=ev.replay_program(own,observed,0,candidate=dict(kind='all-gold-case-tables-and-bodies',identity=identity),retain_all=True)
    receipt=dict(schema='judge-case-receipt-v1',identity=identity,collector=_code_receipt(),
        source='gold_full_replay',gold_program_sha256=sha(text),observer_program_sha256=sha(observed),
        kept_context_sha256=sha(values),artifact=replay['artifact'],engine=replay['engine'],
        gold_replays=1,observer_count=len(plans),include_bodies=include_bodies,
        acquire_values=acquire_values,settings=ev.receipt,
        column_witness_program_sha256=sha(observed),
        column_witness_source='exact parsed observed program; unchanged original relation identities')
    if kept_observation is not None:receipt['kept_observation']=kept_observation
    bundle=dict(schema='judge-case-bundle-v1',task=record['task'],case=case,ntrain=ntrain,ntest=ntest,
        program_sha256=sha(text),kept_context_sha256=sha(values),kept_assignments=values,
        tables=[],bodies=[],export=export,receipt=receipt,gaps=gaps,complete=False)
    if replay['engine']!='ran':
        gaps.append(dict(kind='replay',reason=replay.get('reason','gold replay stopped')))
        cache[key]=bundle;return bundle
    native=ev.captures[-1]['native'];ts=native['tables'];definitions=export['definitions']['native_relations']
    # Original declarations remain before every observer, so their form paths
    # and native relation slots are unchanged; exclude synthetic observer tables.
    for table in range(len(ts['form'])):
        form=str(ts['form'][table]);head=form.split('.',1)[0]
        if head and (not head.isdigit() or int(head)>=len(forms)-1):continue
        selector={k:ts[k][table] for k in ('form','point','relation','fact')}
        definitions_here=[d for d in definitions if all(str(selector[k])==str(v)
            for k,v in d['native_selector'].items() if k in ('form','point','relation'))]
        grouped=kept_groups(L,native,table,own,ntrain,ntest) if acquire_values else None
        fields=[dict(field_name=n,type=t) for n,t in zip(ts['column_names'][table],ts['column_types'][table])]
        fields=typed_fields(ev,own,fields)
        label=(definitions_here[0]['display_name'] if definitions_here else ts['fact'][table] or ts['relation_name'][table] or 'body')
        schema=deepcopy(native['_native_reader'].schema(table))
        for definition in definitions_here:
            witnesses=bind_native_column_names(ev,own,definition,schema,artifact=replay['artifact'],table=table)
            definition['column_witnesses']=witnesses
            if (len(witnesses)!=len(schema) or
                    any(w['physical_column']!=c['index'] or w['native_name']!=c['name']
                        or type_identity(ev,own,w['type'])[0]!=type_identity(ev,own,c['type'])[0]
                        for w,c in zip(witnesses,schema))):
                evidence=dict(case=case,selector=selector,table=table,witnesses=witnesses,
                              native_schema=schema,replay_artifact=replay['artifact'])
                folder=ev.artifacts/('schema-identity-'+sha(evidence))
                folder.mkdir(exist_ok=True)
                (folder/'mismatch.json').write_text(json.dumps(evidence,indent=2)+'\n')
                raise Incomplete('observed native column witnesses differ from the replay table schema; '
                                 'artifact='+str(folder))
        bundle['tables'].append(dict(table_id='native:'+str(table),native_table=table,selector=selector,fields=fields,
            native_schema=schema,
            source_name=label,grouped=encode_grouped(grouped) if grouped is not None else None,receipt=dict(case=case,artifact=replay['artifact'],table=table,
            source='gold_full_replay',kept_context_sha256=sha(values),
            complete=not grouped['missing'] if grouped is not None else None,
            values_acquired=acquire_values)))
    for plan in plans:
        try:
            matches=[t for t,f in enumerate(ts['form']) if str(f)==str(plan['observer_form'])]
            if len(matches)!=1:raise Incomplete('observer table is missing or ambiguous')
            table=matches[0];grouped=kept_groups(L,native,table,own,ntrain,ntest)
            columns=list(ts['column_names'][table]);indices=[columns.index('V'+str(i)) for i in range(len(plan['fields']))]
            if [ts['column_types'][table][i] for i in indices]!=[f['type'] for f in plan['fields']]:
                raise Incomplete('observer physical types differ from native BODY view')
            grouped=dict(grouped,groups={k:{frozenset(tuple(row[i] for i in indices) for row in rows) for rows in family}
                                          for k,family in grouped['groups'].items()})
            bundle['bodies'].append(dict(body_path=plan['body_path'],fields=typed_fields(ev,own,plan['fields']),grouped=encode_grouped(grouped),
                receipt=dict(case=case,source='gold_full_replay',artifact=replay['artifact'],observer_table=table,
                    body_path=plan['body_path'],label_ids=[f['native_label_identity']['label_id'] for f in plan['fields']],
                    complete=not grouped['missing'])))
        except (ValueError,KeyError,IndexError,TypeError) as error:
            gaps.append(dict(kind='body',body_path=plan['body_path'],reason=str(error)))
    bundle['complete']=not gaps
    cache[key]=bundle
    return bundle


def _project_body(ev,bundle,record,adapter):
    binding=adapter['comparison_target']['binding'];path=binding['body_path']
    matches=[b for b in bundle['bodies'] if b['body_path']==path]
    if len(matches)!=1:raise Incomplete('single-replay case bundle lacks the requested gold BODY')
    body=matches[0];by_label={f['native_label_identity']['label_id']:i for i,f in enumerate(body['fields'])}
    indices=[]
    for field in binding['projected_schema']:
        if field['source_body_column'] is None:indices.append(None);continue
        identity=field['native_label_identity']
        if identity.get('body_path',path)!=path:raise Incomplete('projected label belongs to another BODY scope')
        label=identity['label_id']
        if label not in by_label:raise Incomplete('projected native LabelId absent from cached BODY')
        indices.append(by_label[label])
    grouped=decode_grouped(body['grouped'])
    groups={k:{frozenset(projected_rows(ev.legacy,rows,indices)) for rows in family}
            for k,family in grouped['groups'].items()}
    grouped=dict(grouped,groups=groups)
    receipt=dict(body['receipt'],projection=indices,fields=binding['projected_schema'],
        original_source_sha256=sha(record),gold_program_sha256=sha(record['gold_sexp']),
        observer_program_sha256=bundle['receipt']['observer_program_sha256'],
        kept_context_sha256=sha(record['evaluation']['kept_assignments']),
        layout_sha256=sha(binding['projected_schema']),binding_sha256=sha(binding),
        train_complete=not any(k[1]==1 for k in grouped['missing']),
        test_complete=not any(k[1]==2 for k in grouped['missing']),
        acquisition='single full-case gold replay with cached BODY observer')
    ref=dict(target_id='G',case=record['case'],role='point',body_path=path)
    return grouped,binding['projected_schema'],ref,receipt


def select_pair(casebundle,record,adapter,*,ev,point_only=False):
    """No replay: select point G + later same-case/all-other-case actual tables.

    casebundle is one bundle or a sequence of case bundles. ev supplies ONLY
    the existing lossless projector's namespace; no engine method is called.
    Returns grouped Python sets for canonical checker/comparator consumers.
    JSON transport remains in the unscoped bundles. point_only leaves table
    values in that transport when the caller consumes only the projected G.
    """
    bundles=[casebundle] if isinstance(casebundle,dict) else list(casebundle)
    point=None;targets=[];available=[];gaps=[];receipts=[]
    policy=None if point_only else _policy()
    own=[b for b in bundles if b['case']==record['case'] and b['task']==record['task']]
    if len(own)!=1:raise Incomplete('selection requires exactly one own-case bundle')
    if own[0]['program_sha256']!=sha(record['gold_sexp']) or own[0]['kept_context_sha256']!=sha(record['evaluation']['kept_assignments']):
        raise Incomplete('own case bundle program/kept identity differs from pair')
    try:point=_project_body(ev,own[0],record,adapter)
    except Incomplete as error:gaps.append(dict(case=record['case'],kind='point',reason=str(error)))
    allowed={d['definition']['display_name'] for d in adapter['availability']['definitions']}
    for bundle in bundles:
        if bundle['task']!=record['task']:raise Incomplete('case bundle belongs to another task')
        same=bundle['case']==record['case'];receipts.append(bundle['receipt'])
        # Unsupported unrelated BODY observers do not invalidate actual table
        # values. Missing point projection is separately required above.
        gaps.extend(g for g in bundle['gaps'] if g.get('kind')=='replay')
        if point_only:continue
        for item in bundle['tables']:
            grouped=decode_grouped(item['grouped']);fields=deepcopy(item['fields'])
            ref=dict(target_id=bundle['case']+': '+item['source_name'],case=bundle['case'],
                role='later' if same else 'other_case',ignore_names=not same,native_selector=item['selector'],
                table_id=item['table_id'],native_schema=deepcopy(item['native_schema']))
            receipt=dict(item['receipt'],original_source_sha256=sha(record),
                observer_program_sha256=bundle['receipt']['observer_program_sha256'],
                gold_program_sha256=bundle['program_sha256'],target_id=ref['target_id'],
                layout_sha256=sha(fields),train_complete=not any(k[1]==1 for k in grouped['missing']),
                test_complete=not any(k[1]==2 for k in grouped['missing']))
            eligible=not same
            if same:
                ts={k:[v] for k,v in item['selector'].items()}
                eligible=policy.same_case_after(ts,0,adapter['comparison_target']['binding'],bundle['export'])
                if eligible is None:gaps.append(dict(case=bundle['case'],kind='scope',reason='native source order unresolved',table=item['table_id']))
                if item['source_name'] in allowed or item['selector']['fact'] in ('ex_input','ex_output'):
                    available.append((grouped,fields,ref,receipt))
            if not same:fields=[dict(f,field_name=None) for f in fields]
            grouped=dict(grouped,catalog_reference=ref)
            if eligible:targets.append((grouped,fields,ref,receipt))
    expected={c['name'] for c in adapter.get('all_case_targets',{}).get('cases',[])}
    missing_cases=expected-{b['case'] for b in bundles}
    gaps.extend(dict(case=c,kind='case',reason='case bundle not supplied') for c in sorted(missing_cases))
    selection=dict(schema='judge-pair-selection-v1',point=point,targets=targets,available=available,gaps=gaps,
        complete=not gaps and point is not None,case_receipts=receipts,source_sha256=sha(record),
        adapter_sha256=sha(adapter),ntrain=own[0]['ntrain'],ntest=own[0]['ntest'],collector=_code_receipt())
    if point_only:
        # Omitted relations are unrequested values, never complete empty tables.
        selection.update(selection_mode='point_only',requested_relations=['point'],
            omitted_values=['targets','available'],complete=False)
        selection['collector']=dict(selection['collector'],selection_mode='point_only')
    return selection


def compare_target(candidate,columns,grouped,fields,reference,*,relation='equal',explicit=None,seconds=10):
    """Canonical Cartesian cross-case comparison; equality is whole-table.

    Containment may project X. This is the unchanged catalog.equality bytecode
    with its compare dependency bound in an owned namespace, not module mutation.
    """
    if relation not in ('equal','contains'):raise ValueError('unsupported comparison relation')
    if relation=='equal' and len(explicit if explicit is not None else columns)!=len(fields):
        return dict(status='mismatch',reason='whole output arity differs',relation=relation)
    namespace=dict(catalog.equality.__globals__)
    namespace['compare']=partial(compare,relation=relation,seconds=seconds)
    function=FunctionType(catalog.equality.__code__,namespace,catalog.equality.__name__,catalog.equality.__defaults__,catalog.equality.__closure__)
    function.__kwdefaults__=dict(catalog.equality.__kwdefaults__ or {})
    return function(candidate,columns,grouped,fields,reference,explicit=explicit)


class _ReplayBudget:
    def __init__(self,ev,maximum):self._ev=ev;self.maximum=maximum;self.operations=[]
    def __getattr__(self,name):return getattr(self._ev,name)
    def replay_program(self,*args,**kwargs):
        if len(self.operations)>=self.maximum:
            return dict(engine='incomplete',artifact=None,reason='cached clause verification reached its mutant replay bound',seconds=0)
        result=self._ev.replay_program(*args,**kwargs)
        self.operations.append(dict(artifact=result['artifact'],engine=result['engine'],candidate=kwargs.get('candidate')))
        return result


def evaluate_cached(ev,record,clause,target,columns,selection,*,row_limit=100,max_mutant_replays=1,include_table=True):
    """Canonical checks.evaluate, cached gold values, one mutant replay by default.

    Isolated globals bind only gold acquisition to selection. No shared module
    or evaluator method is patched. Lib/union instrumentation that would exceed
    the declared mutant-operation cap stays unknown; no hidden second operation.
    include_table=False omits presentation only, avoiding row sorting/counts.
    """
    if selection['source_sha256']!=sha(record) or selection['adapter_sha256']!=sha(target['adapter']):
        raise Incomplete('cached pair selection source/adapter identity mismatch')
    if max_mutant_replays<1:raise ValueError('at least one mutant replay is required')
    def cached_gold(_ev,other_record,_adapter,binding,ntrain,ntest):
        point=selection['point']
        if point is None:raise Incomplete('cached selection has no compatible gold point')
        if other_record['gold_sexp']!=record['gold_sexp'] or sha(binding['projected_schema'])!=sha(point[1]):
            raise Incomplete('requested gold observer is outside cached point binding')
        if (ntrain,ntest)!=(selection['ntrain'],selection['ntest']):raise Incomplete('cached example axes differ')
        # The comparator checks keys present in its target, so an incomplete
        # target must never reach it as if it were a complete gold observation.
        required={(a,kind,i) for a in range(len(record['evaluation']['kept_assignments']))
                  for kind,count in ((1,ntrain),(2,ntest)) for i in range(count)}
        grouped=point[0]
        if (not required or grouped.get('missing')
                or set(grouped.get('required',()))!=required
                or set(grouped.get('groups',{}))!=required
                or any(not family for family in grouped['groups'].values())):
            raise Incomplete('cached gold point lacks exact required kept train/test contexts')
        return point[0],point[3]
    def cached_targets(*args,**kwargs):
        return selection['targets'],selection['gaps'],selection['case_receipts'],selection['available']
    namespace=dict(checks.evaluate.__globals__)
    namespace.update(observe_gold=cached_gold,live_targets=SimpleNamespace(acquire=cached_targets))
    function=FunctionType(checks.evaluate.__code__,namespace,checks.evaluate.__name__,checks.evaluate.__defaults__,checks.evaluate.__closure__)
    function.__kwdefaults__=dict(checks.evaluate.__kwdefaults__ or {})
    proxy=_ReplayBudget(ev,max_mutant_replays)
    result=function(proxy,record,clause,target,columns,explore=False,row_limit=row_limit,include_table=include_table)
    result['cached_case_verification']=dict(collector=_code_receipt(),gold_replays=0,
        mutant_replays=len(proxy.operations),max_mutant_replays=max_mutant_replays,operations=proxy.operations,
        selection_source_sha256=selection['source_sha256'],selection_adapter_sha256=selection['adapter_sha256'])
    return result
