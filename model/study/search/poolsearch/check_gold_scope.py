"""A check of the search arm's candidate path: seeds gold's forms up to a depth cut into the pool, then visits searches over the scope of all of them, one per kind.

  <runtime python> check_gold_scope.py TASK [LEVEL] [LEVELS] [SECONDS]      (from the kit's top folder; LEVEL of LEVELS as --seed-level)
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import superdag_search as X  # noqa: E402
import superdag as D  # noqa: E402
import live  # noqa: E402

task, level, levels, seconds = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
gold = {s['task']: s['gold_sexp'] for s in json.load(open('points-eval.json'))}[task]
sampler = live.Sampler('models-held')
X.SAMPLER[:] = [sampler]
sampler.search_store(None, hot=6)
X.patch_search_run()
a = argparse.Namespace(seed=0, k=6, draws_per_scope=4, seconds=seconds)
sess, d, outs = D.session_of(task)
a.t0 = time.monotonic()
run = D.Run(sampler.pri, sess, 0, a.t0 + seconds, d, live.Limits())
keys = D.gold_keys(run, gold)
events = []
pool = D.Pool(task, d, run, D.UniformPolicy(d), keys, lambda x: None, events.append, a)
pool.slots = {}
pool.sampler, pool.deadline = sampler, a.t0 + seconds
print('seeded %d of %d forms, cut %d of %d' % pool.seed(gold, level, levels))
fids = sorted(pool.forms)
for kind in ('RULE', 'DET'):
    slot = X.Slot(fids, tuple(pool.forms[f].text for f in fids), kind)
    X.PATIENCE = 10 ** 6
    X.VISIT_SECONDS = seconds / 2
    print(kind, 'new nodes', X.visit(pool, slot, pool.deadline))
print('events', [(e['event'], e.get('seconds'), e.get('depth')) for e in events][:20])
print('candidates', len(pool.candidates), 'covered', len(pool.covered), 'of', len(keys))
print({k: v for k, v in run.c.items() if 'error' in k or k.startswith('search:')})
