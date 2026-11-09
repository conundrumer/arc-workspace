"""Targets are the actual tables returned by fresh full gold-case replays.

Saved snapshots and their alias/population completeness flags are not value
sources. The export inventory supplies programs; saved gold DET values or a
complete native gold-only TRAIN FITS observation supply the kept assignment,
never table rows.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import importlib.util
import json
from pathlib import Path
import sys
from evaluator import sha
from tables import kept_groups,Incomplete
from program_metadata import export_named_program,typed_fields


def _scope_policy():
    path=Path(__file__).resolve().parent.parent/'judge3/catalog.py'
    spec=importlib.util.spec_from_file_location('_judge3_target_scope',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.same_case_after


def acquire(ev,record,adapter,ntrain,ntest,*,only_case=None):
    from case_collector import _context
    key=('live-targets',sha(record['gold_sexp']),sha(adapter.get('all_case_targets',{})),ntrain,ntest,only_case)
    if key in ev.target_cache:return ev.target_cache[key]
    sys.path.insert(0,str(ev.run.parent))
    from check_stage1_all import inventory
    inventory_path=Path(adapter['all_case_targets']['catalogue_path']).resolve()
    names,offsets,ids,flags=inventory(inventory_path.parents[2],record['task'],True)
    if only_case is not None and only_case not in names:raise Incomplete('target case is not in the task export')
    contexts={c['name']:c for c in adapter['all_case_targets']['cases']}
    after=_scope_policy();targets=[];available=[];gaps=[];case_receipts=[]
    for case_index,case in enumerate(names):
        if only_case is not None and case!=only_case:continue
        same=case==record['case'];case_meta=contexts.get(case,{})
        values=(record['evaluation']['kept_assignments'] if same else
                case_meta.get('reference',{}).get('evaluation',{}).get('kept_assignments'))
        if same:text=record['gold_sexp']
        else:
            lo,hi=offsets[case_index:case_index+2]
            program=ev.task_evaluator(record['task']).from_stream(ids[lo:hi],[int(v) for v in flags[lo:hi]])
            text=program.sexp()
        try:
            _,text,values,_,kept_observation=_context(ev,record,
                dict(case=case,gold_sexp=text,kept_assignments=values),with_receipt=True)
        except Incomplete as error:
            gap=dict(case=case,reason=str(error),phase='gold_kept_acquisition')
            if hasattr(error,'receipt'):gap['kept_observation']=error.receipt
            gaps.append(gap)
            continue
        own=dict(record,case=case,gold_sexp=text,mutant_sexp=text,
                 evaluation=dict(record['evaluation'],kept_assignments=values))
        replay=ev.replay_program(own,text,0,candidate=dict(kind='full-gold-case-targets',case=case),retain_all=True)
        case_receipt=dict(case=case,artifact=replay['artifact'],program_sha256=sha(text),engine=replay['engine'])
        if kept_observation is not None:case_receipt['kept_observation']=kept_observation
        case_receipts.append(case_receipt)
        if replay['engine']!='ran':
            gaps.append(dict(case=case,reason=replay.get('reason','gold replay stopped')));continue
        native=ev.captures[-1]['native'];ts=native['tables']
        # Export the parsed representation just replayed, including its named
        # column Layout; decode_source would replace it with positional names.
        program=ev.arclog.StudyProgram.from_sexp(text,ev.settings)
        source_names=(json.dumps(record['relation_source_names']) if same and record.get('relation_source_names') else
            program.relation_source_names_json(str(MAIN_ROOT / 'programs/arclog'),record['task'],case))
        export=export_named_program(ev,program,source_names)
        definitions=export['definitions']['native_relations']
        for table in range(len(ts['form'])):
            is_target=not same or after(ts,table,adapter['comparison_target']['binding'],export)
            grouped=kept_groups(ev.legacy,native,table,own,ntrain,ntest)
            definition=next((d for d in definitions if all(str(ts[k][table])==str(v)
                for k,v in d['native_selector'].items() if k in ('form','point','relation'))),None)
            fields=[dict(field_name=name,type=ty) for name,ty in zip(ts['column_names'][table],ts['column_types'][table])]
            fields=typed_fields(ev,own,fields)
            label=(definition or {}).get('display_name') or ts['fact'][table] or ts['relation_name'][table] or 'body'
            ref=dict(target_id=f'{case}: {label}',case=case,role='later' if same else 'other_case',ignore_names=not same,
                     native_selector={k:ts[k][table] for k in ('form','point','relation','fact')})
            ref['display_fields']=[dict(f) for f in fields]
            if not same:fields=[dict(f,field_name=None) for f in fields]
            grouped=dict(grouped,catalog_reference=ref)
            receipt=dict(source='gold_full_replay',artifact=replay['artifact'],table=table,case=case,
                         program_sha256=sha(text),kept_context_sha256=sha(values),complete=True)
            if kept_observation is not None:receipt['kept_observation']=kept_observation
            if is_target:targets.append((grouped,fields,ref,receipt))
            if same:
                allowed={d['definition']['display_name'] for d in adapter['availability']['definitions']}
                if label in allowed or ts['fact'][table] in ('ex_input','ex_output'):
                    available.append((grouped,fields,ref,receipt))
    result=(targets,gaps,case_receipts,available)
    ev.target_cache[key]=result
    return result
