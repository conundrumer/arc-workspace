#!/usr/bin/env python
"""How many of a store's train rows each column has an entry on, for v1_cover.py: a column on fewer rows than a leaf's least count stands in no fit.

  v1_column_counts.py OUT.npz --blocks DIR [--named DIR]

A train row is one candidate at one example. A value that every example of a candidate holds counts once per example. The columns of `base`, `qv`,
`graph`, `relations` and `wide` are numbered as v1_cover.py numbers them. `--named` also counts the shapes of a folder of named lists.
"""
import argparse
import pickle
import struct
import sys
import time
from pathlib import Path

import numpy as np
import zstandard

sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate import read_lists  # noqa: E402

OTHER = 1 << 63
# Each source at the place v1_cover.py numbers it.
SOURCES = {'base': 0, 'qv': 1, 'graph': 2, 'relations': 3, 'wide': 4, 'relations_least': 6, 'relations_most': 7}


def frames(path):
    """Each frame of a store's source: each row's length, each entry's column, and each entry's value."""
    reader = zstandard.ZstdDecompressor().stream_reader(open(path, 'rb'), read_across_frames=True)

    def read(n):
        out = b''
        while len(out) < n:
            piece = reader.read(n - len(out))
            if not piece:
                break
            out += piece
        return out

    while True:
        head = read(12)
        if len(head) < 12:
            return
        rows, entries = struct.unpack('<IQ', head)
        lengths = np.frombuffer(read(4 * rows), dtype=np.uint32)
        columns = np.cumsum(np.frombuffer(read(4 * entries), dtype=np.int32).astype(np.int64))
        values = np.frombuffer(read(4 * entries), dtype=np.float32)
        yield lengths, columns, values


def counted(path, width, weight=None):
    """Each column's rows with an entry that is not 0, where a row counts `weight[row]` times."""
    out = np.zeros(width, dtype=np.int64)
    first = 0
    for lengths, columns, values in frames(path):
        active = values != 0
        if weight is None:
            out += np.bincount(columns[active], minlength=width)
        else:
            per_entry = np.repeat(weight[first:first + len(lengths)], lengths)
            out += np.bincount(columns[active], weights=per_entry[active], minlength=width).astype(np.int64)
        first += len(lengths)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('out')
    parser.add_argument('--blocks', required=True)
    parser.add_argument('--named')
    args = parser.parse_args()
    started = time.time()
    blocks = Path(args.blocks)
    meta = pickle.load((blocks / 'meta.pkl').open('rb'))
    example_of = pickle.load((blocks / 'train.example_of.pkl').open('rb'))
    examples = np.bincount(example_of)
    columns = np.asarray(meta['columns'], dtype=np.uint64)
    held = counted(blocks / 'blocks' / 'train.each.zst', len(columns))
    print(f'each {time.time() - started:.0f}s', flush=True)
    held += counted(blocks / 'blocks' / 'train.stable.zst', len(columns), examples)
    print(f'stable {time.time() - started:.0f}s', flush=True)
    ids, counts = [columns], [held]
    widths = dict(meta['widths'])
    for source, place in SOURCES.items():
        if not (blocks / 'blocks' / f'train.{source}.zst').exists():
            continue
        width = widths[source]
        ids.append(np.uint64(OTHER + (place << 32)) + np.arange(width, dtype=np.uint64))
        counts.append(counted(blocks / 'blocks' / f'train.{source}.zst', width, examples))
        print(f'{source} {time.time() - started:.0f}s', flush=True)
    if args.named:
        named = {}
        for at, path in enumerate(sorted(Path(args.named).glob('*.lists.zst'))):
            head, lists, others = read_lists(path, graded=True)
            train, test = head['train'], head.get('test', 0)
            places = [place for item in head['items'] for place in [item['gold']] + [mutant['table'] for mutant in item['mutants']]]
            uses = np.bincount(places, minlength=len(head['train_rows'])) if places else np.zeros(0, dtype=np.int64)
            for place, own in lists.items():
                if isinstance(place, int):
                    for key in own[0].tolist():
                        named[key] = named.get(key, 0) + int(uses[place]) * (train + test)
                    other = others[place]
                    if len(other[0]):
                        active = (other[4] != 0).sum(axis=1)
                        for key, rows in zip(other[0].tolist(), active.tolist()):
                            named[key] = named.get(key, 0) + int(uses[place]) * rows
                elif isinstance(place, str) and place.endswith('/query'):
                    for key in own[0].tolist():
                        named[key] = named.get(key, 0) + train + test
        ids.append(np.array(list(named), dtype=np.uint64))
        counts.append(np.array(list(named.values()), dtype=np.int64))
        print(f'named {len(named)} columns {time.time() - started:.0f}s', flush=True)
    np.savez_compressed(args.out, ids=np.concatenate(ids), counts=np.concatenate(counts))
    print('written', flush=True)


if __name__ == '__main__':
    main()
