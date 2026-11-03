"""Reads the jobs of a node score run: forms covered, the chance per opening at the top ranks, the cost, and the verdict by the decision rule.

  <python> -I search_node_score_read.py OUT IDENT_FILE [GOLD]

OUT         the folder of the jobs, OUT/<arm>/<task>/ as run3600.sh writes it (OUT/out is used where it exists).
IDENT_FILE  gold-ident-only-kit50.json from search_node_score_gold_ident.py.
GOLD        the kit's points-eval.json. Default: GOLD in the environment, else points-eval.json in the folder above OUT.
Environment: READ_CACHE is the file where the script keeps what it read of each job (default read-cache.json in the working folder). A job already in it
with the same bank and log sizes is not read again; a job with no `end:` line is not kept. READ_SEED (default 1) seeds the resampling.

Arms are named bundle, mt, depth or parity, with f added for the 13 fold tasks, then _s0 or _s1 for the seed. Any other name is read as a plain arm of that name.

What is printed:
  1. Per arm and task set: the jobs that ended and the jobs still open, the jobs that are valid, and the mean over seeds of the sum over tasks of the forms covered
     (all, DET, non-DET, Ident-only). A job counts when its log has an end: line.
  2. Per arm and task set: the cost (deaths and kills from supervisor.log, mean and q99 of ns_ms, search:seconds take per kept node of the bank).
  3. Per arm and task set: the chance per opening at the top ranks: C1, C1-held, C3, R-RULE, and n (ready form-runs, jobs left out by the uses check, form-runs with no opening).
  4. Paired differences against the bundle, with 90% bands, where the bundle, mt and depth arms have tasks whose 6 jobs are all valid, and the verdict by the rules.
A job is valid where its log has an end: line and no `uniform policy` or `steers off` line, has the node score line of the arm's name (none for a bundle job), and its
ns_errors are at most .1% of its nodes.
The chance measure follows the design: kept picks by the bank's lineage, a uses check, kept covers, reach, ready form-runs, and for each opening the chance that
the top picks hold all the reads. Medians are over the form-runs that have an opening.
"""
import collections
import glob
import json
import math
import os
import re
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_node_score_parity as PA  # noqa: E402

PICKS_TOP = 5  # scored picks in a scope; the next pick, if any, is the least used one
CHANCE_BAR = .1
RESAMPLES = 10000
BAND = (5, 95)
INVALID_LOG = ('uniform policy', 'steers off')
ERROR_SHARE = .001
ARM = re.compile(r'^(bundle|mt|depth|parity|\w+?)(f?)_s(\d+)$')
DET_KINDS = ('DET', 'RIGID_DET')
D_FLOOR_13, D_FLOOR_DET = -3, -3
RATIO = 3


def solve_c(w):
    """c with the sum over nodes of 1 - exp(-w c) equal to 5: each node's chance of a scored pick, in the race form of the Gumbel draw."""
    c = 5.0 / w.sum()
    for _ in range(40):
        e = np.exp(-w * c)
        f = (1 - e).sum() - 5.0
        if abs(f) < 1e-7:
            break
        c = max(c - f / (w * e).sum(), c / 8)
    return c


def p_all(masses, c, extra):
    """P(a set of needed reads is all hit), by inclusion and exclusion over needed bits. masses[sig]: weight of nodes whose pick holds the reads of sig. extra: weight added per read."""
    m = len(masses)
    tot = 0.0
    for T in range(m):
        if T == 0:
            tot += 1.0
            continue
        hit = sum(masses[s] for s in range(1, m) if s & T)
        k = bin(T).count('1')
        tot += (-1) ** k * math.exp(-c * (hit + k * extra))
    return max(tot, 0.0)


def need_masses(sig, idx, w, n, nb, rest_bits):
    """Masses over the reads still needed after the least-used pick: an array of size 2 ** k, and k."""
    i = idx[:np.searchsorted(idx, n)]
    keep = [b for b in range(nb) if not (rest_bits >> b) & 1]
    full = np.bincount(sig[i], w[i], minlength=1 << nb) if len(i) else np.zeros(1 << nb)
    if len(keep) == nb:
        return full, nb
    out = np.zeros(1 << len(keep))
    for s, v in enumerate(full):
        t = 0
        for a, b in enumerate(keep):
            if (s >> b) & 1:
                t |= 1 << a
        out[t] += v
    return out, len(keep)


def gold_info(sexp):
    """The gold forms of a task: kinds, and for each form the gold forms it reads. Form g is the g-th non-empty line that does not start with (OUT."""
    lines = [x for x in sexp.strip().split('\n') if x.strip() and not x.startswith('(OUT')]
    reads, head = [], {}
    for i, x in enumerate(lines):
        names = re.findall(r'&r\d+', x)
        h = names[0]
        reads.append(sorted({head[m] for m in names[1:] if m in head and m != h}))
        head[h] = i
    return dict(kinds=[x[1:x.index(' ')] for x in lines], reads=reads)


def last_counts(log):
    """The sum, over the processes in a log, of the last counts line of each: a dict of numbers."""
    total, last = collections.Counter(), None
    for line in log.split('\n'):
        if line.startswith('generation '):
            if last:
                total.update(last)
            last = None
        elif line.startswith('counts '):
            try:
                last = {k: v for k, v in json.loads(line[7:]).items() if isinstance(v, (int, float))}
            except ValueError:
                pass
    if last:
        total.update(last)
    return total


def chance(bank, picks_lines, covers, info):
    """The chance measure of one job. Gives (None, reason) where the job is left out, else (form-runs, ready form-runs)."""
    policy = bank['policy']
    ids, score = policy['ids'], policy['score']
    nodes, forms = bank['nodes'], bank['forms']
    N = len(nodes)
    if ids != list(range(len(ids))) or len(ids) != N:
        return None, 'node ids are not 0..N-1'
    kept, differ = PA.uses_check(bank, picks_lines)
    if differ:
        return None, 'uses check: %d nodes differ' % differ
    sc = np.array([score[i] for i in ids])
    keep_cov = []
    for e in bank['lineage']:
        keep_cov += [x for x in covers if x['proc'] == e['proc'] and e['nodes0'] <= x['node'] < e['nodes1']]
    own = collections.defaultdict(set)
    for x in keep_cov:
        own[x['gold']].add(x['node'])
    first = {q: min(nodes[n].age for n in ns) for q, ns in own.items()}
    nform = np.array([nodes[i].form for i in range(N)])
    fown = collections.defaultdict(set)
    for q, ns in own.items():
        for n in ns:
            fown[nodes[n].form].add(q)
    reach = {}
    for f in sorted(forms):
        r = set(fown.get(f, ()))
        for p in forms[f].parents:
            r |= reach.get(p, set())
        reach[f] = r
    draws = bank['draws']
    runs, ready = [], []
    for h, rd in enumerate(info['reads']):
        if not rd or any(q not in first for q in rd):
            continue
        d_ready = max(first[q] for q in rd)
        d_end = first[h] if h in first else draws
        if d_end > d_ready:
            ready.append((h, rd, d_ready, d_end))
    for h, rd, d_ready, d_end in ready:
        nb = len(rd)
        fsig = {f: sum(1 << b for b, q in enumerate(rd) if q in reach[f]) for f in forms}
        sig = np.array([fsig[f] for f in nform], np.int64)
        runs.append(dict(h=h, kind=info['kinds'][h], reads=rd, nb=nb, d_ready=d_ready, d_end=d_end, sig=sig, idx=np.nonzero(sig)[0], ps=[], held=[], ranks={}))
    u = np.zeros(N)
    for line in kept:
        n, picks, draw = line['n'], line['picks'], line['draw']
        active = [r for r in runs if r['d_ready'] <= draw < r['d_end']]
        if active and n:
            x = sc[:n] - u[:n]
            w = np.exp(x - x.max())
            c = solve_c(w)
            rest = picks[PICKS_TOP] if len(picks) > PICKS_TOP else None
            for r in active:
                nb = r['nb']
                rest_bits = int(r['sig'][rest]) if rest is not None else 0
                if all((rest_bits >> b) & 1 for b in range(nb)):
                    r['ps'].append(1.0)
                else:
                    m, _ = need_masses(r['sig'], r['idx'], w, n, nb, rest_bits)
                    r['ps'].append(p_all(m, c, 0.0))
                got = int(np.bitwise_or.reduce(r['sig'][picks])) if picks else 0
                r['held'].append(got == (1 << nb) - 1)
                for b, q in enumerate(r['reads']):
                    o = np.array(sorted(i for i in own[q] if i < n), np.int64)
                    if len(o):
                        r['ranks'][q] = int(1 + (x > x[o].max()).sum())
        for i in picks:
            u[i] += 1
    out = []
    for r in runs:
        ranks = {q: v for q, v in r['ranks'].items()}
        out.append(dict(h=r['h'], kind=r['kind'], openings=len(r['ps']), mean_p=float(np.mean(r['ps'])) if r['ps'] else None,
                        held=float(np.mean(r['held'])) if r['held'] else None, rule_ranks=[v for q, v in ranks.items() if info['kinds'][q] == 'RULE']))
    return out, len(ready)


def job_record(arm, task, folder, info, ident):
    work = '%s/work/%s' % (folder, task)
    log = open(work + '.log', errors='replace').read() if os.path.exists(work + '.log') else ''
    ended = any(x.startswith('end:') for x in log.split('\n'))
    covers = PA.read_lines(work + '.out.jsonl.cover')
    covered = sorted({x['gold'] for x in covers})
    kinds = info['kinds']
    rec = dict(ended=ended, valid=False, why=[], covered=covered, det=sum(kinds[g] in DET_KINDS for g in covered if g < len(kinds)),
               ident=len(set(covered) & set(ident.get('ident_only', []))), left_out=None, runs=None, ready=0, ns_ms=[], take=None, nodes=None, deaths=None, kills=None)
    if not ended:
        rec['why'].append('open')
        return rec
    sup = open(folder + '/supervisor.log', errors='replace').read() if os.path.exists(folder + '/supervisor.log') else ''
    m = re.findall(r'deaths (\d+) kills (\d+)', sup)
    if m:
        rec['deaths'], rec['kills'] = int(m[-1][0]), int(m[-1][1])
    why = [f for f in INVALID_LOG if f in log]
    markers = set(re.findall(r'^node score: .*$', log, re.M))
    want = PA.expected_name(arm)
    if want is None:
        why += ['node score line in a bundle job'] if markers else []
    else:
        names = {dict(kv.split('=', 1) for kv in x[len('node score: '):].split()).get('name') for x in markers}
        why += [] if names == {want} else ['node score line names %s, want %s' % (sorted(names, key=str), want)]
    if not os.path.exists(work + '.out.jsonl.bank'):
        rec['why'] = why + ['no bank']
        rec['left_out'] = 'no bank'
        return rec
    bank = PA.load_bank(work + '.out.jsonl.bank')
    policy = bank['policy']
    rec['nodes'] = len(bank['nodes'])
    if want is not None:
        rec['ns_ms'] = [round(v, 4) for v in policy.get('ns_ms', [])]
        errors = policy.get('ns_errors', 0)
        if errors > ERROR_SHARE * max(rec['nodes'], 1):
            why.append('ns_errors %d' % errors)
    take = last_counts(log).get('search:seconds take')
    rec['take'] = take
    rec['why'] = why
    rec['valid'] = not why
    runs, ready = chance(bank, PA.read_lines(work + '.out.jsonl.picks'), covers, info)
    if runs is None:
        rec['left_out'] = ready
    else:
        rec['runs'], rec['ready'] = runs, ready
    return rec


def parse_arm(name):
    m = ARM.match(name)
    return (m[1], m[2] == 'f', int(m[3])) if m else (name, False, 0)


def med(v):
    return float(np.median(v)) if len(v) else float('nan')


def band(vals, rng):
    """(point, low, high) of the sum of vals over tasks, with the 90% band over task resamples."""
    v = np.array(vals, float)
    if not len(v):
        return float('nan'), float('nan'), float('nan')
    idx = rng.integers(0, len(v), (RESAMPLES, len(v)))
    s = v[idx].sum(1)
    return float(v.sum()), float(np.percentile(s, BAND[0])), float(np.percentile(s, BAND[1]))


def main():
    out, ident_file = sys.argv[1], sys.argv[2]
    kit_gold = sys.argv[3] if len(sys.argv) > 3 else os.environ.get('GOLD') or os.path.dirname(out.rstrip('/')) + '/points-eval.json'
    cache_path = os.environ.get('READ_CACHE', 'read-cache.json')
    rng = np.random.default_rng(int(os.environ.get('READ_SEED', 1)))
    gold = {x['task']: gold_info(x['gold_sexp']) for x in json.load(open(kit_gold))}
    ident = json.load(open(ident_file))
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    jobs = PA.job_folders(out)
    recs = {}
    for arm, task, folder in jobs:
        work = '%s/work/%s' % (folder, task)
        sig = [os.path.getsize(p) if os.path.exists(p) else -1 for p in (work + '.log', work + '.out.jsonl.bank', work + '.out.jsonl.picks', work + '.out.jsonl.cover')]
        key = '%s/%s' % (arm, task)
        if key in cache and cache[key]['sig'] == sig:
            recs[key] = cache[key]['rec']
            continue
        rec = job_record(arm, task, folder, gold[task], ident.get(task, {}))
        recs[key] = rec
        if rec['ended']:
            cache[key] = dict(sig=sig, rec=rec)
        print('read %s' % key, file=sys.stderr, flush=True)
    with open(cache_path + '.tmp', 'w') as f:
        json.dump(cache, f)
    os.replace(cache_path + '.tmp', cache_path)
    # group: (base arm, fold set) -> seed -> {task: rec}
    groups = collections.defaultdict(lambda: collections.defaultdict(dict))
    for key, rec in recs.items():
        arm, task = key.split('/')
        base, fold, seed = parse_arm(arm)
        groups[base, fold][seed][task] = rec
    order = ['bundle', 'mt', 'depth', 'parity']
    names = sorted(groups, key=lambda g: (order.index(g[0]) if g[0] in order else 9, g[0], g[1]))
    label = lambda g: g[0] + ('f' if g[1] else '')

    print('Forms covered: mean over seeds of the sum over tasks of the jobs that ended')
    print('| arm | tasks | jobs ended | open | valid | all | DET | non-DET | Ident-only |')
    print('| --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    for g in names:
        seeds = groups[g]
        ended = [[r for r in s.values() if r['ended']] for s in seeds.values()]
        mean = lambda f: np.mean([sum(f(r) for r in e) for e in ended]) if ended else float('nan')
        print('| %s | %d | %d | %d | %d | %.1f | %.1f | %.1f | %.1f |' % (label(g), len({t for s in seeds.values() for t in s}), sum(map(len, ended)),
              sum(not r['ended'] for s in seeds.values() for r in s.values()), sum(r['valid'] for s in seeds.values() for r in s.values()),
              mean(lambda r: len(r['covered'])), mean(lambda r: r['det']), mean(lambda r: len(r['covered']) - r['det']), mean(lambda r: r['ident'])))

    print('\nCost: per arm')
    print('| arm | deaths | kills | ns_ms mean | ns_ms q99 | search:seconds take per kept node |')
    print('| --- | --- | --- | --- | --- | --- |')
    for g in names:
        rs = [r for s in groups[g].values() for r in s.values() if r['ended']]
        ms = [v for r in rs for v in r['ns_ms']]
        take = [(r['take'], r['nodes']) for r in rs if r['take'] is not None and r['nodes']]
        print('| %s | %d | %d | %s | %s | %s |' % (label(g), sum(r['deaths'] or 0 for r in rs), sum(r['kills'] or 0 for r in rs),
              '%.2f' % np.mean(ms) if ms else '-', '%.2f' % np.quantile(ms, .99) if ms else '-',
              '%.4f' % (sum(t for t, _ in take) / sum(n for _, n in take)) if take else '-'))

    print('\nChance per opening at the top ranks: medians over the ready form-runs that have an opening')
    print('| arm | C1 | C1-held | C3 | R-RULE | ready form-runs | with opening | jobs left out | jobs read |')
    print('| --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    c1 = {}
    for g in names:
        rs = [r for s in groups[g].values() for r in s.values() if r['ended'] and r['valid']]
        left = [r for r in rs if r['runs'] is None]
        runs = [x for r in rs if r['runs'] is not None for x in r['runs'] if x['openings']]
        ready = sum(r['ready'] for r in rs if r['runs'] is not None)
        c1[g] = med([x['mean_p'] for x in runs])
        print('| %s | %.4f | %.3f | %.3f | %s | %d | %d | %d | %d |' % (label(g), c1[g], med([x['held'] for x in runs]), np.mean([x['mean_p'] >= CHANCE_BAR for x in runs]) if runs else float('nan'),
              '%.1f' % med([v for x in runs for v in x['rule_ranks']]) if any(x['rule_ranks'] for x in runs) else '-', ready, len(runs), len(left), len(rs) - len(left)))
    for g in names:
        left = [(r['left_out']) for s in groups[g].values() for r in s.values() if r['left_out']]
        if left:
            print('left out %s: %s' % (label(g), '; '.join(sorted(set(left)))))
    bad = [(label(g), t, r['why']) for g in names for s in groups[g].values() for t, r in s.items() if r['ended'] and not r['valid']]
    for b in bad:
        print('not valid: %s %s: %s' % b)

    print('\nPaired differences against the bundle: tasks whose 6 jobs are all valid')
    verdict(groups, c1, rng)


def verdict(groups, c1, rng):
    arms = ('bundle', 'mt', 'depth')

    def per_task(fold, f):
        """{arm: {task: mean over seeds of f}} over the tasks whose jobs of all 3 arms and both seeds are valid."""
        need = [groups.get((a, fold)) for a in arms]
        if not all(need):
            return None, []
        tasks = None
        for g in need:
            for seed in (0, 1):
                ok = {t for t, r in g.get(seed, {}).items() if r['valid']}
                tasks = ok if tasks is None else tasks & ok
        tasks = sorted(tasks or ())
        return {a: {t: np.mean([f(groups[a, fold][s][t]) for s in (0, 1)]) for t in tasks} for a in arms}, tasks
    measures = dict(all=lambda r: len(r['covered']), det=lambda r: r['det'], ident=lambda r: r['ident'])
    got = {}
    for fold in (False, True):
        for name, f in measures.items():
            d, tasks = per_task(fold, f)
            got[fold, name] = (d, tasks)
    d37, t37 = got[False, 'all']
    d13, t13 = got[True, 'all']
    if not t37:
        print('no task of the 37 has all 6 jobs valid: no verdict')
        return
    print('37 tasks counted: %d; 13 tasks counted: %d' % (len(t37), len(t13)))
    res = {}
    for arm in ('mt', 'depth'):
        row = {}
        for name in measures:
            d, tasks = got[False, name]
            diff = [d[arm][t] - d['bundle'][t] for t in tasks]
            row[name] = band(diff, rng) + (diff,)
        d13v = sum(d13[arm][t] - d13['bundle'][t] for t in t13) if t13 else float('nan')
        res[arm] = (row, d13v)
        print('%s: D %.1f [%.1f, %.1f]  DET D %.1f [%.1f, %.1f]  Ident-only D %.1f [%.1f, %.1f]  D13 %.1f over %d tasks' % (
            arm, *row['all'][:3], *row['det'][:3], *row['ident'][:3], d13v, len(t13)))
    meets = {}
    for arm, (row, d13v) in res.items():
        meets[arm] = row['all'][1] > 0 and (math.isnan(d13v) or d13v >= D_FLOOR_13) and row['det'][0] >= D_FLOOR_DET
    diff_md = [a - b for a, b in zip(res['mt'][0]['all'][3], res['depth'][0]['all'][3])]
    md = band(diff_md, rng)
    print('M-T D less depth D: %.1f [%.1f, %.1f]' % md)
    print('verdict:')
    if meets['mt'] and meets['depth'] and md[1] <= 0 <= md[2]:
        print('  rule 2: the bundle takes depth in place of M-T (depth needs no table facts and no scipy; M-T gave no live gain over depth)')
    elif meets['mt']:
        print('  rule 1: the bundle takes M-T')
    elif meets['depth']:
        print('  rule 1: the bundle takes depth')
    for arm, (row, _) in res.items():
        if row['all'][2] < 0:
            print('  rule 3: %s is worse (band high end %.1f below 0) and is dropped' % (arm, row['all'][2]))
        elif not meets[arm]:
            if row['ident'][1] > 0:
                print('  rule 4: %s meets no rule above and its Ident-only D band low end is above 0: second batch to the coordinator, no change to the bundle' % arm)
            else:
                ratio = c1.get((arm, False), float('nan')) / c1.get(('bundle', False), float('nan')) if c1.get(('bundle', False)) else float('nan')
                note = 'the block is past the scope pick, in the search kind or clauses' if ratio >= RATIO else 'the fixed-pool read did not carry to live pools'
                print('  rule 5: the bundle stays as it is for %s; live C1 is %.2f times the bundle\'s: %s (note to Features-worker)' % (arm, ratio, note))


if __name__ == '__main__':
    main()
