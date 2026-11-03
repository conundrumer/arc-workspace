"""Read of the joint Ident arm against the bundle: the tables of search_node_score_read.py, with this arm's rule and the INIT patience counts.

  python3 -I search_identj_read.py OUT IDENT_FILE GOLD

Arms are `bundle`/`bundlef`, and `identj`/`identjf` and `identp`/`identpf` (Ident INIT patience alone), seeds 0 and 1. Each arm is read against the bundle by the same rule. The rule: the arm takes the bundle's place when its Ident-only forms on the 37, as the mean of two seeds summed over tasks, are 4 or more above the bundle's, its non-DET forms are -8.5 or more, and its DET forms are -3 or more against the bundle, on the tasks whose 4 jobs are all valid.
"""
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_node_score_read as R  # noqa: E402

ARMS = 'bundle', 'identj'
IDENT_BAR, NONDET_FLOOR, DET_FLOOR = 4, -8.5, -3


def verdict(groups, c1, rng):
    for arm in ('identj', 'identp'):
        if (arm, False) in groups:
            print('== %s' % arm)
            verdict_one(groups, rng, arm)
    patience(sys.argv[1])
    at_k(sys.argv[1], 'identp', rng)
    cpus(sys.argv[1])


def last_draws(log):
    """The highest draw count a job's log gives: draws go on across the processes of a job."""
    best = 0
    for line in open(log, errors='replace'):
        m = R.re.search(r'(\d+) (?:draws|samples)', line) if line.startswith(('end:', 'rss ')) else None
        if m:
            best = max(best, int(m[1]))
    return best


def at_k(out, arm, rng):
    """The arm against the bundle at an equal count of draws, for arms that ran on other pods: per task and seed, k is the lower of the two jobs' draw counts, and each job counts the gold forms its cover lines give at draw k or before."""
    jobs = {(a, t): f for a, t, f in R.PA.job_folders(out)}
    gold = {x['task']: R.gold_info(x['gold_sexp']) for x in R.json.load(open(sys.argv[3]))}
    ident = R.json.load(open(sys.argv[2]))
    rows = collections.defaultdict(lambda: collections.defaultdict(list))
    for (a, t), f in jobs.items():
        base, fold, seed = R.parse_arm(a)
        if base != arm:
            continue
        b = jobs.get(('bundle%s_s%d' % ('f' if fold else '', seed), t))
        if not b:
            continue
        ka, kb = last_draws('%s/work/%s.log' % (f, t)), last_draws('%s/work/%s.log' % (b, t))
        k = min(ka, kb)
        io = set(ident.get(t, {}).get('ident_only', []))
        kinds = gold[t]['kinds'] if isinstance(gold[t], dict) and 'kinds' in gold[t] else None
        for side, folder in ((arm, f), ('bundle', b)):
            got = {x['gold'] for x in R.PA.read_lines('%s/work/%s.out.jsonl.cover' % (folder, t)) if x.get('draw', 0) <= k}
            det = sum(kinds[g] in R.DET_KINDS for g in got if g < len(kinds)) if kinds else 0
            rows[fold, t][side].append(dict(all=len(got), ident=len(got & io), det=det, k=k))
    for fold in (False, True):
        ts = sorted(t for (fd, t), v in rows.items() if fd == fold and len(v[arm]) == 2 and len(v['bundle']) == 2)
        if not ts:
            continue
        out_row = []
        for name in ('ident', 'all', 'det'):
            diff = [np.mean([x[name] for x in rows[fold, t][arm]]) - np.mean([x[name] for x in rows[fold, t]['bundle']]) for t in ts]
            out_row.append('%s D %.1f [%.1f, %.1f]' % (name, *R.band(diff, rng)))
        print('%s at equal draws, %s, %d tasks: %s; median k %d' % (arm, 'the 13' if fold else 'the 37', len(ts), '  '.join(out_row), np.median([x['k'] for t in ts for x in rows[fold, t][arm]])))


def cpus(out):
    """The CPU model of each pod, from cpu.txt beside the out folder."""
    p = R.os.path.join(R.os.path.dirname(out.rstrip('/')), 'cpu.txt')
    if R.os.path.exists(p):
        for line in open(p):
            if line.startswith('pod') or 'Model name' in line and line.startswith('pod'):
                print(line.rstrip()[:160])


def verdict_one(groups, rng, arm):
    measures = dict(ident=lambda r: r['ident'], nondet=lambda r: len(r['covered']) - r['det'], det=lambda r: r['det'], all=lambda r: len(r['covered']))
    for fold in (False, True):
        need = [groups.get((a, fold)) for a in ('bundle', arm)]
        if not all(need):
            print('fold %s: an arm has no jobs' % fold)
            continue
        tasks = None
        for g in need:
            for seed in (0, 1):
                ok = {t for t, r in g.get(seed, {}).items() if r['valid']}
                tasks = ok if tasks is None else tasks & ok
        tasks = sorted(tasks or ())
        row = {}
        for name, f in measures.items():
            diff = [np.mean([f(groups[arm, fold][s][t]) for s in (0, 1)]) - np.mean([f(groups['bundle', fold][s][t]) for s in (0, 1)]) for t in tasks]
            row[name] = R.band(diff, rng) if tasks else (float('nan'),) * 3
        print('%s, %d tasks: Ident-only D %.1f [%.1f, %.1f]  non-DET D %.1f [%.1f, %.1f]  DET D %.1f [%.1f, %.1f]  all D %.1f [%.1f, %.1f]' % (
            'the 13' if fold else 'the 37', len(tasks), *row['ident'], *row['nondet'], *row['det'], *row['all']))
        if not fold:
            ok = row['ident'][0] >= IDENT_BAR and row['nondet'][0] >= NONDET_FLOOR and row['det'][0] >= DET_FLOOR
            print('verdict:', 'the arm takes the bundle\'s place' if ok else 'the bundle stays', '(rule: Ident-only D >= %g, non-DET D >= %g, DET D >= %g, on the 37)' % (IDENT_BAR, NONDET_FLOOR, DET_FLOOR))


def patience(out):
    """INIT visits that took the Ident patience, and of them those whose first Ident read came before the visit ended, from the last `counts` line of each job."""
    c = collections.Counter()
    for arm, task, folder in R.PA.job_folders(out):
        last = None
        for line in open('%s/work/%s.log' % (folder, task), errors='replace'):
            if line.startswith('counts '):
                last = line
        if last:
            d = json.loads(last[7:])
            c[arm.rstrip('01').rstrip('_s'), 'took'] += d.get('search:ident init patience', 0)
            c[arm.rstrip('01').rstrip('_s'), 'first read'] += d.get('search:ident init first read', 0)
    for a in sorted({k[0] for k in c}):
        t, f = c[a, 'took'], c[a, 'first read']
        print('%s: INIT visits with the Ident patience %d, with a first Ident read %d (%.2f)' % (a, t, f, f / t if t else float('nan')))


_expected = R.PA.expected_name


def expected_name(arm):
    """The node score name a job's marker line must give: `mt` for the joint arm, else as the parity script says."""
    return 'mt' if R.parse_arm(arm)[0] == 'identj' else _expected(arm)


R.PA.expected_name = expected_name
R.verdict = verdict
if __name__ == '__main__':
    R.main()
