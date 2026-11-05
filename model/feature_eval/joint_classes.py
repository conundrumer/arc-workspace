#!/usr/bin/env python
"""Classes of closed roots with an equal value vector over the instances of all tasks jointly:
one vector needs one list across tasks, so per-task classes understate what a global list needs.

  uv run python model/feature_eval/joint_classes.py scene-input|rule-base [--suffix .n20] [--d D]
"""
import argparse
import json

import numpy as np

from common import RESULTS, eval_tasks, read_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('test')
    parser.add_argument('--suffix', default='')
    parser.add_argument('--d', type=int, default=1)
    a = parser.parse_args()
    tasks = []
    columns = {}
    blocks = []
    for task in eval_tasks(60):
        result = RESULTS / a.test / f'{task}{a.suffix}.d{a.d}.json'
        if not result.exists():
            continue
        names, _, matrix = read_values(RESULTS / a.test / 'values' / f'{task}{a.suffix}.values.tsv', a.d)
        tasks.append(task)
        blocks.append((names, matrix))
        for name in names:
            columns.setdefault(name, len(columns))
    roots = len(columns)
    width = sum(matrix.shape[1] for _, matrix in blocks)
    joined = np.zeros((roots, width), dtype=np.int64)
    spans = []
    at = 0
    for names, matrix in blocks:
        places = np.array([columns[name] for name in names])
        joined[places, at:at + matrix.shape[1]] = matrix
        spans.append((at, at + matrix.shape[1]))
        at += matrix.shape[1]
    by_count = {}
    for count in (10, 20, 40, 60):
        if count <= len(tasks):
            by_count[count] = len(np.unique(joined[:, :spans[count - 1][1]], axis=0))
    by_count[len(tasks)] = len(np.unique(joined, axis=0))
    unique = np.unique(joined, axis=0)
    constant_within = np.ones(len(unique), dtype=bool)
    for start, end in spans:
        constant_within &= np.all(unique[:, start:end] == unique[:, [start]], axis=1)
    constant_everywhere = np.all(unique == unique[:, [0]], axis=1)
    # What each class is, for a reader: its shortest name.
    print(json.dumps({'test': a.test, 'tasks': len(tasks), 'instances': width, 'roots': roots, 'classes_by_task_count': by_count,
                      'classes_constant_on_every_task': int(constant_within.sum()), 'classes_one_value_everywhere': int(constant_everywhere.sum())}))


if __name__ == '__main__':
    main()
