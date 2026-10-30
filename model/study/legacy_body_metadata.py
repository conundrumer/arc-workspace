"""Acquire and authenticate historical BODY layouts for ordinary source exports."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time
from functools import lru_cache
from copy import deepcopy

from native_correspondence import Correspondence, Unavailable, bind_legacy_body_schema
from study_paths import CODE_ROOT, DATA_ROOT

# This runtime exports correspondence for the canonical serializer used by
# historical corpus payloads. Actual source, streams and header are checked;
# the revision alone never establishes payload compatibility.
METADATA_COMMIT = '0c502f5c386a8e53b96dc0ce9902c3e651fe5df0'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


@lru_cache(maxsize=64)
def _native_numeric_source(repo, revision):
    """Pin the native signed term and packing operations at one full commit."""
    from native_correspondence import _SIGNED_I32_OPERATIONS
    terms=subprocess.check_output(['git','-C',str(repo),'show',revision+':engine/arclog/src/terms.rs'],text=True)
    columns=subprocess.check_output(['git','-C',str(repo),'show',revision+':engine/arclog-tables/src/columns.rs'],text=True)
    operations={}
    for name in ('decode_number','encode_number'):
        start=terms.index('pub fn '+name+'(');end=terms.index('\n    }',start)+6
        operations[name]=digest(terms[start:end].encode())
    for name,text,source in (
        ('number_storage','pub struct Number(pub i32);',terms),
        ('packed_number','Term::Number(number) => out.push(number.0),',columns)):
        if source.count(text)!=1:raise Unavailable('native signed numeric implementation differs')
        operations[name]=digest(text.encode())
    if operations!=_SIGNED_I32_OPERATIONS or 'pub values: Vec<i32>' not in columns:
        raise Unavailable('native signed-i32 encoding is not the pinned protocol')
    dispatches={
        'Number':'ValueType::Number => Term::Number(Number(Term::decode_number(id)))',
        'Int|Nat':'ValueType::Int | ValueType::Nat => Term::Number(Number(Term::decode_number(id)))'}
    found=[name for name,text in dispatches.items() if text in terms]
    if len(found)!=1:raise Unavailable('native numeric dispatch is not certified')
    return dict(revision=revision,terms_sha256=digest(terms.encode()),
                columns_sha256=digest(columns.encode()),operations=operations,dispatch=found[0])


_NUMERIC_BUILD_CACHE = {}


def _loaded_numeric_build():
    import arclog
    import importlib.util
    from types import SimpleNamespace
    binary=Path(importlib.util.find_spec('arclog.arclog').origin).resolve()
    roots=[p.parent for p in binary.parents if p.name=='venv' and (p.parent/'ready.json').is_file()]
    if len(roots)!=1:raise Unavailable('numeric compatibility requires an immutable native runtime receipt')
    ready=json.loads((roots[0]/'ready.json').read_text())
    wheel=Path(ready['wheel'])
    stamp=lambda p:(str(p),p.stat().st_dev,p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ctime_ns)
    key=(ready['revision'],stamp(binary),stamp(wheel))
    if key not in _NUMERIC_BUILD_CACHE:
        spec=importlib.util.spec_from_file_location('_numeric_provenance',CODE_ROOT/'ast/run/provenance.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        _NUMERIC_BUILD_CACHE.clear()
        _NUMERIC_BUILD_CACHE[key]=module.load_build(arclog,SimpleNamespace(build_receipt=None,
            engine_commit=ready['revision'],wheel=wheel))
    return deepcopy(_NUMERIC_BUILD_CACHE[key])


def _numeric_scan(reader, table, schema, columns):
    """Read signed scalars from validated complete runs, without decoding cells."""
    if reader.tables['projections'][table]!=0 or reader.tables['projections_stop_bound'][table]:
        raise Unavailable('historical numeric domain cannot use projection payloads')
    ids=list(reader.bytable[table])
    if not ids or len(ids)!=len(set(ids)):
        raise Unavailable('historical numeric domain requires actual complete table entries')
    width=reader.tables['width'][table]
    native_width=reader.schema.__func__.__globals__['width']
    offsets={i:native_width([c['type'] for c in schema[:i]]) for i in columns}
    stats={i:dict(entries=[],row_count=0,min=None,max=None) for i in columns}
    coverage=[]
    for entry in ids:
        checked=reader.validate_entry(entry,with_extents=False,projection_stop=False)
        if checked['table']!=table or checked['schema']!=schema:
            raise Unavailable('numeric domain validation selected another table or schema')
        count=checked['count']
        assigned=[{k:v[i] for k,v in reader.parts['assigned'].items()} for i in reader.assigned[entry]]
        meta=dict(entry=entry,kind=int(reader.entries['kind'][entry]),
            example_kind=int(reader.entries['example_kind'][entry]),
            example_index=int(reader.entries['example_index'][entry]),model=int(reader.entries['model'][entry]),
            rows=count,offset=int(reader.entries['offset'][entry]),status='complete',
            assignment_metadata_sha256=digest(canonical(assigned)))
        coverage.append(meta)
        for column,offset in offsets.items():
            lo=None;hi=None
            for row in range(count):
                value=reader.values[meta['offset']+row*width+offset]
                lo=value if lo is None else min(lo,value);hi=value if hi is None else max(hi,value)
            target=stats[column];target['row_count']+=count
            if count:
                target['min']=lo if target['min'] is None else min(target['min'],lo)
                target['max']=hi if target['max'] is None else max(target['max'],hi)
            target['entries'].append(dict(coverage=meta,row_count=count,min=lo,max=hi))
    return coverage,stats


class LegacyBodyMetadata:
    def __init__(self):
        self.metadata = {}
        self.runtime = DATA_ROOT / 'ast/run' / ('runtime-' + METADATA_COMMIT[:8])

    @classmethod
    def configured(cls):
        return cls()

    def acquire(self, record):
        worker = CODE_ROOT / 'legacy_body_worker.py'
        ready_path = self.runtime / 'ready.json'
        if not ready_path.exists():
            raise Unavailable('historical BODY metadata runtime missing: '+str(self.runtime))
        ready = json.loads(ready_path.read_text())
        implementation = {str(path):digest(path.read_bytes()) for path in
            (worker, Path(__file__), CODE_ROOT / 'native_correspondence.py',
             CODE_ROOT / 'ast/run/provenance.py')}
        if ready['revision'] != METADATA_COMMIT:
            raise Unavailable('historical BODY correspondence runtime revision differs')
        source = canonical(record)
        key = digest(canonical(dict(source_sha256=digest(source), runtime=ready,
                                    implementation=implementation)))
        if key in self.metadata:
            return self.metadata[key]
        root = DATA_ROOT / 'judgetool/legacy-body-metadata'
        root.mkdir(parents=True, exist_ok=True)
        path = root / (key + '.json.gz')
        if path.exists():
            envelope = json.loads(gzip.decompress(path.read_bytes()))
        else:
            result = subprocess.run([str(self.runtime/'venv/bin/python'), '-B', str(worker)],
                input=canonical(dict(record=record,runtime_ready=ready)),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode:
                raise Unavailable('historical BODY metadata compilation failed: '+
                                  result.stderr.decode(errors='replace')[-3000:])
            value = json.loads(result.stdout)
            envelope = dict(value=value, value_sha256=digest(canonical(value)),
                            implementation=implementation, runtime=ready)
            temporary = path.with_name(path.name+'.'+str(time.time_ns())+'.tmp')
            temporary.write_bytes(gzip.compress(canonical(envelope), mtime=0))
            temporary.replace(path)
        value = envelope['value']
        if (envelope['implementation'] != implementation or envelope['runtime'] != ready
                or envelope['value_sha256'] != digest(canonical(value))
                or value['schema'] != 'legacy-native-body-metadata-v2'
                or canonical(value['source_record']) != source):
            raise Unavailable('historical BODY cached source/runtime evidence differs')
        if (value['build']['engine_commit'] != ready['revision']
                or digest(Path(value['build']['wheel_path']).read_bytes()) != value['build']['wheel_sha256']):
            raise Unavailable('historical BODY acquisition build revision/wheel differs')
        binary = Path(value['runtime']['binary'])
        if (not binary.resolve().is_relative_to(self.runtime.resolve())
                or digest(binary.read_bytes()) != value['runtime']['binary_sha256']):
            raise Unavailable('historical BODY metadata native binary differs')
        self.metadata[key] = value, dict(path=str(path), sha256=digest(path.read_bytes()),
            canonical_value_sha256=envelope['value_sha256'], implementation=implementation)
        return self.metadata[key]

    def bind(self, *, record, side, base, reader, table, schema, program, export, body_path):
        views = [v for v in export['body_views'] if v['body_path'] == body_path]
        if len(views) != 1:
            raise Unavailable('current BODY descriptor is ambiguous')
        # This only decides whether historical acquisition is needed. It
        # supplies no binding or compatibility proof.
        if [c['type'] for c in schema] == [c['type'] for c in views[0]['columns']]:
            return None
        roles = [role for role,index in record['evaluation']['table_indices'].items()
                 if role in (side+'_all', side+'_kept') and index == table]
        if not roles:
            raise Unavailable('historical BODY actual table has no source report role')
        selector = {k:reader.tables[k][table] for k in ('form','point','relation','fact')}
        for key,expected in views[0]['native_table_selector'].items():
            if key in selector and selector[key] != expected:
                raise Unavailable('historical BODY actual payload selector differs')
        ref = record['native'][side]
        with (Path(base) / ref['path']).open('rb') as stream:
            stream.seek(ref['offset'])
            raw = stream.read(ref['bytes'])
        if len(raw) != ref['bytes'] or digest(raw) != ref['sha256']:
            raise Unavailable('historical BODY compressed native payload differs')
        value, acquisition = self.acquire(record)
        evidence = value['sides'][side]
        old_export = evidence['export']
        if old_export['program_sexp'] != record['programs'][side]:
            raise Unavailable('historical BODY exact source writer differs')
        current = Correspondence(export, program_sexp=program.sexp(),
            source_program_sexp=export['correspondence']['source_program_sexp'])
        provenance = dict(legacy_runtime=str(self.runtime),
            source_record_sha256=digest(canonical(record)), native_payload_sha256=ref['sha256'],
            legacy_export_sha256=digest(canonical(old_export)), legacy_schema_sha256=digest(canonical(schema)),
            side=side, roles=roles, table=table, selector=selector,
            native_payload=dict(base=str(base), reference=ref,
                producer={k:record.get(k) for k in ('engine_commit','wheel_sha256','native_binary_sha256')}),
            acquisition=acquisition, acquisition_build=value['build'],
            runtime=value['runtime'], mutation=value['mutation'])
        # Pair only native scoped IDs; the binder repeats the complete stream,
        # source and exact old-header assertions before admitting this evidence.
        old=Correspondence(old_export,program_sexp=old_export['program_sexp'],
            source_program_sexp=old_export['correspondence']['source_program_sexp'])
        old_fields=old.body(body_path)['columns']
        now={(tuple(c['scope_path']),c['label_id']):c for c in current.body(body_path)['columns']}
        numeric=[]
        for field in old_fields:
            linked=now.get((tuple(field['scope_path']),field['label_id']))
            if (field['physical_type']['type']=='Number' and linked is not None
                    and linked['physical_type']['type'] in ('Int','Nat')):
                numeric.append((field,linked))
        if numeric:
            from native_correspondence import _numeric_context
            producer=provenance['native_payload']['producer']
            live=_loaded_numeric_build()
            encoding=dict(schema='native-signed-i32-protocol-v1',producer=producer,
                acquisition=live,legacy_acquisition=value['build'])
            repo=CODE_ROOT.parents[1]
            encoding['sources']={build['engine_commit']:_native_numeric_source(repo,build['engine_commit'])
                for build in (producer,live,value['build'])}
            nat=[old['physical_column'] for old,new in numeric if new['physical_type']['type']=='Nat']
            coverage,stats=_numeric_scan(reader,table,schema,nat) if nat else (None,{})
            provenance.update(native_numeric_encoding=encoding,numeric_entry_coverage=coverage,
                numeric_entry_ids=list(reader.bytable[table]) if nat else None,
                numeric_program_sha256=digest(program.sexp().encode()),numeric_domains={})
            for field,linked in numeric:
                column=field['physical_column']
                if column in stats:
                    context=_numeric_context(provenance,body_path=body_path,scope_path=field['scope_path'],
                        label_id=field['label_id'],physical_column=column,
                        old_descriptor=field['physical_type'],current_descriptor=linked['physical_type'])
                    provenance['numeric_domains'][str(column)]=dict(stats[column],
                        schema='legacy-numeric-domain-v1',context=context,complete=True,
                        policy=dict(with_extents=False,projection_stop=False))
        return bind_legacy_body_schema(current, program, legacy_export=old_export,
            legacy_stream=evidence['stream'], legacy_schema=schema, body_path=body_path,
            legacy_cell_width=reader.tables['width'][table], provenance=provenance, source_local=True)
