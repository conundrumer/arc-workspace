"""Writes a bank file that holds gold's forms for one task, and the task file, for a kaggle_worker run. seed_bank.py TASK WORK POINTS.json
Run with superdag.py and kaggle_worker.py on PYTHONPATH, and ARC_MODELS and ARC_POLICY set."""
import json
import os
import sys

tid, work, points = sys.argv[1:4]
sys.argv = ['x']
import kaggle_worker as W  # noqa: E402
import superdag as D  # noqa: E402

live = D.live
sampler = live.Sampler(os.environ['ARC_MODELS'])
gold = next(x for x in json.load(open(points)) if x['task'] == tid)['gold_sexp']
session, task, outs = D.session_of(tid)
os.makedirs(work, exist_ok=True)
json.dump(dict(train=task['train'], test=task['test']), open('%s/%s' % (work, tid), 'w'))
json.dump(outs, open('%s/%s.outs.json' % (work, tid), 'w'))


class Args:
    seed, k, draws_per_scope, t0 = 1, 6, 4, 0


run = D.Run(sampler.pri, session, 1, 1e12, task, live.Limits())
policy = D.make_policy(os.environ['ARC_POLICY'], task)
pool = D.Pool(tid, task, run, policy, {}, lambda r: None, lambda x: None, Args())
pool.keep_rows = False
print(pool.seed(gold, 1, 1), flush=True)
print(W.write_bank('%s/%s.out.jsonl.bank' % (work, tid), pool, 0, 0), len(pool.forms), flush=True)
os._exit(0)
