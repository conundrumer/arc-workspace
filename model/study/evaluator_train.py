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
    paths = (Path(__file__), Path(tables.__file__), Path(checks.__file__),
             Path(surface.__file__), Path(case_collector.__file__),
             Path(program_metadata.__file__), Path(raw_body.__file__), CODE_ROOT / 'study_paths.py',
             CODE_ROOT / 'judge2/render2/body.py', CODE_ROOT / 'judge3/render_pair.py')
    return {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def det_dependency_receipt():
    """Actual DET metadata/reader/observer source closure, without prose."""
    paths = ('judge3/det_metadata.py', 'judge3/nonrender_metadata.py',
             'judge3/definition_binding.py', 'judge3/catalog.py',
             'judge2/render2/headers.py', 'judge2/render2/column_paths.py',
             'judge2/render2/structured.py', 'ast/run/mech3/det_receipt.py',
             'ast/run/mech3/reader_projection.py', 'ast/run/mech3/common.py',
             'ast/run/mech/run.py')
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


def acquire_train_table(ev, native, table, record, *, ntrain, fields=None,
                        projection=None, output_aliases=None, source=None):
    """Return full typed TRAIN cells at the case's local kept assignments.

    `native` is the canonical native payload/reader, not grouped value tuples.
    `fields` and `projection` must describe the exact canonical physical output
    layout. Repeated indices preserve aliases; None requires a certified Unit.
    Models are local to each (assignment, TRAIN input), never cross-table IDs.
    Missing kept contexts are explicit and do not become empty tables.
    """
    from tables import Incomplete, kept_entries, comparison_type
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
    matched = kept_entries(ev.legacy, metadata, ts['det_relations'][table],
                           ts['det_types'][table], record, ntrain, 0)
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
                    example_index=example, model=model, rows=deepcopy(projected)))
    return dict(fields=fields, entries=entries,
        required=[list(k) for k in sorted(matched['required'])],
        missing=[list(k) for k in matched['missing']],
        source_schema=schema, projection=projection, output_aliases=dict(output_aliases or {}),
        receipt=dict(source=deepcopy(source), source_sha256=sha(record), table=table,
            kept_context_sha256=sha(record['evaluation']['kept_assignments']),
            implementation=dependency_receipt(), test_cells=False,
            model_namespace='local to kept assignment and TRAIN input',
            task_broadcast='native TASK entries over authenticated TRAIN axis'))


def acquire_candidate_train(ev, native, table, record, *, ntrain, proof,
                            columns=None, source=None):
    """Apply the canonical candidate's exported labels and resolved aliases."""
    from surface import tokens
    from tables import Incomplete
    ts = native['tables']
    names = list(ts['column_names'][table])
    exported = {t.lstrip('*^') for t in tokens(proof['canonical']) if t.startswith(('*', '^'))}
    if len(set(names)) != len(names):
        raise Incomplete('candidate native output labels are ambiguous')
    outputs = [(name, i) for i, name in enumerate(names) if name in exported]
    aliases = proof.get('output_aliases', {})
    for alias, original in aliases.items():
        if alias not in exported:
            continue
        if original not in names:
            raise Incomplete('candidate alias source is absent from native output')
        outputs.append((alias, names.index(original)))
    if len({name for name, _ in outputs}) != len(outputs):
        raise Incomplete('candidate output alias is ambiguous')
    if columns is not None:
        by_name = dict(outputs)
        if any(name not in by_name for name in columns):
            raise Incomplete('requested candidate output column is absent')
        outputs = [(name, by_name[name]) for name in columns]
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
    """
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
                     implementation=dependency_receipt(), test_cells=False))


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


def acquire_det_train_point(ev, record, adapter, ntrain, ntest, side='mutant'):
    """Actual mutant BODY or fresh gold BODY, certified public DET fields only.

    One ordinary gold observer replay; zero mutant replays. There is no pair
    fallback, held-gold substitution, kind rewrite or clause-checker bypass.
    """
    from evaluator import sha
    from tables import TargetStore, Incomplete, comparison_type
    from program_metadata import type_identity
    from raw_body import body_observer_program
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
        selected = list(dict.fromkeys(f['source_body_column'] for f in fields
                                     if f['source_body_column'] is not None))
        raw_fields = {f['source_body_column']: f for f in raw['projected_schema']}
        if any(index not in raw_fields for index in selected):
            raise Incomplete('DET selected header lacks its exact RAW physical binding')
        layout = dict(raw, projected_schema=[raw_fields[index] for index in selected])
        if raw.get('scope') == 'TaskWide':
            reason = ('DET gold BODY has TaskWide scope; the RULE observer is PerInput. '
                      'Native original-scope BODY acquisition is required')
            folder = ev.artifacts / ('det-scoped-body-required-'+sha(dict(
                source=sha(record), transport=sha(transport), layout=layout)))
            folder.mkdir(exist_ok=True)
            (folder/'program.arclog').write_text(record['gold_sexp']+'\n')
            (folder/'receipt.json').write_text(json.dumps(dict(reason=reason,
                source_sha256=sha(record), transport_sha256=sha(transport),
                original_scope=raw['scope'], body_path=raw['body_path'],
                original_program_sha256=sha(record['gold_sexp']),
                native_gold_replays=0, native_mutant_replays=0), indent=2)+'\n')
            raise Incomplete(reason+'; artifact='+str(folder))
        observed, form, context = body_observer_program(ev, record, layout)
        own = dict(record, mutant_sexp=record['gold_sexp'])
        replay = ev.replay_program(own, observed, form,
            candidate=dict(kind='mechanical-DET-public-gold-observer',
                           source_sha256=sha(record), transport_sha256=sha(transport)))
        if replay['engine'] != 'ran':
            raise Incomplete('DET gold observer incomplete: '+replay.get('reason', replay['engine'])+
                             '; artifact='+replay['artifact'])
        table = replay.get('kept_coverage', {}).get('table')
        if table is None:
            raise Incomplete('DET gold observer has no exact kept native table')
        native = ev.captures[-1]['native']
        names = list(native['tables']['column_names'][table])
        columns = {}
        for ordinal, index in enumerate(selected):
            name = 'V'+str(ordinal)
            if names.count(name) != 1:
                raise Incomplete('DET gold observer lacks an unambiguous selected output')
            physical = names.index(name)
            if comparison_type(type_identity(ev,record,native['tables']['column_types'][table][physical])[0]) != comparison_type(type_identity(ev,record,raw_fields[index]['type'])[0]):
                raise Incomplete('DET gold observer output type differs from certified BODY field')
            columns[index] = physical
        projection = [None if f['source_body_column'] is None else columns[f['source_body_column']]
                      for f in fields]
        source.update(native_gold_replays=1, artifact=replay['artifact'],
            original_gold_program_sha256=sha(record['gold_sexp']),
            observer_program_sha256=sha(observed), kept_context_sha256=sha(record['evaluation']['kept_assignments']),
            observer_context=context, target_test_fit_claim=False)
    packet = acquire_train_table(ev, native, table, record, ntrain=ntrain,
        fields=fields, projection=projection, source=source)
    if packet['missing']:
        raise Incomplete('DET public TRAIN table lacks required own kept contexts')
    return packet


def acquire_train_point(ev, record, adapter, ntrain, ntest, side='mutant'):
    """Exact saved kept X or fresh canonical full-gold G observer, TRAIN only.

    Missing INIT outer-key values are unsupported; no inferred key joins or
    raw/private-column replacements. G uses a fresh observer even if value-only
    gold groups were cached, because those groups do not retain typed geometry.
    """
    from tables import TargetStore, Incomplete
    if side not in ('mutant', 'gold'):
        raise ValueError('point side must be mutant or gold')
    binding = adapter['input']['binding'] if side == 'mutant' else adapter['comparison_target']['binding']
    if binding.get('kind') == 'Det':
        return acquire_det_train_point(ev, record, adapter, ntrain, ntest, side=side)
    if side == 'mutant':
        store = TargetStore(ev.legacy, CODE_ROOT)
        native, table = store.mutant_snapshot(record, adapter)
        return acquire_train_table(ev, native, table, record, ntrain=ntrain,
            fields=binding['projected_schema'],
            projection=[field['source_body_column'] for field in binding['projected_schema']],
            source=dict(side=side, native_ref=record['native']['mutant'],
                        selector=binding['native_selector']))
    from checks import observe_gold
    saved = {}
    class Observer:
        target_cache = None
        def __init__(self):
            self.target_cache = {}  # Value-only cache cannot serve typed cells.
        def __getattr__(self, name):
            return getattr(ev, name)
        def replay_program(self, *args, **kwargs):
            result = ev.replay_program(*args, **kwargs)
            saved['replay'] = result
            if result.get('engine') == 'ran':
                saved['native'] = ev.captures[-1]['native']
            return result
    _, receipt = observe_gold(Observer(), record, adapter, binding, ntrain, ntest)
    if 'native' not in saved:
        raise Incomplete('fresh gold observer has no typed native capture')
    native = saved['native']
    table = saved['replay'].get('kept_coverage', {}).get('table')
    if table is None:
        raise Incomplete('fresh gold observer table identity is unavailable')
    names = list(native['tables']['column_names'][table])
    fields = binding['projected_schema']
    labels = ['V'+str(i) for i in range(len(fields))]
    if any(names.count(label) != 1 for label in labels):
        raise Incomplete('canonical gold observer output labels are absent or ambiguous')
    return acquire_train_table(ev, native, table, record, ntrain=ntrain,
        fields=fields, projection=[names.index(label) for label in labels],
        source=dict(side=side, observation=receipt))
