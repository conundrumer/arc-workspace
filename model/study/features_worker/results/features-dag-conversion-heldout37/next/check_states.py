"""Checks of the state rows of next_form_rows.py.

  gold_tables_env.sh 1 check_states.py ROWDIR SPLIT POINTS.jsonl [--scramble N] [--tasks T ...]

1. Scope: each state row's scope (keys, in order) and scope_id equal those of the point with the same task, form key and seed in POINTS (points-held-cut.jsonl, points-dev-cut.jsonl or points-fit-cut.jsonl). Counts the state rows with no point and the points with no state row.
2. Scramble: for N tasks of the rows, the lines of gold are shuffled and the task is replayed again; the form rows (without the times) and the state rows (without the times) equal those on disk.
Appends the result to ROWDIR/check-SPLIT.txt.
"""
import argparse
import json
import random
import sys
import time

import next_form_rows as R
import features_dag_order as DO


def strip(r):
    return {k: v for k, v in r.items() if not k.startswith('t_') and k != 'seconds'}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('rows')
    ap.add_argument('split')
    ap.add_argument('points')
    ap.add_argument('--scramble', type=int, default=0)
    ap.add_argument('--tasks', nargs='*')
    a = ap.parse_args()
    import glob
    states = [json.loads(x) for p in sorted(glob.glob('%s/state-rows-%s-*.jsonl' % (a.rows, a.split))) for x in open(p)]
    forms = [json.loads(x) for p in sorted(glob.glob('%s/form-rows-%s-*.jsonl' % (a.rows, a.split))) for x in open(p)]
    pts = {}
    for l in open(a.points):
        r = json.loads(l)
        pts[r['task'], r['key'], r['target_seed']] = r
    have_tasks = {s['task'] for s in states}
    bad, nopoint = [], 0
    seen = set()
    for r in states:
        p = pts.get((r['task'], r['key'], r['seed']))
        if p is None:
            nopoint += 1
            continue
        seen.add((r['task'], r['key'], r['seed']))
        sc = [DO.parse(x)[1] for x in p['scope']]
        if sc != r['scope'] or p['scope_id'] != r['scope_id'] or p['form'] != r['form']:
            bad.append((r['task'], r['key'], r['seed']))
    missing = sum(1 for k in pts if k[0] in have_tasks and k not in seen)
    msg = ['%s scope: %d state rows on %d tasks, %d differ from the points, %d have no point, %d points of those tasks have no row, first %s' % (time.strftime('%H:%M:%S'), len(states), len(have_tasks), len(bad), nopoint, missing, bad[:3])]
    if a.scramble:
        tx = R.texts(a.split)
        tasks = a.tasks or sorted(have_tasks)[:a.scramble]
        by_form, by_state = {}, {}
        for r in forms:
            by_form.setdefault(r['task'], {})[r['key']] = r
        for r in states:
            by_state.setdefault(r['task'], {})[r['key'], r['seed']] = r
        fail = []
        rng = random.Random(1)
        for t in tasks:
            lines = list(tx[t][1])
            rng.shuffle(lines)
            out = dict(form=[], state=[], task=[])
            R.one(t, tx[t][0], lines, R.grids(t), out)
            f2 = {r['key']: r for r in out['form']}
            s2 = {(r['key'], r['seed']): r for r in out['state']}
            same_f = all(strip({k: v for k, v in f2[k].items() if k != 'line_id'}) == strip({k: v for k, v in by_form[t][k].items() if k != 'line_id'}) for k in by_form[t]) and set(f2) == set(by_form[t])
            same_s = set(s2) == set(by_state[t]) and all(strip(s2[k]) == strip(by_state[t][k]) for k in s2)
            if not (same_f and same_s):
                fail.append((t, same_f, same_s))
        msg.append('scramble: %d tasks replayed on shuffled lines, %d differ %s' % (len(tasks), len(fail), fail[:3]))
    print('\n'.join(msg))
    with open('%s/check-%s.txt' % (a.rows, a.split), 'a') as f:
        f.write('\n'.join(msg) + '\n')


if __name__ == '__main__':
    main()
