"""Policy2 against the bundled policy, on the tasks both arms finished: gold covered at equal samples per task, by depth, with non-DET apart from DET, and whole-run samples and scope seconds. Rerun as tasks finish."""
import collections, glob, json, os, re, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__))
P = os.environ.get('POINTS', '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/runs/pool1/points.json')
ARMS = tuple(sys.argv[1:3]) or ('b-full', 'b-p2')
N = re.compile(r'&[A-Za-z_]\w*')
B = [(1, 1, '1'), (2, 3, '2-3'), (4, 6, '4-6'), (7, 99, '7+')]
bucket = lambda x: next(n for a, b, n in B if a <= x <= b)
gold = {}
for sp in json.load(open(P)):
    d = {}; dep = []; k = []
    for l in sp['gold_sexp'].strip().split('\n'):
        if l.startswith('(OUT'):
            continue
        h = l.split()[1]; d[h] = 1 + max([d[m] for m in N.findall(l) if m in d and m != h], default=0)
        dep.append(d[h]); k.append(l[1:l.index(' ')])
    gold[sp['task']] = (dep, k)


def load(a, t):
    f = f'{HERE}/{a}/{t}'
    return json.load(open(f + '.done.json')), [json.loads(l) for l in open(f + '.events.jsonl')]


tasks = sorted(set.intersection(*[{os.path.basename(f)[:-10] for f in glob.glob(f'{HERE}/{a}/*.done.json')} for a in ARMS]))
whole = {a: collections.Counter() for a in ARMS}; got = {a: collections.Counter() for a in ARMS}; per = []; draws = collections.Counter(); scope = collections.Counter()
for t in tasks:
    run = {a: load(a, t) for a in ARMS}
    D = min(r[0]['draws'] for r in run.values()); dep, k = gold[t]; c = {}
    for a, (done, ev) in run.items():
        s = {e['gold'] for e in ev if e['event'] == 'cover' and e['draw'] <= D}
        for i in s:
            got[a][bucket(dep[i]), k[i] == 'DET'] += 1
        c[a] = sum(k[i] != 'DET' for i in s)
        for i in {e['gold'] for e in ev if e['event'] == 'cover'}:
            whole[a][bucket(dep[i]), k[i] == 'DET'] += 1
        draws[a] += done['draws']; scope[a] += done['counts'].get('scope_seconds', 0)
    per.append(c[ARMS[1]] - c[ARMS[0]])
print('tasks', len(tasks), ARMS[1], 'minus', ARMS[0], 'non-DET per task: mean', round(statistics.mean(per), 2) if per else '-', 'better', sum(x > 0 for x in per), 'worse', sum(x < 0 for x in per), 'equal', sum(x == 0 for x in per))
for a in ARMS:
    print(a, 'non-DET', ' '.join(f'{n}:{got[a][n, False]}' for *_, n in B), 'DET', sum(v for (n, d), v in got[a].items() if d), '| samples', draws[a], 'scope s per task', round(scope[a] / max(len(tasks), 1), 1), '| whole run non-DET', ' '.join(f'{n}:{whole[a][n, False]}' for *_, n in B), 'DET', sum(v for (n, d), v in whole[a].items() if d))
