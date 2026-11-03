"""Reads the proposal's rate of the head shape at gold's forms of one task.

  ib_held.py --task T --pass 1|2|3 [--forms g,g] [--max-draws N] [--out DIR]
  ib_held.py --list-pass3

Pass 1: up to 12 Ident-only forms (strata taken in turn) and up to 3 plain control forms. Pass 2: the other Ident-only forms. Pass 3: the in-sample
control, on corpus stems (T is a stem). The models are models-tk for the 37 and pass 3, models-tkf for the ramp. Appends one JSON line per form to
DIR/T.jsonl (default R/held) as soon as the form is done, and a first line {"rec": "task", ...} that lists every form of the task. A rerun skips the
forms done. Gold's rates come from the corpus rows, which must be complete, except with --max-draws (the smoke), which takes the rows that exist
and marks its rows gold_provisional.
"""
import argparse
import collections
import json
import math
import os
import random
import sys
import time

import ib_lib as L

CPU_CAP = 120.0
CAP = 256
RSS_EXIT_GIB = 3.0
BATCH = 32


def corpus_state():
    dirs = [L.R + '/corpus']
    rows, tasks, done = L.load_corpus(dirs)
    complete = len(tasks) == len(L.corpus_stems()) and set(tasks) == set(L.corpus_stems())
    return rows, tasks, complete


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task')
    ap.add_argument('--pass', dest='pas', type=int)
    ap.add_argument('--forms')
    ap.add_argument('--max-draws', type=int)
    ap.add_argument('--out')
    ap.add_argument('--list-pass3', action='store_true')
    a = ap.parse_args()
    L.check_pins()
    rows, ctasks, complete = corpus_state()
    if a.list_pass3:
        if not complete:
            sys.exit('corpus rows incomplete: %d of %d stems' % (len(ctasks), len(L.corpus_stems())))
        print('\n'.join(sorted({s for s, _ in L.pick_pass3(rows)})))
        return 0
    if not a.task or a.pas not in (1, 2, 3):
        sys.exit(__doc__)
    provisional = False
    if not complete:
        if not a.max_draws:
            sys.exit('corpus rows incomplete: %d of %d stems done, so %d are left. Run ib_corpus_all.sh first (gold\'s rates need them).' % (
                len(ctasks), len(L.corpus_stems()), len(L.corpus_stems()) - len(ctasks)))
        rows, ctasks, _ = L.load_corpus([L.R + '/corpus', L.R + '/corpus-smoke'])
        provisional = True
    gold = L.Gold(rows)
    live, _, _ = L.setup()
    task = a.task
    st = 'corpus' if a.pas == 3 else L.set_of(task)
    if st == 'corpus' and a.pas != 3:
        sys.exit('%s is not a held task' % task)
    forms = L.forms_of(L.corpus_gold(task) if st == 'corpus' else L.held_gold()[task])
    sampler = live.Sampler(L.MODELS[st])
    sess, d = L.session_of(L.task_path(task, st))
    t_start = time.time()
    cts, err = L.replay(sampler, d, sess, forms)
    info, reads = L.analyze(forms, cts)
    by = {x['i']: x for x in info}
    got = [x['i'] for x in info if x['ident_only']]
    if st == 'corpus':
        want = sorted(r['g'] for r in rows if r['stem'] == task and r['ident_only'])
    else:
        want = L.ident_list()[task]['ident_only']
    print('%s (%s): replay of %d forms in %.1fs, ident-only %s' % (task, st, len(forms), time.time() - t_start, got), flush=True)
    if err or len(info) != len(forms) or got != want:
        sys.exit('C1 FAIL on %s: replay error %s, %d of %d analyzed, ident-only forms %s, pinned %s' % (task, err, len(info), len(forms), got, want))
    out_dir = a.out or (L.R + '/held')
    os.makedirs(out_dir, exist_ok=True)
    out = '%s/%s.jsonl' % (out_dir, task)
    done, has_head = set(), False
    if os.path.exists(out):
        for line in open(out):
            try:
                x = json.loads(line)
            except ValueError:
                continue
            if x.get('rec') == 'task':
                has_head = True
            elif 'g' in x:
                done.add(x['g'])
    ident1, plain1 = L.pick_pass1(task, info)
    if a.forms:
        picks = [(g, 'ident' if by[g]['ident_only'] else 'plain') for g in (int(x) for x in a.forms.split(','))]
    elif a.pas == 1:
        picks = [(g, 'ident') for g in ident1] + [(g, 'plain') for g in plain1]
    elif a.pas == 2:
        picks = [(g, 'ident') for g in got if g not in ident1]
    else:
        picks = [(g, 'ident') for s, g in L.pick_pass3(rows) if s == task]
    todo = [p for p in picks if p[0] not in done]
    fh = open(out, 'a')
    if not has_head:
        L.append_line(fh, dict(rec='task', task=task, set=st, forms=len(forms), ident_only=got, all=[[x['i'], x['kind'], x['shape'], x['link'], x['ident_only']] for x in info],
                               pass1=dict(ident=ident1, plain=plain1)))
    if not todo:
        print('%d done' % len(picks), flush=True)
        return 0
    print('%d forms to do, %d done' % (len(todo), len(picks) - len(todo)), flush=True)
    t0 = time.time()
    cap = a.max_draws or CAP
    for k, (g, role) in enumerate(todo):
        row = one_form(live, sampler, sess, d, task, st, a.pas, role, by[g], by, forms, reads, gold, cap, provisional)
        L.append_line(fh, row)
        rate, rest = L.eta(k + 1, len(todo), t0)
        print('[%d/%d] g=%d %s %s %s: n=%d h=%d p_kind=%.3f p_gold=%.4f p_prop=%.5f L=%s flag=%s cpu=%.0fs %.2f draws/s | %.0f s a form, ETA %.0f s, rss %.2f GiB' % (
            k + 1, len(todo), g, role, row['kind'], row['shape'], row['n'], row['h'], row['p_kind'], row['p_gold'], row['p_prop'],
            'inf' if row['L'] is None else '%.2f' % row['L'], row['flag'], row['cpu'], row['draws_per_s'], rate, rest, L.rss_gib()), flush=True)
        if L.rss_gib() > RSS_EXIT_GIB and k + 1 < len(todo):
            print('rss past %.1f GiB: exit for a restart (the forms done stay done)' % RSS_EXIT_GIB, flush=True)
            return 75
    return 0


def one_form(live, sampler, sess, d, task, st, pas, role, x, by, forms, reads, gold, cap, provisional):
    """The row of form x: draws in batches of 32, each batch over a new valid order of the scope, until the stopping rule ends."""
    g, kind, scope = x['i'], x['kind'], x['scope']
    p_gold, level, cell_n = gold.rate(x['shape'], x['facts'])
    p_gold_kind = gold.rate_kind(kind, x['facts'])
    want = L.within(x['shape'])
    ident_heads = {by[j]['head'] for j in scope if by[j]['holds']}
    row = dict(task=task, set=st, **{'pass': pas}, role=role, g=g, kind=kind, shape=x['shape'], facts=x['facts'], link=x['link'], nscope=x['nscope'],
               p_gold=p_gold, p_gold_kind=p_gold_kind, level=level, cell_n=cell_n, gold_provisional=provisional)
    cpu0, wall0 = time.process_time(), time.time()
    if sampler.run is None:  # the Run that Sampler.clause makes at its first call
        sampler.run = live.Run(sampler.pri, sess, 0, time.monotonic() + 20, d, live.Limits())
    c0 = dict(sampler.run.c)
    order0 = L.valid_order(scope, reads, random.Random('%s %d %d' % (task, g, 0)))
    p_kind, admitted = L.p_kind_of(sampler, [forms[j] for j in order0], kind) if kind in live.KIND_TOK else (0.0, [])
    n = h = none = reads_ident = key_ident = batches = 0
    shapes = collections.Counter()
    flag = None
    if p_kind == 0:
        flag = 'under'  # gold's kind is outside KIND_TOK or not admitted at the scope: the proposal cannot draw it
    while flag is None:
        order = order0 if batches == 0 else L.valid_order(scope, reads, random.Random('%s %d %d' % (task, g, batches)))
        texts = [forms[j] for j in order]
        seeds = [L.draw_seed(task, g, i) for i in range(n, min(n + BATCH, cap))]
        res = L.draw_batch(sampler, sess, d, texts, kind, seeds, ident_heads, cpu_stop=lambda: time.process_time() - cpu0 >= CPU_CAP)
        batches += 1
        for r in res:
            n += 1
            if r is None:
                none += 1
                continue
            shapes[L.within(r[0])] += 1
            h += L.within(r[0]) == want
            reads_ident += r[1]
            key_ident += r[0].endswith('|key-ident')
        lo, hi = (v * p_kind for v in L.jeffreys(h, n))
        cpu = time.process_time() - cpu0
        if hi < .1 * p_gold:
            flag = 'under'
        elif lo > .1 * p_gold:
            flag = 'not under'
        elif n >= cap or cpu >= CPU_CAP or len(res) < len(seeds):
            flag = 'unresolved'
    p_prop = p_kind * (h + .5) / (n + 1) if n else 0.0
    row.update(p_kind=p_kind, admitted=admitted, kind_outside=kind not in live.KIND_TOK, n=n, h=h, none=none, flag=flag, p_prop=p_prop, point_under=p_prop < .1 * p_gold,
               L=(math.log2(p_gold) - math.log2(p_prop)) if p_prop > 0 else None,
               L_kind=(math.log2(p_gold_kind) - math.log2(p_kind)) if p_kind > 0 else None,
               cpu=round(time.process_time() - cpu0, 2), wall=round(time.time() - wall0, 2), draws_per_s=round(n / max(time.time() - wall0, 1e-9), 3), orders=batches,
               shapes=dict(shapes), reads_ident=reads_ident, key_ident=key_ident,
               drops={k: v - c0.get(k, 0) for k, v in sampler.run.c.items() if k.startswith(('drop', 'error')) and v - c0.get(k, 0)})
    return row


if __name__ == '__main__':
    sys.exit(main())
