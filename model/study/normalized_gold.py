"""Selective normalized GOLD artifact publication with immutable pair provenance.

The current whole-gold-kept row policy is explicit. No prefix-row safety or
normalization row-equivalence is asserted. Original X/ValidMutant stay untouched.
"""
from copy import deepcopy
import ast
from collections import Counter, OrderedDict
from pathlib import Path
from types import SimpleNamespace
import gzip
import hashlib
import json
import os
import shutil
import sys

from study_paths import CODE_ROOT, DATA_ROOT
from native_correspondence import NormalizedGoldView, Unavailable

POLICY='normalized-gold-view-v1'
ROW_POLICY='whole-gold-kept-v1'
SUPERSEDED_MANIFEST='a2b1f8abebe27e207714d7f917061ee74dce24f9fba9989a94e69648da9ff03f'
_CACHE={}
_CASES=OrderedDict()
_PERFORMANCE=Counter()
_PRIOR_RECEIPTS={}
_ACQUISITION_PREDECESSORS=(
    'acf923e5591bbf9ca07c53acf2d0c1845f7704e96a7618fdb0b0eba309893b3e',
    '3ac800acaa7f0bdb47046e5a369a82a732a9ccee0bb262eb1276745e64651a03',
    'ef420d27f50c70fa252dd797bdda26fce1ea7cd77cccf057df21d93912c4cbe3')
_MANIFESTS={}
_SOURCES={}
_BUILDS={}
_DECODER_BINDINGS={}

# Additive metadata binding/anonymous-name checks do not change cached row acquisition.
_METADATA_PREDECESSORS={'../native_correspondence.py': '2d056498bd8d350147db68faa35df51c403ccbe9d707d4877d5c2c0daf6648f0', 'program_metadata.py': 'a9fa67ae77c69aeea3b1adf9dd8dea2f31879a905ab9bd3631023e9ab4d18f66'}


def publication_performance():
    return dict(_PERFORMANCE)


def _sha(value):
    from evaluator import sha
    return sha(value)


def _file(path):
    digest=hashlib.sha256();size=0
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk);size+=len(chunk)
    return dict(sha256=digest.hexdigest(),bytes=size)


def _read(path):
    path=Path(path)
    if path.stat().st_size>64*1024*1024:raise ValueError('normalized metadata exceeds64MiB')
    return json.loads(path.read_text())


def _write(path,value):
    from judge3.dataset_format import write_json
    write_json(Path(path),value,compact=True)


def _manifest(ref):
    if ref['sha256']==SUPERSEDED_MANIFEST:
        raise ValueError('superseded normalization manifest; actual static_pruning=True decoder scope required')
    path=Path(ref['path']).resolve()
    if _file(path)['sha256']!=ref['sha256']:raise ValueError('normalization manifest SHA differs')
    key=(str(path),ref['sha256'])
    if key not in _MANIFESTS:
        manifest=_read(path);files={}
        source_receipt=_read(path.parent/'source-receipt.json')
        if source_receipt.get('manifest_sha256')!=ref['sha256']:
            raise ValueError('normalization manifest source-receipt binding differs')
        evidence_ref=manifest.get('enabled_decoder_evidence')
        if not isinstance(evidence_ref,dict):raise ValueError('actual enabled-decoder evidence reference missing')
        evidence_path=Path(evidence_ref['path']).resolve()
        if not evidence_path.is_relative_to(DATA_ROOT.resolve()):raise ValueError('decoder evidence escapes DATA_ROOT')
        if _file(evidence_path)['sha256']!=evidence_ref['sha256']:raise ValueError('enabled-decoder evidence SHA differs')
        evidence=_read(evidence_path)
        if evidence.get('schema')!='arclog-gold-enabled-decoder-evidence-v1':raise ValueError('enabled-decoder evidence schema differs')
        programs_ref=evidence['programs'];programs_path=Path(programs_ref['path']).resolve()
        if not programs_path.is_relative_to(DATA_ROOT.resolve()) or _file(programs_path)['sha256']!=programs_ref['sha256']:
            raise ValueError('enabled-decoder programs SHA/path differs')
        if programs_ref['index_key']!=['task','case','original_program_sha256']:
            raise ValueError('enabled-decoder index contract differs')
        decoder_rows=[json.loads(line) for line in programs_path.read_text().splitlines() if line]
        if len(decoder_rows)!=programs_ref['rows']:raise ValueError('enabled-decoder row count differs')
        if any(manifest['artifacts'].get(str(q))!=h for q,h in
                ((evidence_path,evidence_ref['sha256']),(programs_path,programs_ref['sha256']))):
            raise ValueError('enabled-decoder files are not bound in manifest artifacts')
        # These authenticated frozen artifacts are referenced more than once.
        # Share their read-only decoded objects instead of decoding duplicates.
        loaded={evidence_path:evidence,programs_path:decoder_rows}
        for name,wanted in manifest['artifacts'].items():
            file=path.parent/name
            if _file(file)['sha256']!=wanted:raise ValueError('normalization manifest artifact differs: '+name)
            resolved=file.resolve()
            if resolved not in loaded:
                _PERFORMANCE['frozen_artifact_decodes']+=1
                loaded[resolved]=_read(file) if file.suffix=='.json' else [json.loads(line) for line in file.read_text().splitlines() if line]
            files[name]=loaded[resolved]
        for name in ('programs','points','pairs','overlays'):
            selected=Path(manifest[name+'_path']).resolve() if name+'_path' in manifest else (path.parent/(name+('.json' if name=='programs' else '.jsonl'))).resolve()
            keys=[k for k in manifest['artifacts'] if (path.parent/k).resolve()==selected]
            if len(keys)!=1:raise ValueError('manifest consumer input lacks a unique authenticated artifact: '+name)
            files[name+('.json' if name=='programs' else '.jsonl')]=files[keys[0]]
        files['_enabled_decoder']=dict(evidence=evidence,reference=evidence_ref,programs_reference=programs_ref,
            rows=decoder_rows,source_receipt=source_receipt,source_receipt_file=_file(path.parent/'source-receipt.json'))
        _MANIFESTS[key]=(manifest,files)
    return _MANIFESTS[key]


def publication_operations(manifest_ref):
    """Read-only authenticated operations shared with the process driver."""
    return _manifest(manifest_ref)[1]['points.jsonl']


def _decoder_stream_binding(engine, settings, program, actual_stream, observed, *, runtime_sha256):
    """Bind token stepping, without transferring an emitter AST path map.

    Stored evidence hashes the from_sexp handle. The acquisition may use a
    decode_source handle with the same writer/ids/model and different scalar
    emitter paths. Verify the stored full hash in its ORIGINAL representation,
    then compare only the ordered ids/model that Session.decoder consumed.
    Source/BODY/column identities remain the normalizer's own native proof.
    """
    from native_correspondence import _native_stream
    writer=program.sexp();writer_sha=hashlib.sha256(writer.encode('utf-8')).hexdigest()
    actual={k:actual_stream[k] for k in ('ids','model','paths')}
    key=(runtime_sha256,writer_sha,observed['stream_sha256'],_sha(actual),_sha(settings))
    if key in _DECODER_BINDINGS:return deepcopy(_DECODER_BINDINGS[key])
    if _sha(actual)==observed['stream_sha256']:
        stream=actual;representation='exact acquisition stream'
    else:
        evidence_settings=engine.DecodeSettings(**settings)
        parsed=engine.StudyProgram.from_sexp(writer,evidence_settings)
        if parsed.sexp()!=writer:raise Unavailable('enabled-decoder from_sexp native writer differs')
        stream=_native_stream(parsed);representation='from_sexp'
        if _sha(stream)!=observed['stream_sha256']:
            raise Unavailable('enabled-decoder from_sexp full native stream SHA differs')
    if stream['ids']!=actual['ids'] or stream['model']!=actual['model']:
        raise Unavailable('enabled-decoder ordered token IDs/model flags differ')
    differences=[i for i,(a,b) in enumerate(zip(stream['paths'],actual['paths'])) if a!=b]
    binding=dict(schema='enabled-decoder-token-stream-binding-v1',program_sha256=writer_sha,
        decoder_representation=representation,decoder_full_stream_sha256=_sha(stream),
        acquisition_full_stream_sha256=_sha(actual),
        ordered_ids_model_sha256=_sha({k:stream[k] for k in ('ids','model')}),
        ordered_ids_model_equal=True,paths_equal=not differences,path_difference_count=len(differences),
        first_path_difference=None if not differences else dict(token_index=differences[0],
            decoder_path=stream['paths'][differences[0]],acquisition_path=actual['paths'][differences[0]]),
        authority='token stepping only; no AST path, scoped label, BODY column or row-equivalence authority')
    if len(_DECODER_BINDINGS)>=32:_DECODER_BINDINGS.clear()
    _DECODER_BINDINGS[key]=binding
    return deepcopy(binding)


def _decoder_record(ev, files, task, case, view):
    """Bind the real static-on decoder run, separately from row evaluation."""
    original_sha=hashlib.sha256(view.original.sexp().encode('utf-8')).hexdigest()
    matches=[r for r in files['_enabled_decoder']['rows'] if
             (r.get('task'),r.get('case'),r.get('original_program_sha256'))==(task,case,original_sha)]
    if len(matches)!=1:raise Unavailable('actual enabled-decoder program evidence missing or ambiguous')
    row=matches[0]
    if row.get('settings',{}).get('static_pruning') is not True or row.get('decode_operation')!='Session.decoder token stepping':
        raise Unavailable('enabled-decoder operation/settings evidence differs')
    stream_bindings={}
    for side,program in (('original',view.original),('normalized',view.program)):
        observed=row[side];stream=view.proof[side]['stream']
        if observed['program_sha256']!=hashlib.sha256(program.sexp().encode('utf-8')).hexdigest():
            raise Unavailable('enabled-decoder '+side+' writer SHA differs')
        if stream.get('status')!='complete':raise Unavailable('enabled-decoder '+side+' native stream metadata unavailable')
        stream_bindings[side]=_decoder_stream_binding(ev.arclog,row['settings'],program,stream,observed,
            runtime_sha256=ev.runtime['binary_sha256'])
    normalized=row['normalized']
    if normalized.get('status')!='complete':raise Unavailable('normalized actual static-on decode did not complete')
    stream=view.proof['normalized']['stream'];total=len(stream['ids']);model=sum(bool(v) for v in stream['model'])
    for key,wanted in (('consumed_tokens',total),('total_tokens',total),('consumed_model_tokens',model),('forced_tokens',total-model)):
        if type(normalized.get(key)) is not int or normalized[key]!=wanted:
            raise Unavailable('normalized enabled-decoder token accounting differs: '+key)
    if normalized.get('grammar_complete') is not True:
        raise Unavailable('normalized enabled-decoder grammar did not consume the complete stream')
    # CONSISTENT OUT / bounded FITS observation remains separate evidence.
    source_ref=row['source_ref'];source_path=Path(source_ref['path']).resolve()
    if not source_path.is_relative_to(DATA_ROOT.resolve()) or _file(source_path)['sha256']!=source_ref['sha256']:
        raise ValueError('enabled-decoder original source manifest SHA differs')
    # Retain original refusal as an observation; it is never rewritten as a
    # successful decode. Complete normalized evidence binds the entire stream.
    runtime_ref=row['runtime_ref'];ready_path=Path(runtime_ref['path']).resolve()
    if not ready_path.is_relative_to(DATA_ROOT.resolve()) or _file(ready_path)['sha256']!=runtime_ref['sha256']:
        raise ValueError('enabled-decoder runtime receipt SHA/path differs')
    build_key=(str(ready_path),runtime_ref['sha256'],ev.runtime['binary_sha256'])
    if build_key not in _BUILDS:
        if str(CODE_ROOT/'ast/run') not in sys.path:sys.path.insert(0,str(CODE_ROOT/'ast/run'))
        from provenance import load_build
        ready=_read(ready_path)
        build=load_build(ev.arclog,SimpleNamespace(build_receipt=ready_path,
            engine_commit=ready['revision'],wheel=None))
        if ev.runtime['binary_sha256'] not in build['native_binary_sha256'].values():
            raise ValueError('decoder evidence build and acquisition native binary differ')
        _BUILDS[build_key]=build
    return dict(record=deepcopy(row),record_sha256=_sha(row),
        evidence=files['_enabled_decoder']['reference'],build=_BUILDS[build_key],stream_bindings=stream_bindings,
        distinction='actual enabled decoder observation; acquisition settings/row policy are retained separately')


def _json_digest(value):
    digest=hashlib.sha256()
    for chunk in json.JSONEncoder(sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).iterencode(value):
        digest.update(chunk.encode('utf-8'))
    return digest.hexdigest()


def _source(binding,task):
    if str(CODE_ROOT/'ast/run') not in sys.path:sys.path.insert(0,str(CODE_ROOT/'ast/run'))
    import mech5._paths
    from mech.source_read import SourceReader
    source=dict(binding['source'],corpus=str(DATA_ROOT/'ast/run'/Path(binding['source']['corpus']).name))
    key=(str(source['corpus']),task,source['file'],source['line'],binding['source_sha256'])
    if key not in _SOURCES:
        reader=SourceReader(CODE_ROOT)
        try:record=reader.record(dict(task=task,source=source,source_sha256=binding['source_sha256']))
        finally:reader.close()
        _SOURCES[key]=(record,source)
    return _SOURCES[key]


def _case_source(files,task,case):
    rows=[p for p in files['points.jsonl'] if p['task']==task and p['case']==case and p.get('source_program_bindings')]
    if not rows:raise Unavailable('normalized case lacks authenticated original source binding: '+case)
    record,locator=_source(rows[0]['source_program_bindings'][0],task)
    specs=[p for p in files['programs.json'] if p['task']==task and p['case']==case]
    if len(specs)!=1:raise Unavailable('normalized program specification missing or ambiguous')
    text=Path(specs[0]['original_program']).read_text()
    if _file(specs[0]['original_program'])['sha256']!=specs[0]['original_program_sha256']:
        raise ValueError('original normalized-program source file SHA differs')
    if text.strip()!=record['gold_sexp'].strip():raise ValueError('manifest gold and source record differ')
    return record,locator,specs[0]


def _producer(ev,record,locator):
    from judge3.nonrender_metadata import MetadataProducer
    return MetadataProducer(engine=ev.arclog,read_native=lambda *args:None,
        corpus=Path(locator['corpus']),settings=ev.settings,case_inventory={})


def _normalized_export(ev,view,original_export):
    """Carry authenticated display names through the native editor relation map.

    The original name map's stream identity cannot be attached to a different
    normalized stream. Only native source-relation correspondence moves names;
    native attachment validates the resulting exact stream/slots/identities.
    """
    naming=deepcopy(original_export.get('relation_source_names'))
    if naming is not None:
        rows=[]
        for source in naming['relations']:
            mapped=view.relation(source['relation_slot'])
            rows.append(dict(source,relation_slot=mapped['relation_slot'],native_relation=mapped['relation']))
        rows.sort(key=lambda row:row['relation_slot'])
        if [r['relation_slot'] for r in rows]!=list(range(len(rows))):
            raise Unavailable('normalized source-name relation map incomplete or ambiguous')
        naming.update(relations=rows,stream_identity={k:view.proof['normalized']['stream'][k] for k in ('ids','model')},
            normalization_source_names=dict(original_map_sha256=_sha(original_export['relation_source_names']),
                normalization_provenance_sha256=_sha(view.proof),authority='native editor source relation correspondence'))
    return json.loads(ev.arclog.study_program_export_json(view.program,
        None if naming is None else json.dumps(naming),source_program=view.program))


def _prior_receipt(ev,provider_sha):
    """Reproduce a compatible predecessor's exact existing code-closure hash.

    Keep the canonical evaluator's dependency list as the sole list. Verify
    the live closure before substituting only this provider's known previous
    bytes; every other setting/code digest must still match a saved cache key.
    """
    key=(_sha(ev.receipt),provider_sha)
    if key in _PRIOR_RECEIPTS:return _PRIOR_RECEIPTS[key]
    import evaluator
    source=Path(evaluator.__file__).resolve()
    tree=ast.parse(source.read_text(),str(source))
    init=next(n for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='ReplayEvaluator'
        for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
    receipt=next(n.value for n in ast.walk(init) if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Attribute) and isinstance(t.value,ast.Name)
                and t.value.id=='self' and t.attr=='receipt' for t in n.targets))
    expression=next(k.value for k in receipt.keywords if k.arg=='implementation_sha256')
    names=ast.literal_eval(expression.args[0].generators[0].iter)
    hashes={name:_file(source.parent/name)['sha256'] for name in names}
    if _sha(hashes)!=ev.receipt['implementation_sha256']:
        raise ValueError('live evaluator implementation closure differs from receipt')
    hashes.update(_METADATA_PREDECESSORS)
    hashes['../normalized_gold.py']=provider_sha
    prior=dict(ev.receipt,implementation_sha256=_sha(hashes))
    _PRIOR_RECEIPTS[key]=prior
    if len(_PRIOR_RECEIPTS)>16:_PRIOR_RECEIPTS.clear()
    return prior


def _case(ev,files,task,case,cache):
    """Reuse immutable handles/exports/decoded packets, not just gzip bytes.

    Retain both identity owners so Python id reuse cannot alias another
    evaluator or manifest. Bound the cache to four cases in one task; callers
    format/copy these packets without mutating their acquisition evidence.
    """
    key=(id(ev),id(files),task,case,str(Path(cache).resolve()))
    if key in _CASES:
        _PERFORMANCE['case_bundle_hits']+=1
        _CASES.move_to_end(key)
        return _CASES[key][2]
    if _CASES and next(iter(_CASES))[2]!=task:_CASES.clear()
    _PERFORMANCE['case_bundle_misses']+=1
    result=_acquire_case(ev,files,task,case,cache)
    _CASES[key]=(ev,files,result)
    while len(_CASES)>4:_CASES.popitem(last=False)
    return result


def _acquire_case(ev,files,task,case,cache):
    """One normalized case acquisition, shared across affected point artifacts."""
    from evaluator import canonical
    from evaluator_train import acquire_train_table,select_train_full_rows,_input_train
    from tables import full_kept_matches
    record,locator,spec=_case_source(files,task,case)
    producer=_producer(ev,record,locator)
    # Use the checked source representation used by the frozen decoder
    # evidence, rather than decode_source()'s different emitter layout.
    original=ev.arclog.StudyProgram.from_sexp(record['gold_sexp'],ev.settings)
    names,_=producer.programs.source_names(original,record['gold_sexp'],record)
    from program_metadata import export_named_program
    original_export=export_named_program(ev,original,names) if names is not None else json.loads(
        ev.arclog.study_program_export_json(original,source_program=original))
    if original_export['program_sexp']!=record['gold_sexp']:
        raise Unavailable('normalized source SELF export writer differs from original record')
    view=NormalizedGoldView.acquire(original)
    decoder=_decoder_record(ev,files,task,case,view)
    needed=[]
    for operation in files['points.jsonl']:
        if operation['task']!=task:continue
        for artifact in operation['artifacts']:
            if artifact.get('table_id') and artifact['table_id']!='G' and artifact['case']==case:
                needed.append(artifact['source_name'])
    needed=set(needed)
    selectors=[]
    for name in sorted(needed):
        if name in ('input','ex_input','ex_output'):
            selectors.append(dict(fact='ex_input' if name=='input' else name))
        else:
            definitions=[d for d in original_export['definitions']['native_relations'] if d['display_name']==name]
            if len(definitions)!=1:raise Unavailable('required original relation name is ambiguous: '+name)
            selectors.append(view.relation(definitions[0]['relation_slot'])['native_selector'])
    export=_normalized_export(ev,view,original_export)
    key=dict(task=task,case=case,source=_sha(record['gold_sexp']),normalized=_sha(view.program.sexp()),
        mapper=_sha(view.proof),settings=ev.receipt,row_policy=ROW_POLICY,policy=POLICY,
        required_source_names=sorted(needed),original_kept_sha256=_sha(record['evaluation']['kept_assignments']),
        task_input=_file(Path(ev.cfg['tasks'])/(task+'.json')),
        enabled_decoder_evidence=decoder['record_sha256'],
        implementation={name:_file(CODE_ROOT/name)['sha256'] for name in ('normalized_gold.py','native_correspondence.py')})
    digest=_sha(key)
    if not needed:
        return dict(key=key,tables=[],view=view,producer=producer,record=record,export=export,
            original_export=original_export,receipt=dict(source_kind='metadata_only_no_relation_acquisition',
                enabled_decoder=decoder,normalization_report=view.report))
    if digest in _CACHE:
        return dict(_CACHE[digest],view=view,producer=producer,record=record,export=export,original_export=original_export)
    folder=Path(cache)/'normalized-gold';folder.mkdir(parents=True,exist_ok=True)
    saved=folder/(digest+'.json.gz');saved_key=key
    if not saved.exists():
        # Only formatting/cache-reuse changed in these exact predecessors.
        # Reuse their actual acquisition keys/provenance without relabeling.
        for prior_sha in _ACQUISITION_PREDECESSORS:
            prior_key=deepcopy(key)
            prior_key['implementation']['normalized_gold.py']=prior_sha
            prior_key['implementation']['native_correspondence.py']=_METADATA_PREDECESSORS['../native_correspondence.py']
            prior_key['settings']=_prior_receipt(ev,prior_sha)
            prior=folder/(_sha(prior_key)+'.json.gz')
            if prior.exists():
                saved=prior;saved_key=prior_key;break
    if saved.exists():
        with gzip.open(saved,'rt') as stream:bundle=json.load(stream)
        if bundle.get('key')!=saved_key:raise ValueError('normalized acquisition cache identity differs')
        claimed=bundle.pop('content_sha256',None)
        if claimed!=_json_digest(bundle):raise ValueError('normalized acquisition cache content digest differs')
        bundle['content_sha256']=claimed
    else:
        task_input=_read(Path(ev.cfg['tasks'])/(task+'.json'));ntrain=len(task_input['train']);ntest=len(task_input['test'])
        with ev.fresh_session() as isolated:
            native_ev=isolated.task_evaluator(task)
            kept=json.loads(native_ev.gold_kept(view.program))
            choices=isolated.validate_gold_observation(view.program,kept,task)
            dets=json.loads(view.program.choice_evidence_json('[]'))
            # This matches actual fresh normalized values to original contexts;
            # native source paths alone never assert held or family equivalence.
            matched=full_kept_matches(ev.legacy,choices,dets['dets'],record)
            original_kept=record['evaluation']['kept_assignments']
            selection=dict(task=task,case=case,gold_sexp=view.program.sexp(),context_schema='normalized-gold-selection-v1',evaluation=dict(kept_assignments=original_kept))
            def required_table(ts,index):
                return any((ts['fact'][index]==item['fact'] if set(item)=={'fact'} else
                    producer.selectors['matches'](ts,index,item)) for item in selectors)
            def select_required(native):
                proof=select_train_full_rows(isolated,native,selection,ntrain=ntrain)
                admitted={i for i in range(len(native['tables']['form'])) if required_table(native['tables'],i)}
                selected={entry for table in admitted for entry in native['_native_reader'].bytable[table]}
                # The canonical selector's entries/mode receipt remains intact.
                return dict(proof,entries=[entry for entry in proof['entries'] if entry in selected])
            replay=isolated.replay_program(record,view.program.sexp(),0,
                candidate=dict(kind='normalized-gold-case',key=digest),retain_all=True,
                full_rows=True,full_rows_selector=select_required,
                assignment_mode='derived',artifact_mode='metadata',checked_program=view.program)
            if replay.get('engine')!='ran':raise Unavailable('normalized case replay incomplete: '+str(replay.get('reason')))
            native=isolated.captures[-1]['native'];ts=native['tables'];tables=[]
            for table in range(len(ts['form'])):
                selector={k:ts[k][table] for k in ('form','point','relation','fact')}
                # Materialized original relations/facts only; BODY is acquired
                # through the native original-scope BODY endpoint below.
                if selector['point']==1 or not required_table(ts,table):continue
                definitions=[d for d in export['definitions']['native_relations'] if
                    producer.selectors['matches'](ts,table,d['native_selector'])]
                schema=native['_native_reader'].schema(table)
                source_name=(definitions[0]['display_name'] if len(definitions)==1 else selector['fact'])
                if not source_name:continue
                # Anonymous RIGID fields have a native declared row path but
                # no AST column name. Bind only those absent names to this
                # exact replay's physical header via the shared validator.
                from program_metadata import bind_native_column_names
                rebound={}
                for definition in definitions:
                    if definition['display_name']==source_name and 'owner' in definition['relation']:
                        witnesses=bind_native_column_names(isolated,selection,definition,schema,
                            artifact=replay['artifact'],table=table)
                        rebound[definition['relation_slot']]=dict(definition,column_witnesses=witnesses)
                metadata_export=export if not rebound else dict(export,definitions=dict(export['definitions'],
                    native_relations=[rebound.get(d['relation_slot'],d) for d in export['definitions']['native_relations']]))
                meta=producer.case_table_metadata(metadata_export,dict(selector=selector,native_schema=schema,source_name=source_name))
                packet=acquire_train_table(isolated,native,table,selection,ntrain=ntrain,
                    fields=[dict(c,field_name=m['display_name']) for c,m in zip(schema,meta['schema'])],
                    projection=list(range(len(schema))),copy_rows=False,
                    source=dict(kind='fresh_normalized',case=case,program_sha256=_sha(view.program.sexp()),
                        observation=replay['artifact'],normalization_sha256=_sha(view.proof)))
                if packet['missing']:raise Unavailable('normalized table missing kept TRAIN contexts')
                tables.append(dict(selector=selector,source_name=source_name,packet=packet,
                    callable_atom=meta['callable_atom'],relation_slots=[d['relation_slot'] for d in definitions]))
                if selector['fact']=='ex_input':
                    tables.append(dict(selector=selector,source_name='input',packet=_input_train(packet),
                        callable_atom=None,relation_slots=[]))
        bundle=dict(key=key,tables=tables,kept=choices,kept_map=matched,kept_report=kept,
            receipt=dict(source_kind='fresh_normalized',row_policy=ROW_POLICY,normalization_report=view.report,
                replay=replay,source_sha256=_sha(record),test_cells=False,test_fit=False,
                held_alignment='canonical full_kept_matches on actual fresh normalized choices',
                enabled_decoder=decoder))
        bundle['content_sha256']=_json_digest(bundle)
        temporary=saved.with_name(saved.name+'.'+str(os.getpid())+'.tmp')
        try:
            with gzip.open(temporary,'wt',compresslevel=1) as stream:
                json.dump(bundle,stream,ensure_ascii=False,allow_nan=False,separators=(',',':'))
            temporary.replace(saved)
        finally:temporary.unlink(missing_ok=True)
    _CACHE.clear();_CACHE[digest]=bundle
    return dict(bundle,view=view,producer=producer,record=record,export=export,original_export=original_export)


def _body(ev,bundle,body_path,full_det,cache):
    from evaluator import canonical
    from evaluator_train import acquire_train_table
    from gold_body import _held_entries
    from tables import full_kept_matches
    from native_correspondence import AtomicPacked
    view=bundle['view'];record=bundle['record'];mapped=view.body(body_path);program=view.program
    reader_projection=None
    export=bundle['export'];sources=[v for v in export['body_views'] if v['body_path']==mapped['body_path']]
    if len(sources)!=1:raise Unavailable('normalized BODY view missing or ambiguous')
    source=sources[0];producer=bundle['producer']
    cache_key=dict(policy=POLICY,row_policy=ROW_POLICY,task=record['task'],case=record['case'],
        source=_sha(record['gold_sexp']),normalized=_sha(program.sexp()),body_path=mapped['body_path'],
        mapper_sha256=_sha(view.proof),kept_sha256=_sha(record['evaluation']['kept_assignments']),
        task_input=_file(Path(ev.cfg['tasks'])/(record['task']+'.json')),runtime_settings=ev.receipt,
        transport='full-physical-body-shared-layouts-v2',enabled_decoder_evidence=bundle['key']['enabled_decoder_evidence'])
    saved=Path(cache)/'normalized-gold/bodies'/(_sha(cache_key)+'.json.gz')
    saved_key=cache_key
    if not saved.exists():
        for prior_sha in _ACQUISITION_PREDECESSORS:
            prior_key=dict(cache_key,runtime_settings=_prior_receipt(ev,prior_sha))
            prior=Path(cache)/'normalized-gold/bodies'/(_sha(prior_key)+'.json.gz')
            if prior.exists():saved=prior;saved_key=prior_key;break
    if saved.exists():
        with gzip.open(saved,'rt') as stream:stored=json.load(stream)
        claimed=stored.pop('content_sha256',None)
        if stored.get('key')!=saved_key or claimed!=_json_digest(stored):
            raise ValueError('normalized BODY cache key/content differs')
        return _body_layout(ev,record,program,stored,full_det)
    task=_read(Path(ev.cfg['tasks'])/(record['task']+'.json'));ntrain=len(task['train'])
    with ev.fresh_session() as isolated:
        native_ev=isolated.task_evaluator(record['task']);kept=json.loads(native_ev.gold_kept(program))
        choices=isolated.validate_gold_observation(program,kept,record['task'])
        schemas=json.loads(program.choice_evidence_json('[]'))
        old=full_kept_matches(ev.legacy,choices,schemas['dets'],record)
        raw,payload=native_ev.gold_body(program,mapped['body_path'],canonical(choices));report=json.loads(raw)
        if (report.get('status')!='complete' or report.get('body_status',{}).get('status')!='complete'
                or report.get('body_coverage',{}).get('complete') is not True):
            raise Unavailable('normalized BODY collection incomplete')
        observed=isolated.validate_gold_observation(program,report,record['task'],schema='arclog-study-gold-body-v1')
        if observed!=choices:raise Unavailable('normalized BODY changed the exact gold observation')
        native=ev.legacy.native(payload);table=report['body_table'];reader=native['_native_reader']
        packed=AtomicPacked(report,reader,program_sexp=program.sexp(),side='gold')
        packed.table(table,role='gold_body_kept')
        packed_receipt=packed.receipt(payload,report_sha256=_sha(report),source_sha256=_sha(record),runtime=isolated.receipt)
        ctx=producer.policy['Document'].__new__(producer.policy['Document'])
        ctx.r=dict(point=mapped['body_path']);ctx.readers={'gold':reader};ctx.gexport=export
        ctx.owner=source['owner_path'];ctx.body=source;ctx.values=SimpleNamespace(f={'column_names':{}})
        fields=packed.body_schema(view.correspondences['normalized'],table,
            body_path=mapped['body_path'])
        for field in fields:
            ctx.values.f['column_names'][field['source_label']]=field['display_name']
        raw_fields=[dict(c,source_body_column=c['index'],callable_row_path=None) for c in fields]
        projected_error=None
        try:
            if source['kind']=='Det':
                if str(CODE_ROOT/'ast/run') not in sys.path:sys.path.insert(0,str(CODE_ROOT/'ast/run'))
                from mech3.det_receipt import side_receipt
                from mech3.reader_projection import reader_header_union
                from judge3.det_metadata import project_header_union
                raw_binding=dict(kind='Det',body_path=mapped['body_path'],owner_path=source['owner_path'],
                    source_body_schema=deepcopy(fields),projected_schema=[dict(c,source_body_column=c['index']) for c in fields])
                readers=side_receipt(export,raw_binding,mapped['body_path'])
                columns=reader_header_union(list(readers['readers'].values()))
                fields=project_header_union(fields,columns,body_path=mapped['body_path'],column_text=producer.policy['column_text'])
                reader_projection=dict(policy='existing projected DET reader/header union',
                    scope='normalized GOLD feature snapshot; no judge admission',reader_receipt=readers,columns=columns)
            else:fields,_,_=ctx.target_projection(reader,fields,{},body_side='gold')
        except (ValueError,KeyError,IndexError,TypeError) as error:
            if not full_det:raise
            fields=None;projected_error=dict(error_type=type(error).__name__,reason=str(error))
        selection=dict(task=record['task'],case=record['case'],gold_sexp=program.sexp(),context_schema='normalized-gold-selection-v1',evaluation=dict(kept_assignments=record['evaluation']['kept_assignments']))
        packet=acquire_train_table(isolated,native,table,selection,ntrain=ntrain,
            fields=raw_fields,projection=list(range(len(raw_fields))),
            held_entries=_held_entries(native,table,report,old),copy_rows=False,
            source=dict(kind='fresh_normalized',normalization_sha256=_sha(view.proof),
                normalized_program_sha256=_sha(program.sexp()),report=report,packed_acquisition=packed_receipt,
                reader_projection=reader_projection,test_fit=False))
        if packet['missing']:raise Unavailable('normalized BODY lacks required original kept TRAIN contexts')
    stored=dict(key=cache_key,packet=packet,projected_fields=fields,projected_error=projected_error,
        projected_indices=None if fields is None else [c['source_body_column'] for c in fields])
    stored['content_sha256']=_json_digest(stored)
    saved.parent.mkdir(parents=True,exist_ok=True)
    temporary=saved.with_name(saved.name+'.'+str(os.getpid())+'.tmp')
    try:
        with gzip.open(temporary,'wt',compresslevel=1) as stream:
            json.dump(stored,stream,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        temporary.replace(saved)
    finally:temporary.unlink(missing_ok=True)
    return _body_layout(ev,record,program,stored,full_det)


def _body_layout(ev,record,program,stored,full_det):
    packet=stored['packet']
    if packet['missing']:raise ValueError('normalized BODY cache contains incomplete contexts')
    if full_det:return packet
    if stored.get('projected_fields') is None:
        raise Unavailable('normalized projected layout unavailable: '+str(stored.get('projected_error')))
    from evaluator_train import _projector
    from program_metadata import typed_fields
    selection=dict(task=record['task'],gold_sexp=program.sexp())
    fields=typed_fields(ev,selection,stored['projected_fields'])
    projection=stored['projected_indices'];entries=[];shared={}
    for entry in packet['entries']:
        key=id(entry['rows']);cached=shared.get(key)
        if cached is None or cached[0] is not entry['rows']:
            # Acquired TRAIN packets store numeric axes, while the canonical
            # renderer projector expects an example name and choice. Adapt
            # its input only; retain the packet's exact axes on the output.
            rows=_projector()(dict(entries=[dict(entry,
                example='train'+str(entry['example_index']+1),
                choice=entry['assignment'])]),projection)[0]['rows']
            shared[key]=(entry['rows'],rows)
        else:rows=cached[1]
        entries.append(dict(entry,rows=rows))
    return dict(packet,fields=fields,entries=entries,projection=projection,
        receipt=dict(packet['receipt'],layout_projection=dict(indices=projection,fields_sha256=_sha(fields),
            source='same validated full physical normalized BODY packet; canonical projector')))


def _receipt_path(private,point_id):
    return Path(private)/'normalized-gold/points'/(point_id+'.json')


def _capabilities(point):
    return dict(normalized_gold=point.get('gold_view')==POLICY,
        det_layout=point.get('det_layout'),row_policy=point.get('row_policy',ROW_POLICY))


def _overlay(operation,files):
    lookup=operation.get('overlay_publication_lookup',{});path=Path(lookup['path']).resolve()
    actual=_file(path)['sha256'] if path.is_file() else None
    expected=lookup.get('sha256') if lookup.get('present_at_snapshot') else None
    if actual!=expected:raise Unavailable('active DET overlay changed since frozen source snapshot')
    rows=[r for r in files['overlays.jsonl'] if r['point_id']==operation['point_id']]
    if not expected:
        if rows:raise ValueError('unpublished overlay unexpectedly bound by mapper')
        return None
    if len(rows)!=1:raise ValueError('published fullBODY overlay lacks unique frozen operation')
    row=rows[0];source=row['source_generation']
    if (source['publication_manifest']!=str(path) or source['publication_manifest_sha256']!=actual
            or row['source_layout_policy']!='det-full-body-train-v1'):
        raise ValueError('overlay publication/layout binding differs')
    manifest=Path(source['artifact_manifest']).resolve()
    if _file(manifest)['sha256']!=source['artifact_manifest_sha256']:raise ValueError('overlay artifact manifest SHA differs')
    generation=(DATA_ROOT/source['generation']).resolve()
    if not generation.is_relative_to(DATA_ROOT.resolve()):raise ValueError('overlay generation escapes DATA_ROOT')
    for relative,wanted in _read(manifest)['files'].items():
        file=(generation/relative).resolve()
        if not file.is_relative_to(generation) or _file(file)!=wanted:raise ValueError('overlay source artifact bytes differ')
    point_file=Path(row['point_json']).resolve()
    if _file(point_file)['sha256']!=row['point_json_sha256']:raise ValueError('overlay point JSON SHA differs')
    point=_read(point_file)
    if point.get('det_layout')!='det-full-body-train-v1':raise ValueError('overlay point is not fullBODY')
    pairs={r['pair_id']:r for r in row['published_pairs']}
    if len(pairs)!=len(row['published_pairs']) or not set(pairs)<=set(operation['published_pairs']):
        raise ValueError('overlay pair coverage differs from base point operation')
    for pair in pairs.values():
        if pair['X_contract']!='det-full-body-train-v1' or _file(pair['pair_json'])['sha256']!=pair['pair_json_sha256']:
            raise ValueError('overlay pair source/layout SHA differs')
    return dict(row=row,point=point,pairs=pairs,source_generation=source)


def _recover_points(root,receipt):
    pending=receipt.get('pending_points',[])
    if not pending and receipt.get('pending_point'):
        pending=[dict(stage=receipt['pending_point'],point=str(root/'points'/receipt['point_id']))]
    moves=[]
    for item in pending:
        point=Path(item['point']).resolve();stage=Path(item['stage']).resolve()
        if not point.is_relative_to(root) or stage!=point.with_name(point.name+'.building'):
            raise ValueError('normalized committed stage escapes declared point')
        if not point.exists():
            if not stage.is_dir():raise ValueError('normalized committed stage missing')
            moves.append((stage,point))
    for relative,wanted in receipt['public_files'].items():
        file=(root/relative).resolve()
        if not file.is_relative_to(root):raise ValueError('normalized public file escapes generation')
        for stage,point in moves:
            if file.is_relative_to(point):file=stage/file.relative_to(point);break
        if _file(file)!=wanted:raise ValueError('normalized recovery source SHA differs')
    for stage,point in moves:stage.rename(point)


def export_normalized_gold_point(ev,manifest_ref,operation,generation_dir,cache,private):
    from judge3.dataset_format import table_packet,table_summary
    manifest,files=_manifest(manifest_ref)
    for folder in (cache,private):
        if not Path(folder).resolve().is_relative_to(DATA_ROOT.resolve()):raise ValueError('normalized cache/private escapes DATA_ROOT')
    matches=[row for row in files['points.jsonl'] if row['point_id']==operation['point_id']]
    if len(matches)!=1 or matches[0]!=operation:raise ValueError('normalized operation differs from frozen manifest')
    root=Path(generation_dir).resolve()
    if not root.is_relative_to(DATA_ROOT.resolve()):raise ValueError('normalized generation escapes DATA_ROOT')
    root.mkdir(parents=True,exist_ok=True)
    old=Path(operation['path']).resolve();point_id=operation['point_id']
    overlay=_overlay(operation,files)
    for artifact in operation['artifacts']:
        if _file(artifact['path'])['sha256']!=artifact['sha256']:
            raise ValueError('normalized input generation artifact changed: '+artifact['path'])
    old_point=_read(old/'point.json');point_dir=root/'points'/point_id
    # A prior completed generation is recovered, never replayed.
    receipt_path=_receipt_path(private,point_id)
    if receipt_path.exists():
        ref=dict(path=str(receipt_path.resolve()),sha256=_file(receipt_path)['sha256'])
        _recover_points(root,_read(receipt_path))
        validate_normalized_gold_export(root,ref,private=private,point_id=point_id)
        return dict(point_id=point_id,normalized_gold_receipt=ref,reused=True)
    if point_dir.exists():raise Unavailable('incomplete normalized point stage retained; explicit repair required')
    point_dir.parent.mkdir(parents=True,exist_ok=True);stage=point_dir.with_name(point_dir.name+'.building')
    if stage.exists():shutil.rmtree(stage)
    shutil.copytree(old,stage)
    newpoint=deepcopy(old_point);acquisitions={};changed=[];case_evidence={}
    own=_case(ev,files,operation['task'],operation['case'],cache)
    names=own['producer'].policy['Names'](own['export'])
    (stage/old_point['programs']['gold']).write_text(names.text(own['view'].program.sexp())+'\n')
    artifacts={a.get('table_id'):a for a in operation['artifacts'] if a.get('table_id')}
    summaries={t['id']:deepcopy(t) for t in old_point['tables']}
    full_det=old_point.get('det_layout')=='det-full-body-train-v1'
    for table_id,artifact in artifacts.items():
        old_summary=summaries[table_id];case=artifact['case'];bundle=_case(ev,files,operation['task'],case,cache)
        if case not in case_evidence:
            evidence_path=Path(private)/'normalized-gold/evidence'/(_sha(bundle['key'])+'.json')
            _write(evidence_path,dict(normalization=bundle['view'].report,acquisition=bundle['receipt'],
                original_source=bundle['record'],normalized_export=bundle['export']))
            case_evidence[case]=dict(path=str(evidence_path.resolve()),**_file(evidence_path))
        if table_id=='G':
            packet=_body(ev,bundle,operation['original_point'],full_det,cache)
            atom=None;selector=dict(body_path=operation['original_point'])
        else:
            # Resolve an original canonical published name to its native source
            # declaration, then use ONLY the native normalization relation map.
            definitions=[d for d in bundle['original_export']['definitions']['native_relations']
                         if d['display_name']==artifact['source_name']]
            if artifact['source_name'] in ('input','ex_input','ex_output'):
                candidates=[t for t in bundle['tables'] if t['source_name']==artifact['source_name']]
            else:
                if len(definitions)!=1:raise Unavailable('published source relation identity ambiguous: '+artifact['source_name'])
                mapped=bundle['view'].relation(definitions[0]['relation_slot'])
                candidates=[t for t in bundle['tables'] if bundle['producer'].selectors['matches'](
                    {k:[v] for k,v in t['selector'].items()},0,mapped['native_selector'])]
            if len(candidates)!=1:raise Unavailable('normalized original relation table missing or ambiguous')
            selected=candidates[0];packet=selected['packet'];atom=selected['callable_atom'];selector=selected['selector']
        public=table_packet(packet,table_id=table_id,source_name=artifact['source_name'],case=case,
            roles=old_summary['roles'],callable_atom=atom,copy_rows=False,sort_rows=True)
        for key in ('side','body_path','body_kind'):
            if key in old_summary:
                public[key]=(bundle['view'].body(old_summary[key])['body_path'] if key=='body_path' else old_summary[key])
        relative=Path(artifact['path']).relative_to(old)
        _write(stage/relative,public);summaries[table_id]=table_summary(public,str(relative))
        acquisitions[table_id]=dict(source_kind='fresh_normalized_or_matching_cache',case=case,selector=selector,
            normalized_program_sha256=_sha(bundle['view'].program.sexp()),mapper_sha256=_sha(bundle['view'].proof),
            receipt=packet['receipt'],required=packet['required'],missing=packet['missing'],schema_sha256=_sha(packet['fields']))
        changed.append(str(relative))
    newpoint['tables']=[summaries[t['id']] for t in old_point['tables']]
    newpoint.update(gold_view=POLICY,row_policy=ROW_POLICY,
        source_generation=dict(manifest_sha256=manifest_ref['sha256'],point_json_sha256=_file(old/'point.json')['sha256'],
            det_layout=old_point.get('det_layout')))
    # Prefix metadata must come from the NORMALIZED handle; original mutant X
    # and its candidate-only metadata remain original and independent.
    from judge3.feature_payload import point_payload
    prefix=json.loads(ev.arclog.study_feature_metadata_json(own['view'].program,own['view'].body(operation['original_point'])['body_path']))
    newpoint.update(point_payload(prefix));_write(stage/'point.json',newpoint)
    point_stages=[(stage,point_dir)]
    layout_variants=dict(base=dict(layout=old_point.get('det_layout','projected-native-point'),
        point_json=str((point_dir/'point.json').relative_to(root)),
        source_generation=dict(point_path=str(old),point_json=_file(old/'point.json'))))
    full_point_dir=None
    if overlay is not None:
        full_point_dir=root/'layouts/det-full-body-train-v1/points'/point_id
        full_stage=full_point_dir.with_name(full_point_dir.name+'.building')
        if full_point_dir.exists():raise ValueError('uncommitted fullBODY point retained without completion receipt')
        full_stage.parent.mkdir(parents=True,exist_ok=True)
        if full_stage.exists():shutil.rmtree(full_stage)
        shutil.copytree(stage,full_stage)
        full_point=deepcopy(newpoint);full_point['det_layout']='det-full-body-train-v1'
        full_packet=_body(ev,own,operation['original_point'],True,cache)
        g=next(t for t in newpoint['tables'] if t['id']=='G')
        full_table=table_packet(full_packet,table_id='G',source_name=g['source_name'],case=operation['case'],
            roles=g['roles'],callable_atom=None,copy_rows=False,sort_rows=True)
        _write(full_stage/g['path'],full_table)
        full_point['tables']=[table_summary(full_table,g['path']) if t['id']=='G' else t for t in full_point['tables']]
        full_point['source_generation']=dict(overlay['source_generation'],manifest_sha256=manifest_ref['sha256'])
        _write(full_stage/'point.json',full_point)
        point_stages.append((full_stage,full_point_dir))
        layout_variants['det-full-body-train-v1']=dict(layout='det-full-body-train-v1',
            point_json=str((full_point_dir/'point.json').relative_to(root)),source_generation=overlay['source_generation'])
        acquisitions['G:det-full-body-train-v1']=dict(receipt=full_packet['receipt'],required=full_packet['required'],
            missing=full_packet['missing'],schema_sha256=_sha(full_packet['fields']))
    per_pair_source_generations={}
    pair_rows={p['pair_id']:p for p in files['pairs.jsonl'] if p['point_id']==point_id}
    pair_dirs=[]
    for pair_id in operation['published_pairs']:
        row=pair_rows[pair_id];overlay_pair=None if overlay is None else overlay['pairs'].get(pair_id)
        if overlay_pair is None:
            origin=Path(row['pair_path']);target_point=point_dir;layout='base';wanted=row['pair_json_sha256']
        else:
            origin=Path(overlay_pair['pair_json']).parent;target_point=full_point_dir;layout='det-full-body-train-v1';wanted=overlay_pair['pair_json_sha256']
            if overlay_pair['source_binding']['source_sha256']!=row['source_sha256']:
                raise ValueError('fullBODY/base pair original source identities differ')
        destination=root/'pairs'/pair_id
        if _file(origin/'pair.json')['sha256']!=wanted:raise ValueError('normalized pair input changed')
        per_pair_source_generations[pair_id]=dict(layout=layout,source_pair=dict(path=str(origin/'pair.json'),sha256=wanted),
            point_json=str((target_point/'point.json').relative_to(root)),source_generation=layout_variants[layout]['source_generation'])
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(origin,destination,dirs_exist_ok=True)
        public=_read(destination/'pair.json');public['point']=os.path.relpath(target_point,destination)
        if row.get('gold_change_text_needs_refresh'):
            body=own['view'].body(row['original_point']);nodes={tuple(n['path']):n for n in own['export']['nodes']}
            public['change']['gold']=names.text(nodes[tuple(body['body_path'])]['sexp'])
        if row.get('prefix_metadata_needs_refresh'):
            public['normalized_gold_prefix_v1']=dict(point_payload(prefix),
                policy=POLICY,program_sha256=_sha(own['view'].program.sexp()),
                mapper_sha256=_sha(own['view'].proof),scope='normalized_gold_prefix_only')
            for key in ('types_frames_v1','canonical_clauses_v1'):
                public[key]=dict(status='unsupported',scope='original_candidate_and_normalized_prefix',
                    missing=[dict(reason='Cross-program candidate/prefix frame composition is not certified')],
                    normalized_prefix_reference='normalized_gold_prefix_v1')
        public['gold_view']=POLICY;_write(destination/'pair.json',public);pair_dirs.append(destination)
    outputs={}
    for directory in [*(item[0] for item in point_stages),*pair_dirs]:
        for path in directory.rglob('*'):
            if path.is_file():
                public_path=path
                for staged,final in point_stages:
                    if path.is_relative_to(staged):public_path=final/path.relative_to(staged);break
                outputs[str(public_path.relative_to(root))]=_file(path)
    receipt=dict(schema='study-normalized-gold-export-v1',policy=POLICY,row_policy=ROW_POLICY,
        complete=True,test_cells=False,test_fit=False,feature_safe_prefix_rows=False,
        point_id=point_id,generation_dir=str(root),pending_points=[dict(stage=str(a),point=str(b)) for a,b in point_stages],manifest=manifest_ref,operation_sha256=_sha(operation),
        input_generation=dict(point_path=str(old),point_json=_file(old/'point.json'),capabilities=_capabilities(old_point)),
        output_capabilities=dict(_capabilities(newpoint),layouts=list(layout_variants)),
        layout_variants=layout_variants,per_pair_source_generations=per_pair_source_generations,
        original_pair_identity_preserved=True,
        normalized_provenance=own['view'].proof,acquisitions=acquisitions,case_evidence=case_evidence,
        enabled_decoder_evidence={k:v for k,v in files['_enabled_decoder'].items() if k!='rows'},
        unchanged_authority='original snapshot files copied byte-for-byte except explicit descriptor edits',
        public_files=outputs,runtime=ev.receipt,
        implementation={str((CODE_ROOT/name).resolve()):_file(CODE_ROOT/name)['sha256'] for name in
            ('normalized_gold.py','native_correspondence.py','evaluator_train.py','judgetool/gold_body.py','judgetool/tables.py')})
    _write(receipt_path,receipt)
    for staged,final in point_stages:staged.rename(final)
    return dict(point_id=point_id,normalized_gold_receipt=dict(path=str(receipt_path.resolve()),sha256=_file(receipt_path)['sha256']))


def validate_normalized_gold_export(generation_dir,receipt_ref=None,*,private=None,point_id=None):
    root=Path(generation_dir).resolve()
    if receipt_ref is None:
        if private is None or point_id is None:raise ValueError('private/point_id required for normalized receipt recovery')
        path=_receipt_path(private,point_id);receipt_ref=dict(path=str(path.resolve()),sha256=_file(path)['sha256'])
    path=Path(receipt_ref['path']).resolve()
    if private is not None and not path.is_relative_to(Path(private).resolve()):raise ValueError('normalized receipt escapes private root')
    if _file(path)['sha256']!=receipt_ref['sha256']:raise ValueError('normalized receipt SHA differs')
    receipt=_read(path)
    if (receipt.get('schema')!='study-normalized-gold-export-v1' or receipt.get('policy')!=POLICY
            or receipt.get('complete') is not True or receipt.get('generation_dir')!=str(root)
            or receipt.get('test_cells') is not False or receipt.get('test_fit') is not False):
        raise ValueError('normalized receipt completeness/policy differs')
    for name,wanted in receipt['implementation'].items():
        if _file(name)['sha256']!=wanted:raise ValueError('normalized provider source SHA differs')
    for evidence in receipt['case_evidence'].values():
        file=Path(evidence['path']).resolve()
        if private is not None and not file.is_relative_to(Path(private).resolve()):raise ValueError('normalized case evidence escapes private root')
        if _file(file)!={k:evidence[k] for k in ('sha256','bytes')}:raise ValueError('normalized native case evidence SHA differs')
    for relative,wanted in receipt['public_files'].items():
        file=(root/relative).resolve()
        if not file.is_relative_to(root) or _file(file)!=wanted:raise ValueError('normalized published artifact SHA differs')
    return dict(schema='study-normalized-gold-validated-v1',complete=True,point_id=receipt['point_id'],
        policy=POLICY,row_policy=receipt['row_policy'],capabilities=receipt['output_capabilities'],
        manifest=receipt['manifest'],normalized_gold_receipt=receipt_ref,public_files=receipt['public_files'],
        layout_variants=receipt.get('layout_variants',{}),per_pair_source_generations=receipt.get('per_pair_source_generations',{}),
        test_cells=False,test_fit=False,feature_safe_prefix_rows=False)
