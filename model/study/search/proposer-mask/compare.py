"""Compares two runs of run_direct.sh on one task: an unmasked run and a masked run of one length and one seed.

  python3 compare.py TASK OFF_DIR ON_DIR

It prints, for each run, the counts of DET admission refusals and the mask counts from the 'all counts' line of worker.log (the run
needs ALL_COUNTS=1), the number of draws, and whether the scope picks (the .picks lines without proc and time) are the same for as
many picks as both runs have. Clauses drawn differ between the runs, and so can the picks after the first pick that reads them.
"""
import json
import sys

task, off, on = sys.argv[1:4]
KEYS = ('DetAdmission', 'mask:', 'admission:', 'search.runs', 'search.clauses', 'search.dead', 'search:visits', 'search:new scope', 'draws')


def counts(d):
    lines = [x for x in open(d + '/worker.log') if x.startswith('all counts')]
    return json.loads(lines[-1][len('all counts'):]) if lines else {}


def picks(d):
    return [(x['draw'], x['n'], x['picks']) for x in map(json.loads, open('%s/%s.out.jsonl.picks' % (d, task)))]


def end(d):
    return next((x.strip() for x in open(d + '/worker.log') if x.startswith('end:')), 'no end line')


for name, d in (('off', off), ('on', on)):
    c = counts(d)
    print('==', name, d)
    print(end(d))
    for k, v in c.items():
        if any(s in k for s in KEYS) and k.split(':')[0] != 'search.seconds':
            print('  ', k, v)
a, b = picks(off), picks(on)
n = min(len(a), len(b))
same = [x == y for x, y in zip(a, b)]
print('picks: off %d, on %d, same on the first %d: %s' % (len(a), len(b), n, all(same)))
for i, (x, y) in enumerate(zip(a, b)):
    print('  pick %d: %s' % (i, 'same' if x == y else 'differs: off %s on %s' % (x, y)))
