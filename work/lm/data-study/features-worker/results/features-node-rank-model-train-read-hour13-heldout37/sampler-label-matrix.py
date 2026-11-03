"""Every label set against every unit and key, on the 26 hour runs at the two cuts, and where the exact picks land by rank. Streams and resumes per run.

  python -I sampler-label-matrix.py SECONDS

Reads search-worker's table rows (poolg/rows/table-hour-*), with their labels, for the same tables.
Writes label-auc-rows.tsv, positive-rows.tsv, pick-rank-rows.tsv, chance-curve-rows.tsv.
"""
import collections, json, math, os, sys, time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
POOLG = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, POOLG)
import numpy as np
import pandas as pd
import poolrun, common2 as C2, aucs as A

LIMIT = float(sys.argv[1]) if len(sys.argv) > 1 else 25
T0 = time.time()
RBINS = [1, 10, 100, 1000, 10 ** 9]
RNAMES = ['1-10', '11-100', '101-1000', '1001+']
CURVE = [1, 3, 10, 30, 100, 300, 1000, 3000]
SHARES = [.01, .1, .18, .29, .5]


def solve_c(w):
    c = 5.0 / w.sum()
    for _ in range(40):
        e = np.exp(-w * c)
        f = (1 - e).sum() - 5.0
        if abs(f) < 1e-7:
            break
        c = max(c - f / (w * e).sum(), c / 8)
    return c


def beat(f, y):
    """For each positive, the share of negatives it beats, ties 1/2."""
    neg = np.sort(f[~y])
    p = f[y]
    lo = np.searchsorted(neg, p, 'left')
    hi = np.searchsorted(neg, p, 'right')
    return (lo + .5 * (hi - lo)) / max(len(neg), 1)


def one(arm, task):
    R = poolrun.Run('hour', arm, task)
    lab = R.lab
    P = np.load(HERE + 'rows/sampler-picks-%s-%s.npz' % (arm, task))
    G = len(lab['lines'])
    rows_auc, rows_pos, rows_curve = [], [], []
    # forms of each table, by gold form
    q_of_t = collections.defaultdict(set)
    for t, s in enumerate(R.pairs):
        for q in R.q_of_pair.get(s, ()):
            q_of_t[t].add(q)
    picks_all = np.concatenate([P['best'], P['rest'][:, None]], axis=1)
    for cut in (600, 3600):
        d, tsec, how = R.cut_draw(cut)
        T = pd.read_csv(POOLG + 'rows/table-hour-%s-%s-%d.tsv.gz' % (arm, task, cut), sep='\t')
        n = int(np.searchsorted(R.age, d, side='right'))
        uses = np.zeros(R.n, np.float64)
        sel = P['d0'] < d
        for row in picks_all[sel]:
            uses[row[row >= 0]] += 1
        if how == 'last write':
            assert (uses == R.uses_end).all(), (arm, task)
        x = R.score[:n] - uses[:n]
        s = R.score[:n]
        tid = R.tid[:n]
        tx = np.full(R.ntab, -np.inf)
        np.maximum.at(tx, tid, x)
        ix = T['table'].values
        T['x'] = tx[ix]
        assert np.isfinite(T['x']).all()
        cov = lambda g: (lab['first'].get(g) is not None and lab['first'][g] <= d)
        # q kind labels, and the forms' states
        def lab_ready(t, rule_q):
            for q in q_of_t.get(t, ()):
                if rule_q and lab['kinds'][q] != 'RULE':
                    continue
                for h in lab['readers'].get(q, ()):
                    if not cov(h) and all(cov(r) for r in lab['reads'][h]):
                        return 1
            return 0
        T['ready_q_rule'] = [lab_ready(int(t), True) for t in ix]
        T['ready_any'] = T['ready_read']
        T['open_not_ready'] = ((T['open_nondet'] == 1) & (T['ready_nondet'] == 0)).astype(int)
        T['closed_read'] = ((T['any_read'] == 1) & (T['open_read'] == 0)).astype(int)
        pmap = {t: i for i, t in enumerate(ix)}
        mx = x.max()
        w = np.exp(x - mx)
        W = w.sum()
        c = solve_c(w)
        # own and reach of each table: forms that hold it, their descendants
        order = np.argsort(-x, kind='stable')
        rk_x = np.empty(n, np.int64)
        rk_x[order] = np.arange(1, n + 1)
        for name in ('open_nondet', 'ready_nondet', 'open_read', 'ready_any', 'ready_q_rule', 'open_not_ready', 'any_read', 'closed_read'):
            y = T[name].values == 1
            if not y.any() or y.all():
                continue
            ts = T['score'].values
            r = {}
            r['table_score'] = beat(ts, y)
            r['table_x'] = beat(T['x'].values, y)
            poss = set(ix[y])
            ny = np.isin(tid, list(poss))
            r['node_score_all_copies'] = beat(s, ny)
            # the stall read: the copy of greatest weight of each positive, among nodes that aren't copies of a positive
            bestn = {}
            for i in np.nonzero(ny)[0]:
                t = int(tid[i])
                if t not in bestn or x[i] > x[bestn[t]]:
                    bestn[t] = i
            bn = np.array(sorted(bestn.values()))
            negx = np.sort(x[~ny])
            lo = np.searchsorted(negx, x[bn], 'left'); hi = np.searchsorted(negx, x[bn], 'right')
            r['node_x_best_copy'] = (lo + .5 * (hi - lo)) / len(negx)
            negs = np.sort(s[~ny])
            sb = s[bn]
            lo = np.searchsorted(negs, sb, 'left'); hi = np.searchsorted(negs, sb, 'right')
            r['node_score_best_copy'] = (lo + .5 * (hi - lo)) / len(negs)
            code = A.strata(T, 'S1')
            a1 = A.auc_run(ts, code, y)
            rows_auc.append([arm, task, cut, name, 'table_score_S1', a1[0], a1[1], '', '', ''])
            for k, v in r.items():
                rows_auc.append([arm, task, cut, name, k, float(np.mean(v)), len(v), float(np.median(v)), n if k.startswith('node') else len(T), ''])
        # per positive table of the widest sets, with chance at the cut
        reachF = None
        anypos = (T['any_read'].values == 1)
        fp = np.zeros(max(R.forms) + 1, np.int32)
        for t in ix[anypos]:
            cp = np.nonzero(tid == t)[0]
            own_w = w[cp].sum()
            fs = {int(R.nform[i]) for i in cp}
            tr = T.iloc[pmap[t]]
            # descendants: forms alive whose ancestors hold it
            mark = {}
            def up(f):
                if f in mark:
                    return mark[f]
                r = f in fs or any(up(p) for p in R.parents[f])
                mark[f] = r
                return r
            sys.setrecursionlimit(100000)
            rw = 0.0
            nr = 0
            for f in sorted(set(R.nform[:n].tolist())):
                if up(f):
                    i2 = np.array([i for i in R.fnodes[f] if i < n], np.int64)
                    rw += w[i2].sum()
                    nr += len(i2)
            rows_pos.append([arm, task, cut, int(t), int(tr['open_nondet']), int(tr['ready_nondet']), int(tr['open_read']), int(tr['ready_read']), int(tr['ready_q_rule']), int(tr['any_read']), int(tr['copies']), tr['kind'], int(tr['depth']), round(float(tr['score']), 3), round(float(tr['x']), 3),
                             int((T['score'].values > tr['score']).sum() + 1), len(T), int((s > tr['score']).sum() + 1), int((x > tr['x']).sum() + 1), n, round(float(mx - math.log(c) - tr['x']), 3),
                             '%.3g' % (1 - math.exp(-c * own_w)), '%.3g' % (1 - math.exp(-c * rw)), nr, int(tr['uses_end']), int(tr['exposure']), int(tr['age'])])
        # the chance curve at the cut
        ww = np.sort(w)[::-1]
        row = [arm, task, cut, n, round(float(mx), 3), round(float(mx - math.log(c)), 3), round(float(np.median(x)), 3), round(float(np.quantile(x, .5)), 3)]
        for k in CURVE:
            row.append('%.4g' % (1 - math.exp(-c * ww[min(k, n) - 1])))
        for sh in SHARES:
            row.append('%.4g' % (1 - math.exp(-c * ww[int(sh * n)])))
        row.append('%.4g' % ww[:int(.18 * n)].sum().__truediv__(W))
        row.append('%.4g' % ww[:int(.29 * n)].sum().__truediv__(W))
        rows_curve.append(row)
    # where the scored picks land
    uses = np.zeros(R.n, np.float64)
    cnt = collections.Counter()
    for j in range(len(P['v'])):
        n = int(P['n'][j])
        x = R.score[:n] - uses[:n]
        b = P['best'][j]
        b = b[b >= 0]
        if P['v'][j] < 0:  # a refused scope
            pk = np.concatenate([b, P['rest'][j:j + 1]])
            uses[pk[pk >= 0]] += 1
            continue
        sec = float(R.visits[int(P['v'][j])]['t'])
        tb = 0 if sec <= 600 else 1 if sec <= 1800 else 2
        for i in b:
            rk = int((x > x[i]).sum() + 1)
            q = rk / n
            for name, hi in zip(RNAMES, RBINS[1:]):
                if rk <= hi:
                    cnt[tb, name] += 1
                    break
            cnt[tb, 'all'] += 1
            cnt[tb, 'top_share_.71'] += q <= .71
            cnt[tb, 'top_share_.01'] += q <= .01
        rs = P['rest'][j]
        if rs >= 0:
            cnt[tb, 'rest'] += 1
            cnt[tb, 'rest_rank_share_sum'] += float(((x > x[rs]).sum() + 1) / n)
            cnt[tb, 'rest_id_sum'] += int(rs)
        pk = np.concatenate([b, [rs]]) if rs >= 0 else b
        uses[pk] += 1
    rows_rank = [[arm, task, tb, k, v] for (tb, k), v in sorted(cnt.items())]
    return rows_auc, rows_pos, rows_curve, rows_rank


def main():
    names = dict(auc='sampler-label-auc-rows.tsv', pos='sampler-positive-rows.tsv', curve='sampler-chance-curve-rows.tsv', rank='sampler-pick-rank-rows.tsv')
    heads = dict(auc='arm task cut label measure auc positives median_beat group_size note'.split(),
                 pos='arm task cut table open_nondet ready_nondet open_read ready_read ready_q_rule any_read copies kind depth score x rank_table_score tables rank_node_score rank_node_x n bar_gap p_own p_reach nreach uses_end exposure age'.split(),
                 curve=('arm task cut n xmax bar median_x median_x2 ' + ' '.join('p_rank%d' % k for k in CURVE) + ' ' + ' '.join('p_share%g' % s for s in SHARES) + ' mass_top18 mass_top29').split(),
                 rank='arm task time_bin key count'.split())
    ck = HERE + 'sampler-label-done.txt'
    done = set(open(ck).read().split('\n')) if os.path.exists(ck) else set()
    if not done:
        for k, f in names.items():
            open(HERE + f, 'w').write('\t'.join(heads[k]) + '\n')
    only = os.environ.get('ONLY')
    for arm in ('hour_s0', 'hour_s1'):
        for task in C2.C.TASKS:
            key = arm + ' ' + task
            if key in done or (only and only != key):
                continue
            if time.time() - T0 > LIMIT:
                print('stopped at the limit', flush=True)
                return
            t1 = time.time()
            out = one(arm, task)
            for k, rows in zip(('auc', 'pos', 'curve', 'rank'), out):
                with open(HERE + names[k], 'a') as fh:
                    fh.write(''.join('\t'.join(map(str, r)) + '\n' for r in rows))
            with open(ck, 'a') as fh:
                fh.write(key + '\n')
            print(key, round(time.time() - t1, 2), flush=True)
    print('done', round(time.time() - T0, 1), flush=True)


main()
