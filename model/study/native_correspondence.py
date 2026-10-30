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
