#!/bin/bash
# Copies job 14's light files from its three pods, then prints the report.
L=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/39487d30-036f-4e4b-ad99-183af6a33661/scratchpad/lanes; SW=/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker; SP=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad
for p in pod16a pod16b pod16c; do
  . $L/$p.env
  rsync -az --timeout=40 --include='*/' --include='start' --include='disk.txt' --include='supervisor.log' --include='*.log' --include='*.cover' --include='*.out.jsonl' --include='submission.json' --exclude='*'     -e "ssh -i $L/key_sampler -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o BatchMode=yes -p $PORT" root@$HOST:/root/lanes/sampler/kit16/out/ $SW/runs/search-pool-vs-sampling-heldout37-3600s-ship4-tie-c1bfa64f2/ 2>/dev/null
done
python3 $SW/search_pool_run_report.py $SW/runs/search-pool-vs-sampling-heldout37-3600s-ship4-tie-c1bfa64f2 $SP/k6/points-eval.json --tasks-dir $SP/b14/kit14/data/tasks
