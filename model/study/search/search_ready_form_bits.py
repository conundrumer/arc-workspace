#!/usr/bin/env python
"""Surprisal of each ready gold form with only its read forms in context, and whether the oracle context arm found it. Streams one row per form and skips finished rows.

  <runtime python> search_ready_form_bits.py OUT.jsonl RUN_DIR      from a kit's top folder, with PYTHONPATH on the kit's sampler

RUN_DIR holds oracle1_search and oracle2_search.
"""
import json
import os
import re
import sys
import tempfile

import live
import or_q
import search_gold as G

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_oracle_report as Rp  # noqa: E402

out, run = sys.argv[1:3]
specs = {x['task']: x['gold_sexp'] for x in json.load(open('points-eval.json'))}
done = {(r['level'], r['task'], r['form']) for r in map(json.loads, open(out))} if os.path.exists(out) else set()
sampler = live.Sampler('models-held')
tmp = tempfile.mkdtemp()
with open(out, 'a') as f:
    for level in (1, 2):
        rows = Rp.load('%s/oracle%d_search' % (run, level))
        for t, r in sorted(rows.items()):
            if not r['ended'] or t not in specs:
                continue
            kinds, reads, fid, ready = Rp.gold(specs[t], level)
            lines = [x for x in specs[t].strip().split('\n') if not x.startswith('(OUT')]
            for i in ready:
                if (level, t, i) in done:
                    continue
                got, todo = set(), list(reads[i])
                while todo:
                    j = todo.pop()
                    if j not in got:
                        got.add(j)
                        todo += reads[j]
                keep = sorted(got)
                path = '%s/g.json' % tmp
                json.dump([dict(task=t, gold_sexp='\n'.join([lines[j] for j in keep] + [lines[i]]))], open(path, 'w'))
                G.GOLDS = path
                G.golds.cache_clear()
                row = dict(level=level, task=t, form=i, kind=kinds[i], parents=len(reads[i]), scope=len(keep), found=i in r['covers'], target=lines[i][:200])
                try:
                    q = or_q.one(sampler, t, 'x', [len(keep), 0])
                    row.update(bits=q.get('total'), valid=not (q.get('bad') or q.get('dead') or q.get('left')), parts=q.get('parts'))
                except Exception as e:  # noqa: BLE001
                    row.update(bits=None, valid=False, error=repr(e)[:160])
                f.write(json.dumps(row) + '\n')
                f.flush()
                print(level, t, i, row.get('bits'), row.get('valid'), row['found'], flush=True)
