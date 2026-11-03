#!/usr/bin/env python3
"""Table recall and paired recall at k for an arm against a base at wall-time cuts, from pool run folders. It reads partial output: a task counts once both arms have its done file.

  python3 search_pool_cuts.py POINTS.json BASE_DIR ARM_DIR [--at 60 300 600]

A cut's k for a task is the fewer of the two arms' proposals by that time, from `visit` events. Whole-budget recall at a cut counts covers by that time. Wins, losses and ties are non-DET forms at k per task, and `cut` gives the same count by time.
"""
import glob
import json
import os
import sys


def load(folder, task):
    covers, visits = {}, []
    for line in open('%s/%s.events.jsonl' % (folder, task)):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e['event'] == 'cover' and e['gold'] not in covers:
            covers[e['gold']] = e['draw'], e['seconds']
        elif e['event'] == 'visit':
            visits.append((e['seconds'], e['tries']))
    return covers, visits


args = sys.argv[1:]
cuts = [60, 300, 600]
if '--at' in args:
    i = args.index('--at')
    cuts = [int(x) for x in args[i + 1:]]
    del args[i:]
points, base, arm = args
kinds = {x['task']: [y.split()[0].lstrip('(') for y in x['gold_sexp'].strip().split('\n') if not y.startswith('(OUT')] for x in json.load(open(points))}
tasks = sorted(set(os.path.basename(p)[:-10] for p in glob.glob(base + '/*.done.json')) & set(os.path.basename(p)[:-10] for p in glob.glob(arm + '/*.done.json')))
A = {t: load(base, t) for t in tasks}
B = {t: load(arm, t) for t in tasks}
print('tasks', len(tasks))
print('cut  base_nd arm_nd  base_nd@k arm_nd@k  wins losses ties  cut_wins cut_losses  base_det arm_det  base_det@k arm_det@k  median_k')
for T in cuts:
    row = dict(an=0, bn=0, ank=0, bnk=0, ad=0, bd=0, adk=0, bdk=0, w=0, l=0, e=0, cw=0, cl=0)
    ks = []
    for t in tasks:
        k = min(sum(n for s, n in A[t][1] if s <= T), sum(n for s, n in B[t][1] if s <= T))
        ks.append(k)
        def n(run, det, at):
            return sum((kinds[t][g] == 'DET') == det and (d <= k if at else s <= T) for g, (d, s) in run[0].items())
        an, bn, ank, bnk = n(A[t], False, False), n(B[t], False, False), n(A[t], False, True), n(B[t], False, True)
        row['an'] += an
        row['bn'] += bn
        row['ank'] += ank
        row['bnk'] += bnk
        row['ad'] += n(A[t], True, False)
        row['bd'] += n(B[t], True, False)
        row['adk'] += n(A[t], True, True)
        row['bdk'] += n(B[t], True, True)
        row['w'] += bnk > ank
        row['l'] += bnk < ank
        row['e'] += bnk == ank
        row['cw'] += bn > an
        row['cl'] += bn < an
    ks.sort()
    print(T, row['an'], row['bn'], row['ank'], row['bnk'], row['w'], row['l'], row['e'], row['cw'], row['cl'], row['ad'], row['bd'], row['adk'], row['bdk'], ks[len(ks) // 2])
