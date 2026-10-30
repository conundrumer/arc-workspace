"""Lossless CaseTables reader: live objects, raw buffers or base64 payloads.

Status 0/no_grid with [-1,-1] is authoritative evidence, 1/resolved requires
positive dimensions, and 2/unresolved remains readable metadata. Missing status
requires explicit missing_extent_status='infer' (legacy_status alias supported):
Offset is no_grid, positive extent runs resolve, all other cases are unresolved.
No Position/Box no_grid inference is made from missing dimensions or frames.
Entry projection-stop rejection is explicit; raw projection/marker buffers are
retained in parts for specialized readers, never normalized into full rows.
"""
import base64
import struct
import sys
from collections import defaultdict

PARTS = ('tables', 'entries', 'assigned', 'projections', 'projection_rows', 'flows', 'copies')
SCHEMA = "arclog-native-tables-v1"

FORMATS = {'uint8': 'B', 'int32': 'i', 'uint32': 'I', 'int64': 'q', 'uint64': 'Q'}
WIDE = {'Box', 'Position', 'Offset'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def blob(value):
    require(isinstance(value, dict) and set(value) == {'base64'}, 'expected native base64')
    return base64.b64decode(value['base64'], validate=True)


def width(types):
    return sum(4 if ty in WIDE else 1 for ty in types)


class Native:
    def __init__(self, payload, *, missing_extent_status='reject', legacy_status=None):
        # The alias keeps the explicitly agreed renderer compatibility boundary.
        if legacy_status is not None:
            require(missing_extent_status == 'reject' or missing_extent_status == legacy_status,
                    'conflicting legacy status policies')
            missing_extent_status = legacy_status
        require(missing_extent_status in ('reject', 'infer'), 'unknown missing extent status policy')
        self.missing_extent_status = missing_extent_status
        if not isinstance(payload, dict):
            payload = dict(dtypes=payload.dtypes, values=payload.values,
                           **{p: getattr(payload, p) for p in PARTS})
        self.parts = {}
        for part in PARTS:
            columns = {}
            for key, value in payload[part].items():
                if isinstance(value, (dict, bytes, bytearray, memoryview)):
                    if 'dtypes' not in payload and isinstance(value, memoryview):
                        require(value.format in FORMATS.values(), 'unknown decoded native dtype')
                    else:
                        dtype = payload['dtypes'][part + '.' + key]
                        require(dtype in FORMATS, 'unknown native dtype: ' + dtype)
                        raw = blob(value) if isinstance(value, dict) else memoryview(value).cast('B')
                        fmt = '<' + FORMATS[dtype]
                        require(len(raw) % struct.calcsize(fmt) == 0, 'partial native scalar')
                        value = memoryview(raw).cast(FORMATS[dtype]) if sys.byteorder == 'little' else [r[0] for r in struct.iter_unpack(fmt, raw)]
                columns[key] = value
            lengths = {len(v) for v in columns.values()}
            require(len(lengths) <= 1, 'native column lengths differ: ' + part)
            self.parts[part] = columns
        raw = blob(payload['values']) if isinstance(payload['values'], dict) else payload['values']
        require(len(raw) % 4 == 0, 'partial native value')
        self.values = memoryview(raw).cast('B').cast('i')
        self.tables = self.parts['tables']
        self.entries = self.parts['entries']
        self.bytable = defaultdict(list)
        self.assigned = defaultdict(list)
        self.schemas = {}
        for e, table in enumerate(self.entries['table']):
            require(0 <= table < len(self.tables['width']), 'entry table outside native tables')
            self.bytable[table].append(e)
        a = self.parts['assigned']
        for i, entry in enumerate(a['entry']):
            require(0 <= entry < len(self.entries['table']), 'assignment entry outside native entries')
            self.assigned[entry].append(i)

    def validate_run(self, offset, count, w):
        require(offset >= 0 and count >= 0 and w >= 0 and offset + count * w <= len(self.values),
                'native run outside values buffer')

    def run(self, offset, count, w):
        self.validate_run(offset, count, w)
        return [list(self.values[offset + j*w:offset + (j+1)*w]) for j in range(count)]

    def schema(self, t):
        if t in self.schemas:
            return self.schemas[t]
        ts = self.tables
        types = ts['column_types'][t]
        require(width(types) == ts['width'][t], 'typed width differs from native width')
        fields = ('column_names', 'column_types', 'column_frames', 'column_slots',
                  'column_labels', 'column_source_labels')
        require(all(len(ts[f][t]) == len(types) for f in fields), 'incomplete native schema')
        result = [dict(index=i, name=ts['column_names'][t][i], type=ty,
                     frame=ts['column_frames'][t][i], slot=ts['column_slots'][t][i],
                     label=ts['column_labels'][t][i], source_label=ts['column_source_labels'][t][i])
                for i, ty in enumerate(types)]
        self.schemas[t] = result
        return result

    def validate_assignment(self, e):
        t = self.entries['table'][e]
        ts, a = self.tables, self.parts['assigned']
        indices = self.assigned[e]
        dets = []
        for i in indices:
            d = a['det'][i]
            require(0 <= d < len(ts['det_relations'][t]), 'assignment DET outside schema')
            w = ts['det_widths'][t][d]
            require(width(ts['det_types'][t][d]) == w, 'DET typed width differs')
            self.validate_run(a['offset'][i], a['rows'][i], w)
            dets.append(d)
        require(sorted(dets) == list(range(len(ts['det_relations'][t]))), 'missing or duplicate native DET assignment')
        require(len({ts['det_relations'][t][d] for d in dets}) == len(dets), 'duplicate native DET assignment')
        return indices

    def assignment(self, e):
        t = self.entries['table'][e]
        ts, a = self.tables, self.parts['assigned']
        return [dict(relation=ts['det_relations'][t][a['det'][i]],
                     types=ts['det_types'][t][a['det'][i]], frames=ts['det_frames'][t][a['det'][i]],
                     columns=ts['det_columns'][t][a['det'][i]],
                     rows=self.run(a['offset'][i], a['rows'][i], ts['det_widths'][t][a['det'][i]]))
                for i in self.validate_assignment(e)]

    def validate_entry(self, e, *, with_extents=True, projection_stop=False):
        """Validate completeness/layout without materializing value row tuples.

        Status 2 is valid unresolved metadata. Only consumer policy decides
        whether an operation needs a resolved frame. Projection stops are an
        explicit admission option, independent of complete value rows.
        """
        es, ts = self.entries, self.tables
        require(0 <= e < len(es['table']), 'native entry index absent')
        t = es['table'][e]
        schema = self.schema(t)
        require(not ts['fault'][t], 'native table fault: ' + str(ts['fault'][t]))
        if projection_stop:
            require(not ts['projections_stop_bound'][t], 'native projection stopped')
        require(es['kind'][e] == 0, f'native entry {e} does not contain complete rows (kind={es["kind"][e]})')
        keys = ('fault', 'stop_bound', 'value_stop_bound')
        if with_extents:
            keys += ('extent_fault', 'extent_stop_bound')
        for key in keys:
            require(not es[key][e], f'native entry {e}: {key}={es[key][e]}')
        self.validate_assignment(e)
        count = es['rows'][e]
        self.validate_run(es['offset'][e], count, ts['width'][t])
        at = 0
        for c in schema:
            if c['type'] == 'Unit':
                require(all(self.values[es['offset'][e] + j*ts['width'][t] + at] == 0 for j in range(count)),
                        'invalid native Unit value')
            at += 4 if c['type'] in WIDE else 1
        extcols = ts['extent_columns'][t]
        require(len(set(extcols)) == len(extcols) and all(0 <= c < len(schema) and schema[c]['type'] in WIDE for c in extcols),
                'invalid native extent columns')
        statuses = es.get('extent_status')
        if statuses is not None:
            require(extcols == [c['index'] for c in schema if c['type'] in WIDE],
                    'native geometric extent column coverage differs')
            statuses = [list(blob(row)) if isinstance(row, dict) else row for row in statuses[e]]
            require(len(statuses) == (count if extcols else 0), 'native extent status row count differs')
        else:
            require(self.missing_extent_status == 'infer' or not extcols,
                    'native extent_status absent; explicit legacy infer policy required')
        eo = es['extent_offset'][e]
        available = bool(extcols and count and eo >= 0)
        if extcols and count:
            if with_extents:
                require(available, 'missing native extents')
            if available:
                self.validate_run(eo, count, 2*len(extcols))
        if statuses is not None:
            for j, row in enumerate(statuses):
                require(len(row) == len(extcols), 'native extent status column count differs')
                for k, status in enumerate(row):
                    require(type(status) is int and status in (0, 1, 2), 'invalid native extent status')
                    if available:
                        start = eo + (j*len(extcols)+k)*2
                        a, b = self.values[start:start+2]
                        require((status == 1 and a > 0 and b > 0) or
                                (status != 1 and a == -1 and b == -1), 'native extent status/size conflict')
                    else:
                        require(status != 1, 'resolved native status without extent buffer')
        elif available:
            for v in range(eo, eo+count*2*len(extcols), 2):
                a, b = self.values[v:v+2]
                require((a == -1 and b == -1) or (a > 0 and b > 0), 'invalid native extent')
        require(es['example_kind'][e] in (0, 1, 2), 'unknown native example kind')
        return dict(table=t, count=count, schema=schema, extent_columns=extcols,
                    extent_status=statuses, extent_available=available)

    def count(self, e, *, with_extents=False, projection_stop=False):
        """Count complete value rows with the same validation as entry()."""
        return self.validate_entry(e, with_extents=with_extents, projection_stop=projection_stop)['count']

    def _extent_values(self, e, checked):
        if not checked['extent_available']:
            return ()
        start = self.entries['extent_offset'][e]
        size = checked['count'] * 2 * len(checked['extent_columns'])
        return self.values[start:start+size]

    def raw_extent_run(self, e):
        """Return the validated flat extent tuple in native row/column order."""
        checked = self.validate_entry(e, with_extents=True, projection_stop=False)
        return tuple(self._extent_values(e, checked))

    def entry(self, e, *, with_extents=True, projection_stop=True):
        checked = self.validate_entry(e, with_extents=with_extents, projection_stop=projection_stop)
        es, ts = self.entries, self.tables
        t = checked['table']
        flat = self.run(es['offset'][e], checked['count'], ts['width'][t])
        extcols = checked['extent_columns']
        statuses = checked['extent_status']
        extents = self._extent_values(e, checked)
        result = []
        for j, row in enumerate(flat):
            at = 0
            cells = []
            for c in checked['schema']:
                w = 4 if c['type'] in WIDE else 1
                value = row[at:at+w]; at += w
                cell = dict(value=value)
                if c['index'] in extcols:
                    k = extcols.index(c['index'])
                    start = (j*len(extcols)+k)*2
                    cell['extent'] = list(extents[start:start+2]) if checked['extent_available'] else None
                if c['type'] in WIDE:
                    if statuses is not None:
                        status = statuses[j][extcols.index(c['index'])]
                    else:
                        # Explicit historical inference only: Offset has no
                        # reference grid; positive sizes resolve, everything
                        # else stays unresolved, including Position and Box.
                        status = 0 if c['type'] == 'Offset' else 1 if cell.get('extent') and min(cell['extent']) > 0 else 2
                    cell['extent_status'] = ('no_grid', 'resolved', 'unresolved')[status]
                cells.append(cell)
            result.append(cells)
        kind, index = es['example_kind'][e], es['example_index'][e]
        name = 'task' if kind == 0 else ('train' if kind == 1 else 'test') + str(index + 1)
        return dict(entry=e, example=name, example_kind=kind, example_index=index,
                    model=es['model'][e], assignment=self.assignment(e), rows=result)

    def table(self, t, kept=None):
        require(0 <= t < len(self.tables['width']), 'native table index absent')
        entries = [self.entry(e) for e in self.bytable[t]]
        require(entries, 'native table has no entries')
        if kept is not None:
            # Export order is examples, assignments, models. A new model 0
            # begins each kept assignment, including identical projected DETs.
            # Validate the assignment values too; do not group by projected DET.
            counters = defaultdict(lambda: -1)
            for entry in entries:
                example = entry['example']
                if entry['model'] == 0:
                    counters[example] += 1
                choice = counters[example]
                require(0 <= choice < len(kept), 'kept entry choice outside report')
                expected = {d['relation']: d['rows'] for d in kept[choice]}
                for det in entry['assignment']:
                    require(det['relation'] in expected, 'kept report lacks native DET')
                    # Value equality is checked after native Term::decode in
                    # body.enrich, never packed IDs versus flattened cells.
                entry['choice'] = choice + 1
            require(all(n + 1 == len(kept) for n in counters.values()), 'missing kept native choices')
        return dict(table=t, form=self.tables['form'][t], point=self.tables['point'][t],
                    relation=self.tables['relation'][t], fact=self.tables['fact'][t],
                    schema=self.schema(t), entries=entries)


def case_payload(obj):
    """Copy native CaseTables buffers without interpreting values or column names."""
    def encode(value):
        if isinstance(value,(bytes,bytearray,memoryview)):
            return dict(base64=base64.b64encode(value).decode())
        if isinstance(value,dict):return {k:encode(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [encode(v) for v in value]
        return value
    return encode(dict(dtypes=obj.dtypes,values=obj.values,**{p:getattr(obj,p) for p in PARTS}))
