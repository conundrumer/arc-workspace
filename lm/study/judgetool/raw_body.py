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


def binding(ev,record,*,native_base):
    program=ev.arclog.StudyProgram.from_sexp(record['gold_sexp'],ev.settings).decode_source()
    names=json.dumps(record['relation_source_names']) if record.get('relation_source_names') else program.relation_source_names_json(
        str(MAIN_ROOT / 'work/arclog/gen'),record['task'],record['case'])
    export=json.loads(ev.arclog.study_program_export_json(program,names))
    views=[v for v in export['body_views'] if v['body_path']==record['point']]
    if len(views)!=1:raise Incomplete('exact gold BODY path unavailable or ambiguous')
    view=views[0]
    native=TargetStore(ev.legacy,S).snapshot(record['native']['gold'],native_base)
    table=record['evaluation']['table_indices']['gold_all'];ts=native['tables']
    if not all(str(ts[k][table])==str(v) for k,v in view['native_table_selector'].items() if k in ('form','point')):
        raise Incomplete('native gold_all does not identify the requested BODY')
    schema=copy.deepcopy(native['_native_reader'].schema(table))
    source=S/'judge2/render2/headers.py';tree=ast.parse(source.read_text(),str(source))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='bind_body_schema')
    namespace={'require':ev.legacy.native.__globals__['_NATIVE'].require}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),namespace)
    namespace['bind_body_schema'](dict(schema=schema),view)
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
        sites.append([':'+spelling,'*V'+str(c['index'])])
    result=dict(kind=view['kind'],input_port=view['input_port'],body_path=view['body_path'],owner_path=view['owner_path'],
        native_selector=view['native_table_selector'],source_body_schema=schema,projected_schema=fields,
        callable_template=ev.legacy.unparse(['&X']+sites),raw_body=True)
    return result,dict(schema='judgetool-raw-body-layout-v1',source_sha256=sha(record),native_gold_all_table=table,
        body_path=view['body_path'],layout_sha256=sha(fields),binding_sha256=sha(result),
        projection='identity in authenticated stored gold BODY physical order',header_helper=str(source)+':bind_body_schema')


def observe_gold_body(ev,record,*,native_base,ntrain,ntest):
    from checks import observe_gold
    layout,receipt=binding(ev,record,native_base=native_base)
    adapter=dict(input=dict(binding=layout),comparison_target=dict(binding=layout),relation_tokens={})
    groups,observation=observe_gold(ev,record,adapter,layout,ntrain,ntest)
    return groups,dict(receipt,observation=observation,source='gold_full_replay',fields=layout['projected_schema'])
