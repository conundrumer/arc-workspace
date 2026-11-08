"""Bind old mechanical BODY witness columns to a fresh gold observer.

Uses the one producer header binder. No written-relation ordering or INIT port
projection is substituted for the raw native BODY layout.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import ast
import copy
import json
from pathlib import Path
from evaluator import S,sha
from tables import TargetStore,Incomplete
from surface import tokens,native_body_labels,native_body_atoms
from program_metadata import type_identity
from native_correspondence import canonical_bound_field_type,source_program_record


def body_schema(ev,native,table,view,*,legacy_binding=None):
    """Apply the producer's native BODY header binder without reimplementing it."""
    schema=copy.deepcopy(native['_native_reader'].schema(table))
    source=S/'judge2/render2/headers.py';tree=ast.parse(source.read_text(),str(source))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='bind_body_schema')
    namespace={'require':ev.legacy.native.__globals__['_NATIVE'].require}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),namespace)
    namespace['bind_body_schema'](dict(schema=schema),view,legacy_binding=legacy_binding)
    return schema


def binding(ev,record,*,native_base,body_side='gold',report_role=None):
    record=source_program_record(record)
    if body_side not in ('gold','mutant'):
        raise Incomplete('raw BODY requires explicit gold or mutant side')
    text=record['programs'][body_side]
    if record.get(body_side+'_sexp',text)!=text:
        raise Incomplete('raw BODY source differs; pass original record and explicit body_side')
    program=ev.arclog.StudyProgram.from_sexp(text,ev.settings).decode_source()
    names=None
    if body_side=='gold':
        names=json.dumps(record['relation_source_names']) if record.get('relation_source_names') else program.relation_source_names_json(
            str(MAIN_ROOT / 'work/arclog/gen'),record['task'],record['case'])
    export=json.loads(ev.arclog.study_program_export_json(program,names,source_program=program))
    views=[v for v in export['body_views'] if v['body_path']==record['point']]
    if len(views)!=1:raise Incomplete('exact gold BODY path unavailable or ambiguous')
    view=views[0]
    native=TargetStore(ev.legacy,S).snapshot(record['native'][body_side],native_base)
    role=report_role or body_side+'_all'
    if role not in (body_side+'_all',body_side+'_kept'):
        raise Incomplete('raw BODY report role differs from explicit side')
    table=record['evaluation']['table_indices'][role];ts=native['tables']
    if not all(str(ts[k][table])==str(v) for k,v in view['native_table_selector'].items() if k in ('form','point')):
        raise Incomplete('native gold_all does not identify the requested BODY')
    from legacy_body_metadata import LegacyBodyMetadata
    raw_schema=native['_native_reader'].schema(table)
    legacy=LegacyBodyMetadata.configured().bind(record=record,side=body_side,base=native_base,
        reader=native['_native_reader'],table=table,schema=raw_schema,program=program,
        export=export,body_path=view['body_path'])
    schema=body_schema(ev,native,table,view,legacy_binding=legacy)
    source=S/'judge2/render2/headers.py'
    labels={c['label_id']:c for c in view['columns']};fields=[];sites=[]
    for c in schema:
        label=labels.get(c['ast_label_id'])
        if label is None:raise Incomplete('raw BODY scalar has no native AST LabelId')
        spelling=label['label_spelling'];identity=dict(label_id=c['ast_label_id'],source_label_spelling=spelling,
            body_path=view['body_path'],owner_path=view['owner_path'])
        c['native_label_identity']=identity
        path=[dict(kind='written',name=spelling)]
        fields.append(dict(physical_index=c['index'],field_name=spelling,type=c['type'],frame=c['frame'],
            source_body_column=c['index'],callable_row_path=path,native_label_identity=identity))
        for key in ('native_legacy_binding','native_type'):
            if key in c:fields[-1][key]=copy.deepcopy(c[key])
        sites.append([':'+spelling,'*V'+str(c['index'])])
    result=dict(kind=view['kind'],input_port=view['input_port'],body_path=view['body_path'],owner_path=view['owner_path'],
        native_selector=view['native_table_selector'],source_body_schema=schema,projected_schema=fields,
        callable_template=ev.legacy.unparse(['&X']+sites),raw_body=True)
    return result,dict(schema='judgetool-raw-body-layout-v1',source_sha256=sha(record),native_gold_all_table=table,body_side=body_side,report_role=role,
        body_path=view['body_path'],layout_sha256=sha(fields),binding_sha256=sha(result),
        projection='identity in authenticated stored gold BODY physical order',header_helper=str(source)+':bind_body_schema')


def body_observer_program(ev,record,layout):
    """Build the exact native BODY observer; no evaluation or kept selection.

    Copy the exact native-exported body node, plus its native key body for an
    INIT input. This is not a judge admission path and does not read DET's
    reader-projected relation or select an INIT port by its label set.
    """
    L=ev.legacy
    # This observer is replayed from named source text. Keep that Layout for
    # its node/label metadata, unlike binding()'s stored decoded-native view.
    program=ev.arclog.StudyProgram.from_sexp(record['gold_sexp'],ev.settings)
    export=json.loads(ev.arclog.study_program_export_json(program))
    nodes={tuple(node['path']):node for node in export['nodes']}
    body=nodes[tuple(layout['body_path'])]
    if body['kind']!='body':raise Incomplete('raw observer path is not a native BODY node')
    key_body=None;key_path=None;key_exports=set()
    owner=nodes[tuple(layout['owner_path'])]
    if owner['kind']=='init' and layout.get('input_port') is not None:
        components=[entry for entry in export['definitions']['registry']['entries']
                    if entry['kind']=='component' and entry['name']==owner['data']['component']]
        ports=[port for entry in components for port in entry['ports']['inputs']
               if port['name']==layout['input_port']]
        if len(ports)!=1 or ports[0]['reads_outputs']:
            raise Incomplete('raw INIT input observer lacks an independent native port context')
        keys=[nodes[tuple(path)] for path in owner['children'] if nodes[tuple(path)]['kind']=='init_key']
        if len(keys)>1:raise Incomplete('native INIT key owner is ambiguous')
        if keys:
            key_bodies=[nodes[tuple(path)] for path in keys[0]['children'] if nodes[tuple(path)]['kind']=='body']
            if len(key_bodies)!=1:raise Incomplete('native INIT key BODY is unavailable')
            key_body=key_bodies[0];key_path=key_body['path']
            key_exports={c['label_id'] for c in keys[0]['data']['columns']}
    fields=layout['projected_schema']
    identities=[f['native_label_identity']['label_id'] for f in fields]
    if None in identities or len(set(identities))!=len(identities):
        raise Incomplete('BODY observer outputs require distinct native scalar labels')
    views=[v for v in export['body_views'] if v['body_path']==layout['body_path']
           and v['owner_path']==layout['owner_path']]
    if len(views)!=1:raise Incomplete('BODY observer lacks its exact native owner/view')
    labels={c['label_id']:c for c in views[0]['columns']}
    if any(label not in labels or type_identity(ev,record,labels[label]['type'])[0]!=type_identity(ev,record,canonical_bound_field_type(field))[0]
           for label,field in zip(identities,fields)):
        raise Incomplete('BODY observer scalar identity/type differs from native source')
    output_names={f['native_label_identity']['label_id']:'V'+str(i) for i,f in enumerate(fields)}
    key_names=native_body_labels(nodes,key_body) if key_body else {}
    input_names=native_body_labels(nodes,body)
    if (set(key_names.values()) & set(input_names.values()))-key_exports:
        raise Incomplete('input BODY refers to a non-exported key-private identity')
    atoms=(native_body_atoms(L,key_body,key_names,output_names) if key_body else [])
    atoms+=native_body_atoms(L,body,input_names,output_names,given=key_exports)
    clause=L.canonical_or(['RULE','&JudgeRawBody']+atoms)
    forms=L.split_forms(record['gold_sexp'])
    if not forms or L.parse(forms[-1])[0]!='OUT':raise Incomplete('raw observer requires final OUT')
    occupied=set(tokens([L.parse(f) for f in forms]))
    while clause[1] in occupied:clause[1]+='Q'
    observed='\n'.join(forms[:-1]+[L.unparse(clause),forms[-1]])
    return observed,len(forms)-1,dict(key_path=key_path,key_export_label_ids=sorted(key_exports))


def _standalone_gold_body(ev,record,*,native_base,ntrain,ntest):
    """Mechanical raw BODY observation, including DET and private INIT labels."""
    from checks import _replay_groups
    from tables import comparison_type
    layout,receipt=binding(ev,record,native_base=native_base)
    observed,form,context=body_observer_program(ev,record,layout)
    fields=layout['projected_schema']
    own=dict(record,mutant_sexp=record['gold_sexp'])
    replay,groups,columns=_replay_groups(ev,own,observed,form,ntrain,ntest,
        dict(kind='mechanical-raw-gold-BODY-observer',body_path=layout['body_path'],key_path=context['key_path']))
    if groups is None or groups['missing']:raise Incomplete('raw gold BODY replay lacks compatible train/test contexts')
    if len({name for name,ty in columns})!=len(columns):raise Incomplete('raw observer exported ambiguous scoped labels')
    try:indices=[next(i for i,c in enumerate(columns) if c[0]=='V'+str(j)) for j in range(len(fields))]
    except StopIteration:raise Incomplete('raw observer lacks a native BODY output label') from None
    if any(comparison_type(columns[i][1])!=comparison_type(canonical_bound_field_type(f)) for i,f in zip(indices,fields)):
        raise Incomplete('raw observer physical types differ from authenticated BODY')
    groups=dict(groups,groups={k:{frozenset(tuple(row[i] for i in indices) for row in rows) for rows in family}
                              for k,family in groups['groups'].items()})
    observation=dict(source='gold_full_replay',artifact=replay['artifact'],original_source_sha256=sha(record),
        gold_program_sha256=sha(record['gold_sexp']),observer_program_sha256=sha(observed),
        kept_context_sha256=sha(record['evaluation']['kept_assignments']),layout_sha256=sha(fields),
        train_complete=True,test_complete=True,body_path=layout['body_path'],**context,
        alpha_binding='native label-node identities per BODY; private identities distinct; input key exports join',
        acquisition='exact native BODY/key node text; one full gold replay with OUT')
    return groups,dict(receipt,observation=observation,source='gold_full_replay',fields=layout['projected_schema'])


def _point_gold_body(ev,record,layout,layout_receipt,ntrain,ntest):
    from tables import decode_kept,kept_entries,read_table,comparison_type
    replay=ev.gold_point_body(record)
    if replay['engine']!='ran':raise Incomplete('native gold point acquisition: '+replay.get('reason','incomplete'))
    report=replay['gold_report'];native=ev.captures[-1]['native'];ts=native['tables']
    table=report['table_indices']['gold_kept'];view=report['body_view']
    if not all(str(ts[k][table])==str(v) for k,v in view['native_table_selector'].items() if k in ('form','point')):
        raise Incomplete('native gold point table does not match certified BODY')
    from tables import full_kept_matches
    old_by_fresh=full_kept_matches(ev.legacy,report['kept_assignments'],report['full_det_schemas'],record)
    # Do not infer fresh held ordinals from body DET subsets: stateful inputs
    # may depend on owner state beyond the public body dependency signature.
    maps=[m for m in report['gold_kept_assignment_map'] if m['table']==table]
    if len(maps)!=1:raise Incomplete('native gold BODY lacks an exact held entry map')
    entries=read_table(ev.legacy,native,table);mapping={m['table_entry']:m for m in maps[0]['entries']}
    reader=native['_native_reader'];ordinals={entry:i for i,entry in enumerate(reader.bytable[table])}
    # The exact source program/point is certified by replay. Authenticate its
    # physical BODY field order using the same native header binder as binding.
    schema=body_schema(ev,native,table,view)
    by_label={c['ast_label_id']:c['index'] for c in schema}
    fields=layout['projected_schema']
    indices=[by_label[f['native_label_identity']['label_id']] for f in fields]
    if any(comparison_type(schema[i]['type'])!=comparison_type(canonical_bound_field_type(f)) for i,f in zip(indices,fields)):
        raise Incomplete('native gold BODY physical type differs from source binding')
    groups={};contexts=[]
    for entry in entries:
        mapped=mapping.get(ordinals[entry['entry']])
        if mapped is None:raise Incomplete('native BODY entry has no held identity receipt')
        kind,index=entry['example'];name={0:'task',1:'train',2:'test'}[kind]
        if (mapped['example_kind'],mapped['example_index'],mapped['model'])!=(name,index,entry['model']):
            raise Incomplete('native BODY entry differs from held map example/model')
        old=old_by_fresh.get(mapped['kept_assignment'],[])
        rows=frozenset(tuple(row[i] for i in indices) for row in entry['rows'])
        examples=([(1,i) for i in range(ntrain)]+[(2,i) for i in range(ntest)] if kind==0 else [(kind,index)])
        for assignment in old:
            for axis,i in examples:groups.setdefault((assignment,axis,i),set()).add(rows)
        contexts.append(dict(entry=entry['entry'],kept_assignments=old,native_held_assignment=mapped['kept_assignment']))
    required={(a,k,i) for a in range(len(record['evaluation']['kept_assignments']))
              for k,count in ((1,ntrain),(2,ntest)) for i in range(count)}
    if not required or set(groups)!=required:raise Incomplete('native gold BODY lacks required kept train/test answers')
    grouped=dict(groups=groups,required=required,missing=[],contexts=contexts,other_contexts=[],det_relations=ts['det_relations'][table])
    observation=dict(source='gold_full_replay',artifact=replay['artifact'],original_source_sha256=sha(record),
        gold_program_sha256=sha(record['gold_sexp']),observer_program_sha256=sha(record['gold_sexp']),
        kept_context_sha256=sha(record['evaluation']['kept_assignments']),layout_sha256=sha(fields),
        train_complete=True,test_complete=True,body_path=record['point'],table=table,
        full_held_context='native gold OUT/FITS then original BODY HeldAssignments; complete full-slot Ident match',
        native_pair_calls=1,mutant_side_work_included=True,mutant_verdicts_used=False,base_label_writes=0,
        gold_point_receipt=replay)
    return grouped,dict(layout_receipt,observation=observation,source='gold_full_replay',fields=fields)


def observe_gold_body(ev,record,*,native_base,ntrain,ntest):
    """At most one standalone replay, then one existing certified-pair fallback."""
    from case_collector import _ReplayBudget
    bounded=_ReplayBudget(ev,1)
    try:
        groups,receipt=_standalone_gold_body(bounded,record,native_base=native_base,ntrain=ntrain,ntest=ntest)
    except (ev.arclog.Refusal,ValueError,KeyError,IndexError,TypeError) as error:
        layout,proof=binding(ev,record,native_base=native_base)
        groups,receipt=_point_gold_body(ev,record,layout,proof,ntrain,ntest)
        receipt['standalone_failure']=str(error)
    receipt['evaluations']=dict(standalone_replays=len(bounded.operations),
        native_pair_calls=receipt['observation'].get('native_pair_calls',0),
        max_native_operations=2,mutant_side_work_included=receipt['observation'].get('mutant_side_work_included',False))
    return groups,receipt
