"""Additive native feature payloads; no gold target or suffix is consumed.

The native metadata call independently resolves the prefix. Normalization uses
only X, available table packets and authenticated projected native flows.
"""
import json
from pathlib import Path

KEYS = ('types_frames_v1', 'canonical_clauses_v1', 'x_nf4f_v1')
MAX_NORMAL_INPUT_BYTES = 16 * 1024 * 1024


def require_feature_api(native):
    """Task-free feature dependencies, in addition to require_exporter."""
    import inspect
    from evaluator_train import acquire_train_table, acquire_train_point, acquire_det_train_point
    missing = [name for name in ('study_mutant_feature_metadata_json', 'study_feature_normalize')
               if not callable(getattr(native, name, None))]
    for function in (acquire_train_table, acquire_train_point, acquire_det_train_point):
        if 'include_projected_flows' not in inspect.signature(function).parameters:
            missing.append('Python '+function.__name__+' include_projected_flows')
    if missing:
        raise ValueError('feature exporter/runtime contract missing: '+', '.join(missing))


def _unknown(reason):
    return dict(format='native-x-nf4f-v1', version=1, algorithm='nf4f-spec-native-v1',
                scope='prefix_only', status='unsupported', entries=[], missing=[dict(reason=str(reason))])


def _rows(entry):
    return [list(v for cell in row for v in cell['value']) for row in entry['rows']]


def _validate_packet(packet, *, case, role):
    """Validate public transport; row equivalence stays typed and set-valued.

    Assignment numbers are only comparable within this source-bound own case.
    A complete zero-row relation is valid; no required contexts is unavailable.
    """
    if packet['case'] != case or role not in packet['roles'] or 'target' in packet['roles']:
        raise ValueError('normalization packet has uncertified case or role')
    if packet['complete'] is not True or packet['missing']:
        raise ValueError('normalization packet lacks complete required TRAIN coverage')
    fields = packet['fields']
    if any(f['index'] != i or not isinstance(f['type'], str) or not f['type']
           for i, f in enumerate(fields)):
        raise ValueError('normalization packet has invalid physical schema')
    required = [tuple(k) for k in packet['required']]
    if not required or len(set(required)) != len(required) or any(
            len(k) != 3 or k[1] != 1 or any(type(n) is not int or n < 0 for n in k)
            for k in required):
        raise ValueError('normalization packet has no exact required TRAIN axes')
    seen = set()
    present = set()
    for entry in packet['entries']:
        key = entry['assignment'], entry['train'], entry['model']
        if any(type(n) is not int or n < 0 for n in key) or key in seen:
            raise ValueError('normalization packet has duplicate or invalid model axes')
        seen.add(key)
        present.add((key[0], 1, key[1]))
        if entry['row_count'] != len(entry['rows']):
            raise ValueError('normalization packet row count differs')
        for row in entry['rows']:
            if len(row) != len(fields) or any(
                    not isinstance(cell.get('value'), list) or any(
                        type(n) is not int or not -(2**31) <= n < 2**31 for n in cell['value'])
                    for cell in row):
                raise ValueError('normalization packet row differs from its physical schema')
    if present != set(required):
        raise ValueError('normalization packet coverage disagrees with required axes')


def _bound_flows(record, adapter, x_meta, public_x):
    """Authenticate the tiny acquisition receipt, never reopen native payloads."""
    from evaluator import sha
    receipt = x_meta.get('projected_flows')
    if not isinstance(receipt, dict) or receipt.get('status') != 'complete':
        raise ValueError('bounded projected native flows unavailable: ' + str(
            None if receipt is None else receipt.get('reason')))
    if x_meta.get('public_fields_sha256') != sha(public_x['fields']):
        raise ValueError('public X field descriptors differ from canonical table_packet output')
    binding = adapter['input']['binding']
    axes = dict(required=public_x['required'], missing=public_x['missing'], entries=[
        [e['assignment'], 1, e['train'], e['model'], e['row_count']] for e in public_x['entries']])
    expected = dict(schema='evaluator-projected-flows-v1', version=1,
        source_sha256=sha(record), native_ref_sha256=sha(record['native']['mutant']),
        table=binding['native_table_index'], selector=binding['native_selector'],
        kept_context_sha256=sha(record['evaluation']['kept_assignments']),
        source_schema_sha256=sha(x_meta['source_schema']), projection_sha256=sha(x_meta['projection']),
        projected_fields_sha256=sha(x_meta['fields']), packet_axes_sha256=sha(axes))
    if any(receipt.get(k) != v for k, v in expected.items()):
        raise ValueError('projected native flows differ from authenticated X packet and source')
    columns = receipt['columns']
    if len(columns) != len(public_x['fields']) or any(
            c['public_column'] != i or c['source_body_column'] != x_meta['projection'][i]
            for i, c in enumerate(columns)):
        raise ValueError('projected native flow aliases differ from X physical projection')
    return [c['edges'] for c in columns]


def _normal(ev, record, adapter, x_meta, x_path, available, head):
    # Existing shared point packets hold no private source/acquisition proof.
    # Local assignment/model numbers and equal decoded Ident tokens cannot
    # authenticate a joint native context. Do not perform cross-table rules.
    if available:
        return _unknown('Available tables lack persisted file-bound acquisition/kept-context and Ident-namespace certificates')
    paths = [Path(x_path)] + [Path(p) for p in available]
    if sum(p.stat().st_size for p in paths) > MAX_NORMAL_INPUT_BYTES:
        return _unknown(f'normalization JSON input exceeds {MAX_NORMAL_INPUT_BYTES} bytes')
    public_x = json.loads(Path(x_path).read_text())
    _validate_packet(public_x, case=record['case'], role='input')
    flows = _bound_flows(record, adapter, x_meta, public_x)
    if len(x_meta['fields']) != len(public_x['fields']) or len(x_meta['projection']) != len(public_x['fields']):
        return _unknown('X projection/schema width differs from validated public X')
    x = dict(x_meta, entries=[dict(e, example_index=e['train']) for e in public_x['entries']])
    types = [field['type'] for field in x['fields']]
    grouped = {}
    for entry in x['entries']:
        grouped.setdefault(entry['assignment'], []).append(entry)
    result = []
    for assignment, entries in sorted(grouped.items()):
        entries = sorted(entries, key=lambda e: (e['example_index'], e['model']))
        if len({e['example_index'] for e in entries}) != len(entries):
            result.extend(dict(assignment=assignment, train=e['example_index'], model=e['model'],
                               status='unsupported', factors=[], removed_columns=[],
                               reason='X has multiple model rows without certified cross-table model alignment')
                          for e in entries)
            continue
        context = []  # Cross-table normalization is refused above until certified.
        table_input = dict(types=types, columns=[f.get('field_name', f.get('name', f'c{i}'))
                            for i, f in enumerate(x['fields'])],
                           rows=[_rows(e) for e in entries], head=head, flows=flows)
        normal = json.loads(ev.arclog.study_feature_normalize(
            json.dumps(table_input), earlier=json.dumps(context)))
        for position, entry in enumerate(entries):
            factors = []
            for factor_id, factor in enumerate(normal.get('factors', [])):
                columns = factor['columns']
                factor_position = position
                for keep, _total in factor['masks']:
                    if factor_position not in keep:
                        factor_position = None
                        break
                    factor_position = keep.index(factor_position)
                wanted = (set(map(tuple, factor['rows'][factor_position]))
                          if factor_position is not None else set())
                projected = {}
                for row in entry['rows']:
                    cells = [row[c] for c in columns]
                    key = tuple(v for cell in cells for v in cell['value'])
                    if key in wanted:
                        old = projected.setdefault(key, cells)
                        if old != cells:
                            raise ValueError('normal factor has ambiguous native geometry for one value row')
                if set(projected) != wanted:
                    raise ValueError('normal factor rows cannot be mapped to original X cells')
                factors.append(dict(id=factor_id, x_columns=columns,
                                    fields=[public_x['fields'][c] for c in columns],
                                    rows=[projected[key] for key in sorted(projected)], masks=factor['masks']))
            result.append(dict(assignment=assignment, train=entry['example_index'], model=entry['model'],
                               status='complete' if normal['status'] == 'determined' else 'unsupported',
                               factors=factors,
                               removed_columns=[dict(x_column=c, reason=rule['rule'], witness=rule)
                                   for rule in normal.get('removed', [])
                                   for c in ([rule['column']] if 'column' in rule else rule.get('columns', []))],
                               context_rules=[rule for rule in normal.get('removed', [])
                                              if 'column' not in rule and 'columns' not in rule],
                               column_mapping=[dict(x_column=i, field=field) for i, field in enumerate(public_x['fields'])],
                               native_status=normal['status'], reason=normal.get('reason')))
    missing = [dict(assignment=e['assignment'], train=e['train'], model=e['model'],
                    reason=e.get('reason')) for e in result if e['status'] != 'complete']
    return dict(format='native-x-nf4f-v1', version=1, algorithm='nf4f-spec-native-v1',
                scope='prefix_only', status='complete' if not missing else 'partial',
                entries=result, missing=missing, multiplicity='native typed row sets; original entry axes retained')


def payload(ev, record, adapter, x_meta, x_path, available, program):
    require_feature_api(ev.arclog)
    native = json.loads(ev.arclog.study_mutant_feature_metadata_json(program))
    try:
        normal = _normal(ev, record, adapter, x_meta, x_path, available, native['normal_head'])
    except (ValueError, KeyError, TypeError) as error:
        normal = _unknown(error)
    native['x_nf4f_v1'] = normal
    return {key: native[key] for key in KEYS}


def point_payload(pair):
    result = {}
    for key in ('types_frames_v1', 'canonical_clauses_v1'):
        value = dict(pair[key])
        value.pop('candidate', None)
        value['scope'] = 'prefix_only'
        if 'prefix' not in value:
            value.update(status='unsupported', missing=[dict(reason='Independent prefix export unavailable')])
            result[key] = value
            continue
        prefix_paths = {tuple(c['path']) for c in value.get('prefix', [])}
        value['missing'] = [m for m in value.get('missing', [])
                            if tuple(m.get('clause_path', m.get('path', []))) in prefix_paths]
        if 'prefix' in value:
            value['status'] = 'complete' if all(c['status'] == 'complete' for c in value['prefix']) else 'partial'
        if key == 'types_frames_v1':
            # Frames of the candidate are never published as prefix evidence.
            roots = {item.get('frame_id') for clause in value.get('prefix', [])
                     for item in clause.get('labels', []) + clause.get('sites', [])}
            frames = {f['id']: f for f in value.get('frames', [])}
            pending = list(roots - {None})
            while pending:
                frame = frames.get(pending.pop())
                for parent in (() if frame is None else frame.get('parents', [])):
                    if parent not in roots:
                        roots.add(parent); pending.append(parent)
            value['frames'] = [f for f in value.get('frames', []) if f['id'] in roots]
        result[key] = value
    result['x_nf4f_v1'] = dict(format='native-x-nf4f-context-v1', version=1,
                               scope='prefix_only', status='complete',
                               meaning='Candidate normal forms are stored per pair.')
    return result
