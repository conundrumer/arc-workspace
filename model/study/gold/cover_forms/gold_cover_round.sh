#!/bin/bash
# usage: gold_cover_round.sh ROUND STEM...: the covering clause step of a regold round, after its cut step, then the view.
R=/Users/davidlu/code/arc-workspace
G=$R/work/lm/data-study/gold/gold-v3-cover-forms-a036da074
"$R/scripts/run_heavy.py" --cpus 1 --need soon "$G/gold_cover_env.sh" gold_cover_round.py "$@" || exit 1
cd "$G" && timeout 110 python3 gold_cover_view.py | tail -1
