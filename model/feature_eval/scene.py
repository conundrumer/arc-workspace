#!/usr/bin/env python
"""Scene recognition on the base table `input`, of docs/feature-spec/evaluation-protocol.md.

  uv run python model/feature_eval/scene.py ENCODER --size D [--first N] [--shard I/N]

Per (task, d) it writes results/scene-input/<task>.d<d>.json, as each ends, and a restart
skips those written. The values of the closed roots stand in results/scene-input/values/.
"""
import argparse
import json
import time

import numpy as np

from common import (RESULTS, classes, data_exists, eval_tasks, flush_print, grids_values, item_statistics, read_json, read_values, task_json, write_json_atomic)

OUT = RESULTS / 'scene-input'


def items_of(task, limit=None):
    """The grids to compare: each input, then its mutations; and each input's place and its
    mutations' places among the grids. `limit` keeps the first N negatives of an input."""
    data = task_json(task)
    items = read_json(RESULTS / f'items/{task}.json')
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
    for record in items['negatives'] + items['test_negatives']:
        kind, index = record['source'].split('/')
        h = int(index) if kind == 'train' else len(train) + int(index)
        if limit is None or len(negatives[h]) < limit:
            negatives[h].append(at(record['grid']))
    negatives = [sorted(set(found) - set(input_places)) for found in negatives]
    return grids, input_places, negatives


def statistics(matrix, sizes, d, input_places, negatives):
    held = matrix[sizes <= d]
    unique = np.unique(held, axis=0) if len(held) else held
    per_input = []
    for h, true_place in enumerate(input_places):
        others = [place for k, place in enumerate(input_places) if k != h]
        found = item_statistics(held, unique, others, true_place, negatives[h])
        v_negative = found['v_other']
        per_input.append({
            'claims': found['claims'],
            'claims_root': found['claims_root'],
            'negatives': len(negatives[h]),
            'v_true': found['v_true'],
            'v_negative': [round(float(v), 8) for v in v_negative],
            'auc': found['auc'],
            'auc_root': found['auc_root'],
            'false_rule_out': bool(found['v_true'] > 0),
            'rule_outs': float((v_negative > 0).mean()) if len(v_negative) else None,
        })
    return per_input


def run_task(task, encoder, size, limit, stats_only=False):
    suffix = f'.n{limit}' if limit else ''
    values_dir = OUT / 'values'
    values_dir.mkdir(parents=True, exist_ok=True)
    done = [OUT / f'{task}{suffix}.d{d}.json' for d in range(1, size + 1)]
    if not stats_only and all(data_exists(path) for path in done):
        return None
    start = time.time()
    grids, input_places, negatives = items_of(task, limit)
    grids_path = values_dir / f'{task}{suffix}.grids.json.zst'
    write_json_atomic(grids_path, grids)
    values_path = values_dir / f'{task}{suffix}.values.tsv.zst'
    if stats_only:
        if not data_exists(values_path):
            return None
    else:
        grids_values(grids_path, values_path, encoder, False, size, log=values_dir / f'{task}.log')
    names, sizes, matrix = read_values(values_path, size)
    summary = None
    for d in range(1, size + 1):
        keep = sizes <= d
        per_input = statistics(matrix, sizes, d, input_places, negatives)
        aucs = [item['auc'] for item in per_input if item['auc'] is not None]
        roots = [item['auc_root'] for item in per_input if item['auc_root'] is not None]
        summary = {'task': task, 'd': d, 'negatives_limit': limit, 'grids': len(grids), 'roots': int(keep.sum()), 'classes': classes(matrix[keep]),
                   'auc': float(np.mean(aucs)) if aucs else None, 'auc_root': float(np.mean(roots)) if roots else None, 'per_input': per_input, 'seconds': time.time() - start}
        write_json_atomic(OUT / f'{task}{suffix}.d{d}.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('encoder')
    parser.add_argument('--size', type=int, default=1)
    parser.add_argument('--first', type=int, default=60)
    parser.add_argument('--shard', default='0/1')
    parser.add_argument('--negatives', type=int, default=None, help='the first N negatives of each input')
    parser.add_argument('--stats-only', action='store_true', help='recompute the statistics from the value files')
    a = parser.parse_args()
    at, of = map(int, a.shard.split('/'))
    tasks = [task for index, task in enumerate(eval_tasks(a.first)) if index % of == at]
    started = time.time()
    for count, task in enumerate(tasks):
        summary = run_task(task, a.encoder, a.size, a.negatives, a.stats_only)
        rate = (count + 1) / (time.time() - started)
        if summary:
            flush_print(f"{count + 1}/{len(tasks)} {task} roots {summary['roots']} classes {summary['classes']} grids {summary['grids']} auc {summary['auc']} {summary['seconds']:.0f}s; ETA {(len(tasks) - count - 1) / rate:.0f}s")


if __name__ == '__main__':
    main()
