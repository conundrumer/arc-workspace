#!/usr/bin/env python
"""The first version's features at each train pair, one zstd JSON file per task, for v1_cover.py.

  <runtime python> -u -I -B v1_dump.py OUT ROOT [--mutants K] TASK...

ROOT holds `train/mutants/`, whose files name each task's gold program and its mutants. A task's file holds:
- `pairs`: at each pair, each gold table's values, at the assignment that solves the train pairs, with the features across its other retained
  assignments.
- `base`: at each pair, what the first version says of the input grid, the output and the changed cells.
- `columns`: each table's column tokens with their types. `tables`: each table's token with its name.
- `coordinates`: each feature of `pairs` and `mutants`, with what it reads, its aggregation level and what else it reads.
- `mutants`, with `--mutants K`: up to K mutants, each with its query, its number there, and the values of its query's tables at each pair.

It skips the tasks done, and it prints a rate and an ETA.
"""
import json
import os
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for place in ('model/contracts/features', 'model/contracts/dev'):
    sys.path.insert(0, str(REPO / place))
sys.path.insert(0, str(REPO / 'model/feature_eval'))
import engine as E  # noqa: E402
import features as F  # noqa: E402
import observations as O  # noqa: E402
import run as R  # noqa: E402
import schema as S  # noqa: E402
from common import read_json  # noqa: E402
from tables_worker import keep  # noqa: E402

SMALL = 300000


def coordinate_of(key, graph, describe):
    held = S.coordinates(key, graph, frozenset(), describe)
    others = sorted({f'{other[1]}:{other[0]}' if other[1] == 'base table' else other[1] for other in held['others']})
    return [held['reads'], held['level'], '+'.join(others) or 'owner']


def features_of(solver, tables, task_json, others, cache):
    graph, reads = E.reads(solver.text), E.table_reads(solver.text)
    pairs = []
    coordinates = {}
    for at in range(len(task_json['train'])):
        pair = R.enc(F.all_features(tables, f'train/{at}', task_json, graph, lambda g, n: E.upstream(g, n), R.grids_of, cache, reads=reads, prov=solver.provenance, others=others))
        by_owner = {}
        for key, value in pair.items():
            owner, _, feature = key.partition('|')
            if feature.endswith(' describe'):
                by_owner.setdefault(owner, {})[feature[:-len(' describe')]] = value
        for key in pair:
            owner, _, feature = key.partition('|')
            if feature not in coordinates and not feature.endswith(' describe'):
                coordinates[feature] = coordinate_of(key, graph, by_owner.get(owner, {}))
        pairs.append(pair)
    return pairs, coordinates


def dump(out, root, task, mutants):
    source = read_json(Path(root) / 'train' / 'mutants' / f'{task}.json')
    task_json = json.loads((REPO / 'data/tasks' / f'{task}.json').read_text())
    for pair in task_json['test']:
        pair['output'] = pair['input']
    solver = O.Solver(task, text=source['gold'])
    tables = solver.tables(task_json, keep_run=True)
    small = sum(len(rows) for table in tables.values() for rows in table['rows'].values()) <= SMALL
    others = solver.other_assignments(16) if small else []
    cache = F.FeatureCache()
    pairs, coordinates = features_of(solver, tables, task_json, others, cache)
    ids = solver.provenance.ids
    names = [name for name in tables if name not in ('ex_input', 'ex_output')]
    columns = {name: [[ids.column_token(name, at), column[1]] for at, column in enumerate(tables[name]['columns'])] for name in names}
    base = [R.enc(F.base_features(task_json, f'train/{at}', R.grids_of)) for at in range(len(task_json['train']))]
    kept = []
    drawn = [(query, mutant) for query in source['queries'] for mutant in query['mutants']]
    random.Random(f'v1-dump.{task}').shuffle(drawn)
    for query, mutant in drawn[:mutants]:
        try:
            other_solver = O.Solver(task, text=mutant['text'])
            run = other_solver.run_engine(task_json, pin={})
            other_tables = other_solver.read(run, next(iter(other_solver.output_keys(run)), None))
            own, own_coordinates = features_of(other_solver, other_tables, task_json, None, cache)
        except Exception as error:
            kept.append(dict(query=query['name'], form=query['form'], mutant=query['mutants'].index(mutant), fault=type(error).__name__))
            continue
        for feature, held in own_coordinates.items():
            coordinates.setdefault(feature, held)
        relation = query['name']
        wanted = [{key: value for key, value in pair.items() if key.partition('|')[0].split('.')[0] == relation} for pair in own]
        other_ids = other_solver.provenance.ids
        own_columns = {name: [[other_ids.column_token(name, at), column[1]] for at, column in enumerate(other_tables[name]['columns'])] for name in other_tables if name.split('.')[0] == relation}
        kept.append(dict(query=relation, form=query['form'], mutant=query['mutants'].index(mutant), edit=mutant.get('edit'), pairs=wanted, columns=own_columns))
    keep(Path(out) / f'{task}.json.zst', dict(task=task, pairs=pairs, base=base, columns=columns, tables={ids.table_token(name): name for name in names}, coordinates=coordinates, assignments=1 + len(others), mutants=kept))


def main(arguments):
    out, root, *rest = arguments
    mutants = 0
    if rest[0] == '--mutants':
        mutants = int(rest[1])
        rest = rest[2:]
    tasks = rest
    started = time.time()
    done = 0
    for at, task in enumerate(tasks):
        if (Path(out) / f'{task}.json.zst').exists():
            continue
        try:
            dump(out, root, task, mutants)
            done += 1
            rate = done / (time.time() - started)
            print(f'{at + 1}/{len(tasks)} {task} {rate * 60:.1f}/min ETA {(len(tasks) - at - 1) / rate:.0f}s', flush=True)
        except Exception as error:
            print(f'{at + 1}/{len(tasks)} {task} failed {type(error).__name__}', flush=True)


if __name__ == '__main__':
    os.makedirs(sys.argv[1], exist_ok=True)
    main(sys.argv[1:])
