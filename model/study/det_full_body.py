"""Opt-in full physical DET BODY transport for TRAIN features only.

Reader-named labels never select fields on this path. Public JSON contains no
TEST cells; inherited available snapshots and gold source authority are explicit.
"""
from copy import deepcopy
from pathlib import Path
import gzip
import hashlib
import json
import os
import shutil
import sys
import time

from study_paths import CODE_ROOT, DATA_ROOT

LAYOUT='det-full-body-train-v1'
POLICY=dict(layout=LAYOUT,physical_body=True,reader_projection=False,
    example='native TRAIN-filtered cells plus separate TRAIN entry axis',
    gold_reuse=['stored_raw','persisted_full','fresh_original_scope'])


def _sha(value):
    from evaluator import sha
    return sha(value)


def _file(path):
    path=Path(path);digest=hashlib.sha256();size=0
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk);size+=len(chunk)
    return dict(sha256=digest.hexdigest(),bytes=size)


def _read(path):
    path=Path(path)
    if path.stat().st_size>32*1024*1024:raise ValueError('full DET metadata exceeds32MiB')
    return json.loads(path.read_text())


def _write(path,value):
    from judge3.dataset_format import write_json
    write_json(Path(path),value,compact=True)


def full_body_snapshot(ev,record,ref,base):
    """Reuse the exact two immutable source payloads within one pair only."""
    from tables import TargetStore
    key=(str(Path(base).resolve()),record['task'],record['case'],tuple(record['point']),
         _sha(record['native']))
    cached=getattr(ev,'_det_full_body_native',None)
    if cached is None or cached[0]!=key:
        cached=(key,TargetStore(ev.legacy,CODE_ROOT));ev._det_full_body_native=cached
    return cached[1].snapshot(ref,base)


def prepare_det_full_body_metadata(ev,record,*,native_base,case_inventory=None):
    if str(CODE_ROOT/'ast/run') not in sys.path:sys.path.insert(0,str(CODE_ROOT/'ast/run'))
    from tables import TargetStore
    from judge3.nonrender_metadata import MetadataProducer
    producer=MetadataProducer(engine=ev.arclog,settings=ev.settings,
        read_native=lambda ref,base:full_body_snapshot(ev,record,ref,base)['_native_reader'],
        corpus=Path(native_base).resolve().parent,case_inventory=case_inventory)
    if case_inventory is None:
        from mech5.metadata import bind_inventory_copy
        key=(producer.corpus,record['task'])
        cached=getattr(ev,'_det_inventory_cache',None)
        if cached is None or cached[0]!=key:
            cached=(key,{});ev._det_inventory_cache=cached
        producer.case_cache=cached[1];bind_inventory_copy(producer)
    return producer.produce(record,native_base=native_base,det_full_body=True)


def _binding(record,adapter,side):
    from tables import Incomplete
    binding=adapter['bindings'][side];proof=adapter.get('det_full_body',{})
    if (proof.get('schema')!='evaluator-det-full-body-source-v1'
            or proof.get('source_sha256')!=_sha(record)
            or proof.get('binding_sha256',{}).get(side)!=_sha(binding)
            or adapter.get('scope')!='TRAIN_features_only_noncallable'
            or binding.get('kind')!='Det' or binding.get('callable') is not False
            or binding.get('callable_template') is not None
            or binding.get('native_ref')!=record['native'][side]
            or binding.get('body_path')!=record['point']):
        raise Incomplete('full DET binding/source differs')
    fields=binding['projected_schema'];schema=binding['source_body_schema']
    if [f['source_body_column'] for f in fields]!=list(range(len(schema))):
        raise Incomplete('full DET binding is not the complete physical BODY layout')
    return binding


def _gold_key(ev,record,adapter,binding):
    task=Path(adapter['source']['task_path'])
    return dict(schema=LAYOUT,policy=POLICY,task=record['task'],case=record['case'],
        body_path=record['point'],gold_program_sha256=_sha(record['gold_sexp']),
        task_input_sha256=_file(task)['sha256'],kept_sha256=_sha(record['evaluation']['kept_assignments']),
        physical_layout_sha256=_sha(binding['source_body_schema']),gold_native=record['native']['gold'],
        producer={k:record[k] for k in ('engine_commit','wheel_sha256','native_binary_sha256')},
        runtime={k:deepcopy(ev.receipt[k]) for k in ('runtime','config_sha256',
            'table_work_cap','rule_tests','session_bytes','reference_sha256')},
        implementation={name:_file(CODE_ROOT/name)['sha256'] for name in (
            'det_full_body.py','evaluator_train.py','native_correspondence.py',
            'judgetool/tables.py','judgetool/gold_body.py','judgetool/program_metadata.py',
            'judge2/render2/body.py','judge2/render2/headers.py','judge3/render_pair.py')})


def _packet_complete(packet):
    if packet.get('missing') or not packet.get('required'):
        raise ValueError('full DET packet lacks required kept TRAIN axes')
    required={tuple(k) for k in packet['required']}
    present={(e['assignment'],e['example_kind'],e['example_index']) for e in packet['entries']}
    if present!=required or any(e['example_kind'] not in (1,2) for e in packet['entries']):
        raise ValueError('full DET packet axes differ or contain entries that are not TRAIN or TEST')
    return packet


def acquire_det_full_body_train_point(ev,record,adapter,ntrain,ntest,side='mutant',*,
        copy_rows=True,include_projected_flows=False,cache=None):
    from evaluator_train import acquire_train_table,_acquire_original_gold_train
    from tables import TargetStore
    if side not in ('mutant','gold'):raise ValueError('invalid full DET side')
    binding=_binding(record,adapter,side)
    def stored():
        native=full_body_snapshot(ev,record,record['native'][side],Path(adapter['source']['native_base']))
        table=binding['native_table_index']
        for name,value in binding['native_selector'].items():
            if name in native['tables'] and native['tables'][name][table]!=value:
                raise ValueError('full DET stored native selector differs')
        return _packet_complete(acquire_train_table(ev,native,table,record,ntrain=ntrain,ntest=ntest,test_rows=True,
            fields=binding['projected_schema'],projection=[f['source_body_column'] for f in binding['projected_schema']],
            source=dict(side=side,layout=LAYOUT,native_ref=record['native'][side],
                selector=binding['native_selector'],gold_source_kind='stored_raw' if side=='gold' else None,
                authority='authenticated original physical BODY snapshot',judge_admission=False),
            copy_rows=copy_rows,include_projected_flows=include_projected_flows))
    if side=='mutant':return stored()
    key=_gold_key(ev,record,adapter,binding);cache_root=Path(cache or DATA_ROOT/'judgetool/det-full-body-train-cache')
    cache_root.mkdir(parents=True,exist_ok=True);path=cache_root/(_sha(key)+'.json.gz');ledger=[]
    try:
        packet=stored();kind='stored_raw'
    except (ev.arclog.Refusal,ValueError,OSError) as error:
        ledger.append(dict(source='stored_raw',status='unavailable',reason=str(error)))
        if path.exists():
            with gzip.open(path,'rt') as stream:envelope=json.load(stream)
            if envelope.get('key')!=key or envelope.get('packet_sha256')!=_json_digest(envelope['packet']):
                raise ValueError('persisted full DET TRAIN cache authentication differs')
            packet=_packet_complete(envelope['packet']);kind='persisted_full'
            packet=dict(packet,receipt=dict(source_sha256=_sha(record),
                kept_context_sha256=_sha(record['evaluation']['kept_assignments']),test_cells=packet['receipt']['test_cells'],
                source=dict(side='gold',layout=LAYOUT,gold_source_kind=kind),
                cached_acquisition=packet['receipt'],cache=dict(path=str(path),**_file(path))))
        else:
            packet=_packet_complete(_acquire_original_gold_train(ev,record,binding,ntrain,ntest=ntest,test_rows=True,
                source=dict(layout=LAYOUT,gold_source_kind='fresh_original_scope',judge_admission=False),copy_rows=copy_rows))
            kind='fresh_original_scope'
    if kind!='persisted_full' and not path.exists():
        temporary=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
        try:
            with gzip.open(temporary,'wt',compresslevel=1) as stream:
                json.dump(dict(key=key,packet_sha256=_json_digest(packet),packet=packet),stream,
                    ensure_ascii=False,allow_nan=False,separators=(',',':'))
                stream.write('\n')
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return dict(packet,det_full_body=dict(layout=LAYOUT,gold_source_kind=kind,key_sha256=_sha(key),
        acquisition=packet['receipt'],fallbacks=ledger,cache=dict(path=str(path),**_file(path))))


def _json_digest(value):
    digest=hashlib.sha256()
    encoder=json.JSONEncoder(ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    for chunk in encoder.iterencode(value):digest.update(chunk.encode())
    return digest.hexdigest()


def packet_summary(packet):
    _packet_complete(packet)
    return dict(fields=deepcopy(packet['fields']),source_schema=deepcopy(packet['source_schema']),
        fields_sha256=_sha(packet['fields']),schema_sha256=_sha(packet['source_schema']),
        projection=list(packet['projection']),required=deepcopy(packet['required']),missing=[],
        present=[list(k) for k in sorted({(e['assignment'],e['example_kind'],e['example_index']) for e in packet['entries']})],
        entries=[dict(assignment=e['assignment'],example_kind=e['example_kind'],example_index=e['example_index'],
            model=e['model'],row_count=len(e['rows'])) for e in packet['entries']],
        acquisition=deepcopy(packet['receipt']),gold=deepcopy(packet.get('det_full_body')),
        namespace=deepcopy(packet.get('current_native_names_acquisition')))


def inherit_available(old,stage,record,task_path,producer):
    """Inherit approved available snapshot bytes/IDs; never reuse old G as full G."""
    old=Path(old).resolve();stage=Path(stage)
    if not old.is_relative_to(DATA_ROOT.resolve()):raise ValueError('inherited point must stay under data root')
    point=_read(old/'point.json')
    if (point.get('kind')!='features-point' or point.get('task')!=record['task']
            or point.get('case')!=record['case'] or point.get('point')!=record['point']):
        raise ValueError('inherited available point identity differs')
    task=_read(task_path)
    if _read(old/point['train'])!=task['train']:
        raise ValueError('inherited available TRAIN inputs differ')
    export=producer._export(record['gold_sexp'],record)
    names=producer.policy['Names'](export)
    if (old/point['programs']['gold']).read_text()!=names.text(record['gold_sexp'])+'\n':
        raise ValueError('inherited available gold presentation differs')
    tables=[deepcopy(t) for t in point['tables'] if t['id']!='G']
    if any('available' not in t['roles'] or not t.get('complete') or t.get('missing') for t in tables):
        raise ValueError('inherited point includes incomplete or nonavailable table')
    if task['test'] and any(t.get('test_rows') is not False and not any('test' in e for e in t['entry_counts']) for t in tables):
        raise ValueError('inherited available table lacks TEST entries')
    paths={t['path'] for t in tables}|{point['train'],point['libraries'],point['programs']['gold']}
    refs={}
    for relative in sorted(paths):
        source=(old/relative).resolve()
        if not source.is_relative_to(old):raise ValueError('inherited point file escapes origin')
        target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True)
        before=source.stat();shutil.copyfile(source,target);after=source.stat()
        if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('inherited available file changed during snapshot')
        refs[relative]=dict(origin=str(source),**_file(target))
    required={'input','ex_input','ex_output'}
    facts={t['source_name'] for t in tables}|{t['id'] for t in tables}
    if not required.issubset(facts):raise ValueError('inherited point lacks required available facts')
    return dict(schema='det-full-body-inherited-available-v1',origin=str(old),
        point_file=dict(path=str(old/'point.json'),**_file(old/'point.json')),
        tables=tables,files=refs,authority='existing validated available snapshot; IDs/bytes unchanged',
        new_native_operations=0)


def _test_cells(tables):
    """True when any of the table summaries holds TEST cells."""
    return any(table['acquisition']['test_cells'] is True for table in tables)


def _implementation():
    from evaluator_train import det_dependency_receipt
    result=det_dependency_receipt()
    for name in ('det_full_body.py','judge3/export_by_pair_id.py','judge3/export_dataset.py',
                 'judge3/dataset_format.py','judge3/nonrender_metadata.py'):
        path=(CODE_ROOT/name).resolve();result[str(path)]=_file(path)['sha256']
    return result


def locate_det_full_body_receipt(private,pair_id):
    path=Path(private).resolve()/'det-full-body/pairs'/(pair_id+'.json')
    return dict(path=str(path),sha256=_file(path)['sha256'])


def _point_receipt_path(private,record):
    key=_sha([record['task'],record['case'],record['point'],LAYOUT])
    return Path(private).resolve()/'det-full-body/points'/(key+'.json')


_POINT_FILES={}


def _point_signature(base,files):
    signature=[]
    for relative in sorted(files):
        path=(base/relative).resolve()
        if not path.is_relative_to(base):raise ValueError('full DET point file escapes point directory')
        stat=path.stat()
        signature.append((relative,stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns))
    return tuple(signature)


def _check_point_files(base,files,*,already_hashed=False):
    """Lossless per-process reuse for the driver's immutable point generation."""
    key=(str(base),_sha(files));signature=_point_signature(base,files)
    if not already_hashed and _POINT_FILES.get(key)!=signature:
        for relative,expected in files.items():
            if _file(base/relative)!=expected:raise ValueError('full DET shared point bytes differ')
    _POINT_FILES[key]=signature
    while len(_POINT_FILES)>4:_POINT_FILES.pop(next(iter(_POINT_FILES)))


def write_export_receipts(ev,pair_id,record,target,adapter,x,g,pair_stage,pair_dir,point_dir,private,inherited=None,namespace_receipt=None):
    """Attest already validated packets and synchronous writes, never reload cells."""
    point_dir=Path(point_dir).resolve()
    implementation=_implementation();point_path=_point_receipt_path(private,record)
    source=dict(task=record['task'],case=record['case'],point=record['point'],
        gold_program_sha256=_sha(record['gold_sexp']),
        task_input_sha256=_file(adapter['source']['task_path'])['sha256'],
        full_kept_sha256=_sha(record['evaluation']['kept_assignments']))
    common=dict(layout=LAYOUT,complete=True,test_fit=False,judge_admission=False,
        policy=POLICY,runtime=deepcopy(ev.receipt),implementation=implementation)
    if g is not None:
        point=_read(point_dir/'point.json');public_files={}
        paths={item['path'] for item in point['tables']}|{'point.json',point['train'],point['libraries'],point['programs']['gold']}
        for relative in paths:public_files[relative]=_file(point_dir/relative)
        gold=g.get('gold')
        if not gold or gold['gold_source_kind'] not in POLICY['gold_reuse']:
            raise ValueError('full DET gold source authority missing')
        point_receipt=dict(common,schema='study-det-full-body-point-v1',source=source,test_cells=_test_cells([g]),
            point_dir=str(point_dir),tables=dict(G=g),gold_source_kind=gold['gold_source_kind'],
            inherited_available=inherited,public_files=public_files)
        _write(point_path,point_receipt)
        _check_point_files(point_dir,public_files,already_hashed=True)
    else:
        point_receipt=_read(point_path)
        if point_receipt['source']!=source or point_receipt['layout']!=LAYOUT:
            raise ValueError('full DET shared point source/policy differs')
        _check_point_files(point_dir,point_receipt['public_files'])
    point_ref=dict(path=str(point_path),sha256=_file(point_path)['sha256'])
    if x is None:return dict(det_full_body_point_receipt=point_ref)
    pair_stage=Path(pair_stage);pair_dir=Path(pair_dir).resolve()
    if x['required']!=point_receipt['tables']['G']['required']:
        raise ValueError('full DET X/G required own kept TRAIN axes differ')
    point_ref=dict(path=str(point_path),sha256=_file(point_path)['sha256'])
    pair=_read(pair_stage/'pair.json')
    files={relative:_file(pair_stage/relative) for relative in
           {'pair.json','tables/X.json',pair['programs']['mutant']}}
    receipt=dict(common,schema='study-det-full-body-export-v1',pair_id=pair_id,test_cells=_test_cells([x]),
        source=dict(source,source_sha256=_sha(record),source_original_sha256=target.get('source_original_sha256'),
            native=deepcopy(record['native']),producer={k:record[k] for k in ('engine_commit','wheel_sha256','native_binary_sha256')},
            mutant_program_sha256=_sha(record['mutant_sexp']),identity_sha256=_sha(record['identity'])),
        pair_dir=str(pair_dir),point_dir=str(point_dir),point_receipt=point_ref,
        namespace_receipt=namespace_receipt,
        tables=dict(X=x),public_files=files,
        authority='same complete physical BODY TRAIN packet and synchronous public write')
    path=Path(private).resolve()/'det-full-body/pairs'/(pair_id+'.json');_write(path,receipt)
    return dict(det_full_body_receipt=locate_det_full_body_receipt(private,pair_id),
                det_full_body_point_receipt=point_ref)


def validate_det_full_body_export(pair_dir,receipt_ref=None,*,private=None):
    """Authenticate saved attestation/files; no table JSON decode or acquisition."""
    pair_dir=Path(pair_dir).resolve();pair=_read(pair_dir/'pair.json')
    if receipt_ref is None:
        if private is None:raise ValueError('private root required for saved full DET receipt recovery')
        receipt_ref=locate_det_full_body_receipt(private,pair['pair_id'])
    path=Path(receipt_ref['path']).resolve()
    if private is not None and not path.is_relative_to(Path(private).resolve()):
        raise ValueError('full DET receipt escapes private root')
    if _file(path)['sha256']!=receipt_ref['sha256']:raise ValueError('full DET pair receipt SHA differs')
    receipt=_read(path);point_ref=receipt['point_receipt'];point_path=Path(point_ref['path']).resolve()
    if private is not None and not point_path.is_relative_to(Path(private).resolve()):
        raise ValueError('full DET point receipt escapes private root')
    if _file(point_path)['sha256']!=point_ref['sha256']:raise ValueError('full DET point receipt SHA differs')
    point=_read(point_path);point_dir=Path(receipt['point_dir']).resolve()
    for value,schema in ((receipt,'study-det-full-body-export-v1'),(point,'study-det-full-body-point-v1')):
        if (value.get('schema')!=schema or value.get('layout')!=LAYOUT or value.get('policy')!=POLICY
                or value.get('complete') is not True or value.get('test_cells') is not _test_cells(value['tables'].values())
                or value.get('test_fit') is not False or value.get('judge_admission') is not False):
            raise ValueError('full DET export policy/completeness differs')
        for filename,expected in value['implementation'].items():
            if _file(filename)['sha256']!=expected:raise ValueError('full DET provider source bytes differ')
        for table in value['tables'].values():
            if table['missing'] or table['present']!=table['required']:
                raise ValueError('full DET saved table completeness differs')
    if (receipt['pair_dir']!=str(pair_dir) or receipt['pair_id']!=pair['pair_id']
            or pair.get('det_layout')!=LAYOUT or point['point_dir']!=str(point_dir)
            or (pair_dir/pair['point']).resolve()!=point_dir):
        raise ValueError('full DET public identity/layout differs')
    private_files=dict(pair=receipt_ref,point=point_ref)
    naming=receipt.get('namespace_receipt')
    if naming is not None:
        naming_path=Path(naming['path']).resolve()
        if private is not None and not naming_path.is_relative_to(Path(private).resolve()):
            raise ValueError('full DET namespace receipt escapes private root')
        if _file(naming_path)['sha256']!=naming['sha256']:
            raise ValueError('full DET namespace receipt SHA differs')
        naming_value=_read(naming_path)
        if (naming_value.get('schema')!='study-current-native-names-x-v1'
                or naming_value.get('pair_id')!=receipt['pair_id']
                or naming_value['source']['source_sha256'] not in
                    (receipt['source']['source_sha256'],receipt['source']['source_original_sha256'])):
            raise ValueError('full DET namespace source binding differs')
        for name,ref in naming_value['files'].items():
            file=Path(ref['path']).resolve()
            if private is not None and not file.is_relative_to(Path(private).resolve()):
                raise ValueError('full DET namespace evidence escapes private root')
            if _file(file)['sha256']!=ref['sha256']:
                raise ValueError('full DET namespace evidence SHA differs')
            private_files['namespace_'+name]=ref
        private_files['namespace']=naming
    refs={}
    _check_point_files(point_dir,point['public_files'])
    for base,value in ((pair_dir,receipt),(point_dir,point)):
        for relative,expected in value['public_files'].items():
            file=(base/relative).resolve()
            if not file.is_relative_to(base) or (base==pair_dir and _file(file)!=expected):
                raise ValueError('full DET public file SHA differs')
            refs[str(file)]=expected
    source=receipt['source'];gold=point['source']
    if any(source[k]!=v for k,v in gold.items()) or receipt['tables']['X']['required']!=point['tables']['G']['required']:
        raise ValueError('full DET pair/point source or kept axes differ')
    return dict(schema='study-det-full-body-validated-v1',complete=True,layout=LAYOUT,
        pair_id=receipt['pair_id'],task=source['task'],case=source['case'],point=source['point'],
        source=source,policy=POLICY,runtime=receipt['runtime'],gold_source_kind=point['gold_source_kind'],
        axes=dict(X=receipt['tables']['X']['required'],G=point['tables']['G']['required']),
        schemas=dict(X=receipt['tables']['X']['fields_sha256'],G=point['tables']['G']['fields_sha256']),
        receipts=private_files,public_files=refs,test_cells=receipt['test_cells'] or point['test_cells'],test_fit=False)
