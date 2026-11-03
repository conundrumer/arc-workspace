"""The read of one run (item 11): ready forms, rank, static chance, replay chance, Ident cell. Shared by features_node_read_held.py.

  read_run(SET, arm, task, scorer, seeds) -> dict   (scorer(rows) gives the score s of each node, t already applied)

Two label sets: 'hash' (the published read's row hash labels, as sampler-ready-forms.py) and 'session' (the rebuilt rows' session key labels).
Two variants: 'all' (every node) and 'clean' (nodes whose row check is tied, other counts or no table get weight 0 and are not ranked).
Cuts: the seconds of the set's cuts (hour 600 and 3600, base and n600 their last write).
The replay draws each opening of the run again from its alive nodes: key = s - uses - log(-log r), the 5 best, then the least-used node outside them,
uses follow the replay's own picks. The openings (alive nodes, refused scopes) are the cache of sampler-picks-cache.py.
Reads no model and no label of its own: the scorer and the rows are given.
"""
import collections, glob, json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, HERE)
import numpy as np
import poolrun, common2 as C2

INF = 1 << 60
STRIDE = 10
MAXB = 7
RANK_BINS = [1, 2, 3, 5, 10, 30, 100, 300, 1000, 3000, 10 ** 9]


def solve_c(w):
    """c with the sum over nodes of 1 - exp(-w c) equal to 5: a node's chance of a scored pick, in the race form of the Gumbel draw."""
    c = 5.0 / w.sum()
    for _ in range(40):
        e = np.exp(-w * c)
        f = (1 - e).sum() - 5.0
        if abs(f) < 1e-7:
            break
        c = max(c - f / (w * e).sum(), c / 8)
    return c


def p_all(masses, c, extra=0.0):
    """P(a set of needed reads is all hit), inclusion and exclusion over the needed bits. masses[sig]: weight of nodes whose pick holds the reads of sig."""
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


def need_masses(sig, idx, w, n, rest_bits, nb):
    """Masses over the reads still needed after the least-used pick."""
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


class Incomplete(Exception):
    pass


def load_rows(SET, arm, task):
    """Rebuilt rows of a run, by node id. Raises Incomplete where the rebuild isn't done."""
    OUT = HERE + SET + '-rows/'
    stem = task if SET == 'n600' else arm + '.' + task
    pp = OUT + stem + '.progress.json'
    if not os.path.exists(pp):
        raise Incomplete('%s %s %s: no rows' % (SET, arm, task))
    prog = json.load(open(pp))
    if prog['next'] < prog.get('forms', 1 << 60):
        raise Incomplete('%s %s %s: rebuild at %d of %d forms' % (SET, arm, task, prog['next'], prog['forms']))
    zs = [np.load(p) for p in sorted(glob.glob(OUT + stem + '.part*.npz'))]
    mc = [str(c) for c in zs[0]['meta_cols']]
    meta = np.vstack([z['meta'] for z in zs])
    col = {c: meta[:, i] for i, c in enumerate(mc)}
    node = col['node'].astype(np.int64)
    o = np.argsort(node)
    if not (node[o] == np.arange(len(node))).all():
        raise Incomplete('%s %s %s: node ids are not 0..n-1' % (SET, arm, task))
    names = [str(x) for x in zs[0]['names']]
    golds = sum((json.loads(str(z['gold'][0])) for z in zs), [])
    X = np.vstack([z['X'] for z in zs])[o]
    return dict(n=len(node), rowcheck=col['rowcheck'][o].astype(int), y=col['y'][o].astype(int), kind=col['kind'][o].astype(int), form=col['form'][o].astype(np.int64), age=col['age'][o].astype(np.int64),
                names=names, hand_names=[str(x) for x in zs[0]['hand_names']], X=X, H=np.vstack([z['H'] for z in zs])[o], gold=[golds[i] for i in o],
                ident=np.nan_to_num(X[:, names.index('tb_t_Ident')]) > 0, goldjson=json.load(open(OUT + stem + '.gold.json')))


class Labels:
    """Gold forms with reads, the first cover draw of each, and the node-by-read ownership."""

    def __init__(self, name, R, reads, kinds, first, own_of):
        self.name, self.reads, self.kinds, self.first = name, reads, kinds, first
        self.G = len(kinds)
        self.qs = sorted({q for h in range(self.G) for q in reads[h]})
        self.qi = {q: i for i, q in enumerate(self.qs)}
        self.ownN = own_of(self.qs)
        nf = max(R.forms) + 1
        fown = np.zeros((nf, len(self.qs)), bool)
        if len(self.qs):
            np.logical_or.at(fown, R.nform, self.ownN)
        reachF = fown.copy()
        for f in range(nf):
            for p in R.parents[f]:
                reachF[f] |= reachF[p]
        self.reachN = reachF[R.nform]

    def ready(self, dc):
        out = []
        for h in range(self.G):
            rd = self.reads[h]
            if not rd:
                continue
            fr = [self.first.get(q) for q in rd]
            if any(f is None or f > dc for f in fr):
                continue
            dr = max(fr)
            fh = self.first.get(h)
            de, pop = (fh, 'then_covered') if (fh is not None and fh <= dc) else (dc, 'ready_end')
            if de <= dr:
                continue
            out.append(dict(h=h, rd=rd, dr=int(dr), de=int(de), pop=pop, kind=self.kinds[h], nb=len(rd)))
        return out


def hash_labels(R):
    lab = R.lab
    G = len(lab['lines'])
    pair_tid = {p: i for i, p in enumerate(R.pairs)}
    gt = {g: sorted(pair_tid[p] for p in lab['tables'][g] if p in pair_tid) for g in range(G)}
    tage = np.full(R.ntab, INF, np.int64)
    np.minimum.at(tage, R.tid, R.age)
    first = {g: (int(tage[gt[g]].min()) if gt[g] else None) for g in range(G)}

    def own_of(qs):
        own = np.zeros((R.n, len(qs)), bool)
        for b, q in enumerate(qs):
            if gt[q]:
                own[:, b] = np.isin(R.tid, gt[q])
        return own
    return Labels('hash', R, lab['reads'], lab['kinds'], first, own_of)


def session_labels(R, rows):
    g = rows['goldjson']
    G = len(g['kinds'])
    own_all = np.zeros((R.n, G), bool)
    for i, gs in enumerate(rows['gold']):
        for q in gs:
            own_all[i, q] = True
    first = {q: (int(R.age[own_all[:, q]].min()) if own_all[:, q].any() else None) for q in range(G)}

    def own_of(qs):
        return own_all[:, qs] if len(qs) else np.zeros((R.n, 0), bool)
    return Labels('session', R, g['reads'], g['kinds'], first, own_of)


def pos_stats(s, is_pos, ident):
    """Per positive node: rank by s in its pool (ties at their mean) and the chance of a scored pick 1 - exp(-c w)."""
    w = np.exp(s - s.max())
    c = solve_c(w)
    ss = np.sort(s)
    p = np.nonzero(is_pos)[0]
    lo, hi = np.searchsorted(ss, s[p], 'left'), np.searchsorted(ss, s[p], 'right')
    rank = (len(s) - hi) + .5 * (hi - lo - 1) + 1
    return rank, 1 - np.exp(-c * w[p]), ident[p]


def read_run(SET, arm, task, scorer, seeds, log=None):
    S = C2.SETS[SET]
    R = poolrun.Run(SET, arm, task, labels=True)
    rows = load_rows(SET, arm, task)
    if rows['n'] != R.n:
        raise Incomplete('%s %s %s: rows %d, bank nodes %d' % (SET, arm, task, rows['n'], R.n))
    P = np.load(HERE + 'rows/sampler-picks-%s-%s.npz' % (arm, task))
    J, D0, N, BEST, REST = P['v'], P['d0'], P['n'], P['best'], P['rest']
    s0 = np.asarray(scorer(rows, R), np.float64)
    assert s0.shape == (R.n,) and np.isfinite(s0).all(), 'scores are not finite'
    bad = rows['rowcheck'] >= 2
    variants = {'all': (s0, np.zeros(R.n, bool)), 'clean': (np.where(bad, -1e9, s0), bad)}
    labs = {'hash': hash_labels(R), 'session': session_labels(R, rows)}
    g = rows['goldjson']
    same_reads = (g['reads'] == labs['hash'].reads and g['kinds'] == labs['hash'].kinds)
    cuts = {}
    for sec in S['cuts']:
        dc = R.cut_draw(sec)[0]
        cuts[str(sec) if SET == 'hour' else 'last'] = min(int(dc), int(R.draws))
    nalive = {c: int(np.searchsorted(R.age, dc, side='right')) for c, dc in cuts.items()}
    # items: one per (label set, cut, form)
    items = []
    for ln, L in labs.items():
        for cn, dc in cuts.items():
            for fm in L.ready(dc):
                fm = dict(fm, ls=ln, cut=cn)
                if fm['nb'] > MAXB:
                    fm['skipped'] = True
                    items.append(fm)
                    continue
                bits = np.array([L.qi[q] for q in fm['rd']])
                sig = (L.reachN[:, bits] * (1 << np.arange(fm['nb']))).sum(1).astype(np.int64)
                fm.update(bits=bits, sig=sig, idx=np.nonzero(sig)[0])
                items.append(fm)
    valid = J >= 0
    for it in items:
        it['winj'] = np.nonzero(valid & (D0 >= it['dr']) & (D0 < it['de']))[0].tolist()
    samp = set(j for j in range(len(J)) if valid[j] and j % STRIDE == 0)
    active, ends = collections.defaultdict(list), collections.defaultdict(list)
    for k, it in enumerate(items):
        w_ = it['winj']
        if not w_ or it.get('skipped'):
            continue
        for j in (w_[0], w_[len(w_) // 2], w_[-1]):
            samp.add(j)
        ends[w_[-1]].append(k)
    for k, it in enumerate(items):
        if it['winj'] and not it.get('skipped'):
            ws = set(it['winj'])
            for j in samp:
                if j in ws:
                    active[j].append(k)
    nk = len(items)
    kind_of_node = rows['kind']
    out = dict(set=SET, arm=arm, task=task, n=R.n, draws=int(R.draws), cuts=cuts, nalive=nalive, openings=int(valid.sum()), bad_nodes=int(bad.sum()), rowcheck=np.bincount(rows['rowcheck'], minlength=5).tolist(), same_reads=bool(same_reads),
               seeds=seeds, items=[dict(ls=it['ls'], cut=it['cut'], h=it['h'], kind=it['kind'], nb=it['nb'], pop=it['pop'], dr=it['dr'], de=it['de'], nwin=len(it['winj']), skipped=bool(it.get('skipped')), rd=it['rd'],
                                        rd_kinds=[labs[it['ls']].kinds[q] for q in it['rd']]) for it in items], res={})
    rng_base = int.from_bytes(('%s%s%s' % (SET, arm, task)).encode()[:8].ljust(8, b'_'), 'little') % (1 << 31)
    for vn, (s_v, bad_v) in variants.items():
        pacc = np.zeros((seeds, nk))
        pn = np.zeros((seeds, nk))
        racc = {}
        pk = np.zeros(4)
        okmask = ~bad_v
        for sd in range(seeds):
            rng = np.random.default_rng([rng_base, sd])
            uses = np.zeros(R.n, np.float64)
            for j in range(len(J)):
                n = int(N[j])
                if n <= 0:
                    continue
                r = rng.random(n)
                r = np.where(r == 0, 1e-12, r)
                key = s_v[:n] - uses[:n] - np.log(-np.log(r))
                m = min(5, n)
                if m < n:
                    part = np.argpartition(-key, m - 1)[:m]
                    best = part[np.argsort(-key[part], kind='stable')]
                    u = uses[:n].copy()
                    u[best] = 1e18
                    u[bad_v[:n]] = 1e18
                    rest = int(np.argmin(u))
                    picks = np.r_[best, rest]
                else:
                    best = np.argsort(-key, kind='stable')
                    rest = None
                    picks = best
                if J[j] >= 0 and (j in active or j in ends):
                    x = s_v[:n] - uses[:n]
                    xm = x.max()
                    w = np.exp(x - xm)
                    c = solve_c(w)
                    for k in active.get(j, ()):
                        it = items[k]
                        L = labs[it['ls']]
                        rb = int(it['sig'][rest]) if rest is not None else 0
                        mm, kk = need_masses(it['sig'], it['idx'], w, n, rb, it['nb'])
                        pacc[sd, k] += 1.0 if kk == 0 else p_all(mm, c)
                        pn[sd, k] += 1
                    for k in ends.get(j, ()):
                        it = items[k]
                        L = labs[it['ls']]
                        for q, qk in zip(it['rd'], out['items'][k]['rd_kinds']):
                            own = np.nonzero(L.ownN[:n, L.qi[q]] & okmask[:n])[0]
                            if len(own) == 0:
                                continue
                            xb, sb = x[own].max(), s_v[own].max()
                            racc.setdefault((k, q), []).append((int((x[okmask[:n]] > xb).sum() + 1), int((s_v[:n][okmask[:n]] > sb).sum() + 1), int(okmask[:n].sum())))
                uses[picks] += 1
                pk += np.bincount(np.minimum(kind_of_node[picks], 3), minlength=4)
        with np.errstate(invalid='ignore'):
            pm = np.where(pn > 0, pacc / np.maximum(pn, 1), np.nan)
        pform = np.nanmean(pm, axis=0) if nk else np.zeros(0)
        out['res'][vn] = dict(p_actual=pform.tolist(), nsamp=pn.mean(0).tolist(), ranks={'%d|%d' % kq: np.median(np.array(v), axis=0).tolist() for kq, v in racc.items()}, picks_by_kind=(pk / max(pk.sum(), 1)).tolist())
        # static, at each cut, uses 0
        st = {}
        for cn, dc in cuts.items():
            nc = nalive[cn]
            s = s_v[:nc]
            ok = okmask[:nc]
            w = np.exp(s - s.max())
            c = solve_c(w)
            order = np.sort(s)[::-1]
            wsum = w.sum()
            ws = np.sort(w)[::-1]
            tm = np.full(R.ntab, -np.inf)
            np.maximum.at(tm, R.tid[:nc][ok], s[ok])
            alive_t = tm > -np.inf
            res_items = {}
            for k, it in enumerate(items):
                if it['cut'] != cn or it.get('skipped'):
                    continue
                L = labs[it['ls']]
                mm = np.bincount(it['sig'][:nc], w, minlength=1 << it['nb']) if nc else np.zeros(1 << it['nb'])
                pst = p_all(mm, c)
                rr = []
                for q, qk in zip(it['rd'], out['items'][k]['rd_kinds']):
                    own = np.nonzero(L.ownN[:nc, L.qi[q]] & ok)[0]
                    if len(own) == 0:
                        continue
                    sb = s[own].max()
                    rr.append((q, qk, int((s[ok] > sb).sum() + 1), int((tm[alive_t] > sb).sum() + 1)))
                res_items[k] = (pst, rr)
            # positives by session key: rank and chance; Ident cell
            is_pos = (rows['y'][:nc] == 1) & ok
            rk, ch, idn = pos_stats(np.where(ok, s, -1e9), is_pos, rows['ident'][:nc]) if is_pos.any() else (np.zeros(0), np.zeros(0), np.zeros(0, bool))
            # chance by rank: mean chance of a pick of the nodes in each rank bin, all nodes and right nodes
            rank_all = np.empty(nc)
            srt = np.argsort(-np.where(ok, s, -1e9), kind='stable')
            rank_all[srt] = np.arange(1, nc + 1)
            chance = 1 - np.exp(-c * w)
            bins = np.digitize(rank_all[ok], RANK_BINS[:-1], right=True)
            sa = np.bincount(bins, chance[ok], minlength=len(RANK_BINS))
            ca = np.bincount(bins, minlength=len(RANK_BINS))
            pb = np.digitize(rank_all[is_pos], RANK_BINS[:-1], right=True)
            sp = np.bincount(pb, chance[is_pos], minlength=len(RANK_BINS))
            cp = np.bincount(pb, minlength=len(RANK_BINS))
            st[cn] = dict(items=res_items, pos_rank=rk.tolist(), pos_chance=ch.tolist(), pos_ident=idn.tolist(), curve=dict(sum_all=sa.tolist(), cnt_all=ca.tolist(), sum_pos=sp.tolist(), cnt_pos=cp.tolist()),
                          top10=float(ws[:10].sum() / wsum), top100=float(ws[:100].sum() / wsum), c=float(c), nalive_ok=int(ok.sum()))
        out['res'][vn]['static'] = st
        if log:
            log('%s %s %s variant %s done' % (SET, arm, task, vn))
    return out
