"""The bank lineage of each round 1 job, to prep/lineage.json. Resumable.
  python -I lineage.py [BUDGET_SECONDS]
"""
import json, os, sys, time
sys.dont_write_bytecode = True
HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/set-pick'
SW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker'
sys.path[:0] = [SW + '/refit-tools', SW]
import search_node_score_parity as PA
RUN = SW + '/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out'
KIT = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/refit/out-r1'
OUT = HERE + '/prep/lineage.json'
budget = float(sys.argv[1]) if len(sys.argv) > 1 else 15
t0 = time.time()
got = json.load(open(OUT)) if os.path.exists(OUT) else {}
for arm in ('bundle_s0', 'bundle_s1', 'refit_s0', 'refit_s1'):
    for t in json.load(open(KIT + '/refit-tasks.json'))['heldout37']:
        k = arm + '__' + t
        if k in got or time.time() - t0 > budget:
            continue
        got[k] = PA.load_bank('%s/%s/%s/work/%s.out.jsonl.bank' % (RUN, arm, t, t))['lineage']
json.dump(got, open(OUT + '.tmp', 'w'))
os.replace(OUT + '.tmp', OUT)
print('jobs', len(got), 'seconds %.1f' % (time.time() - t0))
