#!/usr/bin/env python3
"""Proposal rate against process age on a run that compares two wheels: which part of a try each wheel spends, and which measure of a process's state fits the rise.

    python3 search_rate_age2_report.py RUN_FOLDER > tables.txt

RUN_FOLDER holds out/<arm>/<task>/work/<task>.log. The arms are both_s1, both_s101, evict_s1 and evict_s101. The script imports the log reader and the fit helpers of
search_rate_age_report.py (RATE_AGE_REPORT overrides its path); that file's docstring defines a span, a store and R. Python's standard library is enough to run it.
"""
import argparse
import collections
import importlib.util
import math
import os
import sys

BASE_REPORT = os.environ.get('RATE_AGE_REPORT', '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/search_rate_age_report.py')
spec = importlib.util.spec_from_file_location('search_rate_age_report', BASE_REPORT)
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

ARMS = ['both_s1', 'both_s101', 'evict_s1', 'evict_s101']
KINDS = ('both', 'evict')
AGE_EDGES = [0, 30, 60, 120, 180, 240, 300, 360, 420, 480, 540, 660]
WIDE = [(0, 60), (60, 120), (120, 240), (240, 360), (360, 480), (480, 660)]
R_BANDS = [(0, 2000), (2000, 4000), (4000, 6000), (6000, 8000), (8000, 10000), (10000, 13000), (13000, 17000), (17000, 22000), (22000, 30000), (30000, 100000)]
PARTS = (('setup', lambda s: s['setup']), ('nxt', lambda s: s['nxt']), ('take less test', lambda s: s['take'] - s['test']), ('test', lambda s: s['test']), ('rest of CPU', lambda s: s['cpu'] - s['setup'] - s['nxt'] - s['take']))
CPU = lambda s: s['cpu']  # noqa: E731
MEASURES = (('stores/try x R', lambda r: r['stores'] * r['Rm']), ('R', lambda r: r['Rm'] * r['draws']), ('log2 R', lambda r: math.log2(max(r['Rm'], 1)) * r['draws']), ('entries', lambda r: r['entries'] * r['draws']),
            ('log2 entries', lambda r: math.log2(max(r['entries'], 1)) * r['draws']), ('stores/try', lambda r: r['stores']), ('forms/try', lambda r: r['forms']), ('index count', lambda r: r['idx'] * r['draws']),
            ('index MiB', lambda r: r['cache_idx_bytes'] / 2 ** 20 * r['draws']), ('cache MiB', lambda r: r['cache_bytes'] / 2 ** 20 * r['draws']), ('pool forms', lambda r: r['pool_forms'] * r['draws']), ('RSS', lambda r: r['rss'] * r['draws']),
            ('rest of RSS', lambda r: (r['rss'] - (r['cache_bytes'] + r['cache_idx_bytes'] + r['memo']) / 2 ** 20) * r['draws']), ('memo MiB', lambda r: r['memo'] / 2 ** 20 * r['draws']), ('walk memo domains', lambda r: r['walk_n'] * r['draws']),
            ('intern KiB', lambda r: r['intern'] / 1024 * r['draws']), ('runs alive', lambda r: r['runs'] * r['draws']), ('visits/try', lambda r: r['visits']), ('gc ms/try', lambda r: 1000 * r['gc']))


def per_try(s, f):
    return 1000 * f(s) / s['draws']


def load(folder):
    """The spans of search_rate_age_report.span, with the extra fields of each prof line that a read here needs."""
    rows = []
    for arm in ARMS:
        base = '%s/out/%s' % (folder, arm)
        for task in sorted(os.listdir(base)):
            path = '%s/%s/work/%s.log' % (base, task, task)
            if not os.path.exists(path):
                continue
            prev, gen = None, None
            for kind, x in B.read_log(path):
                if kind == 'gen':
                    prev, gen = None, x[0]
                elif kind == 'prof':
                    if prev is not None:
                        r = B.span(arm, task, dict(gen=gen, clock=0), prev, x)
                        mean = lambda k: (x.get(k, 0) + prev.get(k, 0)) / 2  # noqa: B023
                        r.update(runs=x.get('runs', 0), hot=x.get('hot', 0), idx=mean('cache_idx'), intern=x.get('intern_bytes', 0), entries=mean('cache_entries'), probe_rel=x.get('probe_rel', 0), walk_n=x.get('walk_n', 0),
                                 d_bytes=x.get('cache_bytes', 0) - prev.get('cache_bytes', 0), d_idx_bytes=x.get('cache_idx_bytes', 0) - prev.get('cache_idx_bytes', 0), d_rel=x.get('cache_rel', 0) - prev.get('cache_rel', 0), d_idx=x.get('cache_idx', 0) - prev.get('cache_idx', 0))
                        rows.append(r)
                    prev = x
    return rows


def arm(rows, kind):
    return [r for r in rows if B.arm_of(r['arm']) == kind]


def wide(rows, kind, lo, hi):
    return [r for r in arm(rows, kind) if lo <= r['age0'] < hi]


def age_tables(rows):
    print('## Rate by process age\n')
    out = []
    for kind in KINDS:
        g = B.group(arm(rows, kind), lambda r: B.band(r['age0'], AGE_EDGES))
        for i in sorted(g):
            s = B.sums(g[i])
            sr = [B.sums([r for r in g[i] if r['arm'].endswith(x)]) for x in ('_s1', '_s101')]
            d, c = s['draws'], s['cpu']
            out.append([kind, '%d-%d' % (AGE_EDGES[i], AGE_EDGES[i + 1]), len({(r['arm'], r['task']) for r in g[i]}), '%.0f' % c, '%.2f' % (d / c)] + ['%.2f' % (x['draws'] / x['cpu']) for x in sr]
                       + ['%.0f' % (1000 * c / d)] + ['%.1f' % per_try(s, f) for _, f in PARTS]
                       + ['%.1f' % (1000 * s['gc'] / d), '%.0f' % (1000 * s['setup'] / max(1, s['visits'])), '%.0f' % (1000 * s['test'] / max(1, s['forms'])), '%.2f' % (s['forms'] / d), '%.2f' % (s['equal'] / d), '%.2f' % (s['fail'] / d), '%.0f' % (s['stores'] / d), '%.0f' % B.weighted(g[i], 'Rm'), '%.0f' % B.weighted(g[i], 'pool_forms'), '%.0f' % B.weighted(g[i], 'rss')])
    B.table(['arm', 'age s', 'jobs', 'CPU s', 'proposals/CPU s', 'seed 1', 'seed 101', 'CPU ms/try'] + [p[0] for p in PARTS] + ['gc, inside the others', 'setup ms/visit', 'test ms/form', 'forms/try', 'equal/try', 'failed/try', 'stores/try', 'R', 'pool forms', 'RSS'], out)
    print('Wide bands.\n')
    out = []
    for kind in KINDS:
        for lo, hi in ((0, 60), (480, 660)):
            x = wide(rows, kind, lo, hi)
            s = B.sums(x)
            out.append([kind, '%d-%d' % (lo, hi), len({(r['arm'], r['task']) for r in x}), '%.0f' % s['cpu'], '%.2f' % (s['draws'] / s['cpu'])])
    B.table(['arm', 'age s', 'jobs', 'CPU s', 'proposals/CPU s'], out)


def split(rows):
    print('## The rise by part, both and evict\n')
    print('Rise is the band less age 0-60 s. Fall is both less evict in the band. ms/try. The timers are wall seconds, and `rest of CPU` is CPU s less the three outer timers, so it can go below 0.\n')
    out = []
    y = {k: B.sums(wide(rows, k, 0, 60)) for k in KINDS}
    for lo, hi in WIDE:
        a, b = B.sums(wide(rows, 'both', lo, hi)), B.sums(wide(rows, 'evict', lo, hi))
        row = ['%d-%d' % (lo, hi), '%.1f' % per_try(a, CPU), '%.1f' % per_try(b, CPU)]
        for name, f in PARTS:
            row += ['%.1f' % (per_try(a, f) - per_try(y['both'], f)), '%.1f' % (per_try(b, f) - per_try(y['evict'], f)), '%.1f' % (per_try(a, f) - per_try(b, f))]
        out.append(row)
    head = ['age s', 'both CPU ms/try', 'evict']
    for name, _ in PARTS:
        head += [name + ' rise both', 'rise evict', 'fall']
    B.table(head, out)


def by_r(rows):
    print('## Parts at one R, both and evict, age 45 s and over\n')
    print('ms/try, pooled over jobs in the band. `scan` is stores/try x R x 70 ns.\n')
    out = []
    for lo, hi in R_BANDS:
        got = [[r for r in arm(rows, kind) if lo <= r['Rm'] < hi and r['age0'] >= 45] for kind in KINDS]
        if not all(got):
            continue
        row = ['%d-%d' % (lo, hi)]
        for x in got:
            s = B.sums(x)
            d = s['draws']
            row += ['%.0f' % per_try(s, CPU)] + ['%.1f' % per_try(s, f) for _, f in PARTS[:4]] + ['%.0f' % (s['stores'] / d), '%.2f' % (s['forms'] / d), '%.0f' % B.weighted(x, 'age1'), '%.0f' % B.weighted(x, 'pool_forms'), '%.0f' % (sum(r['stores'] * r['Rm'] for r in x) / d * 70e-6)]
        out.append(row)
    head = ['R']
    for k in KINDS:
        head += [k + ' CPU ms/try', 'setup', 'nxt', 'take less test', 'test', 'stores/try', 'forms/try', 'age', 'pool forms', 'scan']
    B.table(head, out)


def paired(rows):
    print('## Both less evict on one task, one seed, one band of R, age 45 s and over\n')
    print('Each point is a task, seed and R band with 20 CPU s or more on each side. The slope is the fall in a part per unit of stores/try x R on both, through 0, weighted by CPU s. It says which part held the scan that the patch took off.\n')
    idx = collections.defaultdict(list)
    for r in rows:
        if r['age0'] >= 45:
            for i, (lo, hi) in enumerate(R_BANDS):
                if lo <= r['Rm'] < hi:
                    idx[r['task'], r['arm'].split('_')[1], B.arm_of(r['arm']), i].append(r)
                    break
    extra = PARTS + (('CPU', CPU), ('forms/try x 1000', lambda s: s['forms']), ('stores/try', lambda s: s['stores'] / 1000))
    pts = []
    for (task, seed, kind, i), a in list(idx.items()):
        b = idx.get((task, seed, 'evict', i))
        if kind != 'both' or not b:
            continue
        sa, sb = B.sums(a), B.sums(b)
        if sa['cpu'] >= 20 and sb['cpu'] >= 20:
            pts.append(dict(x=sum(r['stores'] * r['Rm'] for r in a) / sa['draws'], w=min(sa['cpu'], sb['cpu']), d={name: per_try(sa, f) - per_try(sb, f) for name, f in extra}))
    out = []
    for name, _ in extra:
        b, r2 = B.ols([[p['x']] for p in pts], [p['d'][name] for p in pts], [p['w'] for p in pts])
        out.append([name, len(pts), '%.1f' % (b[0] * 1e6), '%.2f' % r2, '%.1f' % (sum(p['d'][name] * p['w'] for p in pts) / sum(p['w'] for p in pts))])
    B.table(['part', 'points', 'slope ns/store/relation', 'r2', 'mean both less evict, ms/try'], out)


def kinds_table(rows):
    print('## Cost of a try of each kind, by age\n')
    print('ms, a fit of a span\'s CPU s on its counts of tries of each kind, with no job term. `new form` holds its OUT test.\n')
    out = []
    for kind in KINDS:
        for lo, hi in WIDE:
            x = wide(rows, kind, lo, hi)
            b, _ = B.ols([[r['forms'], r['equal'], r['fail']] for r in x], [r['cpu'] for r in x])
            s = B.sums(x)
            d = s['draws']
            out.append([kind, '%d-%d' % (lo, hi), '%.0f' % (1000 * b[0]), '%.0f' % (1000 * b[1]), '%.0f' % (1000 * b[2]), '%.2f' % (s['forms'] / d), '%.2f' % (s['equal'] / d), '%.2f' % (s['fail'] / d), '%.0f' % (1000 * s['cpu'] / d)])
    B.table(['arm', 'age s', 'new form', 'equal', 'failed', 'forms/try', 'equal/try', 'failed/try', 'CPU ms/try'], out)
    print('Cost of the rise with the kinds held: each band\'s tries of each kind at the costs of its arm\'s age 0-60 s. Mix is that against age 0-60 s, and per-try cost is the rest.\n')
    out = []
    for kind in KINDS:
        y = wide(rows, kind, 0, 60)
        b0, _ = B.ols([[r['forms'], r['equal'], r['fail']] for r in y], [r['cpu'] for r in y])
        sy = B.sums(y)
        c0 = 1000 * sy['cpu'] / sy['draws']
        for lo, hi in WIDE[1:]:
            s = B.sums(wide(rows, kind, lo, hi))
            at = 1000 * (b0[0] * s['forms'] + b0[1] * s['equal'] + b0[2] * s['fail']) / s['draws']
            c = per_try(s, CPU)
            out.append([kind, '%d-%d' % (lo, hi), '%.0f' % c0, '%.0f' % c, '%.0f' % at, '%.0f' % (at - c0), '%.0f' % (c - at)])
    B.table(['arm', 'age s', 'CPU ms/try at 0-60 s', 'CPU ms/try', 'at fixed kind costs', 'mix', 'per-try cost'], out)


def test_split(rows):
    print('## What `test` per form is made of\n')
    print('Stores are not split by part: `stores/form` is all stores of the band over its forms, so it is an upper bound on the stores of `test`.\n')
    out = []
    for kind in KINDS:
        for lo, hi in WIDE:
            s = B.sums(wide(rows, kind, lo, hi))
            d = s['draws']
            out.append([kind, '%d-%d' % (lo, hi), '%.0f' % (1000 * s['test'] / s['forms']), '%.0f' % (s['stores'] / s['forms']), '%.2f' % (1000 * (s['test'] + s['nxt']) / max(1, s['stores'])), '%.2f' % (1000 * s['test'] / max(1, s['stores'])), '%.1f' % (1000 * s['nxt'] / d), '%.1f' % (1000 * s['gc'] / d)])
    B.table(['arm', 'age s', 'test ms/form', 'stores/form', 'test + nxt ms/store', 'test ms/store', 'nxt ms/try', 'gc ms/try'], out)


def band_mean(x, f):
    return sum(f(r) for r in x) / sum(r['draws'] for r in x)


def slopes(rows, kind, part_name='CPU', part=CPU):
    jobs = B.group([r for r in arm(rows, kind) if r['stores'] >= 0], lambda r: (r['arm'], r['task']))
    out = []
    for lo, hi in ((240, 360), (360, 480), (480, 620)):
        for name, f in MEASURES:
            pts = []
            for x in jobs.values():
                fresh, late = [r for r in x if 30 <= r['age0'] < 120], [r for r in x if lo <= r['age0'] < hi]
                if not fresh or sum(r['cpu'] for r in late) < 30:
                    continue
                pts.append((per_try(B.sums(late), part) - per_try(B.sums(fresh), part), band_mean(late, f) - band_mean(fresh, f), band_mean(late, f)))
            for what, get in (('rise', lambda p: p[1]), ('level', lambda p: p[2])):
                mx, my = sum(get(p) for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)
                sxx, syy = sum((get(p) - mx) ** 2 for p in pts), sum((p[0] - my) ** 2 for p in pts)
                if sxx > 0 and syy > 0:
                    cov = sum((get(p) - mx) * (p[0] - my) for p in pts)
                    out.append([part_name, kind, '%d-%d' % (lo, hi), len(pts), name, what, '%.2f' % (cov / math.sqrt(sxx * syy)), '%.3g' % (cov / sxx), '%.0f' % (my - cov / sxx * mx), '%.1f' % my])
    return out


def slope_tables(rows):
    print('## Which measure sorts the tasks at one age\n')
    print('One point per job. y is a part in the age band less the job\'s own at age 30-120 s, ms/try. x is the measure in the band less the job\'s own at age 30-120 s (`rise`), or the measure in the band (`level`). corr is the correlation across jobs; intercept is y at x = 0.\n')
    head = ['y', 'arm', 'age s', 'jobs', 'measure', 'x', 'corr', 'slope', 'intercept', 'mean y']
    out = []
    for kind in KINDS:
        out += slopes(rows, kind)
    B.table(head, sorted(out, key=lambda v: (v[1], v[2], -abs(float(v[6])))))
    for name, f in PARTS[:4]:
        print('Top measures for one part, evict, age 480-620 s.\n')
        B.table(head, sorted((v for v in slopes(rows, 'evict', name, f) if v[2] == '480-620'), key=lambda v: -abs(float(v[6])))[:8])


def within_tables(rows):
    print('## Which measure takes the variance within a job\n')
    print('CPU ms/try on forms/try, stores/try and one measure, with each job\'s mean taken off, weighted by tries.\n')
    out = []
    for kind in KINDS:
        sel = [r for r in arm(rows, kind) if r['draws'] >= 5 and r['stores'] >= 0]
        y = [1000 * r['cpu'] / r['draws'] for r in sel]
        w = [r['draws'] for r in sel]
        for name, f in MEASURES:
            X2, y2 = B.within(sel, [[r['forms'] / r['draws'], r['stores'] / r['draws'], f(r) / r['draws']] for r in sel], y, w)
            b, r2 = B.ols(X2, y2, w)
            out.append([kind, name, '%.3g' % b[2], '%.3f' % r2])
    B.table(['arm', 'measure', 'coefficient, ms/try per unit', 'r2'], sorted(out, key=lambda v: (v[0], -float(v[3]))))


def shape(rows):
    print('## Shape of the cost in R, within a job\n')
    print('Each band against the job\'s own cost at R 2,000-4,000, ms/try. Medians over jobs with 20 CPU s or more in both bands. A straight line in R is a scan. A curve that flattens is a table that outgrows a memory cache of the machine, or a walk by depth.\n')
    out = []
    for kind in KINDS:
        jobs = B.group(arm(rows, kind), lambda r: (r['arm'], r['task']))
        for lo, hi in R_BANDS[2:]:
            pts = []
            for x in jobs.values():
                a, b = [r for r in x if 2000 <= r['Rm'] < 4000], [r for r in x if lo <= r['Rm'] < hi]
                if sum(r['cpu'] for r in a) >= 20 and sum(r['cpu'] for r in b) >= 20:
                    sa, sb = B.sums(a), B.sums(b)
                    pts.append((per_try(sb, CPU) - per_try(sa, CPU), per_try(sb, lambda s: s['nxt']) - per_try(sa, lambda s: s['nxt']), per_try(sb, lambda s: s['test']) - per_try(sa, lambda s: s['test']), sb['forms'] / sb['draws'] - sa['forms'] / sa['draws'], B.weighted(b, 'Rm'), sb['stores'] / sb['draws'] - sa['stores'] / sa['draws'], B.weighted(b, 'entries')))
            if pts:
                out.append([kind, '%d-%d' % (lo, hi), len(pts), '%.0f' % B.med(p[4] for p in pts), '%.0f' % B.med(p[6] for p in pts), '%.1f' % B.med(p[0] for p in pts), '%.1f' % B.med(p[1] for p in pts), '%.1f' % B.med(p[2] for p in pts), '%.2f' % B.med(p[3] for p in pts), '%.0f' % B.med(p[5] for p in pts)])
    B.table(['arm', 'R band', 'jobs', 'R', 'entries', 'CPU rise', 'nxt rise', 'test rise', 'forms/try change', 'stores/try change'], out)


def renewals(rows):
    print('## One step at a renewal\n')
    print('The last 6 spans of a generation against 6 spans of the next from age 15 s on, for generations that reached age 120 s. Pairs are before, after.\n')
    out, ev = [], []
    for (a_, task), x in sorted(B.group(rows, lambda r: (r['arm'], r['task'])).items()):
        gens = sorted({r['gen'] for r in x})
        for a, b in zip(gens, gens[1:]):
            before = sorted((r for r in x if r['gen'] == a), key=lambda r: r['age0'])[-6:]
            after = sorted((r for r in x if r['gen'] == b and r['age0'] >= 15), key=lambda r: r['age0'])[:6]
            if len(before) < 3 or len(after) < 3 or before[-1]['age1'] < 120:
                continue
            sa, sb = B.sums(before), B.sums(after)
            fs = (CPU, lambda s: s['setup'], lambda s: s['nxt'], lambda s: s['take'] - s['test'], lambda s: s['test'])
            v = [(per_try(sa, f), per_try(sb, f)) for f in fs]
            tf = (1000 * sa['test'] / max(1, sa['forms']), 1000 * sb['test'] / max(1, sb['forms']))
            ev.append(v + [tf])
            out.append([a_, task, a, '%.0f' % before[-1]['age1'], '%.0f, %.0f' % (B.weighted(before, 'Rm'), B.weighted(after, 'Rm'))] + ['%.0f, %.0f' % p for p in v] + ['%.0f, %.0f' % tf, '%.2f, %.2f' % (sa['forms'] / sa['draws'], sb['forms'] / sb['draws']), '%.0f, %.0f' % (sa['stores'] / sa['draws'], sb['stores'] / sb['draws']), '%.0f, %.0f' % (B.weighted(before, 'pool_forms'), B.weighted(after, 'pool_forms'))])
    B.table(['arm', 'task', 'generation', 'age at end s', 'R', 'CPU ms/try', 'setup', 'nxt', 'take less test', 'test', 'test ms/form', 'forms/try', 'stores/try', 'pool forms'], out)
    if ev:
        print('Medians over %d renewals, before, after: CPU %.0f, %.0f; setup %.1f, %.1f; nxt %.0f, %.0f; take less test %.0f, %.0f; test %.0f, %.0f; test ms/form %.0f, %.0f.\n' % ((len(ev),) + tuple(B.med(v[i][j] for v in ev) for i in range(6) for j in (0, 1))))


def visits(rows):
    print('## Visits\n')
    print('A visit ends after 8 tries in a row with no new form, or at 4 s, or when the search has no clause left. `wall s/visit` near one value at every age means that tries per visit follow from the cost of a try, so that `visits/try` follows the cost and does not cause it.\n')
    out = []
    for kind in KINDS:
        g = B.group(arm(rows, kind), lambda r: B.band(r['age0'], AGE_EDGES))
        for i in sorted(g):
            s = B.sums(g[i])
            out.append([kind, '%d-%d' % (AGE_EDGES[i], AGE_EDGES[i + 1]), '%.2f' % (s['wall'] / max(1, s['visits'])), '%.1f' % (s['draws'] / max(1, s['visits'])), '%.0f' % (1000 * s['cpu'] / s['draws']), '%.0f' % (1000 * s['setup'] / max(1, s['visits']))])
    B.table(['arm', 'age s', 'wall s/visit', 'tries/visit', 'CPU ms/try', 'setup ms/visit'], out)
    print('Wall s/visit by quarter of each job\'s own CPU ms/try at age 240 s and over, evict: one row per quarter of spans, by CPU ms/try of the span.\n')
    x = sorted([r for r in arm(rows, 'evict') if r['age0'] >= 240 and r['visits'] > 0], key=lambda r: r['cpu'] / r['draws'])
    n = len(x)
    out = []
    for i in range(4):
        q = x[i * n // 4:(i + 1) * n // 4]
        s = B.sums(q)
        out.append([i + 1, len(q), '%.0f' % (1000 * s['cpu'] / s['draws']), '%.2f' % (s['wall'] / s['visits']), '%.1f' % (s['draws'] / s['visits']), '%.2f' % (s['forms'] / s['draws'])])
    B.table(['quarter', 'spans', 'CPU ms/try', 'wall s/visit', 'tries/visit', 'forms/try'], out)


def out_read(folder):
    print('## OUT tries by generation\n')
    print('`out:tried` of the counts line at a generation\'s end, with the generation\'s forms and `test` seconds from its last prof line. Only generations with a counts line. `age` is the age at its end.\n')
    gens = []
    for a_ in ARMS:
        base = '%s/out/%s' % (folder, a_)
        for task in sorted(os.listdir(base)):
            path = '%s/%s/work/%s.log' % (base, task, task)
            if not os.path.exists(path):
                continue
            cur = None
            for kind, x in B.read_log(path):
                if kind == 'gen':
                    cur = dict(arm=a_, task=task, gen=x[0], forms0=x[2], first=None, last=None, c=None)
                    gens.append(cur)
                elif kind == 'prof' and cur is not None:
                    cur['first'] = cur['first'] or x
                    cur['last'] = x
                elif kind == 'counts' and cur is not None and 'out:tried' in x:
                    cur['c'] = x
    use = [g for g in gens if g['c'] and g['last'] and g['last']['forms'] > g['forms0']]
    out = []
    for kind in KINDS:
        for name, sel in (('generation 0', lambda g: g['gen'] == 0), ('later', lambda g: g['gen'] > 0)):
            x = [g for g in use if B.arm_of(g['arm']) == kind and sel(g)]
            if not x:
                continue
            tried = sum(g['c']['out:tried'] for g in x)
            forms = sum(g['last']['forms'] - g['forms0'] for g in x)
            test = sum(g['last']['test'] for g in x)
            refused = sum(v for g in x for k, v in g['c'].items() if k.startswith('out:refused'))
            stopped = sum(g['c'].get('out:Stopped', 0) for g in x)
            capped = sum(g['c'].get('out:capped', 0) for g in x)
            out.append([kind, name, len(x), '%.0f' % B.med(g['last']['t'] for g in x), tried, forms, '%.1f' % (tried / forms), '%.1f' % (1000 * test / tried), '%.0f' % (1000 * test / forms), refused, stopped, capped])
    B.table(['arm', 'generation', 'generations', 'median age at end s', 'OUT tries', 'forms', 'OUT tries/form', 'test ms/OUT try', 'test ms/form', 'refused', 'Stopped', 'capped'], out)
    print('Between tasks, generation 0 of evict: log of test ms/form on log of OUT tries/form and log of test ms/OUT try: the share of the variance of each.\n')
    x = [g for g in use if B.arm_of(g['arm']) == 'evict' and g['gen'] == 0 and g['last']['t'] > 300]
    pts = [(math.log(1000 * g['last']['test'] / (g['last']['forms'] - g['forms0'])), math.log(g['c']['out:tried'] / (g['last']['forms'] - g['forms0'])), math.log(1000 * g['last']['test'] / g['c']['out:tried']), g['last']['t']) for g in x if g['last']['test'] > 0]
    n = len(pts)
    my = sum(p[0] for p in pts) / n
    syy = sum((p[0] - my) ** 2 for p in pts)
    for i, name in ((1, 'OUT tries/form'), (2, 'test ms/OUT try')):
        mx = sum(p[i] for p in pts) / n
        cov = sum((p[i] - mx) * (p[0] - my) for p in pts)
        print('%s: share %.2f, %d generations.' % (name, cov / syy, n))
    print()
    print('The same generation at two lengths: generations of evict ended by memory before the budget, against those that ran to it, generation 0. test ms/form and OUT tries/form.\n')
    out = []
    for lo, hi in ((0, 200), (200, 400), (400, 520), (520, 700)):
        x = [g for g in use if B.arm_of(g['arm']) == 'evict' and g['gen'] == 0 and lo <= g['last']['t'] < hi]
        if x:
            tried, forms, test = sum(g['c']['out:tried'] for g in x), sum(g['last']['forms'] - g['forms0'] for g in x), sum(g['last']['test'] for g in x)
            out.append(['%d-%d' % (lo, hi), len(x), '%.1f' % (tried / forms), '%.1f' % (1000 * test / tried), '%.0f' % (1000 * test / forms)])
    B.table(['age at end s', 'generations', 'OUT tries/form', 'test ms/OUT try', 'test ms/form'], out)
    return use


def stores_by_kind(rows):
    print('## Stores by kind of try\n')
    print('A fit of a span\'s stores on its counts of tries of each kind, no job term, weighted equally. `new form` stores hold those of its OUT test.\n')
    out = []
    for kind in KINDS:
        for lo, hi in WIDE:
            x = [r for r in wide(rows, kind, lo, hi) if r['stores'] >= 0]
            b, r2 = B.ols([[r['forms'], r['equal'], r['fail']] for r in x], [r['stores'] for r in x])
            out.append([kind, '%d-%d' % (lo, hi), '%.0f' % b[0], '%.0f' % b[1], '%.0f' % b[2], '%.2f' % r2])
    B.table(['arm', 'age s', 'stores/new form', 'stores/equal', 'stores/failed', 'r2'], out)
    print('Fit of `nxt` seconds and of `test` seconds on stores and tries, by age, evict: ms/store and ms/try. It reads whether a store costs more with age.\n')
    out = []
    for kind in KINDS:
        for lo, hi in WIDE:
            x = [r for r in wide(rows, kind, lo, hi) if r['stores'] >= 0]
            b, _ = B.ols([[r['stores'], r['draws']] for r in x], [1000 * (r['nxt'] + r['test']) for r in x])
            c, _ = B.ols([[r['stores'], r['forms'], r['equal'], r['fail']] for r in x], [1000 * r['cpu'] for r in x])
            out.append([kind, '%d-%d' % (lo, hi), '%.2f' % b[0], '%.1f' % b[1], '%.2f' % c[0], '%.0f' % c[1], '%.0f' % c[2], '%.0f' % c[3]])
    B.table(['arm', 'age s', 'nxt + test, ms/store', 'ms/try', 'CPU, ms/store', 'ms/new form', 'ms/equal', 'ms/failed'], out)


def out_by_age(rows, use):
    print('## OUT tries per form by age, from generation totals\n')
    print('`out:tried` of a generation has one count. A fit across generations 0 takes it as forms in each age band x OUT tries per form in that band, with no job term and no intercept. Tasks differ, so read the trend and not one band. `share of forms` is the band\'s forms over all. ms/OUT try is the band\'s `test` s over the fitted OUT tries.\n')
    E = [(0, 60), (60, 120), (120, 240), (240, 360), (360, 660)]
    spans = B.group([r for r in rows if r['gen'] == 0], lambda r: (r['arm'], r['task']))
    out = []
    for name, kinds in (('both', ('both',)), ('evict', ('evict',))):
        X, y, w = [], [], []
        for g in use:
            if g['gen'] != 0 or B.arm_of(g['arm']) not in kinds:
                continue
            x = spans.get((g['arm'], g['task']), [])
            f = [sum(r['forms'] for r in x if lo <= r['age0'] < hi) for lo, hi in E]
            f[0] += g['first']['forms'] - g['forms0']  # forms before the first prof line
            X.append(f)
            y.append(g['c']['out:tried'])
            w.append(1.0)
        b, r2 = B.ols(X, y, w)
        tot = [sum(v[i] for v in X) for i in range(len(E))]
        for i, (lo, hi) in enumerate(E):
            test = sum(r['test'] for g in use if g['gen'] == 0 and B.arm_of(g['arm']) in kinds for r in spans.get((g['arm'], g['task']), []) if lo <= r['age0'] < hi)
            forms = sum(r['forms'] for g in use if g['gen'] == 0 and B.arm_of(g['arm']) in kinds for r in spans.get((g['arm'], g['task']), []) if lo <= r['age0'] < hi)
            out.append([name, '%d-%d' % (lo, hi), len(X), '%.2f' % r2, '%.1f' % b[i], '%.2f' % (tot[i] / sum(tot)), '%.0f' % (1000 * test / max(1, forms)), '%.1f' % (1000 * test / max(1.0, b[i] * forms))])
    B.table(['arm', 'age s', 'generations', 'r2', 'OUT tries/form', 'share of forms', 'test ms/form', 'ms/OUT try'], out)


def sizes(rows):
    print('## What a store adds, and the parts per visit\n')
    print('Rise of the cache\'s bytes and index bytes over the rise of its entries in a band, and relations per store. Bytes per store are the size of what an evaluation makes.\n')
    out = []
    for kind in KINDS:
        for lo, hi in WIDE:
            x = [r for r in wide(rows, kind, lo, hi)]
            ok = [r for r in x if r['stores'] > 0]
            st = sum(r['stores'] for r in ok)
            db = sum(r['d_bytes'] for r in ok)
            di = sum(r['d_idx_bytes'] for r in ok)
            dr = sum(r['d_rel'] for r in ok)
            dx = sum(r['d_idx'] for r in ok)
            s = B.sums(x)
            out.append([kind, '%d-%d' % (lo, hi), '%.0f' % (db / st), '%.0f' % (di / st), '%.3f' % (dr / st), '%.3f' % (dx / st), '%.2f' % (1000 * s['nxt'] / s['visits'] / 1000), '%.2f' % (1000 * s['test'] / s['visits'] / 1000), '%.2f' % ((s['take'] - s['test']) / s['visits']), '%.3f' % (s['setup'] / s['visits'])])
    B.table(['arm', 'age s', 'bytes/store', 'index bytes/store', 'relations/store', 'indexes/store', 'nxt s/visit', 'test s/visit', 'take less test s/visit', 'setup s/visit'], out)
    print('A fit of a span\'s `nxt` on tries and visits, by age. Visits end by time as well as by count, so a slow span has more visits per try for that reason alone, and the visit term reads high.\n')
    out = []
    for kind in KINDS:
        for lo, hi in WIDE:
            x = wide(rows, kind, lo, hi)
            b, r2 = B.ols([[r['draws'], r['visits']] for r in x], [1000 * r['nxt'] for r in x])
            out.append([kind, '%d-%d' % (lo, hi), '%.1f' % b[0], '%.0f' % b[1], '%.2f' % r2])
    B.table(['arm', 'age s', 'nxt ms/try', 'nxt ms/visit', 'r2'], out)


def visit_tests(rows, use):
    print('## Is the visit term a cost, or does it follow the cost of a try?\n')
    print('Instrument: forms/try moves tries/visit through the patience rule, and a slow try does not move forms/try. Each row: `nxt` ms/try on visits/try, plain and with visits/try replaced by its fit on forms/try, with each job\'s mean taken off, weighted by tries. If the visit term only followed slow tries, the instrumented slope would fall to about 0.\n')
    out = []
    for kind in KINDS:
        for lo, hi in ((0, 120), (120, 360), (360, 660), (0, 660)):
            sel = [r for r in wide(rows, kind, lo, hi) if r['draws'] >= 10 and r['visits'] > 0]
            w = [r['draws'] for r in sel]
            y = [1000 * r['nxt'] / r['draws'] for r in sel]
            vt = [r['visits'] / r['draws'] for r in sel]
            ft = [r['forms'] / r['draws'] for r in sel]
            X1, y1 = B.within(sel, [[v] for v in vt], y, w)
            b1, r2 = B.ols(X1, y1, w)
            Z, v2 = B.within(sel, [[f] for f in ft], vt, w)
            first, fr2 = B.ols(Z, v2, w)
            pred = [first[0] * z[0] for z in Z]
            b2, _ = B.ols([[p] for p in pred], y1, w)
            out.append([kind, '%d-%d' % (lo, hi), len(sel), '%.0f' % b1[0], '%.2f' % r2, '%.4f' % first[0], '%.2f' % fr2, '%.0f' % b2[0]])
    B.table(['arm', 'age s', 'spans', 'plain slope, ms/visit', 'r2', 'first stage, visits/try per unit of forms/try', 'first stage r2', 'instrumented slope, ms/visit'], out)
    print('Predicted against seen at a renewal. For each renewal in the table below it: before and after, tries/visit, and `nxt` ms/try seen, and predicted by 37 ms/try + 700 ms/visit.\n')
    out = []
    for (a_, task), x in sorted(B.group(arm(rows, 'evict') + arm(rows, 'both'), lambda r: (r['arm'], r['task'])).items()):
        gens = sorted({r['gen'] for r in x})
        for a, b in zip(gens, gens[1:]):
            before = sorted((r for r in x if r['gen'] == a), key=lambda r: r['age0'])[-6:]
            after = sorted((r for r in x if r['gen'] == b and r['age0'] >= 15), key=lambda r: r['age0'])[:6]
            if len(before) < 3 or len(after) < 3 or before[-1]['age1'] < 120:
                continue
            sa, sb = B.sums(before), B.sums(after)
            ta, tb = sa['draws'] / max(1, sa['visits']), sb['draws'] / max(1, sb['visits'])
            out.append((ta, tb, per_try(sa, lambda s: s['nxt']), per_try(sb, lambda s: s['nxt']), 37 + 700 / ta, 37 + 700 / tb))
    m = [B.med(p[i] for p in out) for i in range(6)]
    print('%d renewals, medians: tries/visit %.1f, %.1f; nxt seen %.0f, %.0f; nxt predicted %.0f, %.0f; median fall seen %.0f, predicted %.0f. Correlation of the falls across renewals: %.2f.\n' % (len(out), m[0], m[1], m[2], m[3], m[4], m[5], B.med(p[2] - p[3] for p in out), B.med(p[4] - p[5] for p in out), corr([p[2] - p[3] for p in out], [p[4] - p[5] for p in out])))
    print('Between tasks at one age, evict: `nxt` ms/try against 1,000/(tries/visit).\n')
    out = []
    for lo, hi in ((240, 360), (360, 480), (480, 620)):
        pts = []
        for x in B.group(arm(rows, 'evict'), lambda r: (r['arm'], r['task'])).values():
            y = [r for r in x if lo <= r['age0'] < hi and r['gen'] == 0]
            s = B.sums(y) if y else None
            if s and s['cpu'] >= 30:
                pts.append((1000 * s['visits'] / s['draws'], per_try(s, lambda v: v['nxt'])))
        b, _ = B.ols([[p[0], 1.0] for p in pts], [p[1] for p in pts])
        out.append(['%d-%d' % (lo, hi), len(pts), '%.0f' % (b[0] * 1000), '%.0f' % b[1], '%.2f' % corr([p[0] for p in pts], [p[1] for p in pts])])
    B.table(['age s', 'jobs', 'slope, ms/visit', 'intercept, ms/try', 'corr'], out)
    print('OUT tries per form in two bands, from generation totals: forms made at age 0-120 s and at 120 s and over, a fit with no job term and no intercept.\n')
    spans = B.group([r for r in rows if r['gen'] == 0], lambda r: (r['arm'], r['task']))
    out = []
    for kind in KINDS:
        X, y, tests = [], [], [0.0, 0.0]
        for g in use:
            if g['gen'] == 0 and B.arm_of(g['arm']) == kind:
                x = spans.get((g['arm'], g['task']), [])
                f = [sum(r['forms'] for r in x if r['age0'] < 120) + g['first']['forms'] - g['forms0'], sum(r['forms'] for r in x if r['age0'] >= 120)]
                X.append(f)
                y.append(g['c']['out:tried'])
                tests[0] += sum(r['test'] for r in x if r['age0'] < 120) + g['first']['test']
                tests[1] += sum(r['test'] for r in x if r['age0'] >= 120)
        b, r2 = B.ols(X, y)
        tot = [sum(v[i] for v in X) for i in (0, 1)]
        out.append([kind, len(X), '%.2f' % r2, '%.1f' % b[0], '%.1f' % b[1], '%.0f' % (1000 * tests[0] / tot[0]), '%.0f' % (1000 * tests[1] / tot[1]), '%.1f' % (1000 * tests[0] / (b[0] * tot[0])), '%.1f' % (1000 * tests[1] / (b[1] * tot[1]))])
    B.table(['arm', 'generations', 'r2', 'OUT tries/form, age 0-120 s', 'age 120 s and over', 'test ms/form, age 0-120 s', 'age 120 s and over', 'ms/OUT try, age 0-120 s', 'age 120 s and over'], out)


def new_against_dup(folder):
    print('## `test` on a new form against a dup form, young processes\n')
    print('Run: %s, arms base_s1 and base_s101, the same 37 tasks, 2 seeds, 600 s, wheel c87cf482a with the scan, renewals near age 120 s. A dup form holds a table that an earlier process of the job knew. A fit of a span\'s `test` s, and of its CPU s, on its counts, one row per age band, with no job term and with one, weighted by tries where the job term is on. forms less dup are the new forms. stores/try x R x 45 ns is the scan the patch took off, for size.\n' % os.path.basename(folder.rstrip('/')))
    rows, _ = B.load(folder, ['base_s1', 'base_s101'])
    rows = [r for r in rows if r['draws'] > 0 and r['cpu'] > 0 and r['age0'] < 180 and r['gen'] > 0]
    out = []
    for lo, hi in ((0, 30), (30, 60), (60, 120), (120, 180)):
        x = [r for r in rows if lo <= r['age0'] < hi]
        s = B.sums(x)
        X = [[r['forms'] - r['dup'], r['dup']] for r in x]
        b, _ = B.ols(X, [r['test'] for r in x])
        w = [max(r['draws'], 1) for r in x]
        X2 = [[r['forms'] - r['dup'], r['dup'], 1.0 * r['draws']] for r in x]
        X3, y3 = B.within(x, [[(r['forms'] - r['dup']) / r['draws'], r['dup'] / r['draws']] for r in x], [1000 * r['test'] / r['draws'] for r in x], w)
        c, r2 = B.ols(X3, y3, w)
        d, _ = B.ols(X2, [r['cpu'] for r in x])
        out.append(['%d-%d' % (lo, hi), len(x), '%.0f' % s['cpu'], '%.2f' % (s['dup'] / s['forms']), '%.0f' % (1000 * s['test'] / s['forms']), '%.0f' % (1000 * b[0]), '%.0f' % (1000 * b[1]), '%.0f' % c[0], '%.0f' % c[1], '%.2f' % r2, '%.0f' % (1000 * d[0]), '%.0f' % (1000 * d[1]), '%.0f' % (1000 * d[2]), '%.0f' % (sum(r['stores'] * r['Rm'] for r in x) / s['draws'] * 45e-6), '%.0f' % B.weighted(x, 'Rm')])
    B.table(['age s', 'spans', 'CPU s', 'dup share of forms', 'test ms/form', 'test ms/new form', 'test ms/dup', 'with job term: ms/new form', 'ms/dup', 'r2', 'CPU ms extra/new form', 'CPU ms extra/dup', 'CPU ms/try', 'scan ms/try', 'R'], out)
    print('Generation 1 and later of the run in hand, both and evict together, age 15 s and over: the same fit. These are young processes with the same pools as the old generations 0.\n')


def out_within_task(rows, use):
    print('## OUT tries against the age of the forms, task held\n')
    print('One point per generation 0 with a counts line. x is the forms-weighted mean age of the generation\'s forms, y is OUT tries/form or `test` ms/OUT try. Both have each task\'s mean taken off, over the jobs of that task. Arm is a second term, 1 on evict. Slope is per 100 s of mean age. Mean age differs inside a task because evict reaches more forms late, and by seed.\n')
    spans = B.group([r for r in rows if r['gen'] == 0], lambda r: (r['arm'], r['task']))
    pts = []
    for g in use:
        if g['gen'] != 0:
            continue
        x = spans.get((g['arm'], g['task']), [])
        f = sum(r['forms'] for r in x)
        if f < 100 or g['last']['test'] <= 0:
            continue
        pts.append(dict(arm=g['arm'], task=g['task'], age=sum(r['forms'] * (r['age0'] + r['age1']) / 2 for r in x) / f / 100, evict=1.0 if g['arm'].startswith('evict') else 0.0, o=g['c']['out:tried'] / (g['last']['forms'] - g['forms0']), m=1000 * g['last']['test'] / g['c']['out:tried'], t=1000 * g['last']['test'] / (g['last']['forms'] - g['forms0'])))
    by_task = B.group(pts, lambda p: p['task'])
    pts = [p for x in by_task.values() if len(x) >= 2 for p in x]
    out = []
    for name, key in (('OUT tries/form', 'o'), ('test ms/OUT try', 'm'), ('test ms/form', 't')):
        X, y = [], []
        for x in by_task.values():
            if len(x) < 2:
                continue
            ma, me, my = sum(p['age'] for p in x) / len(x), sum(p['evict'] for p in x) / len(x), sum(p[key] for p in x) / len(x)
            for p in x:
                X.append([p['age'] - ma, p['evict'] - me])
                y.append(p[key] - my)
        b, r2 = B.ols(X, y)
        n = len(y)
        res = [v - b[0] * u[0] - b[1] * u[1] for u, v in zip(X, y)]
        s2 = sum(e * e for e in res) / max(1, n - 2 - sum(1 for x in by_task.values() if len(x) >= 2))  # each task's mean takes one degree of freedom
        sa = sum(u[0] ** 2 for u in X)
        se = sum(u[1] ** 2 for u in X)
        sae = sum(u[0] * u[1] for u in X)
        out.append([name, n, '%.2f' % b[0], '%.2f' % (math.sqrt(s2 * se / (sa * se - sae ** 2))), '%.2f' % b[1], '%.2f' % r2, '%.1f' % (sum(p[key] for p in pts) / len(pts))])
    B.table(['y', 'points', 'slope per 100 s of mean age', 'its standard error', 'evict term', 'r2', 'mean y'], out)
    print('Mean age of forms: %.0f to %.0f s across the points, mean %.0f s.\n' % (100 * min(p['age'] for p in pts), 100 * max(p['age'] for p in pts), 100 * sum(p['age'] for p in pts) / len(pts)))


def hosts(rows, folder):
    print('## By host\n')
    print('From cpu.txt: each pod\'s boot id and its load at the start. All arms of a task sit on one pod.\n')
    host, pod, task_pod, load = {}, None, {}, {}
    with open(folder + '/cpu.txt') as f:
        for line in f:
            if line.startswith('pod '):
                pod = line[4]
            elif line.startswith('boot_id'):
                host[pod] = line.split()[1][:8]
            elif 'load average' in line:
                load[pod] = line.split('load average:')[1].strip()
            elif line.startswith('tasks:'):
                for t in line.split()[1:]:
                    task_pod[t] = pod
    print('Pods: %s\n' % '; '.join('%s host %s load %s, %d tasks' % (p, host[p], load[p], sum(v == p for v in task_pod.values())) for p in sorted(host)))
    out = []
    for h in sorted(set(host.values())):
        for kind in KINDS:
            row = [h, kind]
            for lo, hi in ((0, 60), (240, 360), (480, 660)):
                x = [r for r in wide(rows, kind, lo, hi) if host.get(task_pod.get(r['task'])) == h]
                s = B.sums(x) if x else None
                row += ['%.2f' % (s['draws'] / s['cpu']) if s else '-', '%.0f' % per_try(s, lambda v: v['test']) if s else '-', '%.0f' % per_try(s, lambda v: v['nxt']) if s else '-']
            out.append(row)
    B.table(['host', 'arm', 'proposals/CPU s, age 0-60 s', 'test', 'nxt', 'age 240-360 s', 'test', 'nxt', 'age 480-660 s', 'test', 'nxt'], out)


def extras(rows, folder):
    print('## Other checks\n')
    bound = 2888 * .65 / 2 * 2 ** 20
    margin = bound - bound / 16
    for kind in KINDS:
        x = arm(rows, kind)
        top = max(x, key=lambda r: r['cache_bytes'] + r['cache_idx_bytes'])
        near = [r for r in x if r['cache_bytes'] + r['cache_idx_bytes'] >= margin]
        print('%s: largest cache plus index %.0f MiB on %s %s at age %.0f s; bound %.0f, margin %.0f; spans at or over the margin %d of %d, jobs %d, CPU s %.0f.' % (kind, (top['cache_bytes'] + top['cache_idx_bytes']) / 2 ** 20, top['arm'], top['task'], top['age1'], bound / 2 ** 20, margin / 2 ** 20, len(near), len(x), len({(r['arm'], r['task']) for r in near}), sum(r['cpu'] for r in near)))
    print()
    print('Rate at the fixed kind costs of the earlier read (ms: new form 137, equal 69, no table 91, failed 379), and CPU s over that cost.\n')
    out = []
    for kind in KINDS:
        for lo, hi in WIDE:
            s = B.sums(wide(rows, kind, lo, hi))
            cost = .137 * s['forms'] + .069 * s['equal'] + .091 * s['notable'] + .379 * s['fail']
            out.append([kind, '%d-%d' % (lo, hi), '%.2f' % (s['draws'] / s['cpu']), '%.2f' % (s['draws'] / cost), '%.2f' % (s['cpu'] / cost)])
    B.table(['arm', 'age s', 'proposals/CPU s', 'at fixed kind costs', 'CPU s over cost'], out)
    for kind in KINDS:
        s = B.sums(arm(rows, kind))
        print('%s, all spans: %.2f proposals/CPU s, %.1f CPU ms/try, %.1f tries/visit, %.2f forms/try, test %.1f, nxt %.1f, setup %.1f, take less test %.1f, gc %.1f ms/try.' % (kind, s['draws'] / s['cpu'], 1000 * s['cpu'] / s['draws'], s['draws'] / s['visits'], s['forms'] / s['draws'], 1000 * s['test'] / s['draws'], 1000 * s['nxt'] / s['draws'], 1000 * s['setup'] / s['draws'], 1000 * (s['take'] - s['test']) / s['draws'], 1000 * s['gc'] / s['draws']))
    print()
    print('Digests seconds and Manager counts on evict, read from prof lines.\n')
    tot = collections.defaultdict(lambda: [0.0, 0, 0, 0])
    for a_ in ('evict_s1', 'evict_s101'):
        base = '%s/out/%s' % (folder, a_)
        for task in sorted(os.listdir(base)):
            prev = None
            for kind, x in B.read_log('%s/%s/work/%s.log' % (base, task, task)):
                if kind == 'gen':
                    prev = None
                elif kind == 'prof':
                    if prev is not None and x['draws'] > prev['draws']:
                        for i, (lo, hi) in enumerate(WIDE):
                            if lo <= prev['t'] < hi:
                                u = tot[i]
                                u[0] += x.get('dig_s', 0) - prev.get('dig_s', 0)
                                u[1] += x['draws'] - prev['draws']
                                u[2] += sum(x['mgr'].values()) - sum(prev['mgr'].values())
                                u[3] += x['visits'] - prev['visits']
                    prev = x
    B.table(['age s', 'digests ms/try', 'Manager counts/visit'], [['%d-%d' % WIDE[i], '%.2f' % (1000 * tot[i][0] / tot[i][1]), '%.2f' % (tot[i][2] / tot[i][3])] for i in sorted(tot)])
    print('Tasks for the probe: tasks with no second generation span in any of the four jobs, each of which reached age 540 s. evict_s1, young is age under 120 s, old is age 360 s and over.\n')
    out = []
    for t, x in sorted(B.group(rows, lambda r: r['task']).items()):
        if not any(r['gen'] > 0 for r in x) and all(max((r['age1'] for r in x if r['arm'] == a_), default=0) >= 540 for a_ in ARMS):
            e = [r for r in x if r['arm'] == 'evict_s1']
            sy, so = B.sums([r for r in e if r['age0'] < 120]), B.sums([r for r in e if r['age0'] >= 360])
            out.append([1000 * so['test'] / max(1, so['forms']), t, '%.0f' % (1000 * sy['test'] / max(1, sy['forms'])), '%.0f' % per_try(sy, CPU), '%.0f' % per_try(so, CPU), max(r['rss'] for r in e)])
    B.table(['test ms/form old', 'task', 'test ms/form young', 'CPU ms/try young', 'old', 'largest RSS'], [['%.0f' % v[0]] + v[1:] for v in sorted(out)])


def dup_here(rows):
    out = []
    for kind in KINDS:
        x = [r for r in arm(rows, kind) if r['gen'] > 0 and r['age0'] >= 15]
        if len(x) < 20:
            continue
        s = B.sums(x)
        b, _ = B.ols([[r['forms'] - r['dup'], r['dup']] for r in x], [r['test'] for r in x])
        out.append([kind, len(x), '%.0f' % s['cpu'], '%.2f' % (s['dup'] / s['forms']), '%.0f' % (1000 * s['test'] / s['forms']), '%.0f' % (1000 * b[0]), '%.0f' % (1000 * b[1]), '%.0f' % B.weighted(x, 'pool_forms')])
    B.table(['arm', 'spans', 'CPU s', 'dup share of forms', 'test ms/form', 'test ms/new form', 'test ms/dup', 'pool forms'], out)


def corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


def young_on_grown(rows):
    print('## A young process on a grown pool, evict\n')
    print('One task, one seed, one band of pool forms. `young` is generation 1 and later, `old` is generation 0 at age 240 s and over. 15 CPU s or more on each side. Medians over pairs. In a young process, tables that an old one held as equal come in as new forms, so forms/try differs.\n')
    out = []
    for kind in KINDS:
        for lo, hi in ((500, 900), (900, 1200), (1200, 1600), (1600, 3000)):
            ps = []
            for t in sorted({r['task'] for r in rows}):
                for seed in ('_s1', '_s101'):
                    a = [r for r in rows if r['arm'] == kind + seed and r['task'] == t and r['gen'] > 0 and r['age0'] >= 15 and lo <= r['pool_forms'] < hi]
                    b = [r for r in rows if r['arm'] == kind + seed and r['task'] == t and r['gen'] == 0 and r['age0'] >= 240 and lo <= r['pool_forms'] < hi]
                    if sum(r['cpu'] for r in a) >= 15 and sum(r['cpu'] for r in b) >= 15:
                        sa, sb = B.sums(a), B.sums(b)
                        ps.append([per_try(sa, CPU), per_try(sb, CPU), per_try(sa, lambda s: s['nxt']), per_try(sb, lambda s: s['nxt']), per_try(sa, lambda s: s['test']), per_try(sb, lambda s: s['test']), 1000 * sa['test'] / max(1, sa['forms']), 1000 * sb['test'] / max(1, sb['forms']), sa['forms'] / sa['draws'], sb['forms'] / sb['draws'], sa['stores'] / sa['draws'], sb['stores'] / sb['draws'], 1000 * sa['setup'] / max(1, sa['visits']), 1000 * sb['setup'] / max(1, sb['visits']), B.weighted(a, 'Rm'), B.weighted(b, 'Rm')])
            if ps:
                row = [kind, '%d-%d' % (lo, hi), len(ps)]
                for i, f in zip(range(0, 16, 2), ('%.0f', '%.0f', '%.0f', '%.0f', '%.2f', '%.0f', '%.0f', '%.0f')):
                    row.append((f + ', ' + f) % (B.med(p[i] for p in ps), B.med(p[i + 1] for p in ps)))
                out.append(row)
    B.table(['arm', 'pool forms', 'pairs', 'CPU ms/try young, old', 'nxt', 'test', 'test ms/form', 'forms/try', 'stores/try', 'setup ms/visit', 'R'], out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--out', default='', help='a file for the tables, in place of standard output')
    ap.add_argument('--also', default='', help='a run folder with base_s1 and base_s101, for the table of new forms against dup forms')
    a = ap.parse_args()
    if a.out:
        sys.stdout = open(a.out, 'w')
    rows = [r for r in load(a.run) if r['draws'] > 0 and r['cpu'] > 0]
    print('jobs %d, spans %d\n' % (len({(r['arm'], r['task']) for r in rows}), len(rows)))
    visits(rows)
    use = out_read(a.run)
    stores_by_kind(rows)
    sizes(rows)
    visit_tests(rows, use)
    out_within_task(rows, use)
    hosts(rows, a.run)
    extras(rows, a.run)
    if a.also:
        new_against_dup(a.also)
        dup_here(rows)
    young_on_grown(rows)
    age_tables(rows)
    split(rows)
    by_r(rows)
    paired(rows)
    kinds_table(rows)
    test_split(rows)
    shape(rows)
    within_tables(rows)
    slope_tables(rows)
    renewals(rows)


if __name__ == '__main__':
    main()
