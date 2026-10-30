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
from native_correspondence import Correspondence, AtomicPacked, Unavailable
from copy import deepcopy


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
            # Public fields refer to the decoded-source representation. The
            # native bridge supplies current paths/columns, including any
            # permutation or alpha renaming. Never rederive that bridge here.
            source_program=program.decode_source()
            source_export=json.loads(isolated.arclog.study_program_export_json(source_program))
            bridged=json.loads(isolated.arclog.study_program_export_json(program,source_program=source_program))
            correspondence=Correspondence(bridged,program_sexp=export['program_sexp'],
                source_program_sexp=source_export['program_sexp'])
            source_correspondence=Correspondence(source_export,program_sexp=source_export['program_sexp'],
                source_program_sexp=source_export['program_sexp'])
            view=correspondence.body_from_source(record['point'])
            source_view=source_correspondence.body(record['point'])
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
            status,payload=native_ev.gold_body(program,view['body_path'],canonical(choices))
            report=json.loads(status)
            ledger[-1].update(status=report.get('status'),seconds=time.monotonic()-at)
            observed=isolated.validate_gold_observation(program,report,record['task'],schema='arclog-study-gold-body-v1')
            if (observed!=choices or report.get('gold_observation_ref')!=kept.get('gold_observation_ref')
                    or report.get('gold_observation_cached') is not True):
                raise Incomplete('original BODY did not reuse the exact native gold observation')
            if (report.get('body_path')!=view['body_path'] or report.get('owner_path')!=view['owner_path']
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
            # The binding is consumed only alongside its original returned
            # payload. Persist the complete digest immediately; no later
            # report/payload rehydration is authorized by this live receipt.
            stage='packed_binding';binding_start=time.monotonic()
            native=isolated.legacy.native(payload);table=report['body_table']
            packed=AtomicPacked(report,native['_native_reader'],program_sexp=export['program_sexp'],side='gold')
            packed_table=packed.table(table,role='gold_body_kept')
            packed_receipt=packed.receipt(payload,report_sha256=sha(report),
                source_sha256=sha(record),runtime=isolated.receipt)
            (folder/'packed-acquisition.json').write_text(canonical(packed_receipt)+'\n')
            schema=deepcopy(native['_native_reader'].schema(table))
            if (len(schema)!=len(view['columns']) or
                    packed_table['cell_width']!=sum(c['physical_type']['cell_width'] for c in view['columns'])):
                raise Incomplete('original BODY physical width differs from native correspondence')
            for field in view['columns']:
                physical=field['physical_column'];descriptor=field['physical_type']
                if (type(physical) is not int or not 0<=physical<len(schema)
                        or schema[physical]['type'] not in (descriptor['type'],descriptor['wire_type'])):
                    raise Incomplete('original BODY packed physical type differs from native correspondence')
            held=_held_entries(native,table,report,old_by_fresh)
            binding_seconds=time.monotonic()-binding_start
            paths={Path(__file__).resolve(),Path(ev.legacy.__file__).resolve(),
                Path(ev.legacy.native.__code__.co_filename).resolve(),
                Path(ev.legacy.native.__globals__['_NATIVE'].__file__).resolve()}
            paths.update(CODE_ROOT/name for name in (
                'study_paths.py','native_correspondence.py','normalized_gold.py','prefix_universe.py','det_full_body.py','legacy_body_metadata.py','legacy_body_worker.py','ast/run/provenance.py','judgetool/evaluator.py','judgetool/tables.py',
                'judgetool/raw_body.py','judgetool/program_metadata.py',
                'judge2/render2/headers.py','judge2/render2/body.py'))
            implementation={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
            receipt=dict(source='gold_original_body',artifact=str(folder),implementation=implementation,
                original_source_sha256=sha(record),gold_program_sha256=sha(record['gold_sexp']),
                kept_context_sha256=sha(record['evaluation']['kept_assignments']),
                body_path=record['point'],owner_path=view['owner_path'],scope=report['body_scope'],table=table,
                source_label_correspondence=dict(schema='arclog-study-correspondence-v1',
                    proof='native source_body_path/source_body_column and scoped label mappings',
                    current_export_sha256=sha(bridged),source_export_sha256=sha(source_export),
                    correspondence_sha256=sha(bridged['correspondence'])),
                packed_acquisition=packed_receipt,packed_binding_seconds=binding_seconds,
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
                   correspondence=correspondence,source_correspondence=source_correspondence,
                   held_entries=held,report=report,receipt=receipt)


def projection(body,record,binding):
    """Look up public source fields in the certified current BODY layout."""
    view=body['view'];schema=body['schema'];ev=body['ev']
    source_view=body['source_correspondence'].body(binding['body_path'])
    if (binding['body_path']!=record['point'] or binding['owner_path']!=source_view['owner_path']
            or body['correspondence'].body_from_source(binding['body_path'])['body_path']!=view['body_path']):
        raise Incomplete('public projection belongs to another original BODY')
    indices=[]
    for field in binding['projected_schema']:
        source=field['source_body_column']
        if source is None:
            if field['type']!='Unit' or field.get('source_projection',{}).get('inserted_constant',{}).get('kind')!='unit':
                raise Incomplete('original BODY projection lacks certified inserted Unit')
            indices.append(None);continue
        try:
            original=body['source_correspondence'].body_column(binding['body_path'],source)
            identity=field['native_label_identity']
            if (identity.get('body_path',binding['body_path'])!=binding['body_path']
                    or identity['label_id']!=original['label_id']
                    or identity.get('owner_path',source_view['owner_path'])!=source_view['owner_path']
                    or identity.get('scope_path',original['scope_path'])!=original['scope_path']
                    or identity['source_label_spelling']!=original['canonical_source']['name']):
                raise Incomplete('public BODY field differs from native source identity')
            current=body['correspondence'].body_column_from_source(binding['body_path'],source,
                scope_path=original['scope_path'],label_id=original['label_id'])
        except Unavailable as error:
            raise Incomplete(str(error)) from error
        index=current['physical_column']
        if 'native_legacy_binding' in field:
            from native_correspondence import certify_legacy_body_projection
            try:
                proof=certify_legacy_body_projection(body['source_correspondence'],
                    body_path=binding['body_path'],source_column=source,field=field,
                    current_column=current,actual_type=schema[index]['type'],
                    source_program=record['gold_sexp'],
                    native_payload_sha256=record['native']['gold']['sha256'])
            except (Unavailable,KeyError,TypeError) as error:
                raise Incomplete('original BODY historical projection: '+str(error)) from error
            body['receipt'].setdefault('legacy_projection_bindings',[]).append(proof)
        elif comparison_type(type_identity(ev,record,schema[index]['type'])[0])!=comparison_type(type_identity(ev,record,field['type'])[0]):
            raise Incomplete('original BODY physical field type differs')
        indices.append(index)
    return indices


def projection_fields(body, binding, indices):
    """Canonical declared fields for the already certified fresh projection."""
    from native_correspondence import legacy_projection_field
    fields=binding['projected_schema']
    if len(fields)!=len(indices):
        raise Incomplete('original BODY projected fields and indices differ')
    result=[]
    for field,index in zip(fields,indices):
        if 'native_legacy_binding' not in field:
            result.append(deepcopy(field));continue
        proofs={sha(p):p for p in body['receipt'].get('legacy_projection_bindings',[])
                if p['source_column']==field['source_body_column'] and p['current_column']==index}
        if len(proofs)!=1:
            raise Incomplete('original BODY field lacks one exact historical projection proof')
        try:
            result.append(legacy_projection_field(field,projection=next(iter(proofs.values())),
                physical_column=index))
        except (Unavailable,KeyError,TypeError) as error:
            raise Incomplete('original BODY canonical projection field: '+str(error)) from error
    return result
