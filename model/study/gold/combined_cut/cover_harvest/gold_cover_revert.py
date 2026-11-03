"""The harvest's stems that go back to their text before the harvest, by the read rule of the reread4 kit: on the reread4 rows against the stem's row in merged-before-reread4.jsonl, more forms with no figure, or a worst form higher by more than .01 bits. Writes revert.jsonl in this folder, and prints the counts by set, with the bar crossings of the stems that keep their new text.

  python3 gold_cover_revert.py
"""
import collections, glob, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
BITS = HERE + '/../../gold-v3-dag-bits/'
BARS = (13, 18, 21.5, 25, 28, 32)


def figures(r):
    """(forms with no figure, worst, sum) of a row's forms."""
    bits = [f.get('bits') for f in r['forms']]
    got = [b for b in bits if b is not None]
    return len(bits) - len(got), max(got, default=0.0), sum(got)


before = {r['task']: r for r in map(json.loads, open(BITS + 'reread-kit/merged-before-reread4.jsonl'))}
after = {}
for p in sorted(glob.glob(BITS + 'reread4-all/rows-*.jsonl')):
    for l in open(p):
        if l.endswith('\n'):
            r = json.loads(l)
            if r.get('task') and r.get('forms') is not None:
                after[r['task']] = r
sets = {}
for p in glob.glob(HERE + '/rows-*.jsonl'):
    for l in open(p):
        if l.endswith('\n'):
            r = json.loads(l)
            sets[r['stem']] = r.get('set')
stems = open(BITS + 'reread4-kit/stems.txt').read().split()
c = collections.defaultdict(collections.Counter)
with open(HERE + '/revert.jsonl', 'w') as out:
    for t in stems:
        s = sets.get(t, '?')
        if t not in after or t not in before:
            c[s]['no row'] += 1
            continue
        (n0, w0, s0), (n1, w1, s1) = figures(before[t]), figures(after[t])
        why = 'more forms with no figure' if n1 > n0 else 'worst form higher' if w1 > w0 + .01 else None
        if why:
            c[s]['revert'] += 1
            out.write(json.dumps(dict(stem=t, base_sha=after[t]['base_sha'], worst_before=w0, worst_after=w1, sum_before=round(s0, 2), sum_after=round(s1, 2), blank_before=n0, blank_after=n1, why=why)) + '\n')
            continue
        c[s]['kept'] += 1
        c[s]['sum cut'] += s0 - s1
        c[s]['worst cut'] += w0 - w1
        c[s]['worst lower'] += w1 < w0 - .01
        for x in BARS:
            c[s]['under %s' % x] += w1 <= x < w0
for s in sorted(c):
    print(s, {k: round(v, 1) for k, v in c[s].items()})
