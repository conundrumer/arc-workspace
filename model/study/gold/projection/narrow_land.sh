#!/bin/bash
# Lands the projection-helper rows written so far: copies the Mac rows of the 99, decides bar crossings on all rows (a rerun skips decided steps), rebuilds view-final and programs/gold. Safe to run at any time.
S=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad
N=/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-projection-trial
G=/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-combined-cut
H=/Users/davidlu/code/arc-workspace/scripts/run_heavy.py
mkdir -p $N/trial99/out; cp $S/next-class/trial99/out/rows-*.jsonl $N/trial99/out/ 2>/dev/null; cp $S/next-class/trial99/lines.json $N/trial99/; cp -R $S/next-class/trial/out $S/next-class/trial/lines.json $N/trial/ 2>/dev/null
B="$H --need soon bash $S/narrow-kit/gold_narrow_env.sh $N/bar-commit/bar_commit.py"
timeout 1200 $B "$N/trial/out/rows-*.jsonl" $N/trial/lines.json $N/bar-commit/out-trial.jsonl > $N/bar-commit/run-trial.log 2>&1
timeout 1200 $B "$N/trial99/out/rows-*.jsonl" $N/trial99/lines.json $N/bar-commit/out-99.jsonl > $N/bar-commit/run-99.log 2>&1
ls $G/../gold-projection-all/rows-*.jsonl >/dev/null 2>&1 && timeout 2400 $B "$G/../gold-projection-all/rows-*.jsonl" $S/narrow-kit/lines.json $N/bar-commit/out-all.jsonl > $N/bar-commit/run-all.log 2>&1
cd $G && python3 gold_combined_view.py $G/view-final | tail -1 | tr ',' '\n' | grep -i projection
python3 $G/gold_export.py
date +%T
