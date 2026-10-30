"""Look up native-certified source correspondence without reconstructing it.

Paths, labels and columns are scoped to the exact current/source programs.
This module does not infer mappings, project cells or authenticate row coverage.
Packed payload authentication is a separate acquisition boundary (rule B).
"""
from copy import deepcopy


class Unavailable(ValueError):
    """The requested native identity is missing, ambiguous or unsupported."""


def _path(value):
    if not isinstance(value, (list, tuple)) or any(type(n) is not int or n < 0 for n in value):
        raise Unavailable('invalid native correspondence path')
    return tuple(value)


def _unique(rows, key, name):
    if not isinstance(rows, list):
        raise Unavailable('missing native '+name+' inventory')
    result = {}
    for row in rows:
        identity = key(row)
        if identity in result:
            raise Unavailable('ambiguous native '+name+' identity')
        result[identity] = row
    return result


def _type(value):
    if (not isinstance(value, dict) or not isinstance(value.get('type'), str)
            or not isinstance(value.get('wire_type'), str)
            or type(value.get('cell_width')) is not int or value['cell_width'] < 0
            or type(value.get('nominal')) is not bool):
        raise Unavailable('native physical/source type descriptor unavailable')
    return value


class Correspondence:
    """Read-only lookup view of one authenticated native metadata export.

    The caller supplies exact native writer strings from the acquired handles.
    File/runtime/source authentication stays in the caller's acquisition receipt.
    Returning one deep-copied record prevents mutation of cached native exports.
    """
    def __init__(self, export, *, program_sexp, source_program_sexp):
        try:
            value = export['correspondence']
            if (value['schema'] != 'arclog-study-correspondence-v1'
                    or value['program_sexp'] != program_sexp
                    or export['program_sexp'] != program_sexp
                    or value['source_program_sexp'] != source_program_sexp):
                raise Unavailable('native correspondence program/schema binding differs')
            if value['source_bridge_status'] not in ('same_checked_representation', 'native_writer_trace'):
                raise Unavailable('native source bridge unsupported')
            self._value = value
            self._bodies = _unique(value['bodies'], lambda r: _path(r['body_path']), 'BODY')
            self._relations = _unique(value['relations'], lambda r: r['relation_slot'], 'relation')
            self._readers = _unique(value['readers'],
                lambda r: (_path(r['occurrence_path']), _path(r['argument_path'])), 'scalar reader')
        except (KeyError, TypeError) as error:
            raise Unavailable('native correspondence metadata incomplete') from error

    def body(self, path, *, source=True):
        row = self._bodies.get(_path(path))
        if row is None or (source and row.get('source_status') != 'resolved'):
            raise Unavailable('native BODY source path unavailable')
        return deepcopy(row)

    def body_column(self, path, column, *, source=True):
        row = self.body(path, source=source)
        found = [f for f in row['columns'] if f['physical_column'] == column]
        if len(found) != 1:
            raise Unavailable('native BODY physical column unavailable')
        field = found[0]
        _type(field['physical_type'])
        if source:
            canonical = field.get('canonical_source', {})
            if canonical.get('status') != 'resolved' or field.get('source_body_column') is None:
                raise Unavailable('native BODY column source/type unavailable')
            _type(canonical['source_type'])
        return field

    def relation(self, slot):
        row = self._relations.get(slot)
        if row is None:
            raise Unavailable('native relation slot unavailable')
        return deepcopy(row)

    def reader(self, occurrence_path, argument_path):
        row = self._readers.get((_path(occurrence_path), _path(argument_path)))
        if row is None:
            raise Unavailable('native scalar reader unavailable')
        if row.get('resolution', {}).get('kind') not in ('node', 'library'):
            raise Unavailable('native scalar reader resolution unsupported')
        return deepcopy(row)

    def reader_header(self, occurrence_path, argument_path):
        row = self.reader(occurrence_path, argument_path)
        if row.get('entry_axis_binding') is True:
            raise Unavailable('native reader requires_source_entry_context')
        if row.get('header_column') is None or row.get('header_key') is None:
            raise Unavailable('native reader physical header unavailable')
        return row

    def inventory(self):
        row = self._value.get('table_inventory', {})
        if row.get('complete') is not True:
            raise Unavailable('native materialized-table inventory incomplete')
        return deepcopy(row)

    def nominal_pairs(self):
        """Yield native physical/source type pairs, retaining every alias.

        Unsupported columns are not evidence. No pairing by physical ordinal,
        source name, nominal spelling or type similarity occurs here.
        """
        for relation in self._relations.values():
            for field in relation['columns']:
                current = _type(field['physical_type'])
                if not current['nominal'] or field.get('source_status') != 'resolved_aliases':
                    continue
                for source in field['source_columns']:
                    original = _type(source['physical_type'])
                    if (not original['nominal'] or current['wire_type'] != original['wire_type']
                            or current['cell_width'] != original['cell_width']):
                        raise Unavailable('native nominal source/physical encoding differs')
                    yield deepcopy(dict(physical_type=current, source_type=original,
                        relation_slot=relation['relation_slot'], physical_column=field['physical_column'],
                        source_column=source))

    def body_from_source(self, source_path):
        """Invert only native-certified path links, requiring uniqueness."""
        wanted = _path(source_path)
        rows = [r for r in self._bodies.values() if r.get('source_status') == 'resolved'
                and r.get('source_body_path') is not None and _path(r['source_body_path']) == wanted]
        if len(rows) != 1:
            raise Unavailable('native source BODY has no unique current path')
        return deepcopy(rows[0])

    def body_column_from_source(self, source_path, column, *, scope_path, label_id):
        """Invert the emitted physical permutation and scoped label proof."""
        body = self.body_from_source(source_path)
        rows = [f for f in body['columns'] if f.get('source_body_column') == column
                and f.get('canonical_source', {}).get('status') == 'resolved'
                and f['canonical_source'].get('scope_path') == list(scope_path)
                and f['canonical_source'].get('label_id') == label_id]
        if len(rows) != 1:
            raise Unavailable('native source BODY field has no unique current physical column')
        field = rows[0]
        _type(field['physical_type']); _type(field['canonical_source']['source_type'])
        return deepcopy(field)


def source_program_record(record):
    """Expose exact paired source aliases without changing either program."""
    programs=record.get('programs')
    if programs is None:
        programs={side:record[side+'_sexp'] for side in ('gold','mutant')}
        record=dict(record,programs=programs)
    if any(not isinstance(programs.get(side),str)
           or record.get(side+'_sexp',programs[side])!=programs[side]
           for side in ('gold','mutant')):
        raise Unavailable('paired source program aliases disagree')
    return record


def live_payload_digest(payload):
    """Hash exact typed native buffers and all metadata without copying values.

    This is a framed content digest, not a storage format. It cannot reload a
    payload or authenticate a separately supplied persisted payload by itself.
    """
    import hashlib
    import json
    buffers = 0
    def describe(value):
        nonlocal buffers
        if isinstance(value, (bytes, bytearray, memoryview)):
            view = memoryview(value).cast('B')
            buffers += view.nbytes
            return ['buffer', view.nbytes, hashlib.sha256(view).hexdigest()]
        if isinstance(value, dict):
            return ['object', [[k, describe(v)] for k, v in sorted(value.items())]]
        if isinstance(value, (list, tuple)):
            return ['array', [describe(v) for v in value]]
        if value is None or type(value) in (str, int, bool, float):
            return ['scalar', value]
        raise Unavailable('unsupported native payload digest metadata')
    names = ('task', 'case', 'concept', 'projection_cap', 'base', 'base_tokens',
             'base_tables', 'materialization_stop', 'dtypes', 'values', 'tables',
             'entries', 'assigned', 'projections', 'projection_rows', 'flows', 'copies')
    framed = describe({name: getattr(payload, name) for name in names})
    data = json.dumps(framed, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()
    return dict(format='native-live-framed-sha256-v1', sha256=hashlib.sha256(data).hexdigest(),
                buffer_bytes=buffers, reloadable=False, persisted_payload=False)


class AtomicPacked:
    """Validate only an original atomic native report/CaseTables acquisition.

    No constructor for persisted reports/payloads is provided. Rule B requires
    an actual stored-payload binding receipt for any later persisted lookup.
    """
    def __init__(self, report, reader, *, program_sexp, side):
        value = report.get('packed_correspondence', {})
        if (not isinstance(value, dict)
                or value.get('schema') != 'arclog-study-packed-correspondence-v1'
                or value.get('program_sexp') != program_sexp or value.get('side') != side
                or not isinstance(value.get('packing_ref'), str) or not value['packing_ref']):
            raise Unavailable('atomic native packed program/side binding unavailable')
        self._value = value
        self._reader = reader
        self._tables = _unique(value.get('tables'), lambda r: r['table'], 'packed table')

    def table(self, index, *, role):
        row = self._tables.get(index)
        reader = self._reader
        if row is None or role not in row.get('report_roles', []):
            raise Unavailable('native packed table index/role binding unavailable')
        ts = reader.tables
        if type(index) is not int or not 0 <= index < len(ts['width']):
            raise Unavailable('native packed table is outside actual payload')
        for key, part in (('physical_types', 'column_types'), ('physical_names', 'column_names'),
                          ('physical_labels', 'column_labels'), ('physical_slots', 'column_slots')):
            if row[key] != ts[part][index]:
                raise Unavailable('native packed physical schema differs from actual payload')
        if row['cell_width'] != ts['width'][index]:
            raise Unavailable('native packed cell width differs from actual payload')
        for key, value in row['selector'].items():
            if key in ('form', 'point', 'relation', 'fact') and value != ts[key][index]:
                raise Unavailable('native packed selector differs from actual payload')
        for entry in reader.bytable[index]:
            if reader.entries['clause_index'][entry] != row['clause_index']:
                raise Unavailable('native entry clause identity differs from packed binding')
        return deepcopy(row)

    def receipt(self, payload, *, report_sha256, source_sha256, runtime):
        return dict(schema='evaluator-live-packed-acquisition-v1',
            binding_contract='original atomic tuple only; not a persisted payload lookup receipt',
            packing_ref=self._value['packing_ref'], program_sexp=self._value['program_sexp'],
            side=self._value['side'], report_sha256=report_sha256, source_sha256=source_sha256,
            runtime=deepcopy(runtime), payload_ref=live_payload_digest(payload))


def _native_stream(program):
    """Read all three native stream coordinates; no sexp/text normalization."""
    raw = program.decode_stream()
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        raise Unavailable('native program stream must contain ids, model flags and paths')
    ids, model, paths = raw
    if (len(ids) != len(model) or len(ids) != len(paths)
            or any(type(n) is not int or n < 0 for n in ids)
            or any(type(n) not in (int, bool) or not 0 <= n <= 255 for n in model)):
        raise Unavailable('native program stream coordinates are incomplete')
    return dict(ids=list(ids), model=list(map(int, model)),
                paths=[list(_path(path)) for path in paths])


def certify_stored_representation(rehydrated, stored, *, requested_text,
        rehydrated_export, stored_export, mutation_identity,
        alternate_programs=(), recorded_stream=None):
    """Certify an exact stored writer representation of one native mutation.

    Both handles and their metadata must be from the same native runtime.
    This binds complete native token/model/path streams, never text edits or a
    guessed node-path map. Each returned export keeps its own node identities.
    It does not certify historical payloads, rows, kept contexts or old types.
    """
    import hashlib
    import json
    def digest(value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=False,
            sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    for program, export in ((rehydrated, rehydrated_export), (stored, stored_export)):
        if (export.get('schema') != 'arclog-study-render-v1'
                or export.get('parts', {}).get('nodes') != 'complete'
                or export.get('program_sexp') != program.sexp()):
            raise Unavailable('native representation export/handle binding differs')
    if rehydrated_export.get('mutation_identity') != mutation_identity:
        raise Unavailable('native rehydrated mutation identity differs from record')
    if not isinstance(requested_text, str) or stored_export['program_sexp'] != requested_text:
        raise Unavailable('stored native writer representation differs from exact record text')
    expected = _native_stream(rehydrated)
    compared = [stored, *alternate_programs]
    if any(_native_stream(program) != expected for program in compared):
        raise Unavailable('native stored/rehydrated ids, model flags or paths differ')
    if recorded_stream is not None and recorded_stream != expected:
        raise Unavailable('recorded native stream differs from exact rehydrated stream')
    return dict(schema='native-stored-representation-v1',
        mutation_identity=deepcopy(mutation_identity),
        rehydrated_program_sexp=rehydrated_export['program_sexp'],
        stored_program_sexp=requested_text,
        rehydrated_export_sha256=digest(rehydrated_export),
        stored_export_sha256=digest(stored_export),
        stream_sha256=digest(expected), stream_coordinates=['ids', 'model', 'paths'],
        stream_length=len(expected['ids']), compared_programs=1+len(compared),
        recorded_stream_checked=recorded_stream is not None,
        node_mapping='none; each representation uses its own native export',
        historical_payload_authority=False)


# Native source implementation fingerprints, not descriptor-name aliases.
_SIGNED_I32_OPERATIONS = {
    'decode_number': '43b3627cd0129742845e2984b68a9c7289ae9f1222283182e5fff433212fef15',
    'encode_number': '12512a983cc402ee9cdb184da5a2e78a217d24ac13a8bd75c6d53bcb38526bac',
    'number_storage': '719df7523ba584aac80cbe43c2fa1a5a139fd51d590c3e5e3311a22b0ec61857',
    'packed_number': 'fcde6a79b72b38440e47a7800ca2fe0c26a51ef0068ca7cddff53eda798e0e7c',
}


def _numeric_context(provenance, *, body_path, scope_path, label_id,
                     physical_column, old_descriptor, current_descriptor):
    return dict(source_record_sha256=provenance['source_record_sha256'],
        program_sha256=provenance['numeric_program_sha256'],
        native_payload_sha256=provenance['native_payload_sha256'],
        side=provenance['side'], table=provenance['table'], selector=provenance['selector'],
        body_path=list(body_path), scope_path=list(scope_path), label_id=label_id,
        physical_column=physical_column, old_descriptor=old_descriptor,
        current_descriptor=current_descriptor,
        producer=provenance['native_payload']['producer'],
        acquisition=provenance['native_numeric_encoding']['acquisition'],
        legacy_acquisition=provenance['acquisition_build'],
        entry_ids=provenance.get('numeric_entry_ids'),
        entry_coverage=provenance.get('numeric_entry_coverage'))


def numeric_compatibility(old_descriptor, current_descriptor, *, domain=None,
                          expected_context, encoding):
    """One directional, source-attested Number -> Int/Nat transport bridge."""
    old,new=_type(old_descriptor),_type(current_descriptor)
    shape=lambda v:(v['type'],v['wire_type'],v['cell_width'],v['nominal'])
    if (shape(old)!=('Number','Number',1,False)
            or shape(new) not in (('Int','Int',1,False),('Nat','Nat',1,False))
            or expected_context['old_descriptor']!=old
            or expected_context['current_descriptor']!=new):
        raise Unavailable('unsupported directional historical numeric descriptors')
    if (not isinstance(encoding,dict) or encoding.get('schema')!='native-signed-i32-protocol-v1'
            or encoding['producer']!=expected_context['producer']
            or encoding['acquisition']!=expected_context['acquisition']
            or encoding['legacy_acquisition']!=expected_context['legacy_acquisition']):
        raise Unavailable('historical numeric encoding producer/acquisition differs')
    hex_digest=lambda value,length:isinstance(value,str) and len(value)==length and all(c in '0123456789abcdef' for c in value)
    for role in ('producer','acquisition','legacy_acquisition'):
        build=encoding[role];source=encoding['sources'].get(build['engine_commit'],{})
        # provenance.load_build returns every wheel extension by basename.
        # Preserve that exact manifest in the context, including all digests.
        binaries=build.get('native_binary_sha256')
        manifest=(isinstance(binaries,dict) and bool(binaries)
            and all(isinstance(name,str) and name not in ('.','..')
                and '/' not in name and '\\' not in name and name.endswith(('.so','.pyd'))
                and hex_digest(value,64) for name,value in binaries.items()))
        checks=dict(revision=hex_digest(build['engine_commit'],40),
            source_revision=source.get('revision')==build['engine_commit'],
            operations=source.get('operations')==_SIGNED_I32_OPERATIONS,
            terms_sha256=hex_digest(source.get('terms_sha256'),64),
            columns_sha256=hex_digest(source.get('columns_sha256'),64),
            dispatch=source.get('dispatch')==('Int|Nat' if role=='acquisition' else 'Number'),
            native_binary_sha256=manifest,wheel_sha256=hex_digest(build.get('wheel_sha256'),64))
        failed=[name for name,valid in checks.items() if not valid]
        if failed:
            raise Unavailable('historical numeric native implementation attestation missing: '
                              +role+': '+','.join(failed))
    if new['type']=='Nat':
        if (not isinstance(domain,dict) or domain.get('schema')!='legacy-numeric-domain-v1'
                or domain.get('context')!=expected_context
                or domain.get('policy')!=dict(with_extents=False,projection_stop=False)
                or domain.get('complete') is not True
                or not expected_context['entry_coverage']):
            raise Unavailable('Nat requires complete actual historical column domain evidence')
        entries=domain['entries'];coverage=expected_context['entry_coverage']
        if (len(entries)!=len(coverage)
                or [e['entry'] for e in coverage]!=expected_context['entry_ids']
                or len(set(expected_context['entry_ids']))!=len(coverage)):
            raise Unavailable('historical numeric entry coverage differs')
        total=0;minimum=None;maximum=None
        for entry,expected in zip(entries,coverage):
            count=entry.get('row_count');lo=entry.get('min');hi=entry.get('max')
            if (entry.get('coverage')!=expected or expected['kind']!=0
                    or expected['status']!='complete' or type(count) is not int
                    or count<0 or count!=expected['rows']
                    or (count==0 and (lo is not None or hi is not None))
                    or (count>0 and (type(lo) is not int or type(hi) is not int
                        or not 0<=lo<=hi<=2147483647))):
                raise Unavailable('historical Nat column is negative or incompletely validated')
            total+=count
            if count:minimum=lo if minimum is None else min(minimum,lo);maximum=hi if maximum is None else max(maximum,hi)
        if (type(domain['row_count']) is not int
                or (domain['row_count'],domain['min'],domain['max'])!=(total,minimum,maximum)):
            raise Unavailable('historical numeric domain totals differ')
    return dict(schema='native-legacy-numeric-compatibility-v1',
        direction='Number->'+new['type'],context=deepcopy(expected_context),
        encoding=deepcopy(encoding),domain=deepcopy(domain) if new['type']=='Nat' else None)


def _legacy_type_compatibility(old, new, *, provenance, body_path, scope_path,
                               label_id, physical_column, evidence=None, require_evidence=False):
    old,new=_type(old),_type(new)
    if old['type']=='Number' and new['type'] in ('Int','Nat'):
        context=_numeric_context(provenance,body_path=body_path,scope_path=scope_path,
            label_id=label_id,physical_column=physical_column,
            old_descriptor=old,current_descriptor=new)
        supplied=provenance.get('numeric_domains',{}).get(str(physical_column))
        proof=numeric_compatibility(old,new,expected_context=context,
            encoding=provenance['native_numeric_encoding'],domain=supplied)
        if (require_evidence or evidence is not None) and evidence!=proof:
            raise Unavailable('historical numeric compatibility proof link differs')
        return proof
    if (old['wire_type']!=new['wire_type'] or old['cell_width']!=new['cell_width']
            or old['nominal']!=new['nominal']
            or (old['type']!=new['type'] and not old['nominal'])):
        raise Unavailable('legacy/current native BODY type or encoding differs')
    if evidence is not None:
        raise Unavailable('non-numeric field carries unrelated numeric compatibility evidence')
    return None


def bind_legacy_body_schema(current, current_program, *, legacy_export,
        legacy_stream, legacy_schema, body_path, legacy_cell_width, provenance,
        source_local=False):
    """Bind an authenticated historical BODY using its own native descriptor.

    The acquisition owner authenticates the legacy payload/file/runtime/source
    before this lookup, as for Correspondence. This validates its exact header
    against the old export, then links scoped native IDs under equal complete
    streams. It never parses nominal debug strings or borrows a gold node map.
    No row, assignment or cross-session Ident evidence is established here.
    """
    import hashlib
    import json
    def digest(value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=False,
            sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    required = ('legacy_runtime', 'source_record_sha256', 'native_payload_sha256',
                'legacy_export_sha256', 'legacy_schema_sha256')
    if (not isinstance(provenance, dict)
            or any(not isinstance(provenance.get(k), str) or not provenance[k] for k in required)
            or provenance['legacy_export_sha256'] != digest(legacy_export)
            or provenance['legacy_schema_sha256'] != digest(legacy_schema)):
        raise Unavailable('legacy BODY acquisition/export/schema provenance incomplete')
    if (current._value['program_sexp'] != current_program.sexp()
            or legacy_export.get('program_sexp') != current_program.sexp()
            or _native_stream(current_program) != legacy_stream):
        raise Unavailable('legacy/current BODY program or complete native stream differs')
    old = Correspondence(legacy_export,
        program_sexp=legacy_export['program_sexp'],
        source_program_sexp=legacy_export['correspondence']['source_program_sexp'])
    if type(source_local) is not bool:
        raise Unavailable('source_local must be boolean')
    if source_local and any(
            value['source_program_sexp'] != value['program_sexp']
            or value['source_bridge_status'] != 'same_checked_representation'
            for value in (old._value, current._value)):
        raise Unavailable('legacy/current BODY descriptors must both bind their own checked representation')
    before, after = old.body(body_path), current.body(body_path)
    # Native scope+LabelId is the key. Physical positions are asserted against
    # the old layout, rather than zipped against a newly emitted header.
    now = _unique(after['columns'],
        lambda f: (_path(f['scope_path']), f['label_id']), 'current scoped BODY field')
    views = [v for v in legacy_export.get('body_views', []) if v.get('body_path') == list(body_path)]
    if len(views) != 1:
        raise Unavailable('legacy native BODY view unavailable or ambiguous')
    view = _unique(views[0]['columns'], lambda f: f['body_column'], 'legacy BODY view field')
    schema = _unique(legacy_schema, lambda f: f['index'], 'legacy physical header field')
    if (set(schema) != set(view)
            or set(schema) != {f['physical_column'] for f in before['columns']}
            or len(now) != len(schema)):
        raise Unavailable('legacy/current BODY physical field coverage differs')
    fields = []
    for field in before['columns']:
        index = field['physical_column']
        header, authored = schema[index], view[index]
        old_type = _type(field['physical_type'])
        if (header['type'] != old_type['type'] or header['type'] != authored['type']
                or header['name'] != authored['native_column_name']
                or header['source_label'] != authored['label_spelling']
                or authored['label_id'] != field['label_id']):
            raise Unavailable('legacy physical BODY header differs from its native descriptor')
        identity = (_path(field['scope_path']), field['label_id'])
        linked = now.get(identity)
        if linked is None:
            raise Unavailable('legacy BODY scoped label absent from current native descriptor')
        new_type = _type(linked['physical_type'])
        old_source, new_source = field['canonical_source'], linked['canonical_source']
        if (old_source.get('status') != 'resolved' or new_source.get('status') != 'resolved'
                or (old_source['scope_path'], old_source['label_id'], old_source['name'])
                    != (new_source['scope_path'], new_source['label_id'], new_source['name'])):
            raise Unavailable('legacy/current native BODY scoped type or encoding differs')
        compatibility=_legacy_type_compatibility(old_type,new_type,provenance=provenance,
            body_path=body_path,scope_path=field['scope_path'],label_id=field['label_id'],physical_column=index)
        fields.append(dict(native_compatibility=compatibility,physical_column=index, current_physical_column=linked['physical_column'],
            scope_path=list(identity[0]), label_id=identity[1],
            legacy_physical_type=deepcopy(old_type), physical_type=deepcopy(new_type),
            canonical_source=deepcopy(new_source)))
    if sum(f['legacy_physical_type']['cell_width'] for f in fields) != legacy_cell_width:
        raise Unavailable('legacy native BODY packed width differs from its descriptor')
    result = dict(schema='native-legacy-body-binding-v1', body_path=list(body_path),
        fields=sorted(fields, key=lambda f: f['physical_column']),
        receipt=dict(provenance=deepcopy(provenance),
            program_sha256=hashlib.sha256(current_program.sexp().encode()).hexdigest(),
            stream_sha256=digest(legacy_stream),
            legacy_correspondence_sha256=digest(old._value),
            current_correspondence_sha256=digest(current._value),
            source_local=source_local,
            legacy_source_program_sha256=hashlib.sha256(old._value['source_program_sexp'].encode()).hexdigest(),
            current_source_program_sha256=hashlib.sha256(current._value['source_program_sexp'].encode()).hexdigest(),
            native_compatibility=[dict(physical_column=f['physical_column'],evidence=deepcopy(f['native_compatibility'])) for f in fields if f['native_compatibility'] is not None],
            mapping='native scoped LabelId under exact program and full-stream equality',
            nominal_strings='retained verbatim; never parsed or normalized', rows_checked=False))

    # Projected schemas retain fields, while their enclosing temporary header
    # object need not survive. Keep its acquisition authority with each field.
    for field in result['fields']:
        field['binding_receipt'] = deepcopy(result['receipt'])
    return result


def certify_legacy_body_projection(source_correspondence, *, body_path,
        source_column, field, current_column, actual_type, source_program,
        native_payload_sha256):
    """Compose legacy acquisition -> current source -> fresh inverse proofs.

    No nominal string conversion occurs. Both descriptor edges must already
    be exported by native correspondence, and the saved acquisition must bind
    this exact source program and original gold payload.
    """
    import hashlib
    import json
    def digest(value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=False,
            sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    binding = field.get('native_legacy_binding', {})
    receipt = binding.get('binding_receipt', {})
    program_sha = hashlib.sha256(source_program.encode()).hexdigest()
    if (receipt.get('source_local') is not True
            or receipt.get('program_sha256') != program_sha
            or receipt.get('current_source_program_sha256') != program_sha
            or receipt.get('provenance', {}).get('native_payload_sha256') != native_payload_sha256
            or not isinstance(native_payload_sha256, str) or not native_payload_sha256
            or source_correspondence._value['program_sexp'] != source_program
            or source_correspondence._value['source_program_sexp'] != source_program
            or source_correspondence._value['source_bridge_status'] != 'same_checked_representation'):
        raise Unavailable('legacy BODY projection lacks exact source-local acquisition authority')
    original = source_correspondence.body_column(body_path, source_column)
    legacy_type = _type(binding['legacy_physical_type'])
    checked_type = _type(binding['physical_type'])
    source_type = _type(original['physical_type'])
    fresh_type = _type(current_column['physical_type'])
    fresh_source = current_column['canonical_source']
    if (binding['physical_column'] != source_column
            or binding['current_physical_column'] != original['physical_column']
            or binding['scope_path'] != original['scope_path']
            or binding['label_id'] != original['label_id']
            or field.get('native_type',field['type']) != legacy_type['type']
            or checked_type != source_type
            or binding['canonical_source'] != original['canonical_source']
            or fresh_source.get('status') != 'resolved'
            or fresh_source.get('scope_path') != original['scope_path']
            or fresh_source.get('label_id') != original['label_id']
            or _type(fresh_source['source_type']) != source_type
            or fresh_type['wire_type'] != source_type['wire_type']
            or fresh_type['cell_width'] != source_type['cell_width']
            or fresh_type['nominal'] != source_type['nominal']
            or actual_type not in (fresh_type['type'], fresh_type['wire_type'])):
        raise Unavailable('legacy BODY projection differs from exact native inverse descriptors')
    compatibility=_legacy_type_compatibility(legacy_type,source_type,
        provenance=receipt['provenance'],body_path=body_path,scope_path=binding['scope_path'],
        label_id=binding['label_id'],physical_column=binding['physical_column'],
        evidence=binding.get('native_compatibility'),require_evidence=True)
    return dict(native_compatibility=deepcopy(compatibility),schema='native-legacy-body-projection-v1', body_path=list(body_path),
        source_column=source_column, current_column=current_column['physical_column'],
        acquisition_receipt=deepcopy(receipt), legacy_physical_type=deepcopy(legacy_type),
        source_physical_type=deepcopy(source_type), current_physical_type=deepcopy(fresh_type),
        source_correspondence_sha256=digest(source_correspondence._value),
        native_inverse_sha256=digest(current_column))


def _legacy_projection_types(binding, projection, physical_column):
    old_type = _type(binding['legacy_physical_type'])
    source_type = _type(projection['source_physical_type'])
    fresh_type = _type(projection['current_physical_type'])
    if (projection.get('schema') != 'native-legacy-body-projection-v1'
            or projection['current_column'] != physical_column
            or projection['source_column'] != binding['physical_column']
            or projection['legacy_physical_type'] != old_type
            or projection['acquisition_receipt'] != binding['binding_receipt']
            or projection['acquisition_receipt'].get('source_local') is not True
            or source_type != binding['physical_type']
            or fresh_type['wire_type'] != source_type['wire_type']
            or fresh_type['cell_width'] != source_type['cell_width']
            or fresh_type['nominal'] != source_type['nominal']):
        raise Unavailable('historical projection field lacks a matching certified native edge')
    return old_type,source_type,fresh_type


def legacy_projection_field(field, *, projection, physical_column):
    """Construct a field from an already certified native projection edge.

    This is used at the original-gold acquisition boundary, before the ordinary
    TRAIN validator. The historical physical descriptor stays as evidence;
    the declared type is taken verbatim from the native checked source, never
    rewritten by a nominal-string rule. Caller schemas are not mutated.
    """
    binding = field['native_legacy_binding']
    old_type,source_type,fresh_type=_legacy_projection_types(binding,projection,physical_column)
    storage=field.get('native_type',field['type'])
    if storage!=old_type['type']:
        raise Unavailable('historical projection field storage differs from its certified descriptor')
    compatibility=_legacy_type_compatibility(old_type,source_type,
        provenance=binding['binding_receipt']['provenance'],
        body_path=projection['body_path'],scope_path=binding['scope_path'],
        label_id=binding['label_id'],physical_column=binding['physical_column'],
        evidence=binding.get('native_compatibility'),require_evidence=True)
    if projection.get('native_compatibility')!=compatibility:
        raise Unavailable('historical projection numeric evidence differs')
    result = deepcopy(field)
    result['legacy_physical_type'] = deepcopy(old_type)
    result['type'] = source_type['type']
    result['native_type'] = fresh_type['type']
    result['native_type_projection'] = deepcopy(projection)
    return result


def canonical_bound_field_type(field):
    """Current numeric type only from this field's complete native certificate."""
    binding=field.get('native_legacy_binding')
    if not isinstance(binding,dict) or binding.get('native_compatibility') is None:
        return field['type']
    evidence=binding['native_compatibility'];receipt=binding.get('binding_receipt',{})
    old,new=_type(binding['legacy_physical_type']),_type(binding['physical_type'])
    context=evidence.get('context',{})
    if (receipt.get('source_local') is not True
            or receipt.get('program_sha256')!=context.get('program_sha256')
            or receipt.get('current_source_program_sha256')!=context.get('program_sha256')
            or receipt.get('legacy_source_program_sha256')!=context.get('program_sha256')
            or not isinstance(receipt.get('stream_sha256'),str) or len(receipt['stream_sha256'])!=64
            or field['type'] not in (old['type'],new['type'])):
        raise Unavailable('numeric field lacks exact source-local acquisition identity')
    _legacy_type_compatibility(old,new,provenance=receipt['provenance'],
        body_path=context['body_path'],scope_path=binding['scope_path'],label_id=binding['label_id'],
        physical_column=binding['physical_column'],evidence=evidence,require_evidence=True)
    linked=[f for f in receipt.get('native_compatibility',[]) if f['physical_column']==binding['physical_column']]
    identity=field.get('native_label_identity',{})
    if (len(linked)!=1 or linked[0]['evidence']!=evidence
            or field.get('source_body_column',binding['physical_column'])!=binding['physical_column']
            or identity.get('label_id',binding['label_id'])!=binding['label_id']
            or identity.get('scope_path',binding['scope_path'])!=binding['scope_path']):
        raise Unavailable('numeric field differs from its scoped native acquisition')
    projection=field.get('native_type_projection')
    storage=old['type']
    if projection is not None:
        _,_,fresh=_legacy_projection_types(binding,projection,projection['current_column'])
        if projection.get('native_compatibility')!=evidence:
            raise Unavailable('fresh numeric field lost its domain/encoding proof')
        storage=fresh['type']
    if field.get('native_type',storage)!=storage:
        raise Unavailable('numeric field native_type contradicts certified storage')
    if field['type']==old['type'] and storage!=old['type']:
        raise Unavailable('fresh numeric field retains obsolete declared storage type')
    return new['type']


def namespace_body_columns(current_export, stored_export, namespace_export, legacy_binding, body_path):
    """Compose only explicit native old-storage -> stored -> CURRENT edges."""
    current=Correspondence(current_export,program_sexp=current_export['program_sexp'],
        source_program_sexp=current_export['program_sexp'])
    stored=Correspondence(stored_export,program_sexp=stored_export['program_sexp'],
        source_program_sexp=stored_export['program_sexp'])
    bridge=Correspondence(namespace_export,program_sexp=current_export['program_sexp'],
        source_program_sexp=stored_export['program_sexp'])
    for correspondence in (current,stored):
        if correspondence._value['source_bridge_status']!='same_checked_representation':
            raise Unavailable('namespace endpoints require native SELF descriptors')
    target=bridge.body_from_source(body_path)
    own=current.body(target['body_path'])
    if legacy_binding['body_path']!=list(body_path):
        raise Unavailable('legacy storage binding belongs to another BODY')
    columns=[]
    for field in own['columns']:
        edge=bridge.body_column(target['body_path'],field['physical_column'])
        original=stored.body_column(body_path,edge['source_body_column'])
        source=edge['canonical_source']
        if (edge['scope_path']!=field['scope_path'] or edge['label_id']!=field['label_id']
                or _type(edge['physical_type'])!=_type(field['physical_type'])
                or source['scope_path']!=original['scope_path'] or source['label_id']!=original['label_id']
                or _type(source['source_type'])!=_type(original['physical_type'])):
            raise Unavailable('namespace bridge differs from its exact native endpoints')
        old=[f for f in legacy_binding['fields']
             if f['current_physical_column']==original['physical_column']
             and f['scope_path']==original['scope_path'] and f['label_id']==original['label_id']]
        if len(old)!=1 or _type(old[0]['physical_type'])!=_type(original['physical_type']):
            raise Unavailable('namespace field lacks unique authenticated storage edge')
        columns.append(dict(current=deepcopy(field),namespace=deepcopy(edge),stored=deepcopy(original),
                            storage=deepcopy(old[0])))
    if len({f['storage']['physical_column'] for f in columns})!=len(legacy_binding['fields']):
        raise Unavailable('namespace BODY does not cover the authenticated storage layout')
    return dict(body=own,columns=columns,legacy_binding=deepcopy(legacy_binding))
