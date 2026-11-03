#!/usr/bin/env python
"""The non-held fit points: each form of the rank read's fit tasks (the tasks of its RULE lists) of kind KINDS, gold's parents plus the forms of one late visit of the target's kind in the task's seeded corpus pool.

  python features_ps_points_fit.py PART SHARD_I SHARD_N [--kinds RULE,DET,INIT]    PART = test or train. Appends to points-fit-pool-PART-IofN.jsonl and skips tasks that it holds.

The pool's gold is seeded to one third of depth, so a seeded node is a gold form. A seeded form whose text equals a line of corpus-v3mix after renaming, at the same index, maps to that line. A mapped form in the form's parents leaves the visit's forms, and the kept forms read gold's head in its place. A task with a seeded form that doesn't map has no points. There is no condition that the pool found the read forms: these rows teach the junk of a scope, and the fit's forms come from a seeded pool. `line` is unique over all parts.
"""
import collections
import gzip
import io
import json
import os
import re
import sys
import time
import zlib

import numpy as np
import zstandard

ME = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-dag-conversion-heldout37/'
sys.path.insert(0, ME)
import features_perrel_keys as K  # noqa: E402
import features_dag_order as D  # noqa: E402

KINDS = ('RULE', 'DET', 'INIT')

RANK = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-rank-context-rows-heldout37/'
B = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-corpus-pool-seed1-120s-ship7/level1_search/'
CORPUS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/corpus-v3mix/'
W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/'


def norm(x):
    m = {}
    return re.sub(r'&[rf]\d+', lambda h: m.setdefault(h[0], '&%d' % len(m)), x)


def nodes(t):
    """{form id: (clause, depth, node)} from the fields before x_rows, which a parse of the whole line would cost."""
    out = {}
    with open(B + t + '.nodes.jsonl.zst', 'rb') as f:
        for x in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
            i = x.find(',"x_rows"')
            d = json.loads(x[:i] + '}')
            m = re.match(r'\(\w+ &f(\d+)', d['clause'])
            if m and int(m[1]) not in out:
                out[int(m[1])] = (d['clause'], d['depth'], int(d['token']))
    return out


def one(t, lines_all, rows, tally):
    lines = [x for x in lines_all if not x.startswith('(OUT')]
    ev = [json.loads(x) for x in open(B + t + '.events.jsonl')]
    allvis = {k: [e for e in ev if e.get('event') == 'visit' and e['kind'] == k and e['fids']] for k in KINDS}
    allvis = {k: v[len(v) // 2:] for k, v in allvis.items()}
    prog = D.ProgramDag(lines_all)
    hv = lambda i: prog.content[D.parse(lines[i])[1]]  # noqa: E731  # a form's hash: its content, not its place
    nd = nodes(t)
    bynode = {v[2]: f for f, v in nd.items()}
    mapped = {}
    for e in ev:
        if e.get('event') == 'cover' and e['draw'] == 0:
            f = bynode.get(e['node'])
            if f is None:
                continue
            if e['gold'] >= len(lines) or norm(nd[f][0]) != norm(lines[e['gold']]):
                tally['task with a seed off the text'] += 1
                return []
            mapped[f] = e['gold']
    head = [K.NAME.search(x)[0] for x in lines]
    dep = {i: 1 + prog.depths[D.parse(x)[1]] for i, x in enumerate(lines)}  # the form's depth in the program DAG
    out = []
    for g in rows:
        x = lines_all[g]
        kind = x.split()[0].lstrip('(')
        vis = allvis.get(kind)
        if not vis:
            tally['no %s visit' % kind] += 1
            continue
        gi = lines.index(x)  # the form in the lines without OUT
        rng = np.random.RandomState(zlib.crc32(('fit %s %s' % (t, hv(gi))).encode()))
        w = np.array([v['tries'] for v in vis], float)
        v = vis[rng.choice(len(vis), p=w / w.sum())]
        if any(f not in nd for f in v['fids']):
            tally['visit form not in the nodes'] += 1
            continue
        clo = K.parents(lines, gi)
        cl = set(clo)
        ren = {f: head[i] for f, i in mapped.items() if i in cl}
        kept = [f for f in v['fids'] if f not in ren]
        sub = lambda s: re.sub(r'&f(\d+)', lambda m: ren.get(int(m[1]), m[0]), s)  # noqa: E731
        z = [(dep[i], zlib.crc32(('%s %s' % (hv(i), hv(gi))).encode()), lines[i]) for i in clo]
        z += [(nd[f][1], zlib.crc32(('p%d %s' % (f, hv(gi))).encode()), sub(nd[f][0])) for f in kept]
        z.sort(key=lambda q: q[:2])
        out.append(dict(arm='corpus-seed1', task=t, form=g, kind=kind, form_key=hv(gi), key=D.parse(x)[1], line_id=g, stratum='fit', scope=[q[2] for q in z], target=x, gold_forms=len(clo), pool_forms=len(kept), covers_removed=len(ren), covers_kept=0, visit_forms=len(v['fids'])))
        tally['points'] += 1
    return out


def main():
    global KINDS
    part, i, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    if len(sys.argv) > 5 and sys.argv[4] == '--kinds':
        KINDS = tuple(sys.argv[5].split(','))
    forms = json.load(open(RANK + 'forms-%s.json' % part))
    by = collections.defaultdict(list)
    for r in forms:
        by[r[4]].append(r[5])
    leave = set(open(W + 'held/leave_out.txt').read().split())
    have = {e.name[:8] for e in os.scandir(B) if e.name.endswith('.events.jsonl')}
    tasks = sorted(t for t in by if t in have and t not in leave)
    tasks = [t for j, t in enumerate(tasks) if j % n == i]
    path = ME + 'points-fit-pool-%s-%dof%d.jsonl' % (part, i, n)
    done = set()
    if os.path.exists(path):
        done = {json.loads(x)['task'] for x in open(path)}
    tally = collections.Counter()
    t0 = time.time()
    with open(path, 'a') as out:
        for c, t in enumerate(tasks, 1):
            if t in done:
                continue
            with gzip.open(CORPUS + t + '/pairs.jsonl.gz', 'rt') as f:
                lines_all = [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]
            rows = [g for g, x in enumerate(lines_all) if x.split()[0].lstrip('(') in KINDS and not x.startswith('(OUT')]
            for p in one(t, lines_all, rows, tally):
                p['line'] = zlib.crc32(('%s %s' % (t, p['form_key'])).encode())
                out.write(json.dumps(p) + '\n')
            out.flush()
            if c % 50 == 0 or c == len(tasks):
                el = time.time() - t0
                print('[%d/%d %.0fs %.1f tasks/s eta %.0fs] %s' % (c, len(tasks), el, c / el, el / c * (len(tasks) - c), dict(tally)), flush=True)
    print('done', dict(tally), flush=True)


main()
