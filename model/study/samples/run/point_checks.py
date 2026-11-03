"""Totals of the check counts that each points file's summary record carries (points_write.py), over the files of the given folders, with the tasks
where a count is not 0. A file with no check counts in its summary is counted as unchecked. Also the totals of the summary's `failures`: the samples
and targets that gave no points, by reason, with the tasks of each reason.

  python3 point_checks.py FOLDER...      such as samples/train/points/ordered samples/dev/points/ordered
"""
import gzip
import json
import sys
from pathlib import Path

for folder in sys.argv[1:]:
    tot: dict[str, int] = {}
    nonzero: dict[str, dict[str, int]] = {}
    unchecked = []
    dropped: dict[tuple[str, str], dict[str, int]] = {}
    files = sorted(Path(folder).glob('*.jsonl.gz'))
    for p in files:
        task = p.name.removesuffix('.jsonl.gz')
        last = None
        with gzip.open(p, 'rt') as f:
            for line in f:
                if line.startswith('{"record": "summary"'):
                    last = json.loads(line)
        for kind, by_why in ((last or {}).get('failures') or {}).items():
            for why, n in by_why.items():
                dropped.setdefault((kind, why), {})[task] = n
        checks = (last or {}).get('checks')
        if checks is None:
            unchecked.append(task)
            continue
        for k, v in checks.items():
            tot[k] = tot.get(k, 0) + v
        if any(checks.values()):
            nonzero[task] = {k: v for k, v in checks.items() if v}
    print(f'{folder}: {len(files)} files, {len(unchecked)} unchecked, totals {tot}')
    for task, c in sorted(nonzero.items()):
        print(f'  {task} {c}')
    for (kind, why), by_task in sorted(dropped.items(), key=lambda x: -sum(x[1].values())):
        print(f'  dropped {kind}: {sum(by_task.values())} in {len(by_task)} tasks ({" ".join(sorted(by_task))}): {why[:160]}')
