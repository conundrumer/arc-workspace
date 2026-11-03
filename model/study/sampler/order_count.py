#!/usr/bin/env python
"""Counts of the order-free structures of gold queries, and of the two order plans (order.py). Counts only; one line per query in a jsonl file, and a finished query is skipped on a restart.

    order_count.py ramp   OUT.jsonl [--tasks T,T...] [--limit N]       # the ramp (prep.jsonl): each distinct form (by ident) of each program, over the program's earlier forms
    order_count.py train  OUT.jsonl [--tasks T,T...] [--limit N]       # training samples: each query record, over its program without the last line

One task at a time: one session, freed before the next. The record of a query:
    set, task, qid, kind, sets [[kind, items]], upper_orders, gold_hash,
    ordered {status: ok | stuck | hash_mismatch | overflow | unsupported | error, paths, ties, hashes_ok, stuck_set, why},
    unordered {paths, exact, states, per [[kind, items, count]]}, seconds
"""
import argparse
import gc
import json
import os
import sys
import time

import arclog
import live
import live_try
import order

PREP = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/canon-count/prep.jsonl'
TRAIN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/samples/training/skeleton'
KINDS = ('RULE', 'DET', 'INIT', 'RIGID_DET', 'DEMONSTRATED')


def gold_form(sess, scope, text):
    """(decoder after the scope's tokens, [(token id, model flag)] of the form)."""
    ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*scope, text, live.READER_OUT)), sess.settings).decode_stream()
    dec = sess.decoder()
    full = []
    for t, m, p in zip(ids, model, paths):
        if p[0] < len(scope):
            if m:
                dec.step(t)
        elif p[0] == len(scope):
            full.append((int(t), bool(m)))
    return dec, full


def analyze(env, sess, scope, text, limit=20000, seconds=10.0):
    kind = text.split()[0].lstrip('(')
    rec = dict(kind=kind)
    t0 = time.time()
    try:
        base, full = gold_form(sess, scope, text)
        q = order.read_query(env, base, kind, full)
    except Exception as e:  # noqa: BLE001
        rec['ordered'] = dict(status='error', why='read: %s: %s' % (type(e).__name__, str(e)[:200]))
        return rec
    rec['gold_hash'] = str(q.gold_hash)
    if q.unsupported:
        rec['ordered'] = dict(status='unsupported', why=q.unsupported)
        rec['sets'] = []
        return rec
    rec['sets'] = order.sets_of(q)
    rec['upper_orders'] = str(order.upper_orders(q))
    rec['sites'], rec['sites_not_ascending'], rec['sym_cmp'] = order.site_stats(env, q)
    env.deadline = time.monotonic() + seconds
    try:
        res = order.ordered(env, q)
        o = dict(paths=len(res.paths), tie_paths=res.tied, ties=res.ties, tie_sets=sorted(set(env.tie_log)), hashes_ok=sum(h == q.gold_hash for h in res.hashes))
        if res.overflow:
            o['status'] = 'overflow'
        elif res.stuck is not None:
            o.update(status='stuck', stuck_set=res.stuck_at, why=[list(w) for w in res.stuck.why[:4]], written=res.stuck.written, of=res.stuck.total)
        elif o['hashes_ok'] != o['paths']:
            bad = next(i for i, h in enumerate(res.hashes) if h != q.gold_hash)
            o.update(status='hash_mismatch', first=[h == q.gold_hash for h in res.hashes][:4], diff_sites=order.site_diff(env, q, res.paths[bad], res.nms[bad]))
        else:
            o['status'] = 'ok'
            o['gold_first_path'] = res.paths[0] == tuple(q.gold)
        rec['ordered'] = o
    except Exception as e:  # noqa: BLE001
        rec['ordered'] = dict(status='error', why='%s: %s' % (type(e).__name__, str(e)[:200]))
    rec['t_ordered'] = round(time.time() - t0, 2)
    t1 = time.time()
    env.deadline = time.monotonic() + seconds
    try:
        c, exact, n, per = order.unordered_count(env, q, limit)
        rec['unordered'] = dict(paths=None if c is None else str(c), exact=exact, states=n, per=per)
    except Exception as e:  # noqa: BLE001
        rec['unordered'] = dict(paths=None, exact=False, why='%s: %s' % (type(e).__name__, str(e)[:200]))
    rec['t_unordered'] = round(time.time() - t1, 2)
    return rec


def ramp_queries(task):
    for r in (json.loads(l) for l in open(PREP)):
        if r['task'] != task:
            continue
        seen = set()
        for p in r['programs']:
            for i, (ident, line) in enumerate(zip(p['idents'], p['lines'])):
                if ident in seen or line.split()[0].lstrip('(') not in KINDS:
                    continue
                seen.add(ident)
                yield ident, p['lines'][:i], line


def train_queries(task):
    for l in open('%s/%s.jsonl' % (TRAIN, task)):
        r = json.loads(l)
        if r['record'] == 'query' and r['kind'] in KINDS:
            yield r['hash'], r['program'][:-1], r['program'][-1]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('ramp', 'train'))
    ap.add_argument('out')
    ap.add_argument('--tasks', default='')
    ap.add_argument('--limit', type=int, default=0, help='the most queries per task (0: all)')
    ap.add_argument('--seconds', type=float, default=10.0, help='the time of the ordered walk, and of the unordered count, of one query')
    ap.add_argument('--states', type=int, default=20000)
    ap.add_argument('--shard', default='0/1', help='i/n: the tasks at places i, i+n, ... of the task list')
    a = ap.parse_args(argv)
    live_try.P.REPO = os.environ.get('ARC_ROOT', '/Users/davidlu/code/arc-workspace')
    if a.tasks:
        tasks = a.tasks.split(',')
    elif a.mode == 'ramp':
        tasks = [json.loads(l)['task'] for l in open(PREP)]
    else:
        tasks = sorted(f[:-6] for f in os.listdir(TRAIN))
    i, n = map(int, a.shard.split('/'))
    tasks = tasks[i::n]
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            try:
                r = json.loads(l)
                done.add((r['task'], r['qid']))
            except ValueError:
                pass
    queries = ramp_queries if a.mode == 'ramp' else train_queries
    with open(a.out, 'a') as out:
        for task in tasks:
            todo = [(q, s, t) for q, s, t in queries(task) if (task, q) not in done]
            if a.limit:
                todo = todo[:a.limit]
            if not todo:
                continue
            sess, _, _ = live_try.session_of(task)
            env = order.Env(sess)
            for qid, scope, text in todo:
                rec = analyze(env, sess, scope, text, a.states, a.seconds)
                rec.update(set=a.mode, task=task, qid=qid)
                out.write(json.dumps(rec) + '\n')
                out.flush()
            del sess, env
            gc.collect()


if __name__ == '__main__':
    main(sys.argv[1:])
