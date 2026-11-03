"""Counts of the main DAG's tables by main depth and second-DAG depth, for one task. Depth is the longest chain of forms from the grid: a form that reads only the grid and main DETs has depth 1. In the main DAG a DET adds nothing. In the second DAG, whose forms are DETs by necessity, each form adds one. A table's second depth is the least depth among the second-DAG tables that meet it."""
import ast, collections, os, re, sys
T = sys.argv[1]; H = os.path.dirname(os.path.abspath(__file__))
def forms(s, head):
    out = []; i = s.find(head)
    while i >= 0:
        d = 0
        for j in range(i, len(s)):
            d += (s[j] == '(') - (s[j] == ')')
            if d == 0: break
        out.append(s[i:j + 1]); i = s.find(head, i + 1)
    return out
def depths(text):
    fs = {}
    for k in ('(RULE ', '(INIT '):
        for c in forms(text, k): fs.setdefault(c.split()[1], c)
    dets = {c.split()[1]: c for k in ('(DET ', '(DET_OR_RULE ') for c in forms(text, k)}
    def d(h, seen=()):
        if h in dets and h not in fs: return 0
        if h not in fs or h in seen: return 0
        refs = {r.split('.')[0] for r in re.findall(r'&[\w]+(?:\.\w+)?', fs[h])} - {h}
        return 1 + max([d(r, seen + (h,)) for r in refs], default=0)
    return {h: d(h) for h in list(fs) + list(dets)}
main = depths(open(f'{H}/w/{T}/second/{T}.arclog').read().split('(DET &b_out')[0] + '\n' + open(f'{H}/w/{T}/second/{T}.arclog').read()[open(f'{H}/w/{T}/second/{T}.arclog').read().rindex('(OUT'):])
st = open(f'{H}/{T}.second-dag.arclog').read()
sf = {c.split()[1]: c for k in ('(DET ', '(INIT ') for c in forms(st, k)}
def sd_(h, seen=()):
    if h not in sf or h in seen: return 0
    refs = {r.split('.')[0] for r in re.findall(r'&[bg]_\w+(?:\.\w+)?', sf[h])} - {h}
    return 1 + max([sd_(r, seen + (h,)) for r in refs], default=0)
second = {h: sd_(h) for h in sf}
cells = collections.Counter(); seconds = set(); mains = set(); miss = []
for l in open(f'{H}/w/{T}.second.txt'):
    m = re.match(r'(gold|node) (\S+) (.*)', l.strip())
    if not m: continue
    side, x, rest = m.groups(); md = main.get(x.split('.')[0])
    if md is None: miss.append(x); continue
    mains.add(md)
    if rest.startswith('['):
        sd = min(second[y.split()[0].split('.')[0]] for y in ast.literal_eval(rest)); seconds.add(sd)
    else: sd = 'none'
    cells[md, sd, side] += 1
cols = sorted(seconds) + ['none']
print('missing', miss)
print('main \\ second | ' + ' | '.join(map(str, cols)))
for md in sorted(mains):
    print(f'{md} | ' + ' | '.join(f"{cells[md, c, 'gold']} / {cells[md, c, 'node']}" for c in cols))
