#!/usr/bin/env python
"""One held test case by two-stage search: a first search over the context gives prefixes as clauses, the best K by a rule stay as forms, and a second search over the context with
each kept form must read it. Same match as tp_end.py: a clause that ended with the relation table of the target.

  <runtime python> search_two_stage_job.py TASK CASE POINT --rule score|chance|order|plain|oracle [--budget 60] [--first 20] [--keep 16] [--out DIR]

Run from a kit's top folder, with tp_end.py there, SEARCH_GOLDS and SEARCH_MODELS set, SEARCH_FREE_STOP=1 and, for --rule score, SEARCH_PREFIX_SCORE. --rule oracle reads gold and keeps only gold's prefixes: it bounds any keep rule. --rule plain with --first equal to --budget and no SEARCH_FREE_STOP is the base, with the same key. The score here ranks prefixes for
keeping and does not move the search's order: SEARCH_PREFIX_BETA stays 0. CPU runs from after the session and the Sampler load. Fields as tp_end.py, with hit_stage (1 or 2), kept,
kept_rank (the rank of the prefix the match read, 0 is the best), stage1_cpu, stage1_clauses (distinct prefix tables), gold_prefixes (tables of gold's walk) and
gold_prefix_ranks (the rank of each that stage 1 reached).
"""
import argparse
import json
import math
import os
import re
import sys
import time
import types

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'model', 'study', 'sampler'))
import live  # noqa: E402
import live_try  # noqa: E402
import or_q  # noqa: E402
import search  # noqa: E402
import search_gold as G  # noqa: E402
import superdag as D  # noqa: E402
import superdag_search as SS  # noqa: E402
import tp_end as T  # noqa: E402

st = T.st
HEAD = re.compile(r'^\((\w+) (\S+)')
FORM = 9000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task')
    ap.add_argument('case')
    ap.add_argument('point')
    ap.add_argument('--rule', choices=['score', 'chance', 'order', 'plain', 'oracle'], required=True)
    ap.add_argument('--budget', type=float, default=60)
    ap.add_argument('--first', type=float, default=20)
    ap.add_argument('--keep', type=int, default=16)
    ap.add_argument('--per-atoms', type=int, default=0, help='keep this many at each of 1 to 4 atoms, in place of --keep')
    ap.add_argument('--out', default='out/twostage')
    ap.add_argument('--tag', default='', help='added to the arm folder')
    ap.add_argument('--stage2', choices=['read', 'resume'], default='read', help='read: a clause must read the kept form. resume: the search goes on below the kept prefix, with no read')
    ap.add_argument('--keep-key', action='store_true', help='rank by keep_key(score, atoms), a z value within an atom count')
    a = ap.parse_args()
    task, case, point = a.task, a.case, json.loads(a.point)
    path = T.result_path(a.out, a.rule + ('-peratoms' if a.per_atoms else '') + ('-' + a.tag if a.tag else '') + ('-keepkey' if a.keep_key else '') + ('-resume' if a.stage2 == 'resume' else ''), task, case, point)
    if os.path.exists(path):
        return
    SS.load_rule()
    D.table_key = SS.table_key
    T.install(live, D)
    SS.patch_search_run()
    d, lines = G.gold_of(task, case, point)
    scope, target = lines[:point[0]], lines[point[0]]
    kind = target.split()[0].lstrip('(')
    sampler = live.Sampler(G.MODELS)
    sess, task_json, _ = live_try.session_of(task)
    SS.POOL[:] = [types.SimpleNamespace(task=task_json)]
    res = dict(task=task, case=case, point=point, rule=a.rule, target=target, forms=len(scope), budget=a.budget, first=a.first, keep=a.keep, hit=False, hit_stage=None, kept=0)
    search.SearchRun.trace = []
    q, forced = T.forced_walk(live, or_q, search, sampler, sess, task_json, scope, target, kind)
    gold_tables, search.SearchRun.trace = search.SearchRun.trace, None
    res.update(bits=q['total'], bad=q['bad'], dead=q['dead'], left=q['left'])
    if q['bad'] or q['dead'] or q['left']:
        res['error'] = 'the walk is not valid'
        T.atomic_write(path, res)
        return
    gold, types_ = T.gold_replay(D, live, sampler, sess, task_json, scope, target)
    if not gold:
        res['error'] = 'the replay of the target gave no relation table'
        T.atomic_write(path, res)
        return
    prefix_gold = set()
    for tb in gold_tables:
        try:
            prefix_gold.add(SS.prefix_key(tb))
        except D.M.Fail:
            pass
    st.gold, st.types = set(gold), types_
    st.n.clear()
    c0 = time.process_time()
    cpu = lambda: time.process_time() - c0  # noqa: E731
    st.clock, st.mode = cpu, 'search'
    runs = [0]
    st.tried = lambda: runs[0]
    best, score_cpu, key_cpu = {}, 0.0, 0.0

    def stage1(c):
        nonlocal score_cpu, key_cpu
        tb = getattr(c, 'prefix_tb', None)
        if tb is None or c.prefix_text is None or kind != 'RULE':
            return
        had = 'full' in tb
        t0 = time.process_time()
        try:
            D.S.full(tb)  # one parse for the key and the score
            key = SS.prefix_key(tb)
        except D.M.Fail:
            return
        finally:
            key_cpu += time.process_time() - t0
        if a.rule == 'score':
            t0 = time.process_time()
            value = float(SS.PREFIX_SCORE.score(tb, dict(run=se.run, task=task_json, text=c.prefix_text, atoms=len(c.prefix_text), logp=c.logq)))
            if a.keep_key:
                value = float(SS.PREFIX_SCORE.keep_key(value, len(c.prefix_text)))
            score_cpu += time.process_time() - t0
        elif a.rule == 'order':
            value = -len(best)
        elif a.rule == 'oracle':  # reads gold: only gold's own prefixes are kept, longest first
            value = len(c.prefix_text) if key in prefix_gold else -1
        else:
            value = c.logq
        if not had:
            tb.pop('full', None)  # the memo keeps tb
        if key not in best or (a.rule != 'order' and value > best[key][0]):
            best[key] = value, c.text, len(c.prefix_text), c.go_on

    done = base = 0
    se = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, kind, eager=True)
    while cpu() < a.first and st.hit_at is None:
        for c in se:
            stage1(c)
            if cpu() >= a.first or st.hit_at is not None:
                break
        base = se.stats['runs']
        runs[0] = base
        if se.exhausted or not se.heap:
            break
        se = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, kind, eager=True)
    res.update(stage1_cpu=round(cpu(), 2), stage1_clauses=len(best), stage1_runs=base)
    stage = 1 if st.hit_at is not None else 2
    kept = sorted(best.values(), key=lambda v: -v[0])
    if a.rule == 'oracle':
        kept = [v for v in kept if v[0] >= 0][:a.keep]
    elif a.per_atoms:
        kept = [v for n in (1, 2, 3, 4) for v in [x for x in kept if x[2] == n][:a.per_atoms]]
    else:
        kept = kept[:a.keep]
    res['kept'] = len(kept)
    res['kept_atoms'] = sorted(v[2] for v in kept)
    order = sorted(best, key=lambda k: -best[k][0])
    res.update(gold_prefixes=len(prefix_gold), gold_prefix_ranks=sorted(order.index(k) for k in prefix_gold if k in best))
    res['score_cpu'] = round(score_cpu, 2)
    res['score_failed'] = SS.PREFIX_SCORE.failed[0] if SS.PREFIX_SCORE is not None else None
    res['key_cpu'] = round(key_cpu, 2)
    hit_rank = None
    if stage == 2 and kept and a.stage2 == 'resume':
        run = se.run
        searches = []
        for v in kept:
            if v[3] is not None:
                s = search.Search(run, scope, kind, None, True)
                s.heap = [(0.0, 0, v[3], None, None)]
                searches.append(s)
        res['resumed'] = len(searches)
        while searches and cpu() < a.budget and st.hit_at is None:
            for r, s in enumerate(list(searches)):
                s.deadline = time.monotonic() + 1.0
                before = s.stats['runs']
                st.tried = lambda: base + done + s.stats['runs'] - before
                for _ in s:
                    if st.hit_at is not None or cpu() >= a.budget:
                        break
                done += s.stats['runs'] - before
                if st.hit_at is not None:
                    hit_rank = r
                    break
                if not s.heap:
                    searches.remove(s)
                if cpu() >= a.budget:
                    break
    elif stage == 2 and kept:
        forms = []
        for r, (_, text, _, _) in enumerate(kept):
            m = HEAD.match(text)
            forms.append(text[:m.start(2)] + '&f%d' % (FORM + r) + text[m.end(2):])
        live_slots = list(range(len(forms)))
        while live_slots and cpu() < a.budget and st.hit_at is None:
            for r in list(live_slots):
                texts = (*scope, forms[r])
                s = sampler.search(sess, 0, time.monotonic() + 1.0, task_json, texts, 'RULE', eager=True)
                s.run.picks = frozenset([str(FORM + r)])
                before = s.stats['runs']
                st.tried = lambda: base + done + s.stats['runs'] - before
                try:
                    for _ in s:
                        if st.hit_at is not None or cpu() >= a.budget:
                            break
                except D.M.Fail:
                    pass
                done += s.stats['runs'] - before
                if st.hit_at is not None:
                    hit_rank = r
                    break
                if s.exhausted or not s.heap:
                    live_slots.remove(r)
                if cpu() >= a.budget:
                    break
    st.mode = None
    res.update(hit=st.hit_at is not None, hit_cpu=None if st.hit_at is None else round(st.hit_at, 3), hit_tried=st.hit_tried, hit_text=st.hit_text, hit_stage=stage if st.hit_at is not None else None,
               kept_rank=hit_rank, cpu=round(cpu(), 2), tried=base + done)
    T.atomic_write(path, res)
    print(task, case, point, a.rule, 'hit', res['hit'], res['hit_cpu'], 'stage', res['hit_stage'], 'rank', hit_rank, 'kept', res['kept'], 'of', res['stage1_clauses'], 'tried', res['tried'], flush=True)


if __name__ == '__main__':
    main()
