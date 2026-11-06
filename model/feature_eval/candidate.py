#!/usr/bin/env python
"""Candidate recognition of docs/feature-spec/evaluation-protocol.md, from `candidate-lists`.

  python model/feature_eval/candidate.py ROOT [--shapes output|all]

ROOT holds `lists/`, each table's stable roots on the true outputs, and `null/`, the same on
deranged outputs, with each task's split from work/lm/data-study/samples/split.tsv. It prints, per
split and size, the mean over tasks of the AUC, the null and the gain, on the pairs where the mutant
has rows at every train pair and on every pair, the share of pairs the list speaks on, and how often
it favors the query there.
"""
import argparse
import json
import random
import statistics as st
import struct
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import zstandard

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT as REPO, open_text  # noqa: E402

READS_OUTPUT = 2


def read_lists(path, graded=False):
    """A task's lists: per table, its stable shapes and their values. With `graded`, also its other active
    shapes and each one's least, mean and greatest."""
    raw = zstandard.ZstdDecompressor().stream_reader(open(path, 'rb')).read()
    size = struct.unpack('<Q', raw[:8])[0]
    head = json.loads(raw[8:8 + size])
    at = 8 + size
    dictionary = np.frombuffer(raw, dtype='<u8', count=head['shapes'], offset=at)
    at += 8 * head['shapes']
    lists = {}
    others = {}
    for held in head['lists']:
        places = np.frombuffer(raw, dtype='<u4', count=held['count'], offset=at)
        at += 4 * held['count']
        values = np.frombuffer(raw, dtype='<f4', count=held['count'], offset=at)
        at += 4 * held['count']
        lists[held['owner']] = (dictionary[places], values)
        count = held.get('graded', 0)
        places = np.frombuffer(raw, dtype='<u4', count=count, offset=at)
        at += 4 * count
        numbers = np.frombuffer(raw, dtype='<f4', count=3 * count, offset=at).reshape(3, count)
        at += 12 * count
        others[held['owner']] = (dictionary[places], numbers[0], numbers[1], numbers[2])
    return (head, lists, others) if graded else (head, lists)


def read_names(root):
    """Per shape, what it reads and its size."""
    flags, sizes = {}, {}
    for folder in ('lists', 'null'):
        path = Path(root) / folder / 'names.tsv'
        try:
            lines = open_text(path)
        except OSError:
            continue
        for line in lines:
            parts = line.rstrip('\n').split('\t')
            if len(parts) == 4:
                key = int(parts[0], 16)
                flags[key], sizes[key] = int(parts[2]), int(parts[3])
    return flags, sizes


def item_masks(item, lists, null_side, base_lists, keep):
    """Per contingent class of an item, its mask over the item's tables: the query first, then its
    mutants. A root is contingent where the input or a table the query reads does not have it as
    stable."""
    tables = [item['gold']] + [m['table'] for m in item['mutants']]
    own = [set(lists[t][0].tolist()) if t in lists else set() for t in tables]
    bases = [set(base_lists['input'][0].tolist())] + [set(base_lists[p][0].tolist()) if p in base_lists else set() for p in item['parents']]
    common = set.intersection(*bases)
    masks = set()
    for root in set().union(*own) - common:
        if not keep(root):
            continue
        mask = 0
        for at, held in enumerate(own):
            if root in held:
                mask |= 1 << at
        masks.add(mask)
    return len(tables), masks


def outcomes(count, masks):
    """Per mutant, +1 where the query's score is above its, -1 where below, and 0 at a tie."""
    scores = [sum((mask >> at) & 1 for mask in masks) for at in range(count)]
    return [(score < scores[0]) - (score > scores[0]) for score in scores[1:]]


def boot(values, draws=2000):
    rng = random.Random(1)
    means = sorted(st.mean(rng.choices(values, k=len(values))) for _ in range(draws))
    return means[int(.005 * draws)], means[int(.995 * draws)]


def has_rows(head, table):
    return all(head['train_rows'][table])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('--shapes', choices=['output', 'all'], default='output')
    parser.add_argument('--extra', action='store_true', help='also read the mutants marked extra')
    a = parser.parse_args()
    root = Path(a.root)
    split = {}
    for line in (REPO / 'work/lm/data-study/samples/split.tsv').read_text().splitlines()[1:]:
        task, part, _ = line.split('\t')
        split[task] = part
    flags, sizes = read_names(root)
    top = max(sizes.values(), default=2)
    tallies = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0]))
    files = sorted((root / 'lists').glob('*.lists.zst'))
    for path in files:
        task = path.name.split('.')[0]
        head, lists = read_lists(path)
        null_path = root / 'null' / path.name
        null_lists = read_lists(null_path)[1] if null_path.exists() else None
        # Each table's null list is its list with each root that reads the output as the deranged
        # outputs give it.
        for size in range(1, top + 1):
            keep = lambda key, size=size: sizes.get(key, 0) <= size and (a.shapes == 'all' or flags.get(key, 0) & READS_OUTPUT)
            for item in head['items']:
                if item['last']:
                    continue
                if not a.extra:
                    item = {**item, 'mutants': [m for m in item['mutants'] if not m.get('extra')]}
                if not item['mutants']:
                    continue
                count, masks = item_masks(item, lists, None, lists, keep)
                true = outcomes(count, masks)
                null = None
                if null_lists is not None:
                    merged = {}
                    for owner in set(lists) | set(null_lists):
                        if owner in ('ex_output', 'constants'):
                            continue
                        own = lists.get(owner, (np.zeros(0, dtype=np.uint64), None))[0].tolist()
                        other = null_lists.get(owner, (np.zeros(0, dtype=np.uint64), None))[0].tolist()
                        merged[owner] = (np.array([key for key in own if not flags.get(key, 0) & READS_OUTPUT] + other, dtype=np.uint64), None)
                    count, masks = item_masks(item, merged, None, merged, keep)
                    null = outcomes(count, masks)
                for at, (mutant, won) in enumerate(zip(item['mutants'], true)):
                    lost = null[at] if null is not None else None
                    for label in ('every',) + (('rows',) if has_rows(head, mutant['table']) else ()):
                        held = tallies[(split[task], size, label)][task]
                        held[0] += 1
                        held[1] += won > 0
                        held[2] += won < 0
                        if lost is not None:
                            held[3] += 1
                            held[4] += lost > 0
                            held[5] += lost < 0
    for (part, size, label), by_task in sorted(tallies.items()):
        auc = {t: .5 + (h[1] - h[2]) / (2 * h[0]) for t, h in by_task.items()}
        null = {t: .5 + (h[4] - h[5]) / (2 * h[3]) for t, h in by_task.items() if h[3]}
        gain = [auc[t] - null[t] for t in null]
        pairs = sum(h[0] for h in by_task.values())
        speak = sum(h[1] + h[2] for h in by_task.values())
        favor = sum(h[1] for h in by_task.values()) / max(speak, 1)
        null_speak = sum(h[4] + h[5] for h in by_task.values())
        null_favor = sum(h[4] for h in by_task.values()) / max(null_speak, 1)
        line = f'{part:6} size<={size} {label:6} tasks {len(auc):4} pairs {pairs:6} AUC {st.mean(auc.values()):.3f}'
        if len(gain) > 1:
            low, high = boot(gain)
            line += f' null {st.mean(null.values()):.3f} gain {st.mean(gain):+.3f} ({low:+.3f}, {high:+.3f})'
        line += f' speaks {speak / max(pairs, 1):.3f} favors {favor:.3f} | null speaks {null_speak / max(pairs, 1):.3f} favors {null_favor:.3f}'
        print(line, flush=True)


if __name__ == '__main__':
    main()
