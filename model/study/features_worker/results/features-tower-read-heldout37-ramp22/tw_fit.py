"""Fits the tower models on the corpus walks and scores every held step of every seed.

  tw_fit.py [--refit]

Reads R/walks/corpus.jsonl (989 stems x 4 seeds, every step). Fits M0, M1, M2A, M2B, M2M, M3 with alpha per model and factor chosen by 5-fold CV over
stems (fold = int(sha1(stem)[:8], 16) % 5), and M2A, M2B again with the state permuted within each corpus walk (scored with the true state). Writes
R/fit.json. Then, for each held task whose 16 walks are in R/walks/held.jsonl and that has no finished file yet, scores its steps and writes
R/tower/<task>.jsonl: bits of both factors of each model, of the fit-shuffled models, and the mean over 20 read-time permutations of the state.
A rerun uses the alphas of R/fit.json (--refit chooses them again) and skips the held tasks done.
"""
import argparse
import collections
import json
import os
import random
import sys
import time

import numpy as np

import tw_lib as T

L = T.L
N_PERM = 20


def load_walks(fn):
    steps, walks = [], {}
    for x in T.read_lines(fn):
        if x.get('rec') == 'walk':
            walks[(x['task'], x['seed'])] = x['steps']
        elif 'facts' in x:
            steps.append(dict(task=x['task'], seed=x['seed'], t=x['t'], key_f=x['key_f'], facts=x['facts'], kind_f=x['kind_f'], shape=x['shape'], pattern=x['pattern']))
    return steps, walks


def permute_state(cols, groups, tag):
    """cols with prev permuted within each group (the steps t >= 1 of a walk), and sA, sB recomputed."""
    prev = cols['prev'].copy()
    for gi, idx in groups.items():
        rng = random.Random('%s %s' % (tag, gi))
        p = list(range(len(idx)))
        rng.shuffle(p)
        prev[idx] = cols['prev'][idx[p]]
    out = dict(cols)
    out['prev'] = prev
    return T.set_state(out)


def groups_of(keys, ts):
    """Indices by key, over the steps t >= 1: the state START of step 0 is a function of the facts there, so a permutation leaves it in place."""
    g = collections.defaultdict(list)
    for i, (k, t) in enumerate(zip(keys, ts)):
        if t >= 1:
            g[k].append(i)
    return {k: np.array(v) for k, v in g.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--refit', action='store_true')
    a = ap.parse_args()
    T.setup(engine=False)
    t0 = time.time()
    steps, walks = load_walks(T.R + '/walks/corpus.jsonl')
    stems = T.tasks_of('corpus')
    missing = [(s, k) for s in stems for k in range(4) if (s, k) not in walks]
    if missing:
        sys.exit('corpus walks incomplete: %d of %d walks missing; run tw_walks.py --set corpus --seeds 4' % (len(missing), 4 * len(stems)))
    n_all = len(steps)
    steps = [s for s in steps if s['shape'] is not None and s['task'] in set(stems)]
    fit_stems = sorted({s['task'] for s in steps})
    # K5: no held task enters the fit
    held_out = set(L.read_lines(L.EVAL_TASKS)) | set(L.ramp_tasks()) | set(L.held_tasks())
    assert not (set(fit_stems) & held_out), 'K5 FAIL: a held stem is in the fit: %s' % sorted(set(fit_stems) & held_out)[:5]
    print('K5 PASS: fit on %d stems (%d steps, %d without a shape row left out of %d); none in eval-tasks.txt (%d), the ramp (22) or the 37' % (
        len(fit_stems), len(steps), n_all - len(steps), n_all, len(set(L.read_lines(L.EVAL_TASKS)))), flush=True)
    shapes = sorted({s['shape'] for s in steps})
    sidx = {s: i for i, s in enumerate(shapes)}
    Vs, Vp = len(shapes) + 1, len(T.PATTERNS)
    cols = T.columns(steps, sidx)
    folds = np.array([T.fold_of(s['task']) for s in steps])
    groups = groups_of([(s['task'], s['seed']) for s in steps], [s['t'] for s in steps])
    cols_s = permute_state(cols, groups, 'fit-shuffle')
    print('columns built, %.1f s' % (time.time() - t0), flush=True)
    fit_fn = T.R + '/fit.json'
    cached = json.load(open(fit_fn)) if os.path.exists(fit_fn) and not a.refit else None
    if cached and cached.get('n_rows') != len(steps):
        cached = None
    alphas, cv, cv_fs = {}, {}, {}
    keys = {}
    for m in T.TOWER_MODELS:
        keys[m] = (T.level_keys(cols, T.SHAPE_LEVELS[m]), T.level_keys(cols, T.PATTERN_LEVELS[m]), cols['y_shape'], cols['y_pat'])
    fs_keys = {m: (T.level_keys(cols_s, T.SHAPE_LEVELS[m]), T.level_keys(cols_s, T.PATTERN_LEVELS[m])) for m in T.FS_MODELS}
    for m in T.TOWER_MODELS:
        Ks, Kp, ys, yp = keys[m]
        if cached:
            alphas[m], cv[m] = cached['alphas'][m], cached['cv'][m]
        else:
            (a_s, b_s, _), (a_p, b_p, _) = T.cv_alpha(Ks, ys, Vs, folds), T.cv_alpha(Kp, yp, Vp, folds)
            alphas[m] = dict(shape=a_s, pattern=a_p)
            cv[m] = dict(shape=b_s, pattern=b_p, total=b_s + b_p)
            print('CV %-4s alpha shape %-5s pattern %-5s | CV bits shape %.3f pattern %.3f total %.3f | %.1f s' % (m, a_s, a_p, b_s, b_p, b_s + b_p, time.time() - t0), flush=True)
    for m in T.FS_MODELS:  # fit with the state permuted, scored with the true state, at the alpha of the true model
        Ks, Kp, ys, yp = keys[m]
        tot = {}
        for name, Kfit, Kscore, y, V in (('shape', fs_keys[m][0], Ks, ys, Vs), ('pattern', fs_keys[m][1], Kp, yp, Vp)):
            s = 0.0
            for f in range(5):
                tr, te = np.nonzero(folds != f)[0], np.nonzero(folds == f)[0]
                s += float(T.Backoff(V).fit(Kfit, y, tr).score(Kscore, y, te, alphas[m][name]).sum())
            tot[name] = s / len(y)
        cv_fs[m] = dict(tot, total=tot['shape'] + tot['pattern'])
        print('CV %-4s fit with the state permuted within each walk, scored with the true state: shape %.3f pattern %.3f total %.3f (M1 %.3f, %s %.3f)' % (
            m, tot['shape'], tot['pattern'], cv_fs[m]['total'], cv['M1']['total'], m, cv[m]['total']), flush=True)
    json.dump(dict(n_rows=len(steps), n_stems=len(fit_stems), n_steps_without_shape=n_all - len(steps), shapes=shapes, V_shape=Vs, V_pattern=Vp, alphas=alphas, cv=cv, cv_fs=cv_fs,
                   fit_stems=fit_stems, folds='int(sha1(stem)[:8], 16) % 5', date=time.strftime('%Y-%m-%d %H:%M:%S')), open(fit_fn, 'w'), indent=1)
    print('wrote fit.json, %.1f s' % (time.time() - t0), flush=True)

    # final fits on all corpus rows
    allr = np.arange(len(steps))
    fits = {m: (T.Backoff(Vs).fit(keys[m][0], keys[m][2], allr), T.Backoff(Vp).fit(keys[m][1], keys[m][3], allr)) for m in T.TOWER_MODELS}
    fits_fs = {m: (T.Backoff(Vs).fit(fs_keys[m][0], keys[m][2], allr), T.Backoff(Vp).fit(fs_keys[m][1], keys[m][3], allr)) for m in T.FS_MODELS}

    def bits(fit, m, cols_t, idx, models_fit=None):
        Ks, Kp = T.level_keys(cols_t, T.SHAPE_LEVELS[m]), T.level_keys(cols_t, T.PATTERN_LEVELS[m])
        return fit[0].score(Ks, cols_t['y_shape'], idx, alphas[m]['shape']), fit[1].score(Kp, cols_t['y_pat'], idx, alphas[m]['pattern'])

    # held tasks
    held_steps, held_walks = load_walks(T.R + '/walks/held.jsonl')
    by_task = collections.defaultdict(list)
    for s in held_steps:
        by_task[s['task']].append(s)
    tasks = T.tasks_of('held')
    sig = T.hashlib.sha1(json.dumps([alphas, len(steps), len(shapes)], sort_keys=True).encode()).hexdigest()[:12]  # the tower files of an older fit are scored again
    os.makedirs(T.R + '/tower', exist_ok=True)
    todo, waiting = [], []
    for task in tasks:
        fn = '%s/tower/%s.jsonl' % (T.R, task)
        if any(x.get('rec') == 'task_done' and x.get('fit') == sig for x in T.read_lines(fn)):
            continue
        if all((task, s) in held_walks for s in range(T.NSEED_HELD)):
            todo.append(task)
        else:
            waiting.append(task)
    print('held: %d tasks, %d to score, %d waiting for walks (run tw_shapes_all.sh, then tw_walks.py --set held --seeds 16, then this again)' % (len(tasks), len(todo), len(waiting)), flush=True)
    t1 = time.time()
    for c, task in enumerate(todo):
        st = sorted(by_task[task], key=lambda s: (s['seed'], s['t']))
        ct = T.columns(st, sidx)
        idx = np.arange(len(st))
        res = {m: bits(fits[m], m, ct, idx) for m in T.TOWER_MODELS}
        res_fs = {m: bits(fits_fs[m], m, ct, idx) for m in T.FS_MODELS}
        gr = groups_of([s['seed'] for s in st], [s['t'] for s in st])
        rt = {m: [np.zeros(len(st)), np.zeros(len(st))] for m in T.FS_MODELS}
        for p in range(N_PERM):
            cp = permute_state(ct, gr, '%s read-time %d' % (task, p))
            for m in T.FS_MODELS:
                b = bits(fits[m], m, cp, idx)
                rt[m][0] += b[0] / N_PERM
                rt[m][1] += b[1] / N_PERM
        tmp = '%s/tower/%s.jsonl.tmp' % (T.R, task)
        with open(tmp, 'w') as fh:
            for i, s in enumerate(st):
                T.append_line(fh, dict(
                    task=task, seed=s['seed'], t=s['t'], key_f=s['key_f'], kind=s['kind_f'],
                    bits={m: [round(float(res[m][0][i]), 4), round(float(res[m][1][i]), 4)] for m in T.TOWER_MODELS},
                    fs={m: [round(float(res_fs[m][0][i]), 4), round(float(res_fs[m][1][i]), 4)] for m in T.FS_MODELS},
                    rt={m: [round(float(rt[m][0][i]), 4), round(float(rt[m][1][i]), 4)] for m in T.FS_MODELS}))
            T.append_line(fh, dict(rec='task_done', task=task, steps=len(st), fit=sig))
        os.replace(tmp, '%s/tower/%s.jsonl' % (T.R, task))
        el = time.time() - t1
        print('[%d/%d] %s %d steps scored | %.2f s a task, ETA %.0f s' % (c + 1, len(todo), task, len(st), el / (c + 1), el / (c + 1) * (len(todo) - c - 1)), flush=True)
    print('done, %.1f s' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
