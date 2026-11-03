import json, collections
R='/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-init-residual-bits-split-74forms/'
rows=[json.loads(l) for l in open(R+'form-set.jsonl')]
for r in rows:
    print(r['key'], r['held'], r['target'][:330])
print(sum('(:key' in r['target'] for r in rows))
hs=set(open('/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/held/tasks.txt').read().split())
import os
P='/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-pool-factored-priors-heldout35-600s-ship7/'
ts={f.split('.')[0] for f in os.listdir(P+'factored_search')}
tc={f.split('.')[0] for f in os.listdir(P+'control_search')}
print(len(ts),len(tc), 'held in run', len(hs&ts), hs-ts)
print('rows in run', sum(r['task'] in ts for r in rows), 'tasks', len({r['task'] for r in rows if r['task'] in ts}), 'not held rows in run', sum(r['task'] in ts and not r['held'] for r in rows))
print(sorted({(r['task'],r['held']) for r in rows if r['held'] and r['task'] not in ts}))
