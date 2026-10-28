"""Compare optimized runtime observations with the existing stage-3 evidence.

Expands task-local compact gold references. Ignores only timing/cache telemetry,
then compares reports, mutation identities and native buffer inspection summaries.
Reads complete JSONL lines, so the baseline may still be growing.
"""
import argparse
from collections import Counter
import json
from pathlib import Path


def pairs(path):
    observations = {}
    with path.open() as src:
        for line in src:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                if not line.endswith('\n'):
                    break
                raise
            if row.get('type') != 'pair':
                continue
            report = row['evaluation']
            ref = (row['task'], report.get('gold_observation_ref'))
            if 'gold_assignments' in report:
                observations[ref] = {name: report[name] for name in ('gold_assignments', 'kept_assignments')}
                observations[ref]['gold_train'] = [out['gold_train'] for out in report['outputs']]
            if report.get('gold_observation_cached') and 'gold_assignments' not in report:
                saved = observations[ref]
                for name in ('gold_assignments', 'kept_assignments'):
                    report[name] = saved[name]
                for out, train in zip(report['outputs'], saved['gold_train'], strict=True):
                    out['gold_train'] = train
            for name in ('timings', 'cache', 'gold_observation_cached', 'gold_observation_ref'):
                report.pop(name, None)
            key = (row['task'], row['case'], tuple(row['body']), tuple(row['clause']), row['kind'], json.dumps(row['identity'], sort_keys=True))
            value = {name: row.get(name) for name in ('status', 'reason', 'evaluation', 'native')}
            yield key, value


def differences(a, b, path=''):
    if type(a) is not type(b):
        yield path, a, b
    elif isinstance(a, dict):
        for key in sorted(a.keys() | b.keys()):
            if key not in a or key not in b:
                yield path + '.' + key, a.get(key), b.get(key)
            else:
                yield from differences(a[key], b[key], path + '.' + key)
    elif isinstance(a, list):
        if len(a) != len(b):
            yield path + '.length', len(a), len(b)
        for i, (x, y) in enumerate(zip(a, b)):
            yield from differences(x, y, f'{path}[{i}]')
    elif a != b:
        yield path, a, b


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    candidate = dict(pairs(args.candidate))
    counts = Counter(candidate=len(candidate))
    for key, expected in pairs(args.reference):
        if key not in candidate:
            continue
        actual = candidate.pop(key)
        counts['matched'] += 1
        diff = list(differences(expected, actual))
        if diff:
            counts['different'] += 1
            if counts['different'] <= 10:
                print(json.dumps(dict(task=key[0], case=key[1], body=key[2], differences=diff[:12])), flush=True)
    counts['absent_from_reference'] = len(candidate)
    print(json.dumps(counts), flush=True)
    if counts['different'] or candidate or not counts['matched']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
