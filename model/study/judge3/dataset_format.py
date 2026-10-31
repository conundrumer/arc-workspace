"""Judge-facing JSON, independent of execution and comparison semantics.

The evaluator supplies authenticated TRAIN entries. This module only validates
and serializes them; it never selects assignments, projects rows or compares
component identities. Private execution records are never copied wholesale.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import uuid

FORMAT = 'judge-dataset-v1'


def write_json(path, value, *, compact=False, parent_ready=False):
    if type(compact) is not bool:
        raise ValueError("compact must be boolean")
    path = Path(path)
    if not parent_ready:path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as stream:
            options = dict(ensure_ascii=False, allow_nan=False, indent=None if compact else 2)
            if compact:
                options['separators'] = (',', ':')
            json.dump(value, stream, **options)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def ordered_rows(rows):
    """Canonical public row order over complete native value/frame cells."""
    return sorted(rows, key=lambda row: json.dumps(row, ensure_ascii=False,
        allow_nan=False, sort_keys=True, separators=(',', ':')))


def table_packet(acquired, *, table_id, source_name, case, roles,
                 callable_atom=None, copy_rows=True, sort_rows=False):
    """Package evaluator_train.acquire_train_table output, without truncation.

    copy_rows=False validates the same cells/axes but shares read-only acquired
    rows through the synchronous writer; the default retains independent cells.
    sort_rows=True orders full typed cells after validation; repeated rows and
    all entry/assignment/model axes remain intact. Shared sorting is local to
    this call and retains the exact source row object alongside its result.
    Empty rows are real empty relations; missing contexts remain explicit.
    A native TASK entry must have been broadcast by the evaluator, not here.
    """
    if type(copy_rows) is not bool:
        raise ValueError("copy_rows must be boolean")
    if type(sort_rows) is not bool:
        raise ValueError("sort_rows must be boolean")
    ordered = {}
    fields = []
    for index, field in enumerate(acquired['fields']):
        name = field.get('field_name', field.get('display_name', field.get('name')))
        if not isinstance(name, str) or not name or not isinstance(field.get('type'), str):
            raise ValueError('each physical field needs its source name and native type')
        fields.append(dict(index=index, name=name, type=field['type'],
                           **{k: deepcopy(field[k]) for k in ('frame', 'callable_row_path') if k in field}))
    entries = []
    identities = set()
    for item in acquired['entries']:
        if item['example_kind'] != 1:
            raise ValueError('public table accepts only evaluator-selected TRAIN entries')
        assignment, example, model = item['assignment'], item['example_index'], item['model']
        if any(type(x) is not int or x < 0 for x in (assignment, example, model)):
            raise ValueError('assignment, train index and local model must be nonnegative integers')
        identity = assignment, example, model
        if identity in identities:
            raise ValueError('duplicate train model entry')
        identities.add(identity)
        rows = []
        for row in item['rows']:
            if len(row) != len(fields):
                raise ValueError('row width differs from physical schema')
            for cell in row:
                if not isinstance(cell, dict) or not isinstance(cell.get('value'), list):
                    raise ValueError('cells must retain the native decoded value object')
            # Keep native extent/status evidence, rather than infer a frame.
            rows.append(deepcopy(row) if copy_rows else row)
        if sort_rows:
            key = id(item['rows'])
            cached = ordered.get(key) if not copy_rows else None
            if cached is not None and cached[0] is item['rows']:
                rows = cached[1]
            else:
                rows = ordered_rows(rows)
                if not copy_rows:
                    ordered[key] = (item['rows'], rows)
        entries.append(dict(assignment=assignment, train=example, model=model,
                            row_count=len(rows), rows=rows))
    required = [list(k) for k in acquired['required']]
    missing = [list(k) for k in acquired['missing']]
    if any(len(k) != 3 or k[1] != 1 for k in required + missing):
        raise ValueError('public context axes must be [assignment, 1, train_index]')
    present = {(e['assignment'], 1, e['train']) for e in entries}
    expected = {tuple(k) for k in required}
    if present - expected or set(map(tuple, missing)) != expected - present:
        raise ValueError('required/missing contexts disagree with supplied entries')
    return dict(format=FORMAT, kind='table', id=table_id, source_name=source_name,
                case=case, roles=list(roles), callable_atom=callable_atom,
                fields=fields, entries=entries, required=required, missing=missing,
                complete=not missing, row_count=sum(e['row_count'] for e in entries))


def result_packet(checked, *, command, pair_id, table_path=None):
    """Allowlist judge information; receipts stay in the private checked record."""
    if command not in ('run', 'check', 'alternative'):
        raise ValueError('unsupported command')
    result = dict(format=FORMAT, kind='result', command=command, pair_id=pair_id,
                  engine=checked.get('engine'), reason=checked.get('reason'),
                  table=table_path, comparisons=[])
    if command != 'run':
        result['outcome'] = checked.get('outcome', 'unknown')
    for comparison in checked.get('comparisons', []):
        value = comparison['comparison']
        result['comparisons'].append(dict(target_id=comparison['target_id'],
            **({'target_source': comparison['target_source']} if 'target_source' in comparison else {}),
            **{k: deepcopy(value[k]) for k in ('status', 'reason', 'columns', 'differences') if k in value}))
    if not result['reason']:
        outcome=result.get('outcome')
        if outcome in ('recovery verified','partial source verified'):
            matched=next((c['target_id'] for c in result['comparisons'] if c['status']=='equal'),None)
            result['reason']=f'The clause equals target {matched} on every train and test input; its row-source check passed.'
        elif outcome=='continuation passed':
            result['reason']='Nonempty on every train input, unequal to X and every available table.'
        elif command=='run':
            result['reason']='Exploratory run; the complete train result is written as data.'
    return result


def table_summary(table, path):
    """Small index metadata, copied from the complete table without its rows."""
    if table.get('format')!=FORMAT or table.get('kind')!='table':
        raise ValueError('expected a public table packet')
    return dict(id=table['id'],source_name=table['source_name'],case=table['case'],
                roles=deepcopy(table['roles']),path=path,fields=deepcopy(table['fields']),
                callable_atom=table['callable_atom'],row_count=table['row_count'],
                complete=table['complete'],missing=deepcopy(table['missing']),
                entry_counts=[{k:entry[k] for k in ('assignment','train','model','row_count')}
                              for entry in table['entries']])


def pair_packet(*, pair_id, task, case, change, tables, comparisons='comparisons.json',
                readers='readers.json', train='train.json', programs=None, libraries=None):
    """Index ordinary relative files, never private context paths or test data."""
    paths = [comparisons, readers, train] + [t['path'] for t in tables]
    paths += list((programs or {}).values())
    if libraries is not None:
        paths.append(libraries)
    if any(Path(p).is_absolute() or '..' in Path(p).parts for p in paths):
        raise ValueError('public dataset paths must stay relative to the pair directory')
    return dict(format=FORMAT, kind='pair', pair_id=pair_id, task=task, case=case,
                change=deepcopy(change), tables=deepcopy(tables), comparisons=comparisons,
                readers=readers, train=train, programs=programs or {}, libraries=libraries)
