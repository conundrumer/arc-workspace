#!/bin/bash
# Pins the sampler, makes the Mac's check rows at the new pin, and builds the reread kit.
cd "$(dirname "$0")"
H=/Users/davidlu/code/arc-workspace/scripts/run_heavy.py
python3 - <<'P'
import gold_pod_kit as K, json, hashlib
K.pin_sampler(K.HERE + '/kit-model/study/sampler')
t = {x: K.text_of(x) for x in ('35ab12c3', '88bcf3b4')}
json.dump(t, open('check-lines.json', 'w'))
json.dump({}, open('check-weights.json', 'w'))
open('check-1.txt', 'w').write('35ab12c3\n'); open('check-2.txt', 'w').write('88bcf3b4\n')
P
mkdir -p measured/e88; rm -f measured/rows-0.jsonl measured/e88/rows-0.jsonl
$H --cpus 1 --need soon bash gold_pod_env.sh gold_pod_run.py check-1.txt check-lines.json check-weights.json measured/rows-0.jsonl 0 1 > measured/m1.log 2>&1; echo row1 $?
POD_ORDER_CAP=4 POD_BUDGET=32 POD_ONLY=56,59,72 POD_PREFIX=0 $H --cpus 1 --need soon bash gold_pod_env.sh gold_pod_run.py check-2.txt check-lines.json check-weights.json measured/e88/rows-0.jsonl 0 1 > measured/m2.log 2>&1; echo row2 $?
python3 gold_pod_expect.py && python3 gold_pod_kit.py
