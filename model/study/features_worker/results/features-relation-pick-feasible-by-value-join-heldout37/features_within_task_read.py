#!/usr/bin/env python
"""Part 2: is gold's relation one that this task's kept forms or found forms already use, and what a pick saves by conditioning on that set.

  <runtime python> -u features_within_task_read.py nodes [--limit N]  writes within-task-nodes.jsonl, one row per task and arm of the pool run, flushed; a rerun skips those it holds. No held pick is read
  <runtime python> -u features_within_task_read.py fit      writes within-task-fit.json from the non-held test rows; it opens no held row
  <runtime python> -u features_within_task_read.py read     writes within-task-rows.jsonl, one row per held gold-alive pick, flushed; a rerun skips the picks it holds
  <runtime python> -u features_within_task_read.py summary  writes within-task-read.json from those rows

A set S holds relation names, never NOT or a comparison. An option in S has its weight multiplied by exp(theta); theta is one number, fit by the likelihood of gold's pick on the test tasks' rows (parents context), with S = kept.

Kept set of a pick in form f: the relations that head an atom in the body of a form written before f in the task's gold, f's own atoms not counted.
Found set of a pick in form f, for one arm of the pool run: the lib, macro and fact relations that head an atom in a node's clause, and the derived relations (by the gold form whose table the node has) that a node's clause reads, over the nodes drawn before f's cut.
  f's cut: the draw of the run's first cover of f. Where the run never covers f, the record has no time for the pick, and any draw of f comes after the whole record, so every node counts.
"""
import collections
import glob
import gzip
import io
import json
import math
import os
import re
import sys
import time

import numpy as np
import zstandard

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
R = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
RANK = R + 'features-worker/results/features-relation-pick-rank-context-rows-heldout37/'
GOLD_HELD = R + 'sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/points-base.json'
CORPUS_TEST = R + 'sampler/corpus-v3mix/'
POOL = R + 'sampler/search-worker/runs/search-pool-factored-priors-heldout35-600s-ship7/'
KIT = HERE + 'pool-kit-gold/'  # points-eval.json and golds-factored.json of the run's kit
ARMS = 'control_search', 'factored_search'
HEAD = re.compile(r'\(+(&?[^\s():]+)')
REL_KINDS = 'relation', 'lib relation', 'relation macro', 'fact relation'
CLASS = {'relation': 'derived', 'lib relation': 'lib', 'relation macro': 'macro', 'fact relation': 'fact', 'NOT': 'NOT', 'CMP': 'comparison'}
LN2 = math.log(2)


def records(path):
    with open(path, 'rb') as f:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
            yield json.loads(line)


def valid_picks(path):
    """The rows of the valid forms' gold-alive picks, as the census counts them."""
    buf = []
    for d in records(path):
        if d['rec'] != 'form':
            d.pop('cont', None), d.pop('rowopts', None), d.pop('pre', None)
            buf.append(d)
            continue
        if not (d['error'] or d['dead'] or d['bad'] or not d['aligned']):
            for p in buf:
                g = p['gold_idx']
                if g is not None and not p['opts'][g][3]:
                    yield p
        buf = []


def heads(text):
    return {re.sub(r'\.\w+$', '', h) for h in HEAD.findall(text)}


def body(line):
    """A form's text after its head: `(RULE &r1 ` holds no atom, so the form's own name is not read."""
    return re.sub(r'^\((\w+) &\S+', '(', line)


def kept_sets(lines):
    """{line: the relations that head an atom in a form before it}."""
    out, seen = {}, set()
    for i, x in enumerate(lines):
        out[i] = frozenset(seen)
        seen |= heads(body(x))
    return out


def corpus_lines(t):
    with gzip.open(CORPUS_TEST + t + '/pairs.jsonl.gz', 'rt') as f:
        return [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]


def arrays(p, s):
    w = np.array([x[2] for x in p['opts']], np.float64)
    m = np.array([x[0] in s and x[1] in REL_KINDS for x in p['opts']], bool)
    return w, m


def nll(batch, th):
    """Mean bits of gold's pick and its derivative in theta, over [(weights, mask, gold)]."""
    tot = der = 0.0
    e = math.exp(th)
    for w, m, g in batch:
        ww = w * np.where(m, e, 1.0)
        z = ww.sum()
        tot += -(math.log(ww[g]) - math.log(z))
        der += -(float(m[g]) - ww[m].sum() / z)
    return tot / len(batch) / LN2, der / len(batch)


def fit():
    t0 = time.time()
    batch, ts = [], set()
    kept = {}
    n = 0
    for p in valid_picks(RANK + 'walks/features-walk-test-parents-0of1.jsonl.zst'):
        t = p['task']
        if t not in kept:
            kept[t] = kept_sets(corpus_lines(t))
        w, m = arrays(p, kept[t][p['line']])
        batch.append((w, m, p['gold_idx']))
        ts.add(t)
        n += 1
        if n % 2000 == 0:
            print('%d picks %.0fs' % (n, time.time() - t0), flush=True)
    lo, hi = -2.0, 4.0  # bisection on the derivative, which rises with theta
    for _ in range(26):
        mid = (lo + hi) / 2
        if nll(batch, mid)[1] > 0:
            hi = mid
        else:
            lo = mid
    th = (lo + hi) / 2
    b0, b1 = nll(batch, 0.0)[0], nll(batch, th)[0]
    res = dict(theta=round(th, 4), test_picks=n, test_tasks=len(ts), test_prior_bits=round(b0, 4), test_bits_at_theta=round(b1, 4), test_saved=round(b0 - b1, 4), gold_in_kept=round(float(np.mean([m[g] for w, m, g in batch])), 4),
               rows='walks/features-walk-test-parents-0of1.jsonl.zst of the rank read', fit_rule='likelihood of gold over gold-alive picks of valid forms, by bisection; S = kept set; one number')
    json.dump(res, open(HERE + 'within-task-fit.json', 'w'), indent=1)
    print(res, flush=True)


def mask_names(x):
    return re.sub(r'&\w+', '&_', x)


def read_nodes(task, arm):
    out = []
    with open(POOL + arm + '/' + task + '.nodes.jsonl.zst', 'rb') as f:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
            d = json.loads(line)
            out.append([d['token'], d['tags'].get('draw', -1), sorted(heads(body(d['clause']))), [str(x) for x in d.get('parents') or ()]])
    return out


def nodes():
    path = HERE + 'within-task-nodes.jsonl'
    done = set()
    if os.path.exists(path):
        for line in open(path):
            d = json.loads(line)
            done.add((d['task'], d['arm']))
    tasks = sorted(os.path.basename(p).split('.')[0] for p in glob.glob(POOL + ARMS[0] + '/*.done.json'))
    todo = [(t, a) for t in tasks for a in ARMS if (t, a) not in done]
    if '--limit' in sys.argv:
        todo = todo[:int(sys.argv[sys.argv.index('--limit') + 1])]
    t0 = time.time()
    with open(path, 'a') as out:
        for c, (t, a) in enumerate(todo, 1):
            out.write(json.dumps(dict(task=t, arm=a, nodes=read_nodes(t, a))) + '\n')
            out.flush()
            el = time.time() - t0
            print('[%d/%d %.0fs %.2f s each eta %.0fs] %s %s' % (c, len(todo), el, el / c, el / c * (len(todo) - c), t, a), flush=True)


NODES = {}


def node_rows(task, arm):
    if not NODES:
        for line in open(HERE + 'within-task-nodes.jsonl'):
            d = json.loads(line)
            NODES[d['task'], d['arm']] = d['nodes']
    return NODES[task, arm]


def load_run(task, arm, census):
    """(nodes as (draw, heads, parent tokens), {census line: cut draw}, {census line: covering node}, counts)."""
    nodes_ = [(d, frozenset(h), frozenset(p)) for _t, d, h, p in node_rows(task, arm)]
    ev = json.load(open(KIT + 'points-eval.json'))
    ev = next(x for x in ev if x['task'] == task)['gold_sexp']
    ev = [x for x in ev.splitlines() if x.strip() and not x.startswith('(OUT')]
    fa = next((x for x in json.load(open(KIT + 'golds-factored.json')) if x['task'] == task), None)
    fa = [x for x in fa['gold_sexp'].splitlines() if x.strip() and not x.startswith('(OUT')] if fa else []
    by_mask = collections.defaultdict(list)
    for i, x in enumerate(census):
        by_mask[mask_names(x)].append(i)
    cut, node_of = {}, {}
    c = collections.Counter()
    for line in open(POOL + arm + '/' + task + '.events.jsonl'):
        e = json.loads(line)
        if e['event'] not in ('cover', 'cover2'):
            continue
        src = ev if e['event'] == 'cover' else fa
        if e['gold'] >= len(src):
            c['cover index past the gold'] += 1
            continue
        hit = by_mask.get(mask_names(src[e['gold']]))
        if not hit:
            c['%s event with no census line' % e['event']] += 1
            continue
        c['%s event mapped' % e['event']] += 1
        for i in hit:
            cut[i] = min(cut.get(i, 1 << 60), e['draw'])
            if 'node' in e:
                node_of.setdefault(i, str(e['node']))
    return nodes_, cut, node_of, c


def found_set(nodes, cut, node_of, defs, opt_derived):
    """The relation names of the nodes before cut, with a derived option where a node before cut reads the node that covers its gold form."""
    s = set()
    reads = set()
    for draw, hs, parents in nodes:
        if draw < cut:
            s |= hs
            reads |= parents
    for name in opt_derived:
        i = defs.get(name)
        if i is not None and node_of.get(i) in reads:
            s.add(name)
    return frozenset(s - {x for x in s if x.startswith('&f')})


def defs_of(lines):
    out = {}
    for i, x in enumerate(lines):
        m = re.match(r'\(\w+ (&\w+)', x)
        if m:
            out[m.group(1)] = i
    return out


def read():
    fit_ = json.load(open(HERE + 'within-task-fit.json'))
    th = fit_['theta']
    path = HERE + 'within-task-rows.jsonl'
    done = set()
    if os.path.exists(path):
        for line in open(path):
            d = json.loads(line)
            done.add((d['task'], d['line'], d['ord'], d['phase']))
    gold = {x['task']: [l for l in x['gold_sexp'].splitlines() if l.strip()] for x in json.load(open(GOLD_HELD))}
    tasks = {os.path.basename(p).split('.')[0] for p in glob.glob(POOL + ARMS[0] + '/*.done.json')}
    kept, runs, fcache = {}, {}, {}
    out = open(path, 'a')
    t0 = time.time()
    n = 0
    counts = collections.Counter()
    for p in valid_picks(RANK + 'walks/features-walk-held-0of1.jsonl.zst'):
        t = p['task']
        key = (t, p['line'], p['ord'], p['phase'])
        n += 1
        if key in done:
            continue
        if t not in kept:
            kept[t] = kept_sets(gold[t])
            runs = {}
            fcache = {}
            if t in tasks:
                for arm in ARMS:
                    runs[arm] = load_run(t, arm, gold[t])
                    counts.update(runs[arm][3])
        S0 = kept[t][p['line']]
        g = p['gold_idx']
        names = [x[0] for x in p['opts']]
        der = [x[0] for x in p['opts'] if x[1] == 'relation']
        defs = defs_of(gold[t])
        row = dict(task=t, line=p['line'], ord=p['ord'], phase=p['phase'], k=p['k'], ctx=p['ctx'], gold=p['gold'], gold_kind=p['gold_kind'], cls='own' if p['own'] else CLASS[p['gold_kind']], q_bits=p['q_bits'])
        sets = dict(kept=S0)
        for arm in runs:
            nodes, cut, node_of, _c = runs[arm]
            c = cut.get(p['line'], 1 << 60)
            ck = (arm, c, tuple(der))
            if ck not in fcache:
                fcache[ck] = found_set(nodes, c, node_of, defs, der)
            sets[arm] = fcache[ck]
            sets['both_' + arm] = S0 | fcache[ck]
            row['cut_' + arm] = None if c == 1 << 60 else c
        w0 = np.array([x[2] for x in p['opts']], np.float64)
        rel = np.array([x[1] in REL_KINDS for x in p['opts']], bool)
        row['check_bits'] = round(-math.log2(w0[g] / w0.sum()), 4)
        for nm, s in sets.items():
            m = np.array([a in s for a in names], bool) & rel
            ww = w0 * np.where(m, math.exp(th), 1.0)
            row['in_' + nm] = bool(m[g])
            row['n_' + nm] = int(m.sum())
            row['saved_' + nm] = round(p['q_bits'] - (-math.log2(ww[g] / ww.sum())), 4)
        row['nrel'] = int(rel.sum())
        row['nopts'] = len(names)
        out.write(json.dumps(row) + '\n')
        out.flush()
        if n % 200 == 0:
            el = time.time() - t0
            print('[%d picks %.0fs %.0f picks/s eta %.0fs] %s' % (n, el, n / el, el / n * (1761 - n), t), flush=True)
    print('done', n, 'picks', dict(counts), flush=True)
    json.dump(dict(counts), open(HERE + 'within-task-cover-map.json', 'w'), indent=1)


def boot(rows, f, seed=0, n=10000):
    ts = sorted({r['task'] for r in rows})
    a = np.zeros(len(ts))
    c = np.zeros(len(ts))
    idx = {t: i for i, t in enumerate(ts)}
    for r in rows:
        a[idx[r['task']]] += f(r)
        c[idx[r['task']]] += 1
    rng = np.random.default_rng(seed)
    d = rng.multinomial(len(ts), np.full(len(ts), 1 / len(ts)), size=n)
    v = (d @ a) / (d @ c)
    return float(a.sum() / c.sum()), float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def summary():
    rows = [json.loads(x) for x in open(HERE + 'within-task-rows.jsonl')]
    fit_ = json.load(open(HERE + 'within-task-fit.json'))
    res = dict(theta=fit_['theta'], picks=len(rows), tasks=len({r['task'] for r in rows}), census_check_max_gap=round(max(abs(r['q_bits'] - r['check_bits']) for r in rows), 4), prior_bits=round(float(np.mean([r['q_bits'] for r in rows])), 4))
    arms = [a for a in ARMS]
    pools = [r for r in rows if 'in_' + arms[0] in r]
    res['pool_picks'] = len(pools)
    res['pool_tasks'] = len({r['task'] for r in pools})
    res['pool_prior_bits'] = round(float(np.mean([r['q_bits'] for r in pools])), 4)
    for a in arms:
        res['picks_with_cut_' + a] = sum(r['cut_' + a] is not None for r in pools)
    res['sets'] = {}
    for nm, sub in [('kept', rows), ('kept on pool tasks', pools)] + [(a, pools) for a in arms] + [('both_' + a, pools) for a in arms]:
        k = nm.split(' on ')[0]
        m, lo, hi = boot(sub, lambda r: r['saved_' + k])
        res['sets'][nm] = dict(picks=len(sub), gold_in_set=round(float(np.mean([r['in_' + k] for r in sub])), 4), rel_options_in_set=round(float(np.mean([r['n_' + k] / r['nrel'] for r in sub])), 4), saved=round(m, 3), lo=round(lo, 3), hi=round(hi, 3))
    res['classes'] = {}
    order = ['derived', 'lib', 'own', 'macro', 'NOT', 'fact', 'comparison']
    for c in order:
        sub = [r for r in rows if r['cls'] == c]
        sp = [r for r in pools if r['cls'] == c]
        e = dict(picks=len(sub), prior_bits=round(float(np.mean([r['q_bits'] for r in sub])), 3), gold_in_kept=round(float(np.mean([r['in_kept'] for r in sub])), 3), saved_kept=round(float(np.mean([r['saved_kept'] for r in sub])), 3), pool_picks=len(sp))
        for a in arms:
            e['gold_in_' + a] = round(float(np.mean([r['in_' + a] for r in sp])), 3) if sp else None
            e['saved_' + a] = round(float(np.mean([r['saved_' + a] for r in sp])), 3) if sp else None
            e['gold_in_both_' + a] = round(float(np.mean([r['in_both_' + a] for r in sp])), 3) if sp else None
            e['saved_both_' + a] = round(float(np.mean([r['saved_both_' + a] for r in sp])), 3) if sp else None
        res['classes'][c] = e
    res['positions'] = {}
    for nm, f in (('first atom', lambda r: r['ord'] == 1), ('second atom', lambda r: r['ord'] == 2), ('third atom', lambda r: r['ord'] == 3), ('later atoms', lambda r: r['ord'] > 3)):
        sub = [r for r in rows if f(r)]
        res['positions'][nm] = dict(picks=len(sub), gold_in_kept=round(float(np.mean([r['in_kept'] for r in sub])), 3), saved_kept=round(float(np.mean([r['saved_kept'] for r in sub])), 3))
    json.dump(res, open(HERE + 'within-task-read.json', 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    dict(nodes=nodes, fit=fit, read=read, summary=summary)[sys.argv[1]]()
