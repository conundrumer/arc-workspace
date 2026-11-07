#!/usr/bin/env python
"""read_skeleton.py OUT SPLIT [--samples K] [--seed S] [--root-only-first]: skeleton files whose samples have as targets only the queries a visit of the state should write.

A target of a non-empty state is a query that reads a query of the state, that is, one whose closure isn't empty. The queries that read no query belong to the empty state, whose sample always stays. K samples per task beside it, chosen as points_write.chosen chooses them. A sample left with no target goes. `points_write.py SPLIT --skeleton OUT --samples-per-task 0` writes the points."""
import argparse, sys, collections, hashlib, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study_paths import DATA_ROOT  # noqa: E402

SAMPLES = DATA_ROOT / 'samples'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('split'); ap.add_argument('--samples', type=int, default=8); ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tot = collections.Counter()
    for path in sorted((SAMPLES / a.split / 'skeleton').glob('*.jsonl')):
        records = [json.loads(x) for x in path.read_text().splitlines()]
        queries = {r['hash']: r for r in records if r['record'] == 'query'}
        samples = [r for r in records if r['record'] == 'sample']
        root = [s for s in samples if not s['state']['queries']]
        rest = [s for s in samples if s['state']['queries']]
        chosen = sorted(rest, key=lambda s: hashlib.sha256(f'{a.seed}:{s["id"]}'.encode()).hexdigest())[:a.samples]
        made = list(root)
        for s in chosen:
            aim = [t for t in s['target_queries'] if queries[t]['closure']]
            tot['targets'] += len(s['target_queries']); tot['targets kept'] += len(aim)
            if aim:
                made.append(dict(s, target_queries=aim))
        tot['tasks'] += 1; tot['samples'] += len(made); tot['root samples'] += len(root)
        with (out / path.name).open('w') as f:
            f.write(json.dumps(dict(records[0], samples=len(made))) + '\n')
            for r in queries.values():
                f.write(json.dumps(r) + '\n')
            for s in made:
                f.write(json.dumps(s) + '\n')
    print(dict(tot))


if __name__ == '__main__':
    main()
