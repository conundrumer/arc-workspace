#!/usr/bin/env python
"""Compares arms of the super DAG pool from their out folders, finished tasks or not. Reads <task>.events.jsonl and <task>.done.json only.

  python pool_report.py [LABEL=]OUT_DRAWS [LABEL=]OUT_SEARCH [...] [--every SECONDS]

A task with a done file is finished: its counts come from the done file. A task with an events file alone is running (or was killed): its
gold relations covered and its candidates come from the cover and candidate events, so far. Tasks whose gold does not replay (gold 0) take no
part in the share of gold covered. Per arm, one block for all tasks, and one for the tasks that every arm has finished (the comparison at equal budget).
With --every, the report prints again after that many seconds, until interrupted.
"""
import argparse
import collections
import glob
import json
import os
import statistics
import sys
import time


def load(folder):
    """{task: dict(done=done record or None, covers=, cands=, last=)} of an out folder."""
    out = {}
    for path in sorted(glob.glob(os.path.join(folder, '*.events.jsonl'))):
        task = os.path.basename(path)[:-len('.events.jsonl')]
        t = dict(done=None, covers=0, cands=0, last=0.0)
        try:
            with open(path) as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except ValueError:  # a line that is being written
                        continue
                    t['covers'] += e['event'] == 'cover'
                    t['cands'] += e['event'] == 'candidate'
                    t['last'] = max(t['last'], e.get('seconds', 0) or 0)
        except OSError:
            continue
        dp = os.path.join(folder, task + '.done.json')
        if os.path.exists(dp):
            try:
                t['done'] = json.load(open(dp))
            except ValueError:
                pass
        out[task] = t
    return out


def count(d, key):
    return d['counts'].get(key, 0)


def summary(tasks):
    """The numbers of a set of tasks {task: record}."""
    done = {k: t['done'] for k, t in tasks.items() if t['done']}
    run = {k: t for k, t in tasks.items() if not t['done']}
    shares = [d['covered'] / d['gold'] for d in done.values() if d['gold']]
    s = collections.OrderedDict()
    s['tasks finished / started'] = '%d / %d' % (len(done), len(tasks))
    s['gold tasks (gold > 0) finished'] = len(shares)
    s['gold covered, mean share'] = '%.3f' % statistics.mean(shares) if shares else '-'
    s['gold covered, count / gold'] = '%d / %d' % (sum(d['covered'] for d in done.values()), sum(d['gold'] for d in done.values()))
    s['tasks with a gold relation covered'] = sum(d['covered'] > 0 for d in done.values())
    s['candidates'] = sum(d['candidates'] for d in done.values())
    s['tasks with a candidate'] = sum(d['candidates'] > 0 for d in done.values())
    s['tasks with a candidate right on test'] = sum(d['right'] > 0 for d in done.values())
    secs = sum(d['seconds'] for d in done.values()) or 1e-9
    tries = sum(d['draws'] for d in done.values())
    nodes = sum(d['nodes'] for d in done.values())
    equal = sum(count(d, 'node:equal') for d in done.values())
    kept = sum(sum(v for k, v in d['counts'].items() if k.startswith('kept:')) for d in done.values())
    s['clause tries'] = tries
    s['  per second'] = '%.2f' % (tries / secs)
    s['new nodes'] = nodes
    s['  per second '] = '%.3f' % (nodes / secs)
    s['  per try'] = '%.3f' % (nodes / tries) if tries else '-'
    s['kept forms'] = kept
    s['equal nodes (clause gave only known nodes)'] = equal
    s['  per second  '] = '%.3f' % (equal / secs)
    s['  per try '] = '%.3f' % (equal / tries) if tries else '-'
    s['tries with no table'] = sum(count(d, 'node:no table') for d in done.values())
    s['tries that failed or dropped'] = tries - kept - equal - sum(count(d, 'node:no table') for d in done.values())
    if any('search:visits' in d['counts'] for d in done.values()):
        for k in ('search:visits', 'search:new scope', 'search:resume', 'search:end patience', 'search:end seconds', 'search:end exhausted', 'search:end deadline',
                  'search:equal scope-free', 'search:equal reads scope', 'search:clause deadline', 'search:manager shed', 'search:manager trimmed'):
            s[k] = sum(count(d, k) for d in done.values())
        for k in ('search:seconds new', 'search:seconds equal', 'search:seconds next', 'search:seconds take', 'search:seconds test', 'search:seconds visit setup'):
            s[k] = '%.0f' % sum(count(d, k) for d in done.values())
    s['peak RSS MiB, max'] = max((d['peak_rss_mib'] for d in done.values()), default=0)
    depth = collections.Counter()
    for d in done.values():
        depth.update({int(k): v for k, v in d['depth'].items()})
    s['forms by depth'] = ' '.join('%d:%d' % (k, depth[k]) for k in sorted(depth)) or '-'
    if run:
        s['running or killed: tasks'] = len(run)
        s['  gold covered so far'] = sum(t['covers'] for t in run.values())
        s['  candidates so far'] = sum(t['cands'] for t in run.values())
    return s


def table(title, arms):
    sums = {name: summary(tasks) for name, tasks in arms.items()}
    keys = []
    for s in sums.values():
        keys += [k for k in s if k not in keys]
    w = max(len(k) for k in keys)
    cols = list(arms)
    print('\n%s' % title)
    print('%-*s  %s' % (w, '', '  '.join('%22s' % c[-22:] for c in cols)))
    for k in keys:
        print('%-*s  %s' % (w, k, '  '.join('%22s' % sums[c].get(k, '') for c in cols)))


def report(folders):
    arms = {}
    for f in folders:
        label, _, path = f.rpartition('=')
        arms[label or os.path.basename(path.rstrip('/'))] = load(path)
    table('All tasks of each arm', arms)
    both = set.intersection(*[{k for k, t in a.items() if t['done']} for a in arms.values()])
    table('Tasks that every arm has finished (%d)' % len(both), {f: {k: a[k] for k in both} for f, a in arms.items()})
    sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folders', nargs='+')
    ap.add_argument('--every', type=float, default=0)
    a = ap.parse_args()
    while True:
        report(a.folders)
        if not a.every:
            return
        time.sleep(a.every)
        print('\n' + '=' * 60)


if __name__ == '__main__':
    main()
