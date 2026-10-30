"""Additive, receipt-bound DET header-union metadata. No evaluation or rows read.

Import MetadataProducer here to opt into DET support. Existing hashed producer,
reader mapper, renderer and projector files are not changed. Without a transport
receipt the canonical producer still refuses DET. The transport is produced by
mech3.det_receipt.receipt(record, exports, RAW bindings); never replace those raw
bindings with this module's selected target bindings before calling that mapper.
"""
from __future__ import annotations
import ast
import copy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

if __package__:
    from . import nonrender_metadata as base
    from .definition_binding import definition_node
else:
    import nonrender_metadata as base
    from definition_binding import definition_node


class InvalidDetProjection(ValueError):
    pass


def require(value, message):
    if not value:
        raise InvalidDetProjection(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@lru_cache(maxsize=2)
def _receipt_produce(source):
    """Reuse the canonical produce body, replacing only its explicit DET refusal.

    Fail if that known guard changes. The replacement validates the supplied
    transport; it never makes a raw-all-BODY DET target a fallback.
    """
    path = Path(base.__file__).resolve()
    tree = ast.parse(source.decode(), str(path))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MetadataProducer')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'produce')
    expected = ast.dump(ast.parse("ctx.body['kind']=='Det'", mode='eval').body)
    guards = [n for n in fn.body if isinstance(n, ast.If) and ast.dump(n.test) == expected]
    require(len(guards) == 1, 'canonical DET guard changed')
    guard = guards[0]
    require(len(guard.body) == 1 and isinstance(guard.body[0], ast.Raise), 'canonical DET refusal changed')
    exception = guard.body[0].exc
    require(isinstance(exception, ast.Call) and isinstance(exception.func, ast.Name)
            and exception.func.id == 'UnsupportedProjection', 'canonical DET exception changed')
    guard.body = ast.parse('self._validate_det_context(ctx, r, base)').body
    ast.fix_missing_locations(fn)
    namespace = dict(base.MetadataProducer.produce.__globals__)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['produce']


def _check_mapper(mapper):
    require(mapper.get('schema') == 'mech3-reader-mapper-source-v1', 'mapper source receipt missing')
    for path_key, hash_key in (('source_path', 'source_sha256'), ('adapter_path', 'adapter_sha256')):
        path = Path(mapper[path_key])
        require(hashlib.sha256(path.read_bytes()).hexdigest() == mapper[hash_key], 'mapper source bytes changed')


class MetadataProducer(base.MetadataProducer):
    """Canonical producer plus explicit mech3 DET transport, metadata only."""
    def produce(self, source_record, *, native_base=None, det_projection=None, feature_only=False):
        require(type(feature_only) is bool, 'feature_only must be boolean')
        if det_projection is None:
            require(not feature_only, 'feature-only DET metadata requires certified reader transport')
            return super().produce(source_record, native_base=native_base)
        require(not hasattr(self, '_active_det'), 'one producer cannot process concurrent DET receipts')
        policy = self.policy
        canonical_document = policy['Document']
        producer = self

        class ReceiptDocument(canonical_document):
            def callable_atom(self, schema, name, definition=None):
                if producer._feature_only and self.body['kind'] == 'Det' and name == '&X' and definition is None:
                    return None
                return super().callable_atom(schema, name, definition)

            def target_projection(self, reader, schema, decoded, *, body_side=None):
                if self.body['kind'] != 'Det':
                    return super().target_projection(reader, schema, decoded, body_side=body_side)
                return producer._project_det(self, reader, schema, decoded, body_side=body_side)

        self._active_det = copy.deepcopy(det_projection)
        self._feature_only = feature_only
        self._det_source = copy.deepcopy(source_record)
        self.policy = dict(policy, Document=ReceiptDocument)
        try:
            value = _receipt_produce(Path(base.__file__).read_bytes())(self, source_record, native_base=native_base)
            require(value['bindings']['gold']['kind'] == 'Det', 'DET receipt supplied for another kind')
            value['det_projection_receipt'] = copy.deepcopy(self._active_det)
            for side, binding in value['bindings'].items():
                own = self._active_det['sides'][side]
                binding['target_kind'] = 'det_reader_named_header_union'
                binding['det_projection_receipt'] = dict(schema='judge3-det-binding-receipt-v1',
                    source_sha256=self._active_det['source_sha256'], side=side,
                    program_sha256=own['program_sha256'], export_sha256=own['export_sha256'],
                    body_path=binding['body_path'], owner_path=binding['owner_path'],
                    native_ref_sha256=digest(binding['native_ref']), native_selector=binding['native_selector'],
                    source_body_schema_sha256=digest(binding['source_body_schema']),
                    projected_schema_sha256=digest(binding['projected_schema']),
                    callable_template_sha256=digest(binding['callable_template']),
                    transport_sha256=digest(self._active_det),
                    projection_indices=[f['source_body_column'] for f in binding['projected_schema']],
                    mapper=self._active_det['mapper'],
                    policy='union of actually reader-named native header identities; aliases retained')
                if feature_only:
                    binding['callable'] = False
                    binding['det_projection_receipt'].update(
                        scope='TRAIN_features_only_noncallable', callable=False)
            if feature_only:
                value['input']['callable'] = False
                value['scope'] = 'TRAIN_features_only_noncallable'
            value['reader_projection'] = copy.deepcopy(self._active_det['reader_projection'])
            value['policies'] = list(value['policies']) + [dict(path=str(Path(__file__).resolve()),
                sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                mode='canonical producer with validated reader-header union transport')]
            return value
        finally:
            self.policy = policy
            del self._active_det
            del self._feature_only
            del self._det_source

    def _validate_det_context(self, ctx, record, native_base):
        receipt = self._active_det
        require(receipt.get('schema') == 'mech3-det-header-projection-v1' and receipt.get('complete') is True,
                'complete DET header projection receipt required')
        require(receipt.get('source_sha256') == digest(self._det_source), 'DET receipt source differs')
        require(receipt.get('body_path') == record['point'], 'DET receipt point differs')
        _check_mapper(receipt.get('mapper', {}))
        readers = receipt.get('reader_projection', {})
        require(readers.get('schema') == 'mech3-reader-projection-v1' and readers.get('complete') is True,
                'complete per-reader transport required')
        require(readers.get('source_sha256') == receipt['source_sha256'], 'reader receipt source differs')
        wanted = {tuple(tuple(p) for p in f['row_path']) for r in readers['readers'] for f in r['fields']}
        for side, export in (('gold', ctx.gexport), ('mutant', ctx.mexport)):
            own = receipt['sides'][side]
            require(own['program_sha256'] == digest(record['programs'][side]), 'DET program differs: ' + side)
            require(own['export_sha256'] == digest(export), 'DET native export differs: ' + side)
            require(export['parts'].get('definitions_readers') == 'complete', 'reader inventory incomplete: ' + side)
            view = [v for v in export['body_views'] if v['body_path'] == record['point']]
            require(len(view) == 1 and view[0]['kind'] == 'Det', 'exact DET body view missing: ' + side)
            raw = own['raw_binding']
            require(raw['body_path'] == record['point'] and raw['owner_path'] == view[0]['owner_path'],
                    'raw BODY binding point/owner differs: ' + side)
            require(raw['native_selector'] == view[0]['native_table_selector'], 'raw BODY selector differs: ' + side)
            owner = next(n for n in export['nodes'] if n['path'] == view[0]['owner_path'])
            definitions = [d for d in export['definitions']['native_relations'] if d['relation'] == owner['data']['defines']]
            require(len(definitions) == 1 and definitions[0].get('column_witness_status') == 'complete',
                    'complete native DET declared header unavailable: ' + side)
            headers = definitions[0]['column_witnesses']
            columns = own['columns']
            paths = [self.policy['column_key'](c['row_path']) for c in columns]
            require(len(paths) == len(set(paths)) and set(paths) == wanted,
                    'DET target is not the exact reader-named header union: ' + side)
            physical = [c['header_physical_column'] for c in columns]
            require(physical == sorted(physical) and len(set(physical)) == len(physical),
                    'DET fields must retain distinct native header order: ' + side)
            for column in columns:
                witness = column['native_header']
                require(witness in headers and witness['physical_column'] == column['header_physical_column']
                        and witness['row_path'] == column['row_path'] and witness['type'] == column['type'],
                        'DET header identity differs from native export: ' + side)
                require(column.get('reader_paths'), 'selected DET header lacks an actual reader')
            if not columns:
                proof = receipt.get('no_readers_proof') or {}
                require(proof.get('complete') is True and proof.get('exports_complete') is True
                        and proof.get('count') == 0 and readers['readers'] == [], 'empty DET lacks no-reader proof')
                node = definition_node(export, definitions[0])
                require(not any(r['resolution'].get('kind') == 'graph_node' and r['resolution'].get('node') == node
                                for r in export['definitions']['readers']), 'empty DET still has native readers')

    def _project_det(self, ctx, reader, schema, decoded, *, body_side=None):
        side=ctx._body_side(reader,body_side)
        export = ctx.gexport if side == 'gold' else ctx.mexport
        view = next(v for v in export['body_views'] if v['body_path'] == ctx.r['point'])
        own = self._active_det['sides'][side]
        raw = own['raw_binding']['source_body_schema']
        require(len(raw) == len(schema), 'native BODY width differs from transport: ' + side)
        for a, b in zip(raw, schema):
            require(all(a.get(k) == b.get(k) for k in ('index', 'type', 'slot', 'ast_label_id', 'frame')),
                    'native BODY schema differs from transport: ' + side)
        projected = []
        for index, column in enumerate(own['columns']):
            source_index = column['source_body_column']
            witness = column['native_header']
            if source_index is None:
                cert = column.get('unit_projection_certificate') or {}
                require(column['type'] == 'Unit' and witness.get('status') == 'declared_without_local_label'
                        and witness.get('proof') in ('declared_layout', 'resolved_row_path'), 'uncertified implicit Unit')
                require(cert.get('schema') == 'mech3-native-unit-projection-v1'
                        and cert.get('native_header') == witness and cert.get('source_body_column') is None
                        and cert.get('proof') == witness['proof']
                        and cert.get('projection_helper') == 'judge2/render2/body.py:project_entries', 'Unit certificate differs')
                source = dict(type='Unit', frame='', name=witness.get('native_name') or '', label='', slot=-1,
                    native_label_identity=dict(kind='implicit_unit', label_id=None, certificate=cert))
            else:
                require(type(source_index) is int and 0 <= source_index < len(schema), 'BODY index outside schema')
                source = copy.deepcopy(schema[source_index])
                proof = column.get('scoped_binding')
                require(proof in witness.get('bindings', []) and proof.get('status') == 'resolved'
                        and proof['body_path'] == ctx.r['point'], 'header lacks resolved changed-BODY binding')
                identity = source['native_label_identity']
                require(proof['scope_path'] == identity['scope_path'] and proof['label_id'] == identity['label_id']
                        and proof['field_type'] == source['type'], 'header/BODY scoped label differs')
            path = copy.deepcopy(column['row_path'])
            projected.append(dict(source, index=index, type=column['type'], source_body_column=source_index,
                callable_row_path=path, display_name=self.policy['column_text'](path, 'role'),
                source_label='@column:' + str(index), source_projection=dict(role='det_reader_header',
                    header_physical_column=column['header_physical_column'], native_header=witness,
                    scoped_binding=column.get('scoped_binding'), unit_projection_certificate=column.get('unit_projection_certificate'))))
        indices = [c['source_body_column'] for c in projected]
        result = {e: dict(entry, rows=self.policy['project_entries'](dict(entries=[dict(entry, choice=None)]), indices)[0]['rows'])
                  for e, entry in decoded.items()}
        return projected, result, view

    def project_entries(self, binding, entries):
        """Project supplied stored entries with the one shared projector, no read."""
        require(binding.get('kind') == 'Det' and binding.get('det_projection_receipt'), 'receipt-bound DET binding required')
        receipt = binding['det_projection_receipt']
        require(receipt.get('schema') == 'judge3-det-binding-receipt-v1'
                and receipt['projected_schema_sha256'] == digest(binding['projected_schema'])
                and receipt['source_body_schema_sha256'] == digest(binding['source_body_schema'])
                and receipt['callable_template_sha256'] == digest(binding['callable_template']),
                'DET binding differs from its projection receipt')
        return self.policy['project_entries'](dict(entries=entries),
            [field['source_body_column'] for field in binding['projected_schema']])
