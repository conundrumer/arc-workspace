#!/usr/bin/env python3
"""Each arm of the memory fixes against `base`, per task, from the `prof` lines of worker logs and the cover files. It reads partial output: a task counts once it has a prof line, and a ratio needs both arms.

  python3 search_memory_fixes_report.py OUT_DIR [--points FILE]

OUT_DIR holds <arm>/<task>/work/*.log and *.cover. FILE is the kit's points-eval.json, by default the one in OUT_DIR's parent. Without it, the gold columns are empty.

Columns of the task table:
  proposals, cpu s   the last prof line's draws, and CPU seconds summed over the worker's processes
  prop/cpu           proposals per CPU second
  renew              `generation N` lines past 0, up to the wall time that both arms reached
  max rss            the greatest RSS that any line of the log gives, MiB
  F                  the smaller of the two arms' last form counts
  rss@F              RSS at the first prof line with F forms or more
  MiB/form           RSS grown per form up to F: the rises of RSS between lines of one process, so it doesn't depend on when a renewal cut RSS, over F
  P                  the smaller of the two arms' last proposal counts
  forms@P            forms at P proposals, read between the two prof lines around P
  net@P              forms@P less the dup count at P, so a form that came back doesn't count twice
  gold@P             distinct gold forms covered by P proposals, and of those the non-DET ones
  dup                forms that came back after their keys went, a running count that stays across a renewal (superdag_search.Digests). Keys go at a renewal, and at each ARC_KEYS_RESET_SECONDS
  same               forms whose digests all matched while the keys were there: the digest is coarser than the key on these, so same / forms estimates the false share of dup
  no table           node:no table over all processes: a try that gave no table, which is what a session bound's stall makes
  given-up           runs that no Search keeps and that are alive, at the last prof line
  dig s              wall seconds of the digests over all processes
x base is the arm over base. Each summary row gives, over the tasks with both arms, the median of the task ratios and the ratio of the sums.
"""
import glob
import json
import os
import re
import statistics
import sys

GENERATION = re.compile(r'generation (\d+): rss (\d+) after load')
TIMES = re.compile(r'rss (\d+) at (\d+) s of (\d+), cpu')
JUMP = re.compile(r'rss (\d+) from ')
END = re.compile(r'end: .*, (\d+) MiB, ')


def read_task(folder):
    """{rows, gens, peak} of one arm on one task, or None where it has no prof line. A row is a prof line with the sums over processes: cpu_all, notable_all, grown, el (wall seconds of the job)."""
    rows, gens, peak, total = [], [], 0, None
    cpu_last = cpu_done = notable_last = notable_done = grown = rss_before = 0
    for path in sorted(glob.glob(folder + '/work/*.log')):
        for line in open(path, errors='replace'):
            if line.startswith('generation '):
                m = GENERATION.match(line)
                if m:
                    gens.append([int(m[1]), None])
                    notable_done, notable_last = notable_done + notable_last, 0
                    rss_before = int(m[2])
                    peak = max(peak, rss_before)
            elif line.startswith('prof '):
                try:
                    r = json.loads(line[5:])
                except ValueError:
                    continue
                if r['cpu'] < cpu_last:  # a new process: an execv keeps the CPU clock, and a new worker starts it again
                    cpu_done += cpu_last
                cpu_last, notable_last = r['cpu'], r['notable']
                grown += max(r['rss'] - rss_before, 0)
                rss_before = r['rss']
                peak = max(peak, r['rss'])
                r.update(cpu_all=cpu_done + cpu_last, notable_all=notable_done + notable_last, grown=grown, el=rows[-1]['el'] if rows else 0)
                rows.append(r)
            elif line.startswith('rss '):
                m = TIMES.match(line)
                if m:
                    total = total or int(m[3])
                    el = total - (int(m[3]) - int(m[2]))
                    if rows:
                        rows[-1]['el'] = el
                    for g in gens:  # a generation under PROGRESS_SECONDS long prints no such line, so it takes the next one's time
                        if g[1] is None:
                            g[1] = el
                    peak = max(peak, int(m[1]))
                else:
                    m = JUMP.match(line)
                    peak = max(peak, int(m[1])) if m else peak
            elif line.startswith('end: '):
                m = END.match(line)
                peak = max(peak, int(m[1])) if m else peak
    if not rows:
        return None
    for g in gens:  # a last generation with no line of time yet
        if g[1] is None:
            g[1] = rows[-1]['el']
    return dict(rows=rows, gens=gens, peak=peak)


def covers(folder):
    """{gold form index: the first draw that covered it}."""
    found = {}
    for path in glob.glob(folder + '/work/*.cover'):
        for line in open(path, errors='replace'):
            try:
                e = json.loads(line)
                found[e['gold']] = min(e['draw'], found.get(e['gold'], e['draw']))
            except (ValueError, KeyError, TypeError):
                continue
    return found


def between(rows, by, at, field):
    """rows' field where rows' `by` reaches at, read along the line between the two rows around it."""
    low = None
    for r in rows:
        if r[by] >= at:
            if low is None or r[by] == low[by]:
                return r.get(field, 0)
            a, b = low.get(field, 0), r.get(field, 0)
            return a + (b - a) * (at - low[by]) / (r[by] - low[by])
        low = r
    return low.get(field, 0) if low else 0


def renewals(gens, cut):
    return sum(g > 0 and t is not None and t <= cut for g, t in gens)


def rate(d):
    last = d['rows'][-1]
    return last['draws'] / last['cpu_all'] if last['cpu_all'] else None


def compare(a, b, ka, kb):
    """The numbers of arm a at the cuts it shares with arm b. ka and kb are their cover dicts."""
    ra, rb = a['rows'], b['rows']
    cut = min(ra[-1]['el'], rb[-1]['el'])
    forms = min(ra[-1]['forms'], rb[-1]['forms'])
    draws = min(ra[-1]['draws'], rb[-1]['draws'])
    at_f = next((r for r in ra if r['forms'] >= forms), ra[-1])
    out = dict(renew=renewals(a['gens'], cut), F=forms, rss_f=at_f['rss'], per_form=between(ra, 'forms', forms, 'grown') / max(forms, 1), P=draws, forms=between(ra, 'draws', draws, 'forms'),
               gold=[g for g, d in ka.items() if d <= draws])
    out['net'] = out['forms'] - between(ra, 'draws', draws, 'dup')
    return out


def cell(x, form='%.0f'):
    return '-' if x is None else form % x


def ratio(x, y):
    return x / y if x is not None and y else None


def summary(rows):
    """(median of the task ratios, ratio of the sums) of [(arm's value, base's value)], counting pairs with a base above 0 in the median."""
    rows = [(x, y) for x, y in rows if x is not None and y is not None]
    each = [x / y for x, y in rows if y]
    return (statistics.median(each) if each else None), ratio(sum(x for x, _ in rows), sum(y for _, y in rows)), len(each)


def main():
    args = sys.argv[1:]
    points = None
    if '--points' in args:
        i = args.index('--points')
        points = args[i + 1]
        del args[i:i + 2]
    out = args[0].rstrip('/')
    points = points or os.path.join(os.path.dirname(os.path.abspath(out)), 'points-eval.json')
    kinds = {x['task']: [y.split()[0].lstrip('(') for y in x['gold_sexp'].strip().split('\n') if not y.startswith('(OUT')] for x in json.load(open(points))} if os.path.exists(points) else None
    arms = [a for a in sorted(os.listdir(out), key=lambda a: (a != 'base', a)) if os.path.isdir(out + '/' + a)]
    data, cov = {}, {}
    for arm in arms:
        for t in sorted(os.listdir(out + '/' + arm)):
            d = read_task('%s/%s/%s' % (out, arm, t))
            if d:
                data[arm, t] = d
                cov[arm, t] = covers('%s/%s/%s' % (out, arm, t))
    tasks = sorted({t for _, t in data})
    print('| task | arm | gen | proposals | cpu s | prop/cpu | x base | renew | base | max rss | x base | F | rss@F | MiB/form | x base | P | forms@P | base | net@P | base | gold@P | non-DET | base | dup | base | same | no table | base | given-up | dig s |')
    print('|' + ' --- |' * 30)
    pairs = {}
    for t in tasks:
        base = data.get(('base', t))
        for arm in arms:
            d = data.get((arm, t))
            if not d:
                continue
            last = d['rows'][-1]
            c = compare(d, base, cov[arm, t], cov['base', t]) if base else None
            b = compare(base, d, cov['base', t], cov[arm, t]) if base else None
            non_det = lambda found: None if kinds is None or t not in kinds else sum(kinds[t][g] != 'DET' for g in found)
            print('| %s |' % ' | '.join((
                t, arm, str(d['gens'][-1][0] if d['gens'] else 0), str(last['draws']), cell(last['cpu_all']), cell(rate(d), '%.2f'), cell(ratio(rate(d), rate(base)) if base else None, '%.3f'),
                cell(c and c['renew']), cell(b and b['renew']), str(d['peak']), cell(ratio(d['peak'], base['peak']) if base else None, '%.3f'),
                cell(c and c['F']), cell(c and c['rss_f']), cell(c and c['per_form'], '%.2f'), cell(ratio(c['per_form'], b['per_form']) if base else None, '%.3f'),
                cell(c and c['P']), cell(c and c['forms'], '%.1f'), cell(b and b['forms'], '%.1f'), cell(c and c['net'], '%.1f'), cell(b and b['net'], '%.1f'),
                cell(len(c['gold']) if base else None), cell(non_det(c['gold']) if base else None), cell(len(b['gold']) if base else None),
                cell(last.get('dup')), cell(base['rows'][-1].get('dup') if base else None), cell(last.get('same')),
                cell(last['notable_all']), cell(base['rows'][-1]['notable_all'] if base else None), cell(last.get('given_up')), cell(last.get('dig_s'), '%.2f'))))
            if base and arm != 'base':
                got = pairs.setdefault(arm, {k: [] for k in ('prop/cpu', 'renewals', 'max rss', 'MiB/form', 'forms@P', 'net@P', 'gold@P', 'dup', 'no table')})
                got['prop/cpu'].append((rate(d), rate(base)))
                got['renewals'].append((c['renew'], b['renew']))
                got['max rss'].append((d['peak'], base['peak']))
                got['MiB/form'].append((c['per_form'], b['per_form']))
                got['forms@P'].append((c['forms'], b['forms']))
                got['net@P'].append((c['net'], b['net']))
                got['gold@P'].append((len(c['gold']), len(b['gold'])))
                got['dup'].append((last.get('dup'), base['rows'][-1].get('dup')))
                got['no table'].append((last['notable_all'], base['rows'][-1]['notable_all']))
    print()
    print('| arm | measure | tasks | median of ratios | ratio of sums | arm sum | base sum |')
    print('|' + ' --- |' * 7)
    for arm, got in pairs.items():
        for name, rows in got.items():
            med, whole, n = summary(rows)
            if name == 'prop/cpu':  # the sum over tasks of proposals over the sum of CPU seconds
                last = [(data[arm, t]['rows'][-1], data['base', t]['rows'][-1]) for t in tasks if (arm, t) in data and ('base', t) in data]
                x = sum(r['draws'] for r, _ in last) / max(sum(r['cpu_all'] for r, _ in last), 1e-9)
                y = sum(r['draws'] for _, r in last) / max(sum(r['cpu_all'] for _, r in last), 1e-9)
                print('| %s | %s | %d | %s | %s | %.2f | %.2f |' % (arm, name, n, cell(med, '%.3f'), cell(ratio(x, y), '%.3f'), x, y))
            else:
                print('| %s | %s | %d | %s | %s | %.1f | %.1f |' % (arm, name, n, cell(med, '%.3f'), cell(whole, '%.3f'), sum(x or 0 for x, _ in rows), sum(y or 0 for _, y in rows)))
    if not pairs:
        print('no arm has a base on the same task yet')


main()
