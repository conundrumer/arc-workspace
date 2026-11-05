#!/usr/bin/env python
"""Scene recognition on the base table `input`, of work/feature-spec/evaluation-protocol.md.

  uv run python model/feature_eval/scene.py ENCODER --size D [--first N] [--shard I/N]

Per (task, d) it writes results/scene-input/<task>.d<d>.json, as each ends, and a restart
skips those written. The values of the closed roots stand in results/scene-input/values/.
"""
import argparse
import json
import random
import time

import numpy as np

from common import (RESULTS, auc_of, claims_of, classes, corpus_records, eval_tasks, flush_print, grids_values, mutator,
                    read_values, task_json, violation, write_json_atomic)

OUT = RESULTS / 'scene-input'
TEST_MUTATIONS = 100


def items_of(task):
    """The grids to compare: each input, then its mutations; and each input's place and its
    mutations' places among the grids."""
    data = task_json(task)
    train = [pair['input'] for pair in data['train']]
    test = [pair['input'] for pair in data['test']]
    inputs = train + test
    grids, place = [], {}

    def at(grid):
        key = json.dumps(grid)
        if key not in place:
            place[key] = len(grids)
            grids.append(grid)
        return place[key]

    input_places = [at(grid) for grid in inputs]
    negatives = [[] for _ in inputs]
    trains = {json.dumps(grid) for grid in train}
    for record in corpus_records(task):
        if record.get('kind') != 'in' or record.get('stored') != 'same' or 'grid' not in record:
            continue
        if json.dumps(record['grid']) in trains:
            continue
        kind, index = record['source'].split('/')
        if kind == 'train':
            negatives[int(index)].append(at(record['grid']))
    mutate = mutator()
    for index, grid in enumerate(test):
        rng = random.Random(f'scene/{task}/test/{index}')
        for _ in range(TEST_MUTATIONS):
            mutated, _ = mutate(grid, rng)
            if json.dumps(mutated) not in place or place[json.dumps(mutated)] not in input_places:
                negatives[len(train) + index].append(at(mutated))
    negatives = [sorted(set(found) - set(input_places)) for found in negatives]
    return grids, input_places, negatives


def statistics(matrix, sizes, d, input_places, negatives):
    keep = sizes <= d
    held = matrix[keep]
    per_input = []
    for h, true_place in enumerate(input_places):
        others = [place for k, place in enumerate(input_places) if k != h]
        mask, value = claims_of(held, others)
        v_true = float(violation(held, mask, value, [true_place])[0]) if len(held) else 0.0
        v_negative = violation(held, mask, value, negatives[h]) if negatives[h] else np.zeros(0)
        per_input.append({
            'claims': int(mask.sum()),
            'negatives': len(negatives[h]),
            'v_true': v_true,
            'v_negative': [round(float(v), 8) for v in v_negative],
            'auc': auc_of(v_true, v_negative),
            'false_rule_out': bool(v_true > 0),
            'rule_outs': float((v_negative > 0).mean()) if len(v_negative) else None,
        })
    return per_input


def run_task(task, encoder, size):
    values_dir = OUT / 'values'
    values_dir.mkdir(parents=True, exist_ok=True)
    done = [OUT / f'{task}.d{d}.json' for d in range(1, size + 1)]
    if all(path.exists() for path in done):
        return None
    start = time.time()
    grids, input_places, negatives = items_of(task)
    grids_path = values_dir / f'{task}.grids.json'
    grids_path.write_text(json.dumps(grids))
    values_path = values_dir / f'{task}.values.tsv'
    grids_values(grids_path, values_path, encoder, False, size, log=values_dir / f'{task}.log')
    names, sizes, matrix = read_values(values_path, size)
    summary = None
    for d in range(1, size + 1):
        keep = sizes <= d
        per_input = statistics(matrix, sizes, d, input_places, negatives)
        aucs = [item['auc'] for item in per_input if item['auc'] is not None]
        summary = {'task': task, 'd': d, 'grids': len(grids), 'roots': int(keep.sum()), 'classes': classes(matrix[keep]),
                   'auc': float(np.mean(aucs)) if aucs else None, 'per_input': per_input, 'seconds': time.time() - start}
        write_json_atomic(OUT / f'{task}.d{d}.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('encoder')
    parser.add_argument('--size', type=int, default=1)
    parser.add_argument('--first', type=int, default=60)
    parser.add_argument('--shard', default='0/1')
    a = parser.parse_args()
    at, of = map(int, a.shard.split('/'))
    tasks = [task for index, task in enumerate(eval_tasks(a.first)) if index % of == at]
    started = time.time()
    for count, task in enumerate(tasks):
        summary = run_task(task, a.encoder, a.size)
        rate = (count + 1) / (time.time() - started)
        if summary:
            flush_print(f"{count + 1}/{len(tasks)} {task} roots {summary['roots']} classes {summary['classes']} grids {summary['grids']} auc {summary['auc']} {summary['seconds']:.0f}s; ETA {(len(tasks) - count - 1) / rate:.0f}s")


if __name__ == '__main__':
    main()
