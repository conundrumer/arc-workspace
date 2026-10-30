"""Opt-in CURRENT-name X presentation over an authenticated saved TRAIN packet."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from native_correspondence import Unavailable,namespace_body_columns


def bind_adapter(producer, record, adapter):
    """Keep the source record and execution mutant; compose presentation only."""
    from evaluator import sha
    stored_binding=adapter['bindings']['mutant']
    if stored_binding['kind']=='Det':
        raise Unavailable('CURRENT-name DET reader projection requires a native current reader/header bridge')
    valid,current,_=producer.programs.load(record['programs']['mutant'],mutant_record=record,
                                          current_native_names=True)
    evidence=current['current_native_names']
    stored=evidence['stored_export'];own=evidence['current_export']
    program=producer.engine.StudyProgram.from_sexp(record['programs']['mutant'],producer.programs.settings).decode_source()
    if program.sexp()!=stored['program_sexp']:
        raise Unavailable('stored metadata handle differs from certified stored writer')
    base=Path(adapter['source']['native_base']);table=stored_binding['native_table_index']
    reader=producer.read_native(record['native']['mutant'],base)
    schema=deepcopy(reader.schema(table))
    legacy=producer.legacy_body_metadata.bind(record=record,side='mutant',base=base,reader=reader,
        table=table,schema=schema,program=program,export=stored,body_path=stored_binding['body_path'],force=True)
    mapping=namespace_body_columns(own,stored,evidence['namespace_correspondence'],legacy,stored_binding['body_path'])
    views=[v for v in own['body_views'] if v['body_path']==mapping['body']['body_path']]
    if len(views)!=1:raise Unavailable('CURRENT namespace BODY view is ambiguous')
    view=views[0];view_columns={c['body_column']:c for c in view['columns']}
    current_schema=[];by_current={}
    for link in mapping['columns']:
        field=link['current'];index=field['physical_column'];native=view_columns[index]
        if native['label_id']!=field['label_id'] or native['type']!=field['physical_type']['type']:
            raise Unavailable('CURRENT SELF view differs from native correspondence')
        raw=deepcopy(schema[link['storage']['physical_column']])
        raw.update(index=index,type=native['type'],name=native['native_column_name'],label=native['label_spelling'],
            ast_label_id=field['label_id'],source_label='@label:'+str(field['label_id']),display_name=native['label_spelling'],
            native_label_identity=dict(kind='scoped_label',label_id=field['label_id'],scope_path=field['scope_path'],
                source_label_spelling=field['canonical_source']['name'],body_path=view['body_path'],owner_path=view['owner_path']))
        current_schema.append(raw);by_current[index]=link
    current_schema.sort(key=lambda c:c['index'])
    if [c['index'] for c in current_schema]!=list(range(len(current_schema))):
        raise Unavailable('CURRENT BODY physical layout is not dense')
    ctx=producer.policy['Document'].__new__(producer.policy['Document'])
    ctx.readers={'mutant':reader};ctx.mexport=own;ctx.body=view;ctx.owner=view['owner_path']
    projected,_,_=ctx.target_projection(reader,current_schema,{},body_side='mutant')
    fields=[];storage_fields=[];columns=[];storage_projection=[]
    for c in projected:
        index=c['source_body_column']
        if index is None:
            if c['type']!='Unit' or c['source_projection'].get('inserted_constant',{}).get('kind')!='unit':
                raise Unavailable('CURRENT projection has an uncertified virtual field')
            storage=None;old=deepcopy(c);link=dict(inserted_constant=deepcopy(c['source_projection']))
        else:
            link=by_current[index];storage=link['storage']['physical_column']
            candidates=[f for f in stored_binding['projected_schema'] if f['source_body_column']==storage]
            if not candidates:raise Unavailable('CURRENT projection adds a field absent from the stored target')
            old=deepcopy(candidates[0])
            if any(f.get('native_legacy_binding')!=old.get('native_legacy_binding') or f['type']!=old['type'] for f in candidates):
                raise Unavailable('stored target aliases disagree on native storage authority')
        field=dict(physical_index=c['index'],field_name=c['display_name'],native_name=c['name'],
            native_label_identity=deepcopy(c['native_label_identity']),type=c['type'],frame=c['frame'],
            callable_row_path=deepcopy(c['callable_row_path']),source_body_column=index,
            source_projection=deepcopy(c['source_projection']))
        fields.append(field);storage_fields.append(old);storage_projection.append(storage);columns.append(deepcopy(link))
    if Counter(storage_projection)!=Counter(f['source_body_column'] for f in stored_binding['projected_schema']):
        raise Unavailable('CURRENT and stored native target projections differ in field coverage')
    atom=ctx.callable_atom(projected,'&X')
    binding=dict(stored_binding,body_path=view['body_path'],owner_path=view['owner_path'],
        native_selector=deepcopy(view['native_table_selector']),source_body_schema=current_schema,
        fields=fields,projected_schema=fields,callable_template=atom)
    result=dict(adapter,bindings=dict(adapter['bindings'],mutant=binding),
        input=dict(adapter['input'],binding=binding,fields=fields,callable_template=atom))
    result['_current_native_names']=dict(evidence,stored_binding=stored_binding,storage_fields=storage_fields,
        storage_projection=storage_projection,current_binding=binding,columns=columns,legacy_binding=legacy,
        current_schema=current_schema,current_physical_schema=deepcopy(view['columns']),source_record_sha256=sha(record))
    return result


def acquire_point(ev, record, adapter, ntrain, ntest, *, copy_rows, include_projected_flows):
    """Decode only the certified storage indices through the ordinary evaluator."""
    from evaluator_train import acquire_train_point
    info=adapter['_current_native_names'];old=dict(info['stored_binding'],projected_schema=info['storage_fields'])
    for field,index in zip(old['projected_schema'],info['storage_projection']):
        if field['source_body_column']!=index:
            raise Unavailable('storage TRAIN field differs from admitted native projection')
    ordinary=dict(adapter,bindings=dict(adapter['bindings'],mutant=old),
        input=dict(adapter['input'],binding=old,fields=old['projected_schema']))
    ordinary.pop('_current_native_names')
    packet=acquire_train_point(ev,record,ordinary,ntrain,ntest,side='mutant',copy_rows=copy_rows,
                               include_projected_flows=include_projected_flows)
    if packet['missing']:raise Unavailable('CURRENT namespace X acquisition has missing TRAIN axes')
    if packet['projection']!=info['storage_projection']:
        raise Unavailable('actual TRAIN storage projection differs from native namespace proof')
    return dict(packet,fields=deepcopy(info['current_binding']['projected_schema']),
        source_schema=deepcopy(info['current_schema']),
        projection=[c['source_body_column'] for c in info['current_binding']['projected_schema']],
        current_native_names_acquisition=dict(storage_projection=packet['projection'],
            storage_schema=packet['source_schema'],columns=info['columns'],legacy_binding=info['legacy_binding']))


def file_digest(path):
    path=Path(path);digest=hashlib.sha256();size=0
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk);size+=len(chunk)
    return dict(sha256=digest.hexdigest(),bytes=size)


def write_receipt(ev, pair_id, record, target, adapter, packet, public, output, private):
    """Persist only evidence from the same validated acquisition/public packet."""
    from evaluator import sha
    from evaluator_train import dependency_receipt
    from legacy_body_metadata import _loaded_numeric_build
    from judge3.dataset_format import write_json
    from study_paths import DATA_ROOT
    info=adapter['_current_native_names'];binding=info['current_binding'];old=info['stored_binding']
    locator=target.get('source_locator');source_sha=target.get('source_original_sha256')
    if not isinstance(locator,dict) or source_sha!=sha(record):
        raise Unavailable('CURRENT-name receipt lacks authenticated original SourceReader locator/digest')
    if (public['fields']!=[dict(index=i,name=f['field_name'],type=f['type'],
            **{k:deepcopy(f[k]) for k in ('frame','callable_row_path') if k in f})
            for i,f in enumerate(packet['fields'])]
            or public['callable_atom']!=binding['callable_template'] or public['missing'] or packet['missing']):
        raise Unavailable('CURRENT-name receipt public fields/callable/coverage differ from acquired packet')
    entries=[dict(assignment=e['assignment'],train=e['train'],model=e['model'],row_count=e['row_count']) for e in public['entries']]
    acquired=[dict(assignment=e['assignment'],train=e['example_index'],model=e['model'],row_count=e['row_count']) for e in packet['entries']]
    if entries!=acquired or public['required']!=packet['required'] or packet['receipt']['source_sha256']!=source_sha:
        raise Unavailable('CURRENT-name receipt entry/model summaries differ from acquired packet')
    root=Path(private).resolve()/'current-native-names';root.mkdir(parents=True,exist_ok=True)
    if not root.is_relative_to(DATA_ROOT.resolve()):raise Unavailable('CURRENT-name receipt must stay under private data root')
    evidence_root=root/pair_id;evidence_root.mkdir(exist_ok=True)
    def save(name,value):
        path=evidence_root/(name+'.json');write_json(path,value)
        return dict(path=str(path),sha256=file_digest(path)['sha256'])
    present=sorted({(e['assignment'],1,e['train']) for e in public['entries']})
    if [list(v) for v in present]!=packet['required']:
        raise Unavailable('CURRENT-name receipt required/present TRAIN axes differ')
    acquisition=dict(receipt=deepcopy(packet['receipt']),kept_context_sha256=sha(record['evaluation']['kept_assignments']),
        required_axes=deepcopy(packet['required']),present_axes=[list(v) for v in present],missing_axes=[],
        entries=entries,complete=True,complete_rows=True)
    files={name:save(name,value) for name,value in dict(source_record=record,current_export=info['current_export'],
        stored_export=info['stored_export'],namespace_correspondence=info['namespace_correspondence'],acquisition=acquisition).items()}
    raw=lambda text:hashlib.sha256(text.encode()).hexdigest()
    producer={k:record[k] for k in ('engine_commit','wheel_sha256','native_binary_sha256')}
    storage_schema=packet['current_native_names_acquisition']['storage_schema']
    public_x=dict(path='tables/X.json',**file_digest(Path(output)/'tables/X.json'),fields_sha256=sha(public['fields']),
        required=deepcopy(public['required']),missing=[],entries=entries)
    implementation=dependency_receipt()
    from study_paths import CODE_ROOT
    for name in ('judge2/render2/structured.py','judge3/nonrender_metadata.py','judge3/export_dataset.py',
                 'judge3/export_by_pair_id.py','judge3/feature_payload.py','judge3/dataset_format.py',
                 'judge3/column_paths.py','judge2/render2/column_paths.py','ast/run/mech5/metadata.py'):
        path=CODE_ROOT/name
        if path.exists():implementation[str(path.resolve())]=file_digest(path)['sha256']
    receipt=dict(schema='study-current-native-names-x-v1',pair_id=pair_id,
        source=dict(source_sha256=source_sha,codec='evaluator.canonical-sha256',locator=deepcopy(locator),
            task=record['task'],case=record['case'],point=record['point'],
            gold_program_sha256=raw(record['programs']['gold']),stored_mutant_program_sha256=raw(record['programs']['mutant']),
            identity=deepcopy(record['identity']),identity_sha256=sha(record['identity'])),
        runtime=dict(build=_loaded_numeric_build(),evaluator=deepcopy(ev.receipt),implementation=implementation),
        current=dict(identity=deepcopy(info['identity']),identity_sha256=sha(info['identity']),
            program_sha256=raw(info['current_export']['program_sexp']),body_path=binding['body_path'],
            export_sha256=sha(info['current_export']),namespace_correspondence_sha256=sha(info['namespace_correspondence']),
            identity_certificate=deepcopy(info['identity_certificate']),
            public_mutant=dict(path='mutant.arclog',**file_digest(Path(output)/'mutant.arclog'))),
        binding=dict(storage=dict(native_ref=deepcopy(record['native']['mutant']),producer=producer,
            report_role='mutant_kept' if record['evaluation']['table_indices'].get('mutant_kept')==old['native_table_index'] else 'mutant_all',
            table=old['native_table_index'],selector=old['native_selector'],physical_schema=storage_schema,
            physical_schema_sha256=sha(storage_schema),projection=info['storage_projection']),
            current=dict(body_path=binding['body_path'],owner_path=binding['owner_path'],physical_schema=info['current_physical_schema'],
                physical_schema_sha256=sha(info['current_physical_schema']),columns=info['columns']),
            public=dict(fields=deepcopy(public['fields']),fields_sha256=sha(public['fields']),callable_atom=public['callable_atom'],
                callable_atom_sha256=sha(public['callable_atom'])),receipts=[info['legacy_binding']['receipt'],packet['current_native_names_acquisition']]),
        acquisition=acquisition,public_x=public_x,files=files,authority='same authenticated acquisition and synchronous serialization',
        test_cells=False,test_fit=False)
    path=root/(pair_id+'.json');write_json(path,receipt)
    return dict(path=str(path),sha256=file_digest(path)['sha256'])
