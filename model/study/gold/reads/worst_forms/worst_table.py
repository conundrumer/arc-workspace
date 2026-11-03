"""The worst form of each stem of the 99, on the figures of record at b8e52e249: kind, shape group (form_anatomy_2.group), whether OUT reads it, bits. Writes table.md and rows.jsonl here.

  python3 worst_table.py
"""
import collections, gzip, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
D = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
sys.path.insert(0, D + 'gold/form-anatomy-over-28')
sys.path.insert(0, D + 'gold/form-anatomy-top-tenth')
from form_anatomy_2 import group
from form_anatomy import anatomy
HELD = set(open(D + 'features-worker/arm/held-tasks.txt').read().split())
EVAL = open(D + 'features-worker/arm/eval-tasks.txt').read().split()
VIEW = D + 'gold/gold-v3-combined-cut/view-final/'
merged = {r['task']: r for r in map(json.loads, open(D + 'gold/gold-v3-dag-bits/reread-kit/merged.jsonl'))}
rows = []
for t in EVAL:
    m = merged[t]
    with gzip.open(VIEW + t + '/pairs.jsonl.gz', 'rt') as f:
        ls = [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]
    out = next(x for x in ls if x.startswith('(OUT'))
    fs = [f for f in m['forms'] if isinstance(f['bits'], (int, float))]
    blank = [f for f in m['forms'] if f['status'] not in ('no draw',) and not isinstance(f['bits'], (int, float))]
    w = max(fs, key=lambda f: f['bits'])
    text = ls[w['line']]
    name = re.match(r'\(\w+ (&\S+)', text)[1]
    a = anatomy(text)
    g = group(dict(text=text, bits=w['bits'], kind=w['kind'], ors=a['ors'], alls=a['alls']))
    rows.append(dict(task=t, held=t in HELD, approximated=m['approximated'], line=w['line'], forms=len(ls) - 1, kind=w['kind'], group=g, last=bool(re.search(re.escape(name) + r'(?=[ .)])', out)), bits=w['bits'], status=w['status'], blank=len(blank), text=text))
rows.sort(key=lambda r: (not r['held'], -r['bits']))
with open(HERE + '/rows.jsonl', 'w') as f:
    for r in rows:
        f.write(json.dumps(r) + '\n')
L = ['| Stem | Held | Line of forms | Kind | Group | OUT reads it | Bits | Status | Forms with no figure |', '|---|---|---|---|---|---|---:|---|---:|']
for r in rows:
    L.append('| %s%s | %s | %d of %d | %s | %s | %s | %.2f | %s | %d |' % (r['task'], ' (approximated)' if r['approximated'] else '', 'yes' if r['held'] else '', r['line'], r['forms'], r['kind'], r['group'], 'yes' if r['last'] else '', r['bits'], r['status'], r['blank']))
for name, sel in (('held 37', lambda r: r['held']), ('the 99', lambda r: True)):
    s = [r for r in rows if sel(r)]
    L.append('\n%s: %s; OUT reads it on %d; kinds %s' % (name, dict(collections.Counter(r['group'] for r in s).most_common()), sum(r['last'] for r in s), dict(collections.Counter(r['kind'] for r in s))))
open(HERE + '/table.md', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L[-2:]))
