#!/usr/bin/env python
"""Part 1: reads the rows of features_feasible_walk.py that exist now, writes feasible-read.json and partial.md. Run it at any time while the walk runs.

  <runtime python> features_feasible_read.py [--test feasible-walk-test.jsonl]

With the test rows, the escape weight is the share of test gold-alive picks where gold's relation is out of the set. No number here is fit on held rows.

Sets, all on the options alive by column type:
  any   some map gives a row on at least one train example (a filter: removes a row and keeps a row on one example)
  all   one map gives a row on every train example where the prefix has a row
  keep  as any, with a filter that need only keep a row
An undetermined option stays in each set.
"""
import collections
import json
import math
import os
import statistics as st
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
ROWS = HERE + 'feasible-walk-held.jsonl'
CENSUS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-relation-pick-read-heldout431-census/rel_all.jsonl'
# fields of an option row
NAME, KIND, W, DEAD, OWN, U, A, EU, EA, UND, TABLES, MS = range(12)
CLASS = {'relation': 'derived', 'lib relation': 'lib', 'relation macro': 'macro', 'fact relation': 'fact', 'NOT': 'NOT', 'CMP': 'comparison'}
VARIANTS = 'any', 'all', 'keep'
PART3 = "Every earlier steer conditioned on names, kinds, column types and form structure, general across tasks: the prior's log share, relation name and kind by atom index, option types against scope types, arity, repeats and name crosses with the prefix, the point group and head name (`relfit.py`, `relfeat.py`, `relcheap.py`, `relnet.py`), and in the rank read the reader count, depth, DAG path, rank among options and pick-level counts. Only the rank read's content features read values, and they gave no gain."


def load(path):
    picks = {}
    forms = {}
    for line in open(path):
        if not line.endswith('\n'):
            continue
        d = json.loads(line)
        if d['rec'] == 'form':
            forms[d['task'], d['line']] = d
        else:
            picks[d['task'], d['line'], d['ord'], d['phase']] = d
    return picks, forms


def in_set(d, x, v):
    """Whether option x of pick d is in set v."""
    if x[DEAD]:
        return False
    rows = d['pre']['rows']
    if x[KIND] == 'N':
        return rows is None or any(c > 0 for c in rows.values())
    filt = x[KIND] == 'C' or d['phase'] == 'root2'
    if x[UND]:
        return True
    if v == 'any':
        return (x[EU] if filt else x[U]) > 0
    if v == 'all':
        return bool(x[EA] if filt else x[A])
    return x[U] > 0


def per_example(d):
    """{train example with a prefix row: the size of the set on that example alone}."""
    rows = d['pre']['rows'] or {}
    out = {}
    for e, c in rows.items():
        if c:
            b = 1 << int(e)
            n = 0
            for x in d['o']:
                if x[DEAD]:
                    continue
                filt = x[KIND] == 'C' or d['phase'] == 'root2'
                n += x[KIND] == 'N' or bool(x[UND]) or bool((x[EU] if filt else x[U]) & b)
            out[e] = n
    return out


def why_out(d, g):
    """The kind of pick where gold's relation is out of the `any` set."""
    pre = d['pre']['rows'] or {}
    ga = d['gold_atom']
    gr = ga.get('rows') or {}
    if not any(pre.values()):
        return 'the prefix has no row on a train example'
    if d['gold_kind'] == 'NOT':
        return 'other NOT'
    if d['gold_kind'] == 'CMP' or d['phase'] == 'root2':
        name = 'comparison' if d['gold_kind'] == 'CMP' else 'NOT'
        if ga.get('err'):
            return "%s: gold's atom gives no table" % name
        eff = [e for e, c in pre.items() if c and 0 < gr.get(e, 0) < c]
        if eff:
            return "%s: gold's atom removes and keeps a row, and no map shows it" % name
        if all(gr.get(e, 0) == c for e, c in pre.items()):
            return '%s: gold\'s atom removes no row on any train example' % name
        if not any(gr.values()):
            return "%s: gold's atom removes every row" % name
        return "%s: gold's atom removes all on some examples and none on the others" % name
    if ga.get('err'):
        return "gold's atom gives no table: %s" % str(ga['err'])[:30]
    if ga.get('reads', 0) == 0:
        return "gold's atom reads no bound label%s" % (', inside a branch' if d.get('flat') else '')
    if not any(gr.values()):
        return "gold's atom reads a bound label and has no row on a train example"
    return "gold's atom has a row, and no map shows it"


def boot(task, v, seed=0, n=10000):
    ts = sorted(set(task))
    idx = {t: i for i, t in enumerate(ts)}
    a, c = np.zeros(len(ts)), np.zeros(len(ts))
    for t, x in zip(task, v):
        a[idx[t]] += x
        c[idx[t]] += 1
    d = np.random.default_rng(seed).multinomial(len(ts), np.full(len(ts), 1 / len(ts)), size=n)
    r = (d @ a) / (d @ c)
    return [round(float(a.sum() / c.sum()), 3), round(float(np.percentile(r, 2.5)), 3), round(float(np.percentile(r, 97.5)), 3)]


def quart(v):
    q = np.percentile(v, [25, 50, 75])
    return [round(float(x), 1) for x in q]


def position(d):
    return 'first atom' if d['ord'] == 1 else 'second atom' if d['ord'] == 2 else 'third atom' if d['ord'] == 3 else 'later atoms'


def cls(d):
    return 'own' if d['own'] else CLASS[d['gold_kind']]


def gold_alive(d):
    g = d['gold_idx']
    return g is not None and not d['o'][g][DEAD]


def valid(d, forms):
    f = forms.get((d['task'], d['line']))
    return f is None or not (f['error'] or f['dead'] or f['bad'])


def main():
    test = sys.argv[sys.argv.index('--test') + 1] if '--test' in sys.argv else None
    picks, forms = load(ROWS)
    cen = {}
    for line in open(CENSUS):
        d = json.loads(line)
        if d['rec'] == 'rel':
            cen[d['task'], d['line'], d['ord'], d['phase']] = d['q_bits']
    P = [d for d in picks.values() if valid(d, forms) and gold_alive(d)]
    gap = max(abs(cen[d['task'], d['line'], d['ord'], d['phase']] - d['q_bits']) for d in P)
    res = dict(picks=len(P), of_picks=1761, tasks=len({d['task'] for d in P}), forms=len({(d['task'], d['line']) for d in P}), gap_to_census=round(gap, 4), prior_bits=round(st.mean(d['q_bits'] for d in P), 3), picks_any_context=len(picks))
    res['flat_picks'] = sum(bool(d.get('flat')) for d in P)
    res['no_prefix_table'] = dict(collections.Counter(str(d['pre']['err'])[:40] for d in P if d['pre']['err']))
    lam = None
    if test and os.path.exists(test):
        tp, tf = load(test)
        T = [d for d in tp.values() if valid(d, tf) and gold_alive(d)]
        lam = {v: sum(not in_set(d, d['o'][d['gold_idx']], v) for d in T) / len(T) for v in VARIANTS}
        res['escape'] = dict(test_picks=len(T), test_tasks=len({d['task'] for d in T}), weight={k: round(x, 4) for k, x in lam.items()})
    row = {}
    for d in P:
        g = d['gold_idx']
        w = np.array([x[W] for x in d['o']], float)
        q = w / w.sum()
        ent = {}
        for v in VARIANTS:
            m = np.array([in_set(d, x, v) for x in d['o']], bool)
            alive = np.array([not x[DEAD] for x in d['o']], bool)
            ing = bool(m[g])
            e = dict(n=int(m.sum()), gold=ing, und=sum(1 for x, y in zip(d['o'], m) if y and x[UND]))
            if ing:
                e['uni'] = math.log2(int(m.sum()))
                e['res'] = -math.log2(q[g] / q[m].sum())
            if lam is not None:
                rest = alive & ~m
                nr, wr = int(rest.sum()), q[rest].sum()
                if ing:
                    e['uni_soft'] = -math.log2(1 - lam[v]) + e['uni']
                    e['res_soft'] = -math.log2(1 - lam[v]) + e['res']
                else:
                    e['uni_soft'] = -math.log2(lam[v]) + math.log2(max(nr, 1))
                    e['res_soft'] = -math.log2(lam[v]) - math.log2(q[g] / wr)
            ent[v] = e
        ent['alive'] = int(sum(not x[DEAD] for x in d['o']))
        ex = per_example(d)
        ent['ex'] = st.mean(ex.values()) if ex else 0.0
        row[id(d)] = ent
    # sizes
    res['sizes'] = {}
    groups = [('all picks', P)] + [(n, [d for d in P if position(d) == n]) for n in ('first atom', 'second atom', 'third atom', 'later atoms')]
    for n, sub in groups:
        if sub:
            res['sizes'][n] = dict(picks=len(sub), alive=quart([row[id(d)]['alive'] for d in sub]), any=quart([row[id(d)]['any']['n'] for d in sub]), all=quart([row[id(d)]['all']['n'] for d in sub]), keep=quart([row[id(d)]['keep']['n'] for d in sub]),
                                   mean_example=quart([row[id(d)]['ex'] for d in sub]), undetermined_in_any=round(st.mean(row[id(d)]['any']['und'] for d in sub), 1))
    # bits
    res['bits'] = {}
    for v in VARIANTS:
        sub = [d for d in P if row[id(d)][v]['gold']]
        tk = [d['task'] for d in sub]
        q0 = [d['q_bits'] for d in sub]
        e = dict(gold_in=len(sub), share=round(len(sub) / len(P), 4), prior_same_picks=round(st.mean(q0), 3), uniform_alive_same_picks=round(st.mean(math.log2(row[id(d)]['alive']) for d in sub), 3),
                 uniform_set=round(st.mean(row[id(d)][v]['uni'] for d in sub), 3), prior_in_set=round(st.mean(row[id(d)][v]['res'] for d in sub), 3), saved_prior_in_set=boot(tk, [d['q_bits'] - row[id(d)][v]['res'] for d in sub]))
        if lam is not None:
            tka = [d['task'] for d in P]
            e['soft'] = dict(prior_all_picks=round(st.mean(d['q_bits'] for d in P), 3), uniform=round(st.mean(row[id(d)][v]['uni_soft'] for d in P), 3), prior=round(st.mean(row[id(d)][v]['res_soft'] for d in P), 3),
                             saved_prior=boot(tka, [d['q_bits'] - row[id(d)][v]['res_soft'] for d in P]))
        res['bits'][v] = e
    res['bits_by_class'] = {}
    for c in ('derived', 'lib', 'own', 'macro', 'NOT', 'fact', 'comparison'):
        sub = [d for d in P if cls(d) == c]
        ing = [d for d in sub if row[id(d)]['any']['gold']]
        if ing:
            res['bits_by_class'][c] = dict(picks=len(sub), gold_in_any=len(ing), prior_same_picks=round(st.mean(d['q_bits'] for d in ing), 3), prior_in_set=round(st.mean(row[id(d)]['any']['res'] for d in ing), 3), uniform_set=round(st.mean(row[id(d)]['any']['uni'] for d in ing), 3))
    res['bits_by_position'] = {}
    for n, sub in groups[1:]:
        ing = [d for d in sub if row[id(d)]['any']['gold']]
        if ing:
            res['bits_by_position'][n] = dict(picks=len(sub), gold_in_any=len(ing), prior_same_picks=round(st.mean(d['q_bits'] for d in ing), 3), prior_in_set=round(st.mean(row[id(d)]['any']['res'] for d in ing), 3), uniform_set=round(st.mean(row[id(d)]['any']['uni'] for d in ing), 3))
    # gold out
    out = collections.Counter()
    for d in P:
        if not row[id(d)]['any']['gold']:
            out[why_out(d, d['o'][d['gold_idx']])] += 1
    res['gold_out_any'] = dict(out.most_common())
    res['gold_out_all_only'] = sum(row[id(d)]['any']['gold'] and not row[id(d)]['all']['gold'] for d in P)
    # cost
    O = [x for d in P for x in d['o'] if x[TABLES] > 0]
    ms = sorted(x[MS] for x in O)
    res['cost'] = dict(call='step_tables with before, on a fork at the atom; ms is the whole probe of one option: decoder admits, forks, steps and tables, one thread', options=len(ms), ms_median=round(st.median(ms), 2), ms_mean=round(sum(ms) / len(ms), 2), ms_p95=round(ms[int(len(ms) * .95)], 2), ms_largest=round(ms[-1], 1),
                       tables_median=st.median(x[TABLES] for x in O), tables_largest=max(x[TABLES] for x in O), ms_per_pick_median=round(st.median(d['ms'] for d in P), 1), ms_per_pick_mean=round(st.mean(d['ms'] for d in P), 1), ms_per_pick_largest=round(max(d['ms'] for d in P), 1))
    json.dump(res, open(HERE + 'feasible-read.json', 'w'), indent=1)
    print(json.dumps(res, indent=1))
    write_partial(res)


def write_partial(r):
    L = ['# Feasible relation picks: partial', '', 'Rows: %d of %d gold-alive picks, %d tasks, %d forms. Prior bits on these picks %.3f. Largest gap to the census per pick %s. Numbers below change as rows land.' % (r['picks'], r['of_picks'], r['tasks'], r['forms'], r['prior_bits'], r['gap_to_census']), '']
    L += ['## The feasible set', '', open(HERE + 'feasible-definition.md').read().strip(), '']
    L += ['## Part 1', '', '| Picks | Count | Alive: Q1, median, Q3 | Feasible, any example | Feasible, all examples | Mean over examples, one example at a time |', '|---|---|---|---|---|---|']
    for k, v in r['sizes'].items():
        f = lambda x: '%s, %s, %s' % tuple(x)
        L.append('| %s | %d | %s | %s | %s | %s |' % (k, v['picks'], f(v['alive']), f(v['any']), f(v['all']), f(v['mean_example'])))
    L += ['', '| Set | Gold in set | Share | Prior, same picks | Uniform over alive, same picks | Uniform over set | Prior in set | Saved by the prior in set, 95% by task |', '|---|---|---|---|---|---|---|---|']
    for k, v in r['bits'].items():
        L.append('| %s | %d | %.3f | %.3f | %.3f | %.3f | %.3f | %+.3f (%+.3f to %+.3f) |' % (k, v['gold_in'], v['share'], v['prior_same_picks'], v['uniform_alive_same_picks'], v['uniform_set'], v['prior_in_set'], *v['saved_prior_in_set']))
    if 'escape' in r:
        L += ['', 'All picks, with an escape weight from %d test picks: %s.' % (r['escape']['test_picks'], r['escape']['weight']), '', '| Set | Prior | Uniform over set, escape | Prior in set, escape | Saved |', '|---|---|---|---|---|']
        for k, v in r['bits'].items():
            s = v['soft']
            L.append('| %s | %.3f | %.3f | %.3f | %+.3f (%+.3f to %+.3f) |' % (k, s['prior_all_picks'], s['uniform'], s['prior'], *s['saved_prior']))
    L += ['', 'Gold out of the `any` set:', '']
    L += ['- %s: %d' % (k, v) for k, v in r['gold_out_any'].items()]
    c = r['cost']
    L += ['', 'Probe cost per relation: %s. Median %.2f ms, largest %.1f ms, over %d option probes; %s tables each at the median, %d at most. Per pick: median %.1f ms, mean %.1f ms, largest %.1f ms.' % (c['call'], c['ms_median'], c['ms_largest'], c['options'], c['tables_median'], c['tables_largest'], c['ms_per_pick_median'], c['ms_per_pick_mean'], c['ms_per_pick_largest']), '']
    if os.path.exists(HERE + 'probe-cost-read.json'):
        p = json.load(open(HERE + 'probe-cost-read.json'))
        L += ['Calls on one atom, ms, %d picks:' % p['picks'], '']
        for k in ('step_tables with before, read, fork', 'projections', 'step_tables no before', 'Decoder.admits, per token', 'Decoder.forced'):
            if k in p:
                L.append('- %s: median %s, mean %s, largest %s' % (k, p[k]['median'], p[k]['mean'], p[k]['largest']))
        L += ['']
    if os.path.exists(HERE + 'within-task-read.json'):
        w = json.load(open(HERE + 'within-task-read.json'))
        L += ['## Part 2', '', 'Weight fit on test rows: theta %s. %d held picks, %d on the pool\'s 35 tasks.' % (w['theta'], w['picks'], w['pool_picks']), '', '| Set | Picks | Gold in set | Relation options in set | Saved, 95% by task |', '|---|---|---|---|---|']
        for k, v in w['sets'].items():
            L.append('| %s | %d | %.3f | %.3f | %+.3f (%+.3f to %+.3f) |' % (k, v['picks'], v['gold_in_set'], v['rel_options_in_set'], v['saved'], v['lo'], v['hi']))
        L += ['']
    L += ['## Part 3', '', PART3, '']
    with open(HERE + 'partial.md', 'w') as f:
        f.write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
