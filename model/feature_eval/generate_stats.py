#!/usr/bin/env python
"""The generated shapes' Candidate line: gain over the null on pairs where the mutant has rows.

  python model/feature_eval/generate_stats.py FOLDER [FOLDER ...]

It prints each folder's line per size, its shape counts and its walk times. With --top N and
--out FILE it also writes the top N shapes of the folder by summed net votes, one per line.
"""
import argparse
import glob
import json
import random
import statistics as st
from collections import Counter
from common import glob_data, read_json


def boot(values):
    q = random.Random(1)
    means = sorted(st.mean(q.choices(values, k=len(values))) for _ in range(1000))
    return round(means[5], 3), round(means[994], 3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folders', nargs='+')
    parser.add_argument('--top', type=int, default=0)
    parser.add_argument('--out', default=None)
    a = parser.parse_args()
    votes = Counter()
    for folder in a.folders:
        records = [read_json(f) for f in sorted(glob_data(folder + '/*.json'))]
        if not records:
            continue
        sizes = len(records[0]['sizes'])
        print(f'{folder}: {len(records)} tasks', flush=True)
        for d in range(sizes):
            rows = [r['sizes'][d] for r in records]
            gain = [x['auc_rows'] - x['null_rows'] for x in rows if x.get('auc_rows') is not None and x.get('null_rows') is not None]
            every = [x['auc'] - x['null'] for x in rows if x.get('auc') is not None and x.get('null') is not None]
            print(f"  size {d + 1}: rows gain {st.mean(gain):+.3f} {boot(gain)} n{len(gain)}; every pair {st.mean(every):+.3f}; contingent classes {st.mean(x['contingent'] or 0 for x in rows):.0f}", flush=True)
        schemas = {}
        for r in records:
            for t in r['terms']:
                schemas[t['schema']] = (t['by_size'], t['roots'])
        terms = [v[0][-1] for v in schemas.values()]
        roots = [v[1] for v in schemas.values()]
        print(f"  schemas {len(schemas)}; terms per schema median {st.median(terms):.0f} max {max(terms)}; roots median {st.median(roots):.0f} max {max(roots)}", flush=True)
        walks = sum(r['walks'] for r in records)
        print(f"  {walks} walks, {sum(r['walk_seconds'] for r in records) / max(walks, 1) * 1e3:.1f} ms per walk; {sum(r['seconds'] for r in records):.0f} s in all", flush=True)
        for r in records:
            for name, gold, mutant, compared, null_gold, null_mutant, null_compared in r['shapes']:
                votes[name] += (gold - mutant) - (null_gold - null_mutant) / 3
    if a.top and a.out:
        chosen = [name for name, _ in votes.most_common(a.top)]
        open(a.out, 'w').write('\n'.join(chosen) + '\n')
        print('top', [c[:90] for c in chosen[:10]], flush=True)


if __name__ == '__main__':
    main()
