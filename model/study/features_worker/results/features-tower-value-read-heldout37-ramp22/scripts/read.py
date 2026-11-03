"""Read the fit value, the shipped node score and the depth-only control against the label on the read set (bundle arm of round 1).

  <engine python> -I read.py [--only TASK ...] [--boot N] [--out FILE]

Needs rows/read/*.npz (build_labels.py), rows/read_x/*.progress.json with done=true (build_rows.py) and models/value.pkl, models/depth.pkl (fit.py). A run without finished
T rows is left out and listed. Groups: 37 and ramp, apart.
Metrics, per group and per label subset (all nodes; nodes with exposure of 1 or more):
  AUC per run (runs with both classes) then the median; AUC pooled over the group's nodes.
  Ranks: for each first cover per gold form (an event: cover node c at time t), the pool is the nodes of id up to c (exposure subset: nodes first held by a scope at or before t); the
  positives are the nodes that have c among their cover ids (ancestors of c and c). Rank 1 is the highest score, ties get the middle rank. Reported over the (event, positive) pairs:
  median rank, share of pairs at rank 10 or better, share at rank 100 or better. 'strict' leaves out c itself. Rank gain is node score minus value for the median rank, value minus node score for the shares.
  95% intervals: bootstrap over tasks (resample tasks with replacement; a task keeps its runs and events).
"""
import argparse
import glob
import json
import os
import pickle
import sys
import time

import numpy as np

sys.dont_write_bytecode = True
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-tower-value-read-heldout37-ramp22/scripts'  # the data folder
sys.path.insert(0, HERE)
import common as C

ap = argparse.ArgumentParser()
ap.add_argument('--only', nargs='*')
ap.add_argument('--boot', type=int, default=300)
ap.add_argument('--out', default=C.REC + '/results.json')
ap.add_argument('--model', default='value')
ap.add_argument('--depth-model', default='depth')
ap.add_argument('--groups', nargs='*', default=['37', 'ramp'])
ap.add_argument('--fit-line', default='')
a = ap.parse_args()
SCORES = ['value', 'ship', 'depth']
rng = np.random.default_rng(0)


def auc(y, s):
    """Rank AUC with middle ranks for ties; None where a class is empty."""
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return None
    order = np.argsort(s, kind='mergesort')
    ss = s[order]
    r = np.empty(len(s))
    # middle ranks
    starts = np.r_[0, np.flatnonzero(np.diff(ss)) + 1]
    ends = np.r_[starts[1:], len(ss)]
    mid = (starts + ends + 1) / 2.0
    r[order] = np.repeat(mid, ends - starts)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def load_x(task, seed, ids):
    prog = json.load(open('%s/rows/read_x/%s_%s.progress.json' % (C.REC, task, seed)))
    if not prog['done']:
        return None
    pos = {int(n): i for i, n in enumerate(ids)}
    names = None
    X = None
    code = np.full(len(ids), 3)
    for p in sorted(glob.glob('%s/rows/read_x/%s_%s.part*.npz' % (C.REC, task, seed))):
        r = np.load(p, allow_pickle=False)
        names = list(r['names'])
        if X is None:
            X = np.full((len(ids), len(names)), np.nan, np.float32)
        for row, n in enumerate(r['meta'][:, 0]):
            X[pos[int(n)]] = r['X'][row]
            code[pos[int(n)]] = r['meta'][row, 2]
    return names, X, code


def rank_of(s_pool, s_pos):
    """Middle rank of each value of s_pos within s_pool (which holds them)."""
    gt = (s_pool[None, :] > s_pos[:, None]).sum(1)
    eq = (s_pool[None, :] == s_pos[:, None]).sum(1)
    return 1 + gt + (eq - 1) / 2.0


def main():
    value = pickle.load(open('%s/models/%s.pkl' % (C.REC, a.model), 'rb'))
    depth = pickle.load(open('%s/models/%s.pkl' % (C.REC, a.depth_model), 'rb'))
    print('value model %s: fit on %d rows, %d positives, %d tasks' % (a.model, value['n_rows'], value['n_pos'], len(value['tasks'])))
    # no fit task may be a task that is read, or a task of the 99
    read_tasks = set()
    for group, seed, task, base in C.read_runs():
        if group in a.groups:
            read_tasks.add(task)
    assert not (set(value['tasks']) & (read_tasks | set(C.words(C.E99)))), 'a fit task is read or in the 99'
    runs = []
    left_out = []
    for group, seed, task, base in C.read_runs():
        if (a.only and task not in a.only) or group not in a.groups:
            continue
        z = np.load('%s/rows/read/%s_%s.npz' % (C.REC, task, seed))
        ev = json.load(open('%s/rows/read/%s_%s.json' % (C.REC, task, seed)))
        lx = load_x(task, seed, z['node']) if os.path.exists('%s/rows/read_x/%s_%s.progress.json' % (C.REC, task, seed)) else None
        if lx is None:
            left_out.append((group, task, seed))
            continue
        names, X, code = lx
        tw = np.stack([z[nm] for nm in C.TOWER_NAMES], 1).astype(np.float32)
        XT = np.hstack([X, tw])
        assert names + C.TOWER_NAMES == value['features']
        sv = value['model'].predict_proba(XT)[:, 1]
        sd = depth['model'].predict_proba(tw[:, [C.TOWER_NAMES.index('t_depth')]])[:, 1]
        runs.append(dict(group=group, task=task, seed=seed, ids=z['node'], y=z['label'].astype(int), exp=z['exposure'], fexp=z['first_exposed_time'],
                         s=dict(value=sv, ship=z['score'], depth=sd), cover_ids=[json.loads(c) for c in z['cover_ids']], events=ev['events'], no_table=int((code == 3).sum())))
    print('runs read', len(runs), 'left out (no finished T rows)', len(left_out))
    if not runs:
        return
    res = dict(fit_set=a.fit_line, groups_read=a.groups, value_model=dict(n_rows=value['n_rows'], n_pos=value['n_pos'], tasks=len(value['tasks']), settings=value['settings']), runs_read=len(runs), left_out=left_out, groups={})
    for group in a.groups:
        rs = [r for r in runs if r['group'] == group]
        if not rs:
            continue
        res['groups'][group] = {}
        for subset in ('all', 'exposed'):
            res['groups'][group][subset] = read_group(rs, subset)
    res['exposed_pool_check'] = dict(events=CHK['events'], events_with_cover_node_in_exposed_pool=CHK['cover_in_pool'],
                                     note='In the exposed pool a node counts when a scope held it at or before the cover time. A cover node is built at that time, so it is not in the pool, and the strict and all rows of the exposed subset are the same pairs: ancestors only. The code leaves the covering node out of the exposed positives, so the row is ancestors only by definition.')
    if '37' in res['groups']:
        g = res['groups']['37']
        res['headline'] = dict(
            what='ancestors-only rank on the 37 (strict rank, without the covering node), value against the node score, 95% interval by task; then AUC',
            all_nodes_pool=dict(strict_rank={k: g['all']['ranks'][k + '_strict'] for k in SCORES}, gain_vs_ship_strict=g['all']['ci95_by_task']['ranks'].get('gain_vs_ship_strict_median'),
                                gain_top10_strict=g['all']['ci95_by_task']['ranks'].get('gain_vs_ship_strict_top10'), gain_top100_strict=g['all']['ci95_by_task']['ranks'].get('gain_vs_ship_strict_top100'),
                                ci_strict_median={k: g['all']['ci95_by_task']['ranks'].get(k + '_strict_median') for k in SCORES}),
            exposed_pool=dict(ancestors_only_rank={k: g['exposed']['ranks'][k + '_strict'] for k in SCORES}, gain_vs_ship_median=g['exposed']['ci95_by_task']['ranks'].get('gain_vs_ship_strict_median'),
                              gain_top10=g['exposed']['ci95_by_task']['ranks'].get('gain_vs_ship_strict_top10'), gain_top100=g['exposed']['ci95_by_task']['ranks'].get('gain_vs_ship_strict_top100'),
                              ci_median={k: g['exposed']['ci95_by_task']['ranks'].get(k + '_strict_median') for k in SCORES}),
            auc=dict(all_nodes=dict(median_per_run=g['all']['auc_median_per_run'], pooled=g['all']['auc_pooled'], ci_median=g['all']['ci95_by_task']['auc_median_per_run'], ci_pooled=g['all']['ci95_by_task']['auc_pooled'],
                                    value_minus_ship_ci=g['all']['ci95_by_task']['value_minus_ship_auc_median']),
                     exposed=dict(median_per_run=g['exposed']['auc_median_per_run'], pooled=g['exposed']['auc_pooled'], ci_median=g['exposed']['ci95_by_task']['auc_median_per_run'], ci_pooled=g['exposed']['ci95_by_task']['auc_pooled'],
                                  value_minus_ship_ci=g['exposed']['ci95_by_task']['value_minus_ship_auc_median'])))
    json.dump(res, open(a.out, 'w'), indent=1)
    print('wrote', a.out)


CHK = dict(events=0, cover_in_pool=0)


def run_ranks(r, subset):
    """{score: {'all': [ranks], 'strict': [ranks]}} over the (event, positive) pairs of a run."""
    out = {k: dict(all=[], strict=[]) for k in SCORES}
    ids = r['ids']
    for e in r['events']:
        c = e['node']
        in_pool = ids <= c
        if subset == 'exposed':
            in_pool &= (r['fexp'] <= e['time'])
            CHK['events'] += 1
            CHK['cover_in_pool'] += int(in_pool[ids == c].any())
        pos = np.array([c in cs for cs in r['cover_ids']]) & in_pool
        if subset == 'exposed':
            pos &= (ids != c)   # exposed positives are ancestors only
        if not pos.any():
            continue
        for k in SCORES:
            sp = r['s'][k][in_pool]
            rk = rank_of(sp, r['s'][k][pos])
            out[k]['all'] += list(rk)
            out[k]['strict'] += list(rk[ids[pos] != c])
    return out


def summ(v):
    v = np.asarray(v, float)
    if len(v) == 0:
        return dict(n=0)
    return dict(n=len(v), median=float(np.median(v)), top10=float((v <= 10).mean()), top100=float((v <= 100).mean()))


def read_group(rs, subset):
    tasks = sorted({r['task'] for r in rs})
    sel = {}
    for r in rs:
        m = np.ones(len(r['ids']), bool) if subset == 'all' else (r['exp'] >= 1)
        sel[id(r)] = m
    out = dict(runs=len(rs), tasks=len(tasks), nodes=int(sum(sel[id(r)].sum() for r in rs)), positives=int(sum(r['y'][sel[id(r)]].sum() for r in rs)))
    per_run = {k: [] for k in SCORES}
    per_run_task = []
    for r in rs:
        m = sel[id(r)]
        got = {k: auc(r['y'][m], r['s'][k][m]) for k in SCORES}
        if all(v is not None for v in got.values()):
            for k in SCORES:
                per_run[k].append(got[k])
            per_run_task.append(r['task'])
    out['runs_with_both_classes'] = len(per_run_task)
    out['auc_median_per_run'] = {k: float(np.median(per_run[k])) if per_run[k] else None for k in SCORES}
    pooled = {}
    for k in SCORES:
        y = np.concatenate([r['y'][sel[id(r)]] for r in rs])
        s = np.concatenate([r['s'][k][sel[id(r)]] for r in rs])
        pooled[k] = auc(y, s)
    out['auc_pooled'] = pooled
    # ranks
    rr = {r_id: None for r_id in []}
    ranks = {}
    for r in rs:
        ranks[id(r)] = run_ranks(r, subset)
    def rank_table(rsel):
        t = {}
        for k in SCORES:
            for kind in ('all', 'strict'):
                v = [x for r in rsel for x in ranks[id(r)][k][kind]]
                t['%s_%s' % (k, kind)] = summ(v)
        return t
    out['ranks'] = rank_table(rs)
    # bootstrap over tasks
    by_task = {t: [r for r in rs if r['task'] == t] for t in tasks}
    B = a.boot
    boot = {'auc_med': {k: [] for k in SCORES}, 'auc_pool': {k: [] for k in SCORES}, 'd_med': [], 'd_pool': [], 'rank': {}}
    t0 = time.time()
    for b in range(B):
        pick = rng.choice(len(tasks), len(tasks))
        rsel = [r for i in pick for r in by_task[tasks[i]]]
        pm = {k: [] for k in SCORES}
        for r in rsel:
            m = sel[id(r)]
            got = {k: auc(r['y'][m], r['s'][k][m]) for k in SCORES}
            if all(v is not None for v in got.values()):
                for k in SCORES:
                    pm[k].append(got[k])
        for k in SCORES:
            boot['auc_med'][k].append(np.median(pm[k]) if pm[k] else np.nan)
        pl = {}
        for k in SCORES:
            y = np.concatenate([r['y'][sel[id(r)]] for r in rsel])
            s = np.concatenate([r['s'][k][sel[id(r)]] for r in rsel])
            pl[k] = auc(y, s)
            boot['auc_pool'][k].append(pl[k] if pl[k] is not None else np.nan)
        boot['d_med'].append(boot['auc_med']['value'][-1] - boot['auc_med']['ship'][-1])
        boot['d_pool'].append(pl['value'] - pl['ship'] if pl['value'] is not None else np.nan)
        for kind in ('all', 'strict'):
            tv = {k: [x for r in rsel for x in ranks[id(r)][k][kind]] for k in SCORES}
            for k in SCORES:
                sm = summ(tv[k])
                for q in ('median', 'top10', 'top100'):
                    boot['rank'].setdefault('%s_%s_%s' % (k, kind, q), []).append(sm.get(q, np.nan))
            for q, sign in (('median', -1), ('top10', 1), ('top100', 1)):
                a1, a2 = boot['rank']['value_%s_%s' % (kind, q)][-1], boot['rank']['ship_%s_%s' % (kind, q)][-1]
                boot['rank'].setdefault('gain_vs_ship_%s_%s' % (kind, q), []).append(sign * (a1 - a2))
    ci = lambda v: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] if len(v) and not np.all(np.isnan(v)) else None
    out['ci95_by_task'] = dict(boot=B, boot_seconds=round(time.time() - t0, 1),
                               auc_median_per_run={k: ci(boot['auc_med'][k]) for k in SCORES}, auc_pooled={k: ci(boot['auc_pool'][k]) for k in SCORES},
                               value_minus_ship_auc_median=ci(boot['d_med']), value_minus_ship_auc_pooled=ci(boot['d_pool']),
                               ranks={k: ci(v) for k, v in boot['rank'].items()})
    out['value_minus_ship'] = dict(auc_median_per_run=None if None in (out['auc_median_per_run']['value'], out['auc_median_per_run']['ship']) else out['auc_median_per_run']['value'] - out['auc_median_per_run']['ship'],
                                   auc_pooled=None if None in (pooled['value'], pooled['ship']) else pooled['value'] - pooled['ship'])
    return out


main()
