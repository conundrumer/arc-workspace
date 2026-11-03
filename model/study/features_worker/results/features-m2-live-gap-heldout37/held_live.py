"""Openings of the live M2 run (sampler-pool-m2-600s) where a form of round 1's C list is held with its kind, by the rules of round 1's scope-loss read.

    python -I held_live.py [BUDGET_SECONDS]

One JSON file a job to held/<job>__<task>.json; a job with a file is skipped. Prints `done N todo M`.
Per job: tries by visit kind (all visits, and visits that end within 600 s of the start file), and per C form (kit gold index, mapped by text as c_split.py maps it):
its kind, reads, first cover (s), and each opening before that cover where every read has a kept covering node whose form is in the opening's scope (held),
with the scope's form ids, the visit kind, and the slot tries (scope-loss rule). An opening's scope and kind are those of its matched visit
(the first visit with resume false from the opening's time to the next opening's time).
"""
import bisect, collections, csv, json, os, sys, time
sys.dont_write_bytecode = True
SW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker'
sys.path[:0] = [SW + '/refit-tools']
import search_node_score_parity as PA
import search_node_score_read as R

RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-pool-m2-600s/out'
KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-m2-48211b300'
R1GOLD = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/refit/out-r1/points-eval.json'
SLTSV = SW + '/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/scope-loss/forms.tsv'
HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = ['m2c_s0', 'm2s_s0', 'm2c_s1', 'm2s_s1']


def forms(s):
    return [x for x in s.strip().split('\n') if x.strip() and not x.startswith('(OUT')]


def c_list():
    kg = {p['task']: forms(p['gold_sexp']) for p in json.load(open(KIT + '/points-eval.json'))}
    rg = {p['task']: forms(p['gold_sexp']) for p in json.load(open(R1GOLD))}
    c = {(r['task'], int(r['g'])) for r in csv.DictReader(open(SLTSV), delimiter='\t') if r['arm'].startswith('bundle') and r['class'] == 'C'}
    out = collections.defaultdict(list)
    for t, g in sorted(c):
        idx = [i for i, x in enumerate(kg[t]) if x == rg[t][g]]
        if idx:
            out[t].append(idx[0])
    return out


def job(arm, task, cforms, info):
    w = '%s/%s/%s/work/%s' % (RUN, arm, task, task)
    start = float(open('%s/%s/%s/start' % (RUN, arm, task)).read().split()[0])
    bank = PA.load_bank(w + '.out.jsonl.bank')
    nodes, bforms = bank['nodes'], bank['forms']
    N = len(nodes)
    lin = {e['proc']: e for e in bank['lineage']}
    last1 = bank['lineage'][-1]['nodes1'] if bank['lineage'] else 0
    plines = PA.read_lines(w + '.out.jsonl.picks')
    kept = {(x['proc'], x['seq']) for x in PA.kept_picks(bank['lineage'], plines)}
    allops = sorted(plines, key=lambda x: x['time'])
    all_times = [o['time'] for o in allops]
    ops = [o for o in allops if o['picks']]
    vs = sorted(PA.read_lines(w + '.out.jsonl.visits'), key=lambda v: v['time'])
    v_times = [v['time'] for v in vs]
    covers = sorted(PA.read_lines(w + '.out.jsonl.cover'), key=lambda c: c['time'])
    first_cov = {}
    kcov = collections.defaultdict(list)
    for c in covers:
        first_cov.setdefault(c['gold'], c['time'])
        e = lin.get(c['proc'])
        if e is not None and e['nodes0'] <= c['node'] < e['nodes1']:
            kcov[c['gold']].append((c['time'], c['node'], nodes[c['node']].form))
    tk_all, tk_600, nv = collections.Counter(), collections.Counter(), collections.Counter()
    for v in vs:
        tk_all[v['kind']] += v['tries']
        nv[v['kind']] += 1
        if v['time'] - start <= 600:
            tk_600[v['kind']] += v['tries']
    rec_ops = []
    for o in ops:
        isk = (o['proc'], o['seq']) in kept
        cp = N if isk else min(N, lin[o['proc']]['nodes1'] if o['proc'] in lin else last1)
        npool = min(o['n'], cp)
        k = bisect.bisect_right(all_times, o['time'])
        nxt = all_times[k] if k < len(all_times) else float('inf')
        a = bisect.bisect_left(v_times, o['time'])
        mv = None
        while a < len(vs) and v_times[a] < nxt:
            if not vs[a]['resume']:
                mv = vs[a]
                break
            a += 1
        rec_ops.append(dict(o=o, npool=npool, S=frozenset(mv['fids']) if mv else None, K=mv['kind'] if mv else None))
    keyo = collections.defaultdict(list)
    for oi, r in enumerate(rec_ops):
        if r['K'] is not None:
            keyo[(tuple(sorted(r['S'])), r['K'])].append(oi)
    stries = collections.Counter()
    for v in vs:
        l = keyo.get((tuple(sorted(v['fids'])), v['kind']))
        if not l:
            continue
        ts = [ops[j]['time'] for j in l]
        b = bisect.bisect_right(ts, v['time']) - 1
        if b >= 0:
            stries[l[b]] += v['tries']
    G = []
    for g in cforms:
        rd = info['reads'][g]
        kind = info['kinds'][g]
        fc = first_cov.get(g)
        row = dict(g=g, kind=kind, reads=rd, cover_s=round(fc - start, 2) if fc else None, ready_n=0, held_n=0, hk=[])
        for oi, r in enumerate(rec_ops):
            t = r['o']['time']
            if fc is not None and t >= fc:
                break
            if r['S'] is None:
                continue
            Fq = [{f for ct, x, f in kcov.get(q, ()) if ct < t and x < r['npool']} for q in rd]
            if not rd or not all(Fq):
                continue
            row['ready_n'] += 1
            if all(F & r['S'] for F in Fq):
                row['held_n'] += 1
                if r['K'] == kind or (kind == 'RIGID_DET' and r['K'] == 'DET'):
                    row['hk'].append(dict(i=oi, time_s=round(t - start, 2), kind=r['K'], fids=sorted(r['S']), tries=stries[oi], n=r['o']['n']))
        row['hk_n'] = len(row['hk'])
        row['hk_tries'] = sum(x['tries'] for x in row['hk'])
        G.append(row)
    return dict(arm=arm, task=task, N=N, n_open=len(ops), n_vis=len(vs), tries_all=dict(tk_all), tries_600=dict(tk_600), visits=dict(nv), forms=G)


def main():
    t0 = time.time()
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 15
    os.makedirs(HERE + '/held', exist_ok=True)
    cl = c_list()
    tasks = json.load(open(KIT + '/refit-tasks.json'))['heldout37']
    gold = {x['task']: R.gold_info(x['gold_sexp']) for x in json.load(open(KIT + '/points-eval.json'))}
    done = todo = 0
    for arm in JOBS:
        for task in tasks:
            out = '%s/held/%s__%s.json' % (HERE, arm, task)
            if os.path.exists(out):
                done += 1
                continue
            if time.time() - t0 > budget:
                todo += 1
                continue
            rec = job(arm, task, cl.get(task, []), gold[task])
            json.dump(rec, open(out + '.tmp', 'w'))
            os.replace(out + '.tmp', out)
            done += 1
            print(arm, task, 'C forms', len(rec['forms']), 'hk', [f['hk_n'] for f in rec['forms']], '%.1fs' % (time.time() - t0), flush=True)
    print('done', done, 'todo', todo, 'seconds %.1f' % (time.time() - t0))


main()
