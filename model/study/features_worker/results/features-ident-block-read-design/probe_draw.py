"""Probe: cost of Sampler.clause draws at one gold form's ancestor scope, and the head shapes they give. Usage: probe_draw.py TASK FORM_INDEX KIND SECONDS"""
import collections
import json
import os
import random
import re
import sys
import time

KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943'
ENGINE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-0a7d32160/py313-path'
GOLD = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/live-gold-r1/points-eval.json'
os.environ.update(P_DAG='1', ORDER_FREE='tie,key', ARCLOG_IDENT_SOURCE='value', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
os.environ.pop('STEER_COVER', None)
sys.dont_write_bytecode = True
sys.path[:0] = [KIT + '/model/study/sampler', ENGINE]
t0 = time.time()
import live  # noqa: E402
import live_try  # noqa: E402
import superdag as D  # noqa: E402
print('import %.1fs arclog from %s' % (time.time() - t0, live.arclog.__file__))

task, gi, kind, secs = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
gold = {x['task']: x['gold_sexp'] for x in json.load(open(GOLD))}[task]
forms = [f for f in gold.split('\n') if f.strip() and not f.startswith('(OUT')]
head = [f.split()[1] for f in forms]
reads = [{m.split('.')[0] for m in re.findall(r'&\w+(?:\.\w+)?', f)} - {h} for f, h in zip(forms, head)]
idx = {h: i for i, h in enumerate(head)}
anc, todo = set(), [idx[r] for r in reads[gi] if r in idx]
while todo:
    j = todo.pop()
    if j not in anc:
        anc.add(j)
        todo += [idx[r] for r in reads[j] if r in idx]
rng = random.Random('%s %d' % (task, gi))
order, left = [], set(anc)
while left:
    ready = sorted(j for j in left if not ({idx[r] for r in reads[j] if r in idx} & left))
    j = rng.choice(ready)
    order.append(j)
    left.discard(j)
scope = [forms[j] for j in order]
print('target', forms[gi][:160])
print('scope', len(scope), 'forms, order', order)
t1 = time.time()
sampler = live.Sampler(KIT + '/models-tk')
sess, d, _ = live_try.session_of(task)
print('sampler+session %.1fs' % (time.time() - t1))
shapes, n, t2 = collections.Counter(), 0, time.time()
cpu0 = time.process_time()
while time.time() - t2 < secs:
    c = sampler.clause(sess, n, time.monotonic() + 20, d, scope, kind)
    n += 1
    if c is None:
        shapes['(none)'] += 1
        continue
    types = []
    for _, j in D.relation_tables(c.tables):
        types.append(tuple(str(t) for t in D.OneTable(c.tables, j).tables['column_types'][0]))
    shapes[tuple(types)] += 1
el = time.time() - t2
print('draws %d in %.1fs wall %.1fs cpu: %.3f s/draw; first draw includes the scope replay' % (n, el, time.process_time() - cpu0, el / max(n, 1)))
print('counts', dict(sampler.run.c.most_common(12)))
for s, k in shapes.most_common(15):
    print(k, s)
