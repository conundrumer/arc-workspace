"""The setting of the teacher-forced walk. Import this first: it sets the environment and sys.path that the sampler code reads at import.

It is the rank read's setting, with the sampler code of this checkout, the same engine and the same steers. Set SAMPLER_CODE before the import to read other sampler code.
"""
import os
import sys

R = '/Users/davidlu/code/arc-workspace'
W = R + '/work/lm/data-study/sampler/sampler-worker/'
RANK = R + '/work/lm/data-study/features-worker/results/features-relation-pick-rank-context-rows-heldout37/'
GOLD_BASE = W + 'sampler-helper-forms/gold-v3-helper-forms-a036da074/'
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
ENGINE = R + '/work/lm/data-study/ast/run/runtime-ba0754492/py313-path'

os.environ.setdefault('SAMPLER_CODE', R + '/.claude/worktrees/agent-a47849b35e6caf985/model/study/sampler')
os.environ.update(RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', STEER_COVER='init,branch', PYTHONDONTWRITEBYTECODE='1', SEARCH_MODELS=RANK + 'steer-models')
if '--corpus' in sys.argv:  # a non-held part, as the rank read walked it
    os.environ['SAMPLER_CORPUS'] = sys.argv[sys.argv.index('--corpus') + 1]
else:
    os.environ.update(SAMPLER_CORPUS=R + '/work/lm/data-study/gold/gold-v3-helper-forms-a036da074/corpus-view/', SEARCH_GOLDS=GOLD_BASE + 'points-base.json')
sys.dont_write_bytecode = True
sys.path.insert(0, ENGINE)
sys.path.insert(0, os.environ['SAMPLER_CODE'])
os.chdir(os.environ['SAMPLER_CODE'])
