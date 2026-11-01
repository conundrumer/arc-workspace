#!/usr/bin/env python
"""The counts `key_types` of the priors (live.py, ORDER_FREE=key): how often a label of a type is a key, among the labels offered at the key picks of gold.

  <runtime python> key_type_counts.py STEMS [STEMS ...] PRIORS_IN PRIORS_OUT [--exclude FILE]

Each STEMS is the `stems` folder of a rows folder of live_rows.py. Its `keypick` rows give, at each key pick of gold's walk, the type sets of the labels offered and of the labels taken
(or_q.Guide.keypick). A label counts under each of its types, whose set is a fact of the atoms as a set, so a row has the same sets in every valid order. PRIORS_OUT is PRIORS_IN with
`key_types`, {type: (taken, offered)}. The rows leave out the leave-out tasks; --exclude takes more tasks out, one a line, for a fit that holds a fold back.
"""
import argparse
import collections
import glob
import gzip
import json
import os
import pickle


def count(folders, exclude=()):
    """{type: [taken, offered]} over the keypick rows of the stems folders, less the stems of the excluded tasks."""
    out = collections.defaultdict(lambda: [0, 0])
    for folder in folders:
        for path in sorted(glob.glob(os.path.join(folder, '*.jsonl.gz'))):
            if os.path.basename(path)[:-len('.jsonl.gz')] in exclude:
                continue
            with gzip.open(path, 'rt') as f:
                f.readline()
                for line in f:
                    k, row = json.loads(line)
                    if k == 'keypick':
                        for i, key in enumerate(('taken', 'offered')):
                            for types in row[key]:
                                for t in types:
                                    out[t][i] += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+', help='stems folders, then the priors file to read and the priors file to write')
    ap.add_argument('--exclude', help='a file of tasks to leave out, one a line')
    a = ap.parse_args()
    *folders, src, dest = a.paths
    counts = count(folders, set(open(a.exclude).read().split()) if a.exclude else ())
    with open(src, 'rb') as f:
        pri = pickle.load(f)
    pri['key_types'] = {t: tuple(c) for t, c in sorted(counts.items())}
    with open(dest + '.tmp', 'wb') as f:
        pickle.dump(pri, f, protocol=5)
    os.replace(dest + '.tmp', dest)
    for t, (taken, offered) in pri['key_types'].items():
        print('%-14s taken %5d of %5d offered' % (t, taken, offered))
    print(dest)


if __name__ == '__main__':
    main()
