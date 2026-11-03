"""Share of gold's forms that restate a single table, and their bits. Bits come from held tasks and are read as a stated count."""
import collections, csv, json, math, statistics, sys
import forms
READ = ('input', 'ex_input', 'ex_output')
BAD = ('ALL', 'ONE', 'IF', 'SET')
PLUMB = ('one read', 'one read, fixed atoms', 'one table read twice or more')

def has(x, heads):
    return isinstance(x, list) and any((i in heads) or has(i, heads) for i in x)

def kind(p):
    k = p[0]
    if k not in ('RULE', 'DET'):
        return k
    body = p[2:]
    if not any(isinstance(a, list) for a in body):
        return k + ' named'
    if has(body, BAD):
        return 'aggregate'
    al = list(forms.atoms(body))
    reads = [a for a in al if a[0].startswith('&') or a[0] in READ]
    fixed = [a for a in al if a not in reads]
    names = {a[0] for a in reads}
    if not reads:
        return 'fixed atoms only'
    if any(a[1] for a in reads):
        return 'negated read'
    if any(a[2] for a in al):
        return 'union'
    if len(names) > 1:
        return 'join of two or more tables'
    if len(reads) > 1:
        return 'one table read twice or more'
    return 'one read, fixed atoms' if fixed else 'one read'

held = set(open('work/lm/data-study/sampler/sampler-worker/held/tasks.txt').read().split())
c, per = collections.Counter(), []
for t, ls in forms.views():
    if t in held:
        continue
    k = [kind(forms.parse(l)) for l in ls]
    c.update(k)
    body = [x for x in k if x != 'OUT']
    per.append(sum(x in PLUMB for x in body) / max(len(body), 1))
tot = sum(v for k, v in c.items() if k != 'OUT')
print('view-final, non-held: forms', tot, 'tasks', len(per))
for k, v in c.most_common():
    print('  %-34s %6d %.3f' % (k, v, v / tot))
print('  restating forms share %.3f; median per task %.3f' % (sum(c[k] for k in PLUMB) / tot, statistics.median(per)))

P = json.load(open('work/lm/data-study/sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/points-base.json'))
text = {r['task']: [x for x in r['gold_sexp'].splitlines() if x.strip()] for r in P}
bits = {}
for r in csv.DictReader(open('work/lm/data-study/features-worker/results/features-dag-order-census-heldout37/form-bits-join.tsv'), delimiter='\t'):
    if r['written']:
        bits.setdefault((r['task'], int(r['line'])), float(r['written']))
S = .3
rows = collections.defaultdict(list)
task = collections.defaultdict(list)
for (t, i), b in bits.items():
    k = kind(forms.parse(text[t][i]))
    rows[k].append(b)
    task[t].append((b, k, text[t][i]))
n = sum(map(len, rows.values()))
tb, tc = sum(sum(v) for v in rows.values()), sum(2 ** (S * b) for v in rows.values() for b in v)
print('held, bits by written form: forms', n, 'tasks', len(task))
print('  %-34s %5s %6s %6s %6s %7s %8s' % ('class', 'n', 'share', 'median', 'max', 'bits %', 'cost %'))
for k, v in sorted(rows.items(), key=lambda x: -len(x[1])):
    print('  %-34s %5d %6.3f %6.1f %6.1f %7.3f %8.3f' % (k, len(v), len(v) / n, statistics.median(v), max(v), sum(v) / tb, sum(2 ** (S * b) for b in v) / tc))
worst = [max(v) for v in task.values()]
print('worst form per task: median %.1f' % statistics.median(b for b, _, _ in worst), collections.Counter(k for _, k, _ in worst).most_common())
print('tasks with a restating form as worst:', sum(k in PLUMB for _, k, _ in worst), 'of', len(worst))
A = 10.6
def full(forms_bits, n):
    p = 1.0
    for b in forms_bits:
        p *= 1 - math.exp(-n * 2 ** -min(A + S * b, 1000))
    return p
print('expected full covers of %d tasks, a %.1f s %.1f; the free column takes restating forms as free, an upper limit' % (len(task), A, S))
for n in (5e3, 5e4, 5e5, 5e6):
    print('  n %8.0f all %.4f free %.4f' % (n, sum(full([b for b, k, _ in v], n) for v in task.values()), sum(full([b for b, k, _ in v if k not in PLUMB], n) for v in task.values())))
reads = collections.Counter()
for t, ls in text.items():
    if t not in task:
        continue
    head, cls = {}, []
    for l in ls:
        p = forms.parse(l)
        cls.append(kind(p))
        if len(p) > 1 and isinstance(p[1], str):
            head[p[1]] = cls[-1]
    hist = dict()
    w = max(task[t])[2]
    for i, l in enumerate(ls):
        if (t, i) not in bits:
            continue
        got = set(__import__('re').findall(r'&[a-z]+\d+', l.split(None, 2)[2] if len(l.split(None, 2)) > 2 else ''))
        rd = any(head.get(x) in PLUMB for x in got)
        reads['forms'] += 1
        reads['forms that read a restating form'] += rd
        if l == w:
            reads['worst forms'] += 1
            reads['worst forms that read a restating form'] += rd
print(dict(reads))
