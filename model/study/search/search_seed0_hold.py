#!/usr/bin/env python3
"""Seed 0 hold rate: for each gold form whose parents all appeared in the pool, how often a later visit's scope held them together, and whether the form was then found.

  python3 search_seed0_hold.py POINTS.json ARM_DIR [ARM_DIR ...]

ARM_DIR holds <task>.events.jsonl with `cover` and `visit` events, and <task>.nodes.jsonl.zst, whose records give each node's form through the clause's head &f<id>.
A parent's form is the pool form of the node that first covered it. Counts run from the time the last parent appeared to the task's end. Reads gold, for a report only.
"""
import argparse
import collections
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_oracle_report as O  # noqa: E402

HEAD = re.compile(r'\(\w+ &f(\d+)')


def node_forms(path):
    out = {}
    text = subprocess.run(['zstd', '-dc', path], capture_output=True, check=False).stdout.decode(errors='replace')
    for line in text.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        m = HEAD.match(r.get('clause') or '')
        if m:
            out[int(r['token'])] = int(m[1])
    return out


def read(path):
    cover, visits = {}, []
    for line in open(path):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e['event'] == 'cover':
            cover.setdefault(e['gold'], (e['seconds'], e['node']))
        elif e['event'] == 'visit':
            visits.append((e['seconds'], set(e['fids'])))
    return cover, visits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('points')
    ap.add_argument('arms', nargs='+')
    a = ap.parse_args()
    specs = {x['task']: x['gold_sexp'] for x in json.load(open(a.points))}
    for arm in a.arms:
        n, held, found, shares = collections.Counter(), collections.Counter(), collections.Counter(), collections.defaultdict(list)
        kn, kf = collections.Counter(), collections.Counter()
        tasks = 0
        for path in glob.glob(arm + '/*.events.jsonl'):
            t = os.path.basename(path).split('.')[0]
            if t not in specs:
                continue
            cover, visits = read(path)
            if not cover:
                continue
            tasks += 1
            nodes = node_forms(path.replace('.events.jsonl', '.nodes.jsonl.zst'))
            kinds, reads, _, _ = O.gold(specs[t], 3)
            for i, r in enumerate(reads):
                if not r or not all(j in cover for j in r):
                    continue
                start = max(cover[j][0] for j in r)
                need = {nodes.get(cover[j][1]) for j in r}
                later = [v for s, v in visits if s >= start]
                share = sum(need <= v for v in later) / len(later) if later and None not in need else 0.0
                p = min(len(r), 4)
                hit = i in cover
                n[p] += 1
                held[p] += share > 0
                found[p] += hit
                shares[p].append(share)
                kn[kinds[i]] += 1
                kf[kinds[i]] += hit
        print('%s: tasks %d; forms with all parents in the pool %d' % (os.path.basename(arm.rstrip('/')), tasks, sum(n.values())))
        for p in sorted(n):
            print('   %s parents: forms %d, held by a later visit %d, found %d, mean share of later visits that hold them %.4f' % (
                p if p < 4 else '4+', n[p], held[p], found[p], sum(shares[p]) / len(shares[p])))
        print('   by kind', {k: '%d of %d' % (kf[k], kn[k]) for k in sorted(kn)})


if __name__ == '__main__':
    main()
