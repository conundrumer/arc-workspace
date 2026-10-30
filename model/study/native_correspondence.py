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


def bind_legacy_body_schema(current, current_program, *, legacy_export,
        legacy_stream, legacy_schema, body_path, legacy_cell_width, provenance):
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
                    != (new_source['scope_path'], new_source['label_id'], new_source['name'])
                or old_type['wire_type'] != new_type['wire_type']
                or old_type['cell_width'] != new_type['cell_width']
                or old_type['nominal'] != new_type['nominal']
                or (old_type['type'] != new_type['type'] and not old_type['nominal'])):
            raise Unavailable('legacy/current native BODY scoped type or encoding differs')
        fields.append(dict(physical_column=index, current_physical_column=linked['physical_column'],
            scope_path=list(identity[0]), label_id=identity[1],
            legacy_physical_type=deepcopy(old_type), physical_type=deepcopy(new_type),
            canonical_source=deepcopy(new_source)))
    if sum(f['legacy_physical_type']['cell_width'] for f in fields) != legacy_cell_width:
        raise Unavailable('legacy native BODY packed width differs from its descriptor')
    return dict(schema='native-legacy-body-binding-v1', body_path=list(body_path),
        fields=sorted(fields, key=lambda f: f['physical_column']),
        receipt=dict(provenance=deepcopy(provenance),
            program_sha256=hashlib.sha256(current_program.sexp().encode()).hexdigest(),
            stream_sha256=digest(legacy_stream),
            legacy_correspondence_sha256=digest(old._value),
            current_correspondence_sha256=digest(current._value),
            mapping='native scoped LabelId under exact program and full-stream equality',
            nominal_strings='retained verbatim; never parsed or normalized', rows_checked=False))
