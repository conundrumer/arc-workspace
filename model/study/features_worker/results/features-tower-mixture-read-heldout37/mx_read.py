"""Tower mixture read on the 37: p_mix(Y) = pi * p_tower(Y | EXTEND) + (1 - pi) * p_prop(Y), pi from a mode model fit on the corpus walks.

  mx_read.py [--rescore]

Design: design.md in this folder. Reads the tower read's records (TW) only. Writes steps.jsonl (one line per task), results.md and tables.json here.
A rerun skips the fit and the scoring when steps.jsonl has all 37 tasks with the same signature; --rescore does them again.
"""
import argparse
import collections
import hashlib
import json
import math
import os
import sys
import time

import numpy as np

R2 = os.path.dirname(os.path.abspath(__file__))
TW = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-read-heldout37-ramp22'
sys.dont_write_bytecode = True
sys.path.insert(0, TW)
import tw_lib as T  # noqa: E402

L = T.L
assert T.R == TW
MODELS = T.TOWER_MODELS
MAIN = 'M2A'
NB = 2000
ML = [tuple(T.FACT_NAMES), ('prev', 'm_band', 'chain_roots', 'h_kind', 'h_ident', 'h_nreads', 'n_open', 'ident_open'), ('prev', 'h_kind', 'h_nreads', 'n_open'), ('prev',), ()]
EXT_PAT = np.array([i for i, p in enumerate(T.PATTERNS) if p.startswith('EXTEND|')])
assert len(EXT_PAT) == 36
VERSION = 'mx1'


def fact_cols(steps):
    n = len(steps)
    return {name: np.fromiter((T.FACT_INDEX[name][s['facts'][name]] for s in steps), np.int64, n) for name in T.FACT_NAMES}


def load_walks(fn, keep):
    out = []
    for x in T.read_lines(fn):
        if 'facts' in x and keep(x):
            out.append(dict(task=x['task'], seed=x['seed'], t=x['t'], key_f=x['key_f'], facts=x['facts'], kind_f=x['kind_f'], shape=x['shape'], pattern=x['pattern'],
                            mode=x['mode'], place=x.get('place'), set=x.get('set')))
    return out


# ------------------------------------------------------------------ the mode model

def pi_of(fit, K, idx, alpha, m0):
    p = np.exp2(-fit.score(K, np.ones(len(m0), np.int64), idx, alpha))
    p = np.where(m0[idx], 0.0, p)
    return p


def logloss(p, y):
    q = np.where(y == 1, p, 1 - p)
    return -np.log2(np.clip(q, 1e-300, 1))


def mode_model(corpus, folds):
    cols = fact_cols(corpus)
    y = np.array([s['mode'] == 'EXTEND' for s in corpus], np.int64)
    m0 = cols['m_band'] == T.FACT_INDEX['m_band']['0']
    assert np.all(y[m0] == 0)
    K = T.level_keys(cols, ML)
    tot = {a: 0.0 for a in T.ALPHAS}
    for f in range(5):
        tr, te = np.nonzero(folds != f)[0], np.nonzero(folds == f)[0]
        b = T.Backoff(2).fit(K, y, tr)
        for a in T.ALPHAS:
            tot[a] += float(logloss(pi_of(b, K, te, a, m0), y[te]).sum())
    alpha = min(T.ALPHAS, key=lambda a: tot[a])
    fit = T.Backoff(2).fit(K, y, np.arange(len(y)))
    rest = ~m0
    const = float(y[rest].mean())
    return dict(fit=fit, alpha=alpha, cv={a: v / len(y) for a, v in tot.items()}, cv_best=tot[alpha] / len(y), const=const,
                const_cv=float(logloss(np.where(m0, 0.0, const), y).mean()), n=len(y), ext_share=float(y.mean()))


def score_pi(mm, steps):
    cols = fact_cols(steps)
    m0 = cols['m_band'] == T.FACT_INDEX['m_band']['0']
    K = T.level_keys(cols, ML)
    return pi_of(mm['fit'], K, np.arange(len(steps)), mm['alpha'], m0), m0


# ------------------------------------------------------------------ the restricted tower model

def tile_keys(K, reps):
    return [np.tile(k, reps) for k in K]


def tower_ext(fits, alphas, st, sidx, shapes):
    """Per model: gold's shape and pattern bits, Z (the EXTEND mass) and the sums of both factors."""
    n = len(st)
    ct = T.columns(st, sidx)
    Vs = len(shapes) + 1
    groups = sorted({(T.KIND_VALUES.index(s.split('|')[0]), T.I_ge1(s)) for s in shapes})
    gidx = {g: i for i, g in enumerate(groups)}
    shape_group = np.array([gidx[(T.KIND_VALUES.index(s.split('|')[0]), T.I_ge1(s))] for s in shapes])
    out = {}
    for m in MODELS:
        fs, fp = fits[m]
        a_s, a_p = alphas[m]['shape'], alphas[m]['pattern']
        Ks = T.level_keys(ct, T.SHAPE_LEVELS[m])
        Kp = T.level_keys(ct, T.PATTERN_LEVELS[m])
        idx = np.arange(n)
        gold_s = fs.score(Ks, ct['y_shape'], idx, a_s)
        gold_p = fp.score(Kp, ct['y_pat'], idx, a_p)
        # all shapes
        ys = np.repeat(np.arange(Vs), n)
        Ps = np.exp2(-fs.score(tile_keys(Ks, Vs), ys, np.arange(n * Vs), a_s)).reshape(Vs, n).T
        # EXTEND mass of the pattern factor, per (kind, I) group; all 216 patterns for the sum check
        E = np.zeros((n, len(groups)))
        psum = np.zeros((n, len(groups)))
        for g, (kv, iv) in enumerate(groups):
            cg = dict(ct)
            cg['kind'] = np.full(n, kv, np.int64)
            cg['I'] = np.full(n, iv, np.int64)
            Kg = T.level_keys(cg, T.PATTERN_LEVELS[m])
            pats = np.arange(len(T.PATTERNS)) if m == MAIN else EXT_PAT  # all 216 for the sum check of the main model only
            V = len(pats)
            yp = np.repeat(pats, n)
            P = np.exp2(-fp.score(tile_keys(Kg, V), yp, np.arange(n * V), a_p)).reshape(V, n).T
            E[:, g] = P[:, np.isin(pats, EXT_PAT)].sum(1)
            psum[:, g] = P.sum(1) if m == MAIN else 1.0
        seen = Ps[:, :Vs - 1]
        Z = (seen * E[:, shape_group]).sum(1) / seen.sum(1)
        out[m] = dict(gold_s=gold_s, gold_p=gold_p, Z=Z, shape_sum=Ps.sum(1), pat_sum=psum)
    return out


# ------------------------------------------------------------------ read helpers

def bits(p):
    return -math.log2(p) if p > 0 else float('inf')


def wmean(E, fn):
    s = sum(e['w'] for e in E)
    return sum(e['w'] * fn(e) for e in E) / s if s else float('nan')


def wmean_ci(E, fn):
    per = {}
    for e in E:
        v = per.setdefault(e['task'], np.zeros(2))
        v += (e['w'] * fn(e), e['w'])
    return T.bootstrap_tasks(per, lambda M: M[:, 0] / M[:, 1], NB)


def fmt(x, nd=2):
    return '-' if x is None or (isinstance(x, float) and math.isnan(x)) else ('%.' + str(nd) + 'f') % x


def fci(t, nd=2):
    return '-' if t is None or t[0] is None else '%s [%s, %s]' % (fmt(t[0], nd), fmt(t[1], nd), fmt(t[2], nd))


# ------------------------------------------------------------------ main

def compute(sig, out_fn):
    t0 = time.time()
    fitj = json.load(open(TW + '/fit.json'))
    fit_stems = set(fitj['fit_stems'])
    held_out = set(L.read_lines(L.EVAL_TASKS)) | set(L.ramp_tasks()) | set(L.held_tasks())
    assert not (fit_stems & held_out), 'a held stem is in the fit'
    corpus = [s for s in load_walks(TW + '/walks/corpus.jsonl', lambda x: x['task'] in fit_stems) if s['shape'] is not None]
    assert len(corpus) == fitj['n_rows'], (len(corpus), fitj['n_rows'])
    print('corpus rows %d over %d stems (none held out), %.1f s' % (len(corpus), len({s['task'] for s in corpus}), time.time() - t0), flush=True)
    folds = np.array([T.fold_of(s['task']) for s in corpus])

    mm = mode_model(corpus, folds)
    print('mode model: alpha %s, CV log loss %.4f bits (constant %.4f), %.1f s' % (mm['alpha'], mm['cv_best'], mm['const_cv'], time.time() - t0), flush=True)

    shapes = fitj['shapes']
    sidx = {s: i for i, s in enumerate(shapes)}
    cols = T.columns(corpus, sidx)
    allr = np.arange(len(corpus))
    Vs, Vp = len(shapes) + 1, len(T.PATTERNS)
    fits = {m: (T.Backoff(Vs).fit(T.level_keys(cols, T.SHAPE_LEVELS[m]), cols['y_shape'], allr),
                T.Backoff(Vp).fit(T.level_keys(cols, T.PATTERN_LEVELS[m]), cols['y_pat'], allr)) for m in MODELS}
    del cols
    print('tower models fit again, %.1f s' % (time.time() - t0), flush=True)

    tasks37 = set(L.held_tasks())
    held = load_walks(TW + '/walks/held.jsonl', lambda x: x['task'] in tasks37)
    # mode model on all seeds of the 37
    pi_all, _ = score_pi(mm, held)
    y_all = np.array([s['mode'] == 'EXTEND' for s in held], np.int64)
    ll_all = float(logloss(pi_all, y_all).mean())
    m0_all = np.array([s['facts']['m_band'] == '0' for s in held])
    ll_all_const = float(logloss(np.where(m0_all, 0.0, mm['const']), y_all).mean())

    st = sorted((s for s in held if s['seed'] == 0), key=lambda s: (s['task'], s['t']))
    pi0, _ = score_pi(mm, st)
    tw = tower_ext(fits, fitj['alphas'], st, sidx, shapes)
    print('restricted tower scored on %d seed-0 steps, %.1f s' % (len(st), time.time() - t0), flush=True)

    # refit check against TW/tower
    old = {}
    for task in tasks37:
        for x in T.read_lines('%s/tower/%s.jsonl' % (TW, task)):
            if 'bits' in x and x['seed'] == 0:
                old[(x['task'], x['t'])] = x['bits']
    maxdiff = 0.0
    for i, s in enumerate(st):
        b = old[(s['task'], s['t'])]
        for m in MODELS:
            maxdiff = max(maxdiff, abs(b[m][0] - tw[m]['gold_s'][i]), abs(b[m][1] - tw[m]['gold_p'][i]))
    print('refit against TW/tower: largest difference %.5f bits' % maxdiff, flush=True)
    if maxdiff > 1e-3:
        sys.exit('the refit differs from TW/tower by %.5f bits' % maxdiff)

    by_task = collections.defaultdict(list)
    for i, s in enumerate(st):
        rec = dict(t=s['t'], key_f=s['key_f'], kind=s['kind_f'], shape=s['shape'], pattern=s['pattern'], mode=s['mode'], place=s['place'],
                   unseen=s['shape'] not in sidx, pi=float(pi0[i]),
                   tower={m: dict(s=round(float(tw[m]['gold_s'][i]), 6), p=round(float(tw[m]['gold_p'][i]), 6), Z=float(tw[m]['Z'][i]),
                                  shape_sum=float(tw[m]['shape_sum'][i]), pat_sum_min=float(tw[m]['pat_sum'][i].min()), pat_sum_max=float(tw[m]['pat_sum'][i].max())) for m in MODELS})
        by_task[s['task']].append(rec)
    meta = dict(rec='meta', sig=sig, mode_alpha=mm['alpha'], mode_cv=mm['cv'], mode_cv_best=mm['cv_best'], mode_const=mm['const'], mode_const_cv=mm['const_cv'],
                mode_n=mm['n'], ll_all=ll_all, ll_all_const=ll_all_const, n_all=len(held), maxdiff=maxdiff, n_fit_stems=len(fit_stems))
    with open(out_fn, 'w') as fh:
        T.append_line(fh, meta)
        for k, task in enumerate(sorted(by_task)):
            T.append_line(fh, dict(rec='task', sig=sig, task=task, steps=by_task[task]))
            print('[%d/%d] %s %d steps written' % (k + 1, len(by_task), task, len(by_task[task])), flush=True)
    print('scoring done, %.1f s' % (time.time() - t0), flush=True)


def read(out_fn):
    meta, steps = None, {}
    for x in T.read_lines(out_fn):
        if x.get('rec') == 'meta':
            meta = x
        elif x.get('rec') == 'task':
            steps[x['task']] = x['steps']
    # proposal rows and weights, as Table 1 of TW
    rows = {}
    for task in steps:
        for x in T.read_lines('%s/held/%s.jsonl' % (TW, task)):
            if 't' in x and 'p_kind' in x:
                rows[(task, x['t'])] = x
    N, Dn = collections.Counter(), collections.Counter()
    for task, ss in steps.items():
        for s in ss:
            if s['kind'] != 'OTHER':
                N[(task, s['place'], T.mode_class(s['mode']))] += 1
    for r in rows.values():
        Dn[(r['task'], r['place'], T.mode_class(r['mode']))] += 1
    E, left = [], collections.Counter()
    for task, ss in steps.items():
        for s in ss:
            r = rows.get((task, s['t']))
            if r is None:
                if s['kind'] != 'OTHER':
                    left['no proposal row'] += 1
                continue
            assert r['key_f'] == s['key_f'] and r['pattern'] == s['pattern'] and r['mode'] == s['mode']
            if r['p_kind'] <= 0 or r['n'] == 0:
                left['P_kind = 0'] += 1
                continue
            ext = s['mode'] == 'EXTEND'
            assert ext == (s['pattern'].split('|')[0] == 'EXTEND')
            pp = r['p_kind'] * (r['h_joint'] + .5) / (r['n'] + 1)
            key = (task, r['place'], T.mode_class(r['mode']))
            e = dict(task=task, t=s['t'], w=N[key] / Dn[key], mc=T.mode_class(s['mode']), hj=r['h_joint'], pi=s['pi'], ext=ext, unseen=s['unseen'], prop=bits(pp), mix={}, orc={}, tower={})
            for m in T.TOWER_MODELS:
                tm = s['tower'][m]
                pt = 2 ** -(tm['s'] + tm['p']) / tm['Z'] if ext else 0.0
                e['tower'][m] = tm['s'] + tm['p']
                e['mix'][m] = bits(s['pi'] * pt + (1 - s['pi']) * pp)
                e['orc'][m] = bits(pt) if ext else bits(pp)
            E.append(e)
    return meta, steps, E, left


def report(meta, steps, E, left):
    lines = ['# Tower mixture read, held-out 37', '', 'Design: `%s/design.md`. Tower read: `%s`.' % (R2, TW), '']
    tj = {}
    allsteps = [s for ss in steps.values() for s in ss]
    sums_s = [s['tower'][m]['shape_sum'] for s in allsteps for m in MODELS]
    sums_p = [v for s in allsteps for m in MODELS for v in (s['tower'][m]['pat_sum_min'], s['tower'][m]['pat_sum_max'])]
    dev = max(max(abs(v - 1) for v in sums_s), max(abs(v - 1) for v in sums_p))
    lines += ['## Data check', '',
              '- Steps used: %d of the seed-0 walks of %d tasks; left out: %s.' % (len(E), len({e['task'] for e in E}), dict(left) or 'none'),
              '- Steps with an unseen gold shape: %d. Steps with h_joint = 0: %d.' % (sum(1 for e in E if e['unseen']), sum(1 for e in E if e['hj'] == 0)),
              '- Largest distance from 1 of the sum of the shape factor (all models) or the pattern factor (%s, all 216 patterns): %.1e.' % (MAIN, dev),
              '- Largest difference of the refit tower models from `TW/tower/`: %.5f bits.' % meta['maxdiff'],
              '- Mode model fit on %d corpus rows of %d stems; none in eval-tasks.txt, the ramp or the 37.' % (meta['mode_n'], meta['n_fit_stems']), '']
    assert dev < 1e-6, dev

    # Table 1
    lines += ['## Table 1, bits per form, the 37', '',
              'Saving = proposal bits minus the row\'s bits. Weighted mean over the done steps of the seed-0 walk, interval by task (2,000 draws), as Table 1 of the tower read. '
              'Mixture: pi from the mode model. Oracle: pi = 1 where gold\'s mode is EXTEND, else 0. The tower model under EXTEND is the named model restricted to EXTEND patterns and renormalised.', '',
              '| row | bits mean | saving against the proposal | saving, steps with h_joint >= 1 |', '|---|---|---|---|']
    hit = [e for e in E if e['hj'] >= 1]
    lines.append('| proposal | %s | - | - |' % fmt(wmean(E, lambda e: e['prop'])))
    t1 = {'proposal': wmean(E, lambda e: e['prop'])}
    order = [MAIN] + [m for m in MODELS if m != MAIN]
    for m in order:
        for name, key in (('mixture', 'mix'), ('oracle', 'orc')):
            sv = wmean_ci(E, lambda e: e['prop'] - e[key][m])
            sh = wmean_ci(hit, lambda e: e['prop'] - e[key][m])
            t1['%s %s' % (name, m)] = dict(mean=wmean(E, lambda e: e[key][m]), saving=sv, saving_hit=sh)
            lines.append('| %s, %s | %s | %s | %s |' % (name, m, fmt(t1['%s %s' % (name, m)]['mean']), fci(sv), fci(sh)))
        sv = wmean_ci(E, lambda e: e['prop'] - e['tower'][m])
        lines.append('| %s alone (unrestricted, for reference) | %s | %s | - |' % (m, fmt(wmean(E, lambda e: e['tower'][m])), fci(sv)))
        t1['%s alone' % m] = dict(mean=wmean(E, lambda e: e['tower'][m]), saving=sv)
    tj['table1'] = t1

    # Table 2
    lines += ['', '## Table 2, by gold\'s mode, %s' % MAIN, '',
              '| gold\'s mode | steps | proposal bits | mean pi | saving of the mixture | saving of the oracle |', '|---|---|---|---|---|---|']
    t2 = {}
    for mc in ('EXTEND', 'BACKTRACK', 'JUMP'):
        sub = [e for e in E if e['mc'] == mc]
        row = dict(n=len(sub), prop=wmean(sub, lambda e: e['prop']), pi=wmean(sub, lambda e: e['pi']),
                   mix=wmean_ci(sub, lambda e: e['prop'] - e['mix'][MAIN]), orc=wmean_ci(sub, lambda e: e['prop'] - e['orc'][MAIN]))
        t2[mc] = row
        lines.append('| %s | %d | %s | %s | %s | %s |' % (mc, row['n'], fmt(row['prop']), fmt(row['pi']), fci(row['mix']), fci(row['orc'])))
    tj['table2'] = t2

    # Table 3
    y = np.array([e['ext'] for e in E], int)
    p = np.array([e['pi'] for e in E])
    w = np.array([e['w'] for e in E])
    ll = logloss(p, y)
    t0m = np.array([e['t'] == 0 for e in E])
    llc = logloss(np.where(t0m, 0.0, meta['mode_const']), y)
    lines += ['', '## Table 3, the mode model', '',
              'Target: gold\'s mode is EXTEND. Log loss in bits per step. The constant reference is pi = the corpus EXTEND share over steps t >= 1 (%.3f), and 0 at step 0.' % meta['mode_const'], '',
              '| set | steps | log loss, mode model | log loss, constant |', '|---|---|---|---|',
              '| corpus, 5-fold CV (alpha %s) | %d | %.4f | %.4f |' % (meta['mode_alpha'], meta['mode_n'], meta['mode_cv_best'], meta['mode_const_cv']),
              '| the 37, the %d read steps (seed 0, weighted) | %d | %.4f | %.4f |' % (len(E), len(E), float((w * ll).sum() / w.sum()), float((w * llc).sum() / w.sum())),
              '| the 37, all steps of seeds 0 to 15 | %d | %.4f | %.4f |' % (meta['n_all'], meta['ll_all'], meta['ll_all_const']), '',
              'Calibration on the read steps (raw counts):', '', '| pi | steps | mean pi | EXTEND share |', '|---|---|---|---|']
    cal = []
    for b in range(10):
        lo, hi = b / 10, (b + 1) / 10
        sel = (p >= lo) & ((p < hi) if b < 9 else (p <= 1))
        if sel.sum():
            cal.append(dict(bin='%.1f-%.1f' % (lo, hi), n=int(sel.sum()), pi=float(p[sel].mean()), share=float(y[sel].mean())))
            lines.append('| %s | %d | %.3f | %.3f |' % (cal[-1]['bin'], cal[-1]['n'], cal[-1]['pi'], cal[-1]['share']))
    tj['table3'] = dict(cv=meta['mode_cv'], alpha=meta['mode_alpha'], cv_best=meta['mode_cv_best'], const_cv=meta['mode_const_cv'],
                        held=float((w * ll).sum() / w.sum()), held_const=float((w * llc).sum() / w.sum()), all_seeds=meta['ll_all'], all_seeds_const=meta['ll_all_const'], calibration=cal)

    # verdict
    sv = t1['mixture %s' % MAIN]['saving']
    ok = sv[1] is not None and sv[1] > 0
    tj['verdict'] = dict(saves=ok)
    lines += ['', '## Verdict', '']
    if ok:
        lines.append('- The mixture with %s saves %s bits per form against the proposal on the 37 (interval above 0). The oracle mode gives %s.' % (MAIN, fci(sv), fci(t1['oracle %s' % MAIN]['saving'])))
    else:
        lines.append('- The mixture with %s saves %s bits per form against the proposal on the 37; the interval is not above 0, so this line stops.' % (MAIN, fci(sv)))
    lines += ['', '## Limits',
              '- The read measures draw distributions at gold\'s step in the round-0 walk, not the search\'s order. Neither side pays the walk\'s own choice bits.',
              '- The proposal\'s bits are a lower bound at steps with h_joint = 0, so the saving there is a lower bound.',
              '- The proposal part of the mixture is the plain proposal, with its mass on EXTEND outcomes. Its draws are of gold\'s kind only, so these records can\'t restrict it to non-EXTEND outcomes.',
              '- The oracle is pi from a perfect mode model, not the best pi at each step.',
              '- The mode model\'s alpha is chosen from {%s}. Its CV log loss by alpha: %s.' % (', '.join(str(a) for a in T.ALPHAS), ', '.join('%s: %.4f' % (a, v) for a, v in meta['mode_cv'].items())), '']
    open(R2 + '/results.md', 'w').write('\n'.join(lines))
    json.dump(tj, open(R2 + '/tables.json', 'w'), indent=1, default=float)
    print('\n'.join(lines))
    print('wrote %s/results.md and tables.json' % R2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rescore', action='store_true')
    a = ap.parse_args()
    fitj = json.load(open(TW + '/fit.json'))
    sig = hashlib.sha1(json.dumps([VERSION, fitj['alphas'], fitj['n_rows'], ML, list(T.ALPHAS)], sort_keys=True).encode()).hexdigest()[:12]
    out_fn = R2 + '/steps.jsonl'
    done = {x['task'] for x in T.read_lines(out_fn) if x.get('rec') == 'task' and x.get('sig') == sig}
    has_meta = any(x.get('rec') == 'meta' and x.get('sig') == sig for x in T.read_lines(out_fn))
    if a.rescore or not has_meta or done != set(L.held_tasks()):
        compute(sig, out_fn)
    else:
        print('steps.jsonl has all %d tasks with signature %s; scoring skipped' % (len(done), sig), flush=True)
    report(*read(out_fn))
    return 0


if __name__ == '__main__':
    sys.exit(main())
