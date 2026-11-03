#!/usr/bin/env python
"""One job of the search-against-sampling comparison on a held-out clause, with the extensional match (table) and the syntactic match (text) in one run.

  <runtime python> tp_held.py TASK CASE POINT ARM [--budget 60] [--out DIR]       (ARM is `search` or `draw`)

Run from a kit's top folder, with SEARCH_GOLDS=$PWD/points-eval.json SEARCH_MODELS=models-held as for search_gold.py. The arms and the CPU clock are
search_gold.job's: the clock starts after the session and the Sampler load, so each arm pays for the replay of the scope, and a proposal is a run in
the search arm and a call of Sampler.clause in the draw arm.

Gold's table is the table of gold's whole body, which or_q's teacher-forced walk gives as the last table that Run.table makes. The hook is on Run.table
(live.py), the call that SearchRun.table memoizes, so a prefix is checked wherever the walk takes its table: after every atom, a one-atom prefix that
takes the `single` stop and a prefix that ends in an OR included. A table is checked once in a run of the search, where its decoder is new. A table counts
once the walk has it, even if the walk then dies or the prefix is dropped. The key is step4/tp.py's table_key of S.full(table), and keys compare in
this process. A key is computed in full only for a table whose sorted column types are gold's, since the first part of the key is those types.

The job runs until the text match (the clause that ends has gold's clause_key) or the budget. Fields:
  hit, hit_cpu, hit_tried   the first prefix with gold's table key: that it matched, CPU s on the job's clock, proposals so far (the one it was in included)
  text_hit, text_cpu, text_tried   the same at the clause that ends with gold's clause_key
  A match is recorded when it comes, so it may lie past the budget by one chunk of the search or one draw; a report counts a match within T when its CPU is at most T.
  tried, clauses, cpu, tables (tables the walk made), bits/bad/dead/left (the teacher-forced walk: q.total, q.bad, q.dead, tokens of gold left), forms (of the scope).
A walk with no valid gold table (bad, dead, tokens left, no table, or a last table that isn't the table at the body's end) writes `error` and runs no search.
"""
import argparse
import collections
import json
import os
import resource
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLER = os.environ.get('SAMPLER_DIR') or os.path.join(HERE, 'model', 'study', 'sampler')
sys.path.insert(0, SAMPLER)


def result_path(out, arm, task, case, point):
    return os.path.join(out, arm, '%s.%s.%s.json' % (task, case.replace(' ', '_').replace('$', ''), '-'.join(map(str, point))))


def table_key(tb):
    """superdag.table_key's merge key of a parsed table with rows (step4/tp.py's)."""
    spans, at = [], 0
    for w in tb['widths']:
        spans.append((at, at + w))
        at += w
    entries = [(tuple(ex), rows) for ex, _, rows, _, _ in tb['entries']]
    cols = []
    for t, (a, b) in zip(tb['types'], spans):
        cols.append((str(t), hash(tuple(sorted((ex, hash(frozenset(r[a:b] for r in rows))) for ex, rows in entries))), a, b))
    order = sorted(cols)
    per = collections.defaultdict(set)
    for ex, rows in entries:
        per[ex].add(hash(frozenset(tuple(v for _, _, a, b in order for v in r[a:b]) for r in rows)))
    body = tuple(sorted((ex, tuple(sorted(s))) for ex, s in per.items()))
    return tuple(c[0] for c in order), hash(body)


class State:
    mode = None  # 'walk' while or_q's walk runs, 'search' while an arm runs
    last = end = None  # walk: (key, decoder) of the last table; the decoder that the clause's END follows
    gold = None  # the key of gold's table
    none = None  # why the last table call gave no table
    precheck = True  # a table whose sorted column types differ from gold's cannot have its key
    hit_at = hit_tried = None
    clock = tried = None
    n = collections.Counter()


st = State


def install(live):
    S = live.S
    orig_table, orig_end = live.Run.table, live.Run.end

    def table(self, fr, dec, pg):
        got = orig_table(self, fr, dec, pg)
        tb = got[0]
        if tb is None:
            st.none = str(got[1])[:80]
            return got
        if st.mode is None:
            return got
        st.n['tables'] += 1
        if st.mode == 'walk':
            key = table_key(S.full(tb))
            if key[0] != tuple(sorted(str(t) for t in tb['types'])):
                st.precheck = False
            st.last = key, dec
        elif st.hit_at is None:
            if st.precheck and tuple(sorted(str(t) for t in tb['types'])) != st.gold[0]:
                return got
            if table_key(S.full(tb)) == st.gold:
                st.hit_at, st.hit_tried = st.clock(), st.tried()
        return got

    def end(self, pg, cur):
        if st.mode == 'walk':
            st.end = cur
        return orig_end(self, pg, cur)

    live.Run.table, live.Run.end = table, end


def atomic_write(path, res):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + '.tmp', 'w') as f:
        json.dump(res, f)
    os.replace(path + '.tmp', path)


def job(task, case, point, arm, out, budget):
    path = result_path(out, arm, task, case, point)
    if os.path.exists(path):
        return None
    import live
    import live_try
    import or_q
    import search
    import search_gold as G
    install(live)
    d, lines = G.gold_of(task, case, point)
    scope, target = lines[:point[0]], lines[point[0]]
    tk = search.clause_key(target)
    kind = target.split()[0].lstrip('(')
    sampler = live.Sampler(G.MODELS)
    res = dict(task=task, case=case, point=point, arm=arm, target=target, forms=len(scope), budget=budget, hit=False, text_hit=False)
    st.mode = 'walk'
    try:
        q = or_q.one(sampler, task, case, point)
    except Exception as e:  # noqa: BLE001
        q = dict(bad=['walk raised %s: %s' % (type(e).__name__, str(e)[:200])])
    st.mode = None
    res.update(bits=q.get('total'), bad=q.get('bad'), dead=q.get('dead'), left=q.get('left'))
    if q.get('bad') or q.get('dead') or q.get('left'):
        res['error'] = 'the walk is not valid: ' + ('bad ' if q.get('bad') else '') + ('dead ' if q.get('dead') else '') + ('left ' if q.get('left') else '')
    elif st.last is None:
        res['error'] = 'the walk made no table: %s' % st.none
    elif st.last[1] is not st.end:
        res['error'] = 'the last table is not the table at the end of the body: %s' % st.none
    if 'error' in res:
        atomic_write(path, res)
        return res
    st.gold, st.last = st.last[0], None
    st.n.clear()
    sess, task_json, _ = live_try.session_of(task)
    c0 = time.process_time()
    cpu = lambda: time.process_time() - c0  # noqa: E731
    st.clock = cpu
    st.mode = 'search'
    try:
        if arm == 'draw':
            calls = ok = 0
            st.tried = lambda: calls + 1
            while cpu() < budget and not res['text_hit']:
                c = sampler.clause(sess, calls, time.monotonic() + 30, task_json, scope, kind)
                calls += 1
                if c is not None:
                    ok += 1
                    if search.clause_key(c.text) == tk:
                        res.update(text_hit=True, text_cpu=round(cpu(), 3), text_tried=calls, text=c.text)
            res.update(tried=calls, clauses=ok)
        else:
            emitted = 0
            box = [sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, kind, eager=True)]
            st.tried = lambda: box[0].stats['runs']
            while cpu() < budget and not res['text_hit']:
                for c in box[0]:
                    emitted += 1
                    if c.key == tk:
                        res.update(text_hit=True, text_cpu=round(cpu(), 3), text_tried=box[0].stats['runs'], text=c.text)
                        break
                se = box[0]
                if se.exhausted or not se.heap:
                    break
                if not res['text_hit']:
                    box[0] = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, kind, eager=True)
            se = box[0]
            res.update(tried=se.stats['runs'], clauses=emitted, exhausted=bool(se.exhausted or not se.heap))
    except Exception as e:  # noqa: BLE001
        res['error'] = 'search raised %s: %s' % (type(e).__name__, str(e)[:200])
    st.mode = None
    res.update(hit=st.hit_at is not None, hit_cpu=None if st.hit_at is None else round(st.hit_at, 3), hit_tried=st.hit_tried, cpu=round(cpu(), 2),
               tables=st.n['tables'], maxrss_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20))
    atomic_write(path, res)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task')
    ap.add_argument('case')
    ap.add_argument('point')
    ap.add_argument('arm', choices=['search', 'draw'])
    ap.add_argument('--budget', type=float, default=60)
    ap.add_argument('--out', default='out/heldtp')
    a = ap.parse_args()
    r = job(a.task, a.case, json.loads(a.point), a.arm, a.out, a.budget)
    if r is None:
        print(a.task, a.case, a.point, a.arm, 'skipped: the job has its file')
        return
    print(a.task, a.case, a.point, a.arm, 'error: ' + r['error'] if 'error' in r else '',
          'table', r['hit'] and r['hit_cpu'], r['hit'] and r['hit_tried'], 'text', r['text_hit'] and r['text_cpu'], r['text_hit'] and r['text_tried'],
          'cpu', r.get('cpu'), 'tried', r.get('tried'), 'tables', r.get('tables'), flush=True)


if __name__ == '__main__':
    main()
