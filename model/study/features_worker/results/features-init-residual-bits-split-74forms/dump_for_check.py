"""Writes comp-priors.json (the component counts of the census priors) and, for the keys given, a program file of the normal-form lines up to the residual INIT, for scripts/arclog_bits.py.

  census_env.sh dump_for_check.py KEY ...
"""
import json
import os
import sys

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-init-residual-bits-split-74forms')
os.environ.setdefault('ARCLOG_THREADS', '1')
import init_residual_bits as I  # noqa: E402
import live  # noqa: E402
import search_gold as G  # noqa: E402

keys = {x.replace('_', ' ') for x in sys.argv[1:]}
sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
json.dump({k: float(v) for k, v in sampler.pri['comps'].items()}, open(I.HERE + 'comp-priors.json', 'w'), indent=0)
for line in open(I.HERE + 'form-set.jsonl'):
    r = json.loads(line)
    if r['key'] in keys:
        nl = I.normal_lines(r)
        path = '%sscratch/program-%s.arclog' % (I.HERE, r['key'].replace(' ', '-'))
        open(path, 'w').write('\n'.join(nl[:r['index'] + 1]) + '\n')
        print(path, r['index'], r['census_bits'])
