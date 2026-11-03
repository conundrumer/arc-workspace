#!/usr/bin/env python
"""One job of the search-against-sampling comparison on a held-out clause, with the extensional match at the clause's end (end table) and the syntactic match (text) in one run.

  <runtime python> tp_end.py TASK CASE POINT ARM [--budget 60] [--out DIR]       (ARM is `search` or `draw`)

Run from a kit's top folder, with SEARCH_GOLDS=$PWD/points-eval.json SEARCH_MODELS=models-held as for search_gold.py. The arms and the CPU clock are
search_gold.job's, as in tp_held.py: the clock starts after the session and the Sampler load, so each arm pays for the replay of the scope, and a
proposal is a run in the search arm and a call of Sampler.clause in the draw arm.

Gold's key is the merge key of the relation table of the target form, read as superdag.Pool.take and superdag.gold_keys read a table: relation_tables of
the step result of the form that gold's replay (Run.scope over the scope and the target) closes, then table_key of S.parse_table(OneTable(ct, j)).
The replay runs in the session of the search, so the row hashes compare. A form with several relation tables (an INIT) has a key for each.

A match is a clause that ended (Run.clause_of, which gives Clause.tables = pg.before, the step result after the clause's END) whose relation tables, read the
same way, have all of gold's keys. So the stop is in the match, and a prefix cannot match: a prefix table at the end of an OR does not show the OR's rows.
There is no prefix match in this file. A key is computed in full only for a table whose sorted column types are those of a gold key.

Before the search, the walk of or_q (gold's choices forced, in this session) ends in a clause, and that clause's relation tables go through the same key
code. Their keys must be gold's (field `forced_ok` true); where they are not, the job writes `error` and runs no search. Where the walk's clause has no
finished relation table (the table hit its work cap on the walk's path), `forced_ok` is null and the search runs: a clause with an unfinished table has no
key, so it cannot match.

The job runs until the text match (the clause that ends has gold's clause_key) or the budget. Fields:
  hit, hit_cpu, hit_tried, hit_text   the first clause that ended with gold's key: that it matched, CPU s on the job's clock, proposals so far (the one it was
                                      in included), its text
  text_hit, text_cpu, text_tried, text   the same at the clause with gold's clause_key
  A match is recorded when it comes, so it may lie past the budget by one chunk of the search or one draw; a report counts a match within T when its CPU is at most T.
  tried, clauses, cpu, tables (clauses of which the relation tables were read), bits/bad/dead/left (the teacher-forced walk: q.total, q.bad, q.dead, tokens of
  gold left), forms (of the scope), gold_tables (relation tables of the target), forced_ok.
A walk that is not valid (bad, dead, tokens left, no clause) or whose clause has keys other than the replay's writes `error` and runs no search.
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


class State:
    mode = None  # 'search' while an arm runs
    gold = None  # the set of the merge keys of the target's relation tables
    types = None  # the sorted column types of those keys
    hit_at = hit_tried = hit_text = None
    clock = tried = None
    n = collections.Counter()


st = State


def table_keys(D, ct, types=None):
    """The merge keys of the relation tables of the step result ct, as superdag.Pool.take reads them. With types (a set of sorted column-type tuples),
    only the tables whose sorted column types are in it have their key; a table that is not finished has none."""
    keys = []
    columns = ct.tables['column_types']
    for _, j in D.relation_tables(ct):
        if types is not None and tuple(sorted(str(t) for t in columns[j])) not in types:
            continue
        try:
            keys.append(D.table_key(D.S.parse_table(D.OneTable(ct, j)))[0])
        except D.M.Fail:
            st.n['table not finished'] += 1
    return keys


def install(live, D):
    orig = live.Run.clause_of

    def clause_of(self, forms, pg, f):
        c = orig(self, forms, pg, f)
        if st.mode == 'search' and st.hit_at is None:
            st.n['tables'] += 1
            try:
                got = table_keys(D, c.tables, st.types)
            except Exception:  # noqa: BLE001
                st.n['key raised'] += 1
                return c
            if st.gold <= set(got):
                st.hit_at, st.hit_tried, st.hit_text = st.clock(), st.tried(), c.text
        return c

    live.Run.clause_of = clause_of


def gold_replay(D, live, sampler, sess, task_json, scope, target):
    """The relation-table keys of the target form, from the replay of scope and target in session sess."""
    run = D.Run(sampler.pri, sess, 0, time.monotonic() + 120, task_json, live.Limits())
    run.collect = []
    run.scope([*scope, target])
    ct = run.collect[len(scope)]
    keys = table_keys(D, ct)
    types = {tuple(sorted(str(t) for t in ct.tables['column_types'][j])) for _, j in D.relation_tables(ct)}
    return keys, types


def forced_walk(live, or_q, search, sampler, sess, task_json, scope, target, kind):
    """or_q.one's walk in session sess, with the clause that it ends in: (the record, the Clause or None)."""
    run = or_q.GuidedRun(sampler.pri, sess, time.monotonic() + 120, task_json, live.Limits(form_tries=1))
    dec, pg = run.scope(scope)
    g = run.rng = or_q.Guide(run, or_q.gold_rest(sess, scope, target, kind), kind)
    dead = clause = None
    try:
        f = run.form(pg, dec, kind)
        if kind == 'INIT' and all(t == or_q.SKIP for t in g.rest):  # the walk steps the SKIP of each port that is left, and takes no call for it
            g.rest.clear()
        clause = run.clause_of(scope, pg, f)
    except or_q.Stuck:
        pass
    except search.Dead as e:
        dead = 'Dead: %s' % e
    except Exception as e:  # noqa: BLE001
        dead = '%s: %s' % (type(e).__name__, str(e)[:100])
    return dict(total=round(sum(g.parts.values()), 2), bad=g.bad, dead=dead, left=len(g.rest)), clause


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
    import superdag as D
    install(live, D)
    d, lines = G.gold_of(task, case, point)
    scope, target = lines[:point[0]], lines[point[0]]
    tk = search.clause_key(target)
    kind = target.split()[0].lstrip('(')
    sampler = live.Sampler(G.MODELS)
    sess, task_json, _ = live_try.session_of(task)
    res = dict(task=task, case=case, point=point, arm=arm, target=target, forms=len(scope), budget=budget, hit=False, text_hit=False)
    try:
        q, forced = forced_walk(live, or_q, search, sampler, sess, task_json, scope, target, kind)
        res.update(bits=q['total'], bad=q['bad'], dead=q['dead'], left=q['left'])
        if q['bad'] or q['dead'] or q['left']:
            res['error'] = 'the walk is not valid: ' + ('bad ' if q['bad'] else '') + ('dead ' if q['dead'] else '') + ('left ' if q['left'] else '')
        elif forced is None:
            res['error'] = 'the walk made no clause'
        else:
            gold, types = gold_replay(D, live, sampler, sess, task_json, scope, target)
            res.update(gold_tables=len(gold))
            if not gold:
                res['error'] = 'the replay of the target gave no relation table'
            else:
                got = table_keys(D, forced.tables)
                if not got:  # the table of the walk's path hit the work cap, so this path has no key; the search may reach the clause by another path
                    res['forced_ok'] = None
                elif set(got) != set(gold):
                    res.update(forced_ok=False, error='the forced clause has other keys than the replay')
                else:
                    res['forced_ok'] = True
    except Exception as e:  # noqa: BLE001
        res['error'] = 'walk raised %s: %s' % (type(e).__name__, str(e)[:200])
    if 'error' in res:
        atomic_write(path, res)
        return res
    st.gold, st.types = set(gold), types
    st.n.clear()
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
    res.update(hit=st.hit_at is not None, hit_cpu=None if st.hit_at is None else round(st.hit_at, 3), hit_tried=st.hit_tried, hit_text=st.hit_text, cpu=round(cpu(), 2),
               tables=st.n['tables'], key_raised=st.n['key raised'], maxrss_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20))
    atomic_write(path, res)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task')
    ap.add_argument('case')
    ap.add_argument('point')
    ap.add_argument('arm', choices=['search', 'draw'])
    ap.add_argument('--budget', type=float, default=60)
    ap.add_argument('--out', default='out/splitend')
    a = ap.parse_args()
    r = job(a.task, a.case, json.loads(a.point), a.arm, a.out, a.budget)
    if r is None:
        print(a.task, a.case, a.point, a.arm, 'skipped: the job has its file')
        return
    print(a.task, a.case, a.point, a.arm, 'error: ' + r['error'] if 'error' in r else '',
          'end table', r['hit'] and r['hit_cpu'], r['hit'] and r['hit_tried'], 'text', r['text_hit'] and r['text_cpu'], r['text_hit'] and r['text_tried'],
          'cpu', r.get('cpu'), 'tried', r.get('tried'), 'tables', r.get('tables'), 'forced_ok', r.get('forced_ok'), flush=True)


if __name__ == '__main__':
    main()
