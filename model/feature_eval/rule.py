#!/usr/bin/env python
"""Rule recognition on the base tables, of docs/feature-spec/evaluation-protocol.md.

  uv run python model/feature_eval/rule.py ENCODER --size D [--first N] [--shard I/N]

Per (task, d) it writes results/rule-base/<task>.d<d>.json, as each ends, and a restart
skips those written. The values of the closed roots stand in results/rule-base/values/.
"""
import argparse
import json
import time

import numpy as np

from common import (RESULTS, auc_of, classes, data_exists, eval_tasks, flush_print, grids_values, item_statistics, read_json, read_values, task_json, write_json_atomic)

OUT = RESULTS / 'rule-base'


def items_of(task):
    """The pairs to compare: each train pair, then each near miss with its pair's input; each
    pair's near misses by their places, with whether each survives the first version's claims."""
    data = task_json(task)
    items = read_json(RESULTS / f'items/{task}.json')
    pairs = [[pair['input'], pair['output']] for pair in data['train']]
    count = len(pairs)
    near = [[] for _ in range(count)]
    for record in items['near_misses']:
        h = int(record['pair'])
        near[h].append((len(pairs), bool(record['survives'])))
        pairs.append([data['train'][h]['input'], record['grid']])
    return pairs, count, near


def statistics(matrix, sizes, d, count, near):
    held = matrix[sizes <= d]
    unique = np.unique(held, axis=0) if len(held) else held
    per_pair = []
    for h in range(count):
        others = [k for k in range(count) if k != h]
        places = [place for place, _ in near[h]]
        survives = np.array([flag for _, flag in near[h]], dtype=bool)
        found = item_statistics(held, unique, others, h, places)
        v_near = found['v_other']
        v_true = found['v_true']
        per_pair.append({
            'claims': found['claims'],
            'claims_root': found['claims_root'],
            'near_misses': len(places),
            'v_true': v_true,
            'v_near': [round(float(v), 8) for v in v_near],
            'survives': survives.tolist(),
            'auc': found['auc'],
            'auc_root': found['auc_root'],
            'auc_survive': auc_of(v_true, v_near[survives]) if places else None,
            'auc_other': auc_of(v_true, v_near[~survives]) if places else None,
            'false_rule_out': bool(v_true > 0),
            'rule_outs': float((v_near > 0).mean()) if len(v_near) else None,
        })
    return per_pair


def run_task(task, encoder, size, stats_only=False, native=False):
    suffix = '.native' if native else ''
    values_dir = OUT / 'values'
    values_dir.mkdir(parents=True, exist_ok=True)
    done = [OUT / f'{task}{suffix}.d{d}.json' for d in range(1, size + 1)]
    if not stats_only and all(data_exists(path) for path in done):
        return None
    start = time.time()
    pairs, count, near = items_of(task)
    pairs_path = values_dir / f'{task}{suffix}.pairs.json.zst'
    write_json_atomic(pairs_path, pairs)
    values_path = values_dir / f'{task}{suffix}.values.tsv.zst'
    if stats_only:
        if not data_exists(values_path):
            return None
    else:
        grids_values(pairs_path, values_path, encoder, True, size, log=values_dir / f'{task}.log', native=native)
    names, sizes, matrix = read_values(values_path, size)
    summary = None
    for d in range(1, size + 1):
        keep = sizes <= d
        per_pair = statistics(matrix, sizes, d, count, near)
        aucs = [item['auc'] for item in per_pair if item['auc'] is not None]
        roots = [item['auc_root'] for item in per_pair if item['auc_root'] is not None]
        summary = {'task': task, 'd': d, 'pairs': len(pairs), 'roots': int(keep.sum()), 'classes': classes(matrix[keep]),
                   'auc': float(np.mean(aucs)) if aucs else None, 'auc_root': float(np.mean(roots)) if roots else None, 'per_pair': per_pair, 'seconds': time.time() - start}
        write_json_atomic(OUT / f'{task}{suffix}.d{d}.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('encoder')
    parser.add_argument('--size', type=int, default=1)
    parser.add_argument('--first', type=int, default=60)
    parser.add_argument('--shard', default='0/1')
    parser.add_argument('--stats-only', action='store_true', help='recompute the statistics from the value files')
    parser.add_argument('--native', action='store_true', help='read the generated shapes over the base tables, under the suffix .native')
    a = parser.parse_args()
    at, of = map(int, a.shard.split('/'))
    tasks = [task for index, task in enumerate(eval_tasks(a.first)) if index % of == at]
    started = time.time()
    for count, task in enumerate(tasks):
        summary = run_task(task, a.encoder, a.size, a.stats_only, a.native)
        rate = (count + 1) / (time.time() - started)
        if summary:
            flush_print(f"{count + 1}/{len(tasks)} {task} roots {summary['roots']} classes {summary['classes']} pairs {summary['pairs']} auc {summary['auc']} {summary['seconds']:.0f}s; ETA {(len(tasks) - count - 1) / rate:.0f}s")


if __name__ == '__main__':
    main()
