"""Step P of the Ident source type: draws, forms and gold of arms off and type, with the run's decision rule.

  python3 -I search_ident_type_report.py RUN_FOLDER [ARM_A ARM_B]

Reads out/<arm>/<task>/work/<task>.log (lines `prof`, `all counts`, `adm stats`), <task>.out.jsonl.cover and disk.txt.
"""
import collections
import glob
import json
import os
import re
import sys

ARMS = tuple(sys.argv[2:4]) or ('off', 'type')
KEYS = 'search.dead:try:unjoined', 'search.dead:try:empty', 'search.dead:complete', 'search.dead:reach', 'node:equal'


def job(d):
    """A job's totals. Draws go on across renewals, so the last progress line gives the job's count; seconds are the sum over processes of each one's last CPU figure. A kit gives `prof` lines, or `rss ... cpu C s, D samples ... generation G` lines. `all counts` (or else the last `counts` line) and `adm stats` hold the last process only, and a worker killed past its end writes no `all counts`, so those rates read over the draws of the processes that wrote them."""
    t = os.path.basename(d)
    r = dict(task=t, draws=0, cpu=0.0, cover=set(), state=None, counts=None, adm=None)
    cpu, rss, rdraws = {}, {}, 0
    for line in open(f'{d}/work/{t}.log', errors='replace'):
        if line.startswith('prof '):
            p = json.loads(line[5:])
            r['draws'] = p.get('draws', r['draws'])
            cpu[p.get('gen')] = p.get('t', 0)
        elif line.startswith('rss ') and ', cpu ' in line:
            m = re.search(r', cpu (\d+) s, (\d+) samples.*generation (\d+)', line)
            if m:
                rss[int(m[3])] = int(m[1])
                rdraws = int(m[2])
        elif line.startswith('all counts '):
            r['counts'] = json.loads(line[len('all counts '):])
        elif line.startswith('counts ') and r['counts'] is None or (line.startswith('counts ') and r.get('from_counts')):
            r['counts'], r['from_counts'] = json.loads(line[len('counts '):]), True
        elif line.startswith('adm stats '):
            r['adm'] = json.loads(line[len('adm stats '):])
    if cpu:
        r['cpu'] = sum(cpu.values())
    else:  # a renewal keeps the process (execv), so its CPU figure goes on across generations
        r['cpu'], r['draws'] = max(rss.values(), default=0), rdraws
    r['cover'] = {json.loads(x)['gold'] for x in open(f'{d}/work/{t}.out.jsonl.cover') if x.strip()}
    rows = [x.split() for x in open(f'{d}/disk.txt') if len(x.split()) == 3 and x.split()[0].isdigit()]
    r['state'] = max((int(x[1]) for x in rows), default=None)
    return r


def main(run):
    A = {a: {os.path.basename(d): job(d) for d in sorted(glob.glob(f'{run}/out/{a}/*'))} for a in ARMS}
    tasks = sorted(set(A[ARMS[0]]) & set(A[ARMS[1]]))
    print(f'| task | draws {ARMS[0]} | draws {ARMS[1]} | wall s {ARMS[0]} | wall s {ARMS[1]} | gold {ARMS[0]} | gold {ARMS[1]} | state KiB {ARMS[0]} | state KiB {ARMS[1]} |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    for t in tasks:
        x, y = (A[a][t] for a in ARMS)
        print(f"| {t} | {x['draws']} | {y['draws']} | {x['cpu']:.0f} | {y['cpu']:.0f} | {len(x['cover'])} | {len(y['cover'])} | {x['state']} | {y['state']} |")
    d = {a: sum(A[a][t]['draws'] for t in tasks) for a in ARMS}
    c = {a: sum(A[a][t]['cpu'] for t in tasks) for a in ARMS}
    g = {a: sum(len(A[a][t]['cover']) for t in tasks) for a in ARMS}
    a0, a1 = ARMS
    fall = 1 - (d[a1] / c[a1]) / (d[a0] / c[a0])
    print(f"\ndraws per s: {a0} {d[a0] / c[a0]:.3f}, {a1} {d[a1] / c[a1]:.3f}, fall {fall:.1%}. Gold covered: {a0} {g[a0]}, {a1} {g[a1]}.")
    print(f'\n| count per draw, last processes | {a0} | {a1} |\n| --- | --- | --- |')
    n = {a: sum((A[a][t]['counts'] or {}).get('draws', 0) for t in tasks) for a in ARMS}
    for k in KEYS:
        s = [sum((A[a][t]['counts'] or {}).get(k, 0) for t in tasks) / max(n[a], 1) for a in ARMS]
        print(f'| {k} | {s[0]:.4f} | {s[1]:.4f} |')
    print('draws in those processes:', n)
    adm = collections.Counter()
    for a in ARMS:
        for t in tasks:
            for (phase, kind, ok), v in A[a][t]['adm'] or []:
                adm[a, kind, ok] += v
    for a in ARMS:
        y, m = adm[a, 'label', True], adm[a, 'label', False]
        print(f'label options {a}: admitted {y}, refused {m}, refused share {m / max(y + m, 1):.3f}')
    print(f'\nFall in draws per s {fall:.1%}, fall in gold {g[a0] - g[a1]}. The rule is in the run manifest.')


main(sys.argv[1])
