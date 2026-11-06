#!/usr/bin/env python
"""Whether the two-table family tells which pairs of gold tables a later gold query reads together.

  state_pairs.py STATE_ROOT OUT [--seeds N]

STATE_ROOT holds `lists/` and, for the deranged outputs, `null/`, as `candidate-lists --state-only` writes them. A row is
a pair of a gold table T and an earlier table U of a task. Its label says whether some later gold form reads both. A
fit on train tasks is read on dev tasks, from what the files hold so far: over a baseline of the two tables' column types and
their places in the graph, over every two-table shape on the true outputs, beside and without that baseline, and over the
shapes that read an output, on the true outputs and on the deranged ones. A first number is each shape's own read:
how much more often it has a value on pairs that a later query reads than on the others, over tasks, against the same number
on the deranged outputs.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import lightgbm as lgb
import numpy as np
import scipy.sparse as sp
from scipy.stats import rankdata

sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate import read_lists  # noqa: E402
from common import open_text, read_json  # noqa: E402
from state_tables import ROOT as TABLES_ROOT, tables_file  # noqa: E402

READS_OUTPUT = 2
SPLITS = 'work/lm/data-study/samples/split.tsv'


def roc_auc_score(labels, scores):
    ranks = rankdata(scores)
    positive = labels.sum()
    return (ranks[labels == 1].sum() - positive * (positive + 1) / 2) / (positive * (len(labels) - positive))


def splits():
    parts = {}
    for line in open_text(SPLITS):
        fields = line.rstrip('\n').split('\t')
        if fields[0] != 'task':
            parts[fields[0]] = fields[1]
    return parts


def name_flags(root):
    """Each shape's name and what it reads, from every names file."""
    names, flags = {}, {}
    for folder in ('lists', 'null'):
        for path in sorted((root / folder).glob('names*.tsv.zst')):
            try:
                for line in open_text(path):
                    fields = line.rstrip('\n').split('\t')
                    if len(fields) == 4:
                        key = int(fields[0], 16)
                        names[key], flags[key] = fields[1], int(fields[2])
            except Exception:
                continue
    return names, flags


def task_tables(task):
    """A task's tables with their state: those with Ident sources where a rebuild has written them."""
    for split in ('train', 'dev'):
        path = TABLES_ROOT.parent / 'all-rows' / split / 'candidate-tables' / f'{task}.json.zst'
        if path.exists():
            return read_json(path)
    return tables_file(task)


def baseline_of(first, second, prefix, nodes):
    """What a pair's column types and its places in the graph give, with no table content."""
    reads = {node['name']: node['reads'] for node in nodes}
    depth = {}
    for node in sorted(nodes, key=lambda node: node['form']):
        depth[node['name']] = max((depth[read] + 1 for read in node['reads'] if read in depth), default=0)
    reached, stack = set(), list(reads.get(first, []))
    while stack:
        at = stack.pop()
        if at not in reached:
            reached.add(at)
            stack.extend(reads.get(at, []))
    out = Counter()
    own = [ty.split('@')[0] for ty in prefix[first]['types']] if first in prefix else []
    theirs = [ty.split('@')[0] for ty in prefix[second]['types']] if second in prefix else []
    for ty in own:
        out['t:' + ty] += 1
    for ty in theirs:
        out['u:' + ty] += 1
    out['shared'] = sum((Counter(own) & Counter(theirs)).values())
    out['parent'] = int(second in reads.get(first, []))
    out['ancestor'] = int(second in reached)
    out['t_depth'] = depth.get(first, 0)
    out['u_depth'] = depth.get(second, 0)
    out['read_by'] = sum(second in node['reads'] for node in nodes)
    return out


def joined_pairs(nodes):
    """The pairs of names that some form reads together, each with the latest such form."""
    reads_at = {node['form']: node['reads'] for node in nodes}
    latest = {}
    for form, reads in reads_at.items():
        for at, first in enumerate(reads):
            for second in reads[at + 1:]:
                for key in ((first, second), (second, first)):
                    latest[key] = max(latest.get(key, -1), form)
    return latest


def pair_rows(path, task):
    """Each gold pair: its entries and whether a later gold form reads both tables."""
    head, lists = read_lists(path)
    names_of = defaultdict(list)
    for name, place in head['places'].items():
        names_of[place].append(name)
    data = task_tables(task)
    nodes, prefix = data['state']['nodes'], data['prefix']
    latest = joined_pairs(nodes)
    form_of = {}
    for item in head['items']:
        form_of.setdefault(item['gold'], item['form'])
    rows = []
    for owner, (ids, values) in lists.items():
        if not owner.startswith('edge/'):
            continue
        _, t, u = owner.split('/')
        t, u = int(t), int(u)
        form = form_of.get(t, -1)
        joined = any(latest.get((a, b), -1) > form for a in names_of[t] for b in names_of[u])
        rows.append((t, u, joined, ids, values, baseline_of(names_of[t][0], names_of[u][0], prefix, nodes) if names_of[t] and names_of[u] else Counter()))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('out')
    parser.add_argument('--seeds', type=int, default=3)
    args = parser.parse_args()
    root, out = Path(args.root), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    parts = splits()
    names, flags = name_flags(root)
    reads_output = {key for key, flag in flags.items() if flag & READS_OUTPUT}
    print('shapes', len(names), 'that read an output', len(reads_output), flush=True)
    tables = {}
    for kind in ('lists', 'null'):
        held = []
        for path in sorted((root / kind).glob('*.lists.zst')):
            task = path.name.split('.')[0]
            if task not in parts or parts[task] not in ('train', 'dev') or task == '981571dc':
                continue
            try:
                held.extend((task, parts[task], row) for row in pair_rows(path, task))
            except Exception as error:
                print('left out', task, type(error).__name__, flush=True)
        tables[kind] = held
        print(kind, 'pairs', len(held), 'tasks', len({row[0] for row in held}), 'joined', sum(row[2][2] for row in held), flush=True)
    # The tasks on both sides, for one comparison.
    both = {row[0] for row in tables['lists']} & {row[0] for row in tables['null']}
    results = {}
    columns = {}
    for kind, held in tables.items():
        for task, split, row in held:
            if split == 'train' and task in both:
                for shape in row[3].tolist():
                    if shape in reads_output:
                        columns.setdefault(shape, len(columns))
    print('columns that read an output', len(columns), flush=True)
    # Each shape's own read on train tasks.
    def own_read(held):
        rate = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))
        for task, split, row in held:
            if split != 'train' or task not in both:
                continue
            joined = row[2]
            for shape, value in zip(row[3].tolist(), row[4].tolist()):
                if shape in columns and value == value and value != 0:
                    rate[shape][task][0 if joined else 1] += 1
            counts = rate['pairs'][task]
            counts[0 if joined else 1] += 1
        pairs = rate.pop('pairs')
        reads = {}
        for shape, tasks in rate.items():
            gaps = []
            for task, counts in tasks.items():
                on, off = pairs[task][:2]
                if on and off:
                    gaps.append(counts[0] / on - counts[1] / off)
            if len(gaps) >= 10:
                reads[shape] = (float(np.mean(gaps)), len(gaps))
        return reads
    true_read, null_read = own_read(tables['lists']), own_read(tables['null'])
    order = sorted(true_read, key=lambda shape: -abs(true_read[shape][0] - null_read.get(shape, (0, 0))[0]))
    with open(out / 'shapes.tsv', 'w') as file:
        for shape in order:
            file.write(f'{true_read[shape][0]:.4f}\t{null_read.get(shape, (0, 0))[0]:.4f}\t{true_read[shape][1]}\t{names.get(shape, "")}\n')
    for shape in order[:15]:
        print(f'{true_read[shape][0]:+.3f} {null_read.get(shape, (0, 0))[0]:+.3f} tasks {true_read[shape][1]} {names.get(shape, "")[:110]}', flush=True)
    # A fit on train tasks, read on dev tasks.
    def matrix(held, split, columns, with_baseline):
        data, rows, cols, labels, groups = [], [], [], [], []
        for task, own, row in held:
            if own != split or task not in both:
                continue
            at = len(labels)
            labels.append(int(row[2]))
            groups.append(task)
            for shape, value in zip(row[3].tolist(), row[4].tolist()):
                place = columns.get(shape)
                if place is not None:
                    rows.append(at)
                    cols.append(place)
                    data.append(value)
            if with_baseline:
                for name, value in row[5].items():
                    place = baseline_columns.get(name)
                    if place is not None:
                        rows.append(at)
                        cols.append(len(columns) + place)
                        data.append(value)
        width = len(columns) + (len(baseline_columns) if with_baseline else 0)
        return sp.csr_matrix((data, (rows, cols)), shape=(len(labels), width), dtype=np.float32), np.array(labels), groups
    every_shape = {}
    for task, split, row in tables['lists']:
        if split == 'train':
            for shape in row[3].tolist():
                every_shape.setdefault(shape, len(every_shape))
    print('columns of every two-table shape', len(every_shape), flush=True)
    baseline_columns = {}
    for task, split, row in tables['lists']:
        if split == 'train':
            for name in row[5]:
                baseline_columns.setdefault(name, len(baseline_columns))
    sets = [('baseline', tables['lists'], {}, True), ('every_shape', tables['lists'], every_shape, False), ('baseline+every_shape', tables['lists'], every_shape, True),
            ('baseline+output', tables['lists'], columns, True), ('baseline+output_deranged', tables['null'], columns, True), ('output', tables['lists'], columns, False), ('output_deranged', tables['null'], columns, False)]
    for kind, held, own_columns, with_baseline in sets:
        train_x, train_y, _ = matrix(held, 'train', own_columns, with_baseline)
        dev_x, dev_y, dev_groups = matrix(held, 'dev', own_columns, with_baseline)
        if not len(dev_y) or len(set(dev_y.tolist())) < 2:
            print(kind, 'no dev pairs of both labels yet', flush=True)
            continue
        scores = np.zeros(len(dev_y))
        for seed in range(args.seeds):
            parameters = dict(objective='binary', learning_rate=0.05, num_leaves=15, feature_fraction=0.5, min_data_in_leaf=10, seed=seed, num_threads=2, verbose=-1)
            scores += lgb.train(parameters, lgb.Dataset(train_x, label=train_y), 200).predict(dev_x)
        by_task = []
        groups = np.array(dev_groups)
        for task in sorted(set(dev_groups)):
            mask = groups == task
            if 0 < dev_y[mask].sum() < mask.sum():
                by_task.append(roc_auc_score(dev_y[mask], scores[mask]))
        results[kind] = dict(pooled=float(roc_auc_score(dev_y, scores)), by_task=float(np.mean(by_task)) if by_task else None, tasks=len(by_task), pairs=int(len(dev_y)), joined=int(dev_y.sum()), train_pairs=int(len(train_y)))
        print(kind, json.dumps(results[kind]), flush=True)
    (out / 'fit.json').write_text(json.dumps(results, indent=1))


if __name__ == '__main__':
    main()
