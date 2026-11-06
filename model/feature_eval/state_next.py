#!/usr/bin/env python
"""Whether a task's pair numbers tell which lib names its gold program uses.

  state_next.py STATE_ROOT OUT [--seeds N]

STATE_ROOT holds `lists/` and `null/`, as `candidate-lists --state-only` writes them. A row is a task, and its features are
the least, the mean and the greatest of each shape of the `pair` list. Each label says whether the gold program uses one lib
relation, component or proposer. Each label is fit on train tasks and read on dev tasks, over the tasks in the files so far:
the shapes that read only the input, and the shapes that read an output, on the true outputs and on the deranged ones. The
true and deranged sets are compared by a bootstrap over dev tasks, on the mean AUC over labels. Each label's line is written
as it ends.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import lightgbm as lgb
import numpy as np
import scipy.sparse as sp
from scipy.stats import rankdata

sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate import read_lists  # noqa: E402
from common import read_json  # noqa: E402
from query_structure import Reader, parse_forms  # noqa: E402
from state_pairs import name_flags, roc_auc_score, splits  # noqa: E402
from state_tables import ROOT as TABLES_ROOT  # noqa: E402

READS_OUTPUT = 2
LABEL_KINDS = ('relation:', 'component:', 'proposer:')
MIN_TRAIN = 25
MIN_DEV = 6


def uses_of(task, split):
    forms = parse_forms(read_json(TABLES_ROOT / split / 'mutants' / f'{task}.json')['gold'])
    reader = Reader()
    for form in forms:
        reader.form(form)
    return {key for key, count in reader.bag.items() if count and key.startswith(LABEL_KINDS)}


def pair_entries(path):
    """Each shape of the list's least, mean and greatest."""
    _, lists, others = read_lists(path, graded=True)
    out = {}
    if 'pair' in lists:
        for shape, value in zip(lists['pair'][0].tolist(), lists['pair'][1].tolist()):
            out[shape] = (value, value, value)
    if 'pair' in others:
        held = others['pair']
        for shape, least, mean, most in zip(held[0].tolist(), held[1].tolist(), held[2].tolist(), held[3].tolist()):
            out[shape] = (least, mean, most)
    return out


def matrix(rows, columns):
    data, at_row, at_column = [], [], []
    for row, entries in enumerate(rows):
        for shape, numbers in entries.items():
            place = columns.get(shape)
            if place is not None:
                for offset, value in enumerate(numbers):
                    at_row.append(row)
                    at_column.append(3 * place + offset)
                    data.append(value)
    return sp.csr_matrix((data, (at_row, at_column)), shape=(len(rows), 3 * len(columns)), dtype=np.float32)


def mean_auc(scores, truth, rows):
    """The mean AUC over labels of the rows given, over the labels that have both classes among them."""
    held = []
    for label in range(truth.shape[1]):
        labels = truth[rows, label]
        positive = labels.sum()
        if 0 < positive < len(labels):
            ranks = rankdata(scores[rows, label])
            held.append((ranks[labels == 1].sum() - positive * (positive + 1) / 2) / (positive * (len(labels) - positive)))
    return float(np.mean(held))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('out')
    parser.add_argument('--seeds', type=int, default=5)
    parser.add_argument('--draws', type=int, default=1000)
    args = parser.parse_args()
    root, out = Path(args.root), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    parts = splits()
    _, flags = name_flags(root)
    sides = {kind: {path.name.split('.')[0]: path for path in (root / kind).glob('*.lists.zst')} for kind in ('lists', 'null')}
    tasks = sorted(task for task in set(sides['lists']) & set(sides['null']) if parts.get(task) in ('train', 'dev') and task != '981571dc')
    train = [task for task in tasks if parts[task] == 'train']
    dev = [task for task in tasks if parts[task] == 'dev']
    print('tasks', len(train), 'train', len(dev), 'dev', flush=True)
    labels = {task: uses_of(task, parts[task]) for task in tasks}
    counts = Counter(label for task in train for label in labels[task])
    dev_counts = Counter(label for task in dev for label in labels[task])
    wanted = sorted(label for label, count in counts.items() if count >= MIN_TRAIN and dev_counts[label] >= MIN_DEV and len(train) - count >= MIN_TRAIN and len(dev) - dev_counts[label] >= MIN_DEV)
    print('labels', len(wanted), flush=True)
    entries = {kind: {task: pair_entries(sides[kind][task]) for task in tasks} for kind in sides}
    seen = Counter(shape for task in train for shape in set(entries['lists'][task]) | set(entries['null'][task]))
    frequent = sorted(shape for shape, count in seen.items() if count >= 5)
    input_only = {shape: at for at, shape in enumerate(shape for shape in frequent if not flags.get(shape, 0) & READS_OUTPUT)}
    reads_output = {shape: at for at, shape in enumerate(shape for shape in frequent if flags.get(shape, 0) & READS_OUTPUT)}
    print('shapes that read only the input', len(input_only), 'that read an output', len(reads_output), flush=True)
    sets = {'input': ('lists', input_only), 'output': ('lists', reads_output), 'output_deranged': ('null', reads_output)}
    built = {name: (matrix([entries[kind][task] for task in train], columns), matrix([entries[kind][task] for task in dev], columns)) for name, (kind, columns) in sets.items()}
    truth = np.array([[label in labels[task] for label in wanted] for task in dev], dtype=int)
    scores = {name: np.zeros((len(dev), len(wanted))) for name in sets}
    per_seed = {name: np.zeros(args.seeds) for name in sets}
    with open(out / 'labels.tsv', 'w') as file:
        for at, label in enumerate(wanted):
            y_train = np.array([label in labels[task] for task in train], dtype=int)
            y_dev = truth[:, at]
            line = []
            for name, (x_train, x_dev) in built.items():
                for seed in range(args.seeds):
                    model = lgb.LGBMClassifier(n_estimators=100, learning_rate=0.05, num_leaves=7, feature_fraction=0.3, min_child_samples=5, seed=seed, n_jobs=2, verbose=-1)
                    model.fit(x_train, y_train)
                    predicted = model.predict_proba(x_dev)[:, 1]
                    scores[name][:, at] += predicted
                    per_seed[name][seed] += roc_auc_score(y_dev, predicted)
                line.append(f'{roc_auc_score(y_dev, scores[name][:, at]):.3f}')
            file.write('\t'.join([label, str(int(y_train.sum())), str(int(y_dev.sum())), *line]) + '\n')
            file.flush()
            print(label, int(y_train.sum()), int(y_dev.sum()), *line, flush=True)
    rows = np.arange(len(dev))
    summary = {name: dict(ensemble=mean_auc(scores[name], truth, rows), seeds_least=float((per_seed[name] / len(wanted)).min()), seeds_most=float((per_seed[name] / len(wanted)).max())) for name in sets}
    rng = np.random.default_rng(7)
    gaps = []
    for _ in range(args.draws):
        drawn = rng.integers(0, len(dev), len(dev))
        gaps.append(mean_auc(scores['output'], truth, drawn) - mean_auc(scores['output_deranged'], truth, drawn))
    summary['output_minus_deranged'] = dict(mean=summary['output']['ensemble'] - summary['output_deranged']['ensemble'], low=float(np.quantile(gaps, 0.005)), high=float(np.quantile(gaps, 0.995)), dev_tasks=len(dev), labels=len(wanted))
    print(json.dumps(summary), flush=True)
    (out / 'summary.json').write_text(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
