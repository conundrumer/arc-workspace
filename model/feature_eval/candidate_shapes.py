#!/usr/bin/env python
"""Candidate recognition on shapes at size 1, by class, from the stored rows of
results/candidate-tables/: a shape is a ground expression with the table and its columns as typed
holes, and its value at a train pair is the multiset of its ground expressions' values.

At size 1 a root reads the table and `output` through one `join`, `antijoin` or `union`, so this
computes those operators on the rows themselves.

  uv run python model/feature_eval/candidate_shapes.py [--nulls N] [--first N]
"""
import argparse
import glob
import itertools
import json
import random
from collections import Counter

import numpy as np

from common import (RESULTS, ROOT, glob_data, read_json, write_json_atomic)

ZERO_TYPES = {'Position', 'Box', 'Offset', 'Int', 'Nat'}
INVARIANT = {'Int', 'Nat'}
ZERO_MARGINS = (0, 0, 0, 0)


def hashable(cell):
    return tuple(cell) if isinstance(cell, list) else cell


def table_rows(table, train):
    """Each pair's rows as tuples; `None` at a pair with no rows given."""
    out = []
    for i in range(train):
        rows = table['rows'].get(f'train/{i}')
        out.append(None if rows is None else [tuple(hashable(cell) for cell in row) for row in rows])
    return out


def grid_rows(grid):
    height, width = len(grid), len(grid[0])
    return [((r, height - 1 - r, c, width - 1 - c), grid[r][c]) for r in range(height) for c in range(width)]


def input_table(task, train):
    rows = {f'train/{i}': [[list(p), col] for p, col in grid_rows(task['train'][i]['input'])] for i in range(train)}
    return {'columns': ['P', 'Col'], 'types': ['Position', 'Color'], 'rows': rows}


def meets(ty, output_column):
    return ty in ('Position', 'Box') if output_column == 'P' else ty == 'Color'


class Holes:
    """The holes of one shape, numbered by first appearance."""

    def __init__(self, types):
        self.types = types
        self.numbers = {}

    def text(self, column):
        if column not in self.numbers:
            self.numbers[column] = len(self.numbers) + 1
        return f'?{self.numbers[column]}:{self.types[column]}'


def join_keys(rows, places):
    return [tuple(row[place] for place in places) for row in rows]


def add(values, name, pair, value):
    values.setdefault(name, {}).setdefault(pair, []).append(value)


def set_roots(values, base, types, rows_of_pair, pair, holes_text):
    """The `value-set` roots over the invariant columns of a table's rows."""
    invariant = [at for at, ty in enumerate(types) if ty in INVARIANT]
    for count in range(1, len(invariant) + 1):
        for chosen in itertools.combinations(invariant, count):
            text = holes_text(chosen)
            add(values, f'set|{base}|{text}', pair, frozenset(tuple(row[at] for at in chosen) for row in rows_of_pair))


def shape_values(table, outputs, train):
    """Each root's list of values per pair, by its shape; a pair with no rows has no entry for it."""
    types = table['types']
    rows = table_rows(table, train)
    arity = len(types)
    values = {}
    missing = [i for i in range(train) if rows[i] is None]
    # The pair sets of each order: one set of (table column, output column).
    candidates = {name: [at for at in range(arity) if meets(types[at], name)] for name in ('P', 'Col')}
    # In `join T output`, each output column pairs with at most one table column.
    table_left = [[]]
    for name in ('P', 'Col'):
        table_left = [held + extra for held in table_left for extra in ([[]] + [[(at, name)] for at in candidates[name]])]
    # In `join output T`, each table column pairs with at most one output column.
    output_left = [[]]
    for at in range(arity):
        names = [name for name in ('P', 'Col') if meets(types[at], name)]
        output_left = [held + extra for held in output_left for extra in ([[]] + [[(at, name)] for name in names])]
    for side, pair_sets in (('T', table_left), ('O', output_left)):
        for pairs in pair_sets:
            holes = Holes(types)
            pair_text = ' '.join(f'({holes.text(at)} {name})' if side == 'T' else f'({name} {holes.text(at)})' for at, name in pairs)
            numbers = dict(holes.numbers)
            join_base = f'join {"T output" if side == "T" else "output T"} {pair_text}'
            left_base = f'antijoin T output {pair_text}' if side == 'T' else f'antijoin output T {pair_text}'

            def column_text(chosen):
                local = Holes(types)
                local.numbers = dict(numbers)
                return ' '.join(local.text(at) for at in chosen)

            for i in range(train):
                if rows[i] is None:
                    continue
                out_rows = outputs[i]
                places = [at for at, _ in pairs]
                out_places = [0 if name == 'P' else 1 for _, name in pairs]
                out_keys = Counter(join_keys(out_rows, out_places))
                row_keys = join_keys(rows[i], places)
                matched = [row for row, key in zip(rows[i], row_keys) if key in out_keys]
                joined = sum(out_keys[key] for key in row_keys if key in out_keys)
                add(values, f'nonempty|{join_base}', i, joined > 0)
                add(values, f'cardinality|{join_base}', i, joined)
                set_roots(values, join_base, types, matched, i, column_text)
                if side == 'T':
                    unmatched = [row for row, key in zip(rows[i], row_keys) if key not in out_keys]
                    if not pairs and out_rows:
                        unmatched = []
                    add(values, f'nonempty|{left_base}', i, len(unmatched) > 0)
                    add(values, f'cardinality|{left_base}', i, len(unmatched))
                    set_roots(values, left_base, types, unmatched, i, column_text)
                else:
                    table_keys = set(row_keys)
                    left = [row for row, key in zip(out_rows, join_keys(out_rows, out_places)) if key not in table_keys]
                    if not pairs and rows[i]:
                        left = []
                    add(values, f'nonempty|{left_base}', i, len(left) > 0)
                    add(values, f'cardinality|{left_base}', i, len(left))
    # `union T output`: every output column pairs with a table column, and each other table column holds 0.
    for p_at in candidates['P']:
        for col_at in candidates['Col']:
            rest = [at for at in range(arity) if at not in (p_at, col_at)]
            if any(types[at] not in ZERO_TYPES for at in rest):
                continue
            holes = Holes(types)
            text = ' '.join(f'({holes.text(at)} {"P" if at == p_at else "Col" if at == col_at else 0})' for at in range(arity))
            base = f'union T output {text}'
            for i in range(train):
                if rows[i] is None:
                    continue
                union = set(rows[i])
                for p, col in outputs[i]:
                    row = [ZERO_MARGINS if types[at] in ('Position', 'Box', 'Offset') else 0 for at in range(arity)]
                    row[p_at], row[col_at] = p, col
                    union.add(tuple(row))
                add(values, f'nonempty|{base}', i, len(union) > 0)
                add(values, f'cardinality|{base}', i, len(union))
    # `union output T`: `Col` pairs with a table column, `P` with one or with 0, and no table column is left.
    if arity in (1, 2):
        for col_at in candidates['Col']:
            for p_at in candidates['P'] + ([None] if arity == 1 else []):
                if arity == 2 and p_at is None:
                    continue
                holes = Holes(types)
                text = f'(P {holes.text(p_at) if p_at is not None else 0}) (Col {holes.text(col_at)})'
                base = f'union output T {text}'
                for i in range(train):
                    if rows[i] is None:
                        continue
                    union = set(outputs[i])
                    for row in rows[i]:
                        union.add((row[p_at] if p_at is not None else ZERO_MARGINS, row[col_at]))
                    add(values, f'nonempty|{base}', i, len(union) > 0)
                    add(values, f'cardinality|{base}', i, len(union))
    # A multiset per pair; a pair with no rows has no value.
    out = {}
    for name, per_pair in values.items():
        vector = []
        for i in range(train):
            if i in missing:
                vector.append(None)
            else:
                vector.append(tuple(sorted(map(repr, per_pair.get(i, [])))))
        out[name] = tuple(vector)
    return out


def stable(vector):
    return vector is not None and all(value is not None for value in vector) and len(set(vector)) == 1


DEFAULTS = {'nonempty': repr(False), 'cardinality': repr(0), 'set': repr(frozenset())}


def active(name, vector):
    """Whether the root has one value at every pair that is not its default: every member of its
    multiset at the default leaves it at the default."""
    if not stable(vector):
        return False
    default = DEFAULTS[name.split('|')[0]]
    return any(value != default for value in vector[0])


def has_rows(table, train):
    """Whether the table has rows at every train pair."""
    return all(table['rows'].get(f'train/{i}') for i in range(train))


def non_vacuous(vector, rows_everywhere):
    """Whether a root has one value at every pair, none of them no value, on a table with rows at
    every pair. A root with no binding is at its default at every pair."""
    if not rows_everywhere:
        return False
    return vector is None or stable(vector)


def item_scores(item, input_values, outputs, train, cache, rule='active', net=None):
    def values_of(table):
        key = id(table)
        if key not in cache:
            cache[key] = shape_values(table, outputs, train)
        return cache[key]

    reads = [(values_of(table), has_rows(table, train)) for table in item['reads'].values()]
    gold = (values_of(item['gold']), has_rows(item['gold'], train))
    mutants = [(values_of(mutant['table']), has_rows(mutant['table'], train)) for mutant in item['mutants']]
    bases = [input_values, *reads]
    every = [*bases, gold, *mutants]
    names = set()
    for values, _ in every:
        names.update(values)

    def holds(name, held):
        values, rows_everywhere = held
        if rule == 'active':
            return active(name, values.get(name))
        return non_vacuous(values.get(name), rows_everywhere)

    # A contingent root is one that `input` or a table Q reads does not have as stable.
    contingent_names = [name for name in names if not all(holds(name, held) for held in bases)]
    classes = {}
    for name in contingent_names:
        classes.setdefault((name.split('|')[0], tuple(held[0].get(name) for held in every), tuple(held[1] for held in every)), name)
    contingent = list(classes.values())
    if net is not None:
        for name in contingent_names:
            on_gold = holds(name, gold)
            for held in mutants:
                on_mutant = holds(name, held)
                if on_gold != on_mutant:
                    record = net.setdefault(name, [0, 0])
                    record[0 if on_gold else 1] += 1
    if not contingent:
        return 0.0, [0.0 for _ in mutants], 0

    def score(held):
        return sum(holds(name, held) for name in contingent) / len(contingent)
    return score(gold), [score(held) for held in mutants], len(contingent)


def auc_items(scores):
    found = [1.0 if gold > mutant else 0.5 if gold == mutant else 0.0 for gold, mutants, _ in scores for mutant in mutants]
    return float(np.mean(found)) if found else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--nulls', type=int, default=20)
    parser.add_argument('--first', type=int, default=60)
    parser.add_argument('--rule', choices=['active', 'nonvacuous'], default='active')
    a = parser.parse_args()
    target = RESULTS / f'candidate/shapes-size1.{a.rule}.json'
    net = {}
    rng = random.Random(23)
    per_task = {}
    for path in sorted(glob_data(str(RESULTS / 'candidate-tables/????????.json')))[:a.first]:
        data = read_json(path)
        if not data['items']:
            continue
        task = read_json(ROOT / f"data/tasks/{data['task']}.json")
        train = data['train']
        outputs = [grid_rows(task['train'][i]['output']) for i in range(train)]
        table_of_input = input_table(task, train)

        def run(items, moved, net=None):
            cache = {}
            input_values = (shape_values(table_of_input, moved, train), True)
            return [item_scores(item, input_values, moved, train, cache, a.rule, net) for item in items]

        rest = [item for item in data['items'] if item['query'] != data['last_query']]
        last = [item for item in data['items'] if item['query'] == data['last_query']]
        scores = run(rest, outputs, net)
        scores_last = run(last, outputs)
        nulls = []
        if len({json.dumps(task['train'][i]['output']) for i in range(train)}) > 1:
            for _ in range(a.nulls):
                order = list(range(train))
                while any(order[i] == i for i in range(train)):
                    rng.shuffle(order)
                found = auc_items(run(rest, [outputs[at] for at in order]))
                if found is not None:
                    nulls.append(found)
        per_task[data['task']] = {
            'auc': auc_items(scores), 'auc_last': auc_items(scores_last), 'null': float(np.mean(nulls)) if nulls else None,
            'items': sum(len(found[1]) for found in scores),
            'contingent_classes': float(np.mean([found[2] for found in scores])) if scores else 0.0,
        }
        print(data['task'], per_task[data['task']], flush=True)
        write_json_atomic(target, {'per_task': per_task})
    aucs = {task: record['auc'] for task, record in per_task.items() if record['auc'] is not None}
    gains = [record['auc'] - record['null'] for record in per_task.values() if record['auc'] is not None and record['null'] is not None]
    bootstrap = lambda values: [float(q) for q in np.quantile(np.array(values)[np.random.default_rng(7).integers(0, len(values), (2000, len(values)))].mean(axis=1), [.005, .995])]
    summary = {
        'tasks': len(aucs), 'auc': float(np.mean(list(aucs.values()))), 'interval_99': bootstrap(list(aucs.values())),
        'null': float(np.mean([record['null'] for record in per_task.values() if record['null'] is not None])) if gains else None,
        'gain_over_null': float(np.mean(gains)) if gains else None, 'gain_interval_99': bootstrap(gains) if gains else None,
        'auc_last': float(np.mean([record['auc_last'] for record in per_task.values() if record['auc_last'] is not None])),
        'items': int(sum(record['items'] for record in per_task.values())),
        'contingent_classes_mean': float(np.mean([record['contingent_classes'] for record in per_task.values()])),
    }
    top = sorted(net.items(), key=lambda item: -(item[1][0] - item[1][1]))[:30]
    bottom = sorted(net.items(), key=lambda item: item[1][0] - item[1][1])[:10]
    summary['top_shapes'] = [{'shape': name, 'gold_not_mutant': found[0], 'mutant_not_gold': found[1], 'net': found[0] - found[1]} for name, found in top]
    summary['bottom_shapes'] = [{'shape': name, 'gold_not_mutant': found[0], 'mutant_not_gold': found[1], 'net': found[0] - found[1]} for name, found in bottom]
    write_json_atomic(target, {'summary': summary, 'per_task': per_task})
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
