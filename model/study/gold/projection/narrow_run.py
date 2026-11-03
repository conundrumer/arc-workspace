"""The DAG split stage (cut2-kit/gold_dagcut2_run.py) with the read narrowing of an INIT (gold_narrow_cuts.py) as its only candidates.
Arguments as gold_dagcut2_run.py.
"""
import os, runpy, sys

K = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-dag-bits/cut2-kit'
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), K]
import gold_dagcut2_one as M  # noqa: E402
import gold_narrow_cuts as N  # noqa: E402

M.dag_candidates = N.narrow_candidates
runpy.run_path(K + '/gold_dagcut2_run.py', run_name='__main__')
