#!/usr/bin/env python3
"""Recall, tries and picks by kind for pool arms on a task list, from run folders. It reads partial output: a task counts for an arm once its done file exists.

  python3 search_pool_cell_report.py POINTS.json BASE=DIR ARM=DIR ... [--tasks a,b,c]

BASE is the first arm. Forms are gold's non-OUT lines. `lost` are DET forms that BASE found and the arm in LOST= (the second arm named) did not. Seconds and tries by kind come from `visit` events: a visit's seconds are the gap to the visit before. Pick depth comes from a visit's fids and the nodes file; fid 0 entries of an empty scope count as none.
"""
import collections
import json
import os
import subprocess
import sys


def load(folder, task):
    done = folder + '/' + task + '.done.json'
    if not os.path.exists(done):
        return None
    r = dict(done=json.load(open(done)), cover={}, sec=collections.Counter(), tries=collections.Counter(), visits=collections.Counter(), picks=collections.Counter())
    depth = {}
    text = subprocess.run(['zstd', '-dcf', folder + '/' + task + '.nodes.jsonl.zst'], capture_output=True, check=False).stdout.decode(errors='replace')
    for line in text.splitlines():
        try:
            n = json.loads(line)
        except ValueError:
            continue
        if 'token' in n and 'depth' in n:
            depth[str(n['token'])] = n['depth']
    last = 0.0
    for line in open(folder + '/' + task + '.events.jsonl'):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e['event'] == 'cover':
            r['cover'][e['gold']] = (e['seconds'], e.get('draw'))
        elif e['event'] == 'visit':
            k = e['kind']
            r['sec'][k] += e['seconds'] - last
            last = e['seconds']
            r['tries'][k] += e['tries']
            r['visits'][k] += 1
            for f in e['fids']:
                d = depth.get(str(f))
                r['picks'][d if d in (1, 2) else 'other' if d else 'unknown'] += 1
    return r


def main():
    args = sys.argv[1:]
    tasks = 'c4d067a0 c7f57c3e cb2d8a2c d35bdbdc dd6b8c4b dfadab01'.split()
    if '--tasks' in args:
        i = args.index('--tasks')
        tasks = args[i + 1].split(',')
        del args[i:i + 2]
    specs = {x['task']: x['gold_sexp'] for x in json.load(open(args[0]))}
    arms = [a.split('=', 1) for a in args[1:]]
    kinds = {t: [x.split()[0].lstrip('(') for x in specs[t].strip().split('\n') if not x.startswith('(OUT')] for t in tasks}
    runs = {name: {t: load(d, t) for t in tasks} for name, d in arms}
    base = arms[0][0]
    lost = None
    if len(arms) > 1:
        lost = sorted((t, g) for t in tasks if runs[base][t] and runs[arms[1][0]][t] for g in runs[base][t]['cover'] if kinds[t][g] == 'DET' and g not in runs[arms[1][0]][t]['cover'])
    for name, _ in arms:
        rs = {t: r for t, r in runs[name].items() if r}
        by = collections.Counter(kinds[t][g] for t, r in rs.items() for g in r['cover'])
        sec, tries, picks = collections.Counter(), collections.Counter(), collections.Counter()
        for r in rs.values():
            sec.update(r['sec'])
            tries.update(r['tries'])
            picks.update(r['picks'])
        total, ntries, npicks = sum(sec.values()) or 1, sum(tries.values()) or 1, sum(picks.values()) or 1
        print(name, 'tasks', len(rs), 'found', dict(sorted(by.items())))
        print('  seconds', {k: '%.0f%%' % (100 * v / total) for k, v in sorted(sec.items())}, 'tries', {k: '%d (%.0f%%)' % (v, 100 * v / ntries) for k, v in sorted(tries.items())})
        print('  picks', {str(k): '%.0f%%' % (100 * v / npicks) for k, v in sorted(picks.items(), key=str)}, 'draws', sum(r['done']['draws'] for r in rs.values()), 'forms', sum(r['done']['forms'] for r in rs.values()), 'covered', sum(r['done']['covered'] for r in rs.values()))
        if lost is not None:
            print('  lost', ' '.join('%s.%d:%s' % (t[:6], g, ('%.0fs/%s' % rs[t]['cover'][g]) if t in rs and g in rs[t]['cover'] else '-') for t, g in lost), 'back', sum(t in rs and g in rs[t]['cover'] for t, g in lost), 'of', len(lost))


main()
