import json, subprocess, sys, collections
P='/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-pool-factored-priors-heldout35-600s-ship7/factored_search/'
t='135a2760'
print(open(P+t+'.done.json').read()[:1500])
print(open(P+t+'.nodes.jsonl.zst.idx.jsonl').read()[:300])
out=subprocess.run(['zstd','-dc',P+t+'.nodes.jsonl.zst'],capture_output=True,text=True).stdout
ls=out.splitlines()
print(len(ls), len(out))
r=json.loads(ls[len(ls)//2])
print({k:(str(v)[:200]) for k,v in r.items()})
print(open(P+t+'.events.jsonl').readline()[:400])
