#!/usr/bin/env python3
"""Memory by side, time by side and limit65_freeze against limit65, from one run folder. It reads partial output.

  python3 search_sides_report.py RUN_DIR

RUN_DIR holds out/<arm>/<task>/work/<task>.log, with arms limit65, limit65_freeze and side_profile.

Field behavior across a generation line: t, gc, gcn and visits restart. draws, forms and nodes come from the bank file, and cpu is process CPU time, which execv keeps, so these carry over. The script checks this and prints the count of breaks.

Memory columns, in MiB:
  cache    result cache bytes plus index bytes
  intern   intern table bytes of the session
  memos    probe memo bytes, index bytes and intern bytes, plus table walk memo bytes
  python   pymalloc's Total, which holds blocks of 512 bytes or less
  glibc    malloc_used plus malloc_free: what glibc holds, which includes Python objects over 512 bytes
  rest     RSS less the columns above
The engine allocates with mimalloc, so its counted bytes are outside glibc's numbers, and the columns do not overlap.

Time sides: `side` keeps only the 24 largest sides and `top` only the 40 largest calls. Seconds in `side` that `top` does not list cannot be split by name.
"""
import collections
import json
import os
import re
import statistics
import sys

M = 2 ** 20
TARGETS = (1500, 2500)
FIT_BAND = (1000, 3000)
PROFILE_SECONDS = 300
ARMS = ('limit65', 'limit65_freeze', 'side_profile')
RENEWING = ARMS[:2]
GENERATION = re.compile(r'generation (\d+): rss (\d+) after load, (\d+) forms, (\d+) nodes, (\d+) s')
END = re.compile(r'end: (\w+), (\d+) draws, (\d+) forms, (\d+) nodes, \d+ candidates, (\d+) MiB, (\d+) s')
BANK = re.compile(r'bank file ([\d.]+) MiB')
RSS = re.compile(r'rss (\d+) (?:at|from) ')
COLS = ('rss', 'cache', 'intern', 'memos', 'python', 'glibc', 'rest', 'forms', 'nodes')


def say(*a):
    print(*a, flush=True)


def med(xs):
    return statistics.median(xs) if xs else float('nan')


def load(path):
    r = dict(prof=[], mem=[], profile=None, gens=[], ends=[], banks=[], rss=0)
    for line in open(path, errors='replace'):
        m = RSS.match(line)
        if m:
            r['rss'] = max(r['rss'], int(m[1]))
        m = GENERATION.match(line)
        if m:
            r['gens'].append(dict(rss=int(m[2]), forms=int(m[3]), nodes=int(m[4]), s=int(m[5])))
        m = END.match(line)
        if m:
            r['ends'].append(dict(why=m[1], draws=int(m[2]), forms=int(m[3]), nodes=int(m[4]), rss=int(m[5]), s=int(m[6]), gen=len(r['gens']) - 1))
            r['rss'] = max(r['rss'], int(m[5]))
        m = BANK.match(line)
        if m:
            r['banks'].append(float(m[1]))
        for name in ('prof', 'mem', 'profile'):
            if line.startswith(name + ' '):
                try:
                    x = json.loads(line[len(name) + 1:])
                except ValueError:
                    continue
                x['gen'] = len(r['gens']) - 1
                if name == 'profile':
                    r['profile'] = x
                else:
                    r[name].append(x)
                    r['rss'] = max(r['rss'], x['rss'])
    return r


def sides(m):
    c, (probe, walk) = m['cache'], m['memos']
    s = dict(rss=m['rss'], cache=(c[2] + c[4]) / M, intern=c[5] / M, memos=(probe[0] + probe[2] + probe[3] + walk[0]) / M,
             python=m['py_total'] / M, glibc=(m['malloc_used'] + m['malloc_free']) / M, forms=m['forms'], nodes=m['nodes'], live=m['py_alloc'] / M)
    s['rest'] = s['rss'] - s['cache'] - s['intern'] - s['memos'] - s['python'] - s['glibc']
    return s


def nearest(mems, target):
    return sides(min(mems, key=lambda m: abs(m['rss'] - target)))


def row(name, s):
    say('  %-10s' % name + ''.join('%8.0f' % s[k] for k in COLS))


def head():
    say('  %-10s' % 'task' + ''.join('%8s' % k for k in COLS))


def read_memory(runs):
    tasks = sorted(runs)
    say('# Read 1: memory by side, side_profile, MiB. Each row is the mem line nearest the target RSS.')
    near = {}
    for target in TARGETS:
        say('near %d MiB' % target)
        head()
        near[target] = {t: nearest(runs[t]['mem'], target) for t in tasks}
        for t in tasks:
            row(t, near[target][t])
        row('median', {k: med([near[target][t][k] for t in tasks]) for k in COLS})
    say('growth between those two lines')
    head()
    grow = {t: {k: near[TARGETS[1]][t][k] - near[TARGETS[0]][t][k] for k in COLS} for t in tasks}
    for t in tasks:
        row(t, grow[t])
    row('median', {k: med([grow[t][k] for t in tasks]) for k in COLS})
    say('  sum of growth, share of RSS growth: ' + ', '.join('%s %.0f%%' % (k, 100 * sum(grow[t][k] for t in tasks) / sum(grow[t]['rss'] for t in tasks)) for k in COLS[1:7]))
    say('least squares slope on RSS, all mem lines with RSS in %d to %d MiB, which smooths the probe memo resets' % FIT_BAND)
    pooled = collections.defaultdict(list)
    for t in tasks:
        xs = [sides(m) for m in runs[t]['mem'] if FIT_BAND[0] <= m['rss'] <= FIT_BAND[1]]
        out = {}
        for k in COLS[1:7]:
            mx, my = statistics.mean(x['rss'] for x in xs), statistics.mean(x[k] for x in xs)
            out[k] = sum((x['rss'] - mx) * (x[k] - my) for x in xs) / sum((x['rss'] - mx) ** 2 for x in xs)
            pooled[k].append(out[k])
        say('  %-10s %2d lines: ' % (t, len(xs)) + ', '.join('%s %.2f' % (k, v) for k, v in out.items()))
    say('  median              ' + ', '.join('%s %.2f' % (k, med(v)) for k, v in pooled.items()))
    say('last mem line')
    head()
    for t in tasks:
        row(t, sides(runs[t]['mem'][-1]))
    say('python live bytes (pymalloc allocated blocks) at the lines above, MiB: ' + ', '.join('%s %.0f, %.0f, %.0f' % (t, near[1500][t]['live'], near[2500][t]['live'], sides(runs[t]['mem'][-1])['live']) for t in tasks))
    say('probe memo bytes over the run, MiB: ' + ', '.join('%s %.0f to %.0f' % (t, min(m['memos'][0][0] for m in runs[t]['mem']) / M, max(m['memos'][0][0] for m in runs[t]['mem']) / M) for t in tasks))
    say('rest against memos, changes between neighboring mem lines; a correlation near -1 means rest rises as memos fall:')
    for t in tasks:
        xs = [sides(m) for m in runs[t]['mem']]
        dm, dr = [b['memos'] - a['memos'] for a, b in zip(xs, xs[1:])], [b['rest'] - a['rest'] for a, b in zip(xs, xs[1:])]
        say('  %-10s correlation %.2f; memos plus rest at the near-1500, near-2500 and last lines: %.0f, %.0f, %.0f' % (t, statistics.correlation(dm, dr), near[1500][t]['memos'] + near[1500][t]['rest'], near[2500][t]['memos'] + near[2500][t]['rest'], xs[-1]['memos'] + xs[-1]['rest']))
    say('largest fall in python live bytes between two mem lines, MiB: ' + ', '.join('%s %.0f' % (t, max(0, *[(a['py_alloc'] - b['py_alloc']) / M for a, b in zip(runs[t]['mem'], runs[t]['mem'][1:])])) for t in tasks))
    say('search objects, median of the first and second half of the mem lines:')
    for t in tasks:
        mems = runs[t]['mem']
        half = len(mems) // 2
        say('  %-10s ' % t + ', '.join('%s %.0f, %.0f' % (k, med([m[k] for m in mems[:half]]), med([m[k] for m in mems[half:]])) for k in ('searches', 'hot', 'heap', 'emitted', 'seen', 'memo', 'shared', 'slots')))
    say()


def read_tracking(runs):
    say('# Does growth track forms and nodes?')
    say('side_profile, steps of about 10 s between prof lines:')
    for t, r in sorted(runs['side_profile'].items()):
        steps = list(zip(r['prof'], r['prof'][1:]))
        flat = [b['rss'] - a['rss'] for a, b in steps if b['forms'] == a['forms'] and b['nodes'] == a['nodes']]
        say('  %-10s %d steps, %d with forms and nodes both flat; forms and nodes never fall: %s' % (t, len(steps), len(flat), all(b['forms'] >= a['forms'] and b['nodes'] >= a['nodes'] for a, b in steps)))
    say('side_profile, RSS growth per new form and per new node, MiB:')
    for t, r in sorted(runs['side_profile'].items()):
        marks = [sides(r['mem'][0]), nearest(r['mem'], 1500), nearest(r['mem'], 2500), sides(r['mem'][-1])]
        parts = []
        for a, b in zip(marks, marks[1:]):
            parts.append('%.0f to %.0f: %.1f, %.1f' % (a['rss'], b['rss'], (b['rss'] - a['rss']) / max(b['forms'] - a['forms'], 1), (b['rss'] - a['rss']) / max(b['nodes'] - a['nodes'], 1)))
        say('  %-10s ' % t + '; '.join(parts))
    say('renewing arms: for each generation that ended by memory, RSS growth per new form and per new proposal; medians for generation 0 and for later ones; then the last load')
    for arm in RENEWING:
        for t, r in sorted(runs[arm].items()):
            ends = {e['gen']: e for e in r['ends']}
            first, later = [], []
            for g, e in ends.items():
                if e['why'] != 'memory':
                    continue
                draws0 = ends[g - 1]['draws'] if g else 0
                x = ((e['rss'] - r['gens'][g]['rss']) / max(e['forms'] - r['gens'][g]['forms'], 1), (e['rss'] - r['gens'][g]['rss']) / max(e['draws'] - draws0, 1))
                (later if g else first).append(x)
            g = r['gens'][-1]
            say('  %-15s %-10s generation 0: %.1f, %.1f; later: %.1f, %.1f over %d; last load %d forms, %d nodes at RSS %d; first load RSS %d; largest bank file %.1f MiB' % (
                arm, t, med([x[0] for x in first]), med([x[1] for x in first]), med([x[0] for x in later]), med([x[1] for x in later]), len(later), g['forms'], g['nodes'], g['rss'], r['gens'][0]['rss'], max(r['banks'] or [0])))
    say()


def prof_at(prof, seconds):
    return min(prof, key=lambda p: abs(p['t'] - seconds))


def cpu_at(prof, draws):
    """The CPU seconds at a proposal count, by a straight line between two prof lines."""
    for a, b in zip(prof, prof[1:]):
        if a['draws'] <= draws <= b['draws'] and b['draws'] > a['draws']:
            return a['cpu'] + (b['cpu'] - a['cpu']) * (draws - a['draws']) / (b['draws'] - a['draws'])
    return None


def profile_shares(r):
    p, load_s = r['profile'], r['gens'][0]['s']
    side, top = p['side'], p['top']
    py = sum(v for k, v in side.items() if k.startswith('py:'))
    listed = side['engine'] + side['c'] + py
    named = [x for x in top if x[2] == 'engine']
    builtin = sum(x[0] for x in named if 'builtins.' in x[3])
    arclog = sum(x[0] for x in named if 'arclog' in x[3])
    unseen = side['engine'] - builtin - arclog
    elapsed = PROFILE_SECONDS - load_s
    tail = elapsed - listed
    return dict(listed=listed, elapsed=elapsed, tail=tail, logged_engine=side['engine'], logged_c=side['c'], logged_py=py, builtin=builtin, arclog=arclog, unseen=unseen,
                engine_low=arclog, engine_high=arclog + unseen, c_low=side['c'] + builtin, c_high=side['c'] + builtin + unseen, nonpy=side['engine'] + side['c'], py=py + tail)


def read_time(runs):
    side_runs = runs['side_profile']
    tasks = sorted(side_runs)
    say('# Read 2: time by side, side_profile, seconds under cProfile over the first %d s' % PROFILE_SECONDS)
    shares = {t: profile_shares(side_runs[t]) for t in tasks}
    say('as logged, share of the seconds listed in `side`')
    say('  %-10s %8s %8s %8s %8s %8s' % ('task', 'listed', 'engine', 'c', 'python', 'ceiling'))
    logged = []
    for t in tasks:
        s = shares[t]
        u = s['listed']
        logged.append(dict(e=s['logged_engine'] / u, c=s['logged_c'] / u, p=s['logged_py'] / u, ceil=u / s['nonpy']))
        say('  %-10s %8.1f %7.1f%% %7.1f%% %7.1f%% %8.2f' % (t, u, 100 * logged[-1]['e'], 100 * logged[-1]['c'], 100 * logged[-1]['p'], logged[-1]['ceil']))
    say('  %-10s %8s %7.1f%% %7.1f%% %7.1f%% %8.2f' % ('median', '', 100 * med([x['e'] for x in logged]), 100 * med([x['c'] for x in logged]), 100 * med([x['p'] for x in logged]), med([x['ceil'] for x in logged])))
    say('classification check: calls the rule put on the engine side, seconds from `top`; unseen is engine seconds that `top` does not list')
    say('  %-10s %8s %8s %8s  of which builtins' % ('task', 'arclog', 'builtins', 'unseen'))
    for t in tasks:
        s = shares[t]
        names = {x[3].split('builtins.')[1].rstrip('>'): x[0] for x in side_runs[t]['profile']['top'] if x[2] == 'engine' and 'builtins.' in x[3]}
        say('  %-10s %8.1f %8.1f %8.1f  %s' % (t, s['arclog'], s['builtin'], s['unseen'], names))
    say('  elapsed profile seconds less the seconds in `side`: ' + ', '.join('%s %.1f of %.0f' % (t, shares[t]['tail'], shares[t]['elapsed']) for t in tasks) + '. The smallest listed side has %.2f s or less, and engine and c are both listed, so these seconds belong to smaller Python files.' % max(min(side_runs[t]['profile']['side'].values()) for t in tasks))
    say('corrected, share of elapsed profile seconds: builtins moved from engine to other C, seconds outside `side` added to Python; engine and c are ranges because the unseen seconds cannot be split')
    say('  %-10s %8s %14s %14s %8s %8s %8s' % ('task', 'elapsed', 'engine', 'c', 'python', '1/nonpy', '1/engine'))
    fixed = []
    for t in tasks:
        s = shares[t]
        u = s['elapsed']
        x = dict(lo=s['engine_low'] / u, hi=s['engine_high'] / u, clo=s['c_low'] / u, chi=s['c_high'] / u, p=s['py'] / u, ceil=u / s['nonpy'], ceil_e=u / s['engine_high'])
        fixed.append(x)
        say('  %-10s %8.1f %6.1f-%5.1f%% %6.1f-%5.1f%% %7.1f%% %8.2f %8.2f' % (t, u, 100 * x['lo'], 100 * x['hi'], 100 * x['clo'], 100 * x['chi'], 100 * x['p'], x['ceil'], x['ceil_e']))
    m = {k: med([x[k] for x in fixed]) for k in fixed[0]}
    say('  %-10s %8s %6.1f-%5.1f%% %6.1f-%5.1f%% %7.1f%% %8.2f %8.2f' % ('median', '', 100 * m['lo'], 100 * m['hi'], 100 * m['clo'], 100 * m['chi'], 100 * m['p'], m['ceil'], m['ceil_e']))
    say('the arclog calls in `top`, seconds:')
    for t in tasks:
        say('  %-10s ' % t + ', '.join('%s %.1f' % (x[3].replace("<method '", '').replace("' of 'arclog.", ' ').replace(' objects>', '').replace("'", '').replace('<built-in method arclog.arclog.', '').rstrip('>'), x[0]) for x in side_runs[t]['profile']['top'] if 'arclog' in x[3]))
    say('top 10 Python items by seconds, summed over the tasks. Calls of one name in one file are told apart by their order in each task, since `top` drops the line number. Each task lists only its 40 largest calls.')
    items, calls = collections.Counter(), collections.Counter()
    by_task = collections.defaultdict(dict)
    for t in tasks:
        seen = collections.Counter()
        for x in sorted(side_runs[t]['profile']['top'], reverse=True):
            if x[2].startswith('py:'):
                key = (x[2][3:], x[3], seen[(x[2], x[3])])
                seen[(x[2], x[3])] += 1
                items[key] += x[0]
                calls[key] += x[1]
                by_task[key][t] = x[0]
    all_py = sum(shares[t]['py'] for t in tasks)
    say('  %-20s %-22s %8s %8s  %s' % ('file', 'name', 'seconds', 'calls', ' '.join('%8s' % t for t in tasks)))
    for key, v in items.most_common(10):
        say('  %-20s %-22s %8.1f %7.2fM  %s' % (key[0], key[1] + ('' if not key[2] else ' #%d' % (key[2] + 1)), v, calls[key] / 1e6, ' '.join('%8.1f' % by_task[key].get(t, float('nan')) for t in tasks)))
    top_sum = sum(v for _, v in items.most_common(10))
    say('  top 10 sum %.1f s, %.0f%% of %.1f Python seconds' % (top_sum, 100 * top_sum / all_py, all_py))
    say('calls in `top`, millions, by side: ' + ', '.join('%s %s' % (t, {k: round(sum(x[1] for x in side_runs[t]['profile']['top'] if (x[2][:2] == 'py' and k == 'py') or x[2] == k) / 1e6) for k in ('engine', 'c', 'py')}) for t in tasks))
    say('cost of cProfile: two rough estimates of the slowdown factor k')
    ks = {}
    for t in tasks:
        prof = side_runs[t]['prof']
        marks = []
        for arm in RENEWING:
            base = [p for p in runs[arm][t]['prof'] if p['gen'] == 0]
            d = min(base[-1]['draws'], prof[-1]['draws'])
            a, b = cpu_at(prof, d), cpu_at(base, d)
            if a and b:
                marks.append((d, a / b))
        p0, p1, p2 = prof_at(prof, PROFILE_SECONDS - 150), prof_at(prof, PROFILE_SECONDS), prof_at(prof, PROFILE_SECONDS + 150)
        before = (p1['draws'] - p0['draws']) / (p1['cpu'] - p0['cpu'])
        after = (p2['draws'] - p1['draws']) / (p2['cpu'] - p1['cpu'])
        ks[t] = (med([x[1] for x in marks]), after / before)
        say('  %-10s CPU s to the same proposal count in generation 0, over limit65 and over limit65_freeze: %s; proposals per CPU s 150 s before and after the profile end: %.2f, %.2f, ratio %.2f' % (t, ', '.join('%.2f at %d' % (x[1], x[0]) for x in marks), before, after, after / before))
    k_a, k_b = med([v[0] for v in ks.values()]), med([v[1] for v in ks.values()])
    say('  medians: %.2f and %.2f' % (k_a, k_b))
    for k in sorted((k_a, k_b)):
        say('  at k %.2f, with all of the cost taken from the Python side, medians: engine share %.1f%%, python share %.1f%%, 1/nonpy %.2f, 1/engine %.2f' % (
            k, 100 * med([s['engine_high'] * k / s['elapsed'] for s in shares.values()]), 100 * med([1 - s['nonpy'] * k / s['elapsed'] for s in shares.values()]), med([s['elapsed'] / k / s['nonpy'] for s in shares.values()]), med([s['elapsed'] / k / s['engine_high'] for s in shares.values()])))
    say()


def run_totals(r):
    """Whole-run and within-generation numbers from the prof lines."""
    prof = r['prof']
    gens = sorted({p['gen'] for p in prof})
    last = {g: [p for p in prof if p['gen'] == g][-1] for g in gens}
    first = {g: [p for p in prof if p['gen'] == g][0] for g in gens}
    inside_d = sum(last[g]['draws'] - first[g]['draws'] for g in gens)
    inside_c = sum(last[g]['cpu'] - first[g]['cpu'] for g in gens)
    ends = {e['gen']: e for e in r['ends']}
    earlier, restarts, breaks = 0, 0, 0
    for a, b in zip(prof, prof[1:]):
        if b['gen'] == a['gen']:
            continue
        if b['cpu'] < a['cpu']:  # a worker that exits with under MIN_RENEW_SECONDS left is followed by a new process, whose CPU time starts at 0
            earlier += a['cpu'] + ends[a['gen']]['s'] - a['t']
            restarts += 1
        breaks += not (b['draws'] >= a['draws'] and b['forms'] >= a['forms'] and b['nodes'] >= a['nodes'] and b['t'] < a['t'])
    wall, gc = sum(last[g]['t'] for g in gens), sum(last[g]['gc'] for g in gens)
    cpu = earlier + prof[-1]['cpu']
    return dict(draws=prof[-1]['draws'], cpu=cpu, wall=wall, gc=gc, gcn=sum(last[g]['gcn'] for g in gens), renewals=len(r['gens']) - 1 - restarts, restarts=restarts, rss=r['rss'], rate=prof[-1]['draws'] / cpu,
                inside=inside_d / inside_c, inside_d=inside_d, inside_c=inside_c, share=gc / wall, breaks=breaks)


def read_freeze(runs):
    tasks = sorted(set(runs['limit65']) & set(runs['limit65_freeze']))
    a = {t: run_totals(runs['limit65'][t]) for t in tasks}
    b = {t: run_totals(runs['limit65_freeze'][t]) for t in tasks}
    say('# Read 3: limit65_freeze against limit65, paired by task')
    say('proposals per CPU s is the last prof line, draws over cpu. inside is the same ratio from within-generation differences only. GC % is GC seconds over wall seconds, each summed over generations.')
    say('field breaks at a generation line (draws, forms or nodes that fall, or t that does not restart): limit65 %d, limit65_freeze %d' % (sum(x['breaks'] for x in a.values()), sum(x['breaks'] for x in b.values())))
    say('generation lines where cpu restarts, because a new process follows a worker that exited with under 30 s left; these are not counted as renewals, and the CPU seconds of both processes are summed: limit65 %d, limit65_freeze %d' % (sum(x['restarts'] for x in a.values()), sum(x['restarts'] for x in b.values())))
    say('  %-10s %7s %7s %7s %7s %6s %6s %5s %5s %7s %7s' % ('task', 'rate', 'rate-f', 'ratio', 'inside', 'gc%', 'gc%-f', 'ren', 'ren-f', 'maxrss', 'mrss-f'))
    for t in tasks:
        x, y = a[t], b[t]
        say('  %-10s %7.2f %7.2f %7.3f %7.3f %6.2f %6.2f %5d %5d %7d %7d' % (t, x['rate'], y['rate'], y['rate'] / x['rate'], y['inside'] / x['inside'], 100 * x['share'], 100 * y['share'], x['renewals'], y['renewals'], x['rss'], y['rss']))
    ratio = [b[t]['rate'] / a[t]['rate'] for t in tasks]
    say('  %-10s %7.2f %7.2f %7.3f %7.3f %6.2f %6.2f %5.1f %5.1f %7.0f %7.0f' % ('median', med([a[t]['rate'] for t in tasks]), med([b[t]['rate'] for t in tasks]), med(ratio), med([b[t]['inside'] / a[t]['inside'] for t in tasks]),
                                                                              100 * med([a[t]['share'] for t in tasks]), 100 * med([b[t]['share'] for t in tasks]), med([a[t]['renewals'] for t in tasks]), med([b[t]['renewals'] for t in tasks]), med([a[t]['rss'] for t in tasks]), med([b[t]['rss'] for t in tasks])))
    total = lambda d, k: sum(d[t][k] for t in tasks)
    sa, sb = total(a, 'draws') / total(a, 'cpu'), total(b, 'draws') / total(b, 'cpu')
    ia, ib = total(a, 'inside_d') / total(a, 'inside_c'), total(b, 'inside_d') / total(b, 'inside_c')
    ga, gb = total(a, 'gc') / total(a, 'wall'), total(b, 'gc') / total(b, 'wall')
    say('  %-10s %7.2f %7.2f %7.3f %7.3f %6.2f %6.2f %5d %5d' % ('sum', sa, sb, sb / sa, (ib / ia), 100 * ga, 100 * gb, total(a, 'renewals'), total(b, 'renewals')))
    say('  tasks where freeze has more proposals per CPU s: %d of %d; ratio range %.3f to %.3f' % (sum(x > 1 for x in ratio), len(ratio), min(ratio), max(ratio)))
    say('  proposals, CPU s, GC s, GC passes: limit65 %d, %.0f, %.1f, %d; limit65_freeze %d, %.0f, %.1f, %d' % (total(a, 'draws'), total(a, 'cpu'), total(a, 'gc'), total(a, 'gcn'), total(b, 'draws'), total(b, 'cpu'), total(b, 'gc'), total(b, 'gcn')))
    say('  GC seconds per pass: limit65 %.3f, limit65_freeze %.3f' % (total(a, 'gc') / total(a, 'gcn'), total(b, 'gc') / total(b, 'gcn')))
    say('# Residue: GC share of wall in limit65: median %.2f%%, pooled %.2f%%, largest task %.2f%%' % (100 * med([a[t]['share'] for t in tasks]), 100 * ga, 100 * max(a[t]['share'] for t in tasks)))
    say()


def read_no_renewal(runs):
    say('# side_profile after the profile ended, no renewal: proposals per CPU s from %d s to the last prof line, its RSS range and GC share, then the whole run of each renewing arm on that task' % (PROFILE_SECONDS + 10))
    for t, r in sorted(runs['side_profile'].items()):
        tail = [p for p in r['prof'] if p['t'] >= PROFILE_SECONDS + 10]
        a, b = tail[0], tail[-1]
        say('  %-10s %.2f at RSS %d to %d, GC %.2f%%; limit65 %.2f, limit65_freeze %.2f' % (t, (b['draws'] - a['draws']) / (b['cpu'] - a['cpu']), a['rss'], b['rss'], 100 * (b['gc'] - a['gc']) / (b['t'] - a['t']), run_totals(runs['limit65'][t])['rate'], run_totals(runs['limit65_freeze'][t])['rate']))
    say()


def read_supervisor(run_dir):
    say('# End of each worker, from supervisor.log')
    for arm in ARMS:
        kills, deaths = 0, 0
        path = os.path.join(run_dir, 'out', arm)
        tasks = sorted(os.listdir(path)) if os.path.isdir(path) else []
        for t in tasks:
            for line in open(os.path.join(path, t, 'supervisor.log'), errors='replace'):
                m = re.search(r'submission written; deaths (\d+) kills (\d+)', line)
                if m:
                    deaths += int(m[1])
                    kills += int(m[2])
        say('  %-15s %d tasks, deaths %d, kills %d' % (arm, len(tasks), deaths, kills))
    say()


def main():
    run_dir = sys.argv[1]
    runs = {}
    for arm in ARMS:
        runs[arm] = {}
        path = os.path.join(run_dir, 'out', arm)
        for t in sorted(os.listdir(path)) if os.path.isdir(path) else []:
            log = os.path.join(path, t, 'work', t + '.log')
            if os.path.exists(log):
                runs[arm][t] = load(log)
    with open(os.path.join(run_dir, 'manifest.json')) as f:
        manifest = json.load(f)
    with open(os.path.join(run_dir, 'cpu.txt'), errors='replace') as f:
        machine = f.readline().strip()
    say('run %s: %s, %s; %s' % (os.path.basename(run_dir.rstrip('/')), manifest['task_set'], manifest['budget'], machine))
    say()
    read_memory(runs['side_profile'])
    read_tracking(runs)
    read_time(runs)
    read_freeze(runs)
    read_no_renewal(runs)
    read_supervisor(run_dir)


if __name__ == '__main__':
    main()
