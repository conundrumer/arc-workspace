"""Original-scope gold BODY transport, with same-session native kept evidence."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import time

from evaluator import canonical, sha
from study_paths import CODE_ROOT
from tables import Incomplete, full_kept_matches, comparison_type
from program_metadata import type_identity
from raw_body import body_schema


def _held_entries(native, table, report, old_by_fresh):
    reader=native['_native_reader'];entries=reader.bytable[table]
    mapping=report['body_assignment_map']
    if mapping.get('table')!=table:raise Incomplete('original BODY held map selects another table')
    rows=mapping.get('entries',[])
    by_entry={r['table_entry']:r for r in rows}
    if len(by_entry)!=len(rows) or set(by_entry)!=set(range(len(entries))):
        raise Incomplete('original BODY held map has incomplete or duplicate entries')
    result={}
    for ordinal,entry in enumerate(entries):
        mapped=by_entry[ordinal]
        kind=reader.entries['example_kind'][entry];index=reader.entries['example_index'][entry]
        if (mapped['example_kind'],mapped['example_index'],mapped['model'])!=(
                {0:'task',1:'train',2:'test'}[kind],index,reader.entries['model'][entry]):
            raise Incomplete('original BODY held entry differs from native example/model metadata')
        fresh=mapped['kept_assignment']
        if fresh is not None and (type(fresh) is not int or not 0<=fresh<len(report['kept_assignments'])):
            raise Incomplete('original BODY map has an invalid full-kept ordinal')
        result[entry]=list(old_by_fresh.get(fresh,[]))
    return result


@contextmanager
def capture(ev,record):
    """Keep FITS memo and original BODY in one independent native session.

    The second operation asserts the fresh ordered choices. Saved choices only
    filter through the shared joint Ident matcher; they never set native state.
    """
    with ev.fresh_session() as isolated:
        start=time.monotonic();kept=None;report=None;ledger=[];stage='source_metadata'
        folder=Path(tempfile.mkdtemp(prefix='gold-body-'+sha(record)[:16]+'-',dir=ev.artifacts))
        (folder/'program.arclog').write_text(record['gold_sexp']+'\n')
        try:
            native_ev=isolated.task_evaluator(record['task'])
            if not hasattr(native_ev,'gold_body') or not hasattr(native_ev,'gold_kept'):
                raise Incomplete('runtime lacks original gold_body/gold_kept endpoints')
            program=isolated.arclog.StudyProgram.from_sexp(record['gold_sexp'],isolated.settings)
            export=json.loads(isolated.arclog.study_program_export_json(program))
            views=[v for v in export['body_views'] if v['body_path']==record['point']]
            if len(views)!=1:raise Incomplete('original gold BODY path unavailable or ambiguous')
            view=views[0]
            # The checked IR's Layout may alpha-name authored labels (Key ->
            # P, P -> P2). Public bindings use its native decoded-source Layout.
            # Establish that spelling correspondence from the SAME program,
            # before acquiring values; never infer it from names or ordinals.
            decoded_export=json.loads(isolated.arclog.study_program_export_json(program.decode_source()))
            source_views=[v for v in decoded_export['body_views'] if v['body_path']==record['point']]
            if len(source_views)!=1:raise Incomplete('decoded source BODY path unavailable or ambiguous')
            source_view=source_views[0]
            if (source_view['owner_path']!=view['owner_path'] or source_view['kind']!=view['kind']
                    or source_view.get('input_port')!=view.get('input_port')):
                raise Incomplete('native source decoding changed original BODY ownership')
            physical={c['label_id']:c for c in view['columns']}
            source_labels={c['label_id']:c for c in source_view['columns']}
            if (len(physical)!=len(view['columns']) or len(source_labels)!=len(source_view['columns'])
                    or physical.keys()!=source_labels.keys()):
                raise Incomplete('native source decoding changed scoped BODY LabelIds')
            for label,column in physical.items():
                source_column=source_labels[label]
                if (column['body_column']!=source_column['body_column'] or
                        comparison_type(type_identity(isolated,record,column['type'])[0])!=
                        comparison_type(type_identity(isolated,record,source_column['type'])[0])):
                    raise Incomplete('native source decoding changed BODY physical column or type')
            evidence=json.loads(program.choice_evidence_json('[]'))
            if evidence.get('schema')!='arclog-study-choices-v1' or evidence.get('complete') is not True:
                raise Incomplete('original gold full DET schema unavailable')
            stage='gold_kept'
            at=time.monotonic();ledger.append(dict(operation=stage,status='started'))
            kept=json.loads(native_ev.gold_kept(program=program))
            ledger[-1].update(status=kept.get('status'),seconds=time.monotonic()-at)
            choices=isolated.validate_gold_observation(program,kept,record['task'])
            old_by_fresh=full_kept_matches(ev.legacy,choices,evidence['dets'],record)
            stage='gold_body'
            at=time.monotonic();ledger.append(dict(operation=stage,status='started',fits_walk=False))
            status,payload=native_ev.gold_body(program,record['point'],canonical(choices))
            report=json.loads(status)
            ledger[-1].update(status=report.get('status'),seconds=time.monotonic()-at)
            observed=isolated.validate_gold_observation(program,report,record['task'],schema='arclog-study-gold-body-v1')
            if (observed!=choices or report.get('gold_observation_ref')!=kept.get('gold_observation_ref')
                    or report.get('gold_observation_cached') is not True):
                raise Incomplete('original BODY did not reuse the exact native gold observation')
            if (report.get('body_path')!=record['point'] or report.get('owner_path')!=view['owner_path']
                    or report.get('body_status',{}).get('status')!='complete'
                    or report.get('body_coverage',{}).get('complete') is not True
                    or report.get('body_table_packed') is not True):
                raise Incomplete('original gold BODY scope, coverage or packing incomplete')
            coverage=report['body_coverage']['examples']
            for example in coverage:
                counts=example.get('model_counts')
                if (example.get('status',{}).get('status')!='complete' or
                        not isinstance(counts,list) or len(counts)!=len(choices) or
                        any(type(c) is not int or c<0 for c in counts)):
                    raise Incomplete('original BODY model enumeration is incomplete')
            native=isolated.legacy.native(payload);table=report['body_table'];ts=native['tables']
            if (type(table) is not int or not 0<=table<len(ts['form']) or
                    any(str(ts[k][table])!=str(v) for k,v in view['native_table_selector'].items() if k in ('form','point'))):
                raise Incomplete('original BODY native table differs from requested source')
            held=_held_entries(native,table,report,old_by_fresh)
            schema=body_schema(isolated,native,table,view)
            paths={Path(__file__).resolve(),Path(ev.legacy.__file__).resolve(),
                Path(ev.legacy.native.__code__.co_filename).resolve(),
                Path(ev.legacy.native.__globals__['_NATIVE'].__file__).resolve()}
            paths.update(CODE_ROOT/name for name in (
                'study_paths.py','native_correspondence.py','judgetool/evaluator.py','judgetool/tables.py',
                'judgetool/raw_body.py','judgetool/program_metadata.py',
                'judge2/render2/headers.py','judge2/render2/body.py'))
            implementation={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
            receipt=dict(source='gold_original_body',artifact=str(folder),implementation=implementation,
                original_source_sha256=sha(record),gold_program_sha256=sha(record['gold_sexp']),
                kept_context_sha256=sha(record['evaluation']['kept_assignments']),
                body_path=record['point'],owner_path=view['owner_path'],scope=report['body_scope'],table=table,
                source_label_correspondence=dict(proof='same native program decode_source; exact scoped LabelId, physical column and type',
                    checked_columns=view['columns'],source_columns=source_view['columns']),
                native_gold_kept_calls=1,native_gold_body_calls=1,native_mutant_replays=0,
                gold_observation_ref=report['gold_observation_ref'],native_axis_complete=True,
                full_kept_match=old_by_fresh,entry_kept_assignments=held,operations=ledger,
                settings=ev.receipt,test_fit=False,rows_complete='consumer native entry guards required',
                acquisition='original checked BODY with native cached full gold held context')
        except Exception as error:
            (folder/'failure.json').write_text(canonical(dict(stage=stage,reason=str(error),
                gold_kept_status=kept.get('status') if kept is not None else None,
                body_collection_status=report.get('status') if report is not None else None,
                body_status=report.get('body_status') if report is not None else None,
                prefix_status=report.get('prefix_status') if report is not None else None,
                operations=ledger,settings=ev.receipt))+'\n')
            if kept is not None:(folder/'gold-kept.json').write_text(canonical(kept)+'\n')
            if report is not None:(folder/'gold-body.json').write_text(canonical(report)+'\n')
            raise Incomplete('original gold BODY acquisition: '+str(error)+'; artifact='+str(folder)) from error
        (folder/'gold-kept.json').write_text(canonical(kept)+'\n')
        (folder/'gold-body.json').write_text(canonical(report)+'\n')
        (folder/'receipt.json').write_text(canonical(dict(receipt,seconds=time.monotonic()-start))+'\n')
        yield dict(ev=isolated,native=native,table=table,view=view,source_view=source_view,schema=schema,
                   held_entries=held,report=report,receipt=receipt)


def projection(body,record,binding):
    """Map the authenticated public fields to original BODY LabelIds/columns."""
    view=body['view'];schema=body['schema'];ev=body['ev']
    if binding['body_path']!=view['body_path'] or binding['owner_path']!=view['owner_path']:
        raise Incomplete('public projection belongs to another original BODY')
    by_label={c['ast_label_id']:c for c in schema}
    if len(by_label)!=len(schema):raise Incomplete('original BODY has ambiguous physical LabelIds')
    # capture authenticated this decoded-source view against the actual
    # checked program's LabelIds/physical layout. Authored spelling belongs to
    # that source Layout, not the compiler's alpha-named checked Layout.
    labels={c['label_id']:c for c in body['source_view']['columns']};indices=[]
    for field in binding['projected_schema']:
        source=field['source_body_column']
        if source is None:
            if field['type']!='Unit' or field.get('source_projection',{}).get('inserted_constant',{}).get('kind')!='unit':
                raise Incomplete('original BODY projection lacks certified inserted Unit')
            indices.append(None);continue
        identity=field['native_label_identity'];label=identity['label_id']
        if (identity.get('body_path',view['body_path'])!=view['body_path'] or label not in by_label
                or label not in labels or labels[label]['label_spelling']!=identity['source_label_spelling']):
            raise Incomplete('original BODY physical field lacks exact scoped source identity')
        column=by_label[label]
        if comparison_type(type_identity(ev,record,column['type'])[0])!=comparison_type(type_identity(ev,record,field['type'])[0]):
            raise Incomplete('original BODY physical field type differs')
        indices.append(column['index'])
    return indices
