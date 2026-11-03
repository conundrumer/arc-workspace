#!/usr/bin/env python
"""Runs order_count.analyze on chosen training queries only.

    order_recheck.py CASES.jsonl OUT.jsonl TASK [--seconds S] [--states N]

CASES.jsonl: lines with task and qid (the records of order_count.py train give them). TASK: the one task to run (a process works on one task). The records go to OUT.jsonl as order_count.py
writes them (set 'train'); a query that is in OUT.jsonl is skipped on a restart.
"""
import argparse
import json
import os
import sys

import live_try
import order
import order_count as oc


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('cases')
    ap.add_argument('out')
    ap.add_argument('task')
    ap.add_argument('--seconds', type=float, default=3.0)
    ap.add_argument('--states', type=int, default=20000)
    a = ap.parse_args(argv)
    live_try.P.REPO = os.environ.get('ARC_ROOT', '/Users/davidlu/code/arc-workspace')
    want = {json.loads(l)['qid'] for l in open(a.cases) if json.loads(l)['task'] == a.task}
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            try:
                r = json.loads(l)
                done.add((r['task'], r['qid']))
            except ValueError:
                pass
    todo = [(q, s, t) for q, s, t in oc.train_queries(a.task) if q in want and (a.task, q) not in done]
    if not todo:
        return
    sess, _, _ = live_try.session_of(a.task)
    env = order.Env(sess)
    with open(a.out, 'a') as out:
        for qid, scope, text in todo:
            rec = oc.analyze(env, sess, scope, text, a.states, a.seconds)
            rec.update(set='train', task=a.task, qid=qid)
            out.write(json.dumps(rec) + '\n')
            out.flush()


if __name__ == '__main__':
    main(sys.argv[1:])
