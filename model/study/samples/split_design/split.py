"""Strata, salt choice, split sizes, and where the current held sets fall. Reads facts.jsonl here; writes split.tsv and split.out here.

Strata (stratum name = source block / depth bin / size bin):
- source block: E where data/tasks/<id>.json `source` has arc-agi-2/evaluation, else T.
- depth bin: graph-tasks-SET.jsonl `goal_depth`: d1-4, d5-7, d8+; `none` where the task has no graph row, an `error` row, or goal_depth inf.
  In block E the depth bins d1-4, d5-7, d8+ are one bin `graph`, since E has 35 graph tasks.
- size bin: `same` where every train pair's output has its input's height and width, else `diff`.
Assignment: u = first 16 hex digits of sha256("<salt>:<task id>") / 16**16; train where u < 0.70, dev where u < 0.85, else held-out.
The salt is the one of 0..SALTS-1 whose split has the least chi-square of dev and held-out counts against their expected counts over the strata.
"""
import collections, hashlib, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SALTS = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
CUT = (0.70, 0.85)
rows = [json.loads(l) for l in open(HERE + '/facts.jsonl')]


def block(r):
    return 'E' if 'arc-agi-2/evaluation' in r['source'] else 'T'


def depth_bin(r):
    d = r.get('goal_depth')
    if d is None or d == float('inf'):
        return 'none'
    if block(r) == 'E':
        return 'graph'
    return 'd1-4' if d <= 4 else 'd5-7' if d <= 7 else 'd8+'


def stratum(r):
    return '%s/%s/%s' % (block(r), depth_bin(r), 'same' if r['output_size_equals_input'] else 'diff')


def u(salt, t):
    return int(hashlib.sha256(('%d:%s' % (salt, t)).encode()).hexdigest()[:16], 16) / 16 ** 16


def split_of(x):
    return 'train' if x < CUT[0] else 'dev' if x < CUT[1] else 'held-out'


for r in rows:
    r['stratum'] = stratum(r)
cells = collections.Counter(r['stratum'] for r in rows)
order = sorted(cells)
share = {'train': CUT[0], 'dev': CUT[1] - CUT[0], 'held-out': 1 - CUT[1]}


def chi(salt):
    got = collections.Counter((r['stratum'], split_of(u(salt, r['task']))) for r in rows)
    c = 0.0
    for s in order:
        for sp in ('dev', 'held-out'):
            e = cells[s] * share[sp]
            c += (got[(s, sp)] - e) ** 2 / e
    return c


scores = sorted((chi(s), s) for s in range(SALTS))
best_chi, salt = scores[0]
med = scores[len(scores) // 2][0]
for r in rows:
    r['split'] = split_of(u(salt, r['task']))
out = open(HERE + '/split.out', 'w')


def p(*a):
    print(*a, file=out)


p('salt %d of %d; chi-square %.2f (median over salts %.2f; cells x 2 = %d terms)' % (salt, SALTS, best_chi, med, 2 * len(order)))
tot = collections.Counter(r['split'] for r in rows)
p('overall: pool %d, train %d, dev %d, held-out %d' % (len(rows), tot['train'], tot['dev'], tot['held-out']))
p('\n| Stratum | Pool | Train | Dev | Held-out | Held-out expected |')
p('|---|---|---|---|---|---|')
for s in order:
    c = collections.Counter(r['split'] for r in rows if r['stratum'] == s)
    p('| %s | %d | %d | %d | %d | %.1f |' % (s, cells[s], c['train'], c['dev'], c['held-out'], cells[s] * share['held-out']))
# current sets per stratum
SETS = [('r22', 'the 22'), ('h37', 'the 37'), ('h99', 'the 99')]
p('\n| Stratum | Pool | The 22 | The 37 | The 99 | 22 exp | 37 exp | 99 exp |')
p('|---|---|---|---|---|---|---|---|')
n = len(rows)
size = {k: sum(r[k] for r in rows) for k, _ in SETS}
for s in order:
    c = {k: sum(r[k] for r in rows if r['stratum'] == s) for k, _ in SETS}
    p('| %s | %d | %d/%d | %d/%d | %d/%d | %.1f | %.1f | %.1f |' % (s, cells[s], c['r22'], size['r22'], c['h37'], size['h37'], c['h99'], size['h99'],
                                                         cells[s] / n * size['r22'], cells[s] / n * size['h37'], cells[s] / n * size['h99']))
# by single variable
for name, f in (('block', block), ('depth bin (E graph as one)', depth_bin), ('size bin', lambda r: 'same' if r['output_size_equals_input'] else 'diff')):
    p('\n%s:' % name)
    vals = sorted(set(f(r) for r in rows))
    for v in vals:
        p('  %-8s pool %4d/%d' % (v, sum(f(r) == v for r in rows), n), ' '.join('%s %d/%d' % (lab, sum(r[k] and f(r) == v for r in rows), size[k]) for k, lab in SETS))
# where the current sets land under the rule
p('\ncurrent sets under the rule:')
for k, lab in SETS:
    c = collections.Counter(r['split'] for r in rows if r[k])
    p('  %s: train %d, dev %d, held-out %d (of %d)' % (lab, c['train'], c['dev'], c['held-out'], size[k]))
legacy = [r for r in rows if r['r22'] or r['h99']]
c = collections.Counter(r['split'] for r in legacy)
p('  the 22 and the 99 together: train %d, dev %d, held-out %d (of %d)' % (c['train'], c['dev'], c['held-out'], len(legacy)))
# option: keep current sets held-out; rule on the rest
rest = [r for r in rows if not (r['r22'] or r['h99'])]
c = collections.Counter(r['split'] for r in rest)
p('option keep: held-out = 121 current + rule-held-out of the rest %d -> held-out %d, dev %d, train %d' % (c['held-out'], 121 + c['held-out'], c['dev'], c['train']))
eb = collections.Counter((r['split'], r['r22'] or r['h99']) for r in rows if block(r) == 'E')
p('block E (120): rule split', dict(collections.Counter(r['split'] for r in rows if block(r) == 'E')), '; E tasks outside the 99 by rule split', {k[0]: v for k, v in eb.items() if not k[1]})
# balance checks on variables that are not strata
def cbin(r):
    x = r.get('cases')
    return 'none' if x is None else '0' if x == 0 else '1' if x == 1 else '2-3' if x <= 3 else '4+'


def ibin(r):
    x = r['input_cells_median']
    return 'a<=81' if x <= 81 else 'b82-225' if x <= 225 else 'c226+'


def fbin(r):
    x = r.get('fewest_productions')
    return 'none' if x is None else 'a<=7' if x <= 7 else 'b8-12' if x <= 12 else 'c13+'


def tbin(r):
    x = r.get('g_tables')
    return 'none' if x is None else 'a<=15' if x <= 15 else 'b16-30' if x <= 30 else 'c31+'


for name, f in (('case-counts cases', cbin), ('input cells median', ibin), ('fewest productions (upper bound)', fbin), ('graph tables', tbin), ('train pairs', lambda r: str(min(r['train_pairs'], 5)) + ('+' if r['train_pairs'] >= 5 else ''))):
    p('\ncheck, %s: per bin pool, then train/dev/held-out' % name)
    for v in sorted(set(f(r) for r in rows)):
        c = collections.Counter(r['split'] for r in rows if f(r) == v)
        m = sum(c.values())
        p('  %-8s pool %4d  train %4d (%.2f)  dev %3d (%.2f)  held-out %3d (%.2f)' % (v, m, c['train'], c['train'] / m, c['dev'], c['dev'] / m, c['held-out'], c['held-out'] / m))
# seeds for a solve change on sets of each size (normal formula of solve-noise-test-size/read.md Part B)
p('\nseeds per arm, two-sided .05, power .8, D0 scaled from the ramp (per task 0.0625/22 solves; 0.625/22 solves or has a candidate):')
for N in (22, 37, 99, tot['dev'], tot['held-out']):
    for lab, d0t in (('solves', 0.0625 / 22), ('solves or cand', 0.625 / 22)):
        D0 = d0t * N
        cells_ = []
        for pts in (1, 2, 5):
            dl = pts / 100 * N
            s = (1.960 * math.sqrt(D0 + dl) + 0.842 * math.sqrt(max(D0 + dl - dl * dl / N, 0))) ** 2 / dl ** 2
            cells_.append('+%d pts: delta %.1f, seeds %d' % (pts, dl, math.ceil(s)))
        p('  N=%d %-15s D0=%.2f  %s' % (N, lab, D0, ' | '.join(cells_)))
out.close()
with open(HERE + '/split.tsv', 'w') as f:
    f.write('task\tstratum\tsplit\tu\n')
    for r in rows:
        f.write('%s\t%s\t%s\t%.6f\n' % (r['task'], r['stratum'], r['split'], u(salt, r['task'])))
