#!/usr/bin/env python3
"""Tables of the OUT tries probe, from the prof lines of its jobs.

    python3 search_out_tries_probe_report.py OUT_FOLDER [--arm probe_s1]

OUT_FOLDER is the kit's `out` folder (or a copy of it): out/<arm>/<task>/work/<task>.log. The report reads partial output: a worker that the
supervisor killed at its deadline prints no end line, so everything here comes from the prof lines, which print every 10 s. A last line that
was cut off is skipped. Python's standard library is enough to run it.

Words. A span is the time between two prof lines of one process (a generation). Process age is `t` of the prof line that opens a span.
A prof line gives counts of its process so far (`x`), and the engine calls and ms of its own span (`eng`), so a span's counts are the
difference of two lines, and the first span of a process starts at zero. An OUT try is one count of `out:tried`: a clause that reached the
decoder's `finish`. The cap `OUT_CANDS` counts clauses (`out:counted`, the sum of `out:try LABEL`), and that includes clauses refused before `finish`.
OUT tries of a label are its `out:try` less its `out:refused`, `out:fault` and `out:no relation`, which differs a little from `out:tried` itself.
A form is a form that `try_clause` kept and gave to the OUT search (`out:forms 0..4`, summed). A visit is one (scope, kind) search of `superdag_search.visit`.
`ms/OUT try` is `test` wall ms over OUT tries, and `test` holds the OUT search's whole cost for a form, so it counts the decoder's work
between tries too.
"""
import argparse
import collections
import glob
import json
import os
import re
import statistics

BANDS = [(0, 60), (60, 120), (120, 240), (240, 360), (360, 480), (480, 660)]
YOUNG = (30, 120)  # the age band that the prediction compares against
OLD = 480
LAYERS = ('overlay paint', 'paint over2', 'frame fill')  # the labels of Run.layers; the others come from Run.cands
ENGINE = ('py.step', 'py.admits', 'py.fork', 'py.forced', 'decode.next', 'decode.with_checks', 'decode.completes', 'det.liveness', 'table.walk', 'table.sub_body', 'eval.domain', 'check.program', 'resolve.last')
ENDS = ('deadline', 'seconds', 'patience', 'exhausted')
CAPS = (25, 50, 75, 100)


def read_log(path):
    """The prof lines of a log as dicts, with the generation lines' numbers. A line that does not parse is skipped."""
    out = []
    with open(path, errors='replace') as f:
        for line in f:
            if line.startswith('prof '):
                try:
                    out.append(json.loads(line[5:]))
                except ValueError:
                    pass  # a line that the kill cut
    return out


def find_logs(folder, arm):
    pat = re.compile(r'out/([^/]+)/([^/]+)/work/[^/]+\.log$')
    found = []
    for path in sorted(glob.glob('%s/out/*/*/work/*.log' % folder) + glob.glob('%s/*/*/work/*.log' % folder)):
        m = pat.search(path) or re.search(r'([^/]+)/([^/]+)/work/[^/]+\.log$', path)
        if m and (arm is None or m[1] == arm):
            found.append((m[1], m[2], path))
    return found


def spans(lines):
    """Spans of one log: dicts with the age at the start, and the differences of the cumulative counts."""
    out, prev = [], None
    for x in lines:
        if prev is not None and x.get('gen') == prev.get('gen') and x['t'] > prev['t']:
            d = lambda k: x.get(k, 0) - prev.get(k, 0)  # noqa: E731
            px, cx = prev.get('x', {}), x.get('x', {})
            dx = collections.Counter({k: v - px.get(k, 0) for k, v in cx.items() if v - px.get(k, 0)})
            out.append(dict(age=prev['t'], gen=x['gen'], wall=d('t'), cpu=d('cpu'), draws=d('draws'), visits=d('visits'), setup=d('setup'), nxt=d('nxt'), take=d('take'),
                            test=d('test'), forms=d('forms'), x=dx, eng=x.get('eng', {})))
        elif prev is None or x.get('gen') != prev.get('gen'):
            # first span of a process: from zero, with the process' own age
            out.append(dict(age=0.0, gen=x.get('gen'), wall=x['t'], cpu=x.get('cpu', 0), draws=x.get('draws', 0), visits=x.get('visits', 0), setup=x.get('setup', 0), nxt=x.get('nxt', 0),
                            take=x.get('take', 0), test=x.get('test', 0), forms=x.get('forms', 0), x=collections.Counter(x.get('x', {})), eng=x.get('eng', {})))
        prev = x
    return out


def tested(s):
    return sum(s['x'].get('out:forms %d' % b, 0) for b in range(5))


def band_of(age):
    for i, (lo, hi) in enumerate(BANDS):
        if lo <= age < hi:
            return i
    return len(BANDS) - 1 if age >= BANDS[-1][1] else 0


def total(rows, key):
    return sum(r['x'].get(key, 0) for r in rows)


def table(head, rows):
    print('| ' + ' | '.join(head) + ' |')
    print('| ' + ' | '.join('---' for _ in head) + ' |')
    for r in rows:
        print('| ' + ' | '.join(str(x) for x in r) + ' |')
    print()


def f1(x, n=1):
    return '-' if x is None else ('%.' + str(n) + 'f') % x


def ratio(a, b):
    return None if a is None or not b else a / b


def lab_tried(g, k):
    return sum(total(g, p + k) * sg for p, sg in (('out:try ', 1), ('out:refused ', -1), ('out:fault ', -1), ('out:no relation ', -1)))


def labels(rows):
    c = collections.Counter()
    for r in rows:
        for k, v in r['x'].items():
            if k.startswith('out:try '):
                c[k[8:]] += v
    return [k for k, _ in c.most_common()]


def pooled(rows, lo, hi):
    return [r for r in rows if lo <= r['age'] < hi]


def stat(rows):
    """Pooled figures of the spans in rows."""
    forms = sum(tested(r) for r in rows)
    tries = total(rows, 'out:tried')
    test = sum(r['test'] for r in rows)
    draws = sum(r['draws'] for r in rows)
    visits = total(rows, 'search:visits')
    cpu = sum(r['cpu'] for r in rows)
    fn = total(rows, 'search:first next new') + total(rows, 'search:first next resume')
    return dict(forms=forms, tries=tries, test=test, draws=draws, visits=visits, cpu=cpu, tf=ratio(tries, forms), ms_try=None if not tries else 1000 * test / tries,
                fn=fn, fn_ms=None if not fn else 1000 * total(rows, 'search:seconds first next') / fn)


def corr(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx, syy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sxx * syy) ** 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--arm', default=None, help='only this arm, as in out/<arm>/')
    a = ap.parse_args()
    jobs = {}
    for arm, task, path in find_logs(a.folder, a.arm):
        lines = read_log(path)
        jobs[arm, task] = (spans(lines), len(lines))
    if not jobs:
        print('no log under %s' % a.folder)
        return
    rows = [dict(r, arm=k[0], task=k[1]) for k, (sp, _) in jobs.items() for r in sp]
    print('# OUT tries probe\n')
    print('Jobs: %d. Spans: %d. Prof lines: %d. Newest age per job: %s.\n' % (len(jobs), len(rows), sum(n for _, n in jobs.values()),
                                                                       ', '.join('%s %.0f' % (k[1], sp[-1]['age'] + sp[-1]['wall']) for k, (sp, _) in sorted(jobs.items()) if sp)))
    has = sum(1 for r in rows if 'out:tried' in r['x'])
    print('Spans with an OUT count: %d of %d. Without one, the worker is not the probe kit.\n' % (has, len(rows)))
    gens = collections.Counter(r['gen'] for r in rows)
    print('Spans by generation: %s. A job with a second generation had a renewal, and its later spans are young processes on a grown pool.\n' % dict(sorted(gens.items())))

    labs = labels(rows)

    print('## OUT tries per form by age and label\n')
    print('Pooled over the jobs. Cells are OUT tries of the label over forms that reached the OUT search, in that age band. `layers` is the sum of %s. `all` is `out:tried`.\n' % ', '.join(LAYERS))
    out = []
    for lo, hi in BANDS:
        g = pooled(rows, lo, hi)
        s = stat(g)
        if not s['forms']:
            out.append(['%d-%d' % (lo, hi), len(g), 0] + ['-'] * (len(labs) + 2))
            continue
        out.append(['%d-%d' % (lo, hi), len(g), s['forms']] + [f1(lab_tried(g, k) / s['forms'], 2) for k in labs]
                   + [f1(sum(lab_tried(g, k) for k in LAYERS) / s['forms'], 2), f1(s['tf'], 2)])
    table(['age s', 'spans', 'forms'] + labs + ['layers', 'all (out:tried)'], out)

    print('Share of each label in the OUT tries of the band:\n')
    out = []
    for lo, hi in BANDS:
        g = pooled(rows, lo, hi)
        t = sum(lab_tried(g, k) for k in labs)
        out.append(['%d-%d' % (lo, hi)] + [f1(100 * lab_tried(g, k) / t, 1) + '%' if t else '-' for k in labs])
    table(['age s'] + labs, out)

    print('Clauses counted toward the cap per form (`out:counted`), and the share of them that were refused before `finish`:\n')
    out = []
    for lo, hi in BANDS:
        g = pooled(rows, lo, hi)
        s = stat(g)
        c = total(g, 'out:counted')
        ref = sum(total(g, 'out:refused ' + k) for k in labs)
        out.append(['%d-%d' % (lo, hi), f1(ratio(c, s['forms']), 2), (f1(100 * ref / c, 0) + '%') if c else '-', total(g, 'out:capped'), (f1(100 * total(g, 'out:capped') / s['forms'], 1) + '%') if s['forms'] else '-'])
    table(['age s', 'clauses counted/form', 'refused', 'out:capped', 'capped per form'], out)

    print('## ms per OUT try by age\n')
    print('`test` wall ms over OUT tries, pooled, and over clauses counted toward the cap. Also `test` ms per proposal and proposals per CPU s, for the overhead check against `evict_s1` on the same tasks (within 5% at age 0-120 s).\n')
    out = []
    for lo, hi in BANDS + [YOUNG, (OLD, 10 ** 9)]:
        g = pooled(rows, lo, hi)
        s = stat(g)
        out.append(['%d-%d' % (lo, hi) if hi < 10 ** 9 else '%d+' % lo, len(g), s['tries'], f1(s['ms_try'], 2), f1(ratio(1000 * s['test'], total(g, 'out:counted')), 2), f1(1000 * s['test'] / s['draws'] if s['draws'] else None, 1), f1(s['draws'] / s['cpu'] if s['cpu'] else None, 2)])
    table(['age s', 'spans', 'OUT tries', 'test ms/OUT try', 'test ms/clause counted', 'test ms/proposal', 'proposals/CPU s'], out)
    print('Per job, young (age %d-%d s) against old (age %d s and over). Only jobs with %d OUT tries or more in each band.\n' % (YOUNG[0], YOUNG[1], OLD, 200))
    out, per = [], []
    for (arm, task), (sp, _) in sorted(jobs.items()):
        y, o = stat(pooled(sp, *YOUNG)), stat(pooled(sp, OLD, 10 ** 9))
        if y['tries'] >= 200 and o['tries'] >= 200:
            per.append((y, o))
            out.append([arm, task, f1(y['tf'], 1), f1(o['tf'], 1), f1(y['ms_try'], 1), f1(o['ms_try'], 1), f1(o['ms_try'] / y['ms_try'], 2)])
    table(['arm', 'task', 'tries/form young', 'old', 'ms/OUT try young', 'old', 'ms ratio'], out)
    if per:
        print('Median over %d jobs: OUT tries/form %.1f to %.1f, ms/OUT try %.1f to %.1f, ratio %.2f.\n' % (len(per), statistics.median(p[0]['tf'] for p in per), statistics.median(p[1]['tf'] for p in per),
                                                                                                       statistics.median(p[0]['ms_try'] for p in per), statistics.median(p[1]['ms_try'] for p in per),
                                                                                                       statistics.median(p[1]['ms_try'] / p[0]['ms_try'] for p in per)))

    print('## Clauses by form size, and what a cap cuts\n')
    print('Forms by the clauses that the cap counts for them (`out:counted`), in bins of 25 (bin 4 is 100 and over), pooled over all spans. A cap of C = 25k cuts, from each form in bin k or above, its clauses above C, so the cut is exact from the bin sums. The cut is of counted clauses, and a refused clause costs less than an OUT try.\n')
    out = []
    for b in range(5):
        fb, ib = total(rows, 'out:cforms %d' % b), total(rows, 'out:cin %d' % b)
        out.append(['%d-%d' % (25 * b, 25 * b + 24) if b < 4 else '100+', fb, ib, f1(ratio(ib, fb), 1)])
    table(['clauses counted for a form', 'forms', 'clauses', 'mean'], out)
    out = []
    for lo, hi in [(0, 10 ** 9)] + BANDS:
        g = pooled(rows, lo, hi)
        allt = sum(total(g, 'out:cin %d' % b) for b in range(5))
        row = ['all' if hi == 10 ** 9 else '%d-%d' % (lo, hi), allt]
        for c in CAPS:
            k = c // 25
            cut = sum(total(g, 'out:cin %d' % b) - c * total(g, 'out:cforms %d' % b) for b in range(k, 5))
            row.append(f1(100 * cut / allt, 1) + '%' if allt else '-')
        out.append(row)
    table(['age s', 'clauses in forms'] + ['share cut at cap %d' % c for c in CAPS], out)
    print('A cap of 100 is the current `OUT_CANDS`, so it cuts nothing here; bin 4 holds the forms that reached it, and `out:capped` counts the searches that stopped there.\n')
    print('The same bins of `out:tried` per form (the OUT tries of a form, bin 4 is 100 and over):\n')
    out = []
    for b in range(5):
        fb, ib = total(rows, 'out:forms %d' % b), total(rows, 'out:in %d' % b)
        out.append(['%d-%d' % (25 * b, 25 * b + 24) if b < 4 else '100+', fb, ib, f1(ratio(ib, fb), 1)])
    table(['OUT tries of a form', 'forms', 'OUT tries', 'mean'], out)

    print('## Partners and forms in a scope, by age\n')
    out = []
    for lo, hi in BANDS:
        g = pooled(rows, lo, hi)
        n, v = total(g, 'out:searched'), total(g, 'search:visits')
        out.append(['%d-%d' % (lo, hi), n, f1(ratio(total(g, 'out:colors'), n), 1), f1(ratio(total(g, 'out:grids'), n), 1), f1(ratio(total(g, 'out:positions'), n), 1),
                    v, f1(ratio(total(g, 'search:scope forms'), v), 2), f1(ratio(total(g, 'out:tried'), tested_sum(g)), 2)])
    table(['age s', 'OUT searches', 'colors', 'grids', 'positions', 'visits', 'forms in scope per visit', 'OUT tries/form'], out)
    print('Colors, grids and positions are the partner lists at the start of an OUT search, per search.\n')
    print('Within one age band, between jobs: correlation of OUT tries/form with forms in scope per visit.\n')
    out = []
    for lo, hi in BANDS:
        xs, ys = [], []
        for (arm, task), (sp, _) in jobs.items():
            g = pooled(sp, lo, hi)
            s = stat(g)
            fs = ratio(total(g, 'search:scope forms'), total(g, 'search:visits'))
            if s['forms'] >= 20 and fs is not None:
                xs.append(fs)
                ys.append(s['tf'])
        c = corr(xs, ys)
        out.append(['%d-%d' % (lo, hi), len(xs), f1(c, 2)])
    table(['age s', 'jobs', 'correlation'], out)

    print('## Visits\n')
    print('`search:end X` over `search:visits`. A visit counted in `search:visits` and cut by the worker\'s kill has no end, so `open` is visits less ends.\n')
    out = []
    for lo, hi in BANDS:
        g = pooled(rows, lo, hi)
        v = total(g, 'search:visits')
        e = [total(g, 'search:end ' + k) for k in ENDS]
        out.append(['%d-%d' % (lo, hi), v] + [e_ for e_ in e] + [v - sum(e)] + [f1(ratio(sum(r['draws'] for r in g), v), 1), f1(ratio(sum(r['nxt'] for r in g), v), 2), f1(ratio(sum(r['test'] for r in g), v), 2),
                                                                         f1(ratio(sum(r['setup'] for r in g), v), 3)])
    table(['age s', 'visits'] + list(ENDS) + ['open', 'tries/visit', 'nxt s/visit', 'test s/visit', 'setup s/visit'], out)

    print('A visit\'s first `next`. `new` is a slot with no earlier visit, `resume` one with an earlier visit. A visit that ends before its first clause is not counted.\n')
    out = []
    for lo, hi in BANDS:
        g = pooled(rows, lo, hi)
        row = ['%d-%d' % (lo, hi)]
        for k in ('new', 'resume'):
            n = total(g, 'search:first next ' + k)
            row += [n, f1(1000 * total(g, 'search:seconds first next ' + k) / n if n else None, 0)]
        n = total(g, 'search:first next new') + total(g, 'search:first next resume')
        row += [f1(1000 * total(g, 'search:seconds first next') / n if n else None, 0)]
        out.append(row)
    table(['age s', 'new visits', 'new ms', 'resume visits', 'resume ms', 'all ms'], out)

    print('## Saves and the scope replay\n')
    out = []
    for lo, hi in BANDS:
        g = pooled(rows, lo, hi)
        d = sum(r['draws'] for r in g)
        v = total(g, 'search:visits')
        out.append(['%d-%d' % (lo, hi), total(g, 'search.saves'), f1(ratio(1000 * total(g, 'search.save seconds'), d), 2), f1(ratio(total(g, 'search.saves'), v), 2),
                    f1(ratio(1000 * total(g, 'sr:scope_seconds'), d), 2), f1(ratio(1000 * total(g, 'sr:scope_seconds'), v), 0)])
    table(['age s', 'saves', 'save ms/try', 'saves/visit', 'scope replay ms/try', 'scope replay ms/visit'], out)
    print('`sr:scope_seconds` is the replay in `Run` of the Runs that the searches hold.\n')

    print('## Engine calls and ns per call by age\n')
    print('From `eng` of each prof line (calls and ms of its own span, whole ms, so a phase under 1 ms a span reads low). Needs a probe run that collected the engine statistics (`arclog.engine_stats(collect=True)`). ns per call is pooled ms over pooled calls.\n')
    out = []
    for name in ENGINE:
        row = [name]
        for lo, hi in BANDS:
            g = pooled(rows, lo, hi)
            calls = sum(r['eng'].get(name, [0, 0])[0] for r in g)
            ms = sum(r['eng'].get(name, [0, 0])[1] for r in g)
            d = sum(r['draws'] for r in g)
            row.append('%s / %s' % (f1(calls / d if d else None, 0), f1(1e6 * ms / calls if calls else None, 0)))
        out.append(row)
    table(['phase (calls per try / ns per call)'] + ['%d-%d' % b for b in BANDS], out)
    others = collections.Counter()
    for r in rows:
        for k, v in r['eng'].items():
            if k not in ENGINE:
                others[k] += v[1]
    if others:
        print('Other phases, total ms: %s.\n' % ', '.join('%s %d' % kv for kv in others.most_common(8)))

    verdicts(rows, jobs, labs)


def tested_sum(g):
    return sum(tested(r) for r in g)


def verdicts(rows, jobs, labs):
    print('## What the read says decides\n')
    y, o = stat(pooled(rows, *YOUNG)), stat(pooled(rows, OLD, 10 ** 9))
    y0, y1 = stat(pooled(rows, 0, 60)), o
    lines = []
    if y['tries'] < 200 or o['tries'] < 200:
        print('Not enough spans: %d OUT tries at age %d-%d s and %d at age %d s and over. Each needs 200. The bands below read as partial.\n' % (y['tries'], YOUNG[0], YOUNG[1], o['tries'], OLD))

    # 1. ms/OUT try
    r1 = ratio(o['ms_try'], y['ms_try'])
    ok = r1 is not None and r1 <= 1.3 and 8 <= o['ms_try'] <= 13
    lines.append(('ms/OUT try at age %d s and up within 1.3 times its value at %d-%d s, in 8 to 13 ms' % (OLD, *YOUNG), '%s to %s ms, ratio %s' % (f1(y['ms_try']), f1(o['ms_try']), f1(r1, 2)), None if r1 is None else ('held' if ok else 'missed')))
    # 2. tries/form
    ok = y0['tf'] is not None and o['tf'] is not None and 4 <= y0['tf'] <= 8 and 15 <= o['tf'] <= 24
    lines.append(('OUT tries/form 4 to 8 at age 0-60 s, 15 to 24 at age %d s and up' % OLD, '%s then %s' % (f1(y0['tf']), f1(o['tf'])), None if o['tf'] is None or y0['tf'] is None else ('held' if ok else 'missed')))
    # 3. layers share of added tries
    ya, oa = pooled(rows, 0, 60), pooled(rows, OLD, 10 ** 9)
    added = None
    if ya and oa and stat(ya)['forms'] and stat(oa)['forms']:
        lay = lambda g: sum(lab_tried(g, k) for k in LAYERS) / stat(g)['forms']  # noqa: E731
        allk = lambda g: sum(lab_tried(g, k) for k in labs) / stat(g)['forms']  # noqa: E731
        added = ratio(lay(oa) - lay(ya), allk(oa) - allk(ya))
    lines.append(('more than half of the added OUT tries carry layers labels', 'layers share of the rise: %s' % (f1(None if added is None else 100 * added, 0) + '%' if added is not None else '-'), None if added is None else ('held' if added > 0.5 else 'missed')))
    # 4. forms in a scope
    fs = lambda g: ratio(total(g, 'search:scope forms'), total(g, 'search:visits'))  # noqa: E731
    a, b = fs(ya), fs(oa)
    lines.append(('forms in a scope double or more from age 0-60 s to %d s and up' % OLD, '%s then %s, ratio %s' % (f1(a, 2), f1(b, 2), f1(ratio(b, a) if a and b else None, 2)), None if not a or not b else ('held' if b >= 2 * a else 'missed')))
    # 5. first next
    bands = {i: pooled(rows, *BANDS[i]) for i in range(len(BANDS))}
    fns = []
    for i in range(len(BANDS)):
        g = bands[i]
        n = total(g, 'search:first next new') + total(g, 'search:first next resume')
        fns.append(None if n < 5 else 1000 * total(g, 'search:seconds first next') / n)
    late = [v for v, (lo, _) in zip(fns, BANDS) if lo >= 120 and v is not None]
    allv = [v for v in fns if v is not None]
    ok5 = bool(allv) and all(150 <= v <= 450 for v in allv) and (not late or max(late) <= 1.25 * min(late))
    lines.append(('a visit\'s first next takes 150 to 450 ms at every age, within 25% from age 120 s on', 'by band: %s ms' % ', '.join(f1(v, 0) for v in fns), None if not allv else ('held' if ok5 else 'missed')))
    # 6. saves
    sv = []
    for g in bands.values():
        d = sum(r['draws'] for r in g)
        sv.append(None if d < 50 else 1000 * total(g, 'search.save seconds') / d)
    vv = [v for v in sv if v is not None]
    lines.append(('saves take under 3 ms/try at every age', 'by band: %s ms/try' % ', '.join(f1(v, 2) for v in sv), None if not vv else ('held' if max(vv) < 3 else 'missed')))
    # 7. engine ns per call
    res = []
    for name in ('py.step', 'py.admits', 'py.fork'):
        ns = []
        for i, (lo, _) in enumerate(BANDS):
            if lo < 120:
                continue
            calls = sum(r['eng'].get(name, [0, 0])[0] for r in bands[i])
            ms = sum(r['eng'].get(name, [0, 0])[1] for r in bands[i])
            ns.append(1e6 * ms / calls if calls >= 1000 else None)
        v = [x for x in ns if x]
        res.append((name, v))
    rise = [ratio(v[-1], v[0]) for _, v in res if len(v) >= 2]
    lines.append(('ns per call of py.step, py.admits and py.fork rise by under 25% from age 120 s on', '; '.join('%s %s' % (n, '->'.join(f1(x, 0) for x in v) or '-') for n, v in res), None if not rise else ('held' if all(r_ < 1.25 for r_ in rise) else 'missed')))
    partial = y['tries'] < 200 or o['tries'] < 200
    table(['prediction', 'seen', 'verdict'], [[x[0], x[1], ('partial, ' if partial else '') + x[2]] if x[2] else [x[0], x[1], 'no data'] for x in lines])

    print('Which candidate the counts name, by the read\'s own rules:\n')
    pick = []
    if r1 is not None and r1 > 2:
        pick.append('ms/OUT try more than doubles (%s): the read is wrong about `test`. The engine counter of `cache::lookup` and `cache::store` comes next.' % f1(r1, 2))
    elif r1 is not None and r1 <= 1.3 and o['tf'] and y0['tf'] and o['tf'] > 1.5 * y0['tf']:
        pick.append('rank 1, more OUT tries per form: ms/OUT try is flat (ratio %s) and OUT tries per form rise (%s to %s). A lower `OUT_CANDS` is the fix to test. The cap comes from the table of clauses by form size above.' % (f1(r1, 2), f1(y0['tf']), f1(o['tf'])))
    elif r1 is not None and r1 > 1.3:
        pick.append('ms/OUT try rises by %s times, between 1.3 and 2: some of the rise is per call. Read the engine ns per call; if those are flat, the cost is in rank 6, and the engine counter comes next.' % f1(r1, 2))
    elif r1 is not None:
        pick.append('ms/OUT try is flat (ratio %s) and OUT tries per form do not rise much (%s to %s): rank 1 has no support here.' % (f1(r1, 2), f1(y0['tf']), f1(o['tf'])))
    if added is not None:
        pick.append('Added OUT tries: %s%% carry layers labels. %s' % (f1(100 * added, 0), 'The layers come after all other clauses, so a lower cap cuts them first.' if added > 0.5 else 'Most of the rise is in the other clause families, so a lower cap cuts some of them too.'))
    if allv:
        pick.append('First next: %s ms by band. %s' % (', '.join(f1(v, 0) for v in fns), 'Inside 150 to 450 ms at every age, so the start cost of a visit (rank 2) stays below the plain 700 ms; its size is the first next plus `setup` per visit.' if ok5 else 'Outside the predicted 150 to 450 ms or not flat from age 120 s: rank 2 is open. Split new from resume in the table above, and compare with the replay in `sr:scope_seconds`.'))
    if vv:
        pick.append('Saves: at most %s ms/try, %s the 3 ms bar, so rank 4 %s on saves.' % (f1(max(vv), 2), 'under' if max(vv) < 3 else 'over', 'has no room' if max(vv) < 3 else 'is open'))
    if not pick:
        pick.append('No count yet.')
    for p in pick:
        print('- ' + p)
    print()


if __name__ == '__main__':
    main()
