#!/usr/bin/env python3
"""Ready forms found by each arm of a seeded pool run, by parent count, with the chance that a visit's scope holds all of a form's parents. Reads partial output.

  python3 search_oracle_report.py POINTS.json RUN_DIR [RUN_DIR ...] [--arms name ...]

A run folder holds <arm><level>_search/ folders, such as oracle2_search. A ready form is a gold form past the seed cut whose read forms are all seeded. It is found when a
cover event with draw above 0 names it. Where the arm has `visit` events, a scope holds a form when all its parents are among the visit's form ids. Oracle context: gold is read.
"""
import argparse
import collections
import glob
import json
import os
import re
import statistics

NAME = re.compile(r'&[A-Za-z_0-9]+')


def gold(sexp, level):
    lines = [x for x in sexp.strip().split('\n') if not x.startswith('(OUT')]
    kinds = [x.split()[0].lstrip('(') for x in lines]
    heads = [NAME.search(x)[0] for x in lines]
    index = {}
    for i, h in enumerate(heads):
        index.setdefault(h, i)
    reads, depth = [], []
    for i, x in enumerate(lines):
        r = sorted({index[n] for n in NAME.findall(x) if n in index and index[n] < i})
        reads.append(r)
        depth.append(1 + max((depth[j] for j in r), default=0))
    cut = -(-max(depth) * level // 3)
    seeds = [i for i in range(len(lines)) if depth[i] <= cut]
    fid = {i: k for k, i in enumerate(seeds)}
    ready = [i for i in range(len(lines)) if i not in fid and all(j in fid for j in reads[i])]
    return kinds, reads, fid, ready


def load(folder):
    out = {}
    for path in glob.glob(folder + '/*.events.jsonl'):
        task = os.path.basename(path).split('.')[0]
        covers, visits, cands, ended = set(), [], 0, False
        for line in open(path):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e['event'] == 'cover' and e['draw'] > 0:
                covers.add(e['gold'])
            elif e['event'] == 'visit':
                visits.append(set(e['fids']))
            elif e['event'] == 'candidate':
                cands += 1
            elif e['event'] == 'done':
                ended = True
        out[task] = dict(covers=covers, visits=visits, cands=cands, ended=ended)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('points')
    ap.add_argument('runs', nargs='+')
    ap.add_argument('--running', action='store_true', help='count tasks that have not ended')
    a = ap.parse_args()
    specs = {x['task']: x['gold_sexp'] for x in json.load(open(a.points))}
    for run in a.runs:
        for folder in sorted(glob.glob(run + '/*_search')):
            name = os.path.basename(folder)
            level = int(re.search(r'(\d)_search', name)[1])
            rows = load(folder)
            n, hit, held, any_held, ctx = collections.Counter(), collections.Counter(), collections.defaultdict(list), collections.Counter(), []
            kind_n, kind_hit = collections.Counter(), collections.Counter()
            tasks = cands = 0
            for t, r in rows.items():
                if (not r['ended'] and not a.running) or t not in specs:
                    continue
                tasks += 1
                cands += r['cands']
                kinds, reads, fid, ready = gold(specs[t], level)
                ctx += [len(v) for v in r['visits']]
                for i in ready:
                    p = min(len(reads[i]), 4)
                    n[p] += 1
                    kind_n[kinds[i]] += 1
                    hit[p] += i in r['covers']
                    kind_hit[kinds[i]] += i in r['covers']
                    if r['visits']:
                        need = {fid[j] for j in reads[i]}
                        share = sum(need <= v for v in r['visits']) / len(r['visits'])
                        held[p].append(share)
                        any_held[p] += share > 0
            print('%s: tasks ended %d, candidates %d, ready %d, found %d; by kind %s%s' % (
                name, tasks, cands, sum(n.values()), sum(hit.values()), {k: '%d of %d' % (kind_hit[k], kind_n[k]) for k in sorted(kind_n)},
                '; median forms in a visit\'s scope %d, visits %d' % (statistics.median(ctx), len(ctx)) if ctx else ''))
            for p in sorted(n):
                extra = ''
                if held[p]:
                    extra = '; mean share of visits whose scope holds all parents %.4f, forms held by any visit %d' % (statistics.mean(held[p]), any_held[p])
                print('   %s parents: ready %d, found %d%s' % (p if p < 4 else '4+', n[p], hit[p], extra))


if __name__ == '__main__':
    main()
