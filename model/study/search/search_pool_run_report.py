#!/usr/bin/env python3
"""A run of run14.sh (jobs 14 and 16) by the chain and its memory and disk, from a copy of the kit's out/ folder. It reads partial output.

  python3 job14_report.py OUT_DIR POINTS.json [--at 60 300 600 1800 3600]

OUT_DIR holds <arm>/<task>/ with start, disk.txt, supervisor.log and work/. Covers come from work/*.cover, with the first time of each gold form across a task's generations.
Forms are non-OUT lines of gold, non-DET and DET apart, by dependency depth band. Tasks count where both arms have a start file and the cover check read gold.
"""
import argparse
import collections
import glob
import json
import os
import re
import statistics
import time

NAME = re.compile(r'&[A-Za-z_0-9]+')
BANDS = (1, 1, '1'), (2, 3, '2-3'), (4, 6, '4-6'), (7, 10 ** 6, '7+')


def gold_forms(sexp):
    lines = [x for x in sexp.strip().split('\n') if not x.startswith('(OUT')]
    kinds = [x.split()[0].lstrip('(') for x in lines]
    heads = {}
    for i, x in enumerate(lines):
        m = NAME.search(x)
        if m:
            heads.setdefault(m[0], i)
    depth = []
    for i, x in enumerate(lines):
        depth.append(1 + max((depth[heads[n]] for n in set(NAME.findall(x)) if n in heads and heads[n] < i), default=0))
    return kinds, depth


def band(d):
    return next(name for a, b, name in BANDS if a <= d <= b)


def load(folder, outs):
    task = os.path.basename(folder)
    r = dict(task=task, covers={}, cands=0, right=0, attempts=[], rss=0.0, deaths=0, generations=0, samples=0, trimmed=0, shed=0, disk_kb=0, files=0, renewals=0)
    try:
        r['start'] = float(open(folder + '/start').read())
    except (OSError, ValueError):
        return None
    for path in glob.glob(folder + '/work/*.cover'):
        for line in open(path):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            t = e['time'] - r['start']
            if e['gold'] not in r['covers'] or t < r['covers'][e['gold']]:
                r['covers'][e['gold']] = t
    for path in glob.glob(folder + '/work/*.out.jsonl'):
        for line in open(path):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            r['cands'] += 1
            r['attempts'].append(max((len(a) for a in e['attempts']), default=0))
            if task in outs and all(o in a for o, a in zip(outs[task], e['attempts'])):
                r['right'] += 1
    for path in glob.glob(folder + '/work/*.log'):
        for line in open(path, errors='replace'):
            m = re.match(r'rss (\d+) at .*?(\d+) samples, ', line)
            if m:
                r['rss'], r['samples'] = max(r['rss'], float(m[1])), int(m[2])
            m = re.match(r'generation (\d+):', line)
            if m:
                r['generations'] = max(r['generations'], int(m[1]) + 1)
            if line.startswith('manager '):
                got = re.search(r"'trimmed': (\d+)", line)
                r['trimmed'] = int(got[1]) if got else r['trimmed']
                got = re.search(r"'shed': (\d+)", line)
                r['shed'] = int(got[1]) if got else r['shed']
    try:
        for line in open(folder + '/supervisor.log', errors='replace'):
            m = re.search(r'deaths (\d+)', line)
            if m:
                r['deaths'] = max(r['deaths'], int(m[1]))
    except OSError:
        pass
    try:
        rows = [x.split() for x in open(folder + '/disk.txt') if len(x.split()) == 3 and x.split()[0].isdigit()]
        if rows:
            r['disk_kb'], r['files'] = max(int(x[1]) for x in rows), max(int(x[2]) for x in rows)
    except OSError:
        pass
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('points')
    ap.add_argument('--at', type=int, nargs='*', default=[60, 300, 600, 1200, 1800, 2400, 3000, 3600])
    ap.add_argument('--tasks-dir', default='data/tasks')
    a = ap.parse_args()
    specs = {x['task']: x['gold_sexp'] for x in json.load(open(a.points))}
    golds = {t: gold_forms(s) for t, s in specs.items()}
    outs = {}
    for t in specs:
        p = '%s/%s.json' % (a.tasks_dir, t)
        if os.path.exists(p):
            outs[t] = [x.get('output') for x in json.load(open(p))['test']]
    arms = {}
    for d in sorted(glob.glob(a.out + '/*')):
        if os.path.isdir(d):
            got = [load(x, outs) for x in sorted(glob.glob(d + '/*'))]
            arms[os.path.basename(d)] = {r['task']: r for r in got if r}
    names = list(arms)
    tasks = sorted(set.intersection(*[set(v) for v in arms.values()]) & set(golds))
    tasks = [t for t in tasks if any(arms[n][t]['covers'] for n in names)]
    now = time.time()
    elapsed = max((now - r['start'] for v in arms.values() for r in v.values()), default=0)
    print('tasks in both arms with any cover: %d; elapsed about %d s at copy time' % (len(tasks), elapsed))
    print('%-8s %7s %8s %8s %6s %6s' % ('arm', 'seconds', 'non-DET', 'DET', 'cands', 'right'))
    for t in a.at:
        for n in names:
            nd = sum(golds[x][0][i] != 'DET' for x in tasks for i, s in arms[n][x]['covers'].items() if s <= t and i < len(golds[x][0]))
            dt = sum(golds[x][0][i] == 'DET' for x in tasks for i, s in arms[n][x]['covers'].items() if s <= t and i < len(golds[x][0]))
            print('%-8s %7d %8d %8d' % (n, t, nd, dt))
    for n in names:
        by = collections.Counter()
        for x in tasks:
            kinds, depth = golds[x]
            for i in arms[n][x]['covers']:
                if i < len(kinds):
                    by['DET ' + band(depth[i]) if kinds[i] == 'DET' else 'non-DET ' + band(depth[i])] += 1
        print(n, 'by depth so far:', dict(sorted(by.items())))
    print('forms: non-DET %d, DET %d' % (sum(k != 'DET' for t in tasks for k in golds[t][0]), sum(k == 'DET' for t in tasks for k in golds[t][0])))
    for n in names:
        v = list(arms[n].values())
        print('%s: tasks %d, candidates %d, tasks with one %d, tasks right %d, deaths %d, median generations %.0f, median samples %.0f' % (
            n, len(v), sum(r['cands'] for r in v), sum(r['cands'] > 0 for r in v), sum(r['right'] > 0 for r in v), sum(r['deaths'] for r in v),
            statistics.median(r['generations'] for r in v) if v else 0, statistics.median(r['samples'] for r in v) if v else 0))
        wrong = [r for r in v if r['cands'] > r['right']]
        att = collections.Counter(x for r in v for x in r['attempts'])
        print('   false candidates %d; tasks with a false candidate alone %d, with a true one too %d; candidates by attempts per test input %s' % (
            sum(r['cands'] - r['right'] for r in v), sum(not r['right'] for r in wrong), sum(r['right'] > 0 for r in wrong), dict(sorted(att.items()))))
        print('   worst RSS MiB %.0f, median worst %.0f; store: worst %.1f MiB, median %.1f MiB, worst files %d; manager trimmed: worst %d, median %.0f, shed median %.0f' % (
            max((r['rss'] for r in v), default=0), statistics.median(r['rss'] for r in v) if v else 0, max((r['disk_kb'] for r in v), default=0) / 1024,
            statistics.median(r['disk_kb'] for r in v) / 1024 if v else 0, max((r['files'] for r in v), default=0), max((r['trimmed'] for r in v), default=0),
            statistics.median(r['trimmed'] for r in v) if v else 0, statistics.median(r['shed'] for r in v) if v else 0))


if __name__ == '__main__':
    main()
