#!/usr/bin/env python
"""Kept or found (item 12): is gold's relation one that the forms of the pick's cut scope already use, or one that a pool run's nodes already use, and what a pick saves by conditioning on that set.

  features_dagc_env.sh 1 features_within_task_read.py [--seconds S] [--check]

A set S holds relation names, never NOT or a comparison. An option in S has its weight multiplied by exp(theta). Theta is one number per steer mode, fit by the likelihood of gold's pick on the gold-alive RULE picks of
test-parents (a pick weighs its walks over the form's walks), with S = kept. It opens no held row. The same theta applies to the found sets.

Kept set of a pick in form f, for a seed s: the relations that head a relation atom (or one inside a NOT) of a form in the `cut` scope of f for seed s, from points-held-cut.jsonl (points-test-cut.jsonl for the fit).
A derived relation is the content key of its form, `D:<content key>`, with the port left off. The target's own atoms are not in the scope. The two seeds give two kept sets, and a pick counts half for each.
The kept set is a function of the set of forms in the scope: no line's place, no atom's place.

Found set of a pick in form f, for one arm of the pool run: unchanged from the source record (features-relation-pick-feasible-by-value-join-heldout37): the lib, macro and fact relations that head an atom in a node's clause,
and the derived relations that a node's clause reads (by the gold form whose table the node has), over the nodes drawn before f's cut, where f's cut is the draw of the run's first cover of f (every node if the run never covers f).
It reads a run's nodes and draws and no gold text order. within-task-nodes.jsonl of the source record stands as it is.

Rows: walks/held-parents-off-*, held-parents-live-*, test-parents-off-*, test-parents-live-* (RULE forms), whatever exists. Prints which shards and how many forms. --check scrambles the lines of programs and compares the kept sets.
"""
import argparse
import collections
import glob
import json
import math
import os
import re
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_dag_order as D  # noqa: E402
import features_dagc_lib as L  # noqa: E402
import features_dagc_rows as RW  # noqa: E402

ME = RW.ME
SRC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-feasible-by-value-join-heldout37/'
KIT = SRC + 'pool-kit-gold/'
POOL = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-pool-factored-priors-heldout35-600s-ship7/'
ARMS = 'control_search', 'factored_search'
CMP = ('=', '!=', '<', '<=', '>', '>=')
HEAD = re.compile(r'\(+(&?[^\s():]+)')
NAME_, KIND_, W_ = 0, 1, 2


def rel_heads(text):
    """The relation heads of a form's leaf atoms, a NOT's inner atoms included, with the port: `lib_name` or `&rN.port`."""
    dag = D.FormDag(text)
    out = set()
    for a in dag.atoms.values():
        if a.kind == 'rel' and isinstance(a.tree[0], str):
            out.add(a.tree[0])
        elif a.kind == 'not':
            for x in a.tree[1:]:
                if isinstance(x, list) and x and isinstance(x[0], str) and x[0] not in CMP and x[0] != 'NOT':
                    out.add(x[0])
    return out


def kept_of_scope(scope, cp_all, name_ck):
    """The kept set of a cut scope: relation keys. A derived head is `D:<content key>`; `name_ck` maps a form name of the program to its content key."""
    s = set()
    for text in scope:
        if text.startswith('(OUT'):
            continue
        for h in rel_heads(text):
            if h.startswith('&'):
                ck = name_ck.get(h.partition('.')[0])
                if ck:
                    s.add('D:' + ck)
            else:
                s.add(h)
    return frozenset(s)


def opt_key(name):
    return name.partition('.')[0] if name.startswith('D:') else name


class Programs:
    """The gold program of a task: lines, content keys, cut scopes of its points."""

    def __init__(self, kind):
        self.kind = kind
        if kind == 'held':
            self.gold = L.base_gold()
            self.pts = [json.loads(x) for x in open(ME + 'points-held-cut.jsonl')]
        else:
            self.gold = None
            self.pts = [json.loads(x) for x in open(ME + 'points-test-cut.jsonl')]
        self.cut = {}  # (task, line_id) -> {seed: scope}
        for p in self.pts:
            self.cut.setdefault((p['task'], p['line_id']), {})[p['target_seed']] = p['scope']
        self.cache = {}
        self.kcache = {}

    def prog(self, task):
        if task not in self.cache:
            lines = self.gold[task] if self.gold is not None else L.fit_gold([task])[task]
            cp = D.ProgramDag(lines)
            name_ck = {k: cp.content[k] for k in cp.lines}
            line_of_ck = {}
            for i, x in enumerate(lines):
                k = 'OUT' if x.startswith('(OUT') else D.parse(x)[1]
                line_of_ck.setdefault(cp.content[k], i)
            self.cache[task] = (lines, cp, name_ck, line_of_ck)
        return self.cache[task]

    def kept(self, task, line_id):
        """[kept set for each seed] of the form at line_id."""
        got = self.kcache.get((task, line_id))
        if got is None:
            lines, cp, name_ck, _ = self.prog(task)
            sc = self.cut[task, line_id]
            got = self.kcache[task, line_id] = [kept_of_scope(sc[s], cp, name_ck) for s in sorted(sc)]
        return got


# ---- the found sets (the source record's) ----

def mask_names(x):
    return re.sub(r'&\w+', '&_', x)


def heads(text):
    return {re.sub(r'\.\w+$', '', h) for h in HEAD.findall(text)}


def body(line):
    return re.sub(r'^\((\w+) &\S+', '(', line)


def load_nodes():
    out = {}
    for line in open(SRC + 'within-task-nodes.jsonl'):
        d = json.loads(line)
        out[d['task'], d['arm']] = d['nodes']
    return out


def load_run(task, arm, census, nodes_all):
    """(nodes as (draw, heads, parent tokens), {census line: cut draw}, {census line: covering node})."""
    nodes_ = [(d, frozenset(h), frozenset(p)) for _t, d, h, p in nodes_all[task, arm]]
    ev = json.load(open(KIT + 'points-eval.json'))
    ev = next(x for x in ev if x['task'] == task)['gold_sexp']
    ev = [x for x in ev.splitlines() if x.strip() and not x.startswith('(OUT')]
    fa = next((x for x in json.load(open(KIT + 'golds-factored.json')) if x['task'] == task), None)
    fa = [x for x in fa['gold_sexp'].splitlines() if x.strip() and not x.startswith('(OUT')] if fa else []
    by_mask = collections.defaultdict(list)
    for i, x in enumerate(census):
        by_mask[mask_names(x)].append(i)
    cut, node_of = {}, {}
    for line in open(POOL + arm + '/' + task + '.events.jsonl'):
        e = json.loads(line)
        if e['event'] not in ('cover', 'cover2'):
            continue
        src = ev if e['event'] == 'cover' else fa
        if e['gold'] >= len(src):
            continue
        hit = by_mask.get(mask_names(src[e['gold']]))
        if not hit:
            continue
        for i in hit:
            cut[i] = min(cut.get(i, 1 << 60), e['draw'])
            if 'node' in e:
                node_of.setdefault(i, str(e['node']))
    return nodes_, cut, node_of


def found_set(nodes, cut, node_of, defs, opt_derived):
    s, reads = set(), set()
    for draw, hs, parents in nodes:
        if draw < cut:
            s |= hs
            reads |= parents
    for name in opt_derived:
        i = defs.get(name)
        if i is not None and node_of.get(i) in reads:
            s.add(name)
    return frozenset(s - {x for x in s if x.startswith('&f')})


# ---- theta ----

def pick_arrays(e, S):
    """(total weight, weight inside S, gold's weight, gold inside) of a pick for a set S of relation keys."""
    w = np.array([x[W_] for x in e['opts']], float)
    m = np.array([x[KIND_] in RW.REL_KINDS and opt_key(x[NAME_]) in S for x in e['opts']], bool)
    g = e['gold_idx']
    return float(w.sum()), float(w[m].sum()), float(w[g]), bool(m[g]), int(m.sum())


def fit_theta(Z, Sin, Wg, Mg, pw):
    lo, hi = -2.0, 4.0
    for _ in range(40):
        mid = (lo + hi) / 2
        ex = math.exp(mid)
        z = Z + (ex - 1) * Sin
        der = float((pw * (-Mg.astype(float) + ex * Sin / z)).sum())
        if der > 0:
            hi = mid
        else:
            lo = mid
    th = (lo + hi) / 2
    return th


def bits_at(th, Z, Sin, Wg, Mg):
    ex = math.exp(th)
    z = Z + (ex - 1) * Sin
    return -np.log2(Wg * np.where(Mg, ex, 1.0) / z)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--seconds', type=float, default=20)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--final', action='store_true', help='this is the held read of the item: append it to held-reads.jsonl. Not for a pilot on partial rows')
    a = ap.parse_args()
    t0 = time.time()
    held_p, test_p = Programs('held'), Programs('test')
    if a.check:
        return check(held_p)
    tt = set(L.test_tasks())
    assert not tt & RW.HELD
    out = dict(steers={})
    nodes_all = load_nodes()
    pool_tasks = {t for t, _a in nodes_all}
    cache_runs = {}
    cells_rows = []
    for steers in ('off', 'live'):
        # theta on test-parents
        T = RW.load('test-parents', steers, tasks=tt, seconds=a.seconds)
        assert not {e['task'] for e in T.entries.values()} & RW.HELD
        recs = []
        for (pt, k), e in T.entries.items():
            if not RW.gold_alive(e):
                continue
            ks = test_p.kept(e['task'], e['line_id'])
            for S in ks:
                recs.append(pick_arrays(e, S) + (RW.weight(T, e) / len(ks),))
        R = np.array(recs, float)
        Z, Sin, Wg, Mg, pw = R[:, 0], R[:, 1], R[:, 2], R[:, 3] > 0, R[:, 5]
        th = fit_theta(Z, Sin, Wg, Mg, pw)
        b0, b1 = float(np.average(bits_at(0.0, Z, Sin, Wg, Mg), weights=pw)), float(np.average(bits_at(th, Z, Sin, Wg, Mg), weights=pw))
        fitres = dict(theta=round(th, 4), test_pick_sets=len(R), test_tasks=len({e['task'] for e in T.entries.values()}), forms=len(T.nok), test_prior_bits=round(b0, 4), test_bits_at_theta=round(b1, 4), test_saved=round(b0 - b1, 4),
                      gold_in_kept=round(float(np.average(Mg, weights=pw)), 4), files=T.files)
        print(steers, 'theta', fitres, '%.0fs' % (time.time() - t0), flush=True)
        # held read
        H = RW.load('held-parents', steers, seconds=a.seconds)
        rows = []
        for (pt, k), e in H.entries.items():
            if not RW.gold_alive(e):
                continue
            task, line = e['task'], e['line_id']
            lines, cp, name_ck, line_of_ck = held_p.prog(task)
            sets = {'kept': held_p.kept(task, line)}
            rels = [opt_key(x[NAME_]) for x in e['opts'] if x[KIND_] == 'relation']
            if task in pool_tasks:
                for arm in ARMS:
                    if (task, arm) not in cache_runs:
                        cache_runs[task, arm] = load_run(task, arm, lines, nodes_all)
                    nodes, cut, node_of = cache_runs[task, arm]
                    c = cut.get(line, 1 << 60)
                    defs = {'D:' + ck: i for ck, i in line_of_ck.items()}
                    f = found_set(nodes, c, node_of, defs, rels)
                    sets[arm] = [f]
                    sets['both_' + arm] = [kk | f for kk in sets['kept']]
            rows.append((e, RW.weight(H, e), sets))
        print(steers, 'held picks', len(rows), '%.0fs' % (time.time() - t0), flush=True)
        res = summarize(rows, th, steers, H)
        res['fit'] = fitres
        out['steers'][steers] = res
        cells_rows += write_cells_rows(rows, th, steers)
    write_cells(cells_rows)
    json.dump(out, open(ME + 'within-task-read.json', 'w'), indent=1)
    if a.final:
        with open(ME + 'held-reads.jsonl', 'a') as f:
            for steers in out['steers']:
                f.write(json.dumps(dict(name='within-task-held_read', group='kept or found', arm='theta', tier='kept+found', steers=steers, control=False, time=time.strftime('%Y-%m-%dT%H:%M:%S'))) + '\n')
    md = write_md(out)
    print(md)


def summarize(rows, th, steers, H):
    names = ['kept', 'kept on pool tasks'] + list(ARMS) + ['both_' + x for x in ARMS]
    base = {'kept': 'kept', 'kept on pool tasks': 'kept'}
    task = np.array([e['task'] for e, _w, _s in rows])
    wt = np.array([w for _e, w, _s in rows])
    inpool = np.array(['control_search' in s for _e, _w, s in rows])
    qb = np.array([e['q_bits'] for e, _w, _s in rows])
    res = dict(picks=len(rows), tasks=len(set(task.tolist())), forms=len({(e['task'], e['line_id']) for e, _w, _s in rows}), prior_bits=round(float(np.average(qb, weights=wt)), 4), pool_picks=int(inpool.sum()),
               pool_prior_bits=round(float(np.average(qb[inpool], weights=wt[inpool])), 4) if inpool.any() else None, files=H.files, theta=round(th, 4), sets={})

    def per(nm):
        key = base.get(nm, nm)
        sv, gin, relin = np.zeros(len(rows)), np.zeros(len(rows)), np.zeros(len(rows))
        for i, (e, _w, sets) in enumerate(rows):
            if key not in sets:
                continue
            ss = sets[key]
            for S in ss:
                Z, Sin, Wg, Mg, n = pick_arrays(e, S)
                ex = math.exp(th)
                cost = -math.log2(Wg * (ex if Mg else 1.0) / (Z + (ex - 1) * Sin))
                sv[i] += (e['q_bits'] - cost) / len(ss)
                gin[i] += Mg / len(ss)
                nrel = sum(x[KIND_] in RW.REL_KINDS for x in e['opts'])
                relin[i] += n / max(nrel, 1) / len(ss)
        return sv, gin, relin
    saved = {}
    for nm in names:
        sv, gin, relin = per(nm)
        saved[nm] = (sv, gin, relin)
        m = inpool if (nm != 'kept') else np.ones(len(rows), bool)
        if nm == 'kept on pool tasks' or nm in ARMS or nm.startswith('both_'):
            m = inpool
        if not m.any():
            continue
        res['sets'][nm] = dict(picks=int(m.sum()), gold_in_set=round(float(np.average(gin[m], weights=wt[m])), 4), rel_options_in_set=round(float(np.average(relin[m], weights=wt[m])), 4), saved=[round(x, 3) for x in RW.boot(wt * sv, wt, task, m)])
    # by class and band for kept, and for the arms
    res['classes'], res['bands'] = {}, {}
    cl = np.array([RW.cls_of(e) for e, _w, _s in rows])
    bd = np.array([e['band'] for e, _w, _s in rows])
    for grp, vals, dst in (('cls', ['derived', 'lib', 'own', 'macro', 'NOT', 'fact', 'comparison'], res['classes']), ('band', list(RW.BANDS), res['bands'])):
        arr = cl if grp == 'cls' else bd
        for v in vals:
            m = arr == v
            if not m.any():
                continue
            e_ = dict(picks=int(m.sum()), prior_bits=round(float(np.average(qb[m], weights=wt[m])), 3), gold_in_kept=round(float(np.average(saved['kept'][1][m], weights=wt[m])), 3), saved_kept=[round(x, 3) for x in RW.boot(wt * saved['kept'][0], wt, task, m)], pool_picks=int((m & inpool).sum()))
            for arm in ARMS:
                mm = m & inpool
                if mm.any():
                    e_['gold_in_' + arm] = round(float(np.average(saved[arm][1][mm], weights=wt[mm])), 3)
                    e_['saved_' + arm] = round(float(np.average(saved[arm][0][mm], weights=wt[mm])), 3)
            dst[v] = e_
    res['pool_tasks'] = len({e['task'] for e, _w, s in rows if 'control_search' in s})
    return res


def write_cells_rows(rows, th, steers):
    import zlib
    out = []
    for e, w, sets in rows:
        for nm, ss in sets.items():
            for S in ss:
                Z, Sin, Wg, Mg, n = pick_arrays(e, S)
                ex = math.exp(th)
                cost = -math.log2(Wg * (ex if Mg else 1.0) / (Z + (ex - 1) * Sin))
                nrel = sum(x[KIND_] in RW.REL_KINDS for x in e['opts'])
                out.append('within\t%s\t%s\t%s %d\t%s\t%d\t%.6f\t%s\t%s\t%s\t%s\t%.4f\t%d\t%d\t%d\t%.4f\n' % (nm, e['task'], e['task'], e['line_id'], e['kind'], zlib.crc32(repr(e['key']).encode()), w / len(ss), e['band'], e['place'], RW.cls_of(e), steers, e['q_bits'], Mg, n, nrel, e['q_bits'] - cost))
    return out


def write_cells(lines):
    with open(ME + 'cells-input-within.tsv', 'w') as f:
        f.write('read\tset\ttask\tform\tkind\tkey_hash\tw\tband\tplace\tcls\tsteers\tprior\tinside\tn_rel_in_set\tn_rel\tsaved_theta\n')
        f.writelines(lines)


def write_md(o):
    L_ = ['# Kept or found, held-parents RULE picks, gold alive', '']
    for steers, r in o['steers'].items():
        f = r['fit']
        L_.append('## Steers %s' % steers)
        L_.append('')
        L_.append('Theta %s fit on %d pick sets of %d test tasks (test-parents RULE, %s). Test bits %.3f at 0, %.3f at theta. Gold in kept on the fit rows %.3f.' % (f['theta'], f['test_pick_sets'], f['test_tasks'], steers, f['test_prior_bits'], f['test_bits_at_theta'], f['gold_in_kept']))
        L_.append('')
        L_.append('Held: %d picks, %d tasks, %d forms, prior bits %.3f; %d picks on the %d pool tasks (prior %s). Walk files: %s.' % (r['picks'], r['tasks'], r['forms'], r['prior_bits'], r['pool_picks'], r['pool_tasks'], r['pool_prior_bits'], r['files']))
        L_.append('')
        L_.append(RW.table_md(['Set', 'Picks', 'Gold in set', 'Relation options in set', 'Saved, 95% by task'], [[k, v['picks'], v['gold_in_set'], v['rel_options_in_set'], RW.fmt3(v['saved'])] for k, v in r['sets'].items()]))
        L_.append(RW.table_md(['Class', 'Picks', 'Prior bits', 'Gold in kept', 'Saved by kept', 'Pool picks', 'Gold in control, factored', 'Saved control, factored'],
                              [[k, v['picks'], v['prior_bits'], v['gold_in_kept'], RW.fmt3(v['saved_kept']), v['pool_picks'], '%s, %s' % (v.get('gold_in_control_search'), v.get('gold_in_factored_search')), '%s, %s' % (v.get('saved_control_search'), v.get('saved_factored_search'))] for k, v in r['classes'].items()]))
        L_.append(RW.table_md(['d_depth band', 'Picks', 'Prior bits', 'Gold in kept', 'Saved by kept'], [[k, v['picks'], v['prior_bits'], v['gold_in_kept'], RW.fmt3(v['saved_kept'])] for k, v in r['bands'].items()]))
    md = '\n'.join(L_) + '\n'
    open(ME + 'within-task-read.md', 'w').write(md)
    return md


def check(held_p):
    """A scramble of a program's lines leaves each kept set the same: the cut scope is rebuilt from ProgramDag on the scrambled lines and the kept set compared."""
    import random
    bad = n = 0
    tasks = sorted(held_p.gold)[:40]
    for t in tasks:
        lines = held_p.gold[t]
        sh = lines[:]
        random.Random('scramble|' + t).shuffle(sh)
        cp0, cp1 = D.ProgramDag(lines), D.ProgramDag(sh)
        nm0 = {k: cp0.content[k] for k in cp0.lines}
        nm1 = {k: cp1.content[k] for k in cp1.lines}
        for key in cp0.lines:
            if key == 'OUT':
                continue
            for s in (0, 1):
                o0 = cp0.random_order(s, cp0.non_descendants(key) | {key})
                o1 = cp1.random_order(s, cp1.non_descendants(key) | {key})
                k0 = kept_of_scope(cp0.texts(o0[:o0.index(key)]), cp0, nm0)
                k1 = kept_of_scope(cp1.texts(o1[:o1.index(key)]), cp1, nm1)
                n += 1
                bad += k0 != k1
    print('scramble check: %d kept sets on %d tasks, %d differ' % (n, len(tasks), bad))


if __name__ == '__main__':
    main()
