"""Ready forms on the 26 hour runs, against the exact picks. Streams and resumes per run.

  python -I sampler-ready-forms.py SET SECONDS     (SET: hour or base)

A form h with reads is ready from d_ready, the draw at which the last of its reads is first covered by row hash, to d_end, its own first cover by row hash or the last bank write.
Writes form-rows.tsv (one per run and ready form), read-rows.tsv (one per run, ready form and read), phase-rows.tsv (rank at the window's start, middle and end), opening-rows.tsv (the group at sampled openings), hold-checks.jsonl.
"""
import collections, csv, itertools, json, math, os, sys, time
sys.dont_write_bytecode = True
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-rank-model-train-read-hour13-heldout37/'  # the data folder
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-rank-model-train-read-hour13-heldout37')
import numpy as np
import poolrun, common2 as C2

SET = sys.argv[1]
LIMIT = float(sys.argv[2]) if len(sys.argv) > 2 else 25
ARMS = C2.SETS[SET]['arms']
TASKS = C2.SETS[SET]['tasks']
STRIDE = int(os.environ.get('STRIDE', 10))
T0 = time.time()
INF = 1 << 60
FORM_COLS = 'arm task h kind nreads depth pop d_ready d_end sec_ready sec_end openings held_openings held_by_own_picks held_via_ancestor any_read_held tries held_tries right_kind_tries visits held_visits model_n model_held p_actual p_top1 p_top100 p_group10 p_distinct p_flat'.split()
READ_COLS = 'arm task h q qkind qdepth openings held_openings own_pick_openings reach_pick_openings rest_pick_openings mean_rank_share_score mean_rank_share_weight median_n logmean_own_share logmean_reach_share mean_p_read'.split()
PHASE_COLS = 'arm task h q phase d0 n tables rank_score rank_weight rank_table_score nown nreach best_score best_uses best_x bar_gap own_share reach_share p_read wtop'.split()
OPEN_COLS = 'arm task j d0 sec n tables wmax_x bar_nats neff n50 top10 top100 top1000 median_x mean_x'.split()


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
    nb = int(math.log2(m))
    tot = 0.0
    for T in range(m):
        if T == 0:
            tot += 1.0
            continue
        hit = sum(masses[s] for s in range(1, m) if s & T)
        k = bin(T).count('1')
        tot += (-1) ** k * math.exp(-c * (hit + k * extra))
    return max(tot, 0.0)


def need_masses(sig, idx, w, n, mneed, rest_bits, nb):
    """Masses over the reads still needed after the least-used pick. Gives masses of size 2 ** k."""
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


def one(arm, task):
    R = poolrun.Run(SET, arm, task)
    lab = R.lab
    P = np.load(HERE + 'rows/sampler-picks-%s-%s.npz' % (arm, task))
    pair_tid = {p: i for i, p in enumerate(R.pairs)}
    G = len(lab['lines'])
    gt = {g: sorted(pair_tid[p] for p in lab['tables'][g] if p in pair_tid) for g in range(G)}
    tage = np.full(R.ntab, INF, np.int64)
    np.minimum.at(tage, R.tid, R.age)
    first_rh = {g: (int(tage[gt[g]].min()) if gt[g] else None) for g in range(G)}
    differ = [(g, first_rh[g], lab['first'].get(g)) for g in range(G) if first_rh[g] != lab['first'].get(g)]
    cov = lambda g, d: first_rh[g] is not None and first_rh[g] <= d
    last = R.draws
    # own and reach of each gold form that is read
    qs = sorted({q for h in range(G) for q in lab['reads'][h]})
    qi = {q: i for i, q in enumerate(qs)}
    nf = R.nform.max() + 1 if False else max(R.forms) + 1
    fown = np.zeros((nf, len(qs)), bool)
    ownN = np.zeros((R.n, len(qs)), bool)
    tid2q = collections.defaultdict(list)
    for q in qs:
        for t in gt[q]:
            tid2q[t].append(qi[q])
    for i in range(R.n):
        for b in tid2q.get(int(R.tid[i]), ()):
            ownN[i, b] = True
            fown[R.nform[i], b] = True
    reachF = fown.copy()
    for f in range(nf):
        for p in R.parents[f]:
            reachF[f] |= reachF[p]
    reachN = reachF[R.nform]
    birth_q = {}
    for q in qs:
        b = {}
        for i in np.nonzero(ownN[:, qi[q]])[0]:
            f = int(R.nform[i])
            b[f] = min(b.get(f, INF), int(R.age[i]))
        birth_q[q] = b
    # ready forms
    forms = []
    no_table_read = 0
    for h in range(G):
        rd = lab['reads'][h]
        if not rd:
            continue
        if any(first_rh[q] is None for q in rd):
            no_table_read += 1
            continue
        dr = max(first_rh[q] for q in rd)
        de = first_rh[h] if first_rh[h] is not None else last
        if de <= dr:
            continue
        forms.append(dict(h=h, rd=rd, dr=dr, de=de, pop='ready_end' if first_rh[h] is None else 'then_covered'))
    # first copy of each table, in id order
    first_copy = np.zeros(R.n, bool)
    first_copy[np.unique(R.tid, return_index=True)[1]] = True
    vs = [v for v in R.visits if v['d0'] < R.draws]
    # visits: held by each read, all visits with new and resumed scopes
    for fm in forms:
        fm.update(openings=0, held=0, by_own=0, via_anc=0, anyq=0, tries=0, held_tries=0, right_tries=0, visits=0, held_visits=0, model=[], model_held=0)
        fm['rc'] = {q: collections.Counter() for q in fm['rd']}
        nb = len(fm['rd'])
        bits = np.array([qi[q] for q in fm['rd']])
        fm['bits'] = bits
        sig = (reachN[:, bits] * (1 << np.arange(nb))).sum(1).astype(np.int64)
        fm['sig'] = sig
        fm['idx'] = np.nonzero(sig)[0]
        fm['idx_first'] = np.nonzero((sig > 0) & first_copy)[0]
        fm['winj'] = []
    # all visits, tries
    fidsets = [set(v['fids']) for v in vs]
    hcache = {}

    def held_q(q, k):
        r = hcache.get((q, k))
        if r is None:
            fs, d = fidsets[k], vs[k]['d0']
            b = birth_q[q]
            r = any(f in fs and b[f] <= d for f in b) if len(b) < len(fs) else any(b.get(f, INF) <= d for f in fs)
            hcache[q, k] = r
        return r
    for k, v in enumerate(vs):
        for fm in forms:
            if not (fm['dr'] <= v['d0'] < fm['de']):
                continue
            hq = [held_q(q, k) for q in fm['rd']]
            ok = all(hq)
            fm['visits'] += 1
            fm['tries'] += v['tries']
            if ok:
                fm['held_visits'] += 1
                fm['held_tries'] += v['tries']
                if v['kind'] == lab['kinds'][fm['h']]:
                    fm['right_tries'] += v['tries']
    # openings
    J = P['v']
    uses = np.zeros(R.n, np.float64)
    phases = []
    open_rows = []
    sc = R.score
    for j in range(len(J)):
        k, n, d0 = int(J[j]), int(P['n'][j]), int(P['d0'][j])
        best = [int(x) for x in P['best'][j] if x >= 0]
        rest = [int(P['rest'][j])] if P['rest'][j] >= 0 else []
        picks = best + rest
        if k < 0:  # a refused scope: its picks take uses, and no visit follows
            uses[picks] += 1
            continue
        active = [fm for fm in forms if fm['dr'] <= d0 < fm['de']]
        sampled = j % STRIDE == 0
        for fm in active:
            if not fm['winj']:
                fm['first_j_seen'] = True
                sampled = True
            fm['winj'].append(j)
        ps = None
        if active or sampled:
            x = sc[:n] - uses[:n]
        if sampled:
            xm = x.max()
            w = np.exp(x - xm)
            c = solve_c(w)
            W = w.sum()
            ww = np.sort(w)[::-1]
            cum = np.cumsum(ww) / W
            pr = w / W
            open_rows.append([arm, task, j, d0, round(float(vs[k]['t']), 1), n, len(np.unique(R.tid[:n])), round(float(xm), 3), round(float(xm - math.log(c)), 3), round(float(math.exp(-(pr[pr > 0] * np.log(pr[pr > 0])).sum())), 1), int(np.searchsorted(cum, .5) + 1),
                              round(float(cum[min(9, n - 1)]), 4), round(float(cum[min(99, n - 1)]), 4), round(float(cum[min(999, n - 1)]), 4), round(float(np.median(x)), 3), round(float(math.log(W / n) + xm), 3)])
            top1, top100 = 1.0, float(ww[min(99, n - 1)])
            wdist = w * first_copy[:n]
            cd = solve_c(wdist[wdist > 0])
            cf = -math.log(1 - 5.0 / n) if n > 5 else 10.0
        for fm in active:
            fm['openings'] += 1
            h, rd = fm['h'], fm['rd']
            hq = [held_q(q, k) for q in rd]
            ok = all(hq)
            fm['held'] += ok
            fm['anyq'] += any(hq)
            own_hit, reach_hit = {}, {}
            for q, hh in zip(rd, hq):
                b = qi[q]
                oh = any(ownN[i, b] for i in picks)
                rh = any(reachN[i, b] for i in picks)
                rr = bool(rest) and reachN[rest[0], b]
                rc = fm['rc'][q]
                rc['openings'] += 1
                rc['held'] += hh
                rc['own'] += oh
                rc['reach'] += rh
                rc['rest'] += rr
                own_hit[q] = oh
            if ok:
                if all(own_hit.values()):
                    fm['by_own'] += 1
                else:
                    fm['via_anc'] += 1
            if sampled:
                nb = len(rd)
                rest_bits = int(fm['sig'][rest[0]]) if rest else 0
                m, kk = need_masses(fm['sig'], fm['idx'], w, n, None, rest_bits, nb)
                if kk == 0:
                    vals = [1.0] * 6
                else:
                    p0 = p_all(m, c, 0.0)
                    pt = p_all(m, c, top1)
                    p100 = p_all(m, c, top100)
                    pg = p_all(m, c * 10, 0.0)
                    md, _ = need_masses(fm['sig'], fm['idx_first'], w, n, None, rest_bits, nb)
                    pd_ = p_all(md, cd, 0.0)
                    mf, _ = need_masses(fm['sig'], fm['idx'], np.ones(n), n, None, rest_bits, nb)
                    pf = p_all(mf, cf, 0.0)
                    vals = [p0, pt, p100, pg, pd_, pf]
                fm['model'].append(vals)
                fm['model_held'] += ok
                for q in rd:
                    b = qi[q]
                    rc = fm['rc'][q]
                    own = np.nonzero(ownN[:n, b])[0]
                    if len(own) == 0:
                        continue
                    sb = sc[own].max()
                    xb = x[own].max()
                    rc['rs'] += ((sc[:n] > sb).sum() + 1) / n
                    rc['rx'] += ((x > xb).sum() + 1) / n
                    rc['n_rank'] += 1
                    rc['nsum'] += n
                    ro = pr[own].sum()
                    rch = pr[reachN[:n, b]].sum()
                    rc['los'] += math.log(max(ro, 1e-300))
                    rc['lrs'] += math.log(max(rch, 1e-300))
                    rc['pread'] += 1 - math.exp(-c * W * rch)
                    rc['ns'] += 1
        uses[picks] += 1
    return R, forms, open_rows, dict(arm=arm, task=task, gold=G, first_rh_differs=differ, reads_with_no_table_forms=no_table_read, ready_forms=len(forms), first_rh_count=sum(v is not None for v in first_rh.values()), union_count=sum(v is not None for v in lab['first'].values())), qi, ownN, reachN, first_rh


def sec_of(R, d):
    """The second, on the start-file clock, of the visit that holds draw d."""
    i = min(np.searchsorted(R.vends, d), len(R.vends) - 1)
    return round(float(R.visits[i]['t']), 1)


def phases(R, P, forms, qi, ownN, reachN, arm, task):
    """Rank rows at the first, middle and last opening of each window, with uses at that opening."""
    J, D0, N, B, Rst = P['v'], P['d0'], P['n'], P['best'], P['rest']
    want = collections.defaultdict(list)
    for fm in forms:
        js = fm['winj']
        if not js:
            continue
        for ph, j in (('start', js[0]), ('mid', js[len(js) // 2]), ('end', js[-1])):
            want[j].append((fm, ph))
    uses = np.zeros(R.n, np.float64)
    rows = []
    sc = R.score
    for j in range(len(J)):
        if j in want and J[j] >= 0:
            n = int(N[j])
            x = sc[:n] - uses[:n]
            xm = x.max()
            w = np.exp(x - xm)
            c = solve_c(w)
            W = w.sum()
            tm = np.full(R.ntab, -np.inf)
            np.maximum.at(tm, R.tid[:n], sc[:n])
            alive = tm > -np.inf
            nt = int(alive.sum())
            for fm, ph in want[j]:
                for q in fm['rd']:
                    b = qi[q]
                    own = np.nonzero(ownN[:n, b])[0]
                    if len(own) == 0:
                        continue
                    so = sc[own].max()
                    i = own[np.argmax(x[own])]
                    xb = float(x[i])
                    rch = np.nonzero(reachN[:n, b])[0]
                    rows.append([arm, task, fm['h'], q, ph, int(D0[j]), n, nt, int((sc[:n] > so).sum() + 1), int((x > xb).sum() + 1), int((tm[alive] > so).sum() + 1), len(own), len(rch), round(float(so), 3), int(uses[i]), round(xb, 3),
                                 round(float(xm - math.log(c) - xb), 3), '%.3g' % (w[own].sum() / W), '%.3g' % (w[rch].sum() / W), '%.3g' % (1 - math.exp(-c * w[rch].sum())), round(float(xm), 3)])
        b = [int(y) for y in B[j] if y >= 0]
        if Rst[j] >= 0:
            b.append(int(Rst[j]))
        uses[b] += 1
    return rows


def main():
    ff = {k: HERE + SET + '-' + k for k in ('sampler-form-rows.tsv', 'sampler-read-rows.tsv', 'sampler-phase-rows.tsv', 'sampler-opening-rows.tsv')}
    ck = HERE + SET + '-sampler-hold-checks.jsonl'
    done = {(json.loads(l)['arm'], json.loads(l)['task']) for l in open(ck)} if os.path.exists(ck) else set()
    if not done:
        for k, c in (('sampler-form-rows.tsv', FORM_COLS), ('sampler-read-rows.tsv', READ_COLS), ('sampler-phase-rows.tsv', PHASE_COLS), ('sampler-opening-rows.tsv', OPEN_COLS)):
            open(ff[k], 'w').write('\t'.join(c) + '\n')
    only = os.environ.get('ONLY')
    for arm in ARMS:
        for task in TASKS:
            if (arm, task) in done or (only and only != '%s/%s' % (arm, task)):
                continue
            if time.time() - T0 > LIMIT:
                print('stopped at the limit', flush=True)
                return
            t1 = time.time()
            R, forms, open_rows, chk, qi, ownN, reachN, first_rh = one(arm, task)
            P = np.load(HERE + 'rows/sampler-picks-%s-%s.npz' % (arm, task))
            ph = phases(R, P, forms, qi, ownN, reachN, arm, task)
            lab = R.lab
            fr, rr = [], []
            for fm in forms:
                h = fm['h']
                m = np.array(fm['model']) if fm['model'] else np.zeros((0, 6))
                mean = m.mean(0) if len(m) else [''] * 6
                fr.append([arm, task, h, lab['kinds'][h], len(fm['rd']), lab['depth'][h], fm['pop'], fm['dr'], fm['de'], sec_of(R, fm['dr']), sec_of(R, fm['de']), fm['openings'], fm['held'], fm['by_own'], fm['via_anc'], fm['anyq'], fm['tries'], fm['held_tries'], fm['right_tries'], fm['visits'], fm['held_visits'], len(m), fm['model_held']] + [round(float(v), 5) if v != '' else '' for v in mean])
                for q in fm['rd']:
                    c = fm['rc'][q]
                    nr = max(c['n_rank'], 1)
                    ns = max(c['ns'], 1)
                    rr.append([arm, task, h, q, lab['kinds'][q], lab['depth'][q], c['openings'], c['held'], c['own'], c['reach'], c['rest'], round(c['rs'] / nr, 4), round(c['rx'] / nr, 4), round(c['nsum'] / nr), '%.4g' % math.exp(c['los'] / ns), '%.4g' % math.exp(c['lrs'] / ns), round(c['pread'] / ns, 4)])
            for name, rows in (('sampler-form-rows.tsv', fr), ('sampler-read-rows.tsv', rr), ('sampler-phase-rows.tsv', ph), ('sampler-opening-rows.tsv', open_rows)):
                with open(ff[name], 'a') as fh:
                    fh.write(''.join('\t'.join(map(str, r)) + '\n' for r in rows))
            with open(ck, 'a') as fh:
                fh.write(json.dumps(chk) + '\n')
            print(arm, task, len(forms), 'forms', len(open_rows), 'sampled', round(time.time() - t1, 1), 's', flush=True)
    print('done', round(time.time() - T0, 1), flush=True)


main()
