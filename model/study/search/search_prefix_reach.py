#!/usr/bin/env python
"""When a free-stop search first reaches each of gold's prefixes. One JSON file per case.

  <runtime python> search_prefix_reach.py TASK FORM --out DIR [--budget 60]

Run from a kit's top folder, as search_prefix_rows.py. A gold prefix is the table of gold's walk after each atom; it is reached when a stopped prefix has its merge key. Fields: atoms (gold's
atom count), prefixes, a list of [atoms, merged (the same key as a shorter gold prefix), cpu at reach or None, proposals at reach, atoms of the text that reached it], distinct (prefix tables
seen), runs, cpu.
"""
import argparse
import json
import os
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task')
    ap.add_argument('form', type=int)
    ap.add_argument('--budget', type=float, default=60)
    ap.add_argument('--out', default='out/reach')
    a = ap.parse_args()
    path = '%s/%s.%d.json' % (a.out, a.task, a.form)
    if os.path.exists(path):
        return
    D.table_key = SS.table_key
    SS.patch_search_run()
    _, lines = G.gold_of(a.task, 'x', [a.form, 0])
    scope, target = lines[:a.form], lines[a.form]
    kind = target.split()[0].lstrip('(')
    sampler = live.Sampler(G.MODELS)
    sess, task_json, _ = live_try.session_of(a.task)
    SS.POOL[:] = [types.SimpleNamespace(task=task_json)]
    search.SearchRun.trace = []
    q, _ = T.forced_walk(live, or_q, search, sampler, sess, task_json, scope, target, kind)
    tables, search.SearchRun.trace = search.SearchRun.trace, None
    keys = []
    for tb in tables:
        try:
            keys.append(SS.prefix_key(tb))
        except D.M.Fail:
            keys.append(None)
    first = {}
    for i, k in enumerate(keys, 1):
        if k is not None:
            first.setdefault(k, i)
    reach = {}
    seen = set()
    c0 = time.process_time()
    runs = [0]
    se = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, kind, eager=True)
    while time.process_time() - c0 < a.budget and len(reach) < len(first):
        for c in se:
            tb = getattr(c, 'prefix_tb', None)
            if tb is not None:
                try:
                    key = SS.prefix_key(tb)
                except D.M.Fail:
                    key = None
                seen.add(key)
                if key in first and key not in reach:
                    reach[key] = round(time.process_time() - c0, 2), se.stats['runs'], len(c.prefix_text or ())
            if time.process_time() - c0 >= a.budget or len(reach) == len(first):
                break
        if se.exhausted or not se.heap:
            break
        se = sampler.search(sess, 0, time.monotonic() + G.CHUNK, task_json, scope, kind, eager=True)
    rows = []
    for i, k in enumerate(keys, 1):
        got = reach.get(k)
        rows.append([i, k is not None and first[k] < i, got[0] if got else None, got[1] if got else None, got[2] if got else None])
    os.makedirs(a.out, exist_ok=True)
    res = dict(task=a.task, form=a.form, bits=q['total'], valid=not (q['bad'] or q['dead'] or q['left']), atoms=len(keys), prefixes=rows, distinct=len(seen), runs=se.stats['runs'], cpu=round(time.process_time() - c0, 2))
    with open(path + '.tmp', 'w') as f:
        json.dump(res, f)
    os.replace(path + '.tmp', path)
    print(json.dumps(res)[:200], flush=True)


if __name__ == '__main__':
    main()
