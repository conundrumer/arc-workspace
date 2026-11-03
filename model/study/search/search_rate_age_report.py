#!/usr/bin/env python3
"""Proposal rate against process age, memo size, pool size and result cache size, from the logs of a search-worker run.

    python3 search_rate_age_report.py RUN_FOLDER [--also EARLIER_RUN_FOLDER ...] [--json FILE]

RUN_FOLDER holds out/<arm>/<task>/work/<task>.log, supervisor logs and cpu.txt. The arms are base_s1, both_s1, base_s101 and both_s101. Each log is read one line at a time, and
only the numbers of each `prof` line and the `rss ... memos` line after it stay in memory. Python's standard library is enough to run it.

A span is the stretch between two neighbouring `prof` lines of one process generation. Every count in a span is a difference inside a generation: `t`, `visits`, `setup`, `nxt`,
`take`, `test`, `gc`, `notable`, `equal` and the cache and memo fields restart at a generation, `cpu` restarts at a new worker, and `draws`, `forms`, `nodes` and `dup` go on. Spans
leave out what comes before a generation's first `prof` line, which the renewal table sizes.

Words: a proposal or a try is one clause that the search gives (`draws`). A store is one new entry of the result cache, counted as the rise of `entries`: a store whose key the cache
holds adds no entry, so the count is a lower bound on the calls of `evict`. R is the relations that the cache holds, the second field of `cache (...)`. c is the fitted time of one
store for one held relation.
"""
import argparse
import ast
import collections
import json
import math
import os
import re
import sys

ARMS = ['base_s1', 'both_s1', 'base_s101', 'both_s101']
AGE_EDGES = [0, 30, 60, 120, 180, 240, 300, 360, 420, 480, 540, 660]
FORM_EDGES = [0, 250, 500, 1000, 1500, 2000, 3000]
MEMO_EDGES = [0, 20, 40, 60, 80, 100, 120, 400]
RSS_EDGES = [0, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500, 4000]
REL_EDGES = [0, 1000, 2000, 3000, 4000, 6000, 8000, 10000, 12000, 15000, 20000, 30000, 100000]
FIT_EDGES = [0, 2000, 4000, 6000, 8000, 10000, 12000, 15000, 20000, 100000]
RENEW_MIB = 2888 * 0.6  # ARC_RENEW_SHARE default of --rss-limit-mib
DOUBLING_FORMS = 8  # gold forms per doubling of budget, from earlier runs, rough
GEN = re.compile(r'generation (\d+): rss (\d+) after load, (\d+) forms, (\d+) nodes, (\d+) s')
END = re.compile(r'end: (\w+), (\d+) draws, (\d+) forms, (\d+) nodes, (\d+) candidates, (\d+) MiB, (\d+) s')
STATS = re.compile(r'cache \(([^)]*)\), memos \(\(([^)]*)\), \(([^)]*)\)\)')
BANK = re.compile(r'bank file ([\d.]+) MiB in ([\d.]+) s')
PEAK = re.compile(r'RSS peak (\d+) MiB')
JUMP = re.compile(r'rss (\d+) from (\d+) at')


def ints(s):
    return [int(x) for x in s.split(',')]


def read_log(path):
    """Yields ('prof', dict), ('gen', tuple), ('end', tuple), ('bank', tuple), ('counts', dict), ('peak', MiB) and ('jump', (to, from)) in log order."""
    pending = None
    with open(path, errors='replace') as f:
        for line in f:
            if line.startswith('prof '):
                if pending is not None:
                    yield 'prof', pending
                pending = json.loads(line[5:])
            elif line.startswith('rss ') and ' from ' in line[:24]:
                m = JUMP.match(line)
                if m:
                    yield 'jump', (int(m[1]), int(m[2]))
            elif line.startswith('rss ') and pending is not None:
                m = STATS.search(line)
                if m:
                    c, p, w = ints(m[1]), ints(m[2]), ints(m[3])
                    pending.update(cache_entries=c[0], cache_rel=c[1], cache_bytes=c[2], cache_idx=c[3], cache_idx_bytes=c[4], intern_bytes=c[5],
                                   probe_bytes=p[0], probe_rel=p[1], probe_idx=p[2], probe_intern=p[3], walk_bytes=w[0], walk_n=w[1])
                yield 'prof', pending
                pending = None
            elif line.startswith('generation '):
                m = GEN.match(line)
                if m:
                    yield 'gen', tuple(int(x) for x in m.groups())
            elif line.startswith('end: '):
                m = END.match(line)
                if m:
                    yield 'end', (m[1],) + tuple(int(x) for x in m.groups()[1:])
            elif line.startswith('bank file '):
                m = BANK.match(line)
                if m:
                    yield 'bank', (float(m[1]), float(m[2]))
            elif line.startswith("{'"):
                try:
                    yield 'counts', ast.literal_eval(line)
                except (ValueError, SyntaxError):
                    pass
            elif 'RSS peak' in line:
                m = PEAK.search(line)
                if m:
                    yield 'peak', int(m[1])
    if pending is not None:
        yield 'prof', pending


def load(folder, arms):
    """(spans, jobs). A job holds its generations, each with its first and last prof line, load seconds, end line and counts."""
    rows, jobs = [], []
    for arm in arms:
        base = '%s/out/%s' % (folder, arm)
        for task in sorted(os.listdir(base)):
            path = '%s/%s/work/%s.log' % (base, task, task)
            if not os.path.exists(path):
                continue
            job = dict(arm=arm, task=task, gens=[], lives=0, peak=0, jumps=[])
            jobs.append(job)
            g, prev, last_cpu, clock = None, None, None, 0
            for kind, x in read_log(path):
                if kind == 'gen':
                    if g is not None:
                        clock += g['end'][-1] if g['end'] else g['last']['t'] if g['last'] else 0
                    g = dict(gen=x[0], load_rss=x[1], forms0=x[2], nodes0=x[3], load_s=x[4], first=None, last=None, end=None, bank=None, n=0, rss_max=x[1], clock=clock)
                    job['gens'].append(g)
                    prev = None
                elif kind == 'end':
                    g['end'] = x
                    g['rss_max'] = max(g['rss_max'], x[5])
                elif kind == 'bank':
                    g['bank'] = x
                elif kind == 'counts':
                    g['counts'] = x
                elif kind == 'peak':
                    job['peak'] = max(job['peak'], x)
                elif kind == 'jump':
                    if g is not None:
                        g['rss_max'] = max(g['rss_max'], x[0])
                        job['jumps'].append((g['gen'], x[0], x[1], (g['last'] or {}).get('t', 0)))
                elif kind == 'prof' and g is not None:
                    if g['first'] is None:
                        g['first'] = x
                    g['last'] = x
                    g['n'] += 1
                    g['rss_max'] = max(g['rss_max'], x['rss'])
                    if last_cpu is None or x['cpu'] < last_cpu:
                        job['lives'] += 1
                        g['new_life'] = True
                    last_cpu = x['cpu']
                    if prev is not None:
                        rows.append(span(arm, task, g, prev, x))
                    prev = x
    return rows, jobs


def span(arm, task, g, a, b):
    d = lambda k: b.get(k, 0) - a.get(k, 0)  # earlier runs' prof lines have fewer fields
    r = dict(arm=arm, task=task, gen=g['gen'], age0=a['t'], age1=b['t'], cpu=d('cpu'), wall=d('t'), draws=d('draws'), forms=d('forms'), nodes=d('nodes'),
             notable=d('notable'), equal=d('equal'), dup=d('dup'), visits=d('visits'), setup=d('setup'), nxt=d('nxt'), take=d('take'), test=d('test'), gc=d('gc'), gcn=d('gcn'),
             rss=b['rss'], pool_forms=b['forms'], cache_bytes=b.get('cache_bytes', 0), cache_idx_bytes=b.get('cache_idx_bytes', 0), probe=b.get('probe_bytes', 0), walk=b.get('walk_bytes', 0))
    r['memo'] = r['probe'] + r['walk']
    r['clock'] = g['clock'] + a['t']
    r['rel'] = b.get('cache_rel', 0)
    r['Rm'] = (b.get('cache_rel', 0) + a.get('cache_rel', 0)) / 2
    r['stores'] = b.get('cache_entries', 0) - a.get('cache_entries', 0)
    r['fail'] = r['draws'] - r['forms'] - r['notable'] - r['equal']
    return r


def band(x, edges):
    for i in range(len(edges) - 1):
        if edges[i] <= x < edges[i + 1]:
            return i
    return len(edges) - 2


def group(rows, key):
    out = collections.defaultdict(list)
    for r in rows:
        out[key(r)].append(r)
    return out


KEYS = ('cpu', 'wall', 'draws', 'forms', 'notable', 'equal', 'dup', 'fail', 'visits', 'setup', 'nxt', 'take', 'test', 'gc', 'stores')


def sums(rows):
    return {k: sum(r[k] for r in rows) for k in KEYS}


def table(head, rows):
    print('| ' + ' | '.join(head) + ' |')
    print('| ' + ' | '.join('---' for _ in head) + ' |')
    for r in rows:
        print('| ' + ' | '.join(str(x) for x in r) + ' |')
    print()


def arm_of(arm):
    return arm.split('_')[0]


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def weighted(rows, field):
    c = sum(r['cpu'] for r in rows)
    return sum(r[field] * r['cpu'] for r in rows) / c


def solve(A, b):
    """x of A x = b, by Gaussian elimination with pivoting. A column with no pivot gets 0."""
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda k: abs(M[k][i]))
        M[i], M[p] = M[p], M[i]
        if abs(M[i][i]) < 1e-12:
            continue
        for k in range(n):
            if k != i and M[k][i]:
                f = M[k][i] / M[i][i]
                M[k] = [u - f * v for u, v in zip(M[k], M[i])]
    return [M[i][n] / M[i][i] if abs(M[i][i]) >= 1e-12 else 0.0 for i in range(n)]


def ols(X, y, w=None):
    """Least squares of y on the columns of X, with weights w. Gives (coefficients, the share of the sum of squares of y that the fit takes)."""
    w = w or [1.0] * len(y)
    k = len(X[0])
    A = [[0.0] * k for _ in range(k)]
    b = [0.0] * k
    for x, v, u in zip(X, y, w):
        for i in range(k):
            b[i] += u * x[i] * v
            for j in range(i, k):
                A[i][j] += u * x[i] * x[j]
    for i in range(k):
        for j in range(i):
            A[i][j] = A[j][i]
    beta = solve(A, b)
    res = sum(u * (v - sum(c * z for c, z in zip(beta, x))) ** 2 for x, v, u in zip(X, y, w))
    tot = sum(u * v * v for v, u in zip(y, w))
    return beta, 1 - res / tot if tot else 0.0


def within(rows, X, y, w):
    """X and y with each job's weighted mean taken off."""
    g = collections.defaultdict(list)
    for i, r in enumerate(rows):
        g[r['arm'], r['task']].append(i)
    X2, y2 = [list(x) for x in X], list(y)
    k = len(X[0])
    for ids in g.values():
        tw = sum(w[i] for i in ids)
        ym = sum(w[i] * y[i] for i in ids) / tw
        xm = [sum(w[i] * X[i][j] for i in ids) / tw for j in range(k)]
        for i in ids:
            y2[i] -= ym
            X2[i] = [X[i][j] - xm[j] for j in range(k)]
    return X2, y2


def rate_rows(rows, edges, field, unit=1):
    out = []
    for kind in ('base', 'both'):
        g = group([r for r in rows if arm_of(r['arm']) == kind], lambda r: band(r[field] / unit, edges))
        for i in sorted(g):
            s = sums(g[i])
            sr = [sums([r for r in g[i] if r['arm'].endswith(x)]) for x in ('_s1', '_s101')]
            c = s['cpu']
            out.append([kind, '%g-%g' % (edges[i], edges[i + 1]), len({(r['arm'], r['task']) for r in g[i]}), '%.0f' % c, '%.2f' % (s['draws'] / c)] + ['%.2f' % (x['draws'] / x['cpu']) if x['cpu'] else '-' for x in sr]
                       + ['%.2f' % ((s['forms'] - s['dup']) / c), '%.2f' % (s['dup'] / c), '%.2f' % (s['equal'] / c), '%.2f' % (s['notable'] / c), '%.2f' % (s['fail'] / c)])
    return ['arm', 'band', 'jobs', 'CPU s', 'proposals/CPU s', 'seed 1', 'seed 101', 'forms less dup/CPU s', 'dup/CPU s', 'equal/CPU s', 'no table/CPU s', 'failed/CPU s'], out


def parts_rows(rows, edges, field):
    """Each part of a try's cost by band. The timers are wall seconds; `cpu` is CPU seconds."""
    out = []
    for kind in ('base', 'both'):
        g = group([r for r in rows if arm_of(r['arm']) == kind], lambda r: band(r[field], edges))
        for i in sorted(g):
            s = sums(g[i])
            d, c = s['draws'], s['cpu']
            out.append([kind, '%g-%g' % (edges[i], edges[i + 1]), '%.0f' % (1000 * c / d), '%.1f' % (1000 * s['setup'] / d), '%.1f' % (1000 * s['nxt'] / d), '%.1f' % (1000 * (s['take'] - s['test']) / d), '%.1f' % (1000 * s['test'] / d), '%.1f' % (1000 * s['gc'] / d),
                        '%.0f' % (1000 * s['setup'] / max(1, s['visits'])), '%.0f' % (1000 * s['test'] / max(1, s['forms'])), '%.2f' % (s['forms'] / d), '%.0f' % (s['stores'] / d), '%.0f' % weighted(g[i], 'Rm'), '%.0f' % weighted(g[i], 'pool_forms'), '%.0f' % weighted(g[i], 'rss')])
    return ['arm', 'band', 'CPU ms/try', 'setup', 'nxt', 'take less test', 'test', 'gc (inside the others)', 'setup ms/visit', 'test ms/form', 'forms/try', 'stores/try', 'R', 'pool forms', 'RSS'], out


def pods(folder):
    got, pod = {}, None
    try:
        with open(folder + '/cpu.txt') as f:
            for line in f:
                m = re.match(r'pod (\w):', line)
                if m:
                    pod = m[1]
                if line.startswith('tasks:'):
                    for t in line.split()[1:]:
                        got[t] = pod
    except OSError:
        pass
    return got


def kind_x(r):
    return [r['forms'] - r['dup'], r['dup'], r['equal'], r['notable'], r['fail']]


def records(jobs, rows):
    print('## Records\n')
    print('jobs %d, spans %d, generations %d.' % (len(jobs), len(rows), sum(len(j['gens']) for j in jobs)))
    print('generations by arm: %s' % {a: sum(len(j['gens']) for j in jobs if j['arm'] == a) for a in ARMS})
    print('end: memory lines by arm: %s' % {a: sum(1 for j in jobs if j['arm'] == a for g in j['gens'] if g['end'] and g['end'][0] == 'memory') for a in ARMS})
    print('end lines by kind: %s' % dict(collections.Counter((arm_of(j['arm']), g['end'][0] if g['end'] else 'no end line') for j in jobs for g in j['gens'])))
    print('jobs with more than one worker life: %s' % [(j['arm'], j['task']) for j in jobs if j['lives'] > 1])
    neg = collections.Counter(k for r in rows for k in KEYS if r[k] < 0)
    print('negative differences inside a generation: %s (the cache never fell inside a generation, so no entry left it)' % dict(neg))
    top = max(rows, key=lambda r: r['cache_bytes'] + r['cache_idx_bytes'])
    print('largest cache bytes plus index bytes in a span, MiB: %.0f on %s %s at age %.0f; the eviction bound at session share .65 is %.0f' % ((top['cache_bytes'] + top['cache_idx_bytes']) / 2 ** 20, top['arm'], top['task'], top['age1'], 2888 * 0.65 / 2))
    print('new worker lives after the first, by arm: %s' % {a: sum(j['lives'] - 1 for j in jobs if j['arm'] == a) for a in ARMS})
    print('largest RSS in a job by the `RSS peak` field (ru_maxrss, which an execv keeps): %s' % sorted(((j['peak'], j['arm'], j['task']) for j in jobs), reverse=True)[:4])
    print('largest sampled RSS by arm: %s\n' % {a: max(g['rss_max'] for j in jobs if j['arm'] == a for g in j['gens']) for a in ARMS})


def controls(rows, folder):
    print('## Controls\n')
    print('Base, process age 30 to 120 s, by job clock: the pool grows and the machine load changes, and the process stays young.\n')
    out = []
    base = [r for r in rows if arm_of(r['arm']) == 'base' and 30 <= r['age0'] < 120]
    for lo, hi in ((0, 100), (100, 200), (200, 300), (300, 400), (400, 500), (500, 700)):
        x = [r for r in base if lo <= r['clock'] < hi]
        s = sums(x)
        out.append(['%d-%d' % (lo, hi), len({(r['arm'], r['task']) for r in x}), '%.0f' % s['cpu'], '%.2f' % (s['draws'] / s['cpu']), '%.0f' % (1000 * s['cpu'] / s['draws']), '%.0f' % (1000 * s['test'] / s['forms']), '%.0f' % weighted(x, 'pool_forms'), '%.0f' % weighted(x, 'Rm')])
    table(['job clock s', 'jobs', 'CPU s', 'proposals/CPU s', 'CPU ms/try', 'test ms/form', 'pool forms', 'R'], out)
    print('By host. Pod d sat on a host with load 17 to 64; the other pods shared a host with load 239 to 357, 192 CPUs on each.\n')
    pm = pods(folder)
    out = []
    for kind in ('base', 'both'):
        for lo, hi in ((0, 60), (60, 120), (120, 240), (240, 360), (360, 480), (480, 660)):
            x = [r for r in rows if arm_of(r['arm']) == kind and lo <= r['age0'] < hi]
            a, b = [r for r in x if pm.get(r['task']) == 'd'], [r for r in x if pm.get(r['task']) != 'd']
            if a and b and sum(r['cpu'] for r in a) > 100:
                sa, sb = sums(a), sums(b)
                out.append([kind, '%d-%d' % (lo, hi), '%.2f' % (sa['draws'] / sa['cpu']), '%.2f' % (sb['draws'] / sb['cpu']), '%.2f' % ((sa['draws'] / sa['cpu']) / (sb['draws'] / sb['cpu']))])
    table(['arm', 'age s', 'pod d', 'other pods', 'pod d / others'], out)
    print('Young base against old both on one task, one seed, pool forms 700 to 1,300, CPU s over 30 on each side.\n')
    pairs = []
    for t in sorted({r['task'] for r in rows}):
        for seed in ('_s1', '_s101'):
            a = [r for r in rows if r['arm'] == 'base' + seed and r['task'] == t and 700 <= r['pool_forms'] < 1300 and r['age0'] < 120]
            b = [r for r in rows if r['arm'] == 'both' + seed and r['task'] == t and 700 <= r['pool_forms'] < 1300]
            if sum(r['cpu'] for r in a) > 30 and sum(r['cpu'] for r in b) > 30:
                sa, sb = sums(a), sums(b)
                pairs.append((sa['draws'] / sa['cpu'], sb['draws'] / sb['cpu'], weighted(a, 'age1'), weighted(b, 'age1'), weighted(a, 'Rm'), weighted(b, 'Rm')))
    table(['pairs', 'base proposals/CPU s', 'both', 'median both/base', 'both lower in', 'age base', 'age both', 'R base', 'R both'],
          [[len(pairs), '%.2f' % med(p[0] for p in pairs), '%.2f' % med(p[1] for p in pairs), '%.2f' % med(p[1] / p[0] for p in pairs), sum(p[1] < p[0] for p in pairs)] + ['%.0f' % med(p[j] for p in pairs) for j in (2, 3, 4, 5)]])
    print('Base against both on one task, one seed, one band of R, process age 45 s or more, CPU s over 20 on each side.\n')
    out = []
    for lo, hi in ((3000, 5000), (5000, 7000), (7000, 10000), (10000, 16000)):
        ps = []
        for t in sorted({r['task'] for r in rows}):
            for seed in ('_s1', '_s101'):
                a = [r for r in rows if r['arm'] == 'base' + seed and r['task'] == t and lo <= r['Rm'] < hi and r['age0'] >= 45]
                b = [r for r in rows if r['arm'] == 'both' + seed and r['task'] == t and lo <= r['Rm'] < hi and r['age0'] >= 45]
                if sum(r['cpu'] for r in a) > 20 and sum(r['cpu'] for r in b) > 20:
                    sa, sb = sums(a), sums(b)
                    ps.append((1000 * sa['cpu'] / sa['draws'], 1000 * sb['cpu'] / sb['draws'], weighted(a, 'age1'), weighted(b, 'age1'), weighted(a, 'pool_forms'), weighted(b, 'pool_forms'), weighted(a, 'rss'), weighted(b, 'rss'), sa['stores'] / sa['draws'], sb['stores'] / sb['draws']))
        if ps:
            out.append(['%d-%d' % (lo, hi), len(ps), '%.0f' % med(p[0] for p in ps), '%.0f' % med(p[1] for p in ps), '%.2f' % med(p[1] / p[0] for p in ps)] + ['%.0f, %.0f' % (med(p[j] for p in ps), med(p[j + 1] for p in ps)) for j in (2, 4, 6, 8)])
    table(['R', 'pairs', 'base CPU ms/try', 'both', 'median both/base', 'age', 'pool forms', 'RSS', 'stores/try'], out)


def mix(rows):
    print('## Mix\n')
    print('Cost of one try of each kind, ms, a fit of a span\'s CPU s on its counts of tries of each kind, with no job term.\n')
    sets = (('base, age 30-120, clock over 100', [r for r in rows if arm_of(r['arm']) == 'base' and 30 <= r['age0'] < 120 and r['clock'] > 100]),
            ('both, age under 120', [r for r in rows if arm_of(r['arm']) == 'both' and r['age0'] < 120]), ('both, age 360 and over', [r for r in rows if arm_of(r['arm']) == 'both' and r['age0'] >= 360]))
    out, base_k = [], None
    for name, x in sets:
        b, _ = ols([kind_x(r) for r in x], [r['cpu'] for r in x])
        base_k = base_k or b
        out.append([name] + ['%.0f' % (1000 * v) for v in b])
    table(['spans', 'new form', 'dup form', 'equal', 'no table', 'failed'], out)
    print('Rate at fixed kind costs: the tries of each band, each kind at the cost of the first row above. CPU s over that cost is the decay with the mix taken out.\n')
    out = []
    for kind in ('base', 'both'):
        g = group([r for r in rows if arm_of(r['arm']) == kind], lambda r: band(r['age0'], AGE_EDGES))
        for i in sorted(g):
            s = sums(g[i])
            exp = sum(sum(c * z for c, z in zip(base_k, kind_x(r))) for r in g[i])
            out.append([kind, '%d-%d' % (AGE_EDGES[i], AGE_EDGES[i + 1]), '%.2f' % (s['draws'] / s['cpu']), '%.2f' % (s['draws'] / exp), '%.2f' % (s['cpu'] / exp)])
        s = sums([r for r in rows if arm_of(r['arm']) == kind])
        exp = sum(sum(c * z for c, z in zip(base_k, kind_x(r))) for r in rows if arm_of(r['arm']) == kind)
        out.append([kind, 'all spans', '%.2f' % (s['draws'] / s['cpu']), '%.2f' % (s['draws'] / exp), '%.2f' % (s['cpu'] / exp)])
    table(['arm', 'age s', 'proposals/CPU s', 'at fixed kind costs', 'CPU s over cost'], out)


def fits(rows):
    print('## Cost of a store against R\n')
    rows = [r for r in rows if r['draws'] >= 5 and r['stores'] >= 0]
    out = []
    for name, sel in (('both', [r for r in rows if arm_of(r['arm']) == 'both']), ('base', [r for r in rows if arm_of(r['arm']) == 'base']), ('base, age 45 and over', [r for r in rows if arm_of(r['arm']) == 'base' and r['age0'] >= 45])):
        kk = sorted({band(r['Rm'], FIT_EDGES) for r in sel})
        X, y, w = [], [], []
        for r in sel:
            s = r['stores'] / r['draws']
            b = band(r['Rm'], FIT_EDGES)
            X.append([r['forms'] / r['draws'], s] + [s if b == k else 0.0 for k in kk[1:]])
            y.append(1000 * r['cpu'] / r['draws'])
            w.append(r['draws'])
        X2, y2 = within(sel, X, y, w)
        b, r2 = ols(X2, y2, w)
        for k, d in zip(kk[1:], b[2:]):
            rm = sum(r['Rm'] for r in sel if band(r['Rm'], FIT_EDGES) == k) / sum(1 for r in sel if band(r['Rm'], FIT_EDGES) == k)
            out.append([name, '%d-%d' % (FIT_EDGES[k], FIT_EDGES[k + 1]), '%.0f' % rm, '%.3f' % d, '%.0f' % (d * 1e6 / rm), '%.2f' % r2])
    print('CPU ms/try on forms/try, stores/try and stores/try in each band of R, within a job, weighted by tries. Extra ms/store is against the lowest band. r2 is of the fit within a job.\n')
    table(['arm', 'R', 'mean R', 'extra ms/store', 'ns/store/relation', 'r2'], out)
    print('Which measure takes the variance within a job, on both: CPU ms/try on forms/try, stores/try and one measure, r2 of the fit.\n')
    both = [r for r in rows if arm_of(r['arm']) == 'both']
    out = []
    for name, f in (('stores/try x R', lambda r: r['stores'] / r['draws'] * r['Rm']), ('R', lambda r: r['Rm']), ('process age', lambda r: r['age1']), ('cache MiB', lambda r: r['cache_bytes'] / 2 ** 20), ('RSS', lambda r: r['rss']), ('pool forms', lambda r: r['pool_forms']), ('memo MiB', lambda r: r['memo'] / 2 ** 20)):
        X = [[r['forms'] / r['draws'], r['stores'] / r['draws'], f(r)] for r in both]
        y = [1000 * r['cpu'] / r['draws'] for r in both]
        w = [r['draws'] for r in both]
        X2, y2 = within(both, X, y, w)
        b, r2 = ols(X2, y2, w)
        out.append([name, '%.3g' % b[2], '%.3f' % r2])
    table(['measure', 'coefficient, ms/try per unit', 'r2'], out)
    print('Same age, tasks that differ in R: one row per age band, one point per both job. Excess is CPU ms/try in the band less the job\'s own in age 30 to 120. x is stores/try x R in the band less the same in age 30 to 120.\n')
    jobs = group(both, lambda r: (r['arm'], r['task']))
    out = []
    for lo, hi in ((180, 300), (300, 420), (420, 540), (480, 620)):
        pts = []
        for x in jobs.values():
            fresh, late = [r for r in x if 30 <= r['age0'] < 120], [r for r in x if lo <= r['age0'] < hi]
            if not fresh or sum(r['cpu'] for r in late) < 30:
                continue
            sf, sl = sums(fresh), sums(late)
            xs = [sum(r['stores'] * r['Rm'] for r in q) / s['draws'] for q, s in ((fresh, sf), (late, sl))]
            pts.append((1000 * (sl['cpu'] / sl['draws'] - sf['cpu'] / sf['draws']), xs[1] - xs[0]))
        b, _ = ols([[p[1], 1.0] for p in pts], [p[0] for p in pts])
        mx, my = sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)
        cov = sum((p[1] - mx) * (p[0] - my) for p in pts)
        corr = cov / math.sqrt(sum((p[1] - mx) ** 2 for p in pts) * sum((p[0] - my) ** 2 for p in pts))
        out.append(['%d-%d' % (lo, hi), len(pts), '%.0f' % (b[0] * 1e6), '%.0f' % b[1], '%.0f' % my, '%.0f' % (b[0] * mx), '%.2f' % corr])
    table(['age s', 'jobs', 'slope ns/store/relation', 'intercept ms/try', 'mean excess ms/try', 'slope x mean x, ms/try', 'correlation'], out)
    print('The fit of one job at a time: span CPU s on tries, forms, stores and stores x R. Quantiles over jobs of the last coefficient, ns/store/relation.\n')
    out = []
    for arm in ARMS:
        cs = []
        for x in group([r for r in rows if r['arm'] == arm], lambda r: r['task']).values():
            if len(x) >= 15:
                b, _ = ols([[r['draws'], r['forms'], r['stores'], r['stores'] * r['Rm']] for r in x], [r['cpu'] for r in x])
                cs.append(b[3] * 1e9)
        out.append([arm, len(cs), '%.0f' % q(cs, .1), '%.0f' % q(cs, .25), '%.0f' % med(cs), '%.0f' % q(cs, .75), '%.0f' % q(cs, .9)])
    table(['arm', 'jobs', 'q10', 'q25', 'median', 'q75', 'q90'], out)
    print('Which timer holds the slope, both, within a job: each part ms/try on forms/try, stores/try and stores/try x R. The timers are wall seconds.\n')
    out = []
    use = both
    for name, f in (('setup', lambda r: r['setup']), ('nxt', lambda r: r['nxt']), ('take less test', lambda r: r['take'] - r['test']), ('test', lambda r: r['test']), ('gc, inside the others', lambda r: r['gc']), ('CPU s of the span', lambda r: r['cpu'])):
        X = [[r['forms'] / r['draws'], r['stores'] / r['draws'], r['stores'] / r['draws'] * r['Rm']] for r in use]
        y = [1000 * f(r) / r['draws'] for r in use]
        w = [r['draws'] for r in use]
        X2, y2 = within(use, X, y, w)
        b, r2 = ols(X2, y2, w)
        out.append([name, '%.1f' % (b[2] * 1e6), '%.2f' % r2])
    table(['part', 'ns/store/relation', 'r2'], out)
    print('Cost with the scan taken off, both: CPU ms/try less c x stores/try x R, by age band, at three values of c, and the rate that gives.\n')
    g = group(both, lambda r: band(r['age0'], AGE_EDGES))
    out = []
    for i in sorted(g):
        s = sums(g[i])
        row = ['%d-%d' % (AGE_EDGES[i], AGE_EDGES[i + 1]), '%.0f' % (1000 * s['cpu'] / s['draws'])]
        for c in (55, 70, 100):
            scan = sum(r['stores'] * r['Rm'] for r in g[i]) * c * 1e-9
            row += ['%.0f' % (1000 * scan / s['draws']), '%.2f' % (s['draws'] / (s['cpu'] - scan))]
        out.append(row)
    table(['age s', 'CPU ms/try', 'scan at 55 ns, ms/try', 'rate', 'scan at 70 ns', 'rate', 'scan at 100 ns', 'rate'], out)


def job_cpu(j):
    """The CPU s of a job: `cpu` of its last prof line in each worker life."""
    ends, cur = [], None
    for g in j['gens']:
        if g.get('new_life') and cur is not None:
            ends.append(cur)
        if g['last']:
            cur = g['last']['cpu']
    ends.append(cur or 0)
    return sum(ends)


def steps(jobs, rows):
    print('## One step: the last 6 spans of a generation against 6 spans of the next from age 15 s on\n')
    print('The pool and the search state carry over a renewal, so what changes is the process.\n')
    J = group([r for r in rows if r['stores'] >= 0], lambda r: (r['arm'], r['task']))
    ev = []
    for j in jobs:
        x = J[j['arm'], j['task']]
        for a, b in zip(j['gens'], j['gens'][1:]):
            if not a['end'] or a['end'][0] != 'memory':
                continue
            before = sorted((r for r in x if r['gen'] == a['gen']), key=lambda r: r['age0'])[-6:]
            after = sorted((r for r in x if r['gen'] == b['gen'] and r['age0'] >= 15), key=lambda r: r['age0'])[:6]
            if len(before) < 3 or len(after) < 3:
                continue
            sa, sb = sums(before), sums(after)
            ev.append(dict(arm=j['arm'], task=j['task'], age=a['end'][-1], c0=1000 * sa['cpu'] / sa['draws'], c1=1000 * sb['cpu'] / sb['draws'], x0=sum(r['stores'] * r['Rm'] for r in before) / sa['draws'], x1=sum(r['stores'] * r['Rm'] for r in after) / sb['draws'],
                           R0=weighted(before, 'Rm'), R1=weighted(after, 'Rm'), f0=sa['forms'] / sa['draws'], f1=sb['forms'] / sb['draws']))
    out = []
    for v in ev:
        if arm_of(v['arm']) == 'both':
            out.append([v['arm'], v['task'], v['age'], '%.1f' % (1000 / v['c0']), '%.1f' % (1000 / v['c1']), '%.0f' % v['c0'], '%.0f' % v['c1'], '%.0f' % v['R0'], '%.0f' % v['R1'], '%.2f' % v['f0'], '%.2f' % v['f1']])
    table(['arm', 'task', 'age at renewal s', 'proposals/CPU s before', 'after', 'CPU ms/try before', 'after', 'R before', 'after', 'forms/try before', 'after'], out)
    out = []
    for name, sel in (('both', [v for v in ev if arm_of(v['arm']) == 'both']), ('base, age at renewal 120 and over', [v for v in ev if arm_of(v['arm']) == 'base' and v['age'] >= 120]), ('base, under 120', [v for v in ev if arm_of(v['arm']) == 'base' and v['age'] < 120])):
        dc, dx = med(v['c0'] - v['c1'] for v in sel), med(v['x0'] - v['x1'] for v in sel)
        out.append([name, len(sel), '%.0f' % med(v['c0'] for v in sel), '%.0f' % med(v['c1'] for v in sel), '%.0f' % med(v['R0'] for v in sel), '%.0f' % med(v['R1'] for v in sel), '%.0f' % dc, '%.0f' % dx, '%.0f' % (dc * 1e6 / dx) if dx > 20000 else '-'])
    table(['renewals', 'n', 'CPU ms/try before', 'after', 'R before', 'after', 'median fall ms/try', 'median fall of stores/try x R', 'ns/store/relation if R were all of it'], out)


def out_tries(jobs):
    print('## OUT tries\n')
    print('`out:tried` of the counts line at a generation\'s end, for generations with one. A job killed at its end leaves no counts line.\n')
    out = []
    rows = collections.defaultdict(lambda: [0, 0, 0.0, 0])
    for j in jobs:
        for g in j['gens']:
            c = g.get('counts')
            if c and g['last'] and g['end']:
                k = (arm_of(j['arm']), min(g['gen'], 4))
                u = rows[k]
                u[0] += c.get('out:tried', 0)
                u[1] += g['end'][2] - g['forms0']
                u[2] += g['last']['test']
                u[3] += 1
    for k in sorted(rows):
        u = rows[k]
        out.append([k[0], k[1] if k[1] < 4 else '4 and later', u[3], u[0], u[1], '%.1f' % (u[0] / max(1, u[1])), '%.1f' % (1000 * u[2] / max(1, u[0]))])
    table(['arm', 'generation', 'generations', 'OUT tries', 'forms', 'OUT tries/form', 'test ms/OUT try'], out)


def renewals(jobs, rows):
    print('## What a renewal costs, base\n')
    young = [r for r in rows if arm_of(r['arm']) == 'base' and 30 <= r['age0'] < 120 and r['clock'] > 100]
    sy = sums(young)
    steady = sy['draws'] / sy['cpu']
    gaps, loads, banks = [], [], []
    for j in jobs:
        if arm_of(j['arm']) != 'base':
            continue
        gs = [g for g in j['gens'] if g['first'] and g['last']]
        for a, b in zip(gs, gs[1:]):
            if b.get('new_life') or not a['end']:
                continue
            gc, gd = b['first']['cpu'] - a['last']['cpu'], b['first']['draws'] - a['last']['draws']
            gaps.append((gc, gd))
            loads.append(b['load_s'])
            banks.append(a['bank'][1] if a['bank'] else 0.0)
    gc = sum(g[0] for g in gaps)
    gd = sum(g[1] for g in gaps)
    cpu_all = 0.0
    for j in jobs:
        if arm_of(j['arm']) == 'base':
            cpu_all += job_cpu(j)
    s = sums([r for r in rows if arm_of(r['arm']) == 'base'])
    dup_ms = ols([kind_x(r) for r in young], [r['cpu'] for r in young])[0][1]
    lost = gc - gd / steady
    print('Renewals with a span on each side: %d. CPU s from the last prof line of a generation to the first of the next: %.1f on average, with %.1f proposals in them; at the young rate of %.2f those proposals take %.1f CPU s.' % (len(gaps), gc / len(gaps), gd / len(gaps), steady, gd / len(gaps) / steady))
    print('CPU s lost per renewal, gap less that: %.1f. Sum %.0f of %.0f CPU s, %.1f%%.' % (lost / len(gaps), lost, cpu_all, 100 * lost / cpu_all))
    print('Load seconds per renewal, wall: median %.0f. Bank write, wall: median %.2f s.' % (med(loads), med(banks)))
    print('Duplicate forms: %d, at %.0f ms each by the fit in the mix table: %.0f CPU s, %.1f%% of CPU s. They add no form.\n' % (s['dup'], dup_ms * 1000, s['dup'] * dup_ms, 100 * s['dup'] * dup_ms / cpu_all))
    return steady


def gains(jobs, rows, steady):
    print('## Size of a flat rate on both\n')
    both = group([r for r in rows if arm_of(r['arm']) == 'both' and r['draws'] > 0], lambda r: (r['arm'], r['task']))
    jj = {(j['arm'], j['task']): j for j in jobs}
    fresh_all = sums([r for r in rows if arm_of(r['arm']) == 'both' and r['age0'] < 30])
    fresh60 = sums([r for r in rows if arm_of(r['arm']) == 'both' and r['age0'] < 60])
    young = steady
    print('Levels, proposals/CPU s: both age 0-30 %.2f, both age 0-60 %.2f, base age 30-120 with clock over 100 %.2f.\n' % (fresh_all['draws'] / fresh_all['cpu'], fresh60['draws'] / fresh60['cpu'], young))
    rowsv = collections.defaultdict(list)
    rss_age = {}
    for key, x in both.items():
        j = jj[key]
        T = job_cpu(j)
        last = [g['last'] for g in j['gens'] if g['last']][-1]
        n, forms, dup = last['draws'], last['forms'], last['dup']
        dist = forms - dup
        x = sorted(x, key=lambda r: (r['gen'], r['age0']))
        # forms per try in the last third of the job's tries
        done, tail_d, tail_f, tail_cost = 0, 0, 0, 0.0
        cum = []
        for r in x:
            done += r['draws']
            cum.append((done, r))
        total = done
        for at, r in cum:
            if at > total * 2 / 3:
                tail_d += r['draws']
                tail_f += r['forms'] - r['dup']
                tail_cost += r['cpu']
        tail = tail_f / max(1, tail_d)
        # exponent of forms on tries, on the job's second half
        pts, cf = [], 0
        cn = n - total
        for at, r in cum:
            cn += r['draws']
            cf += r['forms'] - r['dup']
            if at > total / 2 and cf > 0:
                pts.append((math.log(cn), math.log(cf + max(0, dist - sum(q['forms'] - q['dup'] for q in x)))))
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
        e = sum((p[0] - mx) * (p[1] - my) for p in pts) / max(1e-9, sum((p[0] - mx) ** 2 for p in pts))
        e = min(max(e, 0.1), 1.0)
        # cost per try against tries so far, T(n) = a n + k n^2 / 2
        Xc, yc, wc = [], [], []
        run = n - total
        for r in x:
            mid = run + r['draws'] / 2
            run += r['draws']
            Xc.append([1.0, mid])
            yc.append(r['cpu'] / r['draws'])
            wc.append(r['draws'])
        (a, k), _ = ols(Xc, yc, wc)
        k = max(k, 1e-9)
        s_try = sum(r['stores'] for r in x) / sum(r['draws'] for r in x)
        rho = max(r['rel'] for r in x if r['gen'] == x[-1]['gen']) / max(1, n)
        v = rowsv
        ratio = T / 600  # CPU s per elapsed s
        T_h = 3600 * ratio

        def solve_n(t, a_, k_):
            return (-a_ + math.sqrt(a_ * a_ + 2 * k_ * t)) / k_ if k_ > 0 else t / a_

        def forms_at(m, base_n, base_f):
            """(constant tail, power law)."""
            return (base_f + (m - base_n) * tail, base_f * (m / base_n) ** e) if m >= base_n else (base_f * m / base_n, base_f * (m / base_n) ** e)

        def scen(name, n600, nhour):
            f600 = forms_at(n600, n, dist)
            fh = forms_at(nhour, n, dist)
            v[name].append((n600, f600[0], f600[1], nhour, fh[0], fh[1]))

        # the record itself
        base_h = solve_n(T_h, a, k)
        # renewal at the trend age of RENEW_MIB
        g0 = [r for r in x if r['gen'] == 0 and r['age1'] >= 120]
        if len(g0) >= 5:
            (sl, b0), _ = ols([[r['age1'], 1.0] for r in g0], [float(r['rss']) for r in g0])
            age_r = (RENEW_MIB - b0) / sl if sl > 0 else 1e9
            age_x = (2400 - b0) / sl if sl > 0 else 1e9
        else:
            age_r, age_x, sl = 1e9, 1e9, 0.0
        rss_age[key] = (sl, age_r, age_x)
        cpu_r = age_r * ratio
        if cpu_r < T_h:
            full = int(T_h // cpu_r)
            n_r = full * solve_n(cpu_r, a, k) + solve_n(T_h - full * cpu_r, a, k)
        else:
            n_r = base_h
        scen('record, no renewal', n, base_h)
        v['record, renewal at 1,733 MiB'].append((n, dist, dist, n_r) + forms_at(n_r, n, dist))
        for name, r0 in (('flat at both age 0-30', fresh_all['draws'] / fresh_all['cpu']), ('flat at both age 0-60', fresh60['draws'] / fresh60['cpu']), ('flat at young base', young)):
            scen(name, r0 * T, r0 * T_h)
        for c in (55, 70, 100):
            scan = sum(r['stores'] * r['Rm'] for r in x) * c * 1e-9
            cost_tail = (tail_cost - sum(r['stores'] * r['Rm'] for at, r in cum if at > total * 2 / 3) * c * 1e-9) / max(1, tail_d)
            fresh = [r for r in x if r['age0'] < 60]
            own = sum(r['cpu'] for r in fresh) / max(1, sum(r['draws'] for r in fresh)) if fresh else 0.09
            n_fix = n + scan / max(cost_tail, own)
            k2 = max(k - s_try * c * 1e-9 * rho, 0.0)
            scen('scan gone, c %d ns, no renewal' % c, n_fix, solve_n(T_h, a, k2))
            if cpu_r < T_h:
                full = int(T_h // cpu_r)
                n_h = full * solve_n(cpu_r, a, k2) + solve_n(T_h - full * cpu_r, a, k2)
            else:
                n_h = solve_n(T_h, a, k2)
            scen('scan gone, c %d ns, renewal at 1,733 MiB' % c, n_fix, n_h)
    head = ['case', 'tries 600 s', 'forms less dup 600 s, tail held', 'power law', 'tries/record', 'gold gain, 8 x log2', 'tries 3,600 s', 'forms, tail held', 'power law', 'tries over no renewal', 'gold', 'tries over renewal', 'gold']
    out = []
    base0 = rowsv['record, no renewal']
    baseR = rowsv['record, renewal at 1,733 MiB']
    n0, nh, nr = sum(v[0] for v in base0), sum(v[3] for v in base0), sum(v[3] for v in baseR)
    result = {}
    for name, v in rowsv.items():
        m = len(v)
        a = [sum(u[i] for u in v) for i in range(6)]
        result[name] = dict(tries_600=a[0] / m, forms_600_tail=a[1] / m, forms_600_power=a[2] / m, tries_3600=a[3] / m, forms_3600_tail=a[4] / m, forms_3600_power=a[5] / m)
        out.append([name, '%.0f' % (a[0] / m), '%.0f' % (a[1] / m), '%.0f' % (a[2] / m), '%.2f' % (a[0] / n0), '%.1f' % (DOUBLING_FORMS * math.log2(a[0] / n0)), '%.0f' % (a[3] / m), '%.0f' % (a[4] / m), '%.0f' % (a[5] / m),
                    '%.2f' % (a[3] / nh), '%.1f' % (DOUBLING_FORMS * math.log2(a[3] / nh)), '%.2f' % (a[3] / nr), '%.1f' % (DOUBLING_FORMS * math.log2(a[3] / nr))])
    print('Means over the %d both jobs. CPU s per job is the job\'s own, and an hour is 3,600 s at the job\'s CPU s per elapsed s. Tail held keeps forms less dup per try of the job\'s last third of tries. Power law takes forms as tries to the power the job\'s second half gives. An hour rests on a line: cost per try against tries so far, fitted to each job and carried past its 600 s.\n' % len(base0))
    table(head, out)
    return rss_age, result


def rss(jobs, rows, rss_age):
    print('## RSS on both\n')
    B = [r for r in rows if arm_of(r['arm']) == 'both' and r['gen'] == 0]
    E = [0, 60, 120, 240, 360, 480, 560, 700]
    g = group(B, lambda r: band(r['age1'], E))
    out = []
    for i in sorted(g):
        x = g[i]
        out.append(['%d-%d' % (E[i], E[i + 1]), len(x), '%.0f' % med(r['rss'] for r in x), '%.0f' % q([r['rss'] for r in x], .9), '%.0f' % max(r['rss'] for r in x), '%.0f' % med((r['cache_bytes'] + r['cache_idx_bytes']) / 2 ** 20 for r in x),
                    '%.0f' % med(r['memo'] / 2 ** 20 for r in x), '%.0f' % max(r['memo'] / 2 ** 20 for r in x), '%.0f' % med(r['rss'] - (r['cache_bytes'] + r['cache_idx_bytes'] + r['memo']) / 2 ** 20 for r in x)])
    table(['age s', 'spans', 'RSS median', 'q90', 'max', 'cache + index MiB, median', 'memos median', 'memos max', 'rest median'], out)
    sl = [v[0] for v in rss_age.values() if v[0] > 0]
    a1 = [v[1] for v in rss_age.values() if v[0] > 0]
    a2 = [v[2] for v in rss_age.values() if v[0] > 0]
    print('Trend from age 120 s, one line per job, %d jobs: slope MiB/s q10 %.2f, median %.2f, q90 %.2f.' % (len(sl), q(sl, .1), med(sl), q(sl, .9)))
    print('Age where the line meets 1,733 MiB: q10 %.0f, median %.0f, q90 %.0f s. Age where it meets 2,400 MiB: q10 %.0f, median %.0f, q90 %.0f s. Each is past the 600 s of the record.' % (q(a1, .1), med(a1), q(a1, .9), q(a2, .1), med(a2), q(a2, .9)))
    cs = []
    for x in group([r for r in B if r['age1'] >= 120], lambda r: (r['arm'], r['task'])).values():
        if len(x) >= 10:
            cs.append(ols([[r['age1'], 1.0] for r in x], [(r['cache_bytes'] + r['cache_idx_bytes']) / 2 ** 20 for r in x])[0][0])
    print('Cache plus index slope, median %.2f MiB/s.\n' % med(cs))
    print('Each both generation that ended at `end: memory`.\n')
    out = []
    for j in jobs:
        if arm_of(j['arm']) == 'both':
            for g in j['gens']:
                if g['end'] and g['end'][0] == 'memory':
                    jump = [x for x in j['jumps'] if x[0] == g['gen'] and x[1] == g['end'][5]]
                    out.append([j['arm'], j['task'], g['gen'], g['end'][-1], g['end'][5], jump[-1][2] if jump else '-', max(j['peak'], g['rss_max'])])
    table(['arm', 'task', 'generation', 'age s', 'RSS at end', 'RSS at the sample before', 'largest RSS of the job, sampled or `RSS peak`'], out)


def earlier(folder):
    print('## Earlier run: %s\n' % os.path.basename(folder.rstrip('/')))
    arms = sorted(os.listdir(folder + '/out'))
    rows, jobs = load(folder, arms)
    rows = [r for r in rows if r['draws'] > 0 and r['stores'] >= 0]
    out = []
    for j in jobs:
        if len(j['gens']) > 2:
            continue
        x = [r for r in rows if r['arm'] == j['arm'] and r['task'] == j['task']]
        for lo, hi in ((0, 60), (60, 150), (150, 300), (300, 450), (450, 700)):
            y = [r for r in x if lo <= r['age0'] < hi and r['gen'] == 0]
            if not y:
                continue
            s = sums(y)
            d = s['draws']
            out.append([j['arm'], j['task'], '%d-%d' % (lo, hi), '%.2f' % (d / s['cpu']), '%.0f' % (1000 * s['cpu'] / d), '%.0f' % (s['stores'] / d), '%.0f' % weighted(y, 'Rm'), '%.2f' % (s['forms'] / d), '%.0f' % (1000 * s['test'] / max(1, s['forms'])), '%.1f' % (1000 * s['gc'] / d), '%.0f' % weighted(y, 'rss'), '%.0f' % (s['stores'] / d * weighted(y, 'Rm') * 70e-6)])
    table(['arm', 'task', 'age s', 'proposals/CPU s', 'CPU ms/try', 'stores/try', 'R', 'forms/try', 'test ms/form', 'gc ms/try', 'RSS', 'stores/try x R x 70 ns, ms'], out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--also', action='append', default=[])
    ap.add_argument('--json', default='')
    a = ap.parse_args()
    rows, jobs = load(a.run, ARMS)
    use = [r for r in rows if r['draws'] > 0 and r['cpu'] > 0]
    records(jobs, rows)
    print('## Rate tables\n')
    for name, edges, field, unit in (('process age, s (`t`)', AGE_EDGES, 'age0', 1), ('forms in the pool', FORM_EDGES, 'pool_forms', 1), ('memo MiB: probe memo bytes plus walk memo bytes', MEMO_EDGES, 'memo', 2 ** 20), ('RSS MiB', RSS_EDGES, 'rss', 1), ('R, relations the result cache holds', REL_EDGES, 'Rm', 1)):
        print('By %s.\n' % name)
        table(*rate_rows(use, edges, field, unit))
    print('## Parts of a try\n')
    print('By process age. ms/try unless named.\n')
    table(*parts_rows(use, AGE_EDGES, 'age0'))
    print('By R.\n')
    table(*parts_rows(use, REL_EDGES, 'Rm'))
    controls(use, a.run)
    mix(use)
    fits(use)
    steps(jobs, use)
    out_tries(jobs)
    steady = renewals(jobs, use)
    rss_age, result = gains(jobs, use, steady)
    rss(jobs, use, rss_age)
    for f in a.also:
        earlier(f)
    if a.json:
        with open(a.json, 'w') as f:
            json.dump(result, f, indent=1)


if __name__ == '__main__':
    main()
