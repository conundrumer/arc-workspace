#!/usr/bin/env python
"""The curves of a recognition test so far: per d, the mean over tasks, its 99% bootstrap
interval over tasks, the null, and the roots and classes.

  uv run python model/feature_eval/curve.py scene-input|rule-base [--suffix .n20] [--max-d D] [--nulls 20]

It reads the results that exist, and writes results/<test>/curve<suffix>.json.
"""
import argparse
import json
import random
import re
from collections import defaultdict

import numpy as np

from common import RESULTS, write_json_atomic

# The words of an aggregate on no rows, in the value files of the slower path.
DEFAULT_WORDS = np.array([1 << 61, 1 << 62], dtype=np.uint64)


def per_task(test, suffix, d):
    out = {}
    for path in sorted((RESULTS / test).glob(f'*{suffix}.d{d}.json')):
        if not re.match(r'[0-9a-f]{8}\.', path.name):
            continue
        record = json.load(open(path))
        out[record['task']] = record
    return out


def bootstrap(values, seed=7, draws=2000):
    values = np.array(values, dtype=float)
    if len(values) == 0:
        return None, None
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), (draws, len(values)))].mean(axis=1)
    return float(np.quantile(means, 0.005)), float(np.quantile(means, 0.995))


def null_auc(test, suffix, tasks, d, draws, seed=11):
    """The AUC with the claims from another task, drawn at random, per (task, draw). A unit of
    the statistic is a distinct pair of a value vector over this task's instances and a claim, so
    a statement counts once however many roots write it."""
    if len(tasks) < 2:
        return None
    from common import claims_of, read_values
    loaded = {}
    for task, record in tasks.items():
        names, sizes, matrix = read_values(RESULTS / test / 'values' / f'{task}{suffix}.values.tsv', d)
        _, inverse = np.unique(matrix, axis=0, return_inverse=True)
        loaded[task] = (names, matrix, inverse.reshape(-1), record)
    orders = {task: {name: at for at, name in enumerate(names)} for task, (names, _, _, _) in loaded.items()}
    claims = {}
    for task, (names, matrix, _, record) in loaded.items():
        items = record.get('per_input') or record.get('per_pair')
        anchors = inputs_of(test, task, suffix, len(items))
        rows = []
        for h in range(len(items)):
            others = [place for k, place in enumerate(anchors) if k != h]
            rows.append(claims_of(matrix, others))
        claims[task] = rows
    rng = random.Random(seed)
    per_draw = []
    order = sorted(loaded)
    for _ in range(draws):
        per_task_auc = []
        for task in order:
            names, matrix, inverse, record = loaded[task]
            items = record.get('per_input') or record.get('per_pair')
            places_of = places_for(test, task, suffix, len(items))
            aucs = []
            for h, (true_place, near) in enumerate(places_of):
                if not near:
                    continue
                other = rng.choice([t for t in order if t != task])
                mask, value = rng.choice(claims[other])
                other_order = orders[other]
                here = [at for at, name in enumerate(names) if name in other_order]
                there = [other_order[names[at]] for at in here]
                # An active claim: not a root's value on no rows, and not no value.
                claim_values = value[np.array(there)] if there else np.zeros(0, dtype=np.uint64)
                keep = mask[there] & ~np.isin(claim_values, DEFAULT_WORDS) & (claim_values != 0)
                if not keep.any():
                    aucs.append(0.5)
                    continue
                at = np.array(here)[keep]
                claim = value[np.array(there)[keep]]
                units, first = np.unique(np.stack([inverse[at], claim.astype(np.int64)], axis=1), axis=0, return_index=True)
                at, claim = at[first], claim[first]
                v_true = float((matrix[at, true_place] != claim).mean())
                v_near = (matrix[at][:, near] != claim[:, None]).mean(axis=0)
                aucs.append(float(np.mean(v_true < v_near) + 0.5 * np.mean(v_true == v_near)))
            if aucs:
                per_task_auc.append(float(np.mean(aucs)))
        per_draw.append(float(np.mean(per_task_auc)))
    return float(np.mean(per_draw))


def inputs_of(test, task, suffix, count):
    if test.startswith('scene'):
        import scene
        limit = int(suffix[2:]) if suffix.startswith('.n') else None
        _, places, _ = scene.items_of(task, limit)
        return places
    return list(range(count))


def places_for(test, task, suffix, count):
    if test.startswith('scene'):
        import scene
        limit = int(suffix[2:]) if suffix.startswith('.n') else None
        _, places, negatives = scene.items_of(task, limit)
        return list(zip(places, negatives))
    import rule
    _, _, near = rule.items_of(task)
    return [(h, [place for place, _ in near[h]]) for h in range(count)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('test')
    parser.add_argument('--suffix', default='')
    parser.add_argument('--max-d', type=int, default=1)
    parser.add_argument('--nulls', type=int, default=20)
    a = parser.parse_args()
    curve = []
    for d in range(1, a.max_d + 1):
        tasks = per_task(a.test, a.suffix, d)
        tasks = {task: record for task, record in tasks.items() if record['auc'] is not None}
        aucs = [record['auc'] for record in tasks.values()]
        if not aucs:
            continue
        low, high = bootstrap(aucs)
        null = null_auc(a.test, a.suffix, tasks, d, a.nulls) if a.nulls else None
        items_key = 'per_input' if a.test.startswith('scene') else 'per_pair'
        all_items = [item for record in tasks.values() for item in record[items_key]]
        row = {
            'd': d,
            'tasks': len(aucs),
            'auc': float(np.mean(aucs)),
            'auc_root': float(np.mean([record['auc_root'] for record in tasks.values() if record.get('auc_root') is not None])),
            'interval_99': [low, high],
            'null': null,
            'roots_mean': float(np.mean([record['roots'] for record in tasks.values()])),
            'classes_mean': float(np.mean([record['classes'] for record in tasks.values()])),
            'classes_min': int(np.min([record['classes'] for record in tasks.values()])),
            'classes_max': int(np.max([record['classes'] for record in tasks.values()])),
            'false_rule_out_rate': float(np.mean([item['false_rule_out'] for item in all_items])),
            'rule_out_rate': float(np.mean([item['rule_outs'] for item in all_items if item['rule_outs'] is not None])),
            'no_claim_share': float(np.mean([item['claims'] == 0 for item in all_items])),
            'claims_mean': float(np.mean([item['claims'] for item in all_items])),
        }
        if not a.test.startswith('scene'):
            for key in ('auc_survive', 'auc_other'):
                values = [np.mean([item[key] for item in record[items_key] if item.get(key) is not None]) for record in tasks.values() if any(item.get(key) is not None for item in record[items_key])]
                row[key] = float(np.mean(values)) if values else None
        curve.append(row)
        print(json.dumps(row, indent=None))
    write_json_atomic(RESULTS / a.test / f'curve{a.suffix}.json', {'test': a.test, 'suffix': a.suffix, 'curve': curve})


if __name__ == '__main__':
    main()
