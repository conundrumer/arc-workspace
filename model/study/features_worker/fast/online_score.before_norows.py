"""The hard keys and soft score of one sampler draw, for a sampler that scores its draws as it makes them.

    from online_score import PointScorer
    ps = PointScorer(task, case, point)          # once per point: ~40 ms
    r = ps.score(draw, names)                    # per draw
    r -> {'hard_keys': [...], 'passes': bool | None, 'soft_score': float | None, 'kind': str, 'errors': [...],
          'values': {column: value}}

Runtime: /Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python, with this directory on sys.path.

`draw` is a row in the format of the sampler's draws file: `clause`, `x`, `x_rows`, and `fail`, `static` and
`out_reads` where the sampler has them. `names` is {sampler relation name: program name} for the relations of the
point's prefix (`&r18` -> `&bg`), as `draw_features.py --names` takes it.

`passes` is False where the sampler failed the draw, its static check matched a class other than `valid`, or a hard key
fires; None where the bound cut a rule function and no finished one fired. `soft_score` is given only for a passing
draw that the bound did not cut. Only the functions of the rule file and of the soft model run.

The rule file and the soft model default to fixed versions (RULES, SOFT); a new version of either is a new file.

A cheap score for partial clauses: `PointScorer(task, case, point, rules=None, soft=SOFT_NOROWS)` checks no hard keys and
runs only functions that read no X rows. Its `needs_rows` is False, so a draw may come with `x_rows` empty.
"""
import signal
import sys
import time
from pathlib import Path

HERE = Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/fast')  # the data folder
sys.path[:0] = [str(HERE), '/Users/davidlu/code/arc-workspace/model/study']
import rulecheck  # noqa: E402
from rulecheck import RuleCheck, rename_relations  # noqa: E402
from rulecheck_draws import POINTS, point_dirs  # noqa: E402
from draw_features import SOFT_DEFAULT, Bound, _alarm, flat, static_prune  # noqa: E402
from featlib import FEATURES, no_gc  # noqa: E402

_SP = Path('/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad')
RULES = _SP / 'explore/rules/rules-v9.txt'
CLASSES = _SP / 'explore/rules/rules-v9-classes.tsv'
SOFT = _SP / 'soft/deploy/soft_gold_v11.npz'
# A score for partial clauses: 25 functions that read no X rows (no hard rules: pass rules=None)
SOFT_NOROWS = _SP / 'fast/lin_norows.npz'
# The tree ranker (gradient-boosted trees over the same columns), as a soft model: pass soft=SOFT_TREE
SOFT_TREE = _SP / 'tree/tree_v12.pkl'
SOFT_KEYS = frozenset(SOFT_DEFAULT.split(','))

# The feature functions whose values do not change when X's rows are removed (checked on runN_d draws)
NO_ROWS = frozenset([
    'a2_zero_sites', 'b1_degenerate_generator', 'b2_degenerate_filter', 'b5_init_domain_share',
    'b6_prior_clause_overlap', 'c1_color_cols', 'd1_relation_laws', 'd6_join_cut', 'd7_pair_comparison',
    'e1_zero_box_sites', 'e1_zero_frame_sites', 'f4_zero_bound', 'form', 'g1_degenerate', 'g2_comparisons',
    'g3_unread', 'g4_repeats', 'g5_connect', 'g6_reads', 'g7_join_cut', 'h1_degenerate_by_role', 'h2_or_branches',
    'h3_repeated_test', 'j1_ungrounded_cells', 'j2_atom_graph', 'j5_read_age', 'j6_pending_reads',
    'j7_unbounded_numbers', 'l7_join_index', 'q3a_cell_geometry', 'q3b_comparisons', 'q3c_containment',
    'q3d_box_measures', 'q3e_box_algebra', 'q3f_table_reads', 'q3g_components', 'q3h_orphan', 't2_key_partition',
    'u3_frame_clash', 'u5_frame_lost', 'z5_crop_box'])
_soft = {}
_dirs = {}


class TreeScore:
    """A soft model saved by `fit_score.py` (a pickle of cols, prep, clip and a sklearn classifier), with the interface of
    `rulecheck.SoftScore` that `PointScorer` uses; the score is the classifier's log-odds."""

    def __init__(self, path):
        import pickle
        m = pickle.load(open(path, 'rb'))
        self.cols, (self.median, self.mean, self.scale), self.clip, self.clf = m['cols'], m['prep'], m['clip'], m['clf']
        self.functions = sorted({c.split('.', 1)[0] for c in self.cols})
        self._pools = None
        rulecheck.load_feature_modules((HERE / 'features/enabled.txt').read_text().split())

    def score_values(self, vals):
        import numpy as np
        form = vals.get('form.atoms') is not None
        v = np.array([vals.get(c) if vals.get(c) is not None else (0.0 if form and c.startswith('form.') else np.nan)
                      for c in self.cols], dtype=float)
        v = np.where(np.isnan(v), self.median, v)
        z = np.clip((v - self.mean) / self.scale, -self.clip, self.clip)
        if self._pools is None:  # the libraries are scanned once: a `threadpool_limits` call scans them each time
            from threadpoolctl import ThreadpoolController
            self._pools = ThreadpoolController()
        with self._pools.limit(limits=1, user_api='openmp'):  # one row: the thread pool costs ~300 ms, one thread ~2 ms
            return float(self.clf.decision_function(z[None])[0])


class PointScorer:
    def __init__(self, task, case, point, rules=RULES, classes=CLASSES, soft=SOFT, bound=2.0):
        """point is the point as the draws file gives it (a list, or its JSON text). bound is the seconds a draw's
        functions may take; 0 runs without a bound (needed off the main thread, where SIGALRM is unavailable)."""
        import json
        key = (task, case, point if isinstance(point, str) else json.dumps(point))
        for _ in range(3):  # a point that a running build has just finished may appear a moment later
            if key in _dirs:
                break
            _dirs.update(point_dirs({task}))
            if key not in _dirs:
                time.sleep(1)
        if key not in _dirs:
            raise KeyError(f'no point directory under {POINTS} for {key}')
        # rules None: no hard keys are checked (a score-only scorer, such as a cheap score for partial clauses)
        self.rc = RuleCheck(POINTS / _dirs[key], rules if rules is not None else [], classes)
        if soft not in _soft:
            _soft[soft] = TreeScore(soft) if str(soft).endswith('.pkl') else rulecheck.SoftScore(soft)
        self.soft = _soft[soft]
        rule_fns = [n for n in self.rc.functions if n in FEATURES]
        self.rule_fns = rule_fns
        self.other_fns = [n for n in self.soft.functions if n in FEATURES and n not in set(rule_fns)]
        self.bound = bound
        # needs_rows: whether the functions run read X's rows; without them a draw may come with `x_rows` empty
        self.needs_rows = not set(self.rule_fns + self.other_fns) <= NO_ROWS

    def score(self, draw, names=None):
        with no_gc():  # the collections that a draw's allocations trigger scan the whole heap; the garbage goes after the draw
            return self._score(draw, names)

    def _score(self, draw, names):
        if not draw.get('clause') or not draw.get('x') or (self.needs_rows and not draw.get('x_rows')):
            return dict(hard_keys=[], passes=False, soft_score=None, kind=None, errors=['no clause'])
        rc = self.rc
        clause = rename_relations(draw['clause'], names)
        x = rc.draw_x(draw if self.needs_rows else dict(draw, x_rows=[]), clause)
        cand = rc.candidate(clause, x, out_reads=rc.gold_out_reads(clause) if draw.get('out_reads') is None
                            else draw['out_reads'])
        failed = bool(draw.get('fail') or static_prune(draw))
        vals, bad, cut_at = {}, [], None
        if self.bound:
            signal.signal(signal.SIGALRM, _alarm)
            signal.setitimer(signal.ITIMER_REAL, self.bound)
        try:
            fns = self.rule_fns + ([] if failed else self.other_fns)
            for k, name in enumerate(fns):
                if k == len(self.rule_fns) and any(c in rc._rule_set and c not in SOFT_KEYS and rulecheck._fires(v)
                                                   for c, v in vals.items()):
                    break  # a hard key fires: the other functions are not needed
                cut_at = k
                try:
                    v = FEATURES[name](cand)
                except Exception:
                    bad.append(name)
                    continue
                vals.update(flat(name, v))
            cut_at = None
        except Bound:
            bad.append('bound')
        finally:
            if self.bound:
                signal.setitimer(signal.ITIMER_REAL, 0)
        hard = sorted(k for k, v in vals.items() if k in rc._rule_set and k not in SOFT_KEYS and rulecheck._fires(v))
        passes = not (failed or hard)
        if passes and cut_at is not None and cut_at < len(self.rule_fns):
            passes = None
        soft = self.soft.score_values(vals) if passes and 'bound' not in bad else None
        out = dict(hard_keys=hard, passes=passes, soft_score=soft, kind=cand.kind, errors=bad, values=vals)
        cand.__dict__.clear()  # the view holds itself (its `dir` has a bound method of it): its tables go now, not at a collection
        return out
