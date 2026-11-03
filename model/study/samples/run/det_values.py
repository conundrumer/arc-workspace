"""For each row store file: the DET values that some entry's assignment holds and that have no entry of the DET itself at that value."""
import gzip
import json
import sys
from pathlib import Path

tot_vals = tot_missing = 0
for p in sorted(Path(sys.argv[1]).glob('*.jsonl.gz')):
    kinds, own, used = {}, set(), set()
    with gzip.open(p, 'rt') as f:
        for line in f:
            r = json.loads(line)
            if r['t'] == 'function':
                kinds[r['id']] = r['kind']
            elif r['t'] == 'entry':
                for d, v in r['assignment']:
                    used.add((d, v))
                    if d == r['function']:
                        own.add((d, v))
    dets = {k for k, v in kinds.items() if v == 'DET'}
    vals = {x for x in used if x[0] in dets}
    missing = vals - own
    tot_vals += len(vals)
    tot_missing += len(missing)
    if missing:
        print(p.name[:8], len(vals), len(missing))
print('DET values', tot_vals, 'without an own entry', tot_missing)
