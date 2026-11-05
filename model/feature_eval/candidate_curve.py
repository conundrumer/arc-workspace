#!/usr/bin/env python
"""The curve of Candidate recognition on shapes from the native walk's results: per size and rate of
the shapes sampled, the mean over tasks of the AUC, the null and the gain over it, with 99% intervals,
paired with the first version's line where it exists.

  uv run python model/feature_eval/candidate_curve.py
"""
import glob
import json
import re

import numpy as np

from common import RESULTS, write_json_atomic


def bootstrap(values):
    values = np.array(values, dtype=float)
    rng = np.random.default_rng(7)
    means = values[rng.integers(0, len(values), (2000, len(values)))].mean(axis=1)
    return [float(np.quantile(means, 0.005)), float(np.quantile(means, 0.995))]


def reference():
    out = {}
    for path in glob.glob(str(RESULTS / 'candidate-reference-active/????????.json')):
        record = json.load(open(path))
        if record.get('auc') is not None and record.get('null') is not None:
            out[record['task']] = record
    return out


def main():
    found = {}
    for path in glob.glob(str(RESULTS / 'candidate/walk/*.json')):
        match = re.search(r'\.d(\d+)\.r(\d+)\.json$', path)
        if not match:
            continue
        record = json.load(open(path))
        for row in record['sizes']:
            found.setdefault((row['d'], int(match.group(2)), int(match.group(1))), []).append((record, row))
    first = reference()
    curve = []
    for (d, rate, top), held in sorted(found.items()):
        aucs = [row['auc'] for _, row in held if row['auc'] is not None]
        gains = [row['auc'] - row['null'] for _, row in held if row['auc'] is not None and row['null'] is not None]
        last = [row['auc_last'] for _, row in held if row['auc_last'] is not None]
        item = {
            'd': d, 'rate_per_million': rate, 'top': top, 'tasks': len(aucs), 'bounded': bool(held[0][0]['bounded']),
            'auc': float(np.mean(aucs)) if aucs else None, 'interval_99': bootstrap(aucs) if len(aucs) > 1 else None,
            'null': float(np.mean([row['null'] for _, row in held if row['null'] is not None])) if gains else None,
            'gain_over_null': float(np.mean(gains)) if gains else None, 'gain_interval_99': bootstrap(gains) if len(gains) > 1 else None,
            'auc_last': float(np.mean(last)) if last else None,
            'contingent_classes': float(np.mean([row['contingent'] or 0 for _, row in held])),
            'left_out_items': int(sum(len(record['left_out']) for record, _ in held)),
            'seconds_mean': float(np.mean([record['seconds'] for record, _ in held])),
        }
        paired = [row['auc'] - first[record['task']]['auc'] for record, row in held if record['task'] in first and row['auc'] is not None]
        if paired:
            item['paired_with_first_version'] = float(np.mean(paired))
            item['paired_interval_99'] = bootstrap(paired)
        curve.append(item)
        print(json.dumps(item))
    write_json_atomic(RESULTS / 'candidate/curve.json', {'statistic': 'shares of active classes', 'curve': curve})


if __name__ == '__main__':
    main()
