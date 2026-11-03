"""Recount forms covered of the two r1 runs with each job's cover lines expanded by dups.json. No rerun.

  <plain python> -I recount.py

Old: the job's cover lines give a set C of gold indices (what search_node_score_read.job_record reads). With one index kept per table key, a cover line for index i
means a key whose first index is i was covered. New: C plus, for each i in C, the other indices of the dup groups (keys) whose first index is i.
A form with several tables owns several keys, so a line for i can come from any key that i owns. Two expansions bracket this:
  upper: every dup group that i owns is covered.
  lower: only what every key that i owns gives, and nothing where i also owns a key with no duplicate (that key may be the one that was covered).
Counts: all, DET (DET and RIGID_DET gold forms) and Ident-only (the kit's gold-ident-only-refit.json). The verdict rule of both runs:
  per seed, D = arm - bundle >= -noise band (band = |bundle seed 0 - bundle seed 1000|, summed over the 37 tasks) and Ident-only D > 0.
Writes recount.json (all numbers) and prints the tables.
"""
import collections
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/joint/search-joint-r1-kit-0729e4943'
RUNS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/'
REFIT = RUNS + 'search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943'
JOINT = RUNS + 'search-joint-r1-heldout37-2seeds-600s-0729e4943'
DET_KINDS = ('DET', 'RIGID_DET')
SEEDS = (('s0', '0'), ('s1', '1000'))


def read_lines(path):
    got = []
    if os.path.exists(path):
        for line in open(path, errors='replace'):
            try:
                got.append(json.loads(line))
            except ValueError:
                pass
    return got


def main():
    tasks = json.load(open(KIT + '/refit-tasks.json'))['heldout37']
    gold = {x['task']: x['gold_sexp'] for x in json.load(open(KIT + '/points-eval.json'))}
    kinds = {}
    for t in tasks:
        lines = [x for x in gold[t].strip().split('\n') if x.strip() and not x.startswith('(OUT')]
        kinds[t] = [x[1:x.index(' ')] for x in lines]
    ident = {t: set(v['ident_only']) for t, v in json.load(open(KIT + '/gold-ident-only-refit.json')).items()}
    keylists = {}
    for line in open(HERE + '/dups.jsonl'):
        r = json.loads(line)
        keylists[r['task']] = r['all_keys']
    assert all(t in keylists for t in tasks)

    def expand(t, C):
        """(lower, upper) sets: C with the indices of the dup groups that the indices of C own."""
        low, up = set(C), set(C)
        for i in C:
            owned = [k for k in keylists[t] if k[0] == i]
            dup = [k for k in owned if len(k) >= 2]
            if not dup:
                continue
            for k in dup:
                up |= set(k)
            if len(dup) == len(owned):
                low |= set.intersection(*(set(k) for k in dup))
        return low, up

    def measure(t, S):
        return dict(all=len(S), det=sum(kinds[t][g] in DET_KINDS for g in S if g < len(kinds[t])), ident=len(S & ident.get(t, set())))

    def jobs(run, arm, seed):
        out = {}
        for t in tasks:
            w = '%s/out/%s_%s/%s/work/%s' % (run, arm, seed, t, t)
            log = open(w + '.log', errors='replace').read() if os.path.exists(w + '.log') else ''
            ended = any(x.startswith('end:') for x in log.split('\n'))
            C = {x['gold'] for x in read_lines(w + '.out.jsonl.cover') if 'gold' in x}
            out[t] = (ended, C)
        return out

    result = {}
    detail = {}
    for name, run, arm in (('refit', REFIT, 'refit'), ('joint', JOINT, 'joint')):
        for a in ('bundle', arm):
            for seed, sname in SEEDS:
                J = jobs(run, a, seed)
                tot = {k: collections.Counter() for k in ('old', 'lower', 'upper')}
                for t, (ended, C) in J.items():
                    assert ended, (run, a, seed, t)
                    low, up = expand(t, C)
                    for k, S in (('old', C), ('lower', low), ('upper', up)):
                        tot[k].update(measure(t, S))
                    if up != C:
                        detail.setdefault(t, {})['%s/%s_%s' % (name, a, sname)] = dict(old=len(C), lower=sorted(low - C), upper=sorted(up - C))
                result['%s/%s/%s' % (name, a, seed)] ={k: dict(v) for k, v in tot.items()}

    # verdict
    verdicts = {}
    for name, arm in (('refit', 'refit'), ('joint', 'joint')):
        for k in ('old', 'lower', 'upper'):
            g = lambda a, s, m: result['%s/%s/%s' % (name, a, s)][k][m]  # noqa: E731
            band = abs(g('bundle', 's0', 'all') - g('bundle', 's1', 'all'))
            v = dict(band=band, seeds={})
            ok = True
            for s in ('s0', 's1'):
                D = g(arm, s, 'all') - g('bundle', s, 'all')
                DI = g(arm, s, 'ident') - g('bundle', s, 'ident')
                DD = g(arm, s, 'det') - g('bundle', s, 'det')
                f_ok, i_up = D >= -band, DI > 0
                ok &= f_ok and i_up
                v['seeds'][s] = dict(bundle=g('bundle', s, 'all'), arm=g(arm, s, 'all'), D=D, forms_ok=f_ok, ident_bundle=g('bundle', s, 'ident'), ident_arm=g(arm, s, 'ident'), D_ident=DI,
                                     ident_up=i_up, D_det=DD)
            v['mean_D'] = sum(v['seeds'][s]['D'] for s in v['seeds']) / 2
            v['mean_D_ident'] = sum(v['seeds'][s]['D_ident'] for s in v['seeds']) / 2
            v['passed'] = ok
            verdicts['%s/%s' % (name, k)] = v

    # frontier: the stuck roots of ready.tsv
    rows = []
    header = None
    for line in open(REFIT + '/frontier/ready.tsv'):
        f = line.rstrip('\n').split('\t')
        if header is None:
            header = f
            continue
        rows.append(dict(zip(header, f)))
    covers = {s: jobs(REFIT, 'bundle', s) for s, _ in SEEDS}
    frontier = {}
    stuck_detail = []
    for seed, sname in SEEDS:
        sd = '0' if seed == 's0' else '1'
        R = [r for r in rows if r['seed'] == sd]
        out = dict(ready=len(R), roots=0, roots_low=0, roots_up=0, with_reads=0, with_reads_low=0, with_reads_up=0, roots_covered_in_old=0)
        for r in R:
            t, g = r['task'], int(r['g'])
            C = covers[seed][t][1]
            low, up = expand(t, C)
            root = r['nreads'] == '0'
            key = 'roots' if root else 'with_reads'
            out[key] += 1
            out[key + '_low'] += g in low
            out[key + '_up'] += g in up
            if g in C:
                out['roots_covered_in_old'] += 1  # a ready row that the cover lines already hold
            if root and g in up:
                stuck_detail.append(dict(seed=sd, task=t, g=g, kind=r['kind'], bits=r['bits'], certain=g in low,
                                         via=[k for k in keylists[t] if g in k and len(k) >= 2 and k[0] in C]))
        frontier['seed' + sd] = out

    json.dump(dict(totals=result, verdicts=verdicts, frontier=frontier, stuck_roots_covered=stuck_detail, per_task=detail), open(HERE + '/recount.json', 'w'), indent=1)
    for k, v in result.items():
        print(k, {kk: (vv['all'], vv['det'], vv['ident']) for kk, vv in v.items()})
    for k, v in verdicts.items():
        print(k, json.dumps(v))
    print(json.dumps(frontier))
    for s in stuck_detail:
        print(s)


main()
