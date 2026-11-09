"""Compact authoritative observations; expansion never evaluates a program."""
from copy import deepcopy


def target_identity(ref):
    return {k:ref[k] for k in ('case','role','table_id','body_path','native_selector','ignore_names') if k in ref}


def compact(kind,value):
    if kind=='case' and value.get('schema')=='judge-case-bundle-v1':
        axis=next((g['required'] for item in value['tables']+value['bodies']
                   if (g:=item.get('grouped'))),None)
        if axis is None:
            axis=[[a,k,i] for a in range(len(value['kept_assignments']))
                  for k,n in ((1,value['ntrain']),(2,value['ntest'])) for i in range(n)]
        result={k:deepcopy(value[k]) for k in ('task','case','program_sha256','kept_context_sha256','receipt','gaps')}
        result['receipt'].pop('settings',None)
        if 'caller_task_inputs' in value:result['caller_task_inputs']=value['caller_task_inputs']
        result.update(schema='mech-case-observations-v2',axis=axis,tables=[],bodies=[])
        for group in ('tables','bodies'):
            for item in value[group]:
                kept={k:deepcopy(v) for k,v in item.items() if k not in ('grouped','fields','label_ids','complete')}
                # Native table schemas already hold names and types. Observer
                # columns hold their physical LabelId binding once.
                if group=='bodies':kept['fields']=deepcopy(item['fields'])
                kept['grouped']={k:deepcopy(item['grouped'][k]) for k in ('groups','det_relations')}
                # Table completeness is a view of axis versus observed groups.
                if 'receipt' in kept:
                    kept['receipt']={k:v for k,v in kept['receipt'].items()
                        if k not in ('complete','case','artifact','source','kept_context_sha256','body_path','label_ids','table')}
                result[group].append(kept)
        return result
    if kind=='candidate':
        # Human table samples/counts are presentation, not another fact store.
        return {k:v for k,v in value.items() if k not in ('table','receipt')}
    if kind=='comparison':
        def check(value):
            return {k:value[k] for k in ('status','indices','reason','phase') if k in value}
        target=target_identity(value['target_reference'])
        if 'projection' in value.get('target_receipt',{}):target['projection']=value['target_receipt']['projection']
        return dict(schema='mech-target-comparison-v2',target=target,
                    equality=check(value['equality']),containment=check(value['containment']))
    if kind=='search':
        result={k:v for k,v in value.items() if k not in ('checked','candidate')}
        if 'receipt' in result:
            result['receipt']={k:v for k,v in result['receipt'].items() if k!='gold_receipt'}
        return dict(result,schema='mech-target-search-v2')
    if kind=='pair':
        return dict(schema='mech-target-facts-v2',source_sha256=value['source_sha256'],
            base_result_sha256=value['base_result_sha256'],case_refs=value.get('case_refs',[]),axis_ref=value.get('axis_ref'),
            case_failure_refs=value.get('case_failure_refs',[]),
            comparison_refs=[dict(reference=v['reference']) for v in value.get('comparison_refs',[])],searches=value.get('searches',[]),
            gaps=[g for g in value.get('gaps',[]) if g.get('stage') not in ('comparison','other_target_search')],
            stopped=value.get('work_stop'))
    return value


def expand_case(value,ev,record,context):
    if value.get('schema')!='mech-case-observations-v2':return value
    from case_collector import _context
    from evaluator import sha
    import json
    from ._paths import MAIN_ROOT
    case,text,kept,names=_context(ev,record,context)
    if sha(text)!=value['program_sha256'] or sha(kept)!=value['kept_context_sha256']:
        raise ValueError('case metadata does not match observed program/kept identities')
    program=ev.arclog.StudyProgram.from_sexp(text,ev.settings).decode_source()
    naming=json.dumps(names) if names is not None else program.relation_source_names_json(
        str(MAIN_ROOT/'programs/arclog'),record['task'],case)
    result=deepcopy(value);result['schema']='judge-case-bundle-v1'
    result['export']=json.loads(ev.arclog.study_program_export_json(program,naming))
    result['kept_assignments']=kept
    axis=value['axis'];result['ntrain']=len({i for a,k,i in axis if k==1});result['ntest']=len({i for a,k,i in axis if k==2})
    for group in ('tables','bodies'):
        for item in result[group]:
            g=item['grouped'];present={tuple(v['context']) for v in g['groups']}
            g.update(required=axis,missing=[k for k in axis if tuple(k) not in present])
            item['receipt']=dict(item.get('receipt',{}),case=value['case'],source='gold_full_replay',
                artifact=value['receipt'].get('artifact'),kept_context_sha256=value['kept_context_sha256'],
                complete=not g['missing'])
            if group=='tables':item['receipt']['table']=item['native_table']
            else:item['receipt'].update(body_path=item['body_path'],
                label_ids=[f['native_label_identity']['label_id'] for f in item['fields']])
            if group=='tables':item['fields']=[dict(field_name=c['name'],type=c['type']) for c in item['native_schema']]
            else:item['label_ids']=[f['native_label_identity']['label_id'] for f in item['fields']]
    result['complete']=not result['gaps']
    return result
