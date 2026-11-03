#!/usr/bin/env python
"""The held test cases: a gold RULE form with a scope that a real pool run had.

  python features_ps_points.py [--arms base_s0,base_s1] [--visits 2]    writes points-held-pool.jsonl and points-held-parents.jsonl

A form qualifies in a run when the run's cover events hold each form it reads, as table recall counts them, within 600 s. For each form and run, --visits visits are drawn with chance in proportion to tries, from the run's RULE visits that end after the last read form's first cover. Where visits of that kind hold every read form in their scope, they are the ones drawn.

The scope of a point is the visit's forms in their stored text and gold's text of the form's read forms with their ancestors. A visit form that covers one of those gold forms leaves the scope, unless another form of the scope reads it. Forms sort by depth, as the pool sorts them, and ties sort by a hash, so that gold's forms do not sit in one place.

A point in points-held-parents.jsonl is the same form with its parents scope alone. `line` is the point's id in its file.
"""
import argparse
import collections
import glob
import json
import re
import sys
import zlib

import numpy as np

BASE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-base-cost-read-heldout37/'
sys.path.insert(0, BASE)
import read_common as C  # noqa: E402

ME = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-per-relation-pool-scope-heldout37/'
sys.path.insert(0, ME)
import features_perrel_keys as K  # noqa: E402

CUT = 600.0
WIDE = False
GOLD ='/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-extended-cut/view-pass1/points-eval.json'
NEW = {x['task']: x['gold_sexp'] for x in json.load(open(GOLD))}
ALIAS = {}
for l_ in open(BASE + 'gold-dups.jsonl'):
    q_ = json.loads(l_)
    ALIAS[q_['task']] = q_
PROP = re.compile(r'\((RULE|DET) \S+ [A-Za-z]\S*\)$')


def gold_forms(t):
    """As build-rows.py: lines, the read forms of each form as cover indices, whether a read has no table to match."""
    lines = [x for x in NEW[t].strip().split('\n') if not x.startswith('(OUT')]
    head, reads = {}, []
    for i, x in enumerate(lines):
        names = re.findall(r'&r\d+', x)
        h = names[0]
        reads.append(sorted({head[m] for m in names[1:] if m in head and m != h}))
        head[h] = i
    q = ALIAS[t]
    nk = set(q['no_key'])
    out, unk = [], []
    for r in reads:
        got, u = set(), 0
        for m in r:
            if m not in nk:
                got.add(m)
            elif q['alias'][str(m)]:
                got |= set(q['alias'][str(m)])
            else:
                u = 1
        out.append(sorted(got))
        unk.append(u)
    return lines, reads, out, unk


def depths(lines, reads):
    d = {}
    for i in range(len(lines)):
        d[i] = 1 + max((d[r] for r in reads[i]), default=0)
    return d


def one(arm, t, n_vis, out, parents, tally):
    d = '%s%s/%s' % (C.A, arm, t)
    base = float(open(d + '/start').read())
    work = d + '/work/'
    st = C.bank(glob.glob(work + '*.out.jsonl.bank')[0])
    forms, nodes = st['forms'], st['nodes']
    age = collections.defaultdict(set)
    for n in nodes.values():
        age[n.age].add(n.form)
    visits = []
    for p in glob.glob(work + '*.visits'):
        for x in open(p):
            try:
                visits.append(json.loads(x))
            except ValueError:
                continue
    visits.sort(key=lambda v: v['time'])
    covs = []
    for p in glob.glob(work + '*.out.jsonl.cover'):
        for x in open(p):
            try:
                covs.append(json.loads(x))
            except ValueError:
                pass
    lines, areads, reads, unknown = gold_forms(t)
    dep = depths(lines, areads)
    g2p, p2g = collections.defaultdict(set), collections.defaultdict(set)
    first = {}
    for c in covs:
        for f in age.get(c['draw'], ()):
            g2p[c['gold']].add(f)
            p2g[f].add(c['gold'])
        if c['time'] - base <= CUT:
            cur = first.get(c['gold'])
            if cur is None or c['draw'] < cur['draw']:
                first[c['gold']] = c
    cum = 0
    for v in visits:
        v['t'] = v['time'] - base
        v['d0'], v['d1'] = cum, cum + v['tries']
        cum += v['tries']
        v['held'] = set()
        for f in v['fids']:
            v['held'] |= p2g.get(f, set())
        v['bank'] = all(f in forms for f in v['fids'])
    pool = [v for v in visits if v['kind'] == 'RULE' and v['t'] <= CUT and v['fids'] and v['bank']]
    if WIDE:  # every RULE form, gold's parents plus one late visit's forms: an oracle context with junk added
        late = [v for v in pool if v['t'] >= CUT / 2] or pool
        for g, x in enumerate(lines):
            if not x.startswith('(RULE') or PROP.match(x.strip()) or not late:
                continue
            tally['RULE forms'] += 1
            r = set(reads[g])
            found = not unknown[g] and all(q in first for q in r)
            clo = K.parents(lines, g)
            parents.append(dict(arm=arm, task=t, form=g, stratum='found' if found else 'oracle', scope=[lines[i] for i in clo], target=x, gold_forms=len(clo), pool_forms=0))
            rng = np.random.RandomState(zlib.crc32(('wide %s %s %d' % (arm, t, g)).encode()))
            w = np.array([v['tries'] for v in late], float)
            v = late[rng.choice(len(late), p=w / w.sum())]
            kept = list(v['fids'])
            dup = 0
            rm = sorted({f for c in clo for f in g2p.get(c, ()) if f in kept})
            for f in rm:
                if any(f in forms[o].parents for o in kept if o != f):
                    dup += 1
                else:
                    kept.remove(f)
            rows = [(dep[i], zlib.crc32(('%d %d' % (i, g)).encode()), lines[i]) for i in clo]
            rows += [(forms[f].depth, zlib.crc32(('p%d %d' % (f, g)).encode()), forms[f].text) for f in kept]
            rows.sort(key=lambda z: z[:2])
            out.append(dict(arm=arm, task=t, form=g, stratum='found' if found else 'oracle', visit_second=round(v['t'], 1), visit_forms=len(v['fids']), scope=[z[2] for z in rows], target=x, gold_forms=len(clo), gold_forms_covered=sum(1 for c in clo if c in first), pool_forms=len(kept), covers_removed=len(rm) - dup, covers_kept=dup, nreads=len(r)))
        return
    for g, x in enumerate(lines):
        if not x.startswith('(RULE') or PROP.match(x.strip()):
            continue
        tally['RULE forms'] += 1
        if unknown[g]:
            tally['a read has no table'] += 1
            continue
        r = set(reads[g])
        if any(q not in first for q in r):
            tally['a read not covered'] += 1
            continue
        rd = max((first[q]['draw'] for q in r), default=0)
        cand = [v for v in pool if v['d1'] > rd]
        hold = [v for v in cand if r <= v['held']]
        stratum = 'noreads' if not r else ('holds' if hold else 'built')
        use = hold if r and hold else cand
        if not use:
            tally['no visit after the reads'] += 1
            continue
        tally['forms with points'] += 1
        tally['stratum ' + stratum] += 1
        rng = np.random.RandomState(zlib.crc32(('%s %s %d' % (arm, t, g)).encode()))
        w = np.array([v['tries'] for v in use], float)
        pick = rng.choice(len(use), min(n_vis, len(use)), replace=False, p=w / w.sum())
        clo = K.parents(lines, g)
        parents.append(dict(arm=arm, task=t, form=g, stratum=stratum, scope=[lines[i] for i in clo], target=x, gold_forms=len(clo), pool_forms=0))
        for vi in pick.tolist():
            v = use[vi]
            kept = list(v['fids'])
            dup = 0
            cl = set(clo)
            rm = sorted({f for c in cl for f in g2p.get(c, ()) if f in kept})
            for f in rm:
                if any(f in forms[o].parents for o in kept if o != f):
                    dup += 1
                else:
                    kept.remove(f)
            rows = [(dep[i], zlib.crc32(('%d %d' % (i, g)).encode()), lines[i]) for i in clo]
            rows += [(forms[f].depth, zlib.crc32(('p%d %d' % (f, g)).encode()), forms[f].text) for f in kept]
            rows.sort(key=lambda z: z[:2])
            covered = sum(1 for c in clo if c in first and first[c]['draw'] < v['d1'])
            out.append(dict(arm=arm, task=t, form=g, stratum=stratum, visit_second=round(v['t'], 1), visit_forms=len(v['fids']), scope=[z[2] for z in rows], target=x, gold_forms=len(clo), gold_forms_covered=covered, pool_forms=len(kept), covers_removed=len(rm) - dup, covers_kept=dup, nreads=len(r)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', default='base_s0,base_s1')
    ap.add_argument('--visits', type=int, default=2)
    ap.add_argument('--wide', action='store_true', help='every RULE form: writes points-held-wide-pool.jsonl and points-held-wide-parents.jsonl')
    a = ap.parse_args()
    global WIDE
    WIDE = a.wide
    tasks = open(C.W + 'held/tasks.txt').read().split()
    out, par, tally = [], [], collections.Counter()
    for arm in a.arms.split(','):
        for t in tasks:
            one(arm, t, a.visits, out, par, tally)
        print(arm, dict(tally), flush=True)
    seen, pp = {}, []
    for p in par:  # a parents point is one form, whichever run qualified it
        k = p['task'], p['form']
        if k not in seen:
            seen[k] = p
            pp.append(p)
    out.sort(key=lambda p: (p['task'], p['form'], p['arm']))
    pp.sort(key=lambda p: (p['task'], p['form']))
    w_ = 'wide-' if WIDE else ''
    for name, rows in (('points-held-%spool.jsonl' % w_, out), ('points-held-%sparents.jsonl' % w_, pp)):
        with open(ME + name, 'w') as f:
            for i, p in enumerate(rows):
                p['line'] = i
                f.write(json.dumps(p) + '\n')
        print(name, len(rows), 'points', len({(p['task'], p['form']) for p in rows}), 'forms', len({p['task'] for p in rows}), 'tasks')
    print(collections.Counter(p['stratum'] for p in out))
    print('scope forms: median', np.median([len(p['scope']) for p in out]), 'visit forms', np.median([p['visit_forms'] for p in out]), 'gold forms', np.median([p['gold_forms'] for p in out]), 'pool', np.median([p['pool_forms'] for p in out]), 'covers kept', sum(p['covers_kept'] for p in out), 'removed', sum(p['covers_removed'] for p in out))
    print('closure forms covered', sum(p['gold_forms_covered'] for p in out), 'of', sum(p['gold_forms'] for p in out))


main()
