#!/usr/bin/env python
"""Checks of the two order plans of train_rows.points_of_targets, on the gold queries of the ramp (prep.jsonl). Counts only; one line per group in a jsonl file, and a finished group is
skipped on a restart. A group is the gold queries of one task that have one scope (the lines before them) and one kind; they are walked together, as a trie.

    plan_check.py ordered   OUT.jsonl [--tasks T,T...] [--limit N]
    plan_check.py unordered OUT.jsonl [--tasks T,T...] [--limit N] [--max-states N]
    plan_check.py summary   OUT.jsonl [OUT2.jsonl ...]

One task at a time: one session, freed before the next.

ordered, for each target: its canonical stream (order.canonical_stream) stays in the mask, ends at the end of the query ('done') and gives the gold QueryHash (or the target is
written in its gold order, counted by cause); the records have positive_ids in ids, and next_id in positive_ids; the stream is in the unordered language (order.Unordered).
unordered: the gold stream is in the unordered language (every next token is a continuation, the end is reached); the search's records have positive_ids in ids and no token left the mask;
a state's positives lead on to an end state whose QueryHash is a target's QueryHash (count of the edges that do not; ends with another QueryHash are the engine's known gaps).
"""
import argparse
import collections
import gc
import json
import os
import sys
import time

import numpy as np

import live
import live_try
import order
import train_rows as tr
import writer
from live import KIND_TOK, arclog

PREP = tr.PREP
KINDS = tuple(KIND_TOK)


def groups_of(task, sess, run):
    """[(scope tuple, kind, [streams])] of the ramp task's gold queries."""
    out = collections.OrderedDict()
    for l in open(PREP):
        r = json.loads(l)
        if r['task'] != task:
            continue
        for p in r['programs']:
            lines = p['lines']
            ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*lines, live.READER_OUT)), sess.settings).decode_stream()
            for i in range(len(lines)):
                toks = [int(t) for t, m, q in zip(ids, model, paths) if m and q[0] == i]
                kind = run.V.name(toks[0])
                if kind not in KIND_TOK:
                    continue
                g = out.setdefault((tuple(lines[:i]), kind), [])
                if toks not in g:
                    g.append(toks)
    return [(s, k, g) for (s, k), g in out.items()]


TRAIN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/samples/training/skeleton'


def train_groups_of(task, sess, run, pattern):
    """[(scope tuple, kind, [streams])] of the training queries of the task (order_count.train_queries) whose text matches the regular expression `pattern`."""
    import re
    out = collections.OrderedDict()
    for l in open('%s/%s.jsonl' % (TRAIN, task)):
        r = json.loads(l)
        if r['record'] != 'query' or r['kind'] not in KINDS or not re.search(pattern, r['program'][-1]):
            continue
        scope, text = tuple(r['program'][:-1]), r['program'][-1]
        ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*scope, text, live.READER_OUT)), sess.settings).decode_stream()
        toks = [int(t) for t, m, q in zip(ids, model, paths) if m and q[0] == len(scope)]
        g = out.setdefault((scope, r['kind']), [])
        if toks not in g:
            g.append(toks)
    return [(s, k, g) for (s, k), g in out.items()]


def in_language(env, dec, kind, stream, seconds=10.0):
    """(True if the stream is a path of the unordered language of its own query, why)."""
    q = order.query_of(env, dec, kind, stream)
    if q.unsupported:
        return None, 'unsupported'
    try:
        w = order.Unordered(env, q, seconds=seconds)
    except order.Overflow:
        return None, 'overflow'
    if not w.ok:
        return False, 'no order'
    cfgs = w.start()
    for n, t in enumerate(stream[1:] if stream[0] == KIND_TOK[kind] else stream):
        if t not in w.nexts(cfgs):
            return False, 'token %d not a continuation' % n
        cfgs = w.step(cfgs, t)
    return w.done(cfgs), 'not at the end' if not w.done(cfgs) else ''


def walk_ends(run, pg, dec, kind, stream):
    """(in the mask all the way, finished at the end, QueryHash) of a stream stepped through the writer."""
    pg.new = []
    pt = writer.start_point(run, pg, run.open_form(pg, dec, kind), kind)
    for t in (stream[1:] if stream[0] == KIND_TOK[kind] else stream):
        if pt.track.where == 'done' or t not in pt.ids_:
            return False, False, None
        pt = writer.step_point(pt, t)
    return True, pt.track.where == 'done', writer.query_hash(pt.dec)


def check_group(run, env, scope, kind, streams, mode, max_states, seconds):
    c = collections.Counter()
    stats = collections.Counter()
    dec, pg = run.scope(scope)
    t0 = time.time()
    c['targets'] = len(streams)
    if mode == 'ordered':
        for s in streams:
            s2, o, why = order.canonical_stream(env, dec, kind, s)
            c['order:' + o + (':' + why.split(':')[0] if why else '')] += 1
            inmask, finished, h = walk_ends(run, pg, dec, kind, s2)
            q = order.query_of(env, dec, kind, s)
            c['stream in the mask'] += inmask
            c['stream finished'] += finished
            c['hash is gold'] += h == q.gold_hash
            if o == 'canonical':
                c['canonical: in mask, finished, gold hash'] += inmask and finished and h == q.gold_hash
                c['canonical = given order'] += s2 == (s[1:] if s[0] == KIND_TOK[kind] else s)
            ok, w2 = in_language(env, dec, kind, [KIND_TOK[kind]] + s2, seconds)
            c['stream in the unordered language'] += bool(ok)
            c['stream in the unordered language: not known (' + w2 + ')'] += ok is None
    else:
        for s in streams:
            ok, why = in_language(env, dec, kind, s, seconds)
            c['gold in the unordered language'] += bool(ok)
            if not ok:
                c['gold not in the language: ' + why] += 1
    graph = {} if mode == 'unordered' else None
    uses = writer.feature_names()
    it = (tr.points_of_targets(run, scope, kind, streams, uses, plan='ordered', stats=stats) if mode == 'ordered'
          else tr.points_of_unordered(run, scope, kind, streams, uses, max_states=max_states, seconds=seconds, stats=stats, graph=graph))
    for i, rec in it:
        if 'error' in rec:
            c['error: ' + type(rec['error']).__name__ + ': ' + str(rec['error'])[:60]] += 1
            continue
        if rec['left_mask']:
            c['left the mask'] += 1
            continue
        c['records'] += 1
        pos = rec['positive_ids']
        c['positive_ids not in ids'] += int(not np.isin(pos, rec['ids']).all())
        c['positive_ids not int32 or not sorted'] += int(pos.dtype != np.int32 or bool((np.diff(pos) <= 0).any()))
        c['no positive'] += int(len(pos) == 0)
        c['next_id not in positive_ids'] += int(rec['next_id'] is not None and rec['next_id'] not in pos)
        c['next_id none'] += int(rec['next_id'] is None)
    if graph is not None:
        hashes = {h for g in graph.values() for h in g['gold']}
        good, state = {}, {}

        def reach(k):
            if k in good:
                return good[k]
            g = graph[k]
            good[k] = bool(g['edges'] == [] and g['hash'] in hashes)
            good[k] = good[k] or any(reach(k2) for _, k2 in g['edges'] if k2 in graph)
            return good[k]
        sys.setrecursionlimit(20000)
        for k in graph:
            reach(k)
        ends = [k for k, g in graph.items() if not g['edges'] and g['hash'] is not None]
        c['graph states'] = len(graph)
        c['graph end states'] = len(ends)
        c['end states with a target QueryHash'] = sum(graph[k]['hash'] in hashes for k in ends)
        c['states that reach no target QueryHash'] = sum(not good[k] for k in graph)
        c['edges to a state that reaches no target QueryHash'] = sum(1 for g in graph.values() for _, k2 in g['edges'] if k2 in graph and not good[k2])
        c['edges'] = sum(len(g['edges']) for g in graph.values())
    for k, v in stats.items():
        c['stat ' + k] = v
    c['seconds'] = round(time.time() - t0, 2)
    return c


def summary(paths):
    tot = collections.Counter()
    n = 0
    for p in paths:
        for l in open(p):
            r = json.loads(l)
            n += 1
            tot.update(r['counts'])
    print('groups', n)
    for k, v in sorted(tot.items()):
        print('  %-70s %s' % (k, v))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('ordered', 'unordered', 'summary'))
    ap.add_argument('out', nargs='+')
    ap.add_argument('--tasks', default='')
    ap.add_argument('--limit', type=int, default=0, help='the most groups per task (0: all)')
    ap.add_argument('--train', default='', help='a regular expression: use the training queries (skeleton) whose text matches it, e.g. "\\(IF |\\(ONE" (default: the ramp)')
    ap.add_argument('--max-states', type=int, default=20000)
    ap.add_argument('--seconds', type=float, default=10.0, help='the time of the automaton of one query')
    a = ap.parse_args(argv)
    if a.mode == 'summary':
        return summary(a.out)
    live_try.P.REPO = os.environ.get('ARC_ROOT', '/Users/davidlu/code/arc-workspace')
    tasks = a.tasks.split(',') if a.tasks else sorted(f[:-6] for f in os.listdir(TRAIN)) if a.train else [json.loads(l)['task'] for l in open(PREP)]
    out = a.out[0]
    done = set()
    if os.path.exists(out):
        for l in open(out):
            try:
                r = json.loads(l)
                done.add((r['task'], r['group']))
            except ValueError:
                pass
    smp = live.Sampler(os.environ['SAMPLER_CODE'] + '/../../../models-current', steers=())
    with open(out, 'a') as f:
        for task in tasks:
            sess, d, _ = live_try.session_of(task)
            run = live.Run(smp.pri, sess, 0, time.monotonic() + 3600, d, live.Limits())
            env = tr.order_env(run)
            groups = train_groups_of(task, sess, run, a.train) if a.train else groups_of(task, sess, run)
            if a.limit:
                groups = groups[:a.limit]
            for gi, (scope, kind, streams) in enumerate(groups):
                if (task, gi) in done:
                    continue
                try:
                    counts = check_group(run, env, scope, kind, streams, a.mode, a.max_states, a.seconds)
                except Exception as e:  # noqa: BLE001
                    counts = collections.Counter({'group error: %s: %s' % (type(e).__name__, str(e)[:80]): 1})
                f.write(json.dumps(dict(task=task, group=gi, kind=kind, scope=len(scope), counts=counts)) + '\n')
                f.flush()
            del sess, run, env
            gc.collect()


if __name__ == '__main__':
    main(sys.argv[1:])
