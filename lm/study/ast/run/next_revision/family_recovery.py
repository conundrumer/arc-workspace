"""Whole-family DETOUR proof over complete native kept-assignment evidence.

One fixed typed selection/comparison/semijoin/antijoin and projection maps each mutant
model family onto the gold family, as SETS, separately at every train input.
No model numbers are paired between programs. Every positive is reverified.
"""
from collections import defaultdict
from itertools import product, combinations
import time


def final_definition(program, body_path, out_binding):
    """Native typed identity proof shared by producer and saved-record audit.

    No stream spellings, path-marker heuristics, or numeric LabelId conversion.
    Return classification and exact native owner/OUT evidence for persistence.
    """
    bodies = [b for b in program['body_views'] if b['body_path'] == list(body_path)]
    if len(bodies) != 1:
        raise ValueError('missing or ambiguous native body owner')
    owner_path = bodies[0]['owner_path']
    owners = [n for n in program['nodes'] if n['path'] == owner_path]
    if len(owners) != 1:
        raise ValueError('missing or ambiguous native owner node')
    definition = owners[0]['data'].get('defines')
    out_path = out_binding['path']
    reads = []
    for node in program['nodes']:
        if node['path'][:len(out_path)] != out_path or node['kind'] != 'atom':
            continue
        relation = node['data']['relation']
        if 'declared' in relation:
            reads.append(dict(path=node['path'], identity=relation['declared']))
    if definition is None:
        final = False
    elif definition.get('kind') == 'declared' and definition.get('name', {}).get('kind') == 'slot':
        final = any(r['identity'] == {'slot': definition['name']['slot']} for r in reads)
    else:
        raise ValueError('unsupported native definition identity')
    return dict(final_output=final, body_path=list(body_path), owner_path=owner_path,
                definition=definition, out_path=out_path, out_reads=reads)


class Incomplete(ValueError):
    pass


def _kept_index(value, name, upper=None):
    if type(value) is not int or value < 0 or (upper is not None and value >= upper):
        raise Incomplete('invalid kept-map ' + name)
    return value


def kept_entry_groups(native, table, maps, nkept, ntrain):
    """Return (groups, evidence) using one structural full-kept matcher.

    groups[assignment][train] is a tuple of GLOBAL native entry IDs, preserving
    map order. Task entries broadcast to every train; train entries stay local.
    All table entries, including test entries, require exact table-local map
    coverage and matching native example/model axes. Test entries are excluded
    only after that validation, with their kept-assignment field unused as in
    v4. Selected train/task entries require explicit full-kept ordinals.

    This function does not decode rows or decide emptiness/completeness. Callers
    must validate every selected entry through Native.count or their row reader.
    Evidence retains the existing per-assignment native_entry map dictionaries.
    """
    try:
        return _kept_entry_groups(native, table, maps, nkept, ntrain)
    except (KeyError, IndexError, TypeError) as exc:
        raise Incomplete(f'malformed kept assignment map: {type(exc).__name__}: {exc}') from exc


def _kept_entry_groups(native, table, maps, nkept, ntrain):
    if type(nkept) is not int or nkept <= 0 or type(ntrain) is not int or ntrain <= 0:
        raise Incomplete('kept-map scope requires kept assignments and train inputs')
    matches = [mapping for mapping in maps if mapping['table'] == table]
    if len(matches) != 1:
        raise Incomplete('missing or ambiguous kept assignment map for table')
    entries = native['entries']
    global_entries = [entry for entry, owner in enumerate(entries['table']) if owner == table]
    mapping = matches[0]['entries']
    ordinals = [_kept_index(item['table_entry'], 'table entry', len(global_entries)) for item in mapping]
    if set(ordinals) != set(range(len(global_entries))) or len(mapping) != len(global_entries):
        raise Incomplete('kept assignment map does not cover exact native entries')
    groups = [[[] for _ in range(ntrain)] for _ in range(nkept)]
    evidence = [[] for _ in range(nkept)]
    seen = set()
    for item, ordinal in zip(mapping, ordinals):
        entry = global_entries[ordinal]
        kind = item['example_kind']
        expected_kind = {'task': 0, 'train': 1, 'test': 2}.get(kind)
        if expected_kind is None:
            raise Incomplete('unknown kept-map example kind')
        example = _kept_index(item['example_index'], 'example index')
        model = _kept_index(item['model'], 'model index')
        if (entries['example_kind'][entry], entries['example_index'][entry], entries['model'][entry]) != (expected_kind, example, model):
            raise Incomplete('kept assignment map disagrees with native example/model')
        if kind == 'test':
            continue
        assignment = _kept_index(item['kept_assignment'], 'full assignment', nkept)
        key = assignment, kind, example, model
        if key in seen:
            raise Incomplete('duplicate kept assignment/example/model mapping')
        seen.add(key)
        for train in range(ntrain) if kind == 'task' else [example]:
            if not 0 <= train < ntrain:
                raise Incomplete('kept map train index outside task')
            groups[assignment][train].append(entry)
        evidence[assignment].append(dict(item, native_entry=entry))
    for assignment, trains in enumerate(groups):
        if any(not ids for ids in trains):
            raise Incomplete(f'kept assignment {assignment} lacks a complete train model family')
    return tuple(tuple(tuple(ids) for ids in trains) for trains in groups), evidence


def kept_families(native, table, rows, maps, nkept, ntrain):
    """Existing row/model SET semantics over the single structural matcher."""
    groups, evidence = kept_entry_groups(native, table, maps, nkept, ntrain)
    by_entry = {row['entry']: row for row in rows}
    required = {entry for trains in groups for ids in trains for entry in ids}
    if not required <= by_entry.keys():
        raise Incomplete('kept train/task entry has no complete assignment mapping')
    rowsets = {entry: frozenset(by_entry[entry]['rows']) for entry in required}
    return [tuple(frozenset(rowsets[entry] for entry in ids) for ids in trains)
            for trains in groups], evidence


class SearchBound(Incomplete):
    """The bounded transform search is incomplete, not a negative proof."""


def _compare(left, right, op):
    if op == 'eq':
        return left == right
    if op == 'ne':
        return left != right
    if op == 'lt':
        return left < right
    if op == 'le':
        return left <= right
    if op == 'gt':
        return left > right
    if op == 'ge':
        return left >= right
    raise ValueError('unknown recovery comparison operator')


def _predicate(atom, available, key_cache, budget=lambda: None, *, types=None):
    """One atomic meaning shared by search and direct witness application."""
    kind = atom['kind']
    if kind == 'false':
        return lambda row, train: False
    if kind in ('semijoin', 'antijoin'):
        number, source_columns = atom['available'], tuple(atom['source_columns'])
        cache_key = number, source_columns
        if cache_key not in key_cache:
            keys = []
            for rows in available[number]['rows']:
                values = set()
                for index, row in enumerate(rows):
                    if index % 256 == 0:
                        budget()
                    values.add(tuple(row[c] for c in source_columns))
                keys.append(values)
            key_cache[cache_key] = keys
        keys, columns = key_cache[cache_key], tuple(atom['columns'])
        negate = kind == 'antijoin'
        return lambda row, train: (tuple(row[c] for c in columns) in keys[train]) != negate
    if kind == 'margin_conjunction':
        # An executable numeric selector, NOT an inside/frame interpretation.
        # Component layout/values come from the canonical native reader.
        if types is None:
            raise Incomplete('native margin operand types required')
        if atom.get('semantics') != 'numeric_native_margin_components':
            raise Incomplete('unsupported native margin selector semantics')
        comparisons = atom['comparisons']
        if len(comparisons) != 4:
            raise Incomplete('native margin conjunction requires four comparisons')
        compiled = []
        for item in comparisons:
            left, right = item['left_column'], item['right_column']
            lc, rc, op = item['left_component'], item['right_component'], item['operator']
            if not (0 <= left < len(types) and 0 <= right < len(types)
                    and types[left] in ('Box', 'Position') and types[right] in ('Box', 'Position')
                    and 0 <= lc < 4 and 0 <= rc < 4
                    and op in ('eq', 'ne', 'lt', 'le', 'gt', 'ge')):
                raise Incomplete('invalid typed native margin comparison')
            compiled.append((left, lc, op, right, rc))
        return lambda row, train: all(_compare(row[a][ac], row[b][bc], op)
                                      for a, ac, op, b, bc in compiled)
    if kind != 'comparison':
        raise ValueError('unknown recovery predicate kind')
    left, op = atom['left'], atom['op']
    if 'right' in atom:
        right = atom['right']
        return lambda row, train: _compare(row[left], row[right], op)
    value = tuple(atom['value'])
    return lambda row, train: _compare(row[left], value, op)


def verify(gold, mutant, witness, available=(), *, budget=lambda: None, mutant_types=None):
    """Apply T afresh to EVERY model; no search mask/model alignment reuse.

    Semijoin/antijoin source projections are constructed once per predicate and
    train input. The verifier owns its cache, independent of search caches.
    """
    if len(gold) != len(mutant):
        return False
    keys = {}
    if witness.get('schema', 'family-selection-v1') not in ('family-selection-v1', 'family-selection-dnf-v2', 'family-selection-numeric-margins-v3'):
        raise ValueError('unsupported recovery witness schema')
    branches = witness.get('selection_any', [witness.get('selection', [])])
    predicates = [[_predicate(atom, available, keys, budget, types=mutant_types) for atom in branch] for branch in branches]
    projection = tuple(witness['projection'])
    for train, (gs, ms) in enumerate(zip(gold, mutant)):
        transformed = set()
        for model in ms:
            rows = set()
            for index, row in enumerate(model):
                if index % 256 == 0:
                    budget()
                if any(all(predicate(row, train) for predicate in branch) for branch in predicates):
                    rows.add(tuple(row[c] for c in projection))
            transformed.add(frozenset(rows))
        if frozenset(transformed) != gs:
            return False
    return True


def _comparison_atoms(types, universe, budget, *, geometric):
    numeric = {'Number', 'number'}
    for left, ty in enumerate(types):
        if (ty in ('Box', 'Position', 'Offset')) != geometric:
            continue
        values = sorted({row[left] for _, row in universe})
        ops = ('eq', 'ne', 'lt', 'le', 'gt', 'ge') if ty in numeric else ('eq', 'ne')
        for value in values:
            for op in ops:
                budget()
                yield dict(kind='comparison', left=left, op=op, value=list(value))
        for right in range(left + 1, len(types)):
            if types[right] == ty:
                for op in ops:
                    budget()
                    yield dict(kind='comparison', left=left, right=right, op=op)


def _atoms(types, universe, available, budget):
    """Finite typed predicates; source-local choices never replace projection."""
    yield dict(kind='false')
    for left, ty in enumerate(types):
        if ty not in ('Box', 'Position'):
            continue
        for right, rt in enumerate(types):
            if right == left or rt not in ('Box', 'Position'):
                continue
            for op in ('ge', 'gt'):
                budget()
                yield dict(kind='margin_conjunction', semantics='numeric_native_margin_components',
                           comparisons=[dict(left_column=left, left_component=c, operator=op,
                                             right_column=right, right_component=c) for c in range(4)])
    yield from _comparison_atoms(types, universe, budget, geometric=False)
    # Prefer the nearest available definition, never a later gold relation.
    # Large coordinate-constant domains cannot starve dropped-table filters.
    for number, source in reversed(list(enumerate(available))):
        for width in range(len(source['types']) + 1):
            for source_columns in combinations(range(len(source['types'])), width):
                join_choices = [[j for j, ty in enumerate(types) if ty == source['types'][c]]
                                for c in source_columns]
                for columns in product(*join_choices):
                    for kind in ('semijoin', 'antijoin'):
                        budget()
                        yield dict(kind=kind, available=number, columns=list(columns),
                                   source_columns=list(source_columns))
    yield from _comparison_atoms(types, universe, budget, geometric=True)


def family_support(gold, mutant):
    """Necessary support for a row-restricting T; no model ordinals paired.

    Every gold model needs a containing mutant model, and every mutant model
    must be able to produce some gold model. Used on the SAME partial column
    projection of both programs and by the subsequent restriction search.
    """
    return all(all(any(g <= m for m in ms) for g in gs)
               and all(any(g <= m for g in gs) for m in ms)
               for gs, ms in zip(gold, mutant))


def _project_family(families, columns, budget):
    result = []
    for models in families:
        projected = []
        for rows in models:
            values = set()
            for index, row in enumerate(rows):
                if index % 256 == 0:
                    budget()
                values.add(tuple(row[c] for c in columns))
            projected.append(frozenset(values))
        result.append(frozenset(projected))
    return tuple(result)


def _supported_projections(choices, gold, mutant, budget, visit):
    """Exhaustive typed projection DFS, pruning only necessary row support.

    Same physical ordinal is a priority, never a requirement. Duplicating a
    source column remains legal. Each partial check projects BOTH sides onto
    the same assigned gold-column prefix. No available-table or filter grammar
    assumption is needed for a negative after exhaustive failure.
    """
    order = sorted(range(len(choices)), key=lambda c: (len(choices[c]), c))
    gold_prefixes = {}
    mapping = [None] * len(choices)
    def search(depth):
        budget()
        if depth == len(order):
            columns = tuple(mapping)
            yield columns, _project_family(mutant, columns, budget)
            return
        column = order[depth]
        prefix = tuple(order[:depth+1])
        if depth not in gold_prefixes:
            gold_prefixes[depth] = _project_family(gold, prefix, budget)
        for source in sorted(choices[column], key=lambda j: (j != column, j)):
            visit()
            mapping[column] = source
            current = _project_family(mutant, tuple(mapping[c] for c in prefix), budget)
            if family_support(gold_prefixes[depth], current):
                yield from search(depth+1)
        mapping[column] = None
    yield from search(0)


def witness(gold_types, gold, mutant_types, mutant, available=(), seconds=1.0, max_states=20000):
    """One shared transform on whole model SETS; bounded exact finite search."""
    deadline = time.monotonic() + seconds
    states = 0
    phase = 'precheck'
    def budget():
        if time.monotonic() >= deadline or states >= max_states:
            raise SearchBound(f'family recovery search bound: phase={phase}, states={states}')
    def positive(projection, selection, branches=None):
        result = dict(status='determined', recoverable=True, projection=list(projection),
                      selection=selection, states=states, schema='family-selection-v1')
        if branches is not None:
            result.pop('selection')
            result.update(schema='family-selection-dnf-v2', selection_any=branches)
        if any(atom['kind'] == 'margin_conjunction' for branch in (branches if branches is not None else [selection]) for atom in branch):
            result['schema'] = 'family-selection-numeric-margins-v3'
        if not verify(gold, mutant, result, available, budget=budget, mutant_types=mutant_types):
            return None
        return dict(result, verified=True)
    if len(gold) != len(mutant):
        raise Incomplete('gold/mutant train family counts differ')
    if any(len(ms) < len(gs) for gs, ms in zip(gold, mutant)):
        return dict(status='determined', recoverable=False, states=0,
                    nonrecoverable_proof='a deterministic transform cannot increase model-family cardinality')
    for train, (gs, ms) in enumerate(zip(gold, mutant)):
        if not gs or not ms:
            raise Incomplete('empty native model family')
        gold_sizes, mutant_sizes = sorted(map(len, gs)), sorted(map(len, ms))
        if gold_sizes[-1] > mutant_sizes[-1] or mutant_sizes[0] < gold_sizes[0]:
            return dict(status='determined', recoverable=False, states=0,
                        nonrecoverable_proof='selection/projection cannot increase a model row cardinality',
                        proof_kind='row_cardinality', train=train,
                        gold_model_rows=gold_sizes, mutant_model_rows=mutant_sizes)
    projection_choices = tuple(tuple(j for j, ty in enumerate(mutant_types) if ty == gold_ty)
                               for gold_ty in gold_types)
    if any(not choices for choices in projection_choices):
        return dict(status='determined', recoverable=False, states=0,
                    nonrecoverable_proof='no typed projection exists')
    def visit_projection():
        nonlocal states
        budget()
        states += 1
    phase = 'projection_support'
    projections = []
    for projection, current in _supported_projections(projection_choices, gold, mutant, budget, visit_projection):
        projections.append(projection)
        if current == gold:
            result = positive(projection, [])
            if result is not None:
                return result
    if not projections:
        return dict(status='determined', recoverable=False, states=states,
                    nonrecoverable_proof='no typed projection has the row support required by any row-restricting transform',
                    proof_kind='row_support')
    phase = 'predicate_search'
    universe = sorted({(i, row) for i, models in enumerate(mutant) for model in models for row in model})
    positions = {value: i for i, value in enumerate(universe)}
    model_masks = []
    for train, models in enumerate(mutant):
        masks = []
        for model in models:
            mask = 0
            for index, row in enumerate(model):
                if index % 256 == 0:
                    budget()
                mask |= 1 << positions[(train, row)]
            masks.append(mask)
        model_masks.append(masks)
    def projected_rows(bits, projected):
        result = set()
        while bits:
            bit = bits & -bits
            bits -= bit
            result.add(projected[bit.bit_length() - 1])
        return frozenset(result)
    allmask = (1 << len(universe)) - 1
    atoms, keys = {}, {}
    # Only search guidance uses gold rows. Executable branches contain permitted
    # row predicates alone, shared across all examples and all native models.
    boolean_targets = []
    if all(len(family) == 1 for family in gold):
        targets = [next(iter(family)) for family in gold]
        for projection in projections:
            wanted = sum(1 << j for j, (train, row) in enumerate(universe)
                         if tuple(row[c] for c in projection) in targets[train])
            boolean_targets.append((projection, wanted))
    def boolean_cover():
        nonlocal states
        for projection, wanted in boolean_targets:
            remaining, branches = wanted, []
            while remaining:
                budget()
                seed = remaining & -remaining
                allowed, branch = allmask, []
                while allowed & ~wanted:
                    budget()
                    candidates = [(mask, atom) for mask, atom in atoms.items()
                                  if mask & seed and (allowed & ~wanted & ~mask)]
                    if not candidates:
                        break
                    mask, atom = max(candidates, key=lambda item:
                        ((allowed & ~wanted & ~item[0]).bit_count(),
                         (allowed & wanted & item[0]).bit_count()))
                    allowed &= mask
                    branch.append(atom)
                if allowed & ~wanted:
                    # This positive row's atomic truth class also contains an
                    # unwanted row. It cannot be selected by this grammar;
                    # another row may still witness the same projected value.
                    equivalent = allmask
                    for mask in atoms:
                        equivalent &= mask if mask & seed else allmask ^ mask
                    remaining &= ~equivalent
                    continue
                branches.append(branch)
                remaining &= ~allowed
            states += 1
            result = positive(projection, [], branches)
            if result is not None:
                return result
        return None
    # Search every single-atom transform (including semi/anti) before the
    # conjunction phase. A late source cannot be starved by a DFS subtree.
    for atom in _atoms(mutant_types, universe, available, budget):
        budget()
        predicate = _predicate(atom, available, keys, budget, types=mutant_types)
        mask = 0
        for index, (train, row) in enumerate(universe):
            if index % 256 == 0:
                budget()
            if predicate(row, train):
                mask |= 1 << index
        if mask == allmask or mask in atoms:
            continue
        atoms[mask] = atom
        for projection in projections:
            budget()
            states += 1
            projected = [tuple(row[c] for c in projection) for _, row in universe]
            if all(frozenset(projected_rows(model & mask, projected) for model in models) == target
                   for models, target in zip(model_masks, gold)):
                result = positive(projection, [atom])
                if result is None:
                    raise ValueError('family recovery witness failed direct verification')
                return result
        # Fair interleaving: Boolean/conjunction candidates must not wait for a
        # potentially huge coordinate-literal domain to be exhausted.
        if len(atoms) % 8 == 0:
            result = boolean_cover()
            if result is not None:
                return result
    result = boolean_cover()
    if result is not None:
        return result
    for projection in projections:
        budget()
        projected = [tuple(row[c] for c in projection) for _, row in universe]
        seen = set()
        def search(allowed):
            nonlocal states
            budget()
            if allowed in seen:
                return None
            seen.add(allowed)
            states += 1
            current = [[projected_rows(mask & allowed, projected) for mask in models] for models in model_masks]
            if not family_support(gold, current):
                return None
            if all(frozenset(ms) == gs for gs, ms in zip(gold, current)):
                return []
            obligations = []
            for train, (gs, ms) in enumerate(zip(gold, current)):
                extra = next((j for j, m in enumerate(ms) if m not in gs), None)
                if extra is not None:
                    obligations = [(train, extra, g) for g in gs if g <= ms[extra]]
                    break
                missing = next((g for g in gs if g not in ms), None)
                if missing is not None:
                    obligations = [(train, j, missing) for j, m in enumerate(ms) if missing <= m]
                    break
            branches = set()
            for train, model, target in obligations:
                unwanted = next(iter(current[train][model] - target))
                mask = model_masks[train][model] & allowed
                bit = next(1 << j for j in range(len(universe)) if mask & (1 << j) and projected[j] == unwanted)
                for predicate_mask, atom in sorted(atoms.items(), key=lambda item: (allowed & item[0]).bit_count()):
                    budget()
                    if predicate_mask & bit:
                        continue
                    reduced = allowed & predicate_mask
                    if reduced in branches:
                        continue
                    branches.add(reduced)
                    rest = search(reduced)
                    if rest is not None:
                        return [atom] + rest
            return None
        selected = search(allmask)
        if selected is not None:
            result = positive(projection, selected)
            if result is None:
                raise ValueError('family recovery witness failed direct verification')
            return result
    raise SearchBound('no witness within the searched Boolean/conjunction grammar; absence not proven')


def recovery(g, gi, m, mi, report, ntrain, rows_reader, available_by_assignment=None, seconds=1.0, *, final_output=False):
    """Adapter for future filters.recovery, requiring explicit native maps."""
    try:
        kept = report.get('kept_assignments', [])
        if not kept:
            raise Incomplete('no kept gold FITS assignment')
        sg, gr, _ = rows_reader(g, gi)
        sm, mr, _ = rows_reader(m, mi)
        gs, ge = kept_families(g, gi, gr, report.get('gold_kept_assignment_map', []), len(kept), ntrain)
        ms, me = kept_families(m, mi, mr, report.get('mutant_kept_assignment_map', []), len(kept), ntrain)
        evidence = []
        for assignment, (gold, mutant) in enumerate(zip(gs, ms)):
            available = (available_by_assignment or {}).get(assignment, ())
            proof = witness(tuple(t for t, _ in sg), gold, tuple(t for t, _ in sm), mutant, available, seconds)
            evidence.append(dict(kept_assignment=assignment, gold_entries=ge[assignment], mutant_entries=me[assignment],
                                 gold_models=[len(x) for x in gold], mutant_models=[len(x) for x in mutant], witness=proof,
                                 available_tables=[s.get('identity') for s in available]))
            if proof.get('nonrecoverable_proof'):
                return dict(status='complete', reject=False, evidence=evidence,
                            nonrecoverable_proof=proof['nonrecoverable_proof'],
                            code_label=None, judge_eligible=True, verified=False)
        return dict(status='complete', reject=all(e['witness']['recoverable'] for e in evidence), evidence=evidence,
                    definition='one transform per kept DET assignment, shared across all train inputs; exact equality of transformed mutant model sets and gold model sets',
                    transform='one Boolean selection (OR of ANDs of typed comparisons and available-table semi/antijoins) followed by projection',
                    verified=all(e['witness'].get('verified', False) for e in evidence),
                    code_label=('WRONG' if final_output else 'DETOUR') if all(e['witness']['recoverable'] for e in evidence) else None,
                    judge_eligible=not all(e['witness']['recoverable'] for e in evidence))
    except SearchBound as exc:
        return dict(status='unknown', reject=False, reason=str(exc), reason_code='search_bound', code_label=None, judge_eligible=None, verified=False)
    except ValueError as exc:
        return dict(status='unknown', reject=False, reason=str(exc), reason_code='evidence_incomplete', code_label=None, judge_eligible=None, verified=False)


def _input_fact(native, table, rows, ntrain):
    """Certify DET-independent native ex_input without inventing kept maps."""
    ts = native['tables']
    if ts['fact'][table] != 'ex_input' or ts['form'][table] or ts['det_relations'][table]:
        raise Incomplete('input source lacks native DET-independent fact identity')
    trains, task, evidence = {}, None, []
    for row in rows:
        if row['assignment']:
            raise Incomplete('input fact unexpectedly has a DET assignment')
        kind, example = row['example']
        if kind == 2:
            continue
        if kind == 0:
            if task is not None or trains:
                raise Incomplete('duplicate or mixed task/train native input facts')
            task = frozenset(row['rows'])
        elif kind == 1 and 0 <= example < ntrain:
            if task is not None or example in trains:
                raise Incomplete('duplicate or mixed native train input facts')
            trains[example] = frozenset(row['rows'])
        else:
            raise Incomplete('native input fact example outside train scope')
        evidence.append(dict(native_entry=row['entry'], example_kind=kind,
                             example_index=example, model=row['model']))
    if task is not None:
        return tuple(task for _ in range(ntrain)), evidence
    if set(trains) != set(range(ntrain)):
        raise Incomplete('native input facts lack exact train coverage')
    return tuple(trains[i] for i in range(ntrain)), evidence


def available_tables(native, maps, kept, ntrain, point, dependencies, rows_reader):
    """Use explicit component maps; offer only deterministic available tables.

An available relation with several distinct models needs joint native choice
evidence before it can be a deterministic argument of T. Such a relation is
reported as incomplete scope, never guessed or matched by model number.
"""
    result = {i: [] for i in range(len(kept))}
    incomplete = []
    top = int(point.clause_path[0]) if hasattr(point, 'clause_path') else int(point[0])
    for table, form in enumerate(native['tables']['form']):
        if not form:
            allowed = native['tables']['fact'][table] == 'ex_input'
        else:
            f = int(form.split('.')[0])
            allowed = native['tables']['point'][table] == 0 and f < top
        if not allowed:
            continue
        try:
            schema, rows, _ = rows_reader(native, table)
            if not form:
                fact_rows, fact_entries = _input_fact(native, table, rows, ntrain)
                for assignment in range(len(kept)):
                    result[assignment].append(dict(types=tuple(t for t, _ in schema), rows=fact_rows,
                        identity=dict(table=table, form=form, fact='ex_input', kept_assignment=assignment,
                                      proof='det_independent_native_fact', entries=fact_entries)))
                continue
            grouped, evidence = kept_families(native, table, rows, maps, len(kept), ntrain)
            for assignment, family in enumerate(grouped):
                if any(len(models) != 1 for models in family):
                    raise Incomplete('available table has multiple distinct native models')
                result[assignment].append(dict(types=tuple(t for t, _ in schema),
                    rows=tuple(next(iter(models)) for models in family),
                    identity=dict(table=table, form=form, fact=native['tables']['fact'][table], relation=native['tables']['relation'][table], source_name=next(m.get('source_name') for m in maps if m['table']==table), kept_assignment=assignment, entries=evidence[assignment])))
        except ValueError as exc:
            incomplete.append(dict(table=table, form=form, reason=str(exc)))
    return result, incomplete
