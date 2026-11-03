"""Held set, train and dev split, strata, salt choice, sizes, and where the 22, the 37 and the 99 fall. Reads facts.jsonl here; writes split2.tsv and split2.out here.

Held: every task whose data/tasks/<id>.json `source` has arc-agi-2/evaluation (block E, 120 tasks).
Train and dev: the other tasks (block T, 1,027 tasks), by strata within T.
Stratum name = depth bin / size bin.
- depth bin: graph-tasks-SET.jsonl `goal_depth`: d1-4, d5-7, d8+; `none` where the task has no graph row, an `error` row, or goal_depth inf.
- size bin: `same` where every train pair's output has its input's height and width, else `diff`.
Assignment in T: u = first 16 hex digits of sha256("<salt>:<task id>") / 16**16; train where u < 0.85, else dev.
The salt is the one of 0..SALTS-1 whose split has the least chi-square of dev counts against their expected counts over the strata.
"""
import collections, hashlib, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SALTS = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
CUT = 0.85
allrows = [json.loads(l) for l in open(HERE + '/facts.jsonl')]


def block(r):
    return 'E' if 'arc-agi-2/evaluation' in r['source'] else 'T'


def depth_bin(r):
    d = r.get('goal_depth')
    if d is None or d == float('inf'):
        return 'none'
    return 'd1-4' if d <= 4 else 'd5-7' if d <= 7 else 'd8+'


def size_bin(r):
    return 'same' if r['output_size_equals_input'] else 'diff'


def stratum(r):
    return '%s/%s' % (depth_bin(r), size_bin(r))


def u(salt, t):
    return int(hashlib.sha256(('%d:%s' % (salt, t)).encode()).hexdigest()[:16], 16) / 16 ** 16


def split_of(r, salt):
    if block(r) == 'E':
        return 'held'
    return 'train' if u(salt, r['task']) < CUT else 'dev'


E = [r for r in allrows if block(r) == 'E']
rows = [r for r in allrows if block(r) == 'T']
for r in allrows:
    r['stratum'] = stratum(r)
cells = collections.Counter(r['stratum'] for r in rows)
order = sorted(cells)
DEV = 1 - CUT


def chi(salt):
    got = collections.Counter(r['stratum'] for r in rows if u(salt, r['task']) >= CUT)
    return sum((got[s] - cells[s] * DEV) ** 2 / (cells[s] * DEV) for s in order)


scores = sorted((chi(s), s) for s in range(SALTS))
best_chi, salt = scores[0]
med = scores[len(scores) // 2][0]
for r in allrows:
    r['split'] = split_of(r, salt)
out = open(HERE + '/split2.out', 'w')


def p(*a):
    print(*a, file=out)


p('salt %d of %d; chi-square %.2f (median over salts %.2f; %d terms, dev counts by stratum)' % (salt, SALTS, best_chi, med, len(order)))
tot = collections.Counter(r['split'] for r in allrows)
p('overall: pool %d, train %d, dev %d, held %d (T %d, E %d); dev share of T %.4f' % (len(allrows), tot['train'], tot['dev'], tot['held'], len(rows), len(E), tot['dev'] / len(rows)))
p('\n| Stratum | T pool | Train | Dev | Dev expected |')
p('|---|---|---|---|---|')
for s in order:
    c = collections.Counter(r['split'] for r in rows if r['stratum'] == s)
    p('| %s | %d | %d | %d | %.1f |' % (s, cells[s], c['train'], c['dev'], cells[s] * DEV))
p('| All | %d | %d | %d | %.1f |' % (len(rows), tot['train'], tot['dev'], len(rows) * DEV))
# held composition
p('\nheld (E): %d tasks' % len(E))
for name, f in (('depth bin', depth_bin), ('size bin', size_bin)):
    pass
hg = [r for r in E if r.get('goal_depth') is not None and r['goal_depth'] != float('inf')]
p('  with a usable union graph: %d; without: %d' % (len(hg), len(E) - len(hg)))
p('  output size same %d, diff %d' % (sum(size_bin(r) == 'same' for r in E), sum(size_bin(r) == 'diff' for r in E)))
p('  graph tasks by goal depth bin: ' + ', '.join('%s %d' % (b, sum(depth_bin(r) == b for r in hg)) for b in ('d1-4', 'd5-7', 'd8+')))
# current sets
SETS = [('r22', 'the 22'), ('h37', 'the 37'), ('h99', 'the 99')]
p('\ncurrent sets under the rule:')
for k, lab in SETS:
    c = collections.Counter(r['split'] for r in allrows if r[k])
    p('  %s: train %d, dev %d, held %d (of %d)' % (lab, c['train'], c['dev'], c['held'], sum(r[k] for r in allrows)))
p('  the 22 by block: %s' % dict(collections.Counter(block(r) for r in allrows if r['r22'])))
p('\nthe 22 per stratum: stratum, T pool, in the 22, of those train, dev')
for s in order:
    m = [r for r in rows if r['stratum'] == s and r['r22']]
    c = collections.Counter(r['split'] for r in m)
    p('  %-10s %3d  %2d  train %d  dev %d' % (s, cells[s], len(m), c['train'], c['dev']))
p('  rest of T (not in the 22): train %d, dev %d' % (sum(r['split'] == 'train' and not r['r22'] for r in rows), sum(r['split'] == 'dev' and not r['r22'] for r in rows)))
p('\nthe 37 and the 99 in E: 37 %d of %d in E; 99 %d of %d in E' % (sum(block(r) == 'E' and r['h37'] for r in allrows), sum(r['h37'] for r in allrows), sum(block(r) == 'E' and r['h99'] for r in allrows), sum(r['h99'] for r in allrows)))
# balance checks over T (train, dev), and E for context
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
    p('\ncheck, %s: per bin T pool, train, dev; then held' % name)
    for v in sorted(set(f(r) for r in allrows)):
        c = collections.Counter(r['split'] for r in rows if f(r) == v)
        m = sum(c.values())
        h = sum(f(r) == v for r in E)
        if m:
            p('  %-8s T pool %4d  train %4d (%.2f)  dev %3d (%.2f)  held %3d (of %d: %.2f)' % (v, m, c['train'], c['train'] / m, c['dev'], c['dev'] / m, h, len(E), h / len(E)))
        else:
            p('  %-8s T pool    0  held %3d (of %d: %.2f)' % (v, h, len(E), h / len(E)))
# seeds
p('\nseeds per arm, two-sided .05, power .8, D0 scaled from the ramp (per task 0.0625/22 solves; 0.625/22 solves or has a candidate):')
for N in (len(E), len(hg), tot['dev']):
    for lab, d0t in (('solves', 0.0625 / 22), ('solves or cand', 0.625 / 22)):
        D0 = d0t * N
        cells_ = []
        for pts in (1, 2, 5):
            dl = pts / 100 * N
            s = (1.960 * math.sqrt(D0 + dl) + 0.842 * math.sqrt(max(D0 + dl - dl * dl / N, 0))) ** 2 / dl ** 2
            cells_.append('+%d pts: delta %.2f, seeds %d (%.2f)' % (pts, dl, math.ceil(s), s))
        p('  N=%d %-15s D0=%.2f  %s' % (N, lab, D0, ' | '.join(cells_)))
# change of 3 solves
for N in (len(E), tot['dev']):
    D0 = 0.0625 / 22 * N
    dl = 3
    s = (1.960 * math.sqrt(D0 + dl) + 0.842 * math.sqrt(max(D0 + dl - dl * dl / N, 0))) ** 2 / dl ** 2
    p('  N=%d, change of 3 solves: seeds %.2f' % (N, s))
p('  standard error ratio against the 22: held sqrt(%d/22) = %.2f, dev sqrt(%d/22) = %.2f' % (len(E), math.sqrt(len(E) / 22), tot['dev'], math.sqrt(tot['dev'] / 22)))
p('  base solves at 8/989 on held: %.2f; on dev: %.2f' % (8 / 989 * len(E), 8 / 989 * tot['dev']))
out.close()
with open(HERE + '/split2.tsv', 'w') as f:
    f.write('task\tblock\tstratum\tsplit\tu\n')
    for r in allrows:
        f.write('%s\t%s\t%s\t%s\t%.6f\n' % (r['task'], block(r), r['stratum'] if block(r) == 'T' else '-', r['split'], u(salt, r['task'])))
