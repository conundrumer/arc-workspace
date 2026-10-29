"""Stored target scope and case receipts; no execution, equality or projection policy."""
from pathlib import Path


def matches(tables, index, selector):
    return all(str(tables[k][index]) == str(value) for k, value in selector.items()
               if k in ('form', 'point', 'relation', 'fact'))


def definition_after(definition, body, export):
    path=tuple(definition['definition_path']); owner=tuple(body['owner_path'])
    relation=definition['relation']
    if path[:len(owner)]==owner:
        parts=relation.get('path',[])
        if len(parts)==1 and 'port' in parts[0]:
            inputs=[v for v in export['body_views'] if v['owner_path']==list(owner)
                    and v['input_port']==parts[0]['port']]
            if len(inputs)==1:
                return tuple(inputs[0]['body_path']) > tuple(body['body_path'])
        return True  # produced relation, after its defining body/input
    return path > owner


def same_case_after(tables, index, body, export):
    """Use native-export source identities within this program only.

    Body sites precede the relation they produce. Numeric PointKind codes are
    categories, not a temporal ordering. Unknown provenance is never guessed.
    """
    if tables['point'][index] == 2:
        return False
    if tables['point'][index] == 1:
        views = [v for v in export['body_views'] if matches(tables, index, v['native_table_selector'])]
        if len(views) == 1:
            return tuple(views[0]['body_path']) > tuple(body['body_path'])
        return None
    definitions = [d for d in export['definitions']['native_relations']
                   if matches(tables, index, d['native_selector'])]
    if definitions:
        paths = [tuple(d['definition_path']) for d in definitions if d['definition_path']]
        if not paths:
            return None
        return any(definition_after(d,body,export) for d in definitions)
    return None


def fields(reader, table, definition=None):
    """Native field identity plus declared source row paths when exported."""
    witnesses = {w['physical_column']: w for w in definition['column_witnesses']} if definition else {}
    return [dict(physical_index=c['index'], field_name=c['name'], native_label=c['label'],
                 type=c['type'], frame=c['frame'], native_slot=c['slot'],
                 row_path=witnesses.get(c['index'], {}).get('row_path')) for c in reader.schema(table)]
