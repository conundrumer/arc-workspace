#!/usr/bin/env python
"""Live prefix rows: every distinct prefix table that the first stage of the resume harness stops at, with its features and table, and gold's prefixes marked. One zstd JSONL per case.

  <runtime python> search_prefix_rows.py TASK FORM --out DIR [--first 20]

Run from a kit's top folder, with tp_end.py there, SEARCH_GOLDS and SEARCH_MODELS set, SEARCH_FREE_STOP=1, and SEARCH_PREFIX_SCORE on features_prefix_keep.py. The context is gold's forms
before the target. A row: task, form, text (atom strings), atoms, logp (the path's log chance in nats, the free stop costs nothing), score (as `score` returns it), gold (the table is one
of the forced walk's prefixes), gold_atoms_max (the most atoms of gold's prefixes with this table), texts (prefix texts that reached the table), atoms_max (the most atoms among them), f (the
feature dict), table (types, labels, x_rows at 200 rows). A row keeps the first text that reached its table. The last line has the case's totals. A case with its file is skipped.
"""
import argparse
import json
import os
import subprocess
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

S = D.S
CAP = 200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task')
    ap.add_argument('form', type=int)
    ap.add_argument('--first', type=float, default=20)
    ap.add_argument('--runs', type=int, default=0, help='stop at this many search runs, so a slower machine gives the same pool; --first is then a cap on CPU s')
    ap.add_argument('--out', default='out/prefix-rows')
    a = ap.parse_args()
    path = '%s/%s.%d.prefix-rows.jsonl.zst' % (a.out, a.task, a.form)
    if os.path.exists(path):
        return
    SS.load_rule()
    D.table_key = SS.table_key
    SS.patch_search_run()
    K = SS.PREFIX_SCORE
    point = [a.form, 0]
    _, lines = G.gold_of(a.task, 'x', point)
    scope, target = lines[:a.form], lines[a.form]
    kind = target.split()[0].lstrip('(')
    sampler = live.Sampler(G.MODELS)
    sess, task_json, _ = live_try.session_of(a.task)
    SS.POOL[:] = [types.SimpleNamespace(task=task_json)]
    search.SearchRun.trace = []
    q, _ = T.forced_walk(live, or_q, search, sampler, sess, task_json, scope, target, kind)
    tables, search.SearchRun.trace = search.SearchRun.trace, None
    gold = {}  # the key of each gold prefix's table -> the most atoms of gold's prefixes with that table
    for i, tb in enumerate(tables, 1):
        try:
            gold[SS.prefix_key(tb)] = i
        except D.M.Fail:
            pass
    valid = not (q['bad'] or q['dead'] or q['left'])
    os.makedirs(a.out, exist_ok=True)
    tmp = '%s.%d.tmp' % (path[:-4], os.getpid())
    seen = {}
    done = dict(task=a.task, form=a.form, kind=kind, bits=q['total'], valid=valid, gold_prefixes=len(gold), gold_rows=0, floor=0, first=a.first, feature_failures=0)
    pairs = K.pairs_of(task_json)
    c0 = time.process_time()
    with open(tmp, 'w') as f:
        def stage1(c):
            tb = getattr(c, 'prefix_tb', None)
            if tb is None or c.prefix_text is None:
                return
            had = 'full' in tb
            try:
                S.full(tb)
                key = SS.prefix_key(tb)
                if key in seen:
                    seen[key]['texts'] += 1
                    seen[key]['atoms_max'] = max(seen[key]['atoms_max'], len(c.prefix_text))
                    return
                ctx = dict(run=se.run, task=task_json, text=c.prefix_text, atoms=len(c.prefix_text), logp=c.logq)
                value = float(K.score(tb, ctx))
                try:
                    got = K.row(tb, ctx)
                except Exception:  # noqa: BLE001
                    done['feature_failures'] += 1
                    got = dict(f=None, table=None)
                row = dict(task=a.task, form=a.form, text=list(c.prefix_text), atoms=len(c.prefix_text), logp=round(c.logq, 4), score=value, gold=key in gold, gold_atoms_max=gold.get(key), texts=1, atoms_max=len(c.prefix_text), **got)
                seen[key] = row
                done['gold_rows'] += row['gold']
                done['floor'] += value <= K.FLOOR
            except D.M.Fail:
                pass
            finally:
                if not had:
                    tb.pop('full', None)

        if valid:
            se = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, kind, eager=True)
            def over():
                return time.process_time() - c0 >= a.first or (a.runs and se.stats['runs'] >= a.runs)

            while not over():
                for c in se:
                    stage1(c)
                    if over():
                        break
                if se.exhausted or not se.heap:
                    break
                se = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, kind, eager=True)
        for row in seen.values():
            f.write(json.dumps(row, default=float) + '\n')
        done.update(rows=len(seen), cpu=round(time.process_time() - c0, 2), score_failed=K.failed[0], runs=se.stats['runs'] if valid else 0, runs_cap=a.runs)
        f.write(json.dumps(dict(done=done)) + '\n')
    subprocess.run(['zstd', '-q', '-f', '--rm', '-o', path, tmp], check=True)
    print(json.dumps(done), flush=True)


if __name__ == '__main__':
    main()
