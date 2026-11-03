#!/bin/bash
L=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/39487d30-036f-4e4b-ad99-183af6a33661/scratchpad/lanes
SW=/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker
for p in pod9a pod9b pod9c; do $SW/pull.sh $L/$p.env /root/lanes/sampler/kit9/out $SW/runs/job9 2>/dev/null; done
