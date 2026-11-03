#!/usr/bin/env python
"""INIT 77 split (item 15): the rows of the 77 rewritten INIT forms, walked in valid orders.

  features_dagc_env.sh 1 features_dagc_init77.py build                    init77-programs.jsonl: each rewritten program in the engine's normal form, and its target
  features_dagc_env.sh 1 features_dagc_init77.py points                   points-init77.jsonl: scope rule `cut`, seeds 0 and 1, on the rewritten program's DAG (no engine)
  features_dagc_env.sh 1 features_dagc_init77.py orders [--seconds S]     orders-init77-shard0of1.jsonl (item 3, K = 8: 16 orders per form) and no-order-init77-shard0of1.tsv
  features_dagc_env.sh 1 features_dagc_init77.py walk --steers off|live [--shard K/N] [--seconds S] [--limit N]    walks/init77-STEERS-KofN.jsonl.zst
  features_dagc_env.sh 1 features_dagc_init77.py check [--seconds S]      the checks of the item, appended to init77-check.txt
  features_dagc_env.sh 1 features_dagc_init77.py written [--limit N]      the walk of each target in its written order on all earlier forms, against the totals of rows.jsonl of the source record

The set is form-set.jsonl of features-init-residual-bits-split-74forms: 77 forms, each with its rewrite (`replace`). The program is built as init_residual_bits.py of that record builds it. Priors and steers are those of the census
(census_env.sh of form-anatomy-top-tenth): SEARCH_MODELS sampler-priors-refit-heldout-8a5ffec60 and the steers of live.STEERS under `live`; the sampler code and the engine are the pin. A point is (task, form of the set): a task
can hold several rewrites, so a row carries `rkey` (the set's key, `<task> <form>`) and `line_id` is the target's index in its rewritten program. The walker's pick rows and `form` lines are used as they stand (features_dagc_walk.pick_rows),
with `rkey` added; `parts` and `total` stay as the walk gives them, and a read takes means over orders.
"""
import argparse
import collections
import glob
import io
import json
import os
import random
import sys
import time
from pathlib import Path

import zstandard

import features_dagc_lib as L

SRC = L.SCRATCH / 'records/features-init-residual-bits-split-74forms'
CENSUS_MODELS = L.DS / 'sampler/sampler-worker/sampler-priors-refit-heldout-8a5ffec60'
K = L.ORDER_PARTS['init77']
OUT = L.OUT_DIR
PROGRAMS = OUT / 'init77-programs.jsonl'
POINTS = OUT / 'points-init77.jsonl'


def setup(models=CENSUS_MODELS, steer_cover=None):
    """The pinned engine and sampler code, with the census priors (the walker's Env asks for its own models; this replaces that ask). steer_cover: a value of STEER_COVER in place of the pin's `init,branch`, for the `written` check only; 'unset' removes it."""
    orig = L.setup_engine

    def fn(corpus, _m):
        orig(corpus, models)
        if steer_cover == 'unset':
            os.environ.pop('STEER_COVER', None)
        elif steer_cover is not None:
            os.environ['STEER_COVER'] = steer_cover
    L.setup_engine = fn
    return orig


def rows_of(path):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            if line.endswith('\n') and line.strip():
                yield json.loads(line)


# ---- build ----

def build():
    L.setup_engine(L.HELD_CORPUS, CENSUS_MODELS)
    L.check_engine_loaded()
    import arclog
    form_set = [json.loads(x) for x in open(SRC / 'form-set.jsonl')]
    done = {r['key'] for r in rows_of(PROGRAMS)}
    n = bad = 0
    with open(PROGRAMS, 'a') as out:
        for r in form_set:
            if r['key'] in done:
                continue
            ls = list(r['lines'])
            for i, new in sorted(r['replace'], key=lambda x: -x[0]):
                ls[i:i + 1] = new
            sess = arclog.Session(arclog.Task.from_json(open('%s/data/tasks/%s.json' % (L.ROOT, r['task'])).read(), arclog.World.Closed), arclog.DecodeSettings(table_work_cap=1 << 20))
            ids, model, _ = arclog.StudyProgram.from_sexp('\n'.join(ls), sess.settings).decode_stream()
            norm = arclog.StudyProgram.from_stream(sess, [int(x) for x in ids], [int(bool(x)) for x in model]).sexp()
            nl = [x for x in norm.splitlines() if x.strip()]
            i = r['index']
            same = nl[i] == r['target']
            bad += not same
            out.write(json.dumps(dict(rkey=r['key'], task=r['task'], form=r['form'], held=r['held'], group=r['group'], index=i, census_bits=r['census_bits'], target=nl[i], target_matches_set=same, lines=nl)) + '\n')
            out.flush()
            n += 1
    print('built %d programs, %d whose normal form at the index differs from the set\'s target' % (n, bad))


def programs():
    return [r for r in rows_of(PROGRAMS)]


# ---- points ----

def points():
    import features_dag_order as D
    out, bad = [], []
    for r in programs():
        prog = D.ProgramDag(r['lines'])
        text = r['lines'][r['index']]
        key = D.parse(text)[1]
        for s in (0, 1):
            order = prog.random_order(s, prog.non_descendants(key) | {key})
            keys = order[:order.index(key)]
            sc = prog.texts(keys)
            sid = D.short(''.join(sorted(prog.content[k] for k in keys)), 16)
            ok = (set(keys) <= prog.non_descendants(key)) and not (set(keys) & (prog.descendants(key) | {key})) and all(prog.parent_ids[k] & set(keys) <= set(keys[:keys.index(k)]) for k in keys)
            ok = ok and prog.ancestors(key) <= set(keys)
            if not ok:
                bad.append((r['rkey'], s))
            out.append(dict(task=r['task'], rkey=r['rkey'], form=prog.content[key], key=key, kind=L.kind_of(text), line_id=r['index'], scope=sc, scope_rule='cut', scope_id=sid, target_seed=s, arm='', stratum='', held=r['held'], line=len(out)))
    with open(POINTS, 'w') as f:
        for p in out:
            f.write(json.dumps(p) + '\n')
    print('init77 points: %d (%d forms, seeds 0 and 1); scopes that fail topological, reads-all-parents or no-descendant: %s' % (len(out), len(programs()), bad[:5]))


# ---- orders ----

def orders(a):
    import features_dag_order as D
    import features_dagc_modes as M
    import features_dagc_orders as O
    L.setup_engine(L.HELD_CORPUS, CENSUS_MODELS)
    L.check_engine_loaded()
    import live
    import live_try
    arclog = live.arclog
    out_path = OUT / 'orders-init77-shard0of1.jsonl'
    no_path = OUT / 'no-order-init77-shard0of1.tsv'
    done = {r['rkey'] for r in rows_of(out_path)}
    if no_path.exists():
        done |= {x.split('\t')[0] for x in open(no_path) if x.strip()}
    todo = [r for r in programs() if r['rkey'] not in done]
    print('init77 orders: %d programs, %d to do, K %d' % (len(programs()), len(todo), K), flush=True)
    t0, tally = time.time(), collections.Counter()
    code = L.code_hash()
    with open(out_path, 'a') as f, open(no_path, 'a') as nof:
        for w, r in enumerate(todo, 1):
            if a.seconds and time.time() - t0 > a.seconds:
                print('stopped: budget spent', flush=True)
                break
            t1 = time.time()
            lines, i = r['lines'], r['index']
            sess = live_try.session_of(r['task'])[0]
            text = lines[i]
            dag = D.FormDag(text)
            dag.n_orders = dag.count_orders()
            prog = D.ProgramDag(lines)
            key = D.parse(text)[1]
            parents = prog.ancestors(key)
            scopes: dict = {}
            accepted_texts, tried, refused = [], 0, collections.Counter()

            def check(s, order):
                nonlocal tried
                if s not in scopes:
                    scopes[s] = prog.texts(prog.random_order(s, parents))
                target = dag.render(order)
                tried += 1
                try:
                    arclog.StudyProgram.from_sexp('\n'.join((*scopes[s], target, live.READER_OUT)), sess.settings).decode_stream()
                    return target
                except Exception as e:  # noqa: BLE001
                    refused[O.refusal(e)] += 1
                    return None
            for k, (seed, order) in enumerate(O.draws(D, dag, O.DRAWS)):
                got = check(k if seed is None else seed, order)
                if got is not None and got not in accepted_texts:
                    accepted_texts.append(got)
            n_acc = len(accepted_texts)
            law = 'uniform' if dag.n_orders is not None else 'cap'
            chosen = list(accepted_texts)
            random.Random('pick|%s' % prog.content[key]).shuffle(chosen)
            chosen = chosen[:2 * K]
            if not chosen:
                law, rng, seen = 'step', random.Random('step|%s' % prog.content[key]), set()
                for k in range(8 * 2 * K):
                    order = O.step_order(D, M, dag, rng)
                    if order is None:
                        continue
                    got = check(k, order)
                    if got is not None and got not in seen:
                        seen.add(got)
                        chosen.append(got)
                    if len(chosen) >= 2 * K:
                        break
            sec = round(time.time() - t1, 2)
            if not chosen:
                nof.write('\t'.join(map(str, (r['rkey'], r['index'], 'INIT', prog.content[key], dag.n_orders, tried, json.dumps(dict(refused.most_common(3)))))) + '\n')
                nof.flush()
                tally['no order'] += 1
            else:
                f.write(json.dumps(dict(rkey=r['rkey'], task=r['task'], line_id=i, key=key, form=prog.content[key], kind='INIT', n_orders=dag.n_orders, tried=tried, accepted=n_acc, refused=dict(refused.most_common()), law=law, k=K, orders=chosen, seconds=sec, code=code)) + '\n')
                f.flush()
                tally[law] += 1
            if w % 10 == 0 or w == len(todo):
                el = time.time() - t0
                print('[%d/%d %ds %.2f forms/s eta %ds] %s' % (w, len(todo), el, w / el, el / w * (len(todo) - w), dict(tally)), flush=True)
    print('done: %s' % dict(tally), flush=True)


# ---- walk ----

def held_frames(path):
    got = {}
    if os.path.exists(path):
        try:
            with open(path, 'rb') as f:
                for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
                    if line.startswith('{"rec": "form"'):
                        d = json.loads(line)
                        got[d['point'], d['order_idx']] = d['ok']
        except zstandard.ZstdError:
            pass
    return got


def walk(a):
    setup(steer_cover=a.steer_cover)
    import features_dagc_walk as W
    import features_dag_order as D
    shard, shards = map(int, a.shard.split('/'))
    pts = [json.loads(x) for x in open(POINTS)]
    table = {r['rkey']: r for r in rows_of(OUT / 'orders-init77-shard0of1.jsonl')}
    tasks = sorted({p['task'] for p in pts})
    keep = {t for j, t in enumerate(tasks) if j % shards == shard}
    todo = [p for p in pts if p['task'] in keep and p['rkey'] in table]
    path = os.path.join(a.out, 'init77-%s-%dof%d.jsonl.zst' % (a.steers, shard, shards))
    os.makedirs(a.out, exist_ok=True)
    held = held_frames(path)
    want = sum(max(0, min(K, len(table[p['rkey']]['orders'])) - sum(1 for i in range(len(table[p['rkey']]['orders'])) if held.get((p['line'], i)))) for p in todo)
    print('init77 %s: %d points in shard %d/%d (%d forms have no order), %d walks held, %d walks to do' % (a.steers, len(todo), shard, shards, len({p['rkey'] for p in pts} - set(table)), len(held), want), flush=True)
    if a.dry:
        return
    env = W.Env('held', a.steers, False, '')
    cz = zstandard.ZstdCompressor(level=6)
    t0, walked, drops, msgs = time.time(), 0, 0, collections.Counter()
    with open(path, 'ab') as out:
        for p in todo:
            if (a.seconds and time.time() - t0 > a.seconds) or (a.limit and walked >= a.limit):
                print('stopped: budget spent', flush=True)
                break
            r = table[p['rkey']]
            n_ok = sum(1 for i in range(len(r['orders'])) if held.get((p['line'], i)))
            for i, text in enumerate(r['orders']):
                if n_ok >= K:
                    break
                if (p['line'], i) in held:
                    continue
                if a.seconds and time.time() - t0 > a.seconds:
                    break
                q, picks, aligned, heads_ok, sec, dag, leaves, extra, ccpu = env.walk(p['task'], 'INIT', p['scope'], text, p['scope_id'])
                why = q.get('error') or (q.get('bad') or [''])[0] if (q.get('error') or q.get('bad')) else q.get('dead') or ('left %d' % q['left'] if q.get('left') else None) or (None if aligned else 'misaligned') or (None if heads_ok is not False else 'heads differ')
                ok = why is None
                order_id = D.short('|'.join(leaves), 12)
                rows = W.pick_rows(env, p, 'init77', a.steers, text, order_id, p['scope_id'], q, picks, dag, leaves) if ok else []
                for x in rows:
                    x['rkey'] = p['rkey']
                msg = ' '.join(str(why).split()[:6]) if why else None
                form = dict(rec='form', part='init77', steers=a.steers, point=p['line'], rkey=p['rkey'], order_idx=i, task=p['task'], line_id=p['line_id'], kind='INIT', form=p['form'], order_id=order_id, ok=ok, drop=msg, total=q.get('total'), parts=q.get('parts'),
                            seconds=sec, picks=len(picks), aligned=aligned, heads_ok=heads_ok, steer_cover=os.environ.get('STEER_COVER'), nscope=len(p['scope']), scope_id=p['scope_id'], target_seed=p['target_seed'], law=r['law'])
                out.write(cz.compress(('\n'.join(json.dumps(x) for x in [*rows, form]) + '\n').encode()))
                out.flush()
                held[p['line'], i] = ok
                walked += 1
                if ok:
                    n_ok += 1
                else:
                    drops += 1
                    msgs[msg] += 1
                if walked % 25 == 0:
                    el = time.time() - t0
                    print('[%d/%d %.0fs %.2f walks/s eta %.0fs] drops %d %s' % (walked, want, el, walked / el, el / walked * max(0, want - walked), drops, dict(msgs.most_common(3))), flush=True)
    el = time.time() - t0
    print('done: %d walks in %.0f s (%.2f walks/s), %d dropped %s' % (walked, el, walked / max(el, 1e-9), drops, dict(msgs)), flush=True)


# ---- checks ----

def frames(path):
    with open(path, 'rb') as f:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
            if line.strip():
                yield json.loads(line)


def check(a):
    """Parts sum to the total on each walk; the 77 forms each have order rows or stand in no-order; each form has walks (as far as they exist); the shared pick keys of the off walks agree."""
    lines = []
    progs = programs()
    pts = [json.loads(x) for x in open(POINTS)] if POINTS.exists() else []
    table = {r['rkey'] for r in rows_of(OUT / 'orders-init77-shard0of1.jsonl')}
    nopath = OUT / 'no-order-init77-shard0of1.tsv'
    noord = {x.split('\t')[0] for x in open(nopath) if x.strip()} if nopath.exists() else set()
    keys = {r['rkey'] for r in progs}
    lines.append('programs %d; with an order row %d; in no-order %d; neither %s; target equals the set\'s target on %d' % (len(keys), len(table), len(noord), sorted(keys - table - noord)[:5], sum(r['target_matches_set'] for r in progs)))
    lines.append('points %d (%d forms x seeds 0 and 1)' % (len(pts), len({p['rkey'] for p in pts})))
    for steers in ('off', 'live'):
        files = sorted(glob.glob(os.path.join(a.out, 'init77-%s-*.jsonl.zst' % steers)))
        forms, bad_sum, walked_keys, drops = 0, [], set(), collections.Counter()
        seen = collections.defaultdict(dict)
        for p in files:
            try:
                for r in frames(p):
                    if r['rec'] == 'form':
                        forms += r['ok']
                        walked_keys.add(r['rkey'])
                        if r['ok']:
                            s = sum(r['parts'].values())
                            if abs(s - r['total']) > 0.05 + 0.001 * len(r['parts']):
                                bad_sum.append((r['rkey'], r['order_idx'], round(s, 3), r['total']))
                        else:
                            drops[r['drop']] += 1
                    elif steers == 'off':
                        k = (r['rkey'], r['scope_id'], r['phase'], r['atom'], tuple(r['downset']))
                        tot = sum(o[2] for o in r['opts']) or 1.0
                        seen[k][r['order_id']] = sorted((o[0], round(o[2] / tot, 6)) for o in r['opts'])
            except zstandard.ZstdError:
                pass
        multi = {k: v for k, v in seen.items() if len(v) > 1}
        diff = sum(1 for v in multi.values() if len({tuple(x) for x in v.values()}) > 1)
        lines.append('steers %s: %d good walks over %d forms (of %d with orders); parts differ from total by more than the rounding on %d %s; drops %s%s' % (
            steers, forms, len(walked_keys), len(table), len(bad_sum), bad_sum[:3], dict(drops.most_common(3)),
            ('; pick keys %d, reached by 2+ orders %d, with options or weights differing at 6 places %d' % (len(seen), len(multi), diff)) if steers == 'off' else ''))
    print('\n'.join(lines))
    with open(OUT / 'init77-check.txt', 'a') as f:
        f.write(time.strftime('%H:%M:%S ') + '\n'.join(lines) + '\n')


def written(a):
    """The walk of each target in its written order on all earlier forms, with the census's priors and steers, against the totals of rows.jsonl: the setup walks as the census did."""
    setup(steer_cover=a.steer_cover or 'unset')  # the census ran with STEER_COVER unset; with the pin's `init,branch` the totals differ
    import features_dagc_walk as W
    env = W.Env('held', 'live', False, '')
    census = {r['key']: r for r in rows_of(SRC / 'rows.jsonl')}
    t0, n, same, diffs = time.time(), 0, 0, []
    for r in programs():
        if a.limit and n >= a.limit or (a.seconds and time.time() - t0 > a.seconds):
            break
        c = census.get(r['rkey'])
        if c is None or c.get('total') is None:
            continue
        i = r['index']
        q, picks, aligned, heads_ok, sec, dag, leaves, extra, ccpu = env.walk(r['task'], 'INIT', r['lines'][:i], r['lines'][i], 'written')
        n += 1
        same += abs((q.get('total') or -1) - c['total']) < 0.02
        if abs((q.get('total') or -1) - c['total']) >= 0.02:
            diffs.append((r['rkey'], q.get('total'), c['total'], q.get('dead') or q.get('error') or q.get('bad')))
    line = 'written order, scope all earlier forms, steers live, census priors: %d forms, %d equal the totals of rows.jsonl to .02 bits; first differences %s (%.0f s)' % (n, same, diffs[:5], time.time() - t0)
    print(line)
    with open(OUT / 'init77-check.txt', 'a') as f:
        f.write(time.strftime('%H:%M:%S ') + line + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['build', 'points', 'orders', 'walk', 'check', 'written'])
    ap.add_argument('--steers', default='off', choices=['off', 'live'])
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--seconds', type=float, default=None)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--out', default=str(OUT / 'walks'))
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--steer-cover', default=None, help="STEER_COVER in place of the pin's `init,branch`; `unset` removes it. `walk` default: the pin. `written` default: unset, the census's setting")
    a = ap.parse_args()
    if a.cmd == 'build':
        build()
    elif a.cmd == 'points':
        points()
    elif a.cmd == 'orders':
        orders(a)
    elif a.cmd == 'walk':
        walk(a)
    elif a.cmd == 'check':
        check(a)
    else:
        written(a)


if __name__ == '__main__':
    main()
