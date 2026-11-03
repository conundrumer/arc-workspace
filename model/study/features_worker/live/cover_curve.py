"""Gold covered over draws, from the replay's labels: for each task, its best case. Gold forms split by depth, with DET apart. A task whose gold has no replay stays out."""
import collections, glob, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
STORE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/feat-exp/fstore-gen3/points-t'
LOG = sys.argv[1] if len(sys.argv) > 1 else HERE + '/labels'
N = re.compile(r'&[A-Za-z_]\w*')
B = [(1, 1, '1'), (2, 3, '2-3'), (4, 6, '4-6'), (7, 99, '7+')]
bucket = lambda x: next(n for a, b, n in B if a <= x <= b)
index = collections.defaultdict(list)
for e in os.scandir(STORE):
    index[e.name[:8]].append(e.path)


def gold(task, case):
    for d in index[task]:
        if json.load(open(d + '/point.json'))['case'] == case:
            lines = [l for l in open(d + '/gold.arclog').read().strip().split('\n') if not l.startswith('(OUT')]
            dep = {}; out = []
            for l in lines:
                h = l.split()[1]; dep[h] = 1 + max([dep[m] for m in N.findall(l) if m in dep and m != h], default=0)
                out.append((dep[h], l[1:l.index(' ')]))
            return out


CUT = (100, 250, 500, 1000, 2000, 5000, 10 ** 9)
tot = collections.Counter(); got = collections.defaultdict(collections.Counter); tasks = 0; none = 0; solved = []
for f in sorted(glob.glob(LOG + '/*.json')):
    v = json.load(open(f))
    if not v['best'] or sum(v['sizes'].values()) == 0:
        none += 1
        continue
    # the best case by covered share
    c = v['best']; forms = gold(v['task'], c)
    if not forms or not v['covered'].get(c) and not v['hits'] and v['nodes'] == 0:
        none += 1
        continue
    tasks += 1
    for d, k in forms:
        tot[bucket(d), k == 'DET'] += 1
    first = {}
    for h in v['hits']:
        for cc, i in h['hit']:
            if cc == c and i not in first and i < len(forms):
                first[i] = h['draw'] or 0
    solved.append((len(first) / len(forms), v['task'], len(forms)))
    for i, dr in first.items():
        d, k = forms[i]
        for cut in CUT:
            if dr <= cut:
                got[cut][bucket(d), k == 'DET'] += 1
nd = lambda c: ' '.join(f'{n}:{c[n, False]}' for *_, n in B)
print('tasks', tasks, 'left out', none, '| gold non-DET', nd(tot), 'DET', sum(v for (n, d), v in tot.items() if d))
for cut in CUT:
    c = got[cut]
    print(f'by draw {cut if cut < 10 ** 9 else "all":>5}: non-DET {nd(c)} = {sum(v for (n, d), v in c.items() if not d)} | DET {sum(v for (n, d), v in c.items() if d)}')
solved.sort(reverse=True)
print('best tasks by share covered', [(round(s, 2), t, n) for s, t, n in solved[:6]], '| zero covered', sum(s == 0 for s, _, _ in solved))
