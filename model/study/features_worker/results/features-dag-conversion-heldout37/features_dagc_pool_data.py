#!/usr/bin/env python
"""Arrays of a pool part (item 18): features_dagc_data.py with the walks of one task set. fit-pool is read as two data sets, train and test tasks, as the tune rows are the test tasks.

  features_dagc_env.sh 1 features_dagc_pool_data.py NAME POINTS WALKS... --tasks train|test|all [--kinds RULE] [--seconds S]

The task set is the tasks of points-fit-pool-train-0of1.jsonl or points-fit-pool-test-0of1.jsonl. A walk of another task is read and counted as not finished (ok false), so the chunk index of features_dagc_data.py, which counts walks, stays the same
whatever the set, and a rerun resumes. POINTS is points-fit-pool.jsonl (the cat of the two). Two points of one task whose forms have equal content keys share a `line` there (crc32 of task and form key): they hold the same text
and the same scope length, so they share their walks.
"""
import json
import os
import sys

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')
import features_dagc_data as DD  # noqa: E402

ME = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37/'  # the data folder


def main():
    argv = sys.argv[1:]
    which = 'all'
    if '--tasks' in argv:
        i = argv.index('--tasks')
        which = argv[i + 1]
        del argv[i:i + 2]
    sys.argv = [sys.argv[0]] + argv
    if which != 'all':
        sel = {json.loads(x)['task'] for x in open(ME + 'points-fit-pool-%s-0of1.jsonl' % which)}
        orig = DD.walk_frames

        def filtered(path, skip=0):
            for rows, fm in orig(path, skip):
                yield rows, (fm if fm['task'] in sel else dict(fm, ok=False))
        DD.walk_frames = filtered
    DD.main()


if __name__ == '__main__':
    main()
