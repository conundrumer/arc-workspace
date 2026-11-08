"""Mutant-derived DET facts through ReplayEvaluator's existing native APIs.

TRAIN authority is the native complete gold_kept walk of the MUTANT program.
TEST never selects assignments: gold_body observes those same TRAIN choices.
Task-grid row equality is sufficient positive TEST evidence; non-equal nonempty
rows remain unknown (no Python grid reader/accepted-set policy is implemented).
Later relation family comparisons are diagnostics, not assignment/fit proofs.
"""
from collections import defaultdict, OrderedDict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import time

from evaluator import sha, canonical
from study_paths import CODE_ROOT
from tables import Incomplete, read_table, compare, comparison_type, task_output_rows

SCHEMA = 'evaluator-det-later-fit-v1'


def _write(path, value):
    with path.open('w') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return dict(path=str(path.resolve()), sha256=digest)


def _digest_json(value):
    """Hash a JSON value without making another full serialized copy."""
    digest=hashlib.sha256()
    encoder=json.JSONEncoder(ensure_ascii=False,allow_nan=False,sort_keys=True,
                             separators=(',',':'))
    for part in encoder.iterencode(value):digest.update(part.encode('utf-8'))
    return digest.hexdigest()


def _report_ref(path, raw, fields):
    """Write consumed report facts and the hash of the exact native JSON text."""
    if not isinstance(raw,str):raise ValueError('native report is not JSON text')
    digest=hashlib.sha256()
    for offset in range(0,len(raw),1 << 20):
        digest.update(raw[offset:offset+(1 << 20)].encode('utf-8'))
    whole_sha=digest.hexdigest()
    ref=_write(path,dict(schema='evaluator-det-report-summary-v1',
                         whole_report_sha256=whole_sha,whole_report_hash_of='native JSON UTF-8',
                         fields=fields))
    ref['whole_report_sha256']=whole_sha
    return ref


def _code():
    root=Path(__file__).resolve().parent
    names=('derived_fit.py','evaluator.py','tables.py','gold_body.py','raw_body.py',
           'surface.py','program_metadata.py','runtime_compat.py','out_fit.py')
    paths=[root/name for name in names]+[CODE_ROOT/name for name in (
        'judge3/nonrender_metadata.py','judge3/det_metadata.py','judge3/render_pair.py',
        'judge3/catalog.py','judge2/render2/structured.py','judge2/render2/headers.py',
        'ast/run/native_tables.py','study_paths.py')]
    return {str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def _operation(ev, operations, name, path, invoke):
    item=dict(operation=name,table_work_cap=ev.work_cap,
              session_bytes=ev.receipt['session_bytes'],native_calls=1,artifact=str(path))
    operations.append(item);start=time.monotonic()
    try:
        result=invoke();item['returned']=True;return result
    except Exception as error:
        item['error']=f'{type(error).__name__}: {error}';raise
    finally:
        item['wall_seconds']=time.monotonic()-start


def _assignment_tests(ev, record, program, native_ev, report, task, folder, operations):
    from gold_body import _held_entries
    from out_fit import native_out_binding,out_body_projection
    binding,columns=native_out_binding(program)
    path=folder/'mutant-out.json'
    status,payload=_operation(ev,operations,'mutant.gold_body.OUT',path,
        lambda:native_ev.gold_body(program,binding['body_path'],canonical(report['kept_assignments'])))
    body=json.loads(status)
    body_ref=_report_ref(path,status,dict(status=body.get('status'),body_path=body.get('body_path'),
        owner_path=body.get('owner_path'),body_table=body.get('body_table'),
        body_table_packed=body.get('body_table_packed'),
        gold_observation_ref=body.get('gold_observation_ref'),
        gold_observation_cached=body.get('gold_observation_cached'),
        body_status=body.get('body_status'),
        body_coverage_complete=(body.get('body_coverage') or {}).get('complete'),
        body_coverage_examples=len((body.get('body_coverage') or {}).get('examples',[])),
        body_assignment_entries=len((body.get('body_assignment_map') or {}).get('entries',[]))))
    choices=ev.validate_gold_observation(program,body,record['task'],schema='arclog-study-gold-body-v1')
    if choices!=report['kept_assignments'] or body.get('gold_observation_ref')!=report.get('gold_observation_ref'):
        raise Incomplete('mutant OUT did not reuse the same native TRAIN FITS memo')
    if body.get('gold_observation_cached') is not True:
        raise Incomplete('mutant OUT lacks cached native TRAIN FITS evidence')
    if (body.get('body_path')!=binding['body_path'] or body.get('owner_path')!=binding['path']
            or body.get('body_table_packed') is not True
            or body.get('body_status',{}).get('status')!='complete'
            or body.get('body_coverage',{}).get('complete') is not True):
        raise Incomplete('mutant OUT BODY/model coverage incomplete')
    native=ev.legacy.native(payload);table=body['body_table']
    held=_held_entries(native,table,body,{i:[i] for i in range(len(choices))})
    reader=native['_native_reader'];schema=deepcopy(reader.schema(table))
    projection=out_body_projection(binding,columns,schema)
    axes=[(kind,i) for kind,section in ((1,'train'),(2,'test')) for i in range(len(task[section]))]
    required={(a,*axis) for a in range(len(choices)) for axis in axes}
    counts={}
    for example in body['body_coverage']['examples']:
        kind={'task':0,'train':1,'test':2}.get(example.get('example_kind'))
        index=example.get('example_index');models=example.get('model_counts')
        if (kind is None or type(index) is not int or example.get('status',{}).get('status')!='complete'
                or not isinstance(models,list) or len(models)!=len(choices)
                or any(type(n) is not int or n<0 for n in models)):
            raise Incomplete('OUT native example/model coverage malformed')
        destinations=axes if kind==0 else [(kind,index)]
        for a,n in enumerate(models):
            for axis in destinations:
                key=(a,*axis)
                if key not in required or key in counts:raise Incomplete('OUT native axes outside task or duplicated')
                counts[key]=n
    if set(counts)!=required:raise Incomplete('OUT native coverage lacks exact TRAIN+TEST axes')
    groups=defaultdict(set);observed_models=defaultdict(set);entry_count=0
    entries_digest=hashlib.sha256()
    for entry in read_table(ev.legacy,native,table):
        entry_count+=1
        entries_digest.update(bytes.fromhex(_digest_json(entry)))
        rows=frozenset(tuple(row[i] for i in projection) for row in entry['rows'])
        kind,index=entry['example']
        if kind==0 and any(c['type']=='Example' for c in schema):
            raise Incomplete('pooled TASK OUT requires a native per-example output certificate')
        destinations=axes if kind==0 else [(kind,index)]
        for assignment in held[entry['entry']]:
            for axis in destinations:
                key=(assignment,*axis)
                if key not in required or entry['model'] in observed_models[key]:
                    raise Incomplete('OUT entry axes outside task or model duplicated')
                observed_models[key].add(entry['model']);groups[key].add(rows)
    if any(observed_models[key]!=set(range(counts[key])) for key in required):
        raise Incomplete('OUT model entries differ from native complete coverage')
    axis_receipt=dict(required_axes=sorted(required),present_axes=sorted(counts),missing_axes=[],
        complete=True,model_counts=[dict(axis=list(key),models=counts[key]) for key in sorted(counts)],
        projection_source='same checked program out_bindings_json native BodyView.column_of',
        body_path=binding['body_path'],owner_path=binding['path'])
    rows_ref=_write(folder/'mutant-out-rows.json',dict(schema='evaluator-det-out-rows-summary-v1',
        table=table,projection=projection,entry_count=entry_count,
        whole_out_entries_sha256=entries_digest.hexdigest(),
        whole_out_entries_hash_of='SHA256 of ordered 32-byte SHA256(canonical JSON entry) digests',
        fields=[dict(field_name='P',type=columns[0]['type']),dict(field_name='Col',type=columns[1]['type'])],
        native_schema=schema,whole_body_report_sha256=body_ref['whole_report_sha256'],axes=axis_receipt))
    summaries=[]
    fields=[dict(field_name='P',type='Position'),dict(field_name='Col',type='Color')]
    for a,assignment in enumerate(choices):
        examples=[]
        for i,pair in enumerate(task['test']):
            key=(a,2,i);family=groups.get(key,set());expected=task_output_rows(pair.get('output'))
            item=dict(example=i,models=len(family),fits=None,complete=False,
                      evidence=rows_ref,required_axis=list(key))
            if not family:item['reason']='no complete OUT model family'
            elif expected is None:item['reason']='task supplies no authenticated TEST output'
            else:
                eq=compare({key:family},[('P','Position'),('Col','Color')],{key:{expected}},fields,
                           explicit=['P','Col'])
                item['comparison']=eq
                if eq['status']=='equal':item.update(fits=True,complete=True,reason='all OUT models equal the given task output')
                elif any(not rows for rows in family):
                    item.update(fits=False,complete=True,reason='native OUT has an empty model')
                else:item['reason']='nonempty OUT differs; native accepted-grid membership not certified'
            examples.append(item)
        flags=[x['fits'] for x in examples]
        value=False if False in flags else True if flags and all(v is True for v in flags) else None
        summaries.append(dict(assignment=a,native_assignment=assignment,fits_train=True,
            fits_test=value,test=examples,test_complete=bool(flags) and all(type(v) is bool for v in flags)))
    return summaries,dict(report=body_ref,rows=rows_ref,binding=binding,projection=projection,
        train_fit_choices_sha256=sha(choices),test_selects_assignments=False,axes=axis_receipt)


def _relation_snapshot(ev,record,text,side,base,operations,folder,*,checked_program=None):
    # Native program loader authenticates original source names and the exact
    # stored mutation identity. It supplies names only; no stored cells read.
    producer=ev._derived_fit_setup['producer']
    own=dict(record,programs=record.get('programs') or
             {s:record[s+'_sexp'] for s in ('gold','mutant')})
    export=producer._export(text,own if side=='gold' else None,
                           mutant_record=own if side=='mutant' else None)
    export_ref=_write(folder/(side+'-source-export.json'),dict(
        schema='evaluator-det-source-summary-v1',whole_export_sha256=_digest_json(export),
        relation_count=len(export['definitions']['native_relations']),
        later_relation_count=sum(bool(d['definition_path'] and
            d['definition_path'][0]>int(record['point'][0]))
            for d in export['definitions']['native_relations'])))
    definitions=[d for d in export['definitions']['native_relations'] if d['definition_path']]
    replay=_operation(ev,operations,side+'.relations.Search',folder/(side+'-relations.json'),
        lambda:ev.replay_program(record,text,int(record['point'][0]),
            candidate=dict(kind='derived-later-relations',side=side),retain_all=True,
            full_rows=True,assignment_mode='derived',artifact_mode='metadata',
            checked_program=checked_program))
    _write(folder/(side+'-relations.json'),replay)
    if replay['engine']!='ran':raise Incomplete(side+' relations: '+replay.get('reason','incomplete'))
    native=ev.captures[-1]['native']
    if len({(tuple(d['definition_path']),d['relation_slot']) for d in definitions})!=len(definitions):
        raise Incomplete('diagnostic declaration identity duplicated')
    # One completed bounded packed gold payload is retained per case. Decode
    # no earlier/fact table and no later table before its comparison needs it.
    return dict(definitions={(tuple(d['definition_path']),d['relation_slot']):d for d in definitions},
        native=native,artifact=replay['artifact'],source_export=export_ref,folder=folder,
        matches=producer.selectors['matches'],decoded=OrderedDict(),cache_units=0)


def _later_definitions(snapshot,form):
    return {key:d for key,d in snapshot['definitions'].items() if key[0][0]>form}


def _relation_value(ev,record,snapshot,definition,side,metrics):
    from program_metadata import type_identity
    ts=snapshot['native']['tables'];selector=definition['native_selector']
    matches=[t for t in range(len(ts['form'])) if snapshot['matches'](ts,t,selector)]
    if len(matches)!=1:raise Incomplete('required later relation selector missing or ambiguous: '+definition['display_name'])
    table=matches[0];cache=snapshot['decoded']
    if table in cache:
        metrics[side+'_cache_hits']+=1;value=cache[table][0];cache.move_to_end(table)
    else:
        started=time.monotonic();families=defaultdict(set)
        entries=read_table(ev.legacy,snapshot['native'],table)
        for e in entries:
            kind,index=e['example']
            axes=([(1,i) for i in range(record['_derived_ntrain'])]+[(2,i) for i in range(record['_derived_ntest'])]
                  if kind==0 else [(kind,index)])
            for axis in axes:families[axis].add(frozenset(e['rows']))
        types=[type_identity(ev,record,ty)[0] for ty in ts['column_types'][table]]
        witness=_write(snapshot['folder']/(side+'-table-'+str(table)+'-witness.json'),dict(
            schema='evaluator-derived-relation-summary-v1',table=table,native_selector=selector,
            program_artifact=snapshot['artifact'],source_export=snapshot['source_export'],
            native_schema=snapshot['native']['_native_reader'].schema(table),entry_count=len(entries),
            whole_entries_sha256=_digest_json(entries),
            row_scope='SHA256 of complete canonical entries used by the later-relation comparison'))
        value=dict(columns=list(zip(ts['column_names'][table],types)),groups=dict(families),witness=witness)
        metrics[side+'_decoded_tables']+=1;metrics[side+'_decoded_entries']+=len(entries)
        metrics[side+'_decode_seconds']+=time.monotonic()-started
        # Retain only a small bounded amount of decoded gold rows; a larger
        # table is still compared completely and is simply not cached. Units
        # count row/tuple/value references, not an asserted byte estimate.
        units=(sum(1+sum(1+len(cell) for cell in row) for e in entries for row in e['rows'])
               if side=='gold' else 100_001)
        if units<=100_000:
            while cache and (len(cache)>=8 or snapshot['cache_units']+units>100_000):
                _,(_,old_units)=cache.popitem(last=False);snapshot['cache_units']-=old_units
            cache[table]=(value,units);snapshot['cache_units']+=units
    metrics.setdefault('table_witnesses',[]).append(dict(side=side,table=table,
        native_selector=selector,witness=value['witness']))
    return dict(value,name=definition['display_name'],form=definition['definition_path'][0],table=table,
        artifact=snapshot['artifact'],source_export=snapshot['source_export'],native_selector=selector)


def _later(ev,record,task,base,operations,folder,key,metrics,mutant_program):
    cached=getattr(ev,'_derived_fit_gold',None)
    if cached is None or cached[0]!=key:
        try:gold=_relation_snapshot(ev,record,record['gold_sexp'],'gold',base,operations,folder)
        except (ValueError,KeyError,IndexError,TypeError) as error:
            ev._derived_fit_gold=(key,None,str(error));raise
        ev._derived_fit_gold=(key,gold,None)
    else:
        if cached[2] is not None:raise Incomplete('cached gold relation evidence unavailable: '+cached[2])
        gold=cached[1]
    # Native PairCache is keyed by checked-program handle. Reuse the handle
    # whose TRAIN walk just ran, so activate() does not clear those results.
    mutant=_relation_snapshot(ev,record,record['mutant_sexp'],'mutant',base,operations,folder,
        checked_program=mutant_program)
    gold_defs=_later_definitions(gold,int(record['point'][0]))
    mutant_defs=_later_definitions(mutant,int(record['point'][0]))
    if set(gold_defs)!=set(mutant_defs):raise Incomplete('gold/mutant later declaration inventory differs')
    required={(kind,i) for kind,section in ((1,'train'),(2,'test')) for i in range(len(task[section]))}
    for relation in sorted(gold_defs):
        metrics['relations_considered']+=1
        g=_relation_value(ev,record,gold,gold_defs[relation],'gold',metrics)
        m=_relation_value(ev,record,mutant,mutant_defs[relation],'mutant',metrics)
        if set(g['groups'])!=required or set(m['groups'])!=required:
            raise Incomplete('later relation lacks complete derived example/model axes')
        fields=[dict(field_name=name,type=ty) for name,ty in g['columns']]
        # Comparator group zero is only a diagnostic family bucket, not a
        # gold/mutant assignment correspondence or a kept ordinal.
        left={(0,*axis):family for axis,family in m['groups'].items()}
        right={(0,*axis):family for axis,family in g['groups'].items()}
        eq=compare(left,m['columns'],right,fields)
        if eq['status']=='unknown':raise Incomplete('later relation comparison: '+str(eq.get('reason')))
        if eq['status']=='mismatch':
            empty=[list(axis) for axis in sorted(required) if any(g['groups'][axis]) and
                   m['groups'][axis] and all(not rows for rows in m['groups'][axis])]
            return dict(relation=g['name'],form=g['form'],reason='empty' if empty else 'differs',
                scope='complete native Search value families; comparison group zero aggregates model families, not assignments; no FITS inference',
                empty_axes=empty,comparison=eq,native_selector=m['native_selector'],
                gold_source_export=g['source_export'],mutant_source_export=m['source_export'],
                gold_artifact=g['artifact'],mutant_artifact=m['artifact'],
                gold_witness=g['witness'],mutant_witness=m['witness'])
    return None


def check(ev,record,*,native_base):
    """Native mutant TRAIN FITS, TEST at the same choices, lazy diagnostics."""
    start=time.monotonic();base=Path(native_base).resolve()
    if record.get('kind','').casefold()!='det':raise ValueError('det_later_fit requires a DET record')
    ev.task_evaluator(record['task'])
    if not hasattr(ev,'_derived_fit_code'):ev._derived_fit_code=_code()
    code=ev._derived_fit_code
    task_path=(Path(ev.cfg['tasks'])/(record['task']+'.json')).resolve();stat=task_path.stat()
    task_key=(str(task_path),stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns)
    if getattr(ev,'_derived_fit_task',(None,))[0]!=task_key:
        task_raw=task_path.read_bytes();task=json.loads(task_raw)
        if not task.get('train') or not isinstance(task.get('test'),list):raise ValueError('authenticated task axes missing')
        ev._derived_fit_task=(task_key,task,hashlib.sha256(task_raw).hexdigest())
    _,task,task_sha=ev._derived_fit_task
    setup=getattr(ev,'_derived_fit_setup',None)
    source_names=record.get('relation_source_names')
    if (setup is None or setup['task_sha']!=task_sha or setup['task']!=record['task']
            or setup['case']!=record['case'] or setup['gold_text']!=record['gold_sexp']
            or setup['base']!=str(base) or setup['source_names']!=source_names):
        from judge3.nonrender_metadata import MetadataProducer
        setup=dict(task=record['task'],case=record['case'],gold_text=record['gold_sexp'],base=str(base),
            task_sha=task_sha,source_names=deepcopy(source_names),
            producer=MetadataProducer(engine=ev.arclog,settings=ev.settings,corpus=base.parent,
                read_native=lambda *args: (_ for _ in ()).throw(Incomplete('diagnostic must not read saved cells'))))
        setup['context']=dict(task=record['task'],case=record['case'],gold=sha(record['gold_sexp']),
            native_base=str(base),task_sha256=task_sha,source_names_sha256=sha(source_names),settings=ev.receipt,code=code)
        setup['gold_key']=sha(setup['context']);ev._derived_fit_setup=setup
        ev.__dict__.pop('_derived_fit_gold',None)
    context=dict(setup['context'],point=record['point'])
    key=sha(dict(context=context,mutant=sha(record['mutant_sexp']),source_names=record.get('relation_source_names')))
    cached=getattr(ev,'_derived_fit_result',None)
    if cached is not None and cached[0]==key:
        result=deepcopy(cached[1]);result['receipt']['reused_for_source_sha256']=sha(record)
        result['receipt']['current_native_calls']=0
        result['receipt']['current_wall_seconds']=time.monotonic()-start;return result
    folder=Path(tempfile.mkdtemp(prefix='det-derived-',dir=ev.artifacts));operations=[]
    result=dict(schema=SCHEMA,status='unknown',fits_train=None,fits_test=None,
        train_fit_assignments=[],first_later_difference=None,reason=None,
        receipt=dict(source_sha256=sha(record),context=context,assignment_mode='derived',
            gold_kept_values_used=False,test_selects_assignments=False,operations=operations,artifact=str(folder)))
    phases=dict(setup=time.monotonic()-start);result['receipt']['phase_wall_seconds']=phases
    old_artifacts=ev.artifacts;ev.artifacts=folder
    try:
        program=ev.arclog.StudyProgram.from_sexp(record['mutant_sexp'],ev.settings)
        phase=time.monotonic()
        report_path=folder/'mutant-train-fits.json'
        raw_report=_operation(ev,operations,'mutant.gold_kept.TRAIN',report_path,
            lambda:ev.ev.gold_kept(program=program))
        report=json.loads(raw_report)
        result['receipt']['train_report']=_report_ref(report_path,raw_report,dict(
            status=report.get('status'),gold_fits=report.get('gold_fits'),
            observation_complete=report.get('observation_complete'),
            assignment_coverage_complete=report.get('assignment_coverage_complete'),
            kept_assignment_count=report.get('kept_assignment_count'),
            gold_observation_ref=report.get('gold_observation_ref')))
        result['partial_proof']=dict(native_gold_fits=report.get('gold_fits'),
            observation_complete=report.get('observation_complete'),report=str(report_path))
        choices=ev.validate_gold_observation(program,report,record['task'],require_fit=False)
        phases['train_fit']=time.monotonic()-phase
        result['fits_train']=report['gold_fits']
        native_train=[v for v in report['gold_assignments'] if v.get('fits') is True]
        if [v['assignment'] for v in native_train]!=choices:raise Incomplete('native TRAIN FITS choice order differs')
        result['train_fit_assignments']=[dict(assignment=i,native_assignment=v['assignment'],
            fits_train=True,native_train=v['train'],fits_test=None,test=[]) for i,v in enumerate(native_train)]
        if choices:
            phase=time.monotonic()
            try:
                assignments,out=_assignment_tests(ev,record,program,ev.ev,report,task,folder,operations)
                for item,train in zip(assignments,native_train):item['native_train']=train['train']
                result['train_fit_assignments']=assignments;result['receipt']['out']=out
                values=[a['fits_test'] for a in assignments]
                # Universal over the already TRAIN-selected set; TEST does not
                # choose a winning assignment. No vacuous positive on no fits.
                result['fits_test']=False if False in values else True if all(v is True for v in values) else None
            except (ValueError,KeyError,IndexError,TypeError) as error:
                result['receipt']['test_unavailable']=str(error)
            phases['test_outputs']=time.monotonic()-phase
        if result['fits_train'] is False or result['fits_test'] is False:
            phase=time.monotonic()
            own=dict(record,_derived_ntrain=len(task['train']),_derived_ntest=len(task['test']))
            metrics=dict(relations_considered=0,**{side+suffix:0 for side in ('gold','mutant') for suffix in
                ('_cache_hits','_decoded_tables','_decoded_entries','_decode_seconds')})
            result['receipt']['diagnostic_work']=metrics
            try:result['first_later_difference']=_later(ev,own,task,base,operations,folder,setup['gold_key'],metrics,program)
            except (ValueError,KeyError,IndexError,TypeError) as error:result['receipt']['diagnostic_unavailable']=str(error)
            phases['later_diagnostics']=time.monotonic()-phase
        if result['fits_train'] is False:
            result.update(status='complete',reason='no derived assignment fits every TRAIN example; TEST not selected')
        elif type(result['fits_test']) is bool:
            result.update(status='complete',reason=None)
        else:result['reason']=result['receipt'].get('test_unavailable','TEST outcomes incomplete for TRAIN-fitting assignments')
    except (ev.arclog.Refusal,ValueError,KeyError,IndexError,TypeError,OSError) as error:
        result['reason']=f'{type(error).__name__}: {error}'
    finally:
        result['receipt'].update(wall_seconds=time.monotonic()-start,
            current_native_calls=sum(op['native_calls'] for op in operations),
            per_operation_bounds=True,code=code,runtime=ev.runtime)
        ev.artifacts=old_artifacts
        ev.captures=[];ev.finish_case()
    ev._derived_fit_result=(key,deepcopy(result))
    return result
