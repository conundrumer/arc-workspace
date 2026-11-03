#!/usr/bin/env python3
"""Recall, renewals and proposals for worker-path arms against a base by wall-time cut. It reads partial output: a task counts once the arm has its cover file.

  python3 search_renewal_report.py POINTS.json BASE_OUT/ARM ARM_OUT/ARM [ARM_OUT/ARM ...] [--at 60 300 600]

A folder holds <task>/start and <task>/work/*.cover and *.log. A renewal is a generation line past generation 0, timed by the first `rss ... at A s of B` line after it, where B is the time left. Base and arm counts are over the tasks each arm has. Wins and losses are non-DET forms per task by the cut, for the arm against the base.
"""
import collections
import glob
import json
import os
import re
import statistics
import sys


def covers(folder, task, cut):
    base = float(open('%s/%s/start' % (folder, task)).read())
    found = {}
    for path in glob.glob('%s/%s/work/*.cover' % (folder, task)):
        for line in open(path):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e['time'] - base <= cut:
                found.setdefault(e['gold'], e['draw'])
    return found


def renewals(folder, task, cut, seconds):
    text = ''.join(open(p, errors='replace').read() for p in glob.glob('%s/%s/work/*.log' % (folder, task)))
    times, gen = {}, 0
    for a, left in re.findall(r'^generation (\d+): rss|^rss \d+ at \d+ s of (\d+)', text, re.M):
        if a:
            gen = int(a)
            times.setdefault(gen, None)
        elif times.get(gen, 0) is None:
            times[gen] = seconds - int(left)
    return sum(v is not None and v <= cut for k, v in times.items() if k > 0)


def samples(folder, task):
    text = ''.join(open(p, errors='replace').read() for p in glob.glob('%s/%s/work/*.log' % (folder, task)))
    return max([0] + [int(x) for x in re.findall(r', (\d+) samples,', text)])


def main():
    args = sys.argv[1:]
    cuts = [60, 300, 600]
    if '--at' in args:
        i = args.index('--at')
        cuts = [int(x) for x in args[i + 1:]]
        del args[i:]
    kinds = {x['task']: [y.split()[0].lstrip('(') for y in x['gold_sexp'].strip().split('\n') if not y.startswith('(OUT')] for x in json.load(open(args[0]))}
    folders = args[1:]
    base = folders[0]
    for folder in folders:
        tasks = sorted(t for t in os.listdir(folder) if glob.glob('%s/%s/work/*.cover' % (folder, t)))
        seconds = 3600 if '3600s' in folder else 600
        print(os.path.basename(folder), 'tasks', len(tasks), 'median samples', statistics.median([samples(folder, t) for t in tasks] or [0]))
        for cut in cuts:
            count = collections.Counter()
            bn = bd = w = l = e = 0
            renew = []
            for t in tasks:
                a = covers(folder, t, cut)
                b = covers(base, t, cut)
                k = kinds[t]
                count.update(k[g] for g in a)
                x = sum(k[g] != 'DET' for g in a)
                y = sum(k[g] != 'DET' for g in b)
                bn += y
                bd += sum(k[g] == 'DET' for g in b)
                w, l, e = w + (x > y), l + (x < y), e + (x == y)
                renew.append(renewals(folder, t, cut, seconds))
            print('  %5d s: non-DET %d, DET %d, INIT %d, RULE %d; base on these tasks %d, %d; wins %d, losses %d, ties %d; renewals %d, median %.0f' % (
                cut, count['INIT'] + count['RULE'], count['DET'], count['INIT'], count['RULE'], bn, bd, w, l, e, sum(renew), statistics.median(renew or [0])))


main()
