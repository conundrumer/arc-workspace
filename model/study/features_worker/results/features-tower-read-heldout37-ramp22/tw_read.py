"""Reads R/walks, R/tower, R/held and R/fit.json and writes R/tables.json and R/results.md.

  tw_read.py [--held-dir DIR] [--out-dir DIR]

Prints the data check first. "Bits" are bits per form, a weighted mean over the done steps of the walk of seed 0 (weight = steps in the task's
stratum / done steps in it); each interval is the 2.5% and 97.5% points of 2,000 bootstrap draws over tasks.
"""
import argparse
import collections
import json
import math
import os
import sys

import numpy as np

import tw_lib as T
from tw_held import pick_pass1

L = T.L
MODELS = T.TOWER_MODELS
PLACES = ('root', 'chain step', 'join', 'top join')
MCLASS = ('EXTEND', 'BACKTRACK', 'JUMP')
NB = 2000


def mean_of(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float('nan')


def fmt(x, nd=2):
    return '-' if x is None or (isinstance(x, float) and math.isnan(x)) else ('%.' + str(nd) + 'f') % x


def fci(t, nd=2):
    return '-' if t is None or t[0] is None else '%s [%s, %s]' % (fmt(t[0], nd), fmt(t[1], nd), fmt(t[2], nd))


def wmean_ci(entries, fn):
    """(mean, lo, hi) of fn over entries, weight e['w'], bootstrap over tasks."""
    per = {}
    for e in entries:
        v = per.setdefault(e['task'], np.zeros(2))
        v += (e['w'] * fn(e), e['w'])
    return T.bootstrap_tasks(per, lambda M: M[:, 0] / M[:, 1], NB)


def wmedian(entries, fn):
    if not entries:
        return float('nan')
    xs = sorted((fn(e), e['w']) for e in entries)
    half, acc = sum(w for _, w in xs) / 2, 0
    for v, w in xs:
        acc += w
        if acc >= half:
            return v
    return xs[-1][0]


def wmean(entries, fn):
    s = sum(e['w'] for e in entries)
    return sum(e['w'] * fn(e) for e in entries) / s if s else float('nan')


# ------------------------------------------------------------------ load

def load(held_dir):
    walks = collections.defaultdict(list)  # (task, seed) -> steps
    for fn in ('held', 'corpus'):
        for x in T.read_lines('%s/walks/%s.jsonl' % (T.R, fn)):
            if 'facts' in x:
                walks[(x['set'], x['task'], x['seed'])].append(dict(
                    task=x['task'], seed=x['seed'], t=x['t'], set=x['set'], kind=x['kind_f'], kind_f=x['kind_f'], mode=x['mode'], place=x['place'], pattern=x['pattern'], shape=x['shape'],
                    walk_bits=x['walk_bits'], prev=x['facts']['prev']))
    tower = {}
    tdir = T.R + '/tower'
    for fn in sorted(os.listdir(tdir)) if os.path.isdir(tdir) else []:
        if fn.endswith('.jsonl'):
            for x in T.read_lines(tdir + '/' + fn):
                if 'bits' in x:
                    tower[(x['task'], x['seed'], x['t'])] = x
    rows = {}
    if os.path.isdir(held_dir):
        for fn in sorted(os.listdir(held_dir)):
            if fn.endswith('.jsonl'):
                for x in T.read_lines(held_dir + '/' + fn):
                    if 't' in x and 'p_kind' in x:
                        rows[(x['task'], x['t'])] = x
    return walks, tower, rows


def mode6(pattern):
    return pattern.split('|')[0]


# ------------------------------------------------------------------ entries

def proposal_bits(r):
    n, pk = r['n'], r['p_kind']
    tot = -math.log2(pk * (r['h_joint'] + .5) / (n + 1))
    shp = -math.log2(pk * (r['h_shape'] + .5) / (n + 1))
    return tot, shp, tot - shp


def done_entries(st, walks, tower, rows):
    """The done steps of set st with a draw rate and tower bits, with their weights."""
    seed0 = {k[1]: v for k, v in walks.items() if k[0] == st and k[2] == 0}
    N = collections.Counter()
    for task, steps in seed0.items():
        for s in steps:
            if s['kind'] != 'OTHER':
                N[(task, s['place'], T.mode_class(s['mode']))] += 1
    Dn = collections.Counter()
    for r in rows.values():
        if r['set'] == st:
            Dn[(r['task'], r['place'], T.mode_class(r['mode']))] += 1
    out, left_out = [], collections.Counter()
    for r in rows.values():
        if r['set'] != st:
            continue
        key = (r['task'], r['place'], T.mode_class(r['mode']))
        tw = tower.get((r['task'], 0, r['t']))
        if r['p_kind'] <= 0 or r['n'] == 0:
            left_out['P_kind = 0'] += 1
            continue
        if tw is None:
            left_out['no tower row'] += 1
            continue
        tot, shp, pat = proposal_bits(r)
        M = {m: (tw['bits'][m][0], tw['bits'][m][1]) for m in MODELS}
        out.append(dict(task=r['task'], t=r['t'], w=N[key] / Dn[key], place=r['place'], mc=T.mode_class(r['mode']), hj=r['h_joint'], kind=r['kind'], shape=r['shape'],
                        mode6=mode6(r['pattern']), P=(shp, pat), M=M, fs=tw['fs'], rt=tw['rt']))
    return out, left_out, N, Dn


def tower_entries(st, walks, tower):
    out = []
    for (s, task, seed), steps in walks.items():
        if s != st:
            continue
        for x in steps:
            tw = tower.get((task, seed, x['t']))
            if tw and x['kind'] != 'OTHER':
                out.append(dict(task=task, seed=seed, w=1.0, place=x['place'], M={m: tuple(tw['bits'][m]) for m in MODELS}, fs=tw['fs'], rt=tw['rt']))
    return out


def tot(pair):
    return pair[0] + pair[1]


# ------------------------------------------------------------------ the tables

def table1(E, lines, tj, name):
    lines += ['', '### Table 1, bits per form: %s' % name, '',
              '| model | bits mean | bits median | shape part | pattern part | saving against the proposal | saving, steps with h_joint >= 1 |', '|---|---|---|---|---|---|---|']
    hit = [e for e in E if e['hj'] >= 1]
    t1 = {}
    lines.append('| proposal | %s | %s | %s | %s | - | - |' % (fmt(wmean(E, lambda e: tot(e['P']))), fmt(wmedian(E, lambda e: tot(e['P']))), fmt(wmean(E, lambda e: e['P'][0])), fmt(wmean(E, lambda e: e['P'][1]))))
    t1['proposal'] = dict(mean=wmean(E, lambda e: tot(e['P'])), median=wmedian(E, lambda e: tot(e['P'])), shape=wmean(E, lambda e: e['P'][0]), pattern=wmean(E, lambda e: e['P'][1]))
    for m in MODELS:
        sv = wmean_ci(E, lambda e: tot(e['P']) - tot(e['M'][m]))
        sh = wmean_ci(hit, lambda e: tot(e['P']) - tot(e['M'][m]))
        row = dict(mean=wmean(E, lambda e: tot(e['M'][m])), median=wmedian(E, lambda e: tot(e['M'][m])), shape=wmean(E, lambda e: e['M'][m][0]), pattern=wmean(E, lambda e: e['M'][m][1]), saving=sv, saving_hit=sh)
        t1[m] = row
        lines.append('| %s | %s | %s | %s | %s | %s | %s |' % (m, fmt(row['mean']), fmt(row['median']), fmt(row['shape']), fmt(row['pattern']), fci(sv), fci(sh)))
    tj['table1'] = t1
    return t1


def table2(E, TE, lines, tj, name):
    lines += ['', '### Table 2, the state: %s' % name, '',
              'Gain = bits of the first model minus bits of the second, in bits per form. "All steps" is every step of every walk seed 0 to 15 (equal weights); "done steps" is seed 0 with the weights of Table 1. '
              'Read-time shuffle: the gain with `prev` permuted within each task-seed walk (steps t >= 1), mean of 20 permutations. Fit-time shuffle: the gain with the second model fit on walks whose `prev` is permuted, scored with the true `prev`.', '',
              '| gain | all steps | done steps | read-time shuffle, all steps | fit-time shuffle, all steps |', '|---|---|---|---|---|']
    t2 = {}
    for a, b in (('M1', 'M2A'), ('M1', 'M2B'), ('M1', 'M2M'), ('M2M', 'M3')):
        g_all = wmean_ci(TE, lambda e: tot(e['M'][a]) - tot(e['M'][b]))
        g_done = wmean_ci(E, lambda e: tot(e['M'][a]) - tot(e['M'][b]))
        rt = fs = None
        if b in ('M2A', 'M2B'):
            rt = wmean_ci(TE, lambda e: tot(e['M'][a]) - tot(e['rt'][b]))
            fs = wmean_ci(TE, lambda e: tot(e['M'][a]) - tot(e['fs'][b]))
        t2['%s-%s' % (a, b)] = dict(all=g_all, done=g_done, rt=rt, fs=fs)
        lines.append('| %s - %s | %s | %s | %s | %s |' % (a, b, fci(g_all, 3), fci(g_done, 3), fci(rt, 3), fci(fs, 3)))
    tj['table2'] = t2
    return t2


def shares(steps_by_walk):
    """Counts of mode6 of the previous step, over steps t >= 1; and the transitions."""
    c, trans = collections.Counter(), collections.defaultdict(collections.Counter)
    for steps in steps_by_walk:
        steps = sorted(steps, key=lambda s: s['t'])
        for a, b in zip(steps, steps[1:]):
            p, m = mode6(a['pattern']), mode6(b['pattern'])
            c[p] += 1
            trans[p][m] += 1
    return c, trans


def share_rows(c):
    n = sum(c.values()) or 1
    r = {m: c[m] / n for m in T.MODE6}
    r['A: prev = EXTEND'] = c['EXTEND'] / n
    r['B: prev on the chain'] = sum(c[m] for m in ('EXTEND', 'BT1', 'BT2', 'BT3+')) / n
    r['BACKTRACK'] = sum(c[m] for m in ('BT1', 'BT2', 'BT3+')) / n
    r['JUMP'] = (c['JUMP0'] + c['JUMP+']) / n
    return r


def table3(walks, lines, tj):
    lines += ['', '### Table 3, share of steps in each state (t >= 1; the state is the mode of the step before)', '',
              'Held sets: seed 0, then mean over seeds 0 to 15 with the standard deviation over seeds. Corpus: mean over seeds 0 to 3.', '']
    cols = ['EXTEND', 'BT1', 'BT2', 'BT3+', 'JUMP0', 'JUMP+', 'BACKTRACK', 'JUMP', 'A: prev = EXTEND', 'B: prev on the chain']
    lines += ['| set | read | ' + ' | '.join(cols) + ' |', '|---|---|' + '---|' * len(cols)]
    t3 = {}
    for st, nseed in (('37', T.NSEED_HELD), ('ramp', T.NSEED_HELD), ('corpus', 4)):
        per_seed = []
        for s in range(nseed):
            ws = [v for k, v in walks.items() if k[0] == st and k[2] == s]
            if ws:
                per_seed.append((share_rows(shares(ws)[0]), shares(ws)[1]))
        if not per_seed:
            continue
        r0 = per_seed[0][0]
        mean = {c: mean_of(p[0][c] for p in per_seed) for c in cols}
        sd = {c: float(np.std([p[0][c] for p in per_seed])) for c in cols}
        t3[st] = dict(seed0=r0, mean=mean, sd=sd, seeds=len(per_seed))
        if st != 'corpus':
            lines.append('| %s | seed 0 | ' % st + ' | '.join('%.1f%%' % (100 * r0[c]) for c in cols) + ' |')
        lines.append('| %s | mean over %d seeds | ' % (st, len(per_seed)) + ' | '.join('%.1f%% (%.1f)' % (100 * mean[c], 100 * sd[c]) for c in cols) + ' |')
    lines += ['', '#### Transitions, P(mode_t | state), seed 0 for the held sets, all corpus seeds for the corpus', '']
    t3['transitions'] = {}
    for st in ('37', 'ramp', 'corpus'):
        ws = [v for k, v in walks.items() if k[0] == st and (k[2] == 0 or st == 'corpus')]
        if not ws:
            continue
        _, trans = shares(ws)
        lines += ['**%s**' % st, '', '| state | steps | ' + ' | '.join(T.MODE6) + ' |', '|---|---|' + '---|' * len(T.MODE6)]
        t3['transitions'][st] = {}
        for p in T.MODE6:
            n = sum(trans[p].values())
            if n:
                lines.append('| %s | %d | ' % (p, n) + ' | '.join('%.1f%%' % (100 * trans[p][m] / n) for m in T.MODE6) + ' |')
                t3['transitions'][st][p] = {m: trans[p][m] / n for m in T.MODE6}
        lines.append('')
    tj['table3'] = t3
    return t3


def table4(E, lines, tj, N, Dn, st):
    lines += ['', '### Table 4, by place of gold\'s form', '',
              'Steps = done / total (non-OTHER steps of the seed-0 walks). Bits are weighted means; the saving is the proposal minus M2A, with an interval by task; the share is the cell\'s part of all saved bits.', '',
              '| place | f\'s mode | steps | proposal | M1 | M2A | M2B | saving of M2A | share of saved bits |', '|---|---|---|---|---|---|---|---|---|']
    total_saved = sum(e['w'] * (tot(e['P']) - tot(e['M']['M2A'])) for e in E) or float('nan')
    t4 = {}
    for p in PLACES:
        for mc in (None,) + MCLASS:
            sub = [e for e in E if e['place'] == p and (mc is None or e['mc'] == mc)]
            tot_n = sum(v for (task, pl, m), v in N.items() if pl == p and (mc is None or m == mc))
            if not tot_n:
                continue
            sv = wmean_ci(sub, lambda e: tot(e['P']) - tot(e['M']['M2A'])) if sub else None
            share = sum(e['w'] * (tot(e['P']) - tot(e['M']['M2A'])) for e in sub) / total_saved if sub else None
            row = dict(done=len(sub), total=tot_n, proposal=wmean(sub, lambda e: tot(e['P'])) if sub else None,
                       M1=wmean(sub, lambda e: tot(e['M']['M1'])) if sub else None, M2A=wmean(sub, lambda e: tot(e['M']['M2A'])) if sub else None,
                       M2B=wmean(sub, lambda e: tot(e['M']['M2B'])) if sub else None, saving=sv, share=share)
            t4['%s/%s' % (p, mc or 'all')] = row
            lines.append('| %s | %s | %d / %d | %s | %s | %s | %s | %s | %s |' % (
                p if mc is None else '', 'all' if mc is None else mc, len(sub), tot_n, fmt(row['proposal']), fmt(row['M1']), fmt(row['M2A']), fmt(row['M2B']), fci(sv),
                '-' if share is None else '%.0f%%' % (100 * share)))
    tj['table4'] = t4
    return t4


def table5(E, lines, tj):
    lines += ['', '### Table 5, by outcome (weighted medians of bits)', '', '| outcome | steps | proposal | M2A |', '|---|---|---|---|']
    t5 = {}
    for field, label in (('mode6', 'gold mode6'), ('shape', 'gold shape')):
        cnt = collections.Counter(e[field] for e in E)
        for v, n in cnt.most_common(10):
            sub = [e for e in E if e[field] == v]
            row = dict(n=n, proposal=wmedian(sub, lambda e: tot(e['P'])), M2A=wmedian(sub, lambda e: tot(e['M']['M2A'])))
            t5['%s=%s' % (field, v)] = row
            lines.append('| %s %s | %d | %s | %s |' % (label, v, n, fmt(row['proposal']), fmt(row['M2A'])))
    tj['table5'] = t5


def verdict(E, TE, t1, t2, lines, tj, name):
    lines += ['', '### Verdict: %s' % name, '']
    v = {}
    if not E:
        lines.append('- No done steps.')
        return
    m2a, m2b = t1['M2A']['saving'], t1['M2B']['saving']
    v['saving'] = bool(m2a[1] is not None and m2a[1] > 0)
    lines.append('- Saving: M2A saves %s bits per form against the proposal, M2B %s. A tower-conditioned proposal saves: **%s** (M2A interval %s 0).' % (
        fci(m2a), fci(m2b), 'yes' if v['saving'] else 'no', 'above' if v['saving'] else 'includes or is below'))
    gA, gB = t2['M1-M2A'], t2['M1-M2B']
    best = 'A' if gA['all'][0] >= gB['all'][0] else 'B'
    g = gA if best == 'A' else gB
    rt = (t2['M1-M2A'] if best == 'A' else t2['M1-M2B'])['rt']
    pos = (gA['all'][1] > 0) or (gB['all'][1] > 0)
    state = bool(pos and g['all'][0] >= .05 and rt[0] <= 0)
    v['state'] = state
    lines.append('- State: M1 - M2A %s, M1 - M2B %s (all steps); the larger gain is meaning %s; read-time-shuffled gain %s. The state carries information: **%s** (interval above 0 for at least one meaning: %s; gain of .05 or more: %s; shuffled gain 0 or below: %s).' % (
        fci(gA['all'], 3), fci(gB['all'], 3), best, fci(rt, 3), 'yes' if state else 'no', pos, g['all'][0] >= .05, rt[0] <= 0))
    total = t1['proposal']['mean'] - t1['M2A']['mean']
    p_m0, m0_m1, m1_m2 = t1['proposal']['mean'] - t1['M0']['mean'], t1['M0']['mean'] - t1['M1']['mean'], t1['M1']['mean'] - t1['M2A']['mean']
    v['source'] = dict(total=total, set=p_m0, last=m0_m1, state=m1_m2)
    lines.append('- Source of the M2A saving (%s bits per form, done steps): set facts (proposal - M0) %s (%.0f%%), the last built (M0 - M1) %s (%.0f%%), the state (M1 - M2A) %s (%.0f%%).' % (
        fmt(total), fmt(p_m0), 100 * p_m0 / total, fmt(m0_m1), 100 * m0_m1 / total, fmt(m1_m2), 100 * m1_m2 / total))
    cells = {p: sum(e['w'] * (tot(e['P']) - tot(e['M']['M2A'])) for e in E if e['place'] == p) for p in PLACES}
    allsaved = sum(cells.values())
    half = [p for p in PLACES if cells[p] >= allsaved / 2] if allsaved > 0 else []
    per_form = {p: wmean([e for e in E if e['place'] == p], lambda e: tot(e['P']) - tot(e['M']['M2A'])) for p in PLACES if any(e['place'] == p for e in E)}
    top = max(per_form, key=per_form.get)
    ordered = sorted(PLACES, key=lambda p: -cells[p])
    lines.append('- Where: share of saved bits by place: %s. Places with half or more of the saved bits: %s. Largest saving per form: %s (%s bits).' % (
        ', '.join('%s %.0f%%' % (p, 100 * cells[p] / allsaved) for p in ordered), ', '.join(half) or 'none (no single place)', top, fmt(per_form[top])))
    v['where'] = dict(shares={p: cells[p] / allsaved for p in PLACES}, half=half, top=top)
    tj['verdict'] = v


def context(E, TE, walks, fit, rows, st, lines, tj):
    lines += ['', '### Table 6, context: %s' % st, '', '| model | alpha shape | alpha pattern | CV bits on the corpus (shape + pattern) | held bits, all steps seeds 0-15 | spread over seeds (sd, min, max) of held bits |', '|---|---|---|---|---|---|']
    t6 = {}
    for m in MODELS:
        by_seed = collections.defaultdict(list)
        for e in TE:
            by_seed[e['seed']].append(tot(e['M'][m]))
        sm = [mean_of(v) for v in by_seed.values()]
        cvb = fit['cv'][m]
        t6[m] = dict(alpha=fit['alphas'][m], cv=cvb['total'], held=mean_of(tot(e['M'][m]) for e in TE), seed_sd=float(np.std(sm)) if sm else None)
        lines.append('| %s | %s | %s | %.3f (%.3f + %.3f) | %s | %s |' % (m, fit['alphas'][m]['shape'], fit['alphas'][m]['pattern'], cvb['total'], cvb['shape'], cvb['pattern'], fmt(t6[m]['held'], 3),
                                                                    '%.3f, %.3f, %.3f' % (np.std(sm), min(sm), max(sm)) if sm else '-'))
    wb = [s['walk_bits'] for (s_, task, seed), v in walks.items() if s_ == st for s in v]
    cb = [s['walk_bits'] for (s_, task, seed), v in walks.items() if s_ == 'corpus' for s in v]
    n_other = sum(1 for (s_, task, seed), v in walks.items() if s_ == st and seed == 0 for s in v if s['kind'] == 'OTHER')
    done_rows = [r for r in rows.values() if r['set'] == st]
    p0 = sum(1 for r in done_rows if r['p_kind'] <= 0)
    h0 = sum(1 for e in E if e['hj'] == 0)
    t6['walk_bits'] = dict(held=mean_of(wb), corpus=mean_of(cb))
    t6['left_out'] = dict(other_kind_seed0=n_other, p_kind_zero_done=p0)
    t6['hjoint0'] = dict(count=h0, share_weighted=(sum(e['w'] for e in E if e['hj'] == 0) / sum(e['w'] for e in E)) if E else None, share_raw=h0 / len(E) if E else None)
    lines += ['', '- Mean `walk_bits` per step (the cost of the order that neither side pays): %s on %s walks (all seeds), %s on the corpus walks.' % (fmt(t6['walk_bits']['held'], 3), st, fmt(t6['walk_bits']['corpus'], 3)),
              '- Steps left out: %d of kind OTHER in the seed-0 walk, %d done steps with P_kind = 0 (kind not admitted or outside KIND_TOK).' % (n_other, p0),
              '- Done steps with h_joint = 0 (the proposal\'s bits are a lower bound there): %d of %d (%s weighted, %s raw).' % (
                  h0, len(E), '-' if not E else '%.0f%%' % (100 * t6['hjoint0']['share_weighted']), '-' if not E else '%.0f%%' % (100 * t6['hjoint0']['share_raw']))]
    if E:
        pos = [e for e in E if e['hj'] >= 1]
        lines.append('- The saving of M2A with the h_joint = 0 steps left out: %s (%d steps).' % (fci(wmean_ci(pos, lambda e: tot(e['P']) - tot(e['M']['M2A']))), len(pos)))
    tj['table6'] = t6


def data_check(walks, tower, rows, lines, held_dir):
    lines += ['## Data check', '']
    bysd = collections.Counter((k[0], k[2]) for k in walks)
    for st in ('37', 'ramp', 'corpus'):
        seeds = sorted(s for (a, s) in bysd if a == st)
        n_tasks = len({k[1] for k in walks if k[0] == st})
        lines.append('- walks, %s: %d tasks, seeds %s, %d walks, %d steps' % (st, n_tasks, '0-%d' % seeds[-1] if seeds else '-', sum(bysd[(st, s)] for s in seeds), sum(len(v) for k, v in walks.items() if k[0] == st)))
    for st in ('37', 'ramp'):
        c = collections.Counter(s['kind'] for k, v in walks.items() if k[0] == st and k[2] == 0 for s in v)
        lines.append('- steps by kind, %s, seed 0: %s' % (st, dict(c)))
    lines.append('- tower rows: %d steps over %d tasks' % (len(tower), len({k[0] for k in tower})))
    for st in ('37', 'ramp'):
        rs = [r for r in rows.values() if r['set'] == st]
        c = collections.Counter(r['pass'] for r in rs)
        want1 = want_n = got1 = 0
        for (s_, task, seed), v in walks.items():
            if s_ == st and seed == 0:
                p1 = pick_pass1(task, v)
                want1 += len(p1)
                want_n += sum(1 for s in v if s['kind'] != 'OTHER')
                got1 += sum(1 for t in p1 if (task, t) in rows)
        lines.append('- held steps done, %s: %d rows (by pass %s), %d tasks; pass-1 steps listed %d, done %d; non-OTHER steps %d, done %d; P_kind = 0: %d; h_joint = 0: %d; held dir %s' % (
            st, len(rs), dict(c), len({r['task'] for r in rs}), want1, got1, want_n, len(rs), sum(1 for r in rs if r['p_kind'] <= 0), sum(1 for r in rs if r['p_kind'] > 0 and r['h_joint'] == 0), held_dir))
    lines.append('')


LIMITS = """## Limits
- The read measures the draw distribution of `Sampler.clause`, not the best-first search's order or its visit end.
- Both sides score gold's form at the step the walk gives. Neither pays for the order, which is `walk_bits` a step. The walk is the round-0 walk of `walk.md`. A refit `theta` changes the steps and asks for a rerun.
- The pattern counts reads by place on the tower. It doesn't say which form of a class f reads. The shape is the head shape, not the body.
- The proposal's bits are a lower bound at steps with `h_joint = 0`.
- `relR4_o.pkl` holds the ramp in its train rows, so the ramp read is held out for the priors only. The corpus copy is of 21:49 on Nov 1, and the priors were fit earlier.
- `models-kr` is `7dafa0ce` plus `key_rel`. With `KEY_IDENT` unset, `key_rel` has no effect. So this bundle differs from `models-tk` by `col` in `ORDER_FREE`, its `COL_TYPE` table and `choice5_o`.
- Alpha is chosen from {0.5, 2, 8, 32, 128}. A choice at 128 is at the edge of that grid.
- The shuffles permute `prev` within a walk over the steps t >= 1 and leave START at step 0 in place.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--held-dir', default=None)
    ap.add_argument('--out-dir', default=None)
    a = ap.parse_args()
    T.setup(engine=False)
    held_dir = a.held_dir or T.R + '/held'
    out_dir = a.out_dir or T.R
    walks, tower, rows = load(held_dir)
    fit = json.load(open(T.R + '/fit.json'))
    lines = ['# Tower read, held-out 37 and ramp 22', '', 'Design: `%s`.' % T.DESIGN, '']
    tj = {}
    data_check(walks, tower, rows, lines, held_dir)
    print('\n'.join(lines), flush=True)
    for st, name in (('37', 'the 37 (the verdict)'), ('ramp', 'the ramp (a second, weak read: relR4_o has the ramp in its train rows)')):
        E, left, N, Dn = done_entries(st, walks, tower, rows)
        TE = tower_entries(st, walks, tower)
        lines += ['', '## %s' % name, '', '%d done steps used, %d tower steps (all seeds); left out: %s.' % (len(E), len(TE), dict(left) or 'none')]
        tj[st] = {}
        if not E or not TE:
            lines.append('')
            lines.append('No data yet.')
            continue
        t1 = table1(E, lines, tj[st], name)
        t2 = table2(E, TE, lines, tj[st], name)
        verdict(E, TE, t1, t2, lines, tj[st], name)
        table4(E, lines, tj[st], N, Dn, st)
        table5(E, lines, tj[st])
        context(E, TE, walks, fit, rows, st, lines, tj[st])
    lines += ['', '## Walks']
    table3(walks, lines, tj)
    lines += ['', LIMITS]
    os.makedirs(out_dir, exist_ok=True)
    open(out_dir + '/results.md', 'w').write('\n'.join(lines) + '\n')
    json.dump(tj, open(out_dir + '/tables.json', 'w'), indent=1, default=float)
    print('wrote %s/results.md and tables.json (%d lines)' % (out_dir, len(lines)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
