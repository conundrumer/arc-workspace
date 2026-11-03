#!/bin/bash
# resume_check.sh TASK: a renewal, then a kill, on the Mac engine, with the search state on disk.
KG=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/kg; R=/Users/davidlu/code/arc-workspace
T=$1; W=$KG/work2/$T
rm -rf $W $KG/store/$T; mkdir -p $W $KG/store; cp $KG/work/$T/$T $W/$T; touch $W/beat
cd $KG/kit
export PYTHONPATH=$KG/kit/model/study/sampler:$R/work/synth-kaggle/macsite3 ARC_MODELS=$KG/models-full ARC_POLICY=$KG/kit/policy ARC_STORE=$KG/store RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 FIRST_PASS_SECONDS=2 FIRST_PASS_RULE=1
PY=$R/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
run() { $PY -u -m kaggle_worker --task $W/$T --out $W/$T.out.jsonl --beat $W/beat --seconds $1 --seed $2 --rss-limit-mib $3; }
echo == renewal at a low limit; run 45 1 500 2>&1 | grep -E 'generation [0-9]+:|^slots|^end:|bank file|SEARCH|Traceback|Error|no more saves' | cut -c1-260
echo == files; ls $KG/store/$T | grep -c bss; du -sh $KG/store/$T; ls -la $W | grep -E 'bank' | cut -c30-
echo == kill; run 60 5 2888 > $W/k.log 2>&1 & P=$!; /bin/sleep 20; pkill -9 -P $P 2>/dev/null; kill -9 $P 2>/dev/null; wait $P 2>/dev/null; grep -E 'generation [0-9]+:|^slots|Traceback' $W/k.log | cut -c1-200
echo == after the kill; run 20 6 2888 2>&1 | grep -E 'generation [0-9]+:|^slots|^end:|SEARCH|Traceback|Error|no more saves' | cut -c1-260
echo == files; ls $KG/store/$T | grep -c bss; du -sh $KG/store/$T
