"""Training rows of the derived pick model (design.md, "Training data"): the pairs on recorded scopes of non-held runs, walked summed over orders, and the pick rows of every order walk.

    bash REC/env.sh ../features-derived-pick-model-heldout37/rows.py --src n600|c120 --shard I/N [--budget S] [--only TASK,TASK] [--out FILE] [--rss-gib 2.5]

One JSON line a task to X/rows/<src>.<I>of<N>.jsonl (--out replaces the path), written when the task is done; tasks already there are skipped. A task goes to the shard crc32(task) % N.
A task that raises gets a line with status `error`. The line: task, src, status, stats (scopes, scope replay errors, pairs by status, kept pairs), pairs. A pair: si (scope index in visit time), g, kind (the form's
kind, which the walk draws), vkind (the visit's), target, fids, total, exact, orders [[call, bits, share]], wall, and rows. A row is one atom start (phases root and root2) of one valid order walk:
    o  the order's call number, w  the order's chance share among the valid orders (2^(low - bits) / sum),  st  the pick state (feats.py),  ro  whether the INIT body is rel_off,
    TB, ZB  the sums of ws and of ws * rf over the options that are not derived (lib, NOT, comparisons),  gb  [class, ws, rf] of the option gold takes where it is not derived else null,
    g0  gold takes a derived option of weight 0,  nD0  the derived options of weight 0,  D  the derived options of weight > 0: [head, j, ws, rf, gold, positive, facts],  gf  the gate facts,
    _k, _nd, _nb  diagnostics (atom index, derived and builtin atoms drawn): never a fact.
Each form has total weight 1 split evenly over its kept pairs (fit.py counts the pairs); the order weight is w.
"""
import argparse
import collections
import hashlib
import json
import os
import resource
import sys
import time
import zlib

T0 = time.time()
X = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37'
sys.path.insert(0, X + '/probe')
ap = argparse.ArgumentParser()
ap.add_argument('--src', required=True, choices=['n600', 'c120'])
ap.add_argument('--shard', default='0/1')
ap.add_argument('--budget', type=float, default=None)
ap.add_argument('--only', default=None)
ap.add_argument('--out', default=None)
ap.add_argument('--rss-gib', type=float, default=2.5)
ARGS = ap.parse_args()
SHARD_I, SHARD_N = (int(x) for x in ARGS.shard.split('/'))
import common as C  # noqa: E402

feats = C.feats
or_q, S, M, ns = C.or_q, C.S, C.S.M, C.ns
MAX_PAIRS = 6
OUT = ARGS.out or '%s/rows/%s.%dof%d.jsonl' % (X, ARGS.src, SHARD_I, SHARD_N)


def view_final_ok():
    """The snapshot of view-final is the one that manifest.json hashed."""
    m = json.load(open(X + '/manifest.json'))
    h = hashlib.sha256()
    for t in sorted(os.listdir(C.VIEW_FINAL)):
        for f in sorted(os.listdir(C.VIEW_FINAL + '/' + t)):
            h.update((t + '/' + f + ' ' + hashlib.sha256(open('%s/%s/%s' % (C.VIEW_FINAL, t, f), 'rb').read()).hexdigest() + '\n').encode())
    assert C.VIEW_FINAL == m['view_final_copy'] and h.hexdigest() == m['tree_sha256'], 'view-final snapshot differs from manifest.json'


view_final_ok()

# ---------------------------------------------------------------- the capture of picks and of the valid orders

CAP = dict(log=None, call=-1, valid=None, got=None, sc=None, srel=None)
_drawer = or_q.GuidedRun.drawer


def drawer(self, pg, kind, dec, place=None, prior=None):
    dr = _drawer(self, pg, kind, dec, place, prior)
    dr._pg, dr._kind = pg, kind
    return dr


or_q.GuidedRun.drawer = drawer
_rf = S.Drawer.rel_factors


def rel_factors(self, fr, n, popts, k, scope_types, key, rel, joined, leaf):
    got = _rf(self, fr, n, popts, k, scope_types, key, rel, joined, leaf)
    self._rf_got = list(got)
    return got


S.Drawer.rel_factors = rel_factors
_pc = or_q.GuidedDrawer.pick_complete


def base_of(dr, t):
    name = dr.V.name(t)
    nm = dr.prog_names.get(name, name)
    h, _, sub = nm.partition('.')
    head = dr._pg.written.get(h, h)
    return (head, int(sub) if sub.isdigit() else (sub or None))


def capture(dr, n, opts, weights, rf, o):
    """The row of this atom start. Weights are those the pick drew from (ws * rf)."""
    KIND = dr.fr.KIND
    rfs = rf if rf is not None and len(rf) == len(opts) else [1.0] * len(opts)
    TB = ZB = 0.0
    nD0, g0, gb, D = 0, False, None, []
    for i, t in enumerate(opts):
        w, r = weights[i], rfs[i]
        ws = w / r if r else 0.0
        if KIND[t] == 'relation':
            if ws > 0:
                D.append((base_of(dr, t), ws, r, t == o))
            else:
                nD0 += 1
                g0 = g0 or t == o
        else:
            TB += ws
            ZB += w
            if t == o:
                gb = ['op' if (t == M.NOT or t in M.CMP) else 'lib', ws, r]
    der, bd, nd, nb = feats.drawn_state(dr, dr._pg)
    hk = 'DET' if dr._kind == 'RIGID_DET' else dr._kind
    st = dict(hk=hk, pl=feats.place_of(getattr(dr, 'place', None)), ph=n.phase, sty=sorted({str(x) for x in dr.p_scope}), dd=der, bd=bd)
    sc, srel = CAP['sc'], CAP['srel']
    bases = [b for b, _, _, _ in D]
    facts = feats.option_facts(sc, st, bases, CAP['miss'])
    gold_key = next((srel[b]['key'] for b, _, _, g in D if g and b in srel), None)
    rows = []
    for (b, ws, r, g), f in zip(D, facts):
        pos = bool(g or (gold_key is not None and b in srel and srel[b]['key'] == gold_key))
        rows.append([b[0], b[1], ws, r, int(g), int(pos and any(x[3] for x in D)), f])
    return dict(o=CAP['call'], st=st, ro=bool(dr.rel_off), TB=TB, ZB=ZB, gb=gb, g0=g0, nD0=nD0, D=rows, gf=feats.gate_facts(sc, st, len(D)),
                _k=dr.p_k, _nd=nd, _nb=nb)


def pick_complete(self, n, opts, weights, key, alt=None):
    rf = getattr(self, '_rf_got', None)
    self._rf_got = None
    o, q = _pc(self, n, opts, weights, key, alt)
    if CAP['log'] is not None and n.phase in ('root', 'root2') and o is not None:
        CAP['log'].append(capture(self, n, opts, weights, rf, o))
    return o, q


or_q.GuidedDrawer.pick_complete = pick_complete
_wo = or_q.walk_order


def walk_order(*a, **k):
    CAP['call'] += 1
    return _wo(*a, **k)


or_q.walk_order = walk_order
_so = or_q.O.sum_orders


def sum_orders(form, walk, *a, **k):
    def w2(text):
        res = walk(text)
        res['_call'] = CAP['call']
        return res
    got = _so(form, w2, *a, **k)
    CAP['valid'] = [(r['_call'], r['bits']) for _, r in got['walks'] if r['bits'] is not None]
    CAP['written'] = (got['written'].get('_call'), got['written']['bits'])
    CAP['got'] = got
    return got


or_q.O.sum_orders = sum_orders


def valid_orders(rec):
    """[(call, bits)] of the orders that or_q.walk read: the valid paths, else the written order where walk reads only that."""
    if CAP['valid'] is None:  # the text did not parse as a form: one walk, call 0
        return [(0, rec_bits(rec))] if rec.get('valid_one') else []
    v = CAP['valid']
    if not v and not CAP['got']['orders_exact'] and CAP['written'][1] is not None and rec.get('orders', {}).get('only_written'):
        v = [CAP['written']]
    return v


def rec_bits(rec):
    return rec.get('total')


# ---------------------------------------------------------------- one pair, one task

def walk_pair(task, src, c, sess, d, si, sc, g, kind, target):
    texts = list(sc['texts'])
    srel = C.relations_x(texts, sess, d)
    scope = feats.Scope(texts, srel)
    CAP.update(log=[], call=-1, valid=None, got=None, sc=scope, srel=srel, miss=[0])
    t1 = time.time()
    try:
        rec = or_q.walk(ns['sampler'], task, src, [g, 0], texts, target, sess, d, kind, seconds=20)
    finally:
        picks, CAP['log'] = CAP['log'], None
    ok = not (rec.get('bad') or rec.get('dead') or rec.get('left'))
    rec['valid_one'] = ok
    vo = valid_orders(rec) if ok else []
    if not vo:
        return dict(si=si, g=g, kind=kind, vkind=sc['kind'], target=target, fids=list(sc['fids']), total=rec.get('total'), valid=False, orders=[], rows=[], wall=round(time.time() - t1, 2))
    low = min(b for _, b in vo)
    sh = [2 ** (low - b) for _, b in vo]
    tot = sum(sh)
    wt = {cl: s / tot for (cl, _), s in zip(vo, sh)}
    rows = []
    for p in picks:
        if p['o'] in wt:
            p['w'] = round(wt[p['o']], 6)
            rows.append(p)
    return dict(si=si, g=g, kind=kind, vkind=sc['kind'], target=target, fids=list(sc['fids']), total=rec.get('total'), valid=True, exact=(rec.get('orders') or {}).get('exact'),
                orders=[[cl, round(b, 3), round(wt[cl], 6)] for cl, b in vo], miss=CAP['miss'][0], wall=round(time.time() - t1, 2), rows=rows)


def do_task(task, src):
    assert task not in C.HELD, task
    CTX = C.NCtx if src == 'n600' else C.CCtx
    C.MEMO.clear()
    c = CTX(task)
    sess, d, _ = C.D.session_of(task)
    st = collections.Counter()
    gk = C.gold_read_keys(c, sess, d)
    pairs, per_form = [], collections.Counter()
    for si, sc in enumerate(c.scopes):
        try:
            srel = C.relations(sc['texts'], sess, d)
        except Exception:  # noqa: BLE001  a scope that does not replay on this kit
            st['scope replay error'] += 1
            continue
        skeys = {v['key'] for v in srel.values()}
        for g, kind, keys, own in gk:
            if per_form[g] >= MAX_PAIRS:
                continue
            if keys <= skeys and own and not (own & skeys):
                bt = ns['build_target'](c, g, kind, list(sc['texts']), sess, d)
                st['pair ' + bt['status']] += 1
                if bt['status'] == 'mapped':
                    per_form[g] += 1
                    try:
                        pairs.append(walk_pair(task, src, c, sess, d, si, sc, g, kind, bt['target']))
                    except Exception as e:  # noqa: BLE001
                        st['pair walk error'] += 1
                        pairs.append(dict(si=si, g=g, kind=kind, valid=False, error='%s: %s' % (type(e).__name__, str(e)[:200]), orders=[], rows=[]))
    st['scopes'] = len(c.scopes)
    st['kept'] = len(pairs)
    st['kept valid'] = sum(1 for p in pairs if p['valid'])
    return dict(task=task, src=src, status='ok', stats=dict(st), pairs=pairs)


def task_list():
    if ARGS.only:
        return ARGS.only.split(',')
    if ARGS.src == 'n600':
        ts = sorted(os.listdir(C.N600))
    else:
        ts = sorted({f[:8] for dd in (C.C120, C.C120_MAC) for f in os.listdir(dd) if f.endswith('.events.jsonl')})
    return [t for t in ts if t not in C.HELD and zlib.crc32(t.encode()) % SHARD_N == SHARD_I]


def main():
    tasks = task_list()
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)['task'] for l in open(OUT)}
    todo = [t for t in tasks if t not in done]
    print('%s shard %d/%d: %d tasks, %d done, %d todo -> %s' % (ARGS.src, SHARD_I, SHARD_N, len(tasks), len(tasks) - len(todo), len(todo), OUT), flush=True)
    n = 0
    with open(OUT, 'a') as fh:
        for task in todo:
            if ARGS.budget is not None and time.time() - T0 > ARGS.budget:
                break
            t1 = time.time()
            try:
                row = do_task(task, ARGS.src)
            except Exception as e:  # noqa: BLE001  a task with no node records here, or no view-final gold
                row = dict(task=task, src=ARGS.src, status='error', error='%s: %s' % (type(e).__name__, str(e)[:300]), pairs=[])
            assert row['task'] not in C.HELD
            row['wall'] = round(time.time() - t1, 2)
            row['rss_gib'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 30, 3)
            fh.write(json.dumps(row, default=str) + '\n')
            fh.flush()
            n += 1
            rate = n / (time.time() - T0)
            rem = len(todo) - n
            print('[%d/%d] %s %s pairs %d (valid %d) rows %d %.1fs rss %.2fG | %.1f tasks/min, ETA %s' % (
                len(tasks) - len(todo) + n, len(tasks), task, row['status'], len(row['pairs']), sum(1 for p in row['pairs'] if p['valid']), sum(len(p['rows']) for p in row['pairs']),
                row['wall'], row['rss_gib'], rate * 60, '%.0f s' % (rem / rate) if rem else 'done'), flush=True)
            if row['rss_gib'] > ARGS.rss_gib:
                print('RSS passed %.1f GiB: run it again' % ARGS.rss_gib, flush=True)
                sys.exit(75)
    print('done %d, %d left, %.1fs' % (len(tasks) - len(todo) + n, len(todo) - n, time.time() - T0), flush=True)


main()
