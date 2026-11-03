"""Reads R/corpus/*.jsonl and R/held/*.jsonl and writes R/tables.json and R/results.md.

  ib_read.py [--corpus DIR ...] [--held DIR] [--allow-partial]

The data check lines come first. With corpus rows incomplete it stops and says how many stems are left (--allow-partial goes on, for tests).
"""
import argparse
import collections
import glob
import json
import math
import os
import sys

import numpy as np

import ib_lib as L

NOISE_B = 1000
SHAPE_ORDER = ['INIT|1|key-ident', 'INIT|2|key-ident', 'INIT|3+|key-ident', 'INIT|1|key-plain', 'INIT|1|nokey', 'INIT|2|nokey', 'INIT|2|key-plain', 'RULE|1|-', 'RULE|2|-', 'RULE|3+|-',
               'DET|1|-', 'RIGID_DET|1|-']
REF = dict(search_tries='4.2%', random_draws_dagb='28.6%', gold_ident_scope='31.6%', gold_with_ident_in_reach='55.2%', pool_over_gold='.04', gold_key_ident='36.4%')


# ------------------------------------------------------------------ helpers

def med(v):
    return float(np.median(v)) if len(v) else None


def mean(v):
    return float(np.mean(v)) if len(v) else None


def wmed(v, w):
    if not len(v):
        return None
    o = np.argsort(v)
    v, w = np.asarray(v)[o], np.asarray(w)[o]
    c = np.cumsum(w)
    return float(v[np.searchsorted(c, c[-1] / 2)])


def f(x, d=2):
    return '-' if x is None else ('%.' + str(d) + 'f') % x


def g4(x):
    return '-' if x is None else '%.4f' % x


def md(headers, rows):
    out = ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers)]
    out += ['| ' + ' | '.join(str(c).replace('|', '/') for c in r) + ' |' for r in rows]
    return '\n'.join(out)


def logit(p):
    return math.log(p / (1 - p))


_bounds = {}


def bounds(n):
    if n not in _bounds:
        from scipy.stats import beta
        h = np.arange(n + 1)
        _bounds[n] = (beta.ppf(.025, h + .5, n - h + .5), beta.ppf(.975, h + .5, n - h + .5))
    return _bounds[n]


def false_under(p_gold, p_kind, rng, cap=256):
    """Share of NOISE_B simulated stopping rules flagged under, for a proposal that matches gold's cell: binomial draws at r = min(1, p_gold / p_kind)."""
    if p_kind <= 0:
        return None
    r = min(1.0, p_gold / p_kind)
    h = np.zeros(NOISE_B, int)
    state = np.zeros(NOISE_B, int)  # 0 running, 1 under, 2 not under
    for n in range(32, cap + 1, 32):
        run = state == 0
        if not run.any():
            break
        h[run] += rng.binomial(32, r, run.sum())
        lo, hi = bounds(n)
        hl, hh = lo[h] * p_kind, hi[h] * p_kind
        state[run & (hh < .1 * p_gold)] = 1
        state[(state == 0) & (hl > .1 * p_gold)] = 2
    return float((state == 1).mean())


def load_held(dirs):
    rows, heads = [], {}
    for d in dirs:
        for fn in sorted(glob.glob(d + '/*.jsonl')):
            for line in open(fn):
                try:
                    x = json.loads(line)
                except ValueError:
                    continue
                if x.get('rec') == 'task':
                    heads[x['task']] = x
                elif 'g' in x:
                    rows.append(x)
    return rows, heads


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', nargs='*', default=[L.R + '/corpus'])
    ap.add_argument('--held', nargs='*', default=[L.R + '/held'])
    ap.add_argument('--allow-partial', action='store_true')
    ap.add_argument('--out', default=L.R)
    a = ap.parse_args()
    out_lines = []

    def say(s=''):
        print(s, flush=True)
        out_lines.append(s)

    # ---- data check
    crow, ctask, shards_done = L.load_corpus(a.corpus)
    listed = L.corpus_stems()
    left = sorted(set(listed) - set(ctask))
    say('## Data check')
    say('- corpus stems listed %d, replayed %d, left %d, with a replay error %d (%d forms listed, %d rows)' % (
        len(listed), len(ctask), len(left), sum(1 for t in ctask.values() if t['error']), sum(t['forms'] for t in ctask.values()), len(crow)))
    if left and not a.allow_partial:
        say('- corpus rows are incomplete: %d stems left (%s ...). Run ib_corpus_all.sh. Stopping.' % (len(left), ', '.join(left[:5])))
        return 1
    gold = L.Gold(crow)
    kinds = collections.Counter(r['kind'] for r in crow)
    say('- corpus forms per kind: ' + ', '.join('%s %d' % kv for kv in sorted(kinds.items())))
    c1 = gold.total['C1']
    small = {c: n for c, n in c1.items() if n < L.MIN_CELL}
    say('- corpus C1 cells: %d, with under %d forms: %d (holding %d forms); shapes seen V=%d' % (len(c1), L.MIN_CELL, len(small), sum(small.values()), gold.V))
    hrows, heads = load_held(a.held)
    pinned = L.ident_list()
    say('- held rows %d, task lines %d, provisional-gold rows %d' % (len(hrows), len(heads), sum(1 for r in hrows if r.get('gold_provisional'))))
    by_pass = collections.Counter((r['set'], r['pass'], r['role']) for r in hrows)
    say('- rows by (set, pass, role): ' + ', '.join('%s' % (k,) + ' %d' % v for k, v in sorted(by_pass.items())))
    for st, tasks in (('37', L.held_tasks()), ('ramp', L.ramp_tasks())):
        tot = sum(len(pinned[t]['ident_only']) for t in tasks)
        done = sum(1 for r in hrows if r['set'] == st and r['role'] == 'ident')
        say('- %s: pinned Ident-only forms %d, done %d, tasks with rows %d of %d' % (st, tot, done, len({r['task'] for r in hrows if r['set'] == st}), len(tasks)))
    seen = collections.Counter((r['task'], r['g']) for r in hrows)
    dup = [k for k, v in seen.items() if v > 1]
    say('- duplicate (task, form) rows: %d' % len(dup))

    # ---- row metrics
    rng = np.random.default_rng(0)
    for r in hrows:
        r['p_gold'], r['level'], r['cell_n'] = gold.rate(r['shape'], r['facts'])
        r['p_gold_kind'] = gold.rate_kind(r['kind'], r['facts'])
        r['p_prop'] = r['p_kind'] * (r['h'] + .5) / (r['n'] + 1) if r['n'] else 0.0
        r['L'] = math.log2(r['p_gold']) - math.log2(r['p_prop']) if r['p_prop'] > 0 else None
        r['L_kind'] = math.log2(r['p_gold_kind']) - math.log2(r['p_kind']) if r['p_kind'] > 0 else None
        r['L_within'] = None if r['L'] is None or r['L_kind'] is None else r['L'] - r['L_kind']
        for tag, lv in (('C2', 'C2'), ('K', 'K')):
            pg = gold.rate(r['shape'], r['facts'], lv)[0]
            r['L_' + tag] = math.log2(pg) - math.log2(r['p_prop']) if r['p_prop'] > 0 else None
        r['noise'] = false_under(r['p_gold'], r['p_kind'], rng) if r['role'] == 'ident' else None
        r['linkbin'] = L.link_bin(r['link'])
    for st in ('37', 'ramp'):
        for t in {r['task'] for r in hrows if r['set'] == st}:
            idr = [r for r in hrows if r['task'] == t and r['role'] == 'ident']
            total = len(pinned[t]['ident_only'])
            for r in hrows:
                if r['task'] == t:
                    r['w'] = total / len(idr) if r['role'] == 'ident' and idr else 1.0
    for r in hrows:
        r.setdefault('w', 1.0)

    # ---- totals by shape from the task lines
    totals = collections.defaultdict(collections.Counter)
    for t, hd in heads.items():
        if hd['set'] == 'corpus':
            continue
        for g_, kind, shape, link, io in hd['all']:
            if io:
                totals[hd['set']][shape] += 1
                totals[hd['set']]['ident'] += 1
            elif shape.split('|')[1] == '0' and kind in L.KINDS:
                totals[hd['set']]['plain'] += 1

    def stats(rs, total=None):
        ls = [r['L'] for r in rs if r['L'] is not None]
        lk = [r['L_kind'] for r in rs if r['L_kind'] is not None]
        u = [r for r in rs if r['flag'] == 'under']
        wsum = sum(r['w'] for r in rs)
        return dict(done=len(rs), total=total, med_pg=med([r['p_gold'] for r in rs]), med_pp=med([r['p_prop'] for r in rs]), mean_L=mean(ls), med_L=med(ls), mean_Lk=mean(lk),
                    under=len(u), unresolved=sum(r['flag'] == 'unresolved' for r in rs), under_w=sum(r['w'] for r in u), w=wsum,
                    share_under_w=(sum(r['w'] for r in u) / wsum) if wsum else None, wmed_L=wmed(ls, [r['w'] for r in rs if r['L'] is not None]),
                    noise=sum(r['noise'] for r in rs if r['noise'] is not None), point_under=sum(r['point_under'] for r in rs))

    def t1_row(name, s):
        tot = '?' if s['total'] is None else s['total']
        return [name, '%d / %s' % (s['done'], tot), g4(s['med_pg']), g4(s['med_pp']), f(s['mean_L']), f(s['med_L']), f(s['mean_Lk']), s['under'], s['unresolved'],
                f(s['under_w'], 1) + ' (%s)' % ('-' if s['share_under_w'] is None else '%.0f%%' % (100 * s['share_under_w'])), f(s['noise'], 1)]

    T1H = ['shape', 'forms (done, total)', 'median p_gold', 'median p_prop', 'mean L', 'median L', 'mean L_kind', 'under (resolved)', 'unresolved', 'under, weighted to all forms', 'noise-floor under']
    tables = {}
    say()
    res = ['# Ident block read, held-out 37 and ramp 22', '']
    res += ['Design: `%s`.' % L.DESIGN, '', '## Verdict', 'VERDICT_PLACEHOLDER', '']
    S = {}
    for st, title in (('37', 'The 37 held-out tasks'), ('ramp', 'The 22 ramp tasks')):
        idr = [r for r in hrows if r['set'] == st and r['role'] == 'ident']
        pl = [r for r in hrows if r['set'] == st and r['role'] == 'plain']
        res += ['## Table 1, by shape: %s' % title, '']
        trs = []
        shapes = [s for s in SHAPE_ORDER if any(r['shape'] == s for r in idr) or totals[st][s]] + sorted({r['shape'] for r in idr} - set(SHAPE_ORDER) | {s for s in totals[st] if s not in ('ident', 'plain') and s not in SHAPE_ORDER})
        for s in shapes:
            trs.append(t1_row(s, stats([r for r in idr if r['shape'] == s], totals[st][s])))
        S[st, 'ident'] = stats(idr, totals[st]['ident'])
        S[st, 'plain'] = stats(pl, totals[st]['plain'])
        trs.append(t1_row('all Ident-only forms', S[st, 'ident']))
        trs.append(t1_row('plain control', S[st, 'plain']))
        res += [md(T1H, trs), '']
        tables['table1_' + st] = trs

    # ---- table 2
    slope = {}
    for st in ('37', 'ramp'):
        idr = [r for r in hrows if r['set'] == st and r['role'] == 'ident' and r['L'] is not None]
        res += ['## Table 2, by link: Ident-only forms, %s' % ('the 37' if st == '37' else 'the ramp'), '']
        trs = []
        for lb in L.LINK_BINS:
            rs = [r for r in idr if r['linkbin'] == lb]
            u = [r for r in rs if r['flag'] == 'under']
            trs.append([lb, len(rs), f(med([r['L'] for r in rs])), f(mean([r['L'] for r in rs])), '-' if not rs else '%.0f%%' % (100 * len(u) / len(rs)),
                        f(med([r['L'] for r in rs if r['kind'] == 'INIT' and not r['shape'].endswith('nokey')])), f(med([r['L'] for r in rs if r['kind'] == 'RULE']))])
        res += [md(['link bin', 'forms', 'median L', 'mean L', 'share under', 'median L, INIT keyed', 'median L, RULE'], trs), '']
        if len(idr) > 2:
            x = np.array([min(r['link'], 8) for r in idr], float)
            y = np.array([r['L'] for r in idr], float)
            tk = [r['task'] for r in idr]
            sl = np.polyfit(x, y, 1)[0] if x.std() > 0 else 0.0
            names = sorted(set(tk))
            ix = {n: [i for i, t in enumerate(tk) if t == n] for n in names}
            bs = []
            br = np.random.default_rng(1)
            for _ in range(1000):
                idx = sum((ix[names[j]] for j in br.integers(0, len(names), len(names))), [])
                xs, ys = x[idx], y[idx]
                if xs.std() > 0:
                    bs.append(np.polyfit(xs, ys, 1)[0])
            lo, hi = np.percentile(bs, [2.5, 97.5]) if bs else (None, None)
            slope[st] = (float(sl), lo, hi)
            res += ['OLS slope of L on link (capped at 8), unweighted: %.2f bits a link, 95%% interval from 1,000 bootstrap draws over tasks [%s, %s].' % (sl, f(lo), f(hi)), '']
        tables['table2_' + st] = trs

    # ---- table 3
    classes = ['no Ident in scope', 'Ident in scope, not at a sink', 'Ident at a sink']
    resp = {}
    for st in ('37', 'ramp'):
        res += ['## Table 3, response of the within-kind share of I >= 1 to Ident in scope: %s' % ('the 37' if st == '37' else 'the ramp'), '']
        trs = []
        for kind in L.KINDS:
            gs, ps = {}, {}
            for c in classes:
                grs = [r for r in crow if r['kind'] == kind and L.scope_class(r['facts']) == c]
                gs[c] = ((sum(L.i_ge1(r['shape']) for r in grs) + .5) / (len(grs) + 1), len(grs))
                prs = [r for r in hrows if r['set'] == st and r['kind'] == kind and L.scope_class(r['facts']) == c and r['n'] - r['none'] > 0]
                shares = [(sum(v for k, v in r['shapes'].items() if k.split('|')[0] in ('1', '2', '3+')) + .5) / (r['n'] - r['none'] + 1) for r in prs]
                ps[c] = (mean(shares), len(prs))
            rise_g = logit(gs[classes[2]][0]) - logit(gs[classes[0]][0])
            rise_p = (logit(ps[classes[2]][0]) - logit(ps[classes[0]][0])) if ps[classes[0]][0] and ps[classes[2]][0] else None
            resp[st, kind] = (rise_g, rise_p, {c: (gs[c], ps[c]) for c in classes})
            for c in classes:
                trs.append([kind, c, '%.3f (%d)' % gs[c], '-' if ps[c][0] is None else '%.3f (%d)' % ps[c], ''])
            trs[-1][4] = 'log-odds rise: gold %.2f, proposal %s' % (rise_g, f(rise_p))
        res += [md(['kind', 'scope class', 'gold share of I>=1 (corpus forms)', 'proposal mean share of I>=1 (held rows)', 'rise from first class to third'], trs), '']
        tables['table3_' + st] = trs

    # ---- table 4
    res += ['## Table 4, against the 4.2% and .04 figures', '']
    t4 = []
    for st in ('37', 'ramp'):
        ini = [r for r in hrows if r['set'] == st and r['kind'] == 'INIT' and r['facts']['ident_in'] != '0']
        valid = sum(r['n'] - r['none'] for r in ini)
        share = sum(r['reads_ident'] for r in ini) / valid if valid else None
        inall = [r for r in hrows if r['set'] == st and r['kind'] == 'INIT']
        valid2 = sum(r['n'] - r['none'] for r in inall)
        kshare = sum(r['key_ident'] for r in inall) / valid2 if valid2 else None
        keyed_draws = sum(v for r in inall for k, v in r['shapes'].items() if not k.endswith('nokey'))
        kshare2 = sum(r['key_ident'] for r in inall) / keyed_draws if keyed_draws else None
        ratio = lambda rs: med([r['p_prop'] / r['p_gold'] for r in rs])  # noqa: E731
        keyed = [r for r in hrows if r['set'] == st and r['role'] == 'ident' and r['kind'] == 'INIT' and not r['shape'].endswith('nokey')]
        nokey = [r for r in hrows if r['set'] == st and r['role'] == 'ident' and r['kind'] == 'INIT' and r['shape'].endswith('nokey')]
        t4 += [[st, '1. INIT draws at Ident scopes that read an Ident scope form', '-' if share is None else '%.1f%% of %d draws' % (100 * share, valid),
                'search tries %s, random draws on dagb %s; gold %s, gold with an Ident form in reach %s' % (REF['search_tries'], REF['random_draws_dagb'], REF['gold_ident_scope'], REF['gold_with_ident_in_reach'])],
               [st, '2. median p_prop / p_gold of INIT Ident-only forms, keyed (%d) | not keyed (%d)' % (len(keyed), len(nokey)), '%s | %s' % (f(ratio(keyed), 3), f(ratio(nokey), 3)),
                'pool share over gold share %s' % REF['pool_over_gold']],
               [st, '3. INIT draws with a key on an Ident label', '-' if kshare is None else '%.1f%% of %d INIT draws, %s of %d keyed draws' % (100 * kshare, valid2, f(None if kshare2 is None else 100 * kshare2, 1) + '%', keyed_draws), 'gold: %s of keys' % REF['gold_key_ident']]]
    res += [md(['set', 'row', 'this read', 'reference'], t4), '']
    tables['table4'] = t4

    # ---- table 5
    res += ['## Table 5, cells', '', '- Corpus forms per C1 cell: %d cells, %d with under %d forms (holding %d forms, which back off).' % (len(c1), len(small), L.MIN_CELL, sum(small.values())), '']
    t5 = []
    for st in ('37', 'ramp'):
        rs = [r for r in hrows if r['set'] == st and r['role'] == 'ident' and r['L'] is not None]
        lv = collections.Counter(r['level'] for r in rs)
        t5.append([st, ', '.join('%s %d' % kv for kv in sorted(lv.items())), f(mean([r['L'] for r in rs])), f(mean([r['L_C2'] for r in rs if r['L_C2'] is not None])), f(mean([r['L_K'] for r in rs if r['L_K'] is not None]))])
    res += [md(['set', 'backoff level of the C1 read (rows)', 'mean L, C1', 'mean L, C2', 'mean L, kind alone'], t5), '']
    big = sorted(c1.items(), key=lambda kv: -kv[1])[:15]
    res += ['Largest C1 cells (nscope, ident_in, ident_sink): ' + '; '.join('%s: %d' % (c, n) for c, n in big), '']
    tables['table5'] = t5

    # ---- pass 3
    p3 = [r for r in hrows if r['set'] == 'corpus']
    if p3:
        res += ['## Pass 3, in-sample control (corpus Ident-only forms on models-tk)', '']
        trs = [t1_row(s, stats([r for r in p3 if r['shape'] == s])) for s in sorted({r['shape'] for r in p3})] + [t1_row('all', stats(p3))]
        res += [md(T1H, trs), '']
        tables['pass3'] = trs

    # ---- verdict
    def apply(st):
        I, P = S[st, 'ident'], S[st, 'plain']
        idr = [r for r in hrows if r['set'] == st and r['role'] == 'ident' and r['L'] is not None]
        mlink = {lb: med([r['L'] for r in idr if r['linkbin'] == lb]) for lb in L.LINK_BINS}
        sl = slope.get(st, (None,))[0]
        rises = [resp[st, k] for k in ('RULE', 'INIT') if resp.get((st, k)) and resp[st, k][1] is not None]
        it = {}
        it['A1'] = (I['share_under_w'] is not None and I['share_under_w'] >= .4 and I['wmed_L'] is not None and I['wmed_L'] >= 2, 'weighted share under %s, weighted median L %s' % (f(I['share_under_w']), f(I['wmed_L'])))
        it['A2'] = (P['done'] > 0 and (P['under'] / P['done']) <= .15 and P['med_L'] is not None and P['med_L'] <= 1, 'plain share under %s, median L %s' % (f(P['under'] / P['done'] if P['done'] else None), f(P['med_L'])))
        it['A3'] = (all(mlink[b] is not None and mlink[b] >= 2 for b in ('1', '2')), 'median L at link 1 %s, link 2 %s' % (f(mlink['1']), f(mlink['2'])))
        it['A4'] = (bool(rises) and all(rp < rg / 2 for rg, rp, _ in rises), 'proposal rise vs gold rise (RULE, INIT): ' + '; '.join('%s vs %s' % (f(rp), f(rg)) for rg, rp, _ in rises))
        it['B1'] = (I['share_under_w'] is not None and I['share_under_w'] <= .15 and I['wmed_L'] is not None and I['wmed_L'] <= 1, 'weighted share under %s, weighted median L %s' % (f(I['share_under_w']), f(I['wmed_L'])))
        it['B2'] = (sl is not None and abs(sl) <= .3 and mlink['5+'] is not None and mlink['5+'] <= 1.5, 'slope %s, median L at link 5+ %s' % (f(sl), f(mlink['5+'])))
        it['C'] = (all(mlink[b] is not None and mlink[b] <= 1 for b in ('1', '2')) and sl is not None and sl >= .5, 'median L at link 1 %s, link 2 %s, slope %s' % (f(mlink['1']), f(mlink['2']), f(sl)))
        holds = {'A': all(it[k][0] for k in ('A1', 'A2', 'A3', 'A4')), 'B': all(it[k][0] for k in ('B1', 'B2')), 'C': it['C'][0]}
        first = next((k for k in 'ABC' if holds[k]), 'mixed')
        under_by = collections.Counter()
        for r in idr:
            if r['flag'] == 'under':
                under_by[r['shape']] += r['w']
        tot_w = sum(r['w'] for r in idr)
        return first, it, holds, [(s, w, w / tot_w if tot_w else None) for s, w in under_by.most_common(6)]

    v = []
    for st, label in (('37', 'The 37 (the verdict)'), ('ramp', 'The ramp (a second, weak read: 41 forms; relR4_o has the ramp in its train rows)')):
        if S[st, 'ident']['done'] == 0:
            v.append('- %s: no rows yet.' % label)
            continue
        first, it, holds, under_by = apply(st)
        v.append('- %s: **%s**. A %s, B %s, C %s.' % (label, {'A': 'A, the proposal\'s Ident conditioning is the block', 'B': 'B, compounding over chain depth is the block', 'C': 'C, conditioning that worsens with depth', 'mixed': 'mixed'}[first], holds['A'], holds['B'], holds['C']))
        for k, (ok, s) in it.items():
            v.append('    - %s %s: %s' % (k, 'holds' if ok else 'fails', s))
        if first == 'mixed':
            v.append('    - shapes that hold the `under` forms (weighted count, share of all Ident-only forms): ' + '; '.join('%s %.1f (%.0f%%)' % (s, w, 100 * (sh or 0)) for s, w, sh in under_by))
        tables['verdict_' + st] = dict(first=first, holds=holds, items={k: list(x) for k, x in it.items()})
    res[res.index('VERDICT_PLACEHOLDER')] = '\n'.join(v)

    # ---- fixed sections
    res += ['## Pins and names',
            '- Models: `models-tk` for the 37 and pass 3, `models-tkf` for the ramp, both in kit `sampler-pool-tiekey-value-0729e4943`. These are the models of `kernel-bundle-ec15d12f0`, the kit the refit and Ident reads ran against as the bundle. The `Bundle:` line of `work/facts.md` names an older Kaggle set (priors 49759a522172b459, relR4_o c527e533408a5269, choice5_o 9603712a5cf35684, tilt_v1 730b7596c1b841cc), which this read does not use.',
            '- The ramp read is held out for the priors only: `relR4_o.pkl` has the ramp tasks in its train rows.',
            '- Held gold: `points-eval.json` (sha256 af855438) and `gold-ident-only-refit.json` (08ec1bc4) of `live-gold-r1`. Corpus gold: `sampler-view-final-2149`, 989 stems (`corpus-pin.json`).',
            '', '## Limits',
            '- The read measures the draw distribution (`Sampler.clause`), not the best-first search\'s order or its visit end.',
            '- The cell rate is a coarse model of gold. A proposal that equals gold\'s own process still shows L below 0 on average, because that process knows more than the cell. So L at or above 0 is a loss even against a coarse gold model, and the size of L is a lower bound.',
            '- The shape is a necessary part of a cover, not the whole of one. A small L rules out the head shape as the block. It doesn\'t rule out the body.',
            '- `relR4_o.pkl` holds the ramp in its train rows. The corpus copy is of 21:49, and the priors were fit earlier, so the corpus can differ from the fit text on stems regolded since.',
            '- Pass 1 alone estimates the totals through the task weights; the raw counts sit beside the weighted ones.']
    check = [l for l in out_lines if l]
    head = res[:2]
    open(a.out + '/results.md', 'w').write('\n'.join(head + [''] + res[2:res.index('## Verdict')] + ['## Verdict', ''] + v + [''] + check + [''] + res[res.index('## Verdict') + 3:]) + '\n')
    json.dump(tables, open(a.out + '/tables.json', 'w'), indent=1, default=str)
    print('wrote %s/results.md and tables.json' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
