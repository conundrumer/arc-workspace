#!/usr/bin/env python
"""The catalog's native pass beside the first version's value, on a sample of Candidate tables.

  uv run python model/feature_eval/catalog_check.py ENCODER [--tasks N] [--per-schema M] [--kinds REGEX]

It prints, per kind in rank order, how many values agree, differ, or stand on one side alone.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path('/Users/davidlu/code/arc-workspace')
RESULTS = ROOT / 'work/feature-spec/results'
C = ROOT / 'model/contracts'
TOKEN = re.compile(r'(?:key\.)?⟦CT#(\d+)⟧')
PLACE = ('Position', 'Box')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('encoder')
    parser.add_argument('--tasks', type=int, default=60)
    parser.add_argument('--per-schema', type=int, default=2)
    parser.add_argument('--kinds', default=None)
    parser.add_argument('--show', type=int, default=2)
    a = parser.parse_args()
    os.environ['CONTRACTS_OUT'] = str(C / 'dev/out-expand')
    sys.path[:0] = [str(C / 'dev/out-expand'), str(C / 'dev'), str(C / 'features')]
    import features as F
    import analyze as A

    ranks = {}
    for line in open(RESULTS / 'candidate-rank.tsv'):
        kind = TOKEN.sub('C', line.rstrip('\n').split('\t')[3])
        ranks.setdefault(kind, len(ranks) + 1)
    tasks = [t for t in (ROOT / 'work/feature-spec/eval-tasks.txt').read_text().split() if (RESULTS / f'candidate-tables/{t}.json').exists()][:a.tasks]
    requests, first, seen = [], {}, Counter()
    for task in tasks:
        data = json.loads((RESULTS / f'candidate-tables/{task}.json').read_text())
        pairs = json.loads((ROOT / f'data/tasks/{task}.json').read_text())['train']
        for item in data['items']:
            for table in [item['gold']] + [m['table'] for m in item['mutants'][:1]]:
                types = table['types']
                schema = tuple(sorted(types))
                if any(t.startswith('Pose') for t in types) or any(len(rows or []) > 2000 for rows in table['rows'].values()):
                    continue
                if seen[schema] >= a.per_schema or not all(table['rows'].get(f'train/{i}') for i in range(len(pairs))):
                    continue
                seen[schema] += 1
                at = len(requests)
                requests.append(dict(task=task, types=types, columns=table['columns'], rows=table['rows']))
                for i, pair in enumerate(pairs):
                    ex = f'train/{i}'
                    rows = table['rows'].get(ex)
                    gi, go = pair['input'], pair['output']
                    sizes = {'input': (len(gi), len(gi[0])), 'output': (len(go), len(go[0]))}
                    tab = dict(columns=[(c, t, 'input' if t in PLACE else None) for c, t in zip(table['columns'], types)], rows={ex: rows})
                    for key, value in F.table_features('T', F.tokened('T', tab), ex, sizes, {}, (gi, go)).items():
                        if key.endswith(' describe') or not A.is_output('T|' + key):
                            continue
                        kind = TOKEN.sub('C', key)
                        holes = tuple(int(m.group(1)) for m in TOKEN.finditer(key))
                        first[(at, i, kind, holes)] = value
    print(f'{len(requests)} tables, {len(first)} first-version values', flush=True)
    with tempfile.TemporaryDirectory() as folder:
        path, out = Path(folder) / 'requests.jsonl', Path(folder) / 'values.jsonl'
        path.write_text('\n'.join(json.dumps(r) for r in requests) + '\n')
        run = subprocess.run([a.encoder, 'catalog-values', str(path), '--out', str(out)], cwd=ROOT, capture_output=True, text=True)
        print(run.stderr[-600:].strip(), flush=True)
        native = {}
        for line in out.read_text().splitlines():
            found = json.loads(line)
            native[(found['line'], found['pair'], found['kind'], tuple(found['holes']))] = found['value']
    written = {key[2] for key in native}
    tally = defaultdict(Counter)
    shown = defaultdict(list)
    for key, value in first.items():
        kind = key[2]
        if kind not in written:
            tally[kind]['unwritten'] += 1
            continue
        if key in native:
            if native[key] == value:
                tally[kind]['agree'] += 1
            else:
                tally[kind]['differ'] += 1
                shown[kind].append((requests[key[0]]['task'], key[1], key[3], value, native[key]))
        else:
            tally[kind]['first only'] += 1
            shown[kind].append((requests[key[0]]['task'], key[1], key[3], value, 'none'))
    for key, value in native.items():
        if key not in first:
            tally[key[2]]['native only'] += 1
            shown[key[2]].append((requests[key[0]]['task'], key[1], key[3], 'none', value))
    print('total', sum((t for t in tally.values()), Counter()), flush=True)
    for kind in sorted(tally, key=lambda k: ranks.get(k, 10 ** 6)):
        if a.kinds and not re.search(a.kinds, kind):
            continue
        t = tally[kind]
        if t['differ'] or t['first only'] or t['native only'] or t['unwritten']:
            print(f"{ranks.get(kind, ''):>4} agree {t['agree']:>5} differ {t['differ']:>4} first {t['first only']:>4} native {t['native only']:>4} unwritten {t['unwritten']:>4} {kind[:80]}", flush=True)
            for item in shown[kind][:a.show]:
                print(f'      {item}', flush=True)


if __name__ == '__main__':
    main()
