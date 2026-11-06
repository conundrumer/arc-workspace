#!/usr/bin/env python
"""The relational family's gain over the null, on train and on dev, and its shapes ranked on train.

  uv run python model/feature_eval/family_stats.py [--top N] [--folder family]

It reads results[/dev]/candidate/<folder>/, writes results/candidate/<folder>-stats.json, and writes
the top shapes on train to results/candidate/<folder>-top.txt, one per line, for the encoder's
`family --names`. A shape's own AUC is P(stable on gold and not on the mutant) + 0.5 P(tie), over the
comparisons it was contingent in, per task, and its gain is that less the same under the null.
"""
import argparse
import glob
import json

import numpy as np

from common import (RESULTS, glob_data, read_json, write_json_atomic)


def bootstrap(values):
    values = np.array(values, dtype=float)
    rng = np.random.default_rng(7)
    means = values[rng.integers(0, len(values), (2000, len(values)))].mean(axis=1)
    return [float(np.quantile(means, 0.005)), float(np.quantile(means, 0.995))]


def read(base, folder):
    return [read_json(path) for path in sorted(glob_data(str(base / 'candidate' / folder / '*.d*.json')))]


def family_line(records, d):
    rows = [record['sizes'][d - 1] for record in records if len(record['sizes']) >= d]
    aucs = [row['auc'] for row in rows if row['auc'] is not None]
    gains = [row['auc'] - row['null'] for row in rows if row['auc'] is not None and row['null'] is not None]
    last = [row['auc_last'] for row in rows if row['auc_last'] is not None]
    if not aucs:
        return None
    return {
        'd': d, 'tasks': len(aucs), 'auc': float(np.mean(aucs)),
        'null': float(np.mean([row['null'] for row in rows if row['null'] is not None])) if gains else None,
        'gain': float(np.mean(gains)) if gains else None, 'gain_interval_99': bootstrap(gains) if len(gains) > 1 else None,
        'auc_last': float(np.mean(last)) if last else None,
        'contingent': float(np.mean([row['contingent'] or 0 for row in rows])),
        **rows_line(rows),
        'left_out_items': int(sum(len(record['left_out']) for record in records)),
    }


def rows_line(rows):
    """The gain over the comparisons whose mutant has rows at every train pair."""
    gains = [row['auc_rows'] - row['null_rows'] for row in rows if row.get('auc_rows') is not None and row.get('null_rows') is not None]
    if not gains:
        return {}
    return {'rows_tasks': len(gains), 'rows_gain': float(np.mean(gains)), 'rows_interval_99': bootstrap(gains) if len(gains) > 1 else None}


def shape_table(records):
    """For each shape: its gain per task, with its tallies."""
    table = {}
    for record in records:
        for name, gold, mutant, compared, null_gold, null_mutant, null_compared in record['shapes']:
            if compared == 0:
                continue
            auc = (gold + 0.5 * (compared - gold - mutant)) / compared
            null = (null_gold + 0.5 * (null_compared - null_gold - null_mutant)) / null_compared if null_compared else 0.5
            held = table.setdefault(name, {'gains': [], 'gold': 0, 'mutant': 0, 'compared': 0})
            held['gains'].append(auc - null)
            held['gold'] += gold
            held['mutant'] += mutant
            held['compared'] += compared
    return table


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--top', type=int, default=30)
    parser.add_argument('--folder', default='family')
    a = parser.parse_args()
    train = read(RESULTS, a.folder)
    dev = read(RESULTS / 'dev', a.folder)
    out = {'train': [family_line(train, d) for d in (1, 2)], 'dev': [family_line(dev, d) for d in (1, 2)]}
    print(json.dumps(out))
    shapes = shape_table(train)
    dev_shapes = shape_table(dev)
    # The ranking reads train alone: a shape's gain summed over the tasks, so a shape that few
    # tasks have counts for less.
    tasks = max(len(train), 1)
    ranked = sorted(shapes.items(), key=lambda item: -sum(item[1]['gains']))
    def row_of(name, held):
        other = dev_shapes.get(name)
        return {
            'shape': name, 'score_train': float(sum(held['gains']) / tasks), 'net_train': held['gold'] - held['mutant'], 'gold_train': held['gold'], 'mutant_train': held['mutant'],
            'gain_train': float(np.mean(held['gains'])), 'tasks_train': len(held['gains']),
            'gain_dev': float(np.mean(other['gains'])) if other else None, 'score_dev': float(sum(other['gains']) / max(len(dev), 1)) if other else None, 'net_dev': other['gold'] - other['mutant'] if other else None, 'tasks_dev': len(other['gains']) if other else 0,
        }
    rows = [row_of(name, held) for name, held in ranked[:max(a.top, 30)]]
    target = [row_of(name, held) for name, held in shapes.items() if name.startswith('(cardinality (project (join T output (?1:Position P))') and name.endswith(' Col))')]
    out['output_colors'] = target
    print('output colors', json.dumps(target)[:400])
    out['top'] = rows
    (RESULTS / 'candidate' / f'{a.folder}-top.txt').write_text('\n'.join(row['shape'] for row in rows[:a.top]) + '\n')
    write_json_atomic(RESULTS / 'candidate' / f'{a.folder}-stats.json', out)
    for row in rows[:15]:
        print(round(row['score_train'], 4), row['tasks_train'], None if row['score_dev'] is None else round(row['score_dev'], 4), row['tasks_dev'], row['shape'][:120])


if __name__ == '__main__':
    main()
