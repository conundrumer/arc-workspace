"""Totals of the check counts that each points file's summary record carries (points_write.py), over the files of the given folders, with the tasks
where a count is not 0. A file with no check counts in its summary is counted as unchecked.

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
    files = sorted(Path(folder).glob('*.jsonl.gz'))
    for p in files:
        task = p.name.removesuffix('.jsonl.gz')
        last = None
        with gzip.open(p, 'rt') as f:
            for line in f:
                if line.startswith('{"record": "summary"'):
                    last = json.loads(line)
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
