"""The proposal's rate of gold's outcome (head shape and read pattern) at the steps of the walk of one held task.

  tw_held.py --task T --pass 1|2 [--steps t,t] [--max-draws N] [--out DIR]

Pass 1: up to 12 steps, the strata (place, f's mode as EXTEND, BACKTRACK or JUMP) taken in turn. Pass 2: the other steps. Steps of kind OTHER are not
picked. The models are models-kr for the 37 and models-krf for the ramp. Reads R/shapes/T.json, walks seed 0 and draws Sampler.clause with the forms present
as the scope, in batches of 32, until 8 draws hit gold's (I, K) and pattern, n = 128 or 45 CPU s. Appends one JSON line per step to DIR/T.jsonl (default
R/held) as soon as the step is done; a rerun skips the steps done. Exit 75 when RSS passes 3 GiB after a step (the driver starts it again).
"""
import argparse
import collections
import json
import os
import random
import sys
import time

import tw_lib as T

L = T.L
CPU_CAP = 45.0
CAP = 128
BATCH = 32
HITS = 8
RSS_EXIT_GIB = 3.0


def pick_pass1(task, recs):
    groups = collections.defaultdict(list)
    for r in recs:
        if r['kind_f'] != 'OTHER':
            groups[(r['place'], T.mode_class(r['mode']))].append(r['t'])
    keys = sorted(groups)
    rng = random.Random('%s pass1' % task)
    for k in keys:
        rng.shuffle(groups[k])
    out = []
    while len(out) < 12 and any(groups.values()):
        for k in keys:
            if groups[k] and len(out) < 12:
                out.append(groups[k].pop())
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', required=True)
    ap.add_argument('--pass', dest='pas', type=int, required=True)
    ap.add_argument('--steps')
    ap.add_argument('--max-draws', type=int)
    ap.add_argument('--out')
    a = ap.parse_args()
    task = a.task
    st = L.set_of(task)
    if st == 'corpus':
        sys.exit('%s is not a held task' % task)
    rows = T.held_shape_rows(task)
    if rows is None:
        sys.exit('no R/shapes/%s.json: run tw_shapes.py first' % task)
    live = T.setup()
    D = T.dago()
    forms = T.gold_forms(task)
    dag = D.ProgramDag(forms)
    gof = {T.head_of(f): g for g, f in enumerate(forms)}
    holds = {k: bool(rows[g][2]) for k, g in gof.items()}
    recs = T.walk(forms, 0, task=task, dag=dag)
    ctx = [(set(r['_S']), list(r['_chain'])) for r in recs]
    order = [r['key_f'] for r in recs]
    T.annotate(dag, recs, holds)
    p1 = pick_pass1(task, recs)
    if a.steps:
        picks = [int(x) for x in a.steps.split(',')]
    elif a.pas == 1:
        picks = p1
    else:
        picks = [r['t'] for r in recs if r['kind_f'] != 'OTHER' and r['t'] not in p1]
    out_dir = a.out or (T.R + '/held')
    os.makedirs(out_dir, exist_ok=True)
    out = '%s/%s.jsonl' % (out_dir, task)
    done = {x['t'] for x in T.read_lines(out) if 't' in x}
    todo = [t for t in picks if t not in done]
    if not todo:
        print('%d done' % len(picks), flush=True)
        return 0
    print('%s (%s): %d steps to do, %d done' % (task, st, len(todo), len(picks) - len(todo)), flush=True)
    sampler = live.Sampler(L.MODELS[st])
    sess, d = L.session_of(L.task_path(task, st))
    fh = open(out, 'a')
    t0 = time.time()
    cap = a.max_draws or CAP
    for k, t in enumerate(todo):
        r = recs[t]
        S, chain = ctx[t]
        row = one_step(live, sampler, sess, d, task, st, a.pas, r, S, chain, order[:t], dag, rows[gof[r['key_f']]], gof[r['key_f']], cap)
        T.append_line(fh, row)
        el = time.time() - t0
        print('[%d/%d] t=%d %s %s %s %s: n=%d h_joint=%d h_shape=%d h_pattern=%d p_kind=%.3f cpu=%.1fs %.3f s a draw | %.1f s a step, ETA %.0f s, rss %.2f GiB' % (
            k + 1, len(todo), t, row['kind'], row['place'], row['mode'], row['shape'], row['n'], row['h_joint'], row['h_shape'], row['h_pattern'], row['p_kind'], row['cpu'],
            row['cpu'] / max(row['n'], 1), el / (k + 1), el / (k + 1) * (len(todo) - k - 1), L.rss_gib()), flush=True)
        if L.rss_gib() > RSS_EXIT_GIB and k + 1 < len(todo):
            print('rss past %.1f GiB: exit for a restart (the steps done stay done)' % RSS_EXIT_GIB, flush=True)
            return 75
    return 0


def one_step(live, sampler, sess, d, task, st, pas, r, S, chain, placed, dag, shape_row, g, cap):
    f, kind, t = r['key_f'], r['kind_f'], r['t']
    shape = shape_row[1]
    want_ik, want_pat = L.within(shape), r['pattern']
    row = dict(task=task, set=st, **{'pass': pas}, t=t, key_f=f, g=g, kind=kind, shape=shape, pattern=want_pat, place=r['place'], mode=r['mode'], prev=r['facts']['prev'], nS=len(S))
    cpu0, wall0 = time.process_time(), time.time()
    if sampler.run is None:  # the Run that Sampler.clause makes at its first call
        sampler.run = live.Run(sampler.pri, sess, 0, time.monotonic() + 20, d, live.Limits())
    c0 = dict(sampler.run.c)
    L.gc.collect()
    texts0 = [dag.lines[k] for k in placed]
    p_kind, admitted = L.p_kind_of(sampler, texts0, kind) if kind in live.KIND_TOK else (0.0, [])
    n = hj = hs = hp = none = notabs = batches = 0
    outcomes = collections.Counter()
    while p_kind > 0:
        order = placed if batches == 0 else dag.random_order(batches, keys=S)
        texts = [dag.lines[k] for k in order]
        L.gc.collect()  # live.Sampler sets gc thresholds so high that finished Runs keep their decoders, and later replays and draws come back empty
        start, early = n, False
        for i in range(start, min(start + BATCH, cap)):
            if time.process_time() - cpu0 >= CPU_CAP:
                early = True
                break
            c = sampler.clause(sess, T.draw_seed(task, f, i), time.monotonic() + 20, d, texts, kind)
            n += 1
            if c is None:
                none += 1
                continue
            ik = L.within(L.shape_of(kind, c.text, c.tables))
            pat = T.pattern_of_text(c.text, S, chain, dag)
            notabs += ik.startswith('none')
            outcomes['%s %s' % (ik, pat)] += 1
            hs += ik == want_ik
            hp += pat == want_pat
            hj += ik == want_ik and pat == want_pat
        batches += 1
        if hj >= HITS or n >= cap or early or time.process_time() - cpu0 >= CPU_CAP:
            break
    row.update(p_kind=p_kind, admitted=admitted, kind_outside=kind not in live.KIND_TOK, n=n, h_joint=hj, h_shape=hs, h_pattern=hp, none=none, notabs=notabs, batches=batches,
               cpu=round(time.process_time() - cpu0, 2), wall=round(time.time() - wall0, 2), outcomes=dict(outcomes),
               drops={k: v - c0.get(k, 0) for k, v in sampler.run.c.items() if k.startswith(('drop', 'error')) and v - c0.get(k, 0)})
    return row


if __name__ == '__main__':
    sys.exit(main())
