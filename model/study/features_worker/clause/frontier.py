"""The gold forms an arm did not cover, split by whether every form they read was covered, with each form's kind, OR and atom count. A frontier form is one the loop could have drawn in the scope of covered forms.

  frontier.py ARM_DIR POINTS.json
"""
import collections, glob, json, os, re, statistics as st, sys
arm, pts = sys.argv[1:3]
P = {p['task']: p['gold_sexp'].split('\n') for p in json.load(open(pts))}
HEAD = re.compile(r'\((\w+) (&\w+)')
REF = re.compile(r'&(\w+)')


def atoms(line):
    d, n = 0, 0
    for c in line:
        if c == '(':
            d += 1
            n += d == 2
        elif c == ')':
            d -= 1
    return n


tot = collections.Counter(); F = []
for f in sorted(glob.glob(arm + '/*.events.jsonl')):
    t = os.path.basename(f)[:8]
    if not os.path.exists(f.replace('.events.jsonl', '.done.json')):
        continue
    cov = {json.loads(l)['gold'] for l in open(f) if '"cover"' in l}
    lines = [l for l in P[t] if l.strip()]
    head = {}
    for i, l in enumerate(lines):
        m = HEAD.match(l)
        if m:
            head[m[2][1:]] = i
    for i, l in enumerate(lines):
        m = HEAD.match(l)
        kind = m[1] if m else '?'
        if i in cov:
            tot['covered'] += 1
            continue
        reads = {head[r] for r in REF.findall(l[m.end():]) if r in head} - {i} if m else set()
        missing = reads - cov
        if missing:
            tot['blocked'] += 1
        else:
            tot['frontier'] += 1
            F.append((kind, 'OR' if '(OR' in l else '', atoms(l), len(reads), t, i))
print(dict(tot), 'tasks', len(glob.glob(arm + '/*.done.json')))
c = collections.Counter((k, o) for k, o, *_ in F)
for k, v in c.most_common():
    a = [x[2] for x in F if (x[0], x[1]) == k]
    print(k, v, 'atoms median', st.median(a), 'reads median', st.median(x[3] for x in F if (x[0], x[1]) == k))
print('tasks with a frontier form', len({x[4] for x in F}))
json.dump(F, open(arm.rstrip('/') + '.frontier.json', 'w'))
