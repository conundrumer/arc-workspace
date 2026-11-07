#!/usr/bin/env python
"""How well each first-version feature alone tells a ground-truth table from its mutants, on the tables that v1_dump.py wrote.

  v1_tell.py OUT.tsv --v1 DIR [--tasks N]

A comparison is a table of the ground-truth program and the same table of a dumped mutant, at one train pair, where the feature has a value on both. Within a task,
`tell` is the share of comparisons where the ground truth's value is higher, with a tie as half. A line gives the mean of `tell` over the tasks, its 99% interval over the
tasks, and the share of comparisons where the two values differ. Features are in the shape form of v1_cover.py. OUT is written again after each 50 tasks, so a reader can
start on it early.
"""
import argparse
import collections
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import open_text  # noqa: E402
from v1_cover import collect  # noqa: E402


def features_of(pair, name, types_of, tables, coordinates, known):
    """A table's features at a pair, as {feature: number}, where a word's feature is 1 at the words the table has and 0 at the other words it could have."""
    out = collections.defaultdict(dict)
    collect(pair, name, types_of, tables, 'shape', out, 0, coordinates, {})
    plain, shapes = {}, {}
    for key, at in out.items():
        if isinstance(key, tuple):
            shapes[key[1]] = at[0]
        else:
            plain[key] = at[0]
    return plain, set(shapes)


def write(out, stats, tasks):
    """Writes each feature's line, the most telling first."""
    lines = []
    for feature, by_task in stats.items():
        tells = [(higher + (pairs - higher - lower) / 2) / pairs for pairs, higher, lower in by_task.values()]
        mean = sum(tells) / len(tells)
        spread = math.sqrt(sum((tell - mean) ** 2 for tell in tells) / max(len(tells) - 1, 1)) / math.sqrt(len(tells))
        pairs = sum(held[0] for held in by_task.values())
        differ = sum(held[1] + held[2] for held in by_task.values())
        lines.append((abs(mean - 0.5), feature, len(tells), pairs, differ / pairs, mean, mean - 2.576 * spread, mean + 2.576 * spread))
    lines.sort(reverse=True)
    with open(out, 'w') as sink:
        sink.write(f'feature\ttasks\tcomparisons\tdiffer\ttell\tlow\thigh\t# read {tasks} tasks\n')
        for _, feature, count, pairs, differ, mean, low, high in lines:
            sink.write(f'{feature}\t{count}\t{pairs}\t{differ:.3f}\t{mean:.3f}\t{low:.3f}\t{high:.3f}\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('out')
    parser.add_argument('--v1', required=True)
    parser.add_argument('--tasks', type=int)
    args = parser.parse_args()
    paths = sorted(Path(args.v1).glob('*.json.zst'))
    paths = paths[:args.tasks] if args.tasks else paths
    stats = collections.defaultdict(dict)
    started = time.time()
    for done, path in enumerate(paths, 1):
        with open_text(path) as lines:
            data = json.load(lines)
        task = data['task']
        tables = data.get('tables', {})
        coordinates = data.get('coordinates', {})
        types_of = {name: dict(columns) for name, columns in data['columns'].items()}
        for mutant in data.get('mutants', []):
            if 'pairs' not in mutant:
                continue
            own_types = dict(types_of)
            own_types.update({name: dict(columns) for name, columns in mutant['columns'].items()})
            for at, (gold, other) in enumerate(zip(data['pairs'], mutant['pairs'])):
                names = {key.split('|', 1)[0] for key in other}
                for name in names:
                    theirs, their_words = features_of(other, name, own_types, tables, coordinates, None)
                    ours, our_words = features_of(gold, name, types_of, tables, coordinates, None)
                    for shape in their_words & our_words:
                        prefix = f'{shape} :'
                        for feature in [key for key in (*ours, *theirs) if key.startswith(prefix)]:
                            ours.setdefault(feature, 0.0)
                            theirs.setdefault(feature, 0.0)
                    for feature in ours.keys() & theirs.keys():
                        held = stats[feature].setdefault(task, [0, 0, 0])
                        held[0] += 1
                        held[1] += ours[feature] > theirs[feature]
                        held[2] += ours[feature] < theirs[feature]
        if done % 50 == 0 or done == len(paths):
            write(args.out, stats, done)
            rate = done / (time.time() - started)
            print(f'{done}/{len(paths)} {rate:.2f}/s ETA {(len(paths) - done) / rate:.0f}s features {len(stats)}', flush=True)


if __name__ == '__main__':
    main()
