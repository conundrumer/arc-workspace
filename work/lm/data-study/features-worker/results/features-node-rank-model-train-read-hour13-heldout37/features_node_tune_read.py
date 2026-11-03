"""Item 9 read on N600: the chance per opening and the rank of right intermediates, per task fold, for the arms that have fold scores.

  features_node_tune_read.py ARM[,ARM...] [--t .5,.75,1,1.5,2] [--out tune-n600.json]

For each N600 task, at the last write of its run: the ready forms of the right program (every read has a node on its table, the form has none),
the chance per opening of holding all reads under a scope draw with uses 0 (static, as sampler-ready-forms.py gives it, ancestors counted through
reachN), and the rank of each RULE and INIT read by score. The hand score (the run's recorded score) is the base. Score of a model is s = t * model(node).
Cell of tables with an Ident column (t_Ident feature above 0): rank and chance per opening of the positives in it, beside the whole and the rest. On N600 a positive is a node on a gold table (session key); on S120 rows a seeded table. S120 is read for the hand score always, and for a model only if it was fit without S120 (fit-out/ARM-fK.scores-s120.npz).
Tune measure: mean over tasks that have a ready form of log10 of the task's median chance over its ready forms. Fold scores come from
fit-out/ARM-fK.scores.npz, K = 0..4. A model is read on the 10 tasks of its fold only.
"""
import glob, json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, HERE)
import numpy as np
import flat_common as C
import features_node_data as DT

W = C.W
BANK = W + 'sampler-pool-dag-nodes-train50-600s/out/nodes_s0/%s/work/%s.out.jsonl.bank'


def solve_c(w):
    c = 5.0 / w.sum()
    for _ in range(40):
        e = np.exp(-w * c)
        f = (1 - e).sum() - 5.0
        if abs(f) < 1e-7:
            break
        c = max(c - f / (w * e).sum(), c / 8)
    return c


def p_all(masses, c):
    m = len(masses)
    tot = 0.0
    for T in range(m):
        if T == 0:
            tot += 1.0
            continue
        hit = sum(masses[s] for s in range(1, m) if s & T)
        tot += (-1) ** bin(T).count('1') * math.exp(-c * hit)
    return max(tot, 0.0)


class TaskPool:
    def __init__(self, t):
        self.t = t
        ps = sorted(glob.glob(HERE + 'n600-rows/%s.part*.npz' % t))
        zs = [np.load(p) for p in ps]
        mc = [str(c) for c in zs[0]['meta_cols']]
        meta = np.vstack([z['meta'] for z in zs])
        col = {c: meta[:, i] for i, c in enumerate(mc)}
        self.node = col['node'].astype(np.int64)
        self.form = col['form'].astype(np.int64)
        self.hand = col['score']
        self.rowcheck = col['rowcheck'].astype(int)
        self.gold = sum((json.loads(str(z['gold'][0])) for z in zs), [])
        g = json.load(open(HERE + 'n600-rows/%s.gold.json' % t))
        self.reads, self.kinds = g['reads'], g['kinds']
        st = C.bank(BANK % (t, t))
        forms = st['forms']
        nf = max(forms) + 1
        self.par = {f: sorted(set(forms[f].parents)) for f in forms}
        n = len(self.node)
        G = len(self.kinds)
        own = np.zeros((n, G), bool)
        for i, gs in enumerate(self.gold):
            for q in gs:
                own[i, q] = True
        fown = np.zeros((nf, G), bool)
        for i in range(n):
            if own[i].any():
                fown[self.form[i]] |= own[i]
        reach = fown.copy()
        for f in sorted(forms):
            for p in self.par[f]:
                reach[f] |= reach[p]
        self.own, self.reachN = own, reach[self.form]
        self.covered = own.any(0)
        self.ready = [h for h in range(G) if self.reads[h] and not self.covered[h] and all(self.covered[q] for q in self.reads[h])]
        self.pos = own.any(1)
        names = [str(x) for x in zs[0]['names']]
        ci = names.index('tb_t_Ident')
        self.ident = np.concatenate([np.nan_to_num(z['X'][:, ci]) for z in zs]) > 0

    def read(self, s):
        """(list of chances over ready forms, ranks of RULE reads, ranks of INIT reads, chance of right nodes by rank bin) for scores s."""
        w = np.exp(s - s.max())
        c = solve_c(w)
        ps = []
        for h in self.ready:
            rd = self.reads[h][:10]
            sig = (self.reachN[:, rd] * (1 << np.arange(len(rd)))).sum(1).astype(np.int64)
            masses = np.bincount(sig, w, minlength=1 << len(rd))
            ps.append(p_all(masses, c))
        order_gt = lambda v: float((s > v).sum() + .5 * ((s == v).sum() - 1)) + 1
        rr, ri = [], []
        for h in self.ready:
            for q in self.reads[h]:
                if self.own[:, q].any():
                    r = order_gt(s[self.own[:, q]].max())
                    (rr if self.kinds[q] == 'RULE' else ri if self.kinds[q] == 'INIT' else []).append(r)
        return ps, rr, ri


def pos_stats(s, is_pos, ident):
    """Per positive node: rank by s in its pool (ties at their mean) and the chance of a scored pick, 1 - exp(-c w). Gives (rank, chance, ident flag)."""
    w = np.exp(s - s.max())
    c = solve_c(w)
    ss = np.sort(s)
    p = np.nonzero(is_pos)[0]
    lo, hi = np.searchsorted(ss, s[p], 'left'), np.searchsorted(ss, s[p], 'right')
    rank = (len(s) - hi) + .5 * (hi - lo - 1) + 1
    return rank, 1 - np.exp(-c * w[p]), ident[p]


def summ(rank, chance):
    if len(rank) == 0:
        return None
    return dict(n=int(len(rank)), median_rank=float(np.median(rank)), top10=float((rank <= 10).mean()), top100=float((rank <= 100).mean()), top1000=float((rank <= 1000).mean()),
                median_chance=float(np.median(chance)), mean_chance=float(np.mean(chance)))


def show(tag, d):
    return '%s n %d median rank %g top10 %.3f top100 %.3f top1000 %.3f chance per opening median %.2e mean %.2e' % (
        tag, d['n'], d['median_rank'], d['top10'], d['top100'], d['top1000'], d['median_chance'], d['mean_chance']) if d else tag + ' none'


class S120Pool:
    """An S120 task: seeded tables are the positives. Hand score from the hand model's fold (computed from the H rows)."""
    bundle = None

    def __init__(self, t):
        import pickle, hashlib
        import features_node_io as IO
        z = np.load(HERE + 's120-rows/%s.npz' % t)
        c = {str(k): z['meta'][:, i] for i, k in enumerate(z['meta_cols'])}
        self.node = c['token'].astype(np.int64)
        self.y = c['y']
        names = [str(x) for x in z['names']]
        self.ident = np.nan_to_num(z['X'][:, names.index('tb_t_Ident')]) > 0
        if S120Pool.bundle is None:
            S120Pool.bundle = pickle.load(open('/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-dag-nodes-train50-final-8be414670/policy/policy_model.pkl', 'rb'))
        b = S120Pool.bundle
        key = hashlib.sha1(json.dumps(IO.load_task(t)['train'], sort_keys=True).encode()).hexdigest()
        m = next((m for trained, m in b['folds'] if key not in trained), b['folds'][0][1])
        self.hand = m.decision_function(z['H'])
        self.t = t


def s120_fold(t, folds):
    """The fold whose model scores an S120 task: features_node_data.s120_fold_map (the N600 fold of an N600 task, else sorted task id position % 5)."""
    if s120_fold.map is None:
        s120_fold.map = DT.s120_fold_map(len(folds))
    return s120_fold.map[t]


s120_fold.map = None


def main():
    arms = sys.argv[1].split(',')
    ts = [float(x) for x in (sys.argv[sys.argv.index('--t') + 1] if '--t' in sys.argv else '.5,.75,1,1.5,2').split(',')]
    outp = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'tune-n600.json'
    pools, spools = {}, {}
    res = {}
    folds = DT.folds(5)
    s120_list = None
    for arm in ['hand'] + arms:
        per_t = {}
        for t in (ts if arm != 'hand' else [float(x) for x in os.environ.get('HAND_T', '1').split(',')]):
            vals, rr, ri, nt, nready = [], [], [], 0, 0
            cell = {'n600': ([], [], []), 's120': ([], [], [])}
            for k in range(5):
                if arm == 'hand':
                    tasks = folds[k]
                else:
                    p = HERE + 'fit-out/%s-f%d.scores.npz' % (arm, k)
                    if not os.path.exists(p):
                        continue
                    z = np.load(p)
                    tasks = list(z['tasks'])
                    off = np.r_[0, np.cumsum(z['pool_sizes'])]
                for i, task in enumerate(tasks):
                    if not glob.glob(HERE + 'n600-rows/%s.part*.npz' % task):
                        continue
                    if task not in pools:
                        pools[task] = TaskPool(task)
                    P = pools[task]
                    if arm == 'hand':
                        s = t * P.hand
                    else:
                        zs = z['score'][off[i]:off[i + 1]]
                        zn = z['node'][off[i]:off[i + 1]]
                        mp = dict(zip(zn.tolist(), zs.tolist()))
                        s = t * np.array([mp[n] for n in P.node.tolist()])
                    nt += 1
                    r_, c_, id_ = pos_stats(s, P.pos, P.ident)
                    for a, b in zip(cell['n600'], (r_, c_, id_)):
                        a.append(b)
                    if not P.ready:
                        continue
                    ps, r1, r2 = P.read(s)
                    nready += len(ps)
                    vals.append(math.log10(max(float(np.median(ps)), 1e-12)))
                    rr += r1
                    ri += r2
            # S120 rows: seeded tables as positives. Held out only for models fit without S120 (scores in fit-out/ARM-fK.scores-s120.npz); the hand score always.
            if s120_list is None:
                import features_node_io as IO
                s120_list = IO.s120_tasks(200)
            s_have = arm == 'hand'
            zk = {}
            if arm != 'hand':
                for k in range(5):
                    p = HERE + 'fit-out/%s-f%d.scores-s120.npz' % (arm, k)
                    if os.path.exists(p):
                        zz = np.load(p)
                        off2 = np.r_[0, np.cumsum(zz['pool_sizes'])]
                        for i, task in enumerate(zz['tasks']):
                            zk[(k, str(task))] = (zz['score'][off2[i]:off2[i + 1]], zz['node'][off2[i]:off2[i + 1]])
            for task in s120_list:
                if arm != 'hand':
                    key = (s120_fold(task, folds), task)
                    if key not in zk:
                        continue
                try:
                    if task not in spools:
                        spools[task] = S120Pool(task)
                except Exception:
                    continue  # rows missing or still being written
                Q = spools[task]
                if arm == 'hand':
                    s = t * Q.hand
                else:
                    zs, zn = zk[key]
                    mp = dict(zip(zn.tolist(), zs.tolist()))
                    s = t * np.array([mp[n] for n in Q.node.tolist()])
                r_, c_, id_ = pos_stats(s, Q.y == 1, Q.ident)
                for a, b in zip(cell['s120'], (r_, c_, id_)):
                    a.append(b)
            if nt:
                v = dict(tasks=nt, tasks_with_ready=len(vals), ready_forms=nready, mean_log10_median_chance=float(np.mean(vals)) if vals else None,
                         median_chance_over_tasks=float(10 ** np.median(vals)) if vals else None,
                         median_rank_rule=float(np.median(rr)) if rr else None, median_rank_init=float(np.median(ri)) if ri else None, n_rule_reads=len(rr), n_init_reads=len(ri))
                v['cell'] = {}
                for src, (R_, C_, I_) in cell.items():
                    if not R_:
                        continue
                    R_, C_, I_ = np.concatenate(R_), np.concatenate(C_), np.concatenate(I_)
                    v['cell'][src] = dict(whole=summ(R_, C_), ident=summ(R_[I_], C_[I_]), no_ident=summ(R_[~I_], C_[~I_]))
                per_t[str(t)] = v
        res[arm] = per_t
        for t, v in per_t.items():
            print('%-18s t=%-5s tasks %d with ready %d ready forms %d | mean log10 median chance %s | median chance %s | median rank RULE %s (%d) INIT %s (%d)' % (
                arm, t, v['tasks'], v['tasks_with_ready'], v['ready_forms'], None if v['mean_log10_median_chance'] is None else round(v['mean_log10_median_chance'], 3),
                None if v['median_chance_over_tasks'] is None else '%.2e' % v['median_chance_over_tasks'], v['median_rank_rule'], v['n_rule_reads'], v['median_rank_init'], v['n_init_reads']))
            for src, cc in v['cell'].items():
                print('    %s positives (N600: gold by session key; S120: seeded) | %s | %s | %s' % (src, show('IDENT CELL', cc['ident']), show('whole', cc['whole']), show('no Ident', cc['no_ident'])))
    json.dump(res, open(HERE + outp, 'w'), indent=1)


main()
