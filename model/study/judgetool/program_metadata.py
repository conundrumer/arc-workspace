"""Authenticate source names and types across decoded and parsed native ASTs.

Decoded metadata authenticates source-name proofs and nominal type identities.
Physical headers, row paths and witnesses retain the exact parsed replay AST.
"""
from copy import deepcopy
import json


def _indexed(export):
    from tables import Incomplete
    rows = export['definitions']['native_relations']
    result = {row['relation_slot']: row for row in rows}
    if len(result) != len(rows):
        raise Incomplete('native export has duplicate writer relation slots')
    return result


def type_identity(ev, record, name):
    """Native decoded identity for a parsed nominal Pose type, never a regex.

    Canonical-form bytes include native names and column layouts too. Pair the
    exact parsed/decode_source exports by declaration identity and physical
    header index; retain the whole native decoded assembly/key type unchanged.
    An unproven nominal correspondence is unavailable, never a type mismatch.
    """
    if not name.startswith('Pose(') or 'Written(' not in name:
        return name, None
    from evaluator import sha
    from tables import Incomplete
    for text in dict.fromkeys(record[k] for k in ('gold_sexp','mutant_sexp') if record.get(k)):
        key=('native-nominal-type-identity',record['task'],sha(text),sha(ev.receipt))
        if key not in ev.target_cache:
            program=ev.arclog.StudyProgram.from_sexp(text,ev.settings)
            parsed=json.loads(ev.arclog.study_program_export_json(program))
            decoded=json.loads(ev.arclog.study_program_export_json(program.decode_source()))
            old,new=_indexed(decoded),_indexed(parsed)
            if set(old)!=set(new):
                raise Incomplete('nominal type decoding changed native declaration population')
            aliases={}
            proof=dict(source_program_sha256=sha(text),parsed_export_sha256=sha(parsed),
                       decoded_export_sha256=sha(decoded),
                       mapping='native decode_source; exact declaration and physical header index')
            for slot,before in old.items():
                after=new[slot]
                if (before['definition_path']!=after['definition_path']
                        or before['native_selector']!=after['native_selector']):
                    raise Incomplete('nominal type decoding changed original declaration identity')
                a,b=before.get('column_witnesses',[]),after.get('column_witnesses',[])
                if (before.get('column_witness_status')!='complete'
                        or after.get('column_witness_status')!='complete'):
                    continue
                if len(a)!=len(b) or any(x['physical_column']!=y['physical_column'] for x,y in zip(a,b)):
                    raise Incomplete('nominal type decoding changed physical header layout')
                for x,y in zip(a,b):
                    if not y['type'].startswith('Pose('):continue
                    if not x['type'].startswith('Pose('):
                        raise Incomplete('nominal type decoding changed physical field kind')
                    if y['type'] in aliases and aliases[y['type']]!=x['type']:
                        raise Incomplete('nominal type has ambiguous native decoded identity')
                    aliases[y['type']]=x['type']
            ev.target_cache[key]=(aliases,proof)
        aliases,proof=ev.target_cache[key]
        if name in aliases:
            return aliases[name],proof
    raise Incomplete('Pose type has no authenticated native decoded source identity')


def typed_fields(ev, record, fields):
    """Canonical nominal identity plus verbatim physical native type evidence."""
    result=[]
    for original in fields:
        field=dict(original)
        identity,proof=type_identity(ev,record,field['type'])
        if identity!=field['type']:
            field.update(native_type=field['type'],type=identity,type_identity=proof)
        result.append(field)
    return result


def bind_native_column_names(ev, record, definition, schema, *, artifact, table):
    """Bind absent physical names to the exact replay's certified layout.

    Rigid outputs have native declared-layout row paths but the AST exporter
    can have no node-level column names. The table packer supplies physical
    names. Read those actual names; never derive cN or invent source names.
    Authored/exported names remain exact assertions and are never replaced.
    """
    from evaluator import sha
    from tables import Incomplete
    witnesses=definition['column_witnesses']
    if len(witnesses)!=len(schema):return witnesses
    bound=[]
    for witness,column in zip(witnesses,schema):
        if witness.get('native_name') is not None:
            bound.append(witness);continue
        if (definition.get('column_witness_status')!='complete'
                or witness.get('proof')!='declared_layout'
                or witness.get('status') not in ('resolved','declared_without_local_label')
                or witness.get('definition_path')!=definition['definition_path']
                or witness.get('relation')!=definition['relation']
                or not witness.get('row_path')
                or witness.get('physical_column')!=column['index']
                or witness.get('logical_slot')!=column['slot']
                or not isinstance(column.get('name'),str) or not column['name']
                or type_identity(ev,record,witness['type'])[0]!=type_identity(ev,record,column['type'])[0]):
            raise Incomplete('anonymous native column lacks an exact declared-layout replay binding')
        bound.append(dict(witness,native_name=column['name'],exported_native_name=None,
            native_name_binding=dict(source='exact native replay schema',artifact=artifact,table=table,
                physical_column=column['index'],logical_slot=column['slot'],
                row_path=deepcopy(witness['row_path']),original_witness_sha256=sha(witness))))
    return bound


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
    old, new = _indexed(decoded), _indexed(parsed)
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
