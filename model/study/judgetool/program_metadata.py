"""Authenticate source names across decoded-slot and parsed-name ASTs.

The decoded AST is used only to validate an existing source-name proof. Native
headers, row paths and witnesses always come from the exact parsed replay AST.
"""
from copy import deepcopy
import json


def export_named_program(ev, program, names):
    """Return native export with preserved source names and exact replay headers.

    A logged source-name map may describe decoder-native slot identities. The
    same source parsed from text can have written names such as ``&r0``. Rebind
    only after native authentication of the old map, using canonical writer
    slots and definition identities; native attachment authenticates the result
    against the exact parsed program's stream and native relation identities.
    """
    from tables import Incomplete
    naming = names if isinstance(names, str) else json.dumps(names)
    try:
        return json.loads(ev.arclog.study_program_export_json(program, naming))
    except ValueError as error:
        if 'relation source-name map does not preserve native slot identity' not in str(error):
            raise
    # This is proof validation, never the export consumed by table binders.
    decoded = json.loads(ev.arclog.study_program_export_json(program.decode_source(), naming))
    parsed = json.loads(ev.arclog.study_program_export_json(program))
    def indexed(export):
        rows = export['definitions']['native_relations']
        result = {row['relation_slot']: row for row in rows}
        if len(result) != len(rows):
            raise Incomplete('source-name rebinding has duplicate writer relation slots')
        return result
    old, new = indexed(decoded), indexed(parsed)
    rebound = deepcopy(json.loads(naming))
    rows = rebound['relations']
    if set(old) != set(new) or set(new) != set(range(len(rows))):
        raise Incomplete('source-name rebinding changed the writer relation population')
    for slot, row in enumerate(rows):
        before, after = old[slot], new[slot]
        if (row['relation_slot'] != slot or before['definition_path'] != after['definition_path']
                or before['native_selector'] != after['native_selector']):
            raise Incomplete('source-name rebinding changed an original definition identity')
        row['native_relation'] = deepcopy(after['relation'])
    # Validates unchanged stream identity, count, exact slots and native IDs.
    # Source names/source_relation are retained verbatim from the proven map.
    return json.loads(ev.arclog.study_program_export_json(program, json.dumps(rebound)))
