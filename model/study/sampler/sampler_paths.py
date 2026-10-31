"""Where the sampler reads its code and data. Importing this module puts the study root on sys.path."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from study_paths import CODE_ROOT, DATA_ROOT, REPO_ROOT  # noqa: E402

CODE, DATA, REPO = str(CODE_ROOT), str(DATA_ROOT), str(REPO_ROOT)
SAMPLER_DATA = DATA + '/sampler'
STUDY = CODE + '/feat_exp'  # the feature code: featlib, strata, rulecheck, measure, online_score, cut_score
