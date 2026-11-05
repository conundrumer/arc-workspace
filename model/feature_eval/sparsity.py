#!/usr/bin/env python
"""How sparse the closed roots are, per table and input: the share of roots at their default,
and the mean count of active roots and active classes. A default is the value of an aggregate on
no rows; a stopped root is no value, which differs from it.

  uv run python model/feature_eval/sparsity.py scene-input|rule-base [--suffix .n20] [--d D]
"""
import argparse
import json

import numpy as np

from common import RESULTS, eval_tasks, write_json_atomic

MARK_NONEMPTY = 1 << 61
MARK_SET = 1 << 62


def read_words(path, d):
    names, rows = [], []
    with open(path) as lines:
        for line in lines:
            parts = line.rstrip('\n').split('\t')
            if len(parts) != 3 or int(parts[1]) > d:
                continue
            names.append(parts[0])
            rows.append([0 if v == '-' else int(v, 16) for v in parts[2].split(' ')])
    return names, np.array(rows, dtype=np.uint64)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('test')
    parser.add_argument('--suffix', default='')
    parser.add_argument('--d', type=int, default=1)
    a = parser.parse_args()
    per_task = {}
    for task in eval_tasks(60):
        path = RESULTS / a.test / 'values' / f'{task}{a.suffix}.values.tsv'
        if not (RESULTS / a.test / f'{task}{a.suffix}.d{a.d}.json').exists():
            continue
        names, matrix = read_words(path, a.d)
        # A nonempty root at false, or a count of 0, has only its kind's bits; an empty set too.
        stopped = matrix == 0
        default = (matrix == MARK_NONEMPTY) | (matrix == MARK_SET)
        active = ~default & ~stopped
        unique, inverse = np.unique(matrix, axis=0, return_inverse=True)
        inverse = inverse.reshape(-1)
        active_classes = [len(np.unique(inverse[active[:, g]])) for g in range(matrix.shape[1])]
        per_task[task] = {
            'grids': int(matrix.shape[1]), 'roots': int(matrix.shape[0]),
            'default_share': float(default.mean()), 'stopped_share': float(stopped.mean()),
            'active_roots': float(active.sum(axis=0).mean()), 'active_classes': float(np.mean(active_classes)),
        }
    summary = {key: float(np.mean([record[key] for record in per_task.values()])) for key in ('default_share', 'stopped_share', 'active_roots', 'active_classes', 'roots')}
    summary['tasks'] = len(per_task)
    write_json_atomic(RESULTS / a.test / f'sparsity{a.suffix}.d{a.d}.json', {'summary': summary, 'per_task': per_task})
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
