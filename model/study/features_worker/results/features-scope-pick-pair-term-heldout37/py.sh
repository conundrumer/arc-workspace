#!/bin/bash
# Runs a script on the Mac runtime ba0754492, one thread, from the kit folder.
ROOT=/Users/davidlu/code/arc-workspace/work/lm/data-study
KIT=$ROOT/sampler/sampler-worker/kits/sampler-pool-extended-text-pass1-8be414670
cd "$KIT"
exec env PYTHONPATH=$ROOT/ast/run/runtime-ba0754492/py313-path:$KIT/model/study/sampler ARC_MODELS=$KIT/models-base RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 ARC_SESSION_SHARE=.9 $ROOT/ast/run/runtime-kaggle-py313/venv/bin/python -u "$@"
