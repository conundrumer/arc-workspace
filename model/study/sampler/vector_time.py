#!/usr/bin/env python
"""The time of the writing-point vector (writer.Features.vectors) on the gold queries of one ramp task (prep.jsonl), under the plans of train_rows.points_of_targets.

    vector_time.py TASK [--plan ordered|unordered|both] [--limit N] [--seconds S] [--max-states N]

One task for each process. The groups are those of plan_check.groups_of (the gold queries of one scope and one kind, walked together as a trie); --limit N takes the first N.
One JSON line for each writing point, as soon as its vector is made:
    {"task", "plan", "group", "kind", "index", "phase", "ids", "defined", "seconds", "successor_seconds", "body_seconds"}
seconds is the time of Features.vectors() at the point (successor_seconds of it in writer.successor_tables, the engine's call, or the oracle with WRITER_SUCCESSOR=oracle; body_seconds in writer.current_body). defined is the count of ids whose
successor body the engine gives. Then one line for each plan: {"task", "plan", "summary": true, "points", "ids", "median_seconds", "p90_seconds", "successor_share", "vector_seconds",
"wall_seconds", "wall_per_point", "successor" (writer.SUCCESSOR), "records", "errors", "left_mask", "undefined", "rule_removed" (the faults: the
records with a next or positive id that the legality rules removed) and "rules" (the plan's stats that name the rules)}. wall_seconds is the time of the whole walk of the plan (stepping, the order plan, the other features and the
vectors).
"""
import argparse
import collections
import json
import os
import sys
import time

import numpy as np

import live
import live_try
import plan_check
import train_rows as tr
import writer


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('task')
    ap.add_argument('--plan', default='both', choices=('ordered', 'unordered', 'both'))
    ap.add_argument('--limit', type=int, default=0, help='the most groups (0: all)')
    ap.add_argument('--seconds', type=float, default=10.0)
    ap.add_argument('--max-states', type=int, default=20000)
    a = ap.parse_args(argv)
    live_try.P.REPO = os.environ.get('ARC_ROOT', '/Users/davidlu/code/arc-workspace')
    smp = live.Sampler(os.environ['SAMPLER_CODE'] + '/../../../models-current', steers=())
    sess, d, _ = live_try.session_of(a.task)
    run = live.Run(smp.pri, sess, 0, time.monotonic() + 3600, d, live.Limits())
    groups = plan_check.groups_of(a.task, sess, run)
    if a.limit:
        groups = groups[:a.limit]
    uses = writer.feature_names()
    names = writer.vector_names(run)
    cur = {}
    log = []  # (seconds, successor seconds, ids) of each point
    orig = writer.Features.vectors

    def timed(self):
        if self._vectors is not None:
            return orig(self)
        o0, b0 = writer.ORACLE['successor seconds'], writer.ORACLE['body seconds']
        t0 = time.perf_counter()
        v = orig(self)
        dt = time.perf_counter() - t0
        so, sb = writer.ORACLE['successor seconds'] - o0, writer.ORACLE['body seconds'] - b0
        pt = self.point_
        log.append((dt, so, len(self.ids)))
        defined = int(np.nansum(v[:, names.index('cand:defined')])) if 'cand:defined' in names else None
        print(json.dumps(dict(task=a.task, plan=cur['plan'], group=cur['group'], kind=cur['kind'], index=len(pt.tokens), phase=pt.place.phase.name, ids=len(self.ids), defined=defined,
                              seconds=round(dt, 4), successor_seconds=round(so, 4), body_seconds=round(sb, 4))), flush=True)
        return v
    writer.Features.vectors = timed
    for plan in ('ordered', 'unordered') if a.plan == 'both' else (a.plan,):
        cur['plan'] = plan
        log.clear()
        writer.ORACLE.clear()
        c = collections.Counter()
        totals = collections.Counter()  # the stats of the groups
        t0 = time.perf_counter()
        for gi, (scope, kind, streams) in enumerate(groups):
            cur.update(group=gi, kind=kind)
            stats = collections.Counter()
            try:
                for i, rec in tr.points_of_targets(run, scope, kind, streams, uses, plan=plan, seconds=a.seconds, stats=stats, max_states=a.max_states, vectors=True):
                    if 'error' in rec:
                        c['errors: ' + type(rec['error']).__name__ + ' ' + str(rec['error'])[:60]] += 1
                    elif rec['left_mask']:
                        c['left_mask'] += 1
                    else:
                        c['records'] += 1
                        c['rule_removed'] += bool(len(rec['rule_removed']))
                        assert rec['vectors'].shape == (len(rec['ids']), len(names)) and rec['names'] is names
            except Exception as e:  # noqa: BLE001
                c['group errors: %s %s' % (type(e).__name__, str(e)[:60])] += 1
            totals.update(stats)
        wall = time.perf_counter() - t0
        sec = np.array([x[0] for x in log])
        tot = float(sec.sum())
        print(json.dumps(dict(task=a.task, plan=plan, summary=True, points=len(log), ids=int(sum(x[2] for x in log)), median_seconds=round(float(np.median(sec)), 4) if len(sec) else None,
                              p90_seconds=round(float(np.percentile(sec, 90)), 4) if len(sec) else None, successor_share=round(sum(x[1] for x in log) / tot, 3) if tot else None,
                              vector_seconds=round(tot, 2), wall_seconds=round(wall, 2), wall_per_point=round(wall / max(len(log), 1), 4), width=len(names),
                              successor=writer.SUCCESSOR, records=c.pop('records', 0), left_mask=c.pop('left_mask', 0), rule_removed=c.pop('rule_removed', 0),
                              rules={k: v for k, v in totals.items() if 'rule' in k}, errors=dict(c),
                              undefined={k[len('undefined: '):]: v for k, v in writer.ORACLE.items() if k.startswith('undefined: ')})), flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
