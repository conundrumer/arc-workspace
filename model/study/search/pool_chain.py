#!/usr/bin/env python3
"""Pool arms by the chain, paired on the tasks that every arm finished. It reads <task>.events.jsonl and <task>.done.json, so it takes partial output.

  python3 pool_chain.py POINTS.json BASE=OUT_DIR ARM=OUT_DIR [...] [--every SECONDS]

The first arm is the base. Terms are those of work/measures.md. For each other arm against the base:
  table recall at the arm's whole budget, and paired table recall at k, non-DET and DET apart, by dependency depth;
  task wins, losses and ties on non-DET paired table recall at k;
  candidate solutions (candidates, tasks with one) and test accuracy (tasks);
  the ready set of ground truth forms at the end of each arm, by kind, with the sum of descendants.
A form is one non-OUT line of gold. Denominators hold every such form, also those with no table of their own in the cover check.
"""
import argparse
import collections
import glob
import json
import os
import re
import statistics
import time

NAME = re.compile(r'&[A-Za-z_0-9]+')
BANDS = (1, 1, '1'), (2, 3, '2-3'), (4, 6, '4-6'), (7, 10 ** 6, '7+')


def band(depth):
    return next(name for a, b, name in BANDS if a <= depth <= b)


class Gold:
    """A program's forms: kind, reads, depth, descendants."""

    def __init__(self, sexp):
        lines = [x for x in sexp.strip().split('\n') if not x.startswith('(OUT')]
        self.kinds = [x.split()[0].lstrip('(') for x in lines]
        heads = {}
        for i, x in enumerate(lines):
            m = NAME.search(x)
            if m:
                heads.setdefault(m[0], i)
        self.reads = [sorted({heads[n] for n in NAME.findall(x) if n in heads and heads[n] < i}) for i, x in enumerate(lines)]
        self.depth = []
        for r in self.reads:
            self.depth.append(1 + max((self.depth[j] for j in r), default=0))
        self.below = [set() for _ in lines]
        for i in range(len(lines) - 1, -1, -1):
            for j in self.reads[i]:
                self.below[j] |= {i} | self.below[i]

    def ready(self, found):
        return [i for i in range(len(self.kinds)) if i not in found and all(j in found for j in self.reads[i])]


def load(folder):
    tasks = {}
    for path in glob.glob(folder + '/*.done.json'):
        task = os.path.basename(path)[:-len('.done.json')]
        try:
            done = json.load(open(path))
            covers, cands = {}, []
            for line in open(os.path.join(folder, task + '.events.jsonl')):
                e = json.loads(line)
                if e['event'] == 'cover' and e['gold'] not in covers:
                    covers[e['gold']] = e['draw'], e['seconds']
                elif e['event'] == 'candidate':
                    cands.append(e['seconds'])
        except (ValueError, OSError):
            continue
        tasks[task] = done, covers, cands
    return tasks


def count_recall(gold, covers, tasks, limit, group):
    """(found, total) by group of forms."""
    found, total = collections.Counter(), collections.Counter()
    for t in tasks:
        g = gold[t]
        for i, kind in enumerate(g.kinds):
            key = group(kind, g.depth[i])
            total[key] += 1
            found[key] += i in covers[t][1] and covers[t][1][i][0] <= limit(t)
    return found, total


def non_det(kind, depth):
    return 'DET' if kind == 'DET' else 'non-DET', band(depth)


def table(gold, base, arm, tasks, ks, name_a, name_b):
    print('  %-16s %12s %12s %12s %12s %8s' % ('kind, depth', name_a[:12] + ' whole', name_b[:12] + ' whole', name_a[:12] + ' @k', name_b[:12] + ' @k', 'forms'))
    inf = lambda t: 10 ** 12  # noqa: E731
    a0, n = count_recall(gold, base, tasks, inf, non_det)
    b0, _ = count_recall(gold, arm, tasks, inf, non_det)
    ak, _ = count_recall(gold, base, tasks, ks.get, non_det)
    bk, _ = count_recall(gold, arm, tasks, ks.get, non_det)
    for key in sorted(n, key=lambda k: (k[0] == 'DET', [b[2] for b in BANDS].index(k[1]))):
        print('  %-16s %12d %12d %12d %12d %8d' % (key[0] + ' ' + key[1], a0[key], b0[key], ak[key], bk[key], n[key]))
    for kind in 'non-DET', 'DET':
        s = lambda c: sum(v for k, v in c.items() if k[0] == kind)  # noqa: E731
        print('  %-16s %12d %12d %12d %12d %8d' % (kind + ' all', s(a0), s(b0), s(ak), s(bk), s(n)))


def wins(gold, base, arm, tasks, ks):
    w = l = e = 0
    for t in tasks:
        g = gold[t]
        nd = {i for i, k in enumerate(g.kinds) if k != 'DET'}
        a = sum(i in nd and d <= ks[t] for i, (d, _) in base[t][1].items())
        b = sum(i in nd and d <= ks[t] for i, (d, _) in arm[t][1].items())
        w, l, e = w + (b > a), l + (b < a), e + (b == a)
    return w, l, e


def ready(gold, arm, tasks):
    by = collections.Counter()
    desc = collections.Counter()
    for t in tasks:
        g = gold[t]
        for i in g.ready(set(arm[t][1])):
            by[g.kinds[i]] += 1
            desc[g.kinds[i]] += len(g.below[i])
    return ' '.join('%s %d (%d desc)' % (k, by[k], desc[k]) for k in sorted(by)) or '-'


def report(a):
    gold = {x['task']: Gold(x['gold_sexp']) for x in json.load(open(a.points))}
    arms = collections.OrderedDict()
    for spec in a.arms:
        name, _, path = spec.rpartition('=')
        arms[name or os.path.basename(path.rstrip('/'))] = load(path)
    names = list(arms)
    ok = set.intersection(*[set(v) for v in arms.values()])
    drop = {t for t in ok if not arms[names[0]][t][0]['gold']}
    tasks = sorted(t for t in ok - drop if t in gold)
    print('tasks finished: %s; in every arm %d; left out, gold does not replay: %s' % (' '.join('%s %d' % (n, len(arms[n])) for n in names), len(tasks), ' '.join(sorted(drop)) or '-'))
    if not tasks:
        return
    print('%-14s %9s %7s %6s %7s %9s %6s %6s %6s %7s %7s' % ('arm', 'proposals', 'per s', 'equal', 'nodes', 'nodes/s', 'budget', 'cands', 'tasks', 'right', 'tables'))
    for n in names:
        ds = [arms[n][t][0] for t in tasks]
        wall = sum(d['seconds'] for d in ds)
        cpu = [d['counts'].get('cpu seconds grow') for d in ds]
        cpu_ok = all(x is not None for x in cpu)
        secs = sum(cpu) if cpu_ok else wall
        tries, nodes = sum(d['draws'] for d in ds), sum(d['nodes'] for d in ds)
        print('%-14s %9d %7.1f %5.0f%% %7d %9.2f %6s %6d %6d %7d %7d' % (
            n[:14], tries, tries / max(secs, 1e-9), 100 * sum(d['counts'].get('node:equal', 0) for d in ds) / max(tries, 1), nodes, nodes / max(secs, 1e-9), 'CPU' if cpu_ok else 'wall',
            sum(d['candidates'] for d in ds), sum(d['candidates'] > 0 for d in ds), sum(d['right'] > 0 for d in ds), sum(d['covered'] for d in ds)))
    if a.at:
        print('recall by wall seconds, %d tasks:' % len(tasks))
        print('  %-14s %7s %9s %9s %11s %9s %11s' % ('arm', 'seconds', 'non-DET', 'DET', 'proposals', 'cands', 'task cands'))
        for n in names:
            for t in a.at:
                nd = dt = cands = with_c = 0
                for x in tasks:
                    g = gold[x]
                    got = [i for i, (_, s) in arms[n][x][1].items() if s <= t]
                    dt += sum(g.kinds[i] == 'DET' for i in got)
                    nd += sum(g.kinds[i] != 'DET' for i in got)
                    c = sum(s <= t for s in arms[n][x][2])
                    cands, with_c = cands + c, with_c + (c > 0)
                print('  %-14s %7d %9d %9d %11s %9d %11d' % (n[:14], t, nd, dt, '', cands, with_c))
    base = arms[names[0]]
    for n in names[1:]:
        arm = arms[n]
        ks = {t: min(base[t][0]['draws'], arm[t][0]['draws']) for t in tasks}
        print('\n%s against %s, %d tasks, median k %d proposals, whole budget is the run\'s wall time' % (n, names[0], len(tasks), statistics.median(ks.values())))
        table(gold, base, arm, tasks, ks, names[0], n)
        print('  non-DET at the whole budget: wins %d, losses %d, ties %d (the pass, where the arm changes throughput)' % wins(gold, base, arm, tasks, dict.fromkeys(tasks, 10 ** 12)))
        print('  non-DET at k: wins %d, losses %d, ties %d (the read of precision)' % wins(gold, base, arm, tasks, ks))
    for n in names:
        print('ready set, %s: %s' % (n, ready(gold, arms[n], tasks)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('points')
    ap.add_argument('arms', nargs='+')
    ap.add_argument('--every', type=float, default=0)
    ap.add_argument('--at', type=int, nargs='*', default=[], help='wall seconds at which to give recall and candidates')
    a = ap.parse_args()
    while True:
        report(a)
        if not a.every:
            return
        time.sleep(a.every)
        print('\n' + '=' * 60)


if __name__ == '__main__':
    main()
