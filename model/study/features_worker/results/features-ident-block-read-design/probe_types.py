"""Probe: column types per table of each gold form of one task, by a replay as search_node_score_gold_ident.py does. Usage: probe_types.py TASK [FIRST LAST]"""
import json
import os
import sys
import time

KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943'
ENGINE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-0a7d32160/py313-path'
GOLD = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/live-gold-r1/points-eval.json'
os.environ.update(P_DAG='1', ORDER_FREE='tie,key', ARCLOG_IDENT_SOURCE='value', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1')
sys.dont_write_bytecode = True
sys.path[:0] = [KIT + '/model/study/sampler', ENGINE]
import live  # noqa: E402
import live_try  # noqa: E402
import superdag as D  # noqa: E402

task = sys.argv[1]
lo, hi = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, 10 ** 6)
forms = [f for f in {x['task']: x['gold_sexp'] for x in json.load(open(GOLD))}[task].split('\n') if f.strip() and not f.startswith('(OUT')]
sampler = live.Sampler(KIT + '/models-tk')
sess, d, _ = live_try.session_of(task)
run = D.Run(sampler.pri, sess, 0, time.monotonic() + 60, d, live.Limits())
run.collect = []
t0 = time.time()
run.scope(forms)
print('replay %.2fs, %d forms, %d collected' % (time.time() - t0, len(forms), len(run.collect)))
for g, ct in enumerate(run.collect):
    if not lo <= g <= hi:
        continue
    tabs = [[str(t) for t in D.OneTable(ct, j).tables['column_types'][0]] for _, j in D.relation_tables(ct)]
    print(g, forms[g][:110])
    print('   ', tabs)
