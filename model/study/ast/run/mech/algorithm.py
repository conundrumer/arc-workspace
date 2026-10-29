"""Mechanical labels from authenticated native evidence.

Fresh implementation of the mechanical-label specification. Shared storage,
decoding, model-family semantics, search and verification stay in STUDY_RUN.
P and briefs/progsynth.md are behavioral references, not implementation sources.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
from dataclasses import dataclass
import os
import sys
import time
from types import FunctionType

sys.path.insert(0, os.environ.get('STUDY_RUN', str(CODE_ROOT / 'ast/run')))
from native_storage import load_native
from filters import native, rows_at
from next_revision import family_recovery as recovery

NUMBERS = frozenset(('Number', 'number'))
BOX_VALUES = frozenset(('Box', 'Position', 'Offset'))
ORDERED = ('eq', 'ne', 'lt', 'le', 'gt', 'ge')
EQUALITY = ('eq', 'ne')


def permitted_comparisons(types, universe, budget, *, geometric):
    """Executable constants come from the language, never from target rows."""
    for column, dtype in enumerate(types):
        if (dtype in BOX_VALUES) != geometric:
            continue
        literal = (0,) if dtype in NUMBERS else (0, 0, 0, 0) if dtype in BOX_VALUES else None
        if literal is not None:
            for operator in ORDERED if dtype in NUMBERS else EQUALITY:
                budget()
                yield dict(kind='comparison', left=column, op=operator, value=list(literal))
        for other in range(column + 1, len(types)):
            if types[other] == dtype:
                for operator in ORDERED if dtype in NUMBERS else EQUALITY:
                    budget()
                    yield dict(kind='comparison', left=column, right=other, op=operator)


def bind_function(function, **bindings):
    """Reuse shared bytecode with owned configuration, without a global patch."""
    scope = dict(function.__globals__)
    scope.update(bindings)
    bound = FunctionType(function.__code__, scope, function.__name__,
                         function.__defaults__, function.__closure__)
    bound.__kwdefaults__ = function.__kwdefaults__
    return bound


# Projection/support search and its independent direct verifier are unchanged.
ATOM_PROVIDER = bind_function(recovery._atoms, _comparison_atoms=permitted_comparisons)
FIND_WITNESS = bind_function(recovery.witness, _atoms=ATOM_PROVIDER)


def unknown(reason, reason_code='evidence_incomplete'):
    return dict(status='unknown', recoverable=None, reason=str(reason), reason_code=reason_code)


def solve(target_types, target, source_types, source, available, seconds):
    try:
        proof = FIND_WITNESS(target_types, target, source_types, source,
                             available, seconds=seconds, max_states=20000)
    except recovery.SearchBound as exc:
        return unknown(exc, 'search_bound')
    except (ValueError, KeyError, IndexError) as exc:
        return unknown(f'{type(exc).__name__}: {exc}')
    if proof.get('recoverable') and proof.get('verified') is not True:
        raise ValueError('shared search returned a positive without direct verification')
    return proof


def selector_shape(proof):
    branches = proof.get('selection_any', [proof.get('selection', [])])
    categories = set()
    for branch in branches:
        for atom in branch:
            category = atom['kind']
            if category == 'comparison':
                category += '-const' if 'value' in atom else '-cols'
            categories.add(category)
    return '+'.join(sorted(categories)) or 'projection-only', len(branches)


def truth_of_searches(proofs, complete=True):
    if any(proof.get('recoverable') is True for proof in proofs):
        return True
    if not complete or any(proof.get('status') == 'unknown' for proof in proofs):
        return None
    return False


def source_name(table):
    identity = table['identity']
    return identity.get('fact') or identity.get('form')


def training_scope(record, gold):
    """Require agreement between available explicit train axes."""
    scopes = []
    tables, entries = gold['tables'], gold['entries']
    inputs = {t for t, fact in enumerate(tables['fact']) if fact == 'ex_input'}
    if not inputs:
        raise ValueError('gold snapshot lacks ex_input identity')
    native_scope = {entries['example_index'][e] for e, owner in enumerate(entries['table'])
                    if owner in inputs and entries['example_kind'][e] == 1}
    if native_scope:
        scopes.append(native_scope)
    for output in record['evaluation'].get('outputs', []):
        examples = output.get('gold_train')
        if examples:
            scopes.append({example['example'] for example in examples})
    if not scopes:
        raise ValueError('no explicit training-input scope')
    scope = scopes[0]
    if any(candidate != scope for candidate in scopes):
        raise ValueError('native and saved output training-input scopes disagree')
    if scope != set(range(len(scope))):
        raise ValueError('training-input scope is not contiguous from zero')
    return len(scope)


@dataclass
class Observation:
    snapshot: dict
    table: int
    maps: list
    types: tuple
    families: tuple

    @classmethod
    def read(cls, snapshot, table, maps, assignments, trains):
        schema, rows, _ = rows_at(snapshot, table)
        families, _ = recovery.kept_families(snapshot, table, rows, maps, assignments, trains)
        return cls(snapshot, table, maps, tuple(dtype for dtype, frame in schema), tuple(families))

    def test_family(self, assignment):
        """Only explicit kept-map test axes admit verification evidence."""
        reader = self.snapshot['_native_reader']
        maps = [item for item in self.maps if item['table'] == self.table]
        if len(maps) != 1:
            raise ValueError('test family lacks unique table map')
        entries = reader.bytable[self.table]
        groups = {}
        for item in maps[0]['entries']:
            if item['example_kind'] != 'test':
                continue
            kept = item.get('kept_assignment')
            if type(kept) is not int or not 0 <= kept < len(self.families):
                raise ValueError('test entry lacks explicit kept assignment')
            if kept != assignment:
                continue
            entry = reader.entry(entries[item['table_entry']], with_extents=False, projection_stop=False)
            rows = frozenset(tuple(tuple(cell['value']) for cell in row) for row in entry['rows'])
            groups.setdefault(item['example_index'], set()).add(rows)
        if not groups:
            raise ValueError('no mapped test inputs')
        input_tables = {t for t, fact in enumerate(reader.tables['fact']) if fact == 'ex_input'}
        expected = {reader.entries['example_index'][entry]
                    for table in input_tables for entry in reader.bytable[table]
                    if reader.entries['example_kind'][entry] == 2}
        if not expected or set(groups) != expected:
            raise ValueError('mapped tests do not cover the explicit test-input scope')
        axes = tuple(sorted(groups))
        return axes, tuple(frozenset(groups[index]) for index in axes)


def scoped_input(table):
    """Expose an input fact at its per-input callable interface."""
    if not table['types'] or table['types'][0] != 'Example':
        return table
    rows = tuple(frozenset(row[1:] for row in values if row[0] == (train,))
                 for train, values in enumerate(table['rows']))
    return dict(table, types=table['types'][1:], rows=rows,
                identity=dict(table['identity'], example_scope='train-local; leading Example removed'))


def inventory(record, base, gold, trains, assignments):
    """Acquire all available sources before invoking ANY recovery search.

    Earlier forms require explicit full-kept maps. Model ordinals or agreement
    with a partial DET signature do not certify a callable available table.
    """
    issues = []; tables = {assignment: [] for assignment in range(assignments)}
    try:
        replay = record['full_replay']
        evidence = replay['evaluation']
        if replay.get('scope') != 'gold_full_kept' or replay.get('ident_namespace') != 'shared task evaluator session':
            raise ValueError('full replay lacks shared-session full-kept scope')
        if evidence.get('kept_assignments') != record['evaluation']['kept_assignments']:
            raise ValueError('full replay kept assignments differ from pair scope')
        if (evidence.get('gold_status', {}).get('status') != 'complete'
                or evidence.get('gold_collection', {}).get('materialization_complete') is not True
                or evidence.get('gold_observation_stop') is not None):
            issues.append(dict(scope='full_replay', reason='gold inventory acquisition is incomplete'))
        full_gold = native(load_native(replay['gold'], base))
        tables, missing = recovery.available_tables(
            full_gold, evidence.get('gold_assignment_map', []),
            record['evaluation']['kept_assignments'], trains, record['point'], None, rows_at)
        issues.extend(missing)
    except (ValueError, KeyError, IndexError, OSError) as exc:
        issues.append(dict(scope='full_replay', reason=f'{type(exc).__name__}: {exc}'))

    # Missing replay never justifies guessing earlier forms. A canonical,
    # DET-independent input fact can still be certified from the kept snapshot.
    if any(not any(table['identity'].get('fact') == 'ex_input' for table in tables[a])
           for a in range(assignments)):
        for number, fact in enumerate(gold['tables']['fact']):
            if fact != 'ex_input':
                continue
            try:
                schema, rows, _ = rows_at(gold, number)
                values, evidence = recovery._input_fact(gold, number, rows, trains)
                source = dict(types=tuple(dtype for dtype, frame in schema), rows=values,
                              identity=dict(fact='ex_input', table=number,
                                            proof='det_independent_native_fact', entries=evidence))
                for assignment in tables:
                    if not any(table['identity'].get('fact') == 'ex_input' for table in tables[assignment]):
                        tables[assignment].append(source)
            except (ValueError, KeyError, IndexError) as exc:
                issues.append(dict(scope='ex_input', table=number, reason=str(exc)))
    available = tuple(tuple(scoped_input(table) if table['identity'].get('fact') == 'ex_input'
                            else table for table in tables[a]) for a in range(assignments))
    return available, issues


def baseline_searches(gold, mutant, assignment, available, seconds):
    """Both independent targets share source-family preparation, not results."""
    sibling = []; redundant = []
    for index, table in enumerate(available):
        family = tuple(frozenset((rows,)) for rows in table['rows'])
        companions = available[:index] + available[index + 1:]
        companion_indices = [i for i in range(len(available)) if i != index]
        for observation, proofs in ((gold, sibling), (mutant, redundant)):
            proof = solve(observation.types, observation.families[assignment], table['types'],
                          family, companions, seconds)
            evidence = dict(proof, source=source_name(table), source_index=index,
                            companion_indices=companion_indices)
            if proof.get('recoverable'):
                evidence['shape'] = selector_shape(proof)[0]
            proofs.append(evidence)
    return sibling, redundant


def generalization(gold, mutant, assignment, witness):
    if not witness.get('recoverable'):
        return None, 'no train witness'
    branches = witness.get('selection_any', [witness.get('selection', [])])
    if any(atom['kind'] in ('semijoin', 'antijoin') for branch in branches for atom in branch):
        return None, 'witness reads available tables; no test inventory'
    try:
        gold_axes, expected = gold.test_family(assignment)
        mutant_axes, source = mutant.test_family(assignment)
        if gold_axes != mutant_axes:
            raise ValueError('gold/mutant test input axes disagree')
        return recovery.verify(expected, source, witness, (), mutant_types=mutant.types), None
    except (ValueError, KeyError, IndexError) as exc:
        return None, f'{type(exc).__name__}: {exc}'


def native_fits(evaluation):
    outputs = evaluation.get('outputs', [])
    return bool(outputs) and all(bool(output.get('mutant', {}).get('train'))
                                 and all(example.get('fits') is True for example in output['mutant']['train'])
                                 for output in outputs)


def classify(record, assignments, inventory_complete, error):
    """Six labels depend on evidence, never the old DETOUR/WRONG verdict."""
    evaluation = record['evaluation']
    comparisons = evaluation.get('kept_comparisons', [])
    relations = sorted({entry.get('relation') for entry in comparisons}, key=str)
    compared = bool(comparisons) and all(entry.get('status') == 'complete' and entry.get('comparable')
                                         for entry in comparisons)
    contains = compared and all(entry.get('relation') in ('equal', 'superset') and not entry.get('missing')
                                for entry in comparisons)
    fits = native_fits(evaluation)
    selected = not error and bool(assignments) and all(item.get('recoverable') is True for item in assignments)
    identity = selected and all(item['projection'] == list(range(len(item['projection']))) for item in assignments)
    first = assignments[0] if assignments and not error else {}
    if relations == ['equal']:
        label = 'equivalent'
    elif fits:
        label = 'fits'
    elif selected and first.get('shape') == 'projection-only' and identity:
        label = 'extension'
    elif contains or selected:
        label = 'overapproximation'
    elif compared:
        label = 'lossy'
    else:
        label = 'undetermined'

    sibling = truth_of_searches(first.get('sibling_searches', []), inventory_complete and not error)
    redundant_searches = [proof for item in assignments for proof in item['redundant_searches']]
    redundant = truth_of_searches(redundant_searches, inventory_complete and not error) if not error else None
    if error:
        search = 'error'
    elif any(item['status'] == 'unknown' for item in assignments):
        search = 'unknown'
    elif not selected:
        search = 'WRONG/unrecoverable'
    elif any(item.get('test_verified') is False for item in assignments):
        search = 'WRONG/memorized'
    elif any(item['baseline'] for item in assignments):
        search = 'WRONG/no_signal'
    elif all(item['shape'] == 'projection-only' for item in assignments):
        search = 'VARIANT'
    elif not inventory_complete or any(truth_of_searches(item['sibling_searches']) is None for item in assignments):
        search = 'unknown'
    else:
        search = 'DETOUR'
    original = record.get('filters', {}).get('recoverable_gold', {})
    return dict(label=label, fits=fits, selection_found=bool(selected),
                generalizes=first.get('test_verified'), sibling=sibling,
                sibling_source=sorted({'ex_input' if proof['source'] == 'ex_input' else 'form'
                                       for proof in first.get('sibling_searches', []) if proof.get('recoverable')}),
                redundant=redundant,
                redundant_from=[dict(proof, assignment=item['assignment']) for item in assignments
                                for proof in item['redundant_searches'] if proof.get('recoverable')],
                rename=bool(selected and not identity), shape=first.get('shape'),
                search=search, rerun=search, relation=relations, table_relation=relations,
                missing=sum(entry.get('missing') or 0 for entry in comparisons),
                extra=sum(entry.get('extra') or 0 for entry in comparisons),
                onpath=not record.get('filters', {}).get('no_dependency_path', {}).get('reject', True),
                recovery_status=original.get('status'), recovery_reason=original.get('reason_code'))


def one_pair(record, base, seconds=1.0, baseline_seconds=.5):
    started = time.monotonic(); assignments = []; issues = []; error = None
    try:
        evaluation = record['evaluation']; count = len(evaluation['kept_assignments'])
        if count == 0:
            raise ValueError('pair has no full kept assignments')
        gold_native = native(load_native(record['native']['gold'], base))
        mutant_native = native(load_native(record['native']['mutant'], base))
        trains = training_scope(record, gold_native)
        available, issues = inventory(record, base, gold_native, trains, count)
        # Inventory acquisition precedes even a projection-only witness.
        gold = Observation.read(gold_native, evaluation['table_indices']['gold_kept'],
                                evaluation['gold_kept_assignment_map'], count, trains)
        mutant = Observation.read(mutant_native, evaluation['table_indices']['mutant_kept'],
                                  evaluation['mutant_kept_assignment_map'], count, trains)
        for ordinal, sources in enumerate(available):
            witness = solve(gold.types, gold.families[ordinal], mutant.types,
                            mutant.families[ordinal], sources, seconds)
            sibling, redundant = baseline_searches(gold, mutant, ordinal, sources, baseline_seconds)
            verified, test_reason = generalization(gold, mutant, ordinal, witness)
            item = dict(assignment=ordinal, status=witness['status'], recoverable=witness.get('recoverable'),
                        reason=witness.get('reason'), witness=witness, test_verified=verified,
                        test_reason=test_reason, sibling_searches=sibling, redundant_searches=redundant,
                        available=[source_name(source) for source in sources],
                        available_metadata=[dict(types=source['types'], identity=source['identity']) for source in sources],
                        baseline=[dict(source=proof['source'], shape=proof['shape']) for proof in sibling
                                  if proof.get('recoverable')])
            if witness.get('recoverable'):
                item['shape'], item['branches'] = selector_shape(witness)
                item['projection'] = witness['projection']
                item['literal_only'] = item['shape'] == 'comparison-const'
            assignments.append(item)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    result = classify(record, assignments, not issues, error)
    result.update(per_assignment=assignments, available_incomplete=issues,
                  seconds=round(time.monotonic() - started, 6))
    if error:
        result['error'] = error
    return result
