#!/usr/bin/env python3
"""Pool recall and candidates by wall seconds, from events alone, so it reads tasks that are still running.

  python3 recall_at.py POINTS.json ARM=OUT_DIR [...] [--at 60 120 300 600]

At each time t, a task counts where its clock reaches t in every arm: its last event, --elapsed, or its done record. Compare arms on that row's task count.
A cover event gives a gold form and its seconds. Forms are non-OUT lines of gold, non-DET and DET apart. A task whose cover check has no gold is left out.
"""
import argparse
import glob
import json
import os


def forms(sexp):
    return [x.split()[0].lstrip('(') for x in sexp.strip().split('\n') if not x.startswith('(OUT')]


def load(folder):
    out = {}
    for path in glob.glob(folder + '/*.events.jsonl'):
        task = os.path.basename(path)[:-len('.events.jsonl')]
        covers, cands, last, ended, right = {}, [], 0.0, False, 0
        with open(path) as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:  # a line that is being written
                    continue
                last = max(last, e.get('seconds', 0) or 0)
                if e['event'] == 'cover':
                    covers.setdefault(e['gold'], e['seconds'])
                elif e['event'] == 'candidate':
                    cands.append(e['seconds'])
                elif e['event'] == 'done':
                    ended, right = True, e['right']
        out[task] = dict(covers=covers, cands=cands, last=last, ended=ended, right=right)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('points')
    ap.add_argument('arms', nargs='+')
    ap.add_argument('--at', type=int, nargs='*', default=[60, 120, 300, 600])
    ap.add_argument('--elapsed', type=float, default=0, help="wall seconds since a common start: a task's clock is at least this, as it writes events only when it finds something")
    a = ap.parse_args()
    gold = {x['task']: forms(x['gold_sexp']) for x in json.load(open(a.points))}
    arms = {}
    for spec in a.arms:
        name, _, path = spec.rpartition('=')
        arms[name or os.path.basename(path.rstrip('/'))] = load(path)
    print('%-12s %7s %6s %8s %8s %6s %11s' % ('arm', 'seconds', 'tasks', 'non-DET', 'DET', 'cands', 'tasks cand'))
    for t in a.at:
        tasks = [x for x in gold if all(x in v and (v[x]['ended'] or max(v[x]['last'], a.elapsed) >= t) for v in arms.values()) and any(v[x]['covers'] for v in arms.values())]
        for name, v in arms.items():
            nd = sum(gold[x][i] != 'DET' for x in tasks for i, s in v[x]['covers'].items() if s <= t)
            dt = sum(gold[x][i] == 'DET' for x in tasks for i, s in v[x]['covers'].items() if s <= t)
            c = [sum(s <= t for s in v[x]['cands']) for x in tasks]
            print('%-12s %7d %6d %8d %8d %6d %11d' % (name[:12], t, len(tasks), nd, dt, sum(c), sum(n > 0 for n in c)))
    for name, v in arms.items():
        print('%s: right on test, tasks that ended: %d of %d' % (name, sum(x['right'] > 0 for x in v.values() if x['ended']), sum(x['ended'] for x in v.values())))


if __name__ == '__main__':
    main()
