"""One stem of the trial, in this process, with no caps: gold_dagcut2_one.py with the read narrowing as its only candidates. For a check.

  narrow_one.py STEM LINES.json BASE-ROWS.json [SECONDS]
"""
import json, os, sys

K = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-dag-bits/cut2-kit'
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), K]
import gold_dagcut2_one as M  # noqa: E402
import gold_narrow_cuts as N  # noqa: E402

M.dag_candidates = N.narrow_candidates
stem, lines_path, base_path = sys.argv[1:4]
M.BASE_ROWS.update(json.load(open(base_path)))
M.load_sampler()
M.setup(stem, lines_path, *(sys.argv[4:5] or [840]))
M.main()
