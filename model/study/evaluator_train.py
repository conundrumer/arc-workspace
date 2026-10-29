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
    paths = (Path(__file__), Path(tables.__file__), Path(checks.__file__),
             Path(surface.__file__), CODE_ROOT / 'study_paths.py',
             CODE_ROOT / 'judge2/render2/body.py', CODE_ROOT / 'judge3/render_pair.py')
    return {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


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
    for field, index in zip(fields, projection):
        if index is None:
            evidence = field.get('source_projection', {})
            if (field['type'] != 'Unit' or
                    evidence.get('inserted_constant', {}).get('kind') != 'unit'):
                raise Incomplete('TRAIN projection lacks certified inserted Unit evidence')
        elif (type(index) is not int or not 0 <= index < len(schema)
              or comparison_type(schema[index]['type']) != comparison_type(field['type'])):
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
    if side == 'mutant':
        store = TargetStore(ev.legacy, CODE_ROOT)
        native = store.snapshot(record['native']['mutant'], adapter['source']['native_base'])
        ts = native['tables']
        # The certified report distinguishes ALL/KEPT tables sharing a selector.
        table = record['evaluation']['table_indices']['mutant_kept']
        if type(table) is not int or not 0 <= table < len(ts['form']):
            raise Incomplete('saved X kept table index is absent')
        if not all(str(ts[key][table]) == str(value)
                   for key, value in binding['native_selector'].items()
                   if key in ('form', 'point', 'relation', 'fact')):
            raise Incomplete('saved X report index differs from canonical BODY selector')
        expected = binding['source_body_schema']
        if [field['type'] for field in expected] != list(ts['column_types'][table]):
            raise Incomplete('saved X physical BODY types differ from canonical binding')
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
