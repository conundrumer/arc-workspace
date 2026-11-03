#!/usr/bin/env python
"""Surprisal by decision of each held RULE test case, under gold's earlier forms as context and under its parents only. One row per case, streamed; finished rows are skipped.

  <runtime python> search_case_bits.py OUT.jsonl STEMS      from a kit's top folder, with PYTHONPATH on the kit's sampler, SEARCH_GOLDS and SEARCH_MODELS set
"""
import json
import os
import sys
import tempfile

import live
import or_q
import search_gold as G

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_oracle_report as Rp  # noqa: E402

out, stems = sys.argv[1:3]
specs = {x['task']: x['gold_sexp'] for x in json.load(open('points-eval.json'))}
done = {(r['task'], r['form']) for r in map(json.loads, open(out))} if os.path.exists(out) else set()
sampler = live.Sampler(os.environ['SEARCH_MODELS'])
tmp = tempfile.mkdtemp()
base = G.GOLDS


def walk(task, lines, keep, i):
    path = tmp + '/g.json'
    json.dump([dict(task=task, gold_sexp='\n'.join([lines[j] for j in keep] + [lines[i]]))], open(path, 'w'))
    G.GOLDS = path
    G.golds.cache_clear()
    try:
        q = or_q.one(sampler, task, 'x', [len(keep), 0])
        return dict(bits=q.get('total'), valid=not (q.get('bad') or q.get('dead') or q.get('left')), parts=q.get('parts'), atoms=len(q.get('atoms') or []))
    except Exception as e:  # noqa: BLE001
        return dict(bits=None, valid=False, error=repr(e)[:160])


with open(out, 'a') as f:
    for line in open(stems):
        if not line.strip():
            continue
        task, case, point = line.rstrip('\n').split('\t')
        i = json.loads(point)[0]
        if case != 'RULE' or task not in specs or (task, i) in done:
            continue
        lines = [x for x in specs[task].strip().split('\n') if not x.startswith('(OUT')]
        _, reads, _, _ = Rp.gold(specs[task], 3)
        got, todo = set(), list(reads[i])
        while todo:
            j = todo.pop()
            if j not in got:
                got.add(j)
                todo += reads[j]
        row = dict(task=task, form=i, parents=len(reads[i]), target=lines[i][:240], earlier=walk(task, lines, list(range(i)), i), reads_only=walk(task, lines, sorted(got), i), n_earlier=i, n_reads=len(got))
        f.write(json.dumps(row) + '\n')
        f.flush()
        print(task, i, row['earlier'].get('bits'), row['reads_only'].get('bits'), flush=True)
