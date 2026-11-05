#!/usr/bin/env python
"""Candidate recognition at size 1, from the stored rows of results/candidate-tables/.

A closed root names no column of the table hole T, and a pool costs at least 2, so at size 1 the
roots with both T and an `output` leaf are `nonempty` and `cardinality` over `join` and `antijoin`
with no column pair. Each reads T's count of rows alone, so this computes them from the counts.
"""
import glob
import json
import random
from pathlib import Path

import numpy as np

from common import RESULTS, ROOT, write_json_atomic


def root_vector(counts, outputs):
    """The value of each root at each train pair: a list per root."""
    return [
        [a > 0 for a in counts],                                    # nonempty (join T output)
        [a * o for a, o in zip(counts, outputs)],                   # cardinality (join T output)
        [False for _ in counts],                                    # nonempty (antijoin T output)
        [0 for _ in counts],                                        # cardinality (antijoin T output)
        [a == 0 for a in counts],                                   # nonempty (antijoin output T)
        [o if a == 0 else 0 for a, o in zip(counts, outputs)],      # cardinality (antijoin output T)
    ]


def stable(vector):
    return all(value is not None for value in vector) and len({value for value in vector}) == 1


def counts_of(table, train):
    return [len(table['rows'][f'train/{i}']) if f'train/{i}' in table['rows'] else None for i in range(train)]


def score(table_counts, outputs, contingent):
    if not contingent:
        return 0.0
    roots = guarded(table_counts, outputs)
    return sum(stable(roots[at]) for at in contingent) / len(contingent)


def guarded(counts, outputs):
    if any(count is None for count in counts):
        known = [0 if count is None else count for count in counts]
        roots = root_vector(known, outputs)
        return [[None if count is None else value for value, count in zip(root, counts)] for root in roots]
    return root_vector(counts, outputs)


def classes_of(all_counts, outputs):
    """A representative of each class of roots over the task's instances."""
    vectors = [[] for _ in range(6)]
    for counts in all_counts:
        for at, root in enumerate(guarded(counts, outputs)):
            vectors[at].extend(root)
    seen, keep = set(), []
    for at, vector in enumerate(vectors):
        key = tuple(map(repr, vector))
        if key not in seen:
            seen.add(key)
            keep.append(at)
    return keep


def item_scores(item, inputs, outputs, train):
    reads = [counts_of(table, train) for table in item['reads'].values()]
    gold = counts_of(item['gold'], train)
    mutants = [counts_of(mutant['table'], train) for mutant in item['mutants']]
    keep = classes_of([inputs, gold, *reads, *mutants], outputs)
    contingent = [at for at in keep if any(not stable(guarded(counts, outputs)[at]) for counts in [inputs, *reads])]
    return score(gold, outputs, contingent), [score(mutant, outputs, contingent) for mutant in mutants], len(contingent)


def auc_items(scores):
    values = []
    for gold, mutants, _ in scores:
        for mutant in mutants:
            values.append(1.0 if gold > mutant else 0.5 if gold == mutant else 0.0)
    return float(np.mean(values)) if values else None


def main():
    per_task = {}
    rng = random.Random(23)
    for path in sorted(glob.glob(str(RESULTS / 'candidate-tables/????????.json'))):
        data = json.load(open(path))
        if not data['items']:
            continue
        task = json.load(open(ROOT / f"data/tasks/{data['task']}.json"))
        train = data['train']
        inputs = [sum(len(row) for row in task['train'][i]['input']) for i in range(train)]
        outputs = [sum(len(row) for row in task['train'][i]['output']) for i in range(train)]
        rest = [item for item in data['items'] if item['query'] != data['last_query']]
        last = [item for item in data['items'] if item['query'] == data['last_query']]
        scores = [item_scores(item, inputs, outputs, train) for item in rest]
        scores_last = [item_scores(item, inputs, outputs, train) for item in last]
        grids = [json.dumps(task['train'][i]['output']) for i in range(train)]
        nulls = []
        if len(set(grids)) > 1:
            for _ in range(20):
                order = list(range(train))
                while any(order[i] == i for i in range(train)):
                    rng.shuffle(order)
                moved = [outputs[at] for at in order]
                nulls.append(auc_items([item_scores(item, inputs, moved, train) for item in rest]))
        nulls = [value for value in nulls if value is not None]
        per_task[data['task']] = {
            'auc': auc_items(scores), 'auc_last': auc_items(scores_last), 'null': float(np.mean(nulls)) if nulls else None,
            'items': sum(len(found[1]) for found in scores), 'contingent': float(np.mean([found[2] for found in scores])) if scores else 0.0,
            'with_contingent': float(np.mean([found[2] > 0 for found in scores])) if scores else 0.0,
        }
    aucs = np.array([record['auc'] for record in per_task.values() if record['auc'] is not None])
    rng_np = np.random.default_rng(7)
    means = aucs[rng_np.integers(0, len(aucs), (2000, len(aucs)))].mean(axis=1)
    summary = {
        'tasks': len(aucs), 'auc': float(aucs.mean()), 'interval_99': [float(np.quantile(means, .005)), float(np.quantile(means, .995))],
        'null': float(np.mean([record['null'] for record in per_task.values() if record['null'] is not None])),
        'auc_last': float(np.mean([record['auc_last'] for record in per_task.values() if record['auc_last'] is not None])),
        'items': int(sum(record['items'] for record in per_task.values())),
        'contingent_classes_mean': float(np.mean([record['contingent'] for record in per_task.values()])),
        'share_queries_with_contingent': float(np.mean([record['with_contingent'] for record in per_task.values()])),
    }
    out = Path(RESULTS / 'candidate')
    out.mkdir(exist_ok=True)
    write_json_atomic(out / 'size1.json', {'summary': summary, 'per_task': per_task})
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
