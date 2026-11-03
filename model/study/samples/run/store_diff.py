"""Compares two row store folders task by task: the set of (function, o, name, assignment, TableHash) of their entries, and of their function ids. Prints the tasks that differ and the counts."""
import gzip, json, sys
from pathlib import Path


def content(p: Path) -> tuple[set, set]:
    ents, funcs = set(), set()
    with gzip.open(p, 'rt') as f:
        for line in f:
            r = json.loads(line)
            if r['t'] == 'footer':
                break
            if r['t'] == 'entry':
                ents.add((r['function'], r['o'], r['name'], json.dumps(r['assignment']), r['hash']))
            elif r['t'] == 'function':
                funcs.add(r['id'])
    return ents, funcs


a, b = Path(sys.argv[1]), Path(sys.argv[2])
same = differ = missing = 0
for p in sorted(a.glob('*.jsonl.gz')):
    q = b / p.name
    if not q.exists():
        missing += 1
        continue
    (ea, fa), (eb, fb) = content(p), content(q)
    if ea == eb and fa == fb:
        same += 1
    else:
        differ += 1
        print(p.name[:8], 'entries only in first', len(ea - eb), 'only in second', len(eb - ea), 'functions only in first', len(fa - fb), 'only in second', len(fb - fa))
print('same', same, 'differ', differ, 'missing in second', missing)
