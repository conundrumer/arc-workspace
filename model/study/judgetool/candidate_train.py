"""Feature-safe projection of ALL STORED candidate assignments, TRAIN only.

This provider performs no replay, gold-kept filtering or comparison. A native
export's stored entries do not prove an exhaustive branch-available population.
"""
from pathlib import Path
from evaluator import S,P,legacy_helpers,read_json,open_source,sha
from tables import TargetStore,read_table,projected_rows,Incomplete


def candidate_training(record,adapter,*,run=S/'ast/run',reference=P):
    """Select mutant BODY and apply the producer's exact physical INIT layout.

    Task entries broadcast only when the native entry itself says TASK and the
    real task file authenticates this task's train axis. Returned native cells
    and assignment contexts come exclusively from TRAIN/TASK entries.
    """
    L=legacy_helpers(Path(run),Path(reference))
    store=TargetStore(L,S);binding=adapter['input']['binding']
    source=adapter['source']
    authenticated,_=open_source(source['record_path'])
    if sha(authenticated)!=sha(record):raise Incomplete('candidate record differs from binding source')
    n=store.snapshot(record['native']['mutant'],source['native_base'])
    ts=n['tables'];selector=binding['native_selector']
    tables=[t for t in range(len(ts['form'])) if all(str(ts[k][t])==str(v)
        for k,v in selector.items() if k in ('form','point','relation','fact'))]
    # Pair exports contain both ALL and KEPT BODY tables with the same
    # form/point. The native pair report identifies ALL explicitly; the
    # document binding index identifies the displayed KEPT table instead.
    table=record['evaluation'].get('table_indices',{}).get('mutant_all')
    if not isinstance(table,int) or table not in tables:
        raise Incomplete('native mutant_all report index does not identify the selected BODY')
    fields=binding['projected_schema'];indices=[f['source_body_column'] for f in fields]
    if any(i is not None and (not isinstance(i,int) or not 0<=i<len(ts['column_types'][table])) for i in indices):
        raise Incomplete('candidate physical projection is outside the native BODY schema')
    expected=binding['source_body_schema']
    if [f['type'] for f in expected]!=list(ts['column_types'][table]):
        raise Incomplete('ALL native BODY physical types differ from projected binding source')
    taskpath=Path(source['task_path']).resolve();task=read_json(taskpath)
    if taskpath.stem!=record['task']:raise Incomplete('task evidence identity differs')
    entries=[]
    for e in read_table(L,n,table,example_kinds={0,1}):
        kind,index=e['example']
        if kind not in (0,1):continue
        rows=projected_rows(L,e['rows'],indices)
        examples=range(len(task['train'])) if kind==0 else [index]
        for train_index in examples:
            if not 0<=train_index<len(task['train']):raise Incomplete('native TRAIN axis outside task evidence')
            entries.append(dict(entry=e['entry'],example_kind='train',example_index=train_index,
                model=e['model'],assignment=e['assignment'],rows=rows,
                native_example_kind='task' if kind==0 else 'train',task_broadcast=kind==0))
    return dict(schema='judgetool-candidate-train-v1',task=record['task'],source_sha256=sha(record),
        binding_sha256=sha(binding),fields=fields,entries=entries,
        task_evidence=dict(path=str(taskpath),sha256=sha(dict(train=task['train'],test_inputs=[{'input':p['input']} for p in task['test']])),train_count=len(task['train'])),
        population=dict(scope='all_stored_assignments',gold_kept_filter=False,test_rows=False,
            branch_available_population='unavailable',exhaustive=False,
            reason='stored export entries do not certify exhaustive branch-available assignments'),
        native_source=dict(reference=record['native']['mutant'],selector=selector,table=table,report_index='evaluation.table_indices.mutant_all',projection=indices))
