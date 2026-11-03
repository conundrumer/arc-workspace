#!/usr/bin/env python
"""Checks of the writing-point vector (writer.Features.vectors, train_rows.points_of_targets(vectors=True)) on the gold queries of ramp tasks (prep.jsonl). A check of an in-progress
feature: it prints one line per check (PASS or FAIL, with counts), gates nothing, and exits 1 where a check fails.

    vector_check.py TASK [TASK ...] [--plan ordered|unordered] [--groups N] [--only shape,nan,unchanged,engine,legal,serve] [--engine-points N] [--serve-tree MODEL]

The checks run under one writer plan (--plan), in a process whose writer plan it is (WRITER_PLAN). With no --plan, the script runs itself once for each plan, with --plan and
WRITER_PLAN set and WRITER_TREE unset, prints the lines of each run under the plan's name, and exits 1 where a run fails.

The checks, each over the first N groups (plan_check.groups_of) of each task (--only names the ones to run):
  shape      every record of points_of_targets(plan=--plan, vectors=True) has vectors of shape (len(ids), width), float32, and names, the same tuple at every
             point and for every task; the names are distinct, and each starts with one of the six block names and a colon, in block order.
  nan        at each writing point of gold's walk: the token, place and task:ex_input / task:ex_output columns have no NaN; the pq columns repeat over the ids; pq:body is all NaN
             where writer.current_body gives none and has no NaN where it gives one; the state columns are not all NaN; cand: a row with cand:defined 0 has NaN in every other cand
             column, a row with 1 has no NaN in cand:succ (the cand:delta columns may be NaN as point_tables says), and cand:succ of a body successor is the writer's assignment vector (to a relative 1e-5: the export sorts the assignments by the hex TableHash, the summaries by the integer one, which changes the order of the float32 sums).
             task:input has no NaN where arclog has base_tables (else it is NaN, counted, not checked); cand:match: a row with cand:defined 1 has no NaN in cand:match:used and
             cand:match:none, cand:match:body is NaN where writer.current_body gives none and has no NaN where it gives one, and every count is 0 or more.
  engine     (--engine-points N: the first N writing points with two ids or more of each task) the vectors of writer.Features with the engine's successor_tables (writer.SUCCESSOR
             'engine') and with the oracle ('oracle') are equal, row by row, on the ids that both define; the ids that only the engine defines are counted by the engine's kind (the
             oracle gives no table where a step leaves the point as it was); an id that only the oracle defines fails.
  legal      at each writing point of gold's walk, gold's next token is in writer.point_ids (the engine's mask with the legality rules and the plan's rules), which the rules must not
             remove.
Under `ordered`, gold's walk of nan, unchanged, engine and legal is its canonical stream (order.canonical_stream), as the training rows walk it; a gold query that the order rule
gives no canonical stream for is walked as given, and is counted.
  serve      (--serve-tree MODEL, a tree over the writing-point vector) at each writing point of gold's walk, the vector of the serving Run (a search.SearchRun with WRITER on and
             the tree as its distribution, as the pool search makes it) equals the vector of the Run that train_rows makes rows on, over
             the same ids, with NaN in the same places; a difference is counted by block.
  unchanged  at each writing point with a current body: the successor (writer.successor_tables) of each admitted NOT, OR, IF, ALL and ONE that the engine gives a table for
             has the TableHashes and TableVectors of the current body table.
"""
import argparse
import collections
import os
import subprocess
import sys
import time

import numpy as np

import live
import live_try
import order
import plan_check
import train_rows as tr
import writer
from live import KIND_TOK, M, arclog

BLOCKS = tuple(writer.VECTOR_BLOCKS)


def cols(names, block, prefix=''):
    return [i for i, n in enumerate(names) if n.startswith(block + ':' + prefix)]


def key_of(rows):
    return sorted((str(r.hash), r.features.tobytes()) for r in rows)


def check_engine(pt, ids, ve, names, seen, bad):
    """Counts, for the vector ve of Features(pt, ids) with the engine's successor_tables, the ids defined by both sources, the ones that only the engine defines (by the engine's
    kind), the ones that only the oracle defines, and the rows of the ids defined by both that differ from the oracle's."""
    if writer.SUCCESSOR != 'engine':
        bad['engine: the wheel has no successor_tables'] += 1
        return
    hows = [s.how for s in writer.successor_tables(pt, ids)]
    writer.drop_successors(pt)
    writer.SUCCESSOR = 'oracle'
    try:
        vo = writer.Features(pt, ids).vectors()
    finally:
        writer.SUCCESSOR = 'engine'
    if 'cand:defined' not in names:  # the cand block is not in the vector: the engine and the oracle give it alone
        return
    d = names.index('cand:defined')
    de, do = ve[:, d] == 1, vo[:, d] == 1
    both = de & do
    same = ((ve == vo) | (np.isnan(ve) & np.isnan(vo))).all(1)
    seen['engine: points'] += 1
    seen['engine: ids defined by both'] += int(both.sum())
    seen['engine: ids with equal rows'] += int((both & same).sum())
    for j in np.flatnonzero(de & ~do):
        seen['engine: ids that only the engine defines, %s' % hows[j]] += 1
    bad['engine: ids that only the oracle defines'] += int((do & ~de).sum())
    bad['engine: rows that differ'] += int((both & ~same).sum())
    writer.drop_successors(pt)


def walk(run, scope, kind, stream):
    """The writing points of one gold stream, as the writer steps it: (point, next token)."""
    dec, pg = run.scope(scope)
    pg.new = []
    pt = writer.start_point(run, pg, run.open_form(pg, dec, kind), kind)
    for t in (stream[1:] if stream[0] == KIND_TOK[kind] else stream):
        if pt.track.where == 'done' or t not in pt.ids_:
            return
        yield pt, t
        pt = writer.step_point(pt, t)


def each_plan(argv):
    """Runs this script once for each writer plan, each in a process of that plan; exits 1 where a run fails."""
    fails = 0
    for plan in tr.PLANS:
        env = dict(os.environ, WRITER_PLAN=plan)
        env.pop('WRITER_TREE', None)
        print('plan %s' % plan, flush=True)
        fails += subprocess.run([sys.executable, os.path.abspath(__file__), *argv, '--plan', plan], env=env).returncode != 0
    sys.exit(1 if fails else 0)


def plan_stream(run, scope, kind, stream, plan, seen):
    """The stream of gold's walk under plan: under `ordered` the canonical stream where the order rule gives one, else the stream as given."""
    if plan != 'ordered':
        return stream
    dec0, _ = run.scope(scope)
    got, o, why = order.canonical_stream(tr.order_env(run), dec0, kind, stream, tr.ORDER_SECONDS)
    seen['legal: streams walked as given, with no canonical stream (%s)' % why.split(':')[0] if o != 'canonical' else 'legal: streams walked in canonical order'] += 1
    return got


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('tasks', nargs='+')
    ap.add_argument('--plan', choices=tr.PLANS, help='the writer plan of the checks, which must be the plan of the process (default: one run for each plan)')
    ap.add_argument('--groups', type=int, default=4)
    ap.add_argument('--only', default='shape,nan,unchanged,engine,legal')
    ap.add_argument('--engine-points', type=int, default=25)
    ap.add_argument('--serve-tree', default='')
    a = ap.parse_args(argv)
    if a.plan is None:
        each_plan(argv)
    only = set(a.only.split(','))
    live_try.P.REPO = os.environ.get('ARC_ROOT', '/Users/davidlu/code/arc-workspace')
    smp = live.Sampler(os.environ['SAMPLER_CODE'] + '/../../../models-current', steers=())
    bad = collections.Counter()
    seen = collections.Counter()
    all_names = []
    t0 = time.time()
    serving = None
    if 'serve' in only:
        import search
        import tree_dist
        serving = tree_dist.load(a.serve_tree) if a.serve_tree else None
        if serving is None or not serving.vector:
            bad['serve: no tree over the writing-point vector (--serve-tree)'] += 1
            serving = None
        else:
            search.WRITER, search.DISTRIBUTION = True, serving
    for task in a.tasks:
        sess, d, _ = live_try.session_of(task)
        run = live.Run(smp.pri, sess, 0, time.monotonic() + 3600, d, live.Limits())
        core = writer.core_of(run)
        writer.keep_state_tables(run)
        names = writer.vector_names(run)
        all_names.append(names)
        if len(set(names)) != len(names):
            bad['shape: names repeat'] += 1
        order = [BLOCKS.index(n.split(':')[0]) if n.split(':')[0] in BLOCKS else -1 for n in names]
        if -1 in order or order != sorted(order):
            bad['shape: names are not in block order'] += 1
        unchanged_ids = {M.NOT, M.OR, core.IF, core.ALL, core.ONE}
        groups = plan_check.groups_of(task, sess, run)[:a.groups]
        if serving is not None:
            srv = search.SearchRun(smp.pri, sess, time.monotonic() + 3600, d, live.Limits())
            for scope, kind, streams in groups:
                for stream in streams:
                    for (pt, t), (ps, _) in zip(walk(run, scope, kind, stream), walk(srv, scope, kind, stream)):
                        ids = writer.point_ids(pt)
                        if len(ids) == 0:
                            continue
                        seen['serve: points'] += 1
                        bad['serve: the two Runs admit other ids'] += int(not np.array_equal(ids, writer.point_ids(ps)))
                        vt, vs = writer.Features(pt, ids).vectors(), writer.Features(ps, ids).vectors()
                        differ = ~((vt == vs) | (np.isnan(vt) & np.isnan(vs))).all(0)
                        for block in sorted({names[i].split(':')[0] for i in np.flatnonzero(differ)}):
                            bad['serve: %s differs' % block] += 1
                        writer.drop_successors(pt)
                        writer.drop_successors(ps)
            del srv
        uses = writer.feature_names()
        for plan in (a.plan,) if 'shape' in only else ():
            for scope, kind, streams in groups:
                for i, rec in tr.points_of_targets(run, scope, kind, streams, uses, plan=plan, vectors=True):
                    if 'error' in rec or rec['left_mask']:
                        continue
                    seen['shape: records ' + plan] += 1
                    v = rec['vectors']
                    if v.shape != (len(rec['ids']), len(names)) or v.dtype != np.float32 or rec['names'] != names:
                        bad['shape: a record has the wrong vectors or names (' + plan + ')'] += 1
        engine_left = a.engine_points
        for scope, kind, streams in groups if only - {'shape', 'serve'} else ():
            for stream in streams:
                for pt, t in walk(run, scope, kind, plan_stream(run, scope, kind, stream, a.plan, seen)):
                    ids = writer.point_ids(pt)
                    if 'legal' in only:
                        seen['legal: points'] += 1
                        seen['legal: points where the rules removed ids'] += int(len(ids) != len(pt.ids_))
                        bad['legal: gold next token removed by the rules'] += int(t not in ids)
                    if len(ids) < 2 or not only & {'nan', 'unchanged', 'engine'}:
                        continue
                    v = writer.Features(pt, ids).vectors()
                    if 'engine' in only and engine_left > 0:
                        engine_left -= 1
                        check_engine(pt, ids, v, names, seen, bad)
                    if 'nan' not in only and 'unchanged' not in only:
                        continue
                    seen['nan: points'] += 1
                    for block in ('token', 'place'):
                        bad['nan: %s has NaN' % block] += int(np.isnan(v[:, cols(names, block)]).any())
                    for b in ('ex_input', 'ex_output'):
                        bad['nan: task:%s has NaN' % b] += int(np.isnan(v[:, cols(names, 'task', b + ':')]).any())
                    if hasattr(arclog, 'base_tables'):
                        bad['nan: task:input has NaN'] += int(np.isnan(v[:, cols(names, 'task', 'input:')]).any())
                    else:
                        seen['nan: task:input all NaN'] += int(np.isnan(v[:, cols(names, 'task', 'input:')]).all())
                    pq = v[:, cols(names, 'pq')]
                    bad['nan: pq differs between ids'] += int(not np.array_equal(pq[0], pq[-1], equal_nan=True) or not np.array_equal(pq, np.broadcast_to(pq[0], pq.shape), equal_nan=True))
                    body = v[0, cols(names, 'pq', 'body:')]
                    cur = writer.current_body(pt)
                    seen['nan: points with a current body'] += int(cur is not None)
                    bad['nan: pq:body NaN where a body exists, or not NaN where none'] += int(np.isnan(body).any() if cur is not None else not np.isnan(body).all())
                    bad['nan: state is all NaN (queries not kept)'] += int(np.isnan(v[0, cols(names, 'state')]).all()) if cols(names, 'state') else 0
                    if 'cand:defined' in names:  # the cand block is in the vector
                        defined = v[:, names.index('cand:defined')]
                        rest = v[:, [i for i in cols(names, 'cand') if names[i] != 'cand:defined']]
                        succ = v[:, cols(names, 'cand', 'succ:')]
                        seen['nan: ids with a successor'] += int(defined.sum())
                        seen['nan: ids with none'] += int((defined == 0).sum())
                        bad['nan: cand:defined is not 0 or 1'] += int(((defined != 0) & (defined != 1)).any())
                        bad['nan: cand has a value where none is defined'] += int((~np.isnan(rest[defined == 0])).any())
                        bad['nan: cand:succ has NaN where it is defined'] += int(np.isnan(succ[defined == 1]).any())
                        match = v[:, cols(names, 'cand', 'match:')]
                        mb, mu = match[:, :3], match[:, 3:]
                        bad['nan: cand:match:used or none has NaN where defined'] += int(np.isnan(mu[defined == 1]).any())
                        bad['nan: cand:match:body NaN does not follow current_body'] += int(np.isnan(mb[defined == 1]).any() if cur is not None else not np.isnan(mb).all())
                        bad['nan: cand:match has a negative count'] += int((match[~np.isnan(match)] < 0).any())
                        bad['nan: cand:succ is not the writer assignment vector'] += int(any(
                            not np.allclose(succ[j], writer._av_of(s.table.rows), rtol=1e-5, atol=0, equal_nan=True) for j, s in enumerate(writer.successor_tables(pt, ids)) if s.defined and s.kind == 'body'))
                    if cur is not None:
                        want = key_of(cur.table.rows)
                        for i, s in zip(ids.tolist(), writer.successor_tables(pt, ids)):
                            if i in unchanged_ids and s.defined:
                                seen['unchanged: tokens checked'] += 1
                                bad['unchanged: successor differs from the current body'] += int(key_of(s.table.rows) != want)
                    writer.drop_successors(pt)
        del sess, run
    for n in all_names[1:]:
        bad['shape: names differ between tasks'] += int(n != all_names[0])
    fails = 0
    for group in [g for g in ('shape', 'nan', 'unchanged', 'engine', 'legal', 'serve') if g in only]:
        keys = sorted(k for k in set(seen) | set(bad) if k.startswith(group + ':'))
        wrong = {k: bad[k] for k in keys if bad[k]}
        fails += bool(wrong)
        print('%-10s %s  %s' % (group, 'FAIL' if wrong else 'PASS', '; '.join('%s %d' % (k.split(': ', 1)[1], seen.get(k, bad[k])) for k in keys if k in seen) + ('   failed: %s' % wrong if wrong else '')))
    print('width %d, %d s' % (len(all_names[0]), time.time() - t0))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
