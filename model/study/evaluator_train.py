"""Full TRAIN typed-cell transport for dataset consumers.

This adapter does no replay on import or table acquisition. Matching and cell
projection delegate to the existing evaluator and canonical producer. TEST
entries are excluded before assignment inspection or cell decoding, unless
the caller passes `ntest` > 0: then the TEST example entries of the native table
(kind 2) and the TASK entries' broadcast to the TEST examples are acquired too.
"""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import ast
import hashlib
import json
from types import SimpleNamespace

from study_paths import CODE_ROOT


def dependency_receipt():
    """Adapter dependencies; callers must also retain evaluator/runtime receipts."""
    import tables
    import checks
    import surface
    import case_collector
    import program_metadata
    import raw_body
    import gold_body
    paths = (Path(__file__), Path(tables.__file__), Path(checks.__file__),
             Path(surface.__file__), Path(case_collector.__file__),
             Path(program_metadata.__file__), Path(raw_body.__file__), Path(gold_body.__file__), CODE_ROOT / 'study_paths.py', CODE_ROOT / 'native_correspondence.py', CODE_ROOT / 'normalized_gold.py', CODE_ROOT / 'prefix_universe.py', CODE_ROOT / 'current_native_names.py', CODE_ROOT / 'det_full_body.py', CODE_ROOT / 'legacy_body_metadata.py', CODE_ROOT / 'legacy_body_worker.py', CODE_ROOT / 'ast/run/provenance.py',
             CODE_ROOT / 'judge2/render2/body.py', CODE_ROOT / 'judge2/render2/headers.py',
             CODE_ROOT / 'judge3/render_pair.py')
    return {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def det_dependency_receipt():
    """Actual DET metadata/reader/observer source closure, without prose."""
    paths = ('judge3/det_metadata.py', 'judge3/nonrender_metadata.py',
             'judge3/definition_binding.py', 'judge3/catalog.py',
             'judge2/render2/headers.py', 'judge2/render2/column_paths.py',
             'judge2/render2/structured.py', 'ast/run/mech3/det_receipt.py',
             'ast/run/mech3/reader_projection.py', 'ast/run/mech3/common.py',
             'ast/run/mech/run.py', 'ast/run/mech5/metadata.py', 'ast/run/mech5/_paths.py')
    return dict(dependency_receipt(), **{
        str((CODE_ROOT / name).resolve()): hashlib.sha256((CODE_ROOT / name).read_bytes()).hexdigest()
        for name in paths})


def prepare_det_metadata(ev, record, *, native_base, case_inventory=None):
    """Canonical RAW metadata -> certified reader/header union -> DET adapter.

    This mechanical feature surface neither admits a judge pair nor acquires
    rows. The ordinary producer and judge clause checker retain DET exclusion.
    """
    import sys
    from tables import TargetStore, Incomplete
    from evaluator import sha
    sys.path.insert(0, str(CODE_ROOT / 'ast/run'))
    from mech3.det_receipt import receipt
    from judge3.det_metadata import MetadataProducer
    store = TargetStore(ev.legacy, CODE_ROOT)
    producer = MetadataProducer(engine=ev.arclog, settings=ev.settings,
        read_native=lambda ref, base: store.snapshot(ref, base)['_native_reader'],
        corpus=Path(native_base).resolve().parent, case_inventory=case_inventory)
    # The immutable corpus inventory is independent of the mutant and its
    # kept selection. Retain only the current corpus/task, not producers,
    # native readers, programs or per-pair adapters. Custom inventory suppliers
    # remain uncached because their lifetime/mutability is caller-owned.
    if case_inventory is None:
        from mech5.metadata import bind_inventory_copy
        key = (producer.corpus, record['task'])
        cached = getattr(ev, '_det_inventory_cache', None)
        if cached is None or cached[0] != key:
            cached = (key, {})
            ev._det_inventory_cache = cached
        producer.case_cache = cached[1]
        # Canonical envelopes are cloned for each pair; only read-only source
        # evidence leaves are shared, as on the ordinary mechanical path.
        bind_inventory_copy(producer)
    if not hasattr(producer, 'raw_side_bindings'):
        raise Incomplete('canonical raw_side_bindings source dependency is not installed')
    raw = producer.raw_side_bindings(record, native_base=native_base)
    if raw.get('schema') != 'judge3-raw-side-bindings-v1' or raw.get('source_sha256') != sha(record):
        raise Incomplete('RAW DET metadata source differs')
    transport = receipt(record, raw['exports'], raw['bindings'])
    adapter = producer.produce(record, native_base=native_base, det_projection=transport, feature_only=True)
    adapter['det_acquisition'] = dict(schema='evaluator-det-source-v1', source_sha256=sha(record),
        transport_sha256=sha(transport), implementation=det_dependency_receipt(),
        purpose='mechanical TRAIN feature acquisition; no judge admission')
    return adapter


@lru_cache(maxsize=1)
def _projector():
    # Execute the same producer function that tables.projected_rows uses, with
    # cells intact. There is no second projection/deduplication policy here.
    source = CODE_ROOT / 'judge2/render2/body.py'
    tree = ast.parse(source.read_text(), str(source))
    function = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == 'project_entries')
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    namespace = {'require': require}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['project_entries']


@lru_cache(maxsize=1)
def _visibility():
    """The renderer's canonical Example-column TRAIN visibility policy."""
    source = CODE_ROOT / 'judge3/render_pair.py'
    tree = ast.parse(source.read_text(), str(source))
    document = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Document')
    function = next(n for n in document.body if isinstance(n, ast.FunctionDef) and n.name == 'visible')
    compact = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'compact')
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    namespace = dict(require=require, json=json)
    exec(compile(ast.Module(body=[compact, function], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['visible']


@lru_cache(maxsize=1)
def _compact():
    """The renderer's cell-row key, used to drop repeated rows."""
    source = CODE_ROOT / 'judge3/render_pair.py'
    tree = ast.parse(source.read_text(), str(source))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'compact')
    namespace = dict(json=json)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['compact']


def test_visible(entry, schema, ntrain, example):
    """The rows of `entry` that belong to TEST example `example`.

    The native numbers the examples of a task as the train pairs and then the
    test inputs (engine/arclog/src/task.rs:218-221), so the Example column
    value of TEST example j is ntrain + j (engine/arclog-tables/src/tables.rs:74-82
    maps a value below ntrain to (1, value) and any other to (2, value - ntrain)).
    A row is kept when every Example column of the table holds that value. A table
    with no Example column keeps all rows. Repeated rows drop, as in
    `Document.visible`, which stays the TRAIN policy and rejects TEST entries.
    """
    compact = _compact()
    columns = [c['index'] for c in schema if c['type'] == 'Example']
    value = ntrain + example
    rows = [row for row in entry['rows'] if all(row[i]['value'][0] == value for i in columns)]
    unique = {compact(row): row for row in rows}
    return dict(entry, rows=[unique[k] for k in sorted(unique)])


def train_entry_contexts(ev, native, table, record, *, ntrain, ntest=0, held_entries=None):
    """Canonical kept TRAIN/TASK selection before any value/extent decoding.

    With `ntest` > 0 the TEST entries (kind 2) take part, and the kept selection
    requires the test axes too."""
    from tables import Incomplete, kept_entries
    if type(ntrain) is not int or ntrain < 1:
        raise Incomplete('TRAIN acquisition requires the authenticated train input count')
    if type(ntest) is not int or ntest < 0:
        raise Incomplete('TEST acquisition requires a nonnegative test input count')
    kinds = (0, 1, 2) if ntest else (0, 1)
    reader = native['_native_reader']
    # Only assignment metadata is read for eligible entries. Dummy rows allow
    # the canonical matcher to select contexts without decoding any value rows.
    metadata = []
    for index in reader.bytable[table]:
        kind = reader.entries['example_kind'][index]
        if kind not in kinds:
            continue
        example = reader.entries['example_index'][index]
        if kind == 1 and not 0 <= example < ntrain:
            raise Incomplete('native TRAIN entry is outside the authenticated input axis')
        if kind == 2 and not 0 <= example < ntest:
            raise Incomplete('native TEST entry is outside the authenticated input axis')
        metadata.append(dict(entry=index, example=(kind, example),
            model=reader.entries['model'][index], rows=(),
            assignment=tuple(sorted((d['relation'], tuple(tuple(r) for r in d['rows']))
                                    for d in reader.assignment(index)))))
    ts = native['tables']
    return kept_entries(ev.legacy, metadata, ts['det_relations'][table],
                           ts['det_types'][table], record, ntrain, ntest, held_entries=held_entries)


def _slot(relation):
    """The sampler's key for a DET slot: the number of `&r12` as text, else the relation name."""
    return relation[2:] if relation.startswith('&r') and relation[2:].isdigit() else relation


def assignment_plan(reader, ts, table, matched, *, ntrain, ntest=0, width=None, copy_rows=True):
    """Every live assignment of a table that reads a DET, numbered as the sampler numbers them.

    `matched` is the table's `train_entry_contexts` result. Its kept contexts and
    its `other_contexts` together are one entry per example and assignment that
    the native walk reached. An assignment is the DET slot rows that the entry
    holds; it takes the number of its first appearance over the entries, as
    `rulecheck._dets_key` numbers a draw's assignments: the TRAIN/TASK entries in
    entry order first, then the TEST entries (a set of slot rows that only a TEST
    entry has takes the next number).

    Returns None where the table reads no DET, or where a kept assignment has no
    entry (the kept form then reports it as missing), else a dict:
    - `contexts`: every entry's context, in entry order; `numbers` maps an
      assignment key to its number; `assignments` lists the DET slot rows of each
      number, `{slot: [row, ...]}` with the slot spelled as the sampler's `dets` do
      (`12` for the DET `&r12`); `kept_numbers` the numbers of the case's kept
      assignments;
    - `missing`: the kept axes without an entry, `[number, kind, example]` with the
      lowest number of the kept assignment;
    - `cells`: the Python cells of the table at every assignment, counted as
      `acquire_train_table` counts them (`width` is the projected field count)."""
    if not ts['det_relations'][table]:
        return None
    contexts = sorted(matched['contexts'] + matched['other_contexts'], key=lambda c: c['entry'])
    numbers = {}
    for context in [c for c in contexts if c['example'][0] != 2] + [c for c in contexts if c['example'][0] == 2]:
        numbers.setdefault(context['assignment'], len(numbers))
    by_kept = {}
    for context in matched['contexts']:
        for a in context['kept_assignments']:
            by_kept.setdefault(a, set()).add(numbers[context['assignment']])
    if {k[0] for k in matched['required']} - by_kept.keys():
        return None
    rows = lambda c: int(reader.entries['rows'][c['entry']])
    examples = lambda c: ntrain + ntest if reader.entries['example_kind'][c['entry']] == 0 else 1
    cells = len(reader.schema(table)) * sum(rows(c) for c in contexts)
    if copy_rows:
        cells += (width if width is not None else len(reader.schema(table))) * sum(rows(c) * examples(c) for c in contexts)
    return dict(contexts=contexts, numbers=numbers,
        assignments=[{_slot(name): [list(row) for row in value] for name, value in key} for key in numbers],
        kept_numbers=sorted({n for found in by_kept.values() for n in found}),
        missing=[[min(by_kept[a]), kind, example] for a, kind, example in matched['missing']],
        cells=cells)


def select_train_full_rows(ev, native, record, *, ntrain, ntest=0, all_assignments=False):
    """Pure mask/receipt from canonical kept metadata; no packed owner escapes.

    With `ntest` > 0 the mask holds the kept TEST entries too, and the receipt
    says so (`test_entries_allowed`). The native packs full rows for any entry
    index in the mask, whatever its kind (engine/arclog-tables/src/columns.rs:438-441).
    With `all_assignments` the mask holds the entries of every live assignment of a
    table that reads a DET (`assignment_plan`), unless that table is over
    TRAIN_TABLE_MAX_CELLS at every assignment: it then keeps the kept entries only,
    and the table's proof says so (`all_assignments`)."""
    from tables import axis_receipt
    reader = native['_native_reader']
    selected = set()
    tables = []
    for table in range(len(native['tables']['form'])):
        proof = dict(table=table)
        try:
            matched = train_entry_contexts(ev, native, table, record, ntrain=ntrain, ntest=ntest)
            proof.update(status='matched', **axis_receipt(matched))
            proof['entries'] = []
            table_entries = set()
            plan = assignment_plan(reader, native['tables'], table, matched, ntrain=ntrain, ntest=ntest) if all_assignments else None
            if plan is not None:
                if plan['cells'] > TRAIN_TABLE_MAX_CELLS:
                    proof['all_assignments'] = dict(status='fallback', cells=plan['cells'], assignments=len(plan['assignments']))
                else:
                    proof['all_assignments'] = dict(status='selected', cells=plan['cells'], assignments=len(plan['assignments']))
                    table_entries.update(c['entry'] for c in plan['contexts'])
            for context in matched['contexts']:
                entry = context['entry']
                table_entries.add(entry)
                proof['entries'].append(dict(entry=entry,
                    example=list(context['example']), model=context['model'],
                    kept_assignments=list(context['kept_assignments']),
                    native_kind=int(reader.entries['kind'][entry]),
                    rows=int(reader.entries['rows'][entry])))
            selected.update(table_entries)
        except (ValueError, KeyError, IndexError, TypeError) as error:
            # The typed consumer retains this table's explicit unavailable
            # result. A failed match grants no full-row transport selection.
            proof.update(status='unavailable', reason=str(error))
        tables.append(proof)
    result = dict(schema='evaluator-train-entry-mask-v1', entries=sorted(selected),
                  tables=tables,
                  test_entries_selected=any(reader.entries['example_kind'][e] == 2 for e in selected),
                  selection='canonical kept_entries over native TRAIN/TASK metadata')
    if ntest:
        result['test_entries_allowed'] = True
    return result


PROJECTED_FLOWS_MAX_BYTES = 1024 * 1024


def _projected_flow_receipt(reader, table, record, schema, projection, fields, source, axes):
    """Copy bounded raw edges while the authenticated native reader is owned.

    This transport never interprets a flow or reads entries/values. Virtual
    columns need an actual native certificate, which this API does not have.
    """
    from evaluator import sha
    result = dict(schema='evaluator-projected-flows-v1', version=1,
        status='unsupported', source_sha256=sha(record), table=table,
        kept_context_sha256=sha(record['evaluation']['kept_assignments']),
        source_schema_sha256=sha(schema), projection_sha256=sha(projection),
        projected_fields_sha256=sha(fields), packet_axes_sha256=sha(axes),
        max_bytes=PROJECTED_FLOWS_MAX_BYTES)
    try:
        if (not isinstance(source, dict) or source.get('side') != 'mutant'
                or source.get('native_ref') != record['native']['mutant']):
            raise ValueError('projected flows require the authenticated mutant snapshot')
        result.update(native_ref_sha256=sha(source['native_ref']), selector=deepcopy(source['selector']))
        selector = source['selector']
        if not {'form', 'point'} <= selector.keys() or any(
                str(reader.tables[k][table]) != str(v) for k, v in selector.items()
                if k in ('form', 'point', 'relation', 'fact')):
            raise ValueError('projected flows selector differs from the native table')
        if any(type(c) is not int or not 0 <= c < len(schema) for c in projection):
            raise ValueError('projected flows unavailable for a virtual or absent native column')
        columns = [dict(public_column=i, source_body_column=c, edges=[])
                   for i, c in enumerate(projection)]
        encoded = lambda v: len(json.dumps(v, ensure_ascii=False, sort_keys=True,
                                           separators=(',', ':'), allow_nan=False).encode('utf-8'))
        # This floor includes receipt keys and empty lists. Every edge below
        # charges its serialized occurrence, including duplicate aliases.
        size = encoded(dict(result, status='complete', columns=columns))
        if size > PROJECTED_FLOWS_MAX_BYTES:
            raise ValueError('projected flow receipt exceeds its byte limit')
        destinations = {}
        for output in columns:
            destinations.setdefault(output['source_body_column'], []).append(output['edges'])
        flow = reader.parts['flows']
        for i in range(len(flow['table'])):
            if flow['table'][i] != table:
                continue
            c = int(flow['column'][i])
            if not 0 <= c < len(schema):
                raise ValueError('native flow column is outside the authenticated schema')
            edge = [int(flow['kind'][i]), int(flow['source_table'][i])]
            for target in destinations.get(c, ()):
                growth = encoded(edge) + bool(target)
                if size + growth > PROJECTED_FLOWS_MAX_BYTES:
                    raise ValueError('projected flow receipt exceeds its byte limit')
                size += growth
                target.append(edge)
        result.update(status='complete', columns=columns)
    except (ValueError, KeyError, IndexError, TypeError) as error:
        result.update(status='unsupported', reason=str(error))
    return result


# The most Python cells that one TRAIN acquisition holds. The native bounds do
# not count them: the session bytes (`session_mib`) count 4 bytes for a native
# cell, and the table work cap counts bindings. A decoded cell is a dict of
# lists, about 1 KB with its extent. A table decodes one cell for each column of
# the native table in each row of each selected entry, and with `copy_rows`
# copies one for each projected column in each row of each kept assignment and
# TRAIN input of the entry.
TRAIN_TABLE_MAX_CELLS = 1 << 19
# The most cells that the acquired tables of one case hold together.
TRAIN_CASE_MAX_CELLS = 1 << 20


def train_table_cells(packet):
    """The cells that the entries of an acquired table hold."""
    return len(packet['fields']) * sum(len(entry['rows']) for entry in packet['entries'])


def without_test_rows(packet):
    """The acquired packet without its TEST entries and test axes, marked `test_rows` False.

    For a table that reads the test output (fact ex_output, or a node in
    `ex_output_dependent_nodes`): such a table has no test rows. A packet from
    `_input_train` takes the same call."""
    private = {k: [axis for axis in packet[k] if axis[1] != 2] for k in ('_kept_required', '_kept_missing') if k in packet}
    return dict(packet,
        entries=[e for e in packet['entries'] if e['example_kind'] != 2],
        required=[k for k in packet['required'] if k[1] != 2],
        missing=[k for k in packet['missing'] if k[1] != 2],
        test_rows=False, receipt=dict(packet['receipt'], test_cells=False), **private)


def kept_form(packet):
    """The packet of a table acquired with `all_assignments`, at the case's kept assignments only.

    The result is the packet that `acquire_train_table` gives without the option:
    `assignment` is the index of the kept assignment, and a model counts per
    (kept assignment, kind, example) in entry order. A packet without the option,
    or a table that reads no DET, comes back as it is. The rows are shared with
    the packet."""
    if '_kept_required' not in packet:
        return packet
    entries, models = [], {}
    items = packet['entries']
    i = 0
    while i < len(items):
        j = i
        while j < len(items) and items[j]['_context'] == items[i]['_context']:
            j += 1
        for a in items[i]['_kept']:
            for e in items[i:j]:
                axis = (a, e['example_kind'], e['example_index'])
                model = models.get(axis, 0)
                models[axis] = model + 1
                entries.append(dict(assignment=a, example_kind=e['example_kind'], example_index=e['example_index'],
                                    model=model, rows=e['rows']))
        i = j
    dropped = ('kept_assignments', 'assignments', 'assignments_partial', 'assignments_fallback', '_kept_required', '_kept_missing')
    return dict({k: v for k, v in packet.items() if k not in dropped}, entries=entries,
                required=packet['_kept_required'], missing=packet['_kept_missing'])


def acquire_train_table(ev, native, table, record, *, ntrain, ntest=0, test_rows=True, fields=None,
                        projection=None, output_aliases=None, source=None, held_entries=None, copy_rows=True,
                        include_projected_flows=False, all_assignments=False, fall_back=None, test_rows_fallback=False):
    """Return full typed TRAIN cells at the case's local kept assignments.

    `native` is the canonical native payload/reader, not grouped value tuples.
    `fields` and `projection` must describe the exact canonical physical output
    layout. Repeated indices preserve aliases; None requires a certified Unit.
    Models are local to each (assignment, TRAIN input), never cross-table IDs.
    Missing kept contexts are explicit and do not become empty tables.
    copy_rows=False shares read-only projected rows across local contexts; the
    synchronous feature writer retains them until serialization completes.
    ntest > 0 adds the TEST entries (kind 2); a TASK entry is broadcast to every
    train and every test example, and a test example keeps the rows of its own
    Example value (`test_visible`). The packet then has `ntrain`, `ntest` and
    `test_rows`. A table of the native fact ex_output, or a call with
    test_rows=False, gets no test entries: it is acquired as with ntest=0 and
    marked `test_rows` False. ntest=0 gives the packet as before.
    all_assignments=True gives a table that reads a DET its entries at every live
    assignment, not only the case's kept ones (`assignment_plan`; not with
    `held_entries`). `assignment` is then the number of the assignment by first
    appearance of its DET slot rows, and the packet adds `kept_assignments` (the
    numbers of the case's kept assignments), `assignments` (the DET slot rows of
    each number), `assignments_partial` (True where an assignment lacks entries
    because the native walk stopped or an entry is unreadable) and
    `assignments_fallback` (the reason, where the table is over
    TRAIN_TABLE_MAX_CELLS at every assignment, or `fall_back` is given: it then
    holds the kept assignments only, with the same numbers). A table that reads no
    DET is acquired as without the option.
    test_rows_fallback=True is for a call with `ntest` > 0 (and test_rows True): a table that is
    over TRAIN_TABLE_MAX_CELLS with its test entries, at the assignments it would hold (every live
    one, or the kept ones where `assignments_fallback` applies), is acquired again at the kept
    assignments without test entries. The packet is then marked `test_rows` False and
    `test_rows_fallback` (the reason, with the count). Only a table that is still over the cap
    without test entries raises. Default off: such a table raises.
    """
    if type(copy_rows) is not bool:
        raise ValueError("copy_rows must be boolean")
    if type(include_projected_flows) is not bool:
        raise ValueError("include_projected_flows must be boolean")
    from tables import Incomplete, comparison_type
    from program_metadata import type_identity, typed_fields
    from native_correspondence import canonical_bound_field_type
    from evaluator import sha
    if type(ntrain) is not int or ntrain < 1:
        raise Incomplete('TRAIN acquisition requires the authenticated train input count')
    if type(ntest) is not int or ntest < 0 or type(test_rows) is not bool:
        raise Incomplete('TEST acquisition requires a nonnegative test input count')
    reader = native['_native_reader']
    test_dropped = False
    if ntest and (not test_rows or native['tables']['fact'][table] == 'ex_output'):
        ntest, test_dropped = 0, True
    schema = deepcopy(reader.schema(table))
    if projection is None:
        if fields is not None:
            raise Incomplete('explicit fields require an explicit physical projection')
        projection = list(range(len(schema)))
    projection = list(projection)
    if fields is None:
        if any(type(i) is not int or not 0 <= i < len(schema) for i in projection):
            raise Incomplete('native TRAIN projection is outside the physical schema')
        fields = [deepcopy(schema[i]) for i in projection]
    else:
        fields = deepcopy(fields)
    if len(fields) != len(projection):
        raise Incomplete('TRAIN fields and physical projection arity differ')
    fields = typed_fields(ev, record, fields)
    for field, index in zip(fields, projection):
        canonical_bound_field_type(field)
        if index is None:
            evidence = field.get('source_projection', {})
            if (field['type'] != 'Unit' or
                    evidence.get('inserted_constant', {}).get('kind') != 'unit'):
                raise Incomplete('TRAIN projection lacks certified inserted Unit evidence')
        elif (type(index) is not int or not 0 <= index < len(schema)
              or comparison_type(type_identity(ev, record, schema[index]['type'])[0]) != comparison_type(type_identity(ev, record, field.get('native_type',field['type']))[0])):
            raise Incomplete('TRAIN projected field type or physical index differs')

    matched = train_entry_contexts(ev, native, table, record, ntrain=ntrain, ntest=ntest, held_entries=held_entries)
    plan = None
    if all_assignments and held_entries is None:
        plan = assignment_plan(reader, native['tables'], table, matched, ntrain=ntrain, ntest=ntest,
                               width=len(fields), copy_rows=copy_rows)
    fallback = None
    if plan is not None:
        fallback = fall_back
        if fallback is None and plan['cells'] > TRAIN_TABLE_MAX_CELLS:
            fallback = f"{plan['cells']} cells at every assignment, over TRAIN_TABLE_MAX_CELLS={TRAIN_TABLE_MAX_CELLS}"
    # The contexts to acquire: the kept ones, or with a plan every one that the native walk reached.
    used = plan['contexts'] if plan is not None and fallback is None else matched['contexts']
    contexts = [(context, int(reader.entries['rows'][context['entry']]),
                 ntrain + ntest if reader.entries['example_kind'][context['entry']] == 0 else 1)
                for context in used]
    cells = len(schema) * sum(rows for _, rows, _ in contexts)
    if copy_rows:
        cells += len(fields) * sum(rows * (1 if plan is not None else len(context['kept_assignments'])) * examples
                                   for context, rows, examples in contexts)
    if cells > TRAIN_TABLE_MAX_CELLS:
        if test_rows_fallback and ntest and not test_dropped:
            # Last step: the kept assignments (as `assignments_fallback` where there is a plan) and train entries only.
            packet = acquire_train_table(ev, native, table, record, ntrain=ntrain, ntest=ntest, test_rows=False, fields=fields,
                projection=projection, output_aliases=output_aliases, source=source, held_entries=held_entries, copy_rows=copy_rows,
                include_projected_flows=include_projected_flows, all_assignments=all_assignments,
                fall_back=fallback if fallback is not None else fall_back)
            packet['test_rows_fallback'] = f'{cells} cells with test rows, over TRAIN_TABLE_MAX_CELLS={TRAIN_TABLE_MAX_CELLS}'
            return packet
        raise Incomplete(f'TRAIN table {table} needs {cells} cells, over TRAIN_TABLE_MAX_CELLS={TRAIN_TABLE_MAX_CELLS}')
    entries = []
    model_counts = {}
    partial = False
    for context in used:
        index = context['entry']
        kept_context = 'kept_assignments' in context
        try:
            # The kind gate above precedes this sole value/geometry decoder.
            decoded = reader.entry(index, with_extents=True, projection_stop=False)
            if decoded['example_kind'] not in ((0, 1, 2) if ntest else (0, 1)):
                raise Incomplete('native entry example kind changed during TRAIN acquisition')
            kind = decoded['example_kind']
            # (example kind, example index, projected rows) of each example that
            # the entry serves: a TASK entry serves every example.
            served = []
            if kind != 2:
                # TASK facts may themselves contain test Example values. Filter with
                # the producer policy before projection can hide the Example column.
                visible = _visibility()(SimpleNamespace(ntrain=ntrain), decoded, schema)
                projected = _projector()(dict(entries=[dict(visible, choice=None)]), projection)[0]['rows']
                served += [(1, example, projected)
                           for example in (range(ntrain) if kind == 0 else [decoded['example_index']])]
            if ntest and kind != 1:
                for example in (range(ntest) if kind == 0 else [decoded['example_index']]):
                    visible = test_visible(decoded, schema, ntrain, example)
                    served.append((2, example, _projector()(dict(entries=[dict(visible, choice=None)]), projection)[0]['rows']))
        except (ValueError, KeyError, IndexError, TypeError):
            # An assignment that is not the case's kept one and that the native cannot give
            # (a stop of the walk or of its rows, or an unreadable entry) leaves the table partial.
            if plan is None or kept_context:
                raise
            partial = True
            continue
        for assignment in ([plan['numbers'][context['assignment']]] if plan is not None else context['kept_assignments']):
            for example_kind, example, projected in served:
                axis = (assignment, example_kind, example)
                model = model_counts.get(axis, 0)
                model_counts[axis] = model + 1
                entries.append(dict(assignment=assignment, example_kind=example_kind,
                    example_index=example, model=model, rows=deepcopy(projected) if copy_rows else projected,
                    **(dict(_context=index, _kept=list(context.get('kept_assignments', ()))) if plan is not None else {})))
    required = [list(k) for k in sorted(matched['required'])]
    missing = [list(k) for k in matched['missing']]
    if plan is not None:
        missing = plan['missing']
        required = [list(k) for k in sorted({(e['assignment'], e['example_kind'], e['example_index']) for e in entries}
                                            | {tuple(k) for k in missing})]
    packet = dict(fields=fields, entries=entries,
        required=required,
        missing=missing,
        source_schema=schema, projection=projection, output_aliases=dict(output_aliases or {}),
        receipt=dict(source=deepcopy(source), source_sha256=sha(record), table=table,
            kept_context_sha256=sha(record['evaluation']['kept_assignments']),
            implementation=dependency_receipt(), test_cells=ntest > 0,
            model_namespace='local to kept assignment and TRAIN input',
            task_broadcast='native TASK entries over authenticated TRAIN axis'))
    if ntest:
        packet.update(ntrain=ntrain, ntest=ntest, test_rows=True)
        packet['receipt']['task_broadcast'] = 'native TASK entries over authenticated TRAIN and TEST axes'
    elif test_dropped:
        packet['test_rows'] = False
    if plan is not None:
        packet.update(kept_assignments=plan['kept_numbers'], assignments=plan['assignments'],
                      _kept_required=[list(k) for k in sorted(matched['required'])],
                      _kept_missing=[list(k) for k in matched['missing']])
        if partial:
            packet['assignments_partial'] = True
        if fallback is not None:
            packet['assignments_fallback'] = fallback
        packet['receipt']['model_namespace'] = 'local to assignment number and TRAIN input'
    if include_projected_flows:
        axes = dict(required=packet['required'], missing=packet['missing'], entries=[
            [e['assignment'], e['example_kind'], e['example_index'], e['model'], len(e['rows'])]
            for e in entries])
        packet['receipt']['projected_flows'] = _projected_flow_receipt(
            reader, table, record, schema, projection, fields, source, axes)
    return packet


def acquire_candidate_train(ev, native, table, record, *, ntrain, proof,
                            columns=None, source=None):
    """Apply the canonical candidate's exported labels and resolved aliases."""
    from surface import tokens, output_projection
    from tables import Incomplete
    ts = native['tables']
    names = list(ts['column_names'][table])
    exported = {t.lstrip('*^') for t in tokens(proof['canonical']) if t.startswith(('*', '^'))}
    if len(set(names)) != len(names):
        raise Incomplete('candidate native output labels are ambiguous')
    aliases = proof.get('output_aliases', {})
    labels = [name for name in names if name in exported]
    labels += [name for name in aliases if name in exported]
    if len(set(labels)) != len(labels):
        raise Incomplete('candidate output alias is ambiguous')
    if columns is not None:
        if any(name not in labels for name in columns):
            raise Incomplete('requested candidate output column is absent')
        labels = list(columns)
    outputs = list(zip(labels, output_projection(names, labels, aliases)))
    schema = native['_native_reader'].schema(table)
    fields = [dict(deepcopy(schema[index]), field_name=name, source_body_column=index)
              for name, index in outputs]
    return acquire_train_table(ev, native, table, record, ntrain=ntrain,
        fields=fields, projection=[index for _, index in outputs],
        output_aliases=aliases, source=source)


def acquire_input_train(ev, native, table, record, *, ntrain, ntest=0, source=None):
    """Expose per-input `input` from the exact native `ex_input` fact table.

    Kept matching, TRAIN visibility, TASK broadcast and typed-cell decoding are
    the same as acquire_train_table. Restrict the native Example column to the
    destination TRAIN input before removing it with the canonical projector.
    Use acquire_train_table separately to retain the full `ex_input` relation.
    """
    from tables import Incomplete
    if native['tables']['fact'][table] != 'ex_input':
        raise Incomplete('input TRAIN acquisition requires the native ex_input fact')
    packet = acquire_train_table(ev, native, table, record, ntrain=ntrain, ntest=ntest, source=source)
    return _input_train(packet)


def _input_train(packet):
    """The sole per-input projection, also reused by once-case acquisition."""
    from tables import Incomplete
    examples = [i for i, field in enumerate(packet['fields']) if field['type'] == 'Example']
    if len(examples) != 1:
        raise Incomplete('native ex_input must have exactly one Example column')
    example_column = examples[0]
    projection = [i for i in range(len(packet['fields'])) if i != example_column]
    entries = []
    for entry in packet['entries']:
        # The native Example value of a test input is ntrain plus its index.
        test = entry['example_kind'] == 2
        rows = [row for row in entry['rows']
                if row[example_column]['value'] == [entry['example_index'] + (packet['ntrain'] if test else 0)]]
        projected = _projector()(dict(entries=[dict(entry, rows=rows,
            example=('test' if test else 'train')+str(entry['example_index']+1), choice=entry['assignment'])]),
            projection)[0]['rows']
        entries.append(dict(entry, rows=deepcopy(projected)))
    return dict(packet, fields=[deepcopy(packet['fields'][i]) for i in projection],
        entries=entries, projection=projection,
        receipt=dict(packet['receipt'], input_projection=dict(
            source_fact='ex_input', relation='input', example_column=example_column,
            rule='Example equals destination TRAIN index (ntrain + index for a TEST input) before Example column removal')))


def acquire_case_train(ev, record, case_context, ntrain, ntest, *, test_rows=False, all_assignments=False, test_rows_fallback=False):
    """One fresh canonical case replay, original table inventory and TRAIN cells.

    Persist this packet once per task/case/settings in the exporter. Every call
    requests one fresh replay; there is no per-pair replay or whole-study cache.
    Missing own-case kept values add one separately receipted native gold-only
    TRAIN FITS observation, reused for identical source/settings/task inputs.
    The full native export graph is metadata, not a grant of clause availability.
    BODY observers are explicitly disabled: this surface returns original
    native tables only. Point G is acquired independently by acquire_train_point.
    No native handle or private TEST table transport escapes this surface.
    test_rows=True adds the TEST entries of each table (kind 2) to the full-row
    mask and the packets; a table whose test entries are absent, as one that reads
    the test output, comes back without them and marked `test_rows` False.
    all_assignments=True gives each table that reads a DET its entries at every
    live assignment (`acquire_train_table`), and the full-row mask holds them. A
    table over TRAIN_TABLE_MAX_CELLS at every assignment, or that would take the
    case over TRAIN_CASE_MAX_CELLS, holds the kept assignments only and is marked
    `assignments_fallback`. Default off: the packet is as without the option.
    test_rows_fallback=True (with test_rows) lets a table that is still over
    TRAIN_TABLE_MAX_CELLS, or that still takes the case over TRAIN_CASE_MAX_CELLS,
    with its test entries at the kept assignments come back at the kept assignments
    without test entries, marked `test_rows` False and `test_rows_fallback` (the
    reason). Only a table that is over a cap without test entries fails.
    Each case owns a fresh native session through replay and typed extraction;
    closing it releases prior-case arenas without changing operation bounds.
    """
    with ev.fresh_session() as isolated:
        packet = _acquire_case_train(isolated, record, case_context, ntrain, ntest, test_rows, all_assignments, test_rows_fallback)
        packet['receipt']['session'] = dict(
            scope='independent case replay and typed TRAIN extraction',
            lifetime='closed before returning JSON packet',
            session_bytes=isolated.receipt['session_bytes'],
            extra_replays=0)
        return packet


def _acquire_case_train(ev, record, case_context, ntrain, ntest, test_rows=False, all_assignments=False, test_rows_fallback=False):
    """Materialize one case while its independent native session is alive."""
    from case_collector import acquire_case, _context, clear_cache
    from tables import Incomplete
    from evaluator import sha
    from program_metadata import type_identity
    if (type(ntrain) is not int or ntrain < 1 or
            type(ntest) is not int or ntest < 0):
        raise Incomplete('case TRAIN acquisition requires authenticated input axes')
    held_test = ntest if test_rows else 0
    case, text, kept, names, kept_observation = _context(ev, record, case_context, with_receipt=True)
    if not kept:
        raise Incomplete('case TRAIN acquisition requires a nonempty own kept axis')
    resolved = dict(case=case, gold_sexp=text, kept_assignments=kept)
    if kept_observation is not None:
        resolved['_gold_kept_receipt'] = kept_observation
    if names is not None:
        resolved['relation_source_names'] = names
    own = dict(record, case=case, gold_sexp=text, mutant_sexp=text,
               evaluation=dict(record['evaluation'], kept_assignments=kept))
    saved = {}
    class Capture:
        def __getattr__(self, name):
            return getattr(ev, name)
        def replay_program(self, *args, **kwargs):
            # Native projections may export Count even for complete Rows.
            # Request the bounded full-row packer; never inflate a decode cap
            # or reconstruct values from counts/projections in Python.
            kwargs['full_rows'] = True
            result = ev.replay_program(*args, **kwargs)
            if saved:
                raise Incomplete('case TRAIN collection exceeded its single replay contract')
            saved['replay'] = result
            if result.get('engine') == 'ran':
                saved['native'] = ev.captures[-1]['native']
            return result
    proxy = Capture()
    try:
        bundle = acquire_case(proxy, record, resolved, ntrain, ntest,
                              include_bodies=False, acquire_values=False)
    finally:
        # The collector's value-only cache cannot serve typed cell transport.
        # Release this private proxy cache as soon as acquisition is finished.
        clear_cache(proxy)
    rows = []
    held = 0
    gaps = deepcopy(bundle['gaps'])
    native = saved.get('native')
    for item in bundle['tables']:
        identity = dict(table_id=item['table_id'], native_table=item['native_table'],
            selector=deepcopy(item['selector']), source_name=item['source_name'],
            native_schema=deepcopy(item['native_schema']))
        output = dict(identity, status='unknown', table=None, input=None)
        try:
            if native is None:
                raise Incomplete('case replay did not produce a complete native capture')
            table = item['native_table']
            fields = [dict(deepcopy(column), field_name=field['field_name'])
                      for column, field in zip(item['native_schema'], item['fields'])]
            if (len(fields) != len(item['fields']) or len(fields) != len(item['native_schema']) or
                    [type_identity(ev,own,field['type'])[0] for field in fields] !=
                    [type_identity(ev,own,field['type'])[0] for field in item['fields']]):
                raise Incomplete('canonical case table fields differ from native physical schema')
            def acquire(fall_back=None, no_test=None):
                packet = acquire_train_table(ev, native, table, own, ntrain=ntrain, ntest=held_test,
                    test_rows=no_test is None, fields=fields, projection=list(range(len(fields))),
                    source=dict(identity, case=case, observation=bundle['receipt']),
                    **(dict(test_rows_fallback=True) if test_rows_fallback and held_test and no_test is None else {}),
                    **(dict(all_assignments=True, fall_back=fall_back) if all_assignments else {}))
                if no_test is not None:
                    packet['test_rows_fallback'] = no_test
                if held_test and packet['missing'] and all(k[1] == 2 for k in packet['missing']):
                    # No native test entry for a required test input, as a relation
                    # that reads the test output: the table has no test rows.
                    packet = without_test_rows(packet)
                return packet
            packet = acquire()
            cells = train_table_cells(packet)
            if 'assignments' in packet and 'assignments_fallback' not in packet and held + cells > TRAIN_CASE_MAX_CELLS:
                # The table at every assignment takes the case over its cap: keep the kept assignments.
                packet = acquire(f'{cells} cells at every assignment, with {held} held, over TRAIN_CASE_MAX_CELLS={TRAIN_CASE_MAX_CELLS}')
                cells = train_table_cells(packet)
            if test_rows_fallback and held_test and packet.get('test_rows') is not False and held + cells > TRAIN_CASE_MAX_CELLS:
                # The table with its test entries, at the kept assignments, takes the case over its cap: train entries only.
                packet = acquire(packet.get('assignments_fallback'),
                                 f'{cells} cells with test rows, with {held} held, over TRAIN_CASE_MAX_CELLS={TRAIN_CASE_MAX_CELLS}')
                cells = train_table_cells(packet)
            if held + cells > TRAIN_CASE_MAX_CELLS:
                raise Incomplete(f'case tables hold {held} cells, and table {table} adds {cells}, over TRAIN_CASE_MAX_CELLS={TRAIN_CASE_MAX_CELLS}')
            held += cells
            output.update(table=packet, status='complete' if not packet['missing'] else 'unknown')
            if packet['missing']:
                output['reason'] = 'case native table lacks required kept TRAIN entries'
            if item['selector']['fact'] == 'ex_input':
                output['input'] = _input_train(packet)
        except (ValueError, KeyError, IndexError, TypeError) as error:
            output.update(status='unknown', reason=str(error), error_type=type(error).__name__)
        if output['status'] != 'complete':
            gaps.append(dict(kind='train_table', table_id=item['table_id'],
                             reason=output['reason']))
        rows.append(output)
    return dict(schema='evaluator-case-train-v1', task=record['task'], case=case,
        ntrain=ntrain, **(dict(ntest=ntest) if test_rows else {}), **(dict(all_assignments=True) if all_assignments else {}),
        program_sha256=bundle['program_sha256'],
        kept_context_sha256=bundle['kept_context_sha256'], kept_assignments=deepcopy(kept),
        export=deepcopy(bundle['export']), tables=rows, gaps=gaps,
        native_table_inventory_complete=native is not None,
        train_tables_complete=native is not None and all(item['status'] == 'complete' for item in rows),
        receipt=dict(observation=bundle['receipt'], original_source_sha256=sha(record),
                     implementation=dependency_receipt(), test_cells=held_test > 0,
                     packing=dict(full_rows=True,
                                  native_full_rows=saved.get('replay', {}).get('engine_report', {}).get('full_rows'),
                                  source='native gold_tables packing',
                                  projection_cap_changed=False)))


def evaluate_train_clause(ev, record, clause, target, columns=None, explore=False):
    """Canonical checked result plus the original candidate's full TRAIN table.

    Checking may privately inspect TEST evidence, as required by the evaluator.
    Only the TRAIN adapter exports cells. The initial candidate capture is saved
    before gold/provenance instrumentation changes ev.captures. No second replay.
    """
    from checks import evaluate
    from surface import prepare
    saved = {}
    class Capture:
        def __getattr__(self, name):
            return getattr(ev, name)
        def replay_program(self, *args, **kwargs):
            result = ev.replay_program(*args, **kwargs)
            if not saved:
                saved['replay'] = result
                if result.get('engine') == 'ran':
                    saved['native'] = ev.captures[-1]['native']
            return result
    # Use the same preparation policy solely to recover its output alias map.
    try:
        _, _, proof = prepare(ev.legacy, record, clause, target['adapter'])
    except (ValueError, KeyError, IndexError, TypeError):
        proof = None
    result = evaluate(Capture(), record, clause, target, columns, explore=explore)
    if proof is None or 'native' not in saved:
        return result, None
    replay = saved['replay']
    table = replay.get('kept_coverage', {}).get('table')
    if table is None:
        return result, None
    try:
        acquired = acquire_candidate_train(ev, saved['native'], table, record,
            ntrain=target['ntrain'], proof=proof, columns=columns,
            source=dict(artifact=replay.get('artifact'), receipt=ev.receipt))
    except (ValueError, KeyError, IndexError, TypeError) as error:
        # A display/acquisition failure cannot rewrite the canonical verdict.
        result = dict(result, train_table_unavailable=dict(
            error_type=type(error).__name__, reason=str(error)))
        return result, None
    return result, acquired


def acquire_det_train_point(ev, record, adapter, ntrain, ntest, side='mutant', *, copy_rows=True,
                            include_projected_flows=False):
    """Actual mutant BODY or fresh gold BODY, certified public DET fields only.

    Gold uses the original native BODY and same-session gold FITS choices.
    No pair fallback, held-gold substitution, kind rewrite or checker bypass.
    """
    from evaluator import sha
    from tables import TargetStore, Incomplete, comparison_type
    from program_metadata import type_identity
    if side not in ('mutant', 'gold'):
        raise ValueError('point side must be mutant or gold')
    if (type(ntrain) is not int or ntrain < 1 or
            type(ntest) is not int or ntest < 0):
        raise Incomplete('DET TRAIN acquisition requires authenticated input axes')
    binding = adapter['bindings'][side]
    transport = adapter.get('det_projection_receipt', {})
    cert = binding.get('det_projection_receipt', {})
    if (binding.get('kind') != 'Det' or transport.get('schema') != 'mech3-det-header-projection-v1'
            or transport.get('complete') is not True or transport.get('source_sha256') != sha(record)
            or cert.get('schema') != 'judge3-det-binding-receipt-v1'
            or cert.get('scope') != 'TRAIN_features_only_noncallable'
            or cert.get('callable') is not False or binding.get('callable') is not False
            or binding.get('callable_template') is not None
            or cert.get('side') != side or cert.get('source_sha256') != sha(record)
            or cert.get('transport_sha256') != sha(transport)
            or cert.get('program_sha256') != sha(record[side+'_sexp'])
            or cert.get('export_sha256') != transport.get('sides', {}).get(side, {}).get('export_sha256')
            or cert.get('native_ref_sha256') != sha(record['native'][side])
            or binding.get('native_ref') != record['native'][side]
            or cert.get('source_body_schema_sha256') != sha(binding['source_body_schema'])
            or cert.get('projected_schema_sha256') != sha(binding['projected_schema'])
            or cert.get('callable_template_sha256') != sha(binding['callable_template'])
            or cert.get('projection_indices') != [f['source_body_column'] for f in binding['projected_schema']]
            or cert.get('body_path') != record['point']
            or cert.get('owner_path') != binding['owner_path']
            or cert.get('native_selector') != binding['native_selector']):
        raise Incomplete('source-bound certified DET header projection required')
    raw = transport['sides'][side]['raw_binding']
    if (raw.get('kind') != 'Det' or raw.get('body_path') != record['point']
            or raw.get('owner_path') != binding['owner_path']
            or raw.get('native_ref') != record['native'][side]
            or raw.get('native_table_index') != binding['native_table_index']
            or raw.get('native_selector') != binding['native_selector']
            or raw.get('program_sha256') != sha(record[side+'_sexp'])
            or raw.get('export_sha256') != cert.get('export_sha256')
            or raw.get('source_body_schema') != binding['source_body_schema']):
        raise Incomplete('DET target binding differs from its actual RAW source')
    fields = deepcopy(binding['projected_schema'])
    for field in fields:
        if field['source_body_column'] is not None:
            continue
        evidence = field.get('source_projection', {})
        unit = evidence.get('unit_projection_certificate', {})
        if (field['type'] != 'Unit' or unit.get('schema') != 'mech3-native-unit-projection-v1'
                or unit.get('native_header') != evidence.get('native_header')
                or unit.get('source_body_column') is not None
                or unit.get('proof') not in ('declared_layout', 'resolved_row_path')
                or unit.get('proof') != evidence.get('native_header', {}).get('proof')
                or evidence.get('native_header', {}).get('status') != 'declared_without_local_label'
                or unit.get('projection_helper') != 'judge2/render2/body.py:project_entries'):
            raise Incomplete('DET virtual Unit lacks its native header certificate')
        field['source_projection']['inserted_constant'] = dict(kind='unit', native_certificate=unit)
    source = dict(side=side, projection='certified native reader-named DET header union',
        transport_sha256=sha(transport), implementation=det_dependency_receipt(),
        native_gold_replays=0, native_mutant_replays=0, judge_admission=False)
    if side == 'mutant':
        store = TargetStore(ev.legacy, CODE_ROOT)
        native, table = store.mutant_snapshot(record, adapter)
        projection = [f['source_body_column'] for f in fields]
        source.update(native_ref=record['native']['mutant'], selector=binding['native_selector'])
    else:
        return _acquire_original_gold_train(ev, record,
            dict(binding, projected_schema=fields), ntrain, source=source, copy_rows=copy_rows)
    packet = acquire_train_table(ev, native, table, record, ntrain=ntrain,
        fields=fields, projection=projection, source=source, copy_rows=copy_rows,
        include_projected_flows=include_projected_flows)
    if packet['missing']:
        raise Incomplete('DET public TRAIN table lacks required own kept contexts')
    return packet


def acquire_train_point(ev, record, adapter, ntrain, ntest, side='mutant', *, copy_rows=True,
                        include_projected_flows=False):
    """Exact saved X or fresh original-scope gold BODY, TRAIN cells only.

    Gold FITS and BODY share one native handle/session. No RULE reconstruction
    changes the lexical owner context; public fields retain their native proof.
    """
    from tables import TargetStore, Incomplete
    if side not in ('mutant', 'gold'):
        raise ValueError('point side must be mutant or gold')
    if side=='mutant' and '_current_native_names' in adapter:
        from current_native_names import acquire_point
        return acquire_point(ev,record,adapter,ntrain,ntest,copy_rows=copy_rows,
                             include_projected_flows=include_projected_flows)
    if adapter.get('det_full_body') is not None:
        from det_full_body import acquire_det_full_body_train_point
        return acquire_det_full_body_train_point(ev,record,adapter,ntrain,ntest,side=side,
            copy_rows=copy_rows,include_projected_flows=include_projected_flows)
    binding = adapter['input']['binding'] if side == 'mutant' else adapter['comparison_target']['binding']
    if binding.get('kind') == 'Det':
        return acquire_det_train_point(ev, record, adapter, ntrain, ntest, side=side, copy_rows=copy_rows,
                                       include_projected_flows=include_projected_flows if side == 'mutant' else False)
    if side == 'mutant':
        store = TargetStore(ev.legacy, CODE_ROOT)
        native, table = store.mutant_snapshot(record, adapter)
        return acquire_train_table(ev, native, table, record, ntrain=ntrain,
            fields=binding['projected_schema'],
            projection=[field['source_body_column'] for field in binding['projected_schema']],
            source=dict(side=side, native_ref=record['native']['mutant'],
                        selector=binding['native_selector']), copy_rows=copy_rows,
            include_projected_flows=include_projected_flows)
    return _acquire_original_gold_train(ev, record, binding, ntrain, copy_rows=copy_rows)


def _acquire_original_gold_train(ev, record, binding, ntrain, *, ntest=0, test_rows=True, source=None, copy_rows=True):
    from tables import Incomplete
    from gold_body import capture,projection,projection_fields
    with capture(ev,record) as body:
        indices=projection(body,record,binding)
        fields=projection_fields(body,binding,indices)
        packet=acquire_train_table(body['ev'],body['native'],body['table'],record,ntrain=ntrain,ntest=ntest,test_rows=test_rows,
            fields=fields,projection=indices,
            held_entries=body['held_entries'],source=dict(source or {},side='gold',observation=body['receipt']),
            copy_rows=copy_rows)
        if packet['missing']:
            raise Incomplete('original gold BODY lacks required kept TRAIN entries')
        return packet
