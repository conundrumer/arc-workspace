"""Full TRAIN typed-cell transport for dataset consumers.

This adapter does no replay on import or table acquisition. Matching and cell
projection delegate to the existing evaluator and canonical producer. TEST
entries are excluded before assignment inspection or cell decoding.
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
             Path(program_metadata.__file__), Path(raw_body.__file__), Path(gold_body.__file__), CODE_ROOT / 'study_paths.py', CODE_ROOT / 'native_correspondence.py',
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


def train_entry_contexts(ev, native, table, record, *, ntrain, held_entries=None):
    """Canonical kept TRAIN/TASK selection before any value/extent decoding."""
    from tables import Incomplete, kept_entries
    if type(ntrain) is not int or ntrain < 1:
        raise Incomplete('TRAIN acquisition requires the authenticated train input count')
    reader = native['_native_reader']
    # Only assignment metadata is read for eligible entries. Dummy rows allow
    # the canonical matcher to select contexts without decoding any value rows.
    metadata = []
    for index in reader.bytable[table]:
        kind = reader.entries['example_kind'][index]
        if kind not in (0, 1):
            continue
        example = reader.entries['example_index'][index]
        if kind == 1 and not 0 <= example < ntrain:
            raise Incomplete('native TRAIN entry is outside the authenticated input axis')
        metadata.append(dict(entry=index, example=(kind, example),
            model=reader.entries['model'][index], rows=(),
            assignment=tuple(sorted((d['relation'], tuple(tuple(r) for r in d['rows']))
                                    for d in reader.assignment(index)))))
    ts = native['tables']
    return kept_entries(ev.legacy, metadata, ts['det_relations'][table],
                           ts['det_types'][table], record, ntrain, 0, held_entries=held_entries)


def select_train_full_rows(ev, native, record, *, ntrain):
    """Pure mask/receipt from canonical kept metadata; no packed owner escapes."""
    from tables import axis_receipt
    reader = native['_native_reader']
    selected = set()
    tables = []
    for table in range(len(native['tables']['form'])):
        proof = dict(table=table)
        try:
            matched = train_entry_contexts(ev, native, table, record, ntrain=ntrain)
            proof.update(status='matched', **axis_receipt(matched))
            proof['entries'] = []
            table_entries = set()
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
    return dict(schema='evaluator-train-entry-mask-v1', entries=sorted(selected),
                tables=tables, test_entries_selected=False,
                selection='canonical kept_entries over native TRAIN/TASK metadata')


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


def acquire_train_table(ev, native, table, record, *, ntrain, fields=None,
                        projection=None, output_aliases=None, source=None, held_entries=None, copy_rows=True,
                        include_projected_flows=False):
    """Return full typed TRAIN cells at the case's local kept assignments.

    `native` is the canonical native payload/reader, not grouped value tuples.
    `fields` and `projection` must describe the exact canonical physical output
    layout. Repeated indices preserve aliases; None requires a certified Unit.
    Models are local to each (assignment, TRAIN input), never cross-table IDs.
    Missing kept contexts are explicit and do not become empty tables.
    copy_rows=False shares read-only projected rows across local contexts; the
    synchronous feature writer retains them until serialization completes.
    """
    if type(copy_rows) is not bool:
        raise ValueError("copy_rows must be boolean")
    if type(include_projected_flows) is not bool:
        raise ValueError("include_projected_flows must be boolean")
    from tables import Incomplete, comparison_type
    from program_metadata import type_identity, typed_fields
    from evaluator import sha
    if type(ntrain) is not int or ntrain < 1:
        raise Incomplete('TRAIN acquisition requires the authenticated train input count')
    reader = native['_native_reader']
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
        if index is None:
            evidence = field.get('source_projection', {})
            if (field['type'] != 'Unit' or
                    evidence.get('inserted_constant', {}).get('kind') != 'unit'):
                raise Incomplete('TRAIN projection lacks certified inserted Unit evidence')
        elif (type(index) is not int or not 0 <= index < len(schema)
              or comparison_type(type_identity(ev, record, schema[index]['type'])[0]) != comparison_type(field['type'])):
            raise Incomplete('TRAIN projected field type or physical index differs')

    matched = train_entry_contexts(ev, native, table, record, ntrain=ntrain, held_entries=held_entries)
    entries = []
    model_counts = {}
    for context in matched['contexts']:
        index = context['entry']
        # The kind gate above precedes this sole value/geometry decoder.
        decoded = reader.entry(index, with_extents=True, projection_stop=False)
        if decoded['example_kind'] not in (0, 1):
            raise Incomplete('native entry example kind changed during TRAIN acquisition')
        # TASK facts may themselves contain test Example values. Filter with
        # the producer policy before projection can hide the Example column.
        decoded = _visibility()(SimpleNamespace(ntrain=ntrain), decoded, schema)
        projected = _projector()(dict(entries=[dict(decoded, choice=None)]), projection)[0]['rows']
        examples = range(ntrain) if decoded['example_kind'] == 0 else [decoded['example_index']]
        for assignment in context['kept_assignments']:
            for example in examples:
                axis = (assignment, 1, example)
                model = model_counts.get(axis, 0)
                model_counts[axis] = model + 1
                entries.append(dict(assignment=assignment, example_kind=1,
                    example_index=example, model=model, rows=deepcopy(projected) if copy_rows else projected))
    packet = dict(fields=fields, entries=entries,
        required=[list(k) for k in sorted(matched['required'])],
        missing=[list(k) for k in matched['missing']],
        source_schema=schema, projection=projection, output_aliases=dict(output_aliases or {}),
        receipt=dict(source=deepcopy(source), source_sha256=sha(record), table=table,
            kept_context_sha256=sha(record['evaluation']['kept_assignments']),
            implementation=dependency_receipt(), test_cells=False,
            model_namespace='local to kept assignment and TRAIN input',
            task_broadcast='native TASK entries over authenticated TRAIN axis'))
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


def acquire_input_train(ev, native, table, record, *, ntrain, source=None):
    """Expose per-input `input` from the exact native `ex_input` fact table.

    Kept matching, TRAIN visibility, TASK broadcast and typed-cell decoding are
    the same as acquire_train_table. Restrict the native Example column to the
    destination TRAIN input before removing it with the canonical projector.
    Use acquire_train_table separately to retain the full `ex_input` relation.
    """
    from tables import Incomplete
    if native['tables']['fact'][table] != 'ex_input':
        raise Incomplete('input TRAIN acquisition requires the native ex_input fact')
    packet = acquire_train_table(ev, native, table, record, ntrain=ntrain, source=source)
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
        rows = [row for row in entry['rows']
                if row[example_column]['value'] == [entry['example_index']]]
        projected = _projector()(dict(entries=[dict(entry, rows=rows,
            example='train'+str(entry['example_index']+1), choice=entry['assignment'])]),
            projection)[0]['rows']
        entries.append(dict(entry, rows=deepcopy(projected)))
    return dict(packet, fields=[deepcopy(packet['fields'][i]) for i in projection],
        entries=entries, projection=projection,
        receipt=dict(packet['receipt'], input_projection=dict(
            source_fact='ex_input', relation='input', example_column=example_column,
            rule='Example equals destination TRAIN index before Example column removal')))


def acquire_case_train(ev, record, case_context, ntrain, ntest):
    """One fresh canonical case replay, original table inventory and TRAIN cells.

    Persist this packet once per task/case/settings in the exporter. Every call
    requests one fresh replay; there is no per-pair replay or whole-study cache.
    Missing own-case kept values add one separately receipted native gold-only
    TRAIN FITS observation, reused for identical source/settings/task inputs.
    The full native export graph is metadata, not a grant of clause availability.
    BODY observers are explicitly disabled: this surface returns original
    native tables only. Point G is acquired independently by acquire_train_point.
    No native handle or private TEST table transport escapes this surface.
    Each case owns a fresh native session through replay and typed extraction;
    closing it releases prior-case arenas without changing operation bounds.
    """
    with ev.fresh_session() as isolated:
        packet = _acquire_case_train(isolated, record, case_context, ntrain, ntest)
        packet['receipt']['session'] = dict(
            scope='independent case replay and typed TRAIN extraction',
            lifetime='closed before returning JSON packet',
            session_bytes=isolated.receipt['session_bytes'],
            extra_replays=0)
        return packet


def _acquire_case_train(ev, record, case_context, ntrain, ntest):
    """Materialize one case while its independent native session is alive."""
    from case_collector import acquire_case, _context, clear_cache
    from tables import Incomplete
    from evaluator import sha
    from program_metadata import type_identity
    if (type(ntrain) is not int or ntrain < 1 or
            type(ntest) is not int or ntest < 0):
        raise Incomplete('case TRAIN acquisition requires authenticated input axes')
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
            kwargs['full_rows_selector'] = lambda native: select_train_full_rows(
                ev, native, own, ntrain=ntrain)
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
            packet = acquire_train_table(ev, native, table, own, ntrain=ntrain,
                fields=fields, projection=list(range(len(fields))),
                source=dict(identity, case=case, observation=bundle['receipt']))
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
        ntrain=ntrain, program_sha256=bundle['program_sha256'],
        kept_context_sha256=bundle['kept_context_sha256'], kept_assignments=deepcopy(kept),
        export=deepcopy(bundle['export']), tables=rows, gaps=gaps,
        native_table_inventory_complete=native is not None,
        train_tables_complete=native is not None and all(item['status'] == 'complete' for item in rows),
        receipt=dict(observation=bundle['receipt'], original_source_sha256=sha(record),
                     implementation=dependency_receipt(), test_cells=False,
                     packing=dict(full_rows=True,
                                  native_full_rows=saved.get('replay', {}).get('engine_report', {}).get('full_rows'),
                                  source='native gold_tables packing',
                                  selection=saved.get('replay', {}).get('packing_selection'),
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


def _acquire_original_gold_train(ev, record, binding, ntrain, *, source=None, copy_rows=True):
    from tables import Incomplete
    from gold_body import capture,projection
    with capture(ev,record) as body:
        indices=projection(body,record,binding)
        packet=acquire_train_table(body['ev'],body['native'],body['table'],record,ntrain=ntrain,
            fields=binding['projected_schema'],projection=indices,
            held_entries=body['held_entries'],source=dict(source or {},side='gold',observation=body['receipt']),
            copy_rows=copy_rows)
        if packet['missing']:
            raise Incomplete('original gold BODY lacks required kept TRAIN entries')
        return packet
