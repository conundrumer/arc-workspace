"""Whole-program TEST OUT evidence through the existing replay evaluator.

Gold equality is the coordinator-approved sufficient TEST check. Extra/differing
outputs remain unknown: row inequality does not establish accepted-grid failure.
No grid reader, lib evaluator or native endpoint is implemented here.
"""
import hashlib
import json
from pathlib import Path

from evaluator import sha
from surface import tokens,native_body_labels,native_body_atoms
from tables import Incomplete,read_table,kept_entries,compare,comparison_type


def _files(folder):
    return [dict(path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(Path(folder).rglob('*')) if path.is_file()]


def _code():
    root=Path(__file__).resolve().parent
    return {str((root/name).resolve()):hashlib.sha256((root/name).read_bytes()).hexdigest()
            for name in ('out_fit.py','evaluator.py','tables.py','surface.py','case_collector.py','../study_paths.py')}


def native_out_binding(program):
    """Authoritative native OUT key and its original BODY physical columns."""
    binding=json.loads(program.out_bindings_json())
    if binding.get('complete') is not True:raise Incomplete('native OUT binding incomplete')
    columns=sorted(binding['columns'],key=lambda c:c['out_column'])
    if ([c['out_column'] for c in columns]!=[0,1]
            or [comparison_type(c['type']) for c in columns]!=['Box','Color']):
        raise Incomplete('native OUT lacks exact Position/Color key projection')
    if binding.get('schema')!='arclog-study-out-bindings-v1':
        raise Incomplete('native OUT binding schema unsupported')
    return binding,columns


def out_body_projection(binding,columns,schema):
    """Use native BodyView column_of, independently of mutation-point catalogs."""
    projection=[column['body_column'] for column in columns]
    if (len(set(projection))!=len(projection) or
            any(type(i) is not int or not 0<=i<len(schema) or schema[i]['index']!=i for i in projection)):
        raise Incomplete('native OUT physical column missing or ambiguous')
    if ([comparison_type(schema[i]['type']) for i in projection]!=
            [comparison_type(column['type']) for column in columns]):
        raise Incomplete('OUT physical projection type differs')
    return projection


def _observe(ev,record,text,side):
    L=ev.legacy;program=ev.arclog.StudyProgram.from_sexp(text,ev.settings)
    binding,columns=native_out_binding(program)
    export=json.loads(program.render_json());nodes={tuple(n['path']):n for n in export['nodes']}
    node=nodes[tuple(binding['body_path'])]
    if node['kind']!='body':raise Incomplete('native OUT binding does not identify a BODY')
    names=native_body_labels(nodes,node)
    outputs={columns[0]['label_id']:'P',columns[1]['label_id']:'Col'}
    if not set(outputs)<=set(names.values()):raise Incomplete('native OUT key label occurrence missing')
    clause=L.canonical_or(['RULE','&JudgeWholeOut']+native_body_atoms(L,node,names,outputs))
    forms=L.split_forms(text);path=binding['path']
    if path!=[len(forms)-1] or L.parse(forms[-1])[0]!='OUT':
        raise Incomplete('whole OUT observer requires the exact final native OUT')
    occupied=set(tokens([L.parse(f) for f in forms]))
    while clause[1] in occupied:clause[1]+='Q'
    index=len(forms)-1;observed='\n'.join(forms[:-1]+[L.unparse(clause),forms[-1]])
    replay=ev.replay_program(record,observed,index,candidate=dict(kind='whole-OUT-observer',side=side,
        binding_sha256=sha(binding)),retain_forms=[index])
    if replay['engine']!='ran':raise Incomplete(side+' OUT replay: '+replay.get('reason','incomplete'))
    native=ev.captures[-1]['native'];ts=native['tables']
    tables=[t for t,f in enumerate(ts['form']) if str(f)==str(index)]
    if len(tables)!=1:raise Incomplete('OUT observer table missing or ambiguous')
    table=tables[0];header=ts['column_names'][table]
    if len(set(header))!=len(header):raise Incomplete('OUT observer has ambiguous scoped output labels')
    try:projection=[header.index(name) for name in ('P','Col')]
    except ValueError:raise Incomplete('OUT observer lost a native key label') from None
    if [comparison_type(ts['column_types'][table][i]) for i in projection]!=['Box','Color']:
        raise Incomplete('OUT observer physical type mismatch')
    entries=read_table(L,native,table)
    entries=[dict(e,rows=tuple(sorted({tuple(row[i] for i in projection) for row in e['rows']}))) for e in entries]
    return dict(entries=entries,det_relations=ts['det_relations'][table],det_types=ts['det_types'][table],
        fields=[dict(field_name='P',type=columns[0]['type']),dict(field_name='Col',type=columns[1]['type'])],
        receipt=dict(source=side+'_full_replay_OUT',program_sha256=sha(text),observer_program_sha256=sha(observed),
            binding=binding,binding_sha256=sha(binding),table=table,projection=projection,
            artifact=replay['artifact'],evidence_files=_files(replay['artifact']),
            original_OUT_retained=True,all_assignments_stored=True),evaluations=1)


def check(ev,record,*,ntrain,ntest,gold_cache=None):
    """Return durable JSON TEST evidence; at most one gold + one mutant replay.

    Gold cache excludes pair/mutant/kept values: select each pair's kept context
    from all returned entries using the same shared matcher. Caller owns cache
    lifetime and may clear it at task boundaries. No label write is performed.
    """
    from case_collector import _ReplayBudget
    gold_budget=_ReplayBudget(ev,1);mutant_budget=_ReplayBudget(ev,1)
    code=_code();evaluations=dict(gold_replays=0,mutant_replays=0)
    result=dict(schema='judgetool-out-fit-v1',fits_test=None,complete=False,
        source_sha256=sha(record),evaluations=evaluations,evidence_files=[])
    receipt=dict(code=code,code_sha256=sha(code),runtime=ev.runtime,settings=ev.receipt,
        source_sha256=sha(record),kept_context_sha256=sha(record['evaluation']['kept_assignments']),
        native_session_scope='fresh native session per independent gold or mutant OUT observation',
        test_policy='complete TEST OUT equality to full gold replay is sufficient; max two outputs; extra families not decided')
    result['receipt']=receipt
    if record['kind'].lower().startswith('det'):
        result['reason']='Step4 OUT fit applies only to nonDET pairs';return result
    if ntest<1:result['reason']='no TEST input axis';return result
    cache=ev.target_cache if gold_cache is None else gold_cache
    task=Path(ev.cfg['tasks'])/(record['task']+'.json')
    receipt['task']=dict(path=str(task.resolve()),sha256=hashlib.sha256(task.read_bytes()).hexdigest())
    key=sha(dict(operation='full-gold-OUT',task=record['task'],case=record['case'],
        program=sha(record['gold_sexp']),settings=ev.receipt,code=sha(code),task_file=receipt['task'],
        ntrain=ntrain,ntest=ntest))
    try:
        gold=cache.get(key)
        if gold is None:
            with ev.fresh_session() as isolated:
                gold_budget=_ReplayBudget(isolated,1)
                gold=_observe(gold_budget,record,record['gold_sexp'],'gold')
            cache[key]=gold
        with ev.fresh_session() as isolated:
            mutant_budget=_ReplayBudget(isolated,1)
            mutant=_observe(mutant_budget,record,record['mutant_sexp'],'mutant')
        receipt.update(gold=gold['receipt'],mutant=mutant['receipt'],gold_cache_key=key)
        result['evidence_files']=gold['receipt']['evidence_files']+mutant['receipt']['evidence_files']
        grouped=[]
        for item in (gold,mutant):
            g=kept_entries(ev.legacy,item['entries'],item['det_relations'],item['det_types'],record,ntrain,ntest)
            required={(a,2,i) for a in range(len(record['evaluation']['kept_assignments'])) for i in range(ntest)}
            tests={k:v for k,v in g['groups'].items() if k[1]==2}
            if not required or set(tests)!=required or any(not family for family in tests.values()):
                raise Incomplete('OUT lacks exact compatible kept TEST contexts')
            grouped.append(tests)
        expected,actual=grouped
        receipt.update(required_test_contexts=len(expected),test_contexts_complete=True)
        if any(not rows for family in expected.values() for rows in family):
            raise Incomplete('gold OUT gives no TEST grid rows')
        if any(len(family)>2 for family in actual.values()):
            result.update(fits_test=False,complete=True,reason='more than two distinct TEST outputs at a kept context')
        elif any(not rows for family in actual.values() for rows in family):
            result.update(fits_test=False,complete=True,reason='mutant OUT is empty at a kept TEST model')
        else:
            comparison=compare(actual,[('P',mutant['fields'][0]['type']),('Col',mutant['fields'][1]['type'])],
                expected,gold['fields'],explicit=['P','Col'])
            result['comparison']=comparison
            if comparison['status']=='equal':
                result.update(fits_test=True,complete=True,reason='whole mutant OUT equals full gold OUT on every kept TEST input')
            else:result['reason']='TEST OUT differs or comparison stopped; additional-output fit is not proved'
    except (ev.arclog.Refusal,ValueError,KeyError,IndexError,TypeError,OSError) as error:
        result['reason']=str(error)
    evaluations.update(gold_replays=len(gold_budget.operations),mutant_replays=len(mutant_budget.operations))
    receipt['operations']=dict(gold=gold_budget.operations,mutant=mutant_budget.operations)
    files={f['path']:f for f in result['evidence_files']}
    for operation in gold_budget.operations+mutant_budget.operations:
        if operation.get('artifact'):
            files.update((f['path'],f) for f in _files(operation['artifact']))
    result['evidence_files']=list(files.values())
    return result
