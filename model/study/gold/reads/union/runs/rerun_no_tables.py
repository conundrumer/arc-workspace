"""Run again each program of fits-SET.jsonl that gives no tables (a timeout or a stop), with FITS_CAP seconds; print one JSON line per program: task, text_sha, cases, result (assignments, fitting, test_ok, why) and seconds. rerun_no_tables.sh runs it in shards, and apply_reruns.py writes the results into the fits shard files.

  ARCLOG_IDENT_SOURCE=value PYTHONPATH=<site> FITS_CAP=S python rerun_no_tables.py SET [K N]    K N: the programs at positions K, K + N, ...
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gold_union_fits as F
s = sys.argv[1]
k, n = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, 1)
i = -1
todo = F.programs_of(s)
env, tasks = F.engine(), F.ROOT / 'data/tasks'
for r in F.rows_of(F.OUT + 'fits-%s.jsonl' % s):
    for x in r['programs']:
        if x['why']:
            i += 1
            if i % n != k:
                continue
            text = next(t for t in todo[r['task']] if F.sha16(t) == x['text_sha'])
            t0 = time.time()
            got = F.capped(env, r['task'], text, tasks, json.load(open(tasks / (r['task'] + '.json'))))
            print(json.dumps(dict(task=r['task'], text_sha=x['text_sha'], cases=x['cases'], result=got, seconds=round(time.time() - t0))), flush=True)
