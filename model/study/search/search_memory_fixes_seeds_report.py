#!/usr/bin/env python3
"""`both` against `base` on two seeds, from a run folder of the memory fixes. It reads partial output, so it can run while the pods still write.

  python3 search_memory_fixes_seeds_report.py RUN_DIR [--points FILE]

RUN_DIR holds manifest.json and out/<arm>/<task>/ with start, supervisor.log, work/*.log and work/*.cover. FILE is the kit's points-eval.json. The job list comes from the manifest's `jobs` path, under RUN_DIR's grandparent.

Terms:
  a job              one arm on one task
  has a task         the job has a start file and a prof line, and the task is in the gold file
  common tasks       the tasks that both arms of a comparison have, counted apart for each comparison
  elapsed            seconds since the job's start file, by the latest of its status lines, `rss ... at A s of B` lines, cover times and disk.txt lines
  ended              supervisor.log has the job's `task ... done` line
  gold               distinct gold forms covered within 600 s of the start, each index once per task
  reached a cut      elapsed is at the cut, or the job ended

A row at a cut counts only the common tasks where both arms reached that cut, so a cut past the read shows 0 tasks. The other tables give each number as of the last line read, so two arms of a task can differ by the time between their last lines.

Sums over a task's processes follow search_memory_fixes_report.py. `cpu` restarts at a new worker and `notable` restarts at each generation. `draws`, `forms` and `dup` run on across generations, so their last prof line gives the total.
"""
import glob
import json
import math
import os
import re
import statistics
import sys
import time

ARMS = 'base_s1', 'both_s1', 'base_s101', 'both_s101'
SEEDS = 1, 101
CUTS = 60, 300, 600
BUDGET = CUTS[-1]
POINTS = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/b41/kit41/points-eval.json'

GENERATION = re.compile(r'generation (\d+): rss (\d+) after load')
TIMES = re.compile(r'rss (\d+) at (\d+) s of (\d+), cpu')
JUMP = re.compile(r'rss (\d+) from ')
END = re.compile(r'end: .*, (\d+) MiB, ')
STATUS = re.compile(r'status at (\d+) s: .*deaths (\d+), kills (\d+), .*tasks with a candidate (\d+)')
ENDED = re.compile(r'task \S+ lives (\d+) candidates (\d+) done \d+ of \d+ at (\d+)')
EXITED = re.compile(r'worker of \S+ exited (-?\d+) after (\d+) s')
KILL = re.compile(r'\d\d:\d\d:\d\d kill \S+ (.*)')


def read_log(d, folder):
    """Adds to d the prof rows with their sums over processes, the generations, the greatest RSS and the worker's elapsed seconds."""
    total = None
    cpu_last = cpu_done = notable_last = notable_done = 0
    for path in sorted(glob.glob(folder + '/work/*.log')):
        for line in open(path, errors='replace'):
            if line.startswith('generation '):
                m = GENERATION.match(line)
                if m:
                    d['gens'].append(int(m[1]))
                    notable_done, notable_last = notable_done + notable_last, 0
                    d['peak'] = max(d['peak'], int(m[2]))
            elif line.startswith('prof '):
                try:
                    r = json.loads(line[5:])
                except ValueError:
                    d['unreadable'] += 1
                    continue
                if r['cpu'] < cpu_last:  # a new worker: an execv keeps the CPU clock
                    cpu_done += cpu_last
                    d['cpu_restarts'] += 1
                if d['rows']:
                    d['fell'].update(k for k in ('draws', 'forms', 'dup') if r.get(k, 0) < d['rows'][-1].get(k, 0))
                d['no_dup'] = d['no_dup'] or 'dup' not in r
                cpu_last, notable_last = r['cpu'], r['notable']
                d['peak'] = max(d['peak'], r['rss'])
                r.update(cpu_all=cpu_done + cpu_last, notable_all=notable_done + notable_last)
                d['rows'].append(r)
            elif line.startswith('rss '):
                m = TIMES.match(line)
                if m:
                    total = total or int(m[3])
                    d['elapsed'] = max(d['elapsed'], total - (int(m[3]) - int(m[2])))
                    d['peak'] = max(d['peak'], int(m[1]))
                else:
                    m = JUMP.match(line)
                    d['peak'] = max(d['peak'], int(m[1])) if m else d['peak']
            elif line.startswith('end: '):
                m = END.match(line)
                d['peak'] = max(d['peak'], int(m[1])) if m else d['peak']


def read_covers(d, folder):
    """Adds to d {gold index: seconds from the start to its first cover} and {gold index: first draw}."""
    for path in glob.glob(folder + '/work/*.cover'):
        for line in open(path, errors='replace'):
            try:
                e = json.loads(line)
                g, draw, t = e['gold'], e['draw'], e['time'] - d['start']
            except (ValueError, KeyError, TypeError):
                d['unreadable'] += 1
                continue
            d['cover_lines'] += 1
            d['covers'][g] = min(t, d['covers'].get(g, t))
            d['draws'][g] = min(draw, d['draws'].get(g, draw))
            d['elapsed'] = max(d['elapsed'], t)


def read_supervisor(d, folder):
    """Adds to d the job's end, candidates, lives and its worker deaths before a kill past the end."""
    try:
        lines = open(folder + '/supervisor.log', errors='replace').read().split('\n')
    except OSError:
        return
    past_end = False
    for line in lines:
        m = STATUS.search(line)
        if m:
            d['elapsed'] = max(d['elapsed'], int(m[1]))
            d['flag'] = int(m[4])
            continue
        m = ENDED.search(line)
        if m:
            d['ended'], d['lives'], d['candidates'] = True, int(m[1]), int(m[2])
            d['elapsed'] = max(d['elapsed'], int(m[3]))
            continue
        m = KILL.match(line)
        if m:
            if 'past its end' in m[1]:
                past_end = True
            else:
                d['other_kills'].append(m[1])
            continue
        m = EXITED.search(line)
        if m and not past_end:
            d['deaths'].append((int(m[1]), int(m[2])))


def read_disk(d, folder):
    try:
        for line in open(folder + '/disk.txt', errors='replace'):
            x = line.split()
            if len(x) == 3 and x[0].isdigit():
                d['elapsed'] = max(d['elapsed'], int(x[0]) - d['start'])
    except OSError:
        pass


def read_job(folder):
    d = dict(start=None, rows=[], gens=[], peak=0, covers={}, draws={}, cover_lines=0, elapsed=0, ended=False, candidates=None, lives=None, flag=0, deaths=[], other_kills=[], fell=set(), no_dup=False, cpu_restarts=0, unreadable=0)
    try:
        d['start'] = float(open(folder + '/start').read())
    except (OSError, ValueError):
        return d
    read_log(d, folder)
    read_covers(d, folder)
    read_supervisor(d, folder)
    read_disk(d, folder)
    return d


def read_jobs(run, manifest):
    """{(arm, task)} from the job list, or None without that file."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(run))), manifest.get('jobs', ''))
    if not os.path.isfile(path):
        return None
    jobs = set()
    for line in open(path):
        m = re.search(r'run3600\.sh (\S+) (\S+) ', line)
        if m:
            jobs.add((m[2], m[1]))
    return jobs


def sign_p(wins, losses):
    n = wins + losses
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2 ** n) if n else None


def cell(x, form='%.0f'):
    return '-' if x is None else form % x


def table(head, rows):
    print('| %s |' % ' | '.join(head))
    print('|' + ' --- |' * len(head))
    for r in rows:
        print('| %s |' % ' | '.join(str(x) for x in r))
    print()


def main():
    args = sys.argv[1:]
    points = POINTS
    if '--points' in args:
        i = args.index('--points')
        points = args[i + 1]
        del args[i:i + 2]
    run = args[0].rstrip('/')
    out = run + '/out'
    manifest = json.load(open(run + '/manifest.json'))
    kinds = {x['task']: [y.split()[0].lstrip('(') for y in x['gold_sexp'].strip().split('\n') if not y.startswith('(OUT')] for x in json.load(open(points))}
    jobs = read_jobs(run, manifest)

    data = {}
    for arm in ARMS:
        folder = '%s/%s' % (out, arm)
        for t in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            if os.path.isdir('%s/%s' % (folder, t)):
                data[arm, t] = read_job('%s/%s' % (folder, t))
    has = {k for k, d in data.items() if d['start'] is not None and d['rows'] and k[1] in kinds}
    tasks = sorted({t for _, t in has})

    def gold(arm, t, cut=BUDGET):
        """(non-DET, DET) forms of the job by the cut."""
        found = [g for g, s in data[arm, t]['covers'].items() if s <= cut and 0 <= g < len(kinds[t])]
        det = sum(kinds[t][g] == 'DET' for g in found)
        return len(found) - det, det

    def reached(arm, t, cut):
        return data[arm, t]['ended'] or data[arm, t]['elapsed'] >= cut

    def common(a, b, cut=None):
        return [t for t in tasks if (a, t) in has and (b, t) in has and (cut is None or reached(a, t, cut) and reached(b, t, cut))]

    def sums(arm, ts, cut=BUDGET):
        got = [gold(arm, t, cut) for t in ts]
        return sum(x for x, _ in got), sum(y for _, y in got)

    ended = sum(d['ended'] for d in data.values())
    finished = bool(jobs) and all(k in data and data[k]['ended'] for k in jobs)
    print('# Memory fixes on two seeds: %s' % os.path.basename(os.path.abspath(run)))
    print()
    print('Read at %s. Jobs listed %s, jobs with a task %d, jobs ended %d.' % (time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime()), cell(jobs and len(jobs)), len(has), ended))
    print()
    rows = []
    for arm in ARMS:
        el = [data[k]['elapsed'] for k in has if k[0] == arm]
        n_cpu = sum(data[k]['rows'][-1]['cpu_all'] for k in has if k[0] == arm)
        rows.append((arm, len(el), sum(data[k]['ended'] for k in has if k[0] == arm), cell(statistics.median(el) if el else None), cell(min(el, default=None)), cell(max(el, default=None)), cell(n_cpu / sum(el) if sum(el) else None, '%.2f')))
    table(('arm', 'tasks', 'ended', 'median elapsed s', 'least', 'most', 'CPU s per elapsed s'), rows)
    rows = [('both_s%d, base_s%d' % (s, s), len(common('base_s%d' % s, 'both_s%d' % s))) for s in SEEDS]
    rows += [('%s_s1, %s_s101' % (a, a), len(common(a + '_s1', a + '_s101'))) for a in ('base', 'both')]
    table(('comparison', 'common tasks'), rows)

    print('## By seed and arm, on common tasks')
    print()
    print('Form rate is forms less duplicates per CPU s, and proposal rate is proposals per CPU s, each as a sum over tasks over the sum of CPU s. Candidates sum the ended tasks. Tasks with one adds running tasks from the status line.')
    print()
    rows = []
    for s in SEEDS:
        ts = common('base_s%d' % s, 'both_s%d' % s)
        for arm in ('base_s%d' % s, 'both_s%d' % s):
            ds = [data[arm, t] for t in ts]
            last = [d['rows'][-1] for d in ds]
            cpu = sum(r['cpu_all'] for r in last)
            nd, det = sums(arm, ts)
            rows.append((s, arm, len(ts), nd, det, cell(sum(r['forms'] - r.get('dup', 0) for r in last) / cpu if cpu else None, '%.3f'), cell(sum(r['draws'] for r in last) / cpu if cpu else None, '%.3f'),
                         sum(sum(g > 0 for g in d['gens']) for d in ds), sum(r.get('dup', 0) for r in last), sum(r['notable_all'] for r in last), cell(cpu),
                         cell(max((d['peak'] for d in ds), default=None)), cell(statistics.median(d['peak'] for d in ds) if ds else None), sum(d['candidates'] or 0 for d in ds), sum(bool(d['candidates'] or d['flag']) for d in ds)))
    table(('seed', 'arm', 'tasks', 'gold non-DET', 'gold DET', 'form rate', 'proposal rate', 'renewals', 'duplicates', 'node:no table', 'CPU s', 'max RSS MiB', 'median task max RSS', 'candidates', 'tasks with one'), rows)

    print('## Gold at the cuts')
    print()
    print('Each row counts the common tasks where both arms of the seed reached the cut.')
    print()
    rows = []
    for cut in CUTS:
        for s in SEEDS:
            ts = common('base_s%d' % s, 'both_s%d' % s, cut)
            for arm in ('base_s%d' % s, 'both_s%d' % s):
                nd, det = sums(arm, ts, cut)
                rows.append((cut, s, arm, len(ts), nd if ts else '-', det if ts else '-'))
    table(('cut s', 'seed', 'arm', 'tasks', 'gold non-DET', 'gold DET'), rows)

    print('## Pairs: both against base within a seed, on all gold')
    print()
    rows = []
    for s in SEEDS:
        a, b = 'both_s%d' % s, 'base_s%d' % s
        ts = common(a, b)
        diff = [sum(gold(a, t)) - sum(gold(b, t)) for t in ts]
        wins, losses = sum(x > 0 for x in diff), sum(x < 0 for x in diff)
        rows.append((s, len(ts), wins, losses, len(ts) - wins - losses, cell(sign_p(wins, losses), '%.4f'), sum(sum(gold(a, t)) for t in ts), sum(sum(gold(b, t)) for t in ts)))
    table(('seed', 'tasks', 'wins', 'losses', 'ties', 'sign test p', 'both gold', 'base gold'), rows)

    print('## Seed band')
    print()
    rows = []
    for arm in ('base', 'both'):
        a, b = arm + '_s1', arm + '_s101'
        ts = common(a, b)
        each = [(gold(a, t), gold(b, t)) for t in ts]
        for kind, pick in (('non-DET', lambda x: x[0]), ('DET', lambda x: x[1]), ('total', sum)):
            x, y = sum(pick(p) for p, _ in each), sum(pick(q) for _, q in each)
            rows.append((arm, kind, len(ts), x, y, abs(x - y), cell(sum(abs(pick(p) - pick(q)) for p, q in each) / len(ts) if ts else None, '%.2f')))
    table(('arm', 'kind', 'tasks', 'seed 1', 'seed 101', 'difference', 'mean of absolute task differences'), rows)

    print('## The bar')
    print()
    print('Bar: %s' % manifest.get('bar'))
    print()
    print('Prediction: gold, %s; band, %s; read, %s.' % (manifest['prediction']['gold'], manifest['prediction']['band'], manifest['prediction']['read']))
    print()
    print('The bar is read on total gold. Gain is both less base on the seed\'s common tasks. Band is the base difference between seeds on the common tasks of those two arms.')
    print()
    base_ts = common('base_s1', 'base_s101')
    rows, gains, band = [], {}, None
    for kind, pick in (('total', sum), ('non-DET', lambda x: x[0]), ('DET', lambda x: x[1])):
        cols = [kind]
        for s in SEEDS:
            ts = common('base_s%d' % s, 'both_s%d' % s)
            gain = pick(sums('both_s%d' % s, ts)) - pick(sums('base_s%d' % s, ts))
            cols += [len(ts), gain]
            if kind == 'total':
                gains[s] = gain
        gap = abs(pick(sums('base_s1', base_ts)) - pick(sums('base_s101', base_ts)))
        band = gap if kind == 'total' else band
        rows.append(cols + [len(base_ts), gap])
    table(('kind', 'tasks seed 1', 'gain seed 1', 'tasks seed 101', 'gain seed 101', 'tasks band', 'band'), rows)
    if finished:
        print('Result: %s.' % ('held' if all(g > band for g in gains.values()) else 'not held'))
    else:
        print('Result: not ready. %d of %s jobs ended.' % (ended, cell(jobs and len(jobs))))
    print()

    print('## Records')
    print()
    said = []

    def say(text):
        said.append(text)
        print('- ' + text)

    extra = sorted(set(os.listdir(out)) - set(ARMS)) if os.path.isdir(out) else []
    if extra:
        say('folders in out/ outside the arms, left out of every count: %s' % ', '.join(extra))
    if jobs is None:
        say('no job list at the manifest path')
    else:
        lost = sorted(jobs - has)
        if lost:
            say('%d listed jobs have no task yet: %s' % (len(lost), ', '.join('%s/%s' % k for k in lost[:8])))
        stray = sorted(set(data) - jobs)
        if stray:
            say('jobs outside the list: %s' % ', '.join('%s/%s' % k for k in stray[:8]))
    def tell(text, found):
        if found:
            say('%s: %d jobs, %s' % (text, len(found), ', '.join(found[:8])))

    names = lambda test: ['%s/%s' % k for k, d in sorted(data.items()) if test(k, d)]
    tell('tasks not in the gold file', names(lambda k, d: k[1] not in kinds))
    tell('prof lines with no dup field', names(lambda k, d: d['no_dup']))
    tell('draws, forms or dup fell between prof lines', names(lambda k, d: d['fell']))
    tell('a generation number that does not rise by one', names(lambda k, d: any(y != x + 1 for x, y in zip(d['gens'], d['gens'][1:]))))
    tell('gold index outside the task\'s forms', names(lambda k, d: k[1] in kinds and any(not 0 <= g < len(kinds[k[1]]) for g in d['covers'])))
    tell('a cover timed before the start', names(lambda k, d: any(s < 0 for s in d['covers'].values())))
    tell('gold first covered after 600 s, left out of gold', names(lambda k, d: any(s > BUDGET for s in d['covers'].values())))
    tell('workers that died before the end', names(lambda k, d: d['deaths']))
    tell('kills for another reason than the end', names(lambda k, d: d['other_kills']))
    tell('more than one worker life', names(lambda k, d: d['cpu_restarts'] or (d['lives'] or 0) > 1))
    for arm in ('base', 'both'):
        same = [t for t in common(arm + '_s1', arm + '_s101') if data[arm + '_s1', t]['draws'] and data[arm + '_s1', t]['draws'] == data[arm + '_s101', t]['draws']]
        tell('the same golds at the same draws in both seeds, %s' % arm, same)
    gaps = [(abs(data['base_s%d' % s, t]['elapsed'] - data['both_s%d' % s, t]['elapsed']), s, t) for s in SEEDS for t in common('base_s%d' % s, 'both_s%d' % s)]
    if gaps and max(gaps)[0] > 60:
        say('largest elapsed gap between the arms of a task: %.0f s, seed %d, %s' % max(gaps))
    unread = sum(d['unreadable'] for d in data.values())
    if unread:
        say('unreadable prof or cover lines, skipped: %d' % unread)
    if not said:
        print('Nothing to note.')


main()
