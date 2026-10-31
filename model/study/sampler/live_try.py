#!/usr/bin/env python
"""Runs live.Sampler on tasks of data/tasks with their test outputs held out, as a Kaggle worker would, and prints each result
as it comes and a line per task: draws per second, peak RSS, counts. The test outputs score the attempts here, after draws.

  RAYON_NUM_THREADS=1 <runtime python> -u live_try.py TASK ... [--seconds 20] [--seed 0] [--models DIR]
"""
import argparse
import json
import resource
import time

import live
import sampler_paths as P

SETTINGS = dict(deadline_seconds=10.0, rule_tests=False, table_work_cap=1 << 21, static_pruning=True)


def session_of(task):
    """An open-world session of the task with no test output, and the test outputs."""
    d = json.load(open('%s/data/tasks/%s.json' % (P.REPO, task)))
    outs = [t.pop('output', None) for t in d['test']]
    return live.arclog.Session(live.arclog.Task.from_json(json.dumps(d), live.arclog.World.Open), live.arclog.DecodeSettings(**SETTINGS), session_bytes=2 << 30), outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tasks', nargs='+')
    ap.add_argument('--seconds', type=float, default=20)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--models', default=P.SAMPLER_DATA + '/models')
    a = ap.parse_args()
    t0 = time.time()
    sampler = live.Sampler(a.models)
    print('loaded %.2fs' % (time.time() - t0), flush=True)
    for task in a.tasks:
        sess, outs = session_of(task)
        last, solved, shown = None, 0, False
        for r in sampler.draws(sess, a.seed, time.monotonic() + a.seconds):
            last = r
            if r.decoder is None:
                break
            right = all(o in att for o, att in zip(outs, r.attempts))
            solved += right
            if not shown or right:  # the first fit, and each that passes the test
                print('%s %.2fs consistent draws=%d test=%s\n%s' % (task, r.seconds, r.counts['draws'], right, r.program), flush=True)
                shown = True
        c = last.counts
        print('%s %.1fs draws=%d forms=%d (%.1f draws/s, search %.1f ms a form) consistent=%d test_right=%d peak_rss=%.0fMiB\n  %s' % (
            task, last.seconds, c['draws'], c.get('forms', 0), c['draws'] / max(last.seconds, 1e-9), 1000 * c.get('search_seconds', 0) / max(c.get('forms', 0), 1),
            c.get('consistent', 0), solved,
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20,
            {k: v for k, v in sorted(c.items(), key=lambda x: str(x[0])) if k not in ('draws', 'limits')}), flush=True)


if __name__ == '__main__':
    main()
