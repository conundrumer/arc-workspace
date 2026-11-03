#!/bin/bash
# seed_check.sh TASK SECONDS: a seeded bank through the search path of the worker, on the Mac engine. Prints whether a written candidate is right on test.
KG=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/kg; R=/Users/davidlu/code/arc-workspace; SW=/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker
T=$1; S=${2:-120}; W=$KG/work/$T
rm -rf $W $KG/store/$T; mkdir -p $W $KG/store
cd $KG/kit
export PYTHONPATH=$KG/kit/model/study/sampler:$R/work/synth-kaggle/macsite3 ARC_MODELS=$KG/models-full ARC_POLICY=$KG/kit/policy ARC_STORE=$KG/store RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export SEARCH_READ_PICK=${SEARCH_READ_PICK:-0} FIRST_PASS_SECONDS=${FIRST_PASS_SECONDS:-0}
PY=$R/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
$PY $SW/seed_bank.py $T $W $KG/kit/points-eval.json 2>&1 | tail -2 | cut -c1-200
touch $W/beat
$R/scripts/run_heavy.py --cpus 1 --need now timeout $((S+60)) $PY -u -m kaggle_worker --task $W/$T --out $W/$T.out.jsonl --beat $W/beat --seconds $S --seed 1 --rss-limit-mib 2888 2>&1 | tail -8 | cut -c1-260
python3 - <<PY
import json
outs=json.load(open('$W/$T.outs.json'))
rows=[json.loads(l) for l in open('$W/$T.out.jsonl')]
right=[r for r in rows if all(o in a for o,a in zip(outs,r['attempts']))]
print('candidates',len(rows),'right on test',len(right))
if right: print(right[0]['program'][-300:])
PY
ls -la $KG/store/$T 2>/dev/null | tail -4 | cut -c30-; du -sh $KG/store/$T 2>/dev/null
