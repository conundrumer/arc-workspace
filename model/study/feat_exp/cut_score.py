"""The score of a sampler clause cut, for a sampler that tilts its proposal by exp(beta * score) at each atom.

    from cut_score import CutScorer
    cs = CutScorer(task, case, point)            # once per point: ~40 ms
    cs.score(cuts, names)                        # per atom, all of that atom's cuts at once
    -> [log-odds, ...]                           # one per cut; nan where a cut has no score

A cut is the clause so far, cut after its first k atoms, as a dict in the format of the sampler's cuts file (`clause`,
`x`, and `fail` and `static` where the sampler has them). `names` is {sampler relation name: program name}, as
`online_score.PointScorer.score` takes it; None scores the clause as written.

The score is the log-odds that the cut is a prefix of gold, from a tree over the columns of the NO_ROWS functions
(`fit_cut_tree.py`), so a cut needs no X rows. A cut has no score where it has no clause or X, where the sampler failed
it or its static check matched a class other than `valid`, and where the bound cut its functions.

Runtime: /Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python, with this directory on sys.path.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
from featlib import DATA, FX  # noqa: E402
# The points root of the run the cuts come from; a run that names another root in its fstore.txt sets FSTORE_POINTS
os.environ.setdefault('FSTORE_POINTS', str(FX / 'fstore-gen3/points'))
from online_score import PointScorer  # noqa: E402

# The tree on gold prefixes against the other cuts, over the columns of the NO_ROWS functions
CUT_TREE_NOROWS = DATA / 'cuthook/cut_tree_norows.pkl'


class CutScorer:
    def __init__(self, task, case, point, bound=2.0):
        """point is the point as the cuts file gives it (a list, or its JSON text). bound is the seconds a cut's
        functions may take; 0 runs without a bound (needed off the main thread, where SIGALRM is unavailable). The
        model is loaded once per process, by the first scorer."""
        self.ps = PointScorer(task, case, point, rules=None, soft=CUT_TREE_NOROWS, bound=bound, norows=None)

    def score(self, cuts, names=None):
        out = []
        for cut in cuts:
            s = self.ps.score(cut, names).get('soft_score')
            out.append(float('nan') if s is None else s)
        return out
