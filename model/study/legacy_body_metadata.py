"""Acquire and authenticate historical BODY layouts for ordinary source exports."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time

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
        return bind_legacy_body_schema(current, program, legacy_export=old_export,
            legacy_stream=evidence['stream'], legacy_schema=schema, body_path=body_path,
            legacy_cell_width=reader.tables['width'][table], provenance=provenance, source_local=True)
