"""Item 11: the held read of one arm, by replay with uses. The coordinator runs it. A ledger file refuses a second read of an arm.

  python -I features_node_read_held.py ARM run SECONDS [I/N]      reads runs until SECONDS pass, resumes; I/N: every N-th run from I (N processes)
  python -I features_node_read_held.py ARM finish                 when all 100 runs are read: tables, the results file, the ledger line "done"
  python -I features_node_read_held.py ARM status                 runs done, ledger lines
  python -I features_node_read_held.py ARM check                  whether the ledger would accept a read of ARM (HELD_LEDGER=path tests another ledger)
  ARM: hand (the base: the recorded score, t 1), C-shuffle, C-depth, M-H, M-T, M-TS, in this order. Run it on the engine venv Python (sklearn 1.6.1).
  Pilot, no held label: ... pilot=NAME:FEATURES:T:TASK run|finish    (an N600 task and a tune fold model, ledger held-reads-pilot.jsonl, out dir read-pilot/)

held-reads.jsonl (one line per event):
  start: written once, before the first run of the arm, with the model's sha256 (checked against final-models/NAME.json and the state file), the time, the sets H and B;
  done:  written by finish, with M1 M2 M3 and the gain, and for C-shuffle whether its bar passed.
  A second read is refused: a "done" line for the arm, or a "start" line with another sha256, or an arm out of order, or any arm after a C-shuffle that missed its bar.
  Runs of one read can resume (same sha256, no "done" line), since a read is slow and goes in slices.

Replay of each run: 20 seeds; each opening is drawn again from the run's alive nodes with s = t * model, uses follow the replay's own picks (readlib.py).
Label sets: hash (the published read's, M1 on its 34 form-runs of H at the 3,600 s cut) and session (rebuilt rows' session key). Variants: all nodes, and without the
replay-differing nodes (row check tied, other counts or no table). H is read at its 600 s and 3,600 s cuts, B at its last write.
Bands: 90%, 10,000 resamples of tasks (the two seeds of a task stay together).
"""
import fcntl, json, os, pickle, sys, time
T0 = time.time()
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'  # the data folder
sys.path.insert(0, HERE)
import numpy as np
import final_arms as FA

ARM = sys.argv[1]
CMD = sys.argv[2]
PILOT = None
if ARM.startswith('pilot='):
    PILOT = ARM[6:].split(':')       # NAME:FEATURES:T:TASK   (NAME hand: the recorded score)
    ARM = 'pilot-hand' if PILOT[0] == 'hand' else 'pilot'
LEDGER = os.environ.get('HELD_LEDGER') or HERE + ('held-reads-pilot.jsonl' if PILOT else 'held-reads.jsonl')   # HELD_LEDGER: a test ledger
OUTDIR = HERE + ('read-pilot/' if PILOT else 'read-out/') + ARM + '/'
NSEEDS = int(os.environ.get('READ_SEEDS', 20))
BOOT = 10000


def log(m):
    print('%7.1fs %s' % (time.time() - T0, m), flush=True)


def lines():
    return [json.loads(l) for l in open(LEDGER)] if os.path.exists(LEDGER) else []


def append(rec):
    with open(LEDGER, 'a') as f:
        f.write(json.dumps(rec) + '\n')


# ---- model
def model_for(arm):
    """(scorer, sha256, info). Hand: the recorded score."""
    if arm in ('hand', 'pilot-hand'):
        return (lambda rows, R: R.score), 'recorded-score', dict(features='hand', t=1.0)
    import forest as FO
    import features_node_data as DT
    if PILOT:
        name, feats, t, task = PILOT
        fold = next(k for k, f in enumerate(DT.folds(5)) if task in f)
        sp = HERE + 'fit-out/%s-f%d.state.pkl' % (name, fold)
        sha, info = FA.sha256(sp), dict(features=feats, t=float(t), state=os.path.basename(sp))
    else:
        if not os.path.exists(FA.card_path(arm)) or not os.path.exists(FA.state_path(arm)):
            sys.exit('refused: no fitted model for %s. Fit it (fit-jobs-final.txt), then run features_node_final.py %s 900 500.' % (arm, arm))
        card = json.load(open(FA.card_path(arm)))
        sp = FA.state_path(arm)
        sha = FA.sha256(sp)
        if card['sha256'] != sha:
            sys.exit('refused: %s differs from final-models card (%s vs %s)' % (sp, sha, card['sha256']))
        feats, t = card['features'], card['t']
        info = dict(features=feats, t=t, state=os.path.basename(sp), card=os.path.basename(FA.card_path(arm)))
    models, done = pickle.load(open(sp, 'rb'))
    if not PILOT and done != FA.ARMS[arm]['rounds']:
        sys.exit('refused: fit has %d of %d rounds' % (done, FA.ARMS[arm]['rounds']))
    F = FO.Forest(models)
    t = float(t)

    def scorer(rows, R):
        if feats == 'H':
            X = rows['H']
            if not PILOT:
                assert rows['hand_names'] == card['feature_names'], 'hand feature names differ from the fit'
        else:
            ci, sel = DT.cols_of(feats, rows['names'])
            X = rows['X'][:, ci]
            if not PILOT:
                assert [str(x) for x in sel] == card['feature_names'], 'feature names differ from the fit'
        return t * F.predict(X)
    return scorer, sha, info


# ---- ledger
def gate(arm, L):
    """The refusal text for a read of ARM given the ledger lines L, or None."""
    mine = [l for l in L if l['arm'] == arm]
    if any(l['event'] == 'done' for l in mine):
        return 'refused: arm %s has been read (ledger %s)' % (arm, LEDGER)
    if any(l['event'] == 'start' for l in mine) or PILOT:
        return None       # a resume of a read that was started
    if arm not in FA.READ_ORDER:
        return 'refused: %s is not an arm (%s)' % (arm, ' '.join(FA.READ_ORDER))
    for prev in FA.READ_ORDER[:FA.READ_ORDER.index(arm)]:
        if not any(l['arm'] == prev and l['event'] == 'done' for l in L):
            return 'refused: read %s first (order: %s)' % (prev, ' '.join(FA.READ_ORDER))
    shuf = [l for l in L if l['arm'] == 'C-shuffle' and l['event'] == 'done']
    if arm not in ('hand', 'C-shuffle') and shuf and not shuf[0].get('passes_bar'):
        return 'refused: C-shuffle missed its bar (M1 at most .0107 and RULE rank share at least .3): a leak or a code fault. Stop.'
    return None


def begin(arm, sha, info):
    """Writes the start line, or lets a resume pass. Exits with a refusal otherwise."""
    with open(LEDGER + '.lock', 'w') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        L = lines()
        msg = gate(arm, L)
        if msg:
            sys.exit(msg)
        st = [l for l in L if l['arm'] == arm and l['event'] == 'start']
        if st:
            if st[0]['sha256'] != sha:
                sys.exit('refused: arm %s has a start line with sha256 %s, this model is %s' % (arm, st[0]['sha256'], sha))
            return False
        append(dict(arm=arm, event='start', time=time.strftime('%Y-%m-%dT%H:%M:%S%z'), sha256=sha, sets=['hour', 'base'] if not PILOT else ['n600'], **info))
        return True


def run_list():
    import common2 as C2
    if PILOT:
        return [('n600', 'nodes_s0', PILOT[3])]
    out = []
    for s in ('hour', 'base'):
        ok = {(json.loads(l)['arm'], json.loads(l)['task']) for l in open(HERE + s + '-sampler-replay-checks.jsonl') if json.loads(l)['failed'] is None}
        out += [(s, a, t) for a in C2.SETS[s]['arms'] for t in C2.SETS[s]['tasks'] if (a, t) in ok]
    return out


def out_path(r):
    return OUTDIR + '%s.%s.%s.pkl' % r


def do_check():
    msg = gate(ARM, lines())
    print(msg or 'the ledger would accept a read of %s' % ARM)


def do_run():
    msg = gate(ARM, lines())
    if msg:
        sys.exit(msg)
    seconds = float(sys.argv[3])
    sl = sys.argv[4] if len(sys.argv) > 4 else '0/1'
    i_, n_ = map(int, sl.split('/'))
    scorer, sha, info = model_for(ARM)
    if begin(ARM, sha, info):
        log('ledger: start line written for %s sha256 %s' % (ARM, sha[:16]))
    os.makedirs(OUTDIR, exist_ok=True)
    import readlib
    runs = run_list()[i_::n_]
    done_n = fails = 0
    for r in runs:
        if os.path.exists(out_path(r)):
            continue
        if time.time() - T0 > seconds:
            break
        t1 = time.time()
        try:
            res = readlib.read_run(r[0], r[1], r[2], scorer, NSEEDS)
        except readlib.Incomplete as e:
            print('SKIPPED', e, flush=True)
            fails += 1
            continue
        pickle.dump(res, open(out_path(r) + '.tmp', 'wb'))
        os.replace(out_path(r) + '.tmp', out_path(r))
        done_n += 1
        log('%s %s %s: nodes %d openings %d items %d seeds %d in %.1f s' % (r[0], r[1], r[2], res['n'], res['openings'], len(res['items']), NSEEDS, time.time() - t1))
    left = sum(not os.path.exists(out_path(r)) for r in runs)
    el = time.time() - T0
    log('this call: %d runs read, %d skipped; left in this slice %d of %d; rate %.1f s/run; ETA %s s' % (done_n, fails, left, len(runs), el / max(done_n, 1), round(left * el / done_n) if done_n else None))


# ---- aggregation
def wmed(v, W):
    """Median of v with integer weights W (B x F), per row of W."""
    o = np.argsort(v, kind='stable')
    v, W = np.asarray(v)[o], W[:, o]
    cw = np.cumsum(W, 1)
    tot = cw[:, -1:]
    lo = (cw >= tot / 2).argmax(1)
    hi = (cw > tot / 2).argmax(1)
    return (v[lo] + v[hi]) / 2


def band(vals_fn, tasks, tid, B=BOOT):
    """90% band of vals_fn(W) with W the (B x F) task multiplicities of form-runs/reads (tid: task index of each unit)."""
    T = len(tasks)
    rng = np.random.default_rng(5)
    idx = rng.integers(0, T, (B, T))
    mult = np.zeros((B, T))
    for b in range(B):
        mult[b] = np.bincount(idx[b], minlength=T)
    W = mult[:, tid]
    v = vals_fn(W)
    v = v[np.isfinite(v)]
    return (float(np.percentile(v, 5)), float(np.percentile(v, 95))) if len(v) else (float('nan'), float('nan'))


def fmt(x):
    return 'nan' if x != x else ('%.3g' % x)


def load_all(arm):
    d = HERE + ('read-pilot/' if PILOT else 'read-out/') + arm + '/'
    out = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.endswith('.pkl'):
            out.append(pickle.load(open(d + f, 'rb')))
    return out


GROUPS = [('H600', 'hour', '600'), ('H3600', 'hour', '3600'), ('B', 'base', 'last'), ('N600', 'n600', 'last')]


def population(runs, setn, cut, ls, vn, pop='ready_end'):
    """Form-run units: dict key -> (task, kind, p, nsamp, static p), and read units."""
    units, reads = {}, []
    for r in runs:
        if r['set'] != setn:
            continue
        res = r['res'][vn]
        for k, it in enumerate(r['items']):
            if it['ls'] != ls or it['cut'] != cut or it['pop'] != pop or it['skipped']:
                continue
            p = res['p_actual'][k]
            if not (p == p):
                continue
            stat = res['static'][cut]['items'].get(k)
            units[(r['set'], r['arm'], r['task'], it['h'])] = dict(task=r['task'], kind=it['kind'], p=p, pst=stat[0] if stat else float('nan'), nb=it['nb'])
            for q, qk in zip(it['rd'], it['rd_kinds']):
                rk = res['ranks'].get('%d|%d' % (k, q))
                if rk:
                    reads.append(dict(task=r['task'], qk=qk, rank_x=rk[0], rank_s=rk[1], n=rk[2], key=(r['set'], r['arm'], r['task'], it['h'], q)))
    return units, reads


def summ_cell(R_, C_):
    if len(R_) == 0:
        return None
    R_, C_ = np.asarray(R_), np.asarray(C_)
    return dict(n=int(len(R_)), median_rank=float(np.median(R_)), top10=float((R_ <= 10).mean()), top100=float((R_ <= 100).mean()), top1000=float((R_ <= 1000).mean()),
                median_chance=float(np.median(C_)), mean_chance=float(np.mean(C_)))


def show_cell(tag, d):
    return '%s: none' % tag if not d else '%s: n %d median rank %g top10 %.3f top100 %.3f top1000 %.3f chance per opening median %.2e mean %.2e' % (
        tag, d['n'], d['median_rank'], d['top10'], d['top100'], d['top1000'], d['median_chance'], d['mean_chance'])


def aggregate(arm, runs, hand_runs):
    out, txt = {}, []

    def P(s):
        txt.append(s)
        print(s, flush=True)
    for gname, setn, cut in GROUPS:
        rs = [r for r in runs if r['set'] == setn]
        if not rs:
            continue
        hs = {(r['set'], r['arm'], r['task']): r for r in (hand_runs or [])}
        for ls in ('hash', 'session'):
            for vn in ('all', 'clean'):
                pops = {}
                for pop in ('ready_end', 'then_covered'):
                    pops[pop] = population(runs, setn, cut, ls, vn, pop)
                units, reads = pops['ready_end']
                key = '%s|%s|%s' % (gname, ls, vn)
                tasks = sorted({u['task'] for u in units.values()} | {x['task'] for x in reads})
                if not units:
                    P('== %s %s labels %s, %s: no ready_end form-runs' % (arm, gname, ls, 'all nodes' if vn == 'all' else 'without the replay-differing nodes'))
                    continue
                ti = {t: i for i, t in enumerate(tasks)}
                ukeys = sorted(units)
                pv = np.array([units[k]['p'] for k in ukeys])
                ut = np.array([ti[units[k]['task']] for k in ukeys])
                m1 = float(np.median(pv))
                b1 = band(lambda W: wmed(pv, W), tasks, ut)
                m3 = int((pv >= .1).sum())
                b3 = band(lambda W: (W * (pv >= .1)).sum(1) / W.sum(1), tasks, ut)
                rule = [x for x in reads if x['qk'] == 'RULE']
                ent = dict(key=key, form_runs=len(units), tasks=len(tasks), M1=m1, M1_band=b1, M3=m3, M3_share=m3 / len(units), M3_share_band=b3)
                P('== %s  %s  labels %s  %s: form-runs (ready_end) %d, tasks %d' % (arm, gname, ls, 'all nodes' if vn == 'all' else 'WITHOUT replay-differing nodes', len(units), len(tasks)))
                P('   M1 median one-step chance per opening (replay p_actual) %s  90%% band [%s, %s]' % (fmt(m1), fmt(b1[0]), fmt(b1[1])))
                if rule:
                    rv = np.array([x['rank_x'] for x in rule], float)
                    rs_ = np.array([x['rank_s'] for x in rule], float)
                    rt = np.array([ti[x['task']] for x in rule])
                    rshare = float(np.median([x['rank_x'] / x['n'] for x in rule]))
                    b2 = band(lambda W: wmed(rv, W), tasks, rt)
                    ent.update(M2=float(np.median(rv)), M2_band=b2, M2_by_score=float(np.median(rs_)), M2_reads=len(rule), rule_rank_share=rshare)
                    P('   M2 median absolute rank of RULE reads by score - uses at the last opening of the window %s  90%% band [%s, %s]  (%d reads; by score alone %s; median rank share %.3f)' % (
                        fmt(float(np.median(rv))), fmt(b2[0]), fmt(b2[1]), len(rule), fmt(float(np.median(rs_))), rshare))
                else:
                    P('   M2: no RULE reads')
                P('   M3 form-runs with M1 chance .1 or more: %d of %d (share %.3f, 90%% band [%.3f, %.3f])' % (m3, len(units), m3 / len(units), b3[0], b3[1]))
                # gain over the hand score
                if hand_runs and arm not in ('hand', 'pilot-hand'):
                    hu, _ = population(hand_runs, setn, cut, ls, vn, 'ready_end')
                    common = [k for k in ukeys if k in hu]
                    if common:
                        a = np.array([units[k]['p'] for k in common])
                        h = np.array([hu[k]['p'] for k in common])
                        ct = np.array([ti[units[k]['task']] for k in common])
                        g = float(np.median(a) / max(np.median(h), 1e-300))
                        bg = band(lambda W: wmed(a, W) / np.maximum(wmed(h, W), 1e-300), tasks, ct)
                        ent.update(gain=g, gain_band=bg, hand_M1=float(np.median(h)))
                        P('   gain in median chance over the hand score (same form-runs, hand M1 %s): %.3gx  90%% band [%.3g, %.3g]' % (fmt(float(np.median(h))), g, bg[0], bg[1]))
                kinds = {}
                for kd in ('DET', 'RULE', 'INIT'):
                    ks = [k for k in ukeys if units[k]['kind'] == kd]
                    if ks:
                        kinds[kd] = (len(ks), float(np.median([units[k]['p'] for k in ks])), int(sum(units[k]['p'] >= .1 for k in ks)))
                ent['by_form_kind'] = kinds
                P('   by form kind (n, median chance, with .1 or more): ' + '; '.join('%s %d, %s, %d' % (k, v[0], fmt(v[1]), v[2]) for k, v in kinds.items()))
                rk_by = {}
                for kd in ('DET', 'RULE', 'INIT'):
                    xs = [x['rank_x'] for x in reads if x['qk'] == kd]
                    if xs:
                        rk_by[kd] = (len(xs), float(np.median(xs)))
                ent['rank_by_read_kind'] = rk_by
                P('   median rank by score - uses by read kind (n, rank): ' + '; '.join('%s %d, %s' % (k, v[0], fmt(v[1])) for k, v in rk_by.items()))
                ps = np.array([units[k]['pst'] for k in ukeys])
                ent['static_median'] = float(np.nanmedian(ps))
                P('   static chance at the cut with uses 0, median over these form-runs: %s' % fmt(ent['static_median']))
                ue, re_ = pops['then_covered']
                if ue:
                    ent['then_covered_M1'] = float(np.median([u['p'] for u in ue.values()]))
                    ent['then_covered_n'] = len(ue)
                    P('   forms covered inside the cut (then_covered): %d form-runs, median chance %s' % (len(ue), fmt(ent['then_covered_M1'])))
                out[key] = ent
        # cut-level: Ident cell, curve, top shares, picks by kind, replay-differing nodes
        for vn in ('all', 'clean'):
            rk, ch, idn = [], [], []
            cur = dict(sum_all=0, cnt_all=0, sum_pos=0, cnt_pos=0)
            t10, t100, pk = [], [], []
            for r in rs:
                st = r['res'][vn]['static'].get(cut)
                if not st:
                    continue
                rk += st['pos_rank']
                ch += st['pos_chance']
                idn += st['pos_ident']
                for k_ in cur:
                    cur[k_] = np.array(st['curve'][k_], float) + cur[k_]
                t10.append(st['top10'])
                t100.append(st['top100'])
                pk.append(r['res'][vn]['picks_by_kind'])
            if not rk and not t10:
                continue
            rk, ch, idn = np.array(rk), np.array(ch), np.array(idn, bool)
            cells = dict(whole=summ_cell(rk, ch), ident=summ_cell(rk[idn], ch[idn]), no_ident=summ_cell(rk[~idn], ch[~idn]))
            tag = '%s %s' % (arm, gname)
            P('-- %s, %s: positives by session key at the cut (static, uses 0)' % (tag, 'all nodes' if vn == 'all' else 'without replay-differing nodes'))
            P('   ' + show_cell('IDENT CELL (tb_t_Ident above 0)', cells['ident']))
            P('   ' + show_cell('whole', cells['whole']))
            P('   ' + show_cell('no Ident', cells['no_ident']))
            if np.ndim(cur['cnt_all']):
                from readlib import RANK_BINS
                labels = ['%d' % RANK_BINS[0]] + [('%d' % RANK_BINS[i]) if RANK_BINS[i] == RANK_BINS[i - 1] + 1 else '%d-%d' % (RANK_BINS[i - 1] + 1, RANK_BINS[i]) for i in range(1, len(RANK_BINS) - 1)] + ['>%d' % RANK_BINS[-2]]
                curve = {labels[i]: (float(cur['sum_all'][i] / cur['cnt_all'][i]) if cur['cnt_all'][i] else None, float(cur['sum_pos'][i] / cur['cnt_pos'][i]) if cur['cnt_pos'][i] else None, int(cur['cnt_pos'][i])) for i in range(len(labels))}
                P('   chance of a scored pick by rank bin (mean over nodes; mean over right nodes; right nodes): ' + '; '.join('%s: %s, %s, %d' % (k, fmt(v[0] if v[0] is not None else float('nan')), fmt(v[1] if v[1] is not None else float('nan')), v[2]) for k, v in curve.items()))
            else:
                curve = None
            P('   share of weight in the top 10 %.3f, top 100 %.3f (mean over runs); share of replay picks by form kind DET %.3f RULE %.3f INIT %.3f other %.3f' % tuple([np.mean(t10), np.mean(t100)] + list(np.mean(pk, 0))))
            bad = sum(r['bad_nodes'] for r in rs)
            nodes = sum(r['n'] for r in rs)
            rcs = np.sum([r['rowcheck'] for r in rs], 0)
            out['cut:%s|%s' % (gname, vn)] = dict(cells=cells, curve=curve, top10=float(np.mean(t10)), top100=float(np.mean(t100)), picks_by_kind=np.mean(pk, 0).tolist(), replay_differing_nodes=int(bad), nodes=int(nodes), rowcheck=rcs.tolist())
            if vn == 'all':
                P('   row check over these runs (equal, ident, tied, other counts, no table): %s; replay-differing nodes %d of %d (%.2f%%); runs with at least one: %d of %d' % (
                    rcs.tolist(), bad, nodes, 100 * bad / max(nodes, 1), sum(r['bad_nodes'] > 0 for r in rs), len(rs)))
    return out, txt


def do_finish():
    scorer, sha, info = model_for(ARM)
    L = [l for l in lines() if l['arm'] == ARM]
    if not any(l['event'] == 'start' for l in L):
        sys.exit('refused: no start line for %s' % ARM)
    if any(l['event'] == 'done' for l in L):
        sys.exit('refused: arm %s has been read' % ARM)
    runs_needed = run_list()
    missing = [r for r in runs_needed if not os.path.exists(out_path(r))]
    if missing:
        sys.exit('not finished: %d of %d runs have no result, e.g. %s. Run the slices again.' % (len(missing), len(runs_needed), missing[0]))
    runs = load_all(ARM)
    hand_runs = None
    if ARM not in ('hand', 'pilot-hand'):
        hd = HERE + ('read-pilot/pilot-hand/' if PILOT else 'read-out/hand/')
        if os.path.isdir(hd):
            hand_runs = load_all('pilot-hand' if PILOT else 'hand')
    out, txt = aggregate(ARM, runs, hand_runs)
    json.dump(out, open(OUTDIR[:-1] + '.results.json', 'w'), indent=1, default=float)
    open(OUTDIR[:-1] + '.results.txt', 'w').write('\n'.join(txt) + '\n')
    h = out.get('H3600|hash|all', {})
    b = out.get('B|hash|all', {})
    rec = dict(arm=ARM, event='done', time=time.strftime('%Y-%m-%dT%H:%M:%S%z'), sha256=sha, runs=len(runs),
               H3600_hash_all=dict(form_runs=h.get('form_runs'), M1=h.get('M1'), M2=h.get('M2'), M3=h.get('M3'), gain=h.get('gain')),
               B_hash_all=dict(form_runs=b.get('form_runs'), M1=b.get('M1'), M2=b.get('M2'), M3=b.get('M3'), gain=b.get('gain')))
    if ARM == 'C-shuffle':
        rec['passes_bar'] = bool(h.get('M1') is not None and h['M1'] <= .0107 and h.get('rule_rank_share') is not None and h['rule_rank_share'] >= .3)
        P_ = 'C-shuffle bar: M1 on H (hash labels, 3,600 s) %s at most .0107, RULE rank share %s at least .3 -> %s' % (fmt(h.get('M1', float('nan'))), fmt(h.get('rule_rank_share', float('nan'))), 'PASS' if rec['passes_bar'] else 'MISS: STOP, read no other model')
        print(P_)
    if ARM == 'hand':
        chk = sum(json.loads(l)['nodes_with_other_uses'] for l in open(HERE + 'hour-sampler-replay-checks.jsonl'))
        rec['base_reproduction'] = dict(M1_H=h.get('M1'), in_band=bool(h.get('M1') is not None and .00050 <= h['M1'] <= .00060), nodes_with_other_uses_H=chk)
        print('base reproduction: M1 on H (hash labels, 3,600 s) %s, band .00050 to .00060 -> %s; nodes with other uses on the replay of H: %d' % (fmt(h.get('M1', float('nan'))), 'PASS' if rec['base_reproduction']['in_band'] else 'MISS', chk))
    append(rec)
    log('ledger: done line written for %s; results in %s' % (ARM, OUTDIR[:-1] + '.results.txt'))


def do_status():
    runs = run_list()
    have = sum(os.path.exists(out_path(r)) for r in runs)
    print('arm', ARM, 'runs read', have, 'of', len(runs))
    for l in lines():
        if l['arm'] == ARM:
            print(' ', {k: v for k, v in l.items() if k in ('event', 'time', 'sha256', 'passes_bar')})


{'run': do_run, 'finish': do_finish, 'status': do_status, 'check': do_check}[CMD]()
