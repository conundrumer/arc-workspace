# Normal-form owner handover

The completed functional-lib run has mutants normal 101,337/non-normal 14,376/unavailable 671 and gold points normal 14,429/non-normal 101/unavailable 6. The total increase does not mean the lib rule failed: the authenticated run-2 reconstruction exactly reproduces 14,393/100/43. Its 75 changed points and reasons are listed in review/run2-run3-diff.md and DATA_ROOT/ast/run/mech2/gold-run-diff.json. Prior per-point records were overwritten, so the previous states are marked reconstructed; original cache history was not retained. The comparison is also linked from the data summary.

Transitions: 26 non-normal to normal, 3 non-normal to unavailable, 24 unavailable to non-normal, 16 unavailable to normal, 6 normal to non-normal. Thus 100-26-3+24+6=101. All expected-clear task IDs have no remaining gold failures; the cited retained failures remain. Six new failures (two points of 03560426 and four of 95a58926) have a multi-row projection in the additional point-prefix snapshot; full replay alone appeared one-row. Other transitions reflect form-span fixes, spatial widths, and the functional-lib rule. The retired/repository writer definitions differ only in one_row_component; the imported encoder additionally changed Position/Offset width from one scalar to four margins. Constraint set remains normal, not normal2/normal3.

Actual cache defect fixed this turn: cached body-column mappings now retain/replay their transitive unavailable warnings. Previously cache hits could lose uncertainty. The runner archives prior gold point snapshots in gold_point_history before replacement, summarizes point transitions, and stores non-one-row components on gold failures. No writer policy was loosened to force a target count.

After merging this worktree, run the full stored-data normal pass:

```sh
/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --need soon --cpus 1 /Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python /Users/davidlu/code/arc-workspace/model/study/ast/run/mech2/classify_normal.py
```

This run is needed for the cache correctness fix and new failure receipts. No pair-program evaluations or tests were run here. The historical stored-gold audit took about 23 seconds; its source and encoder references were hash verified and its counts matched the previous run. Review script reconstruct_gold_runs.py deliberately requires the old run-3 database and its pinned source commit. It compiles selected historical definitions for that audit without importing retired modules into the current labeler.

Owner notice sent to n-mech as 7710009. Next owner message request ID: 7710010. Current counts are from before the cache repair; do not predict the next count from aggregate subtraction. Git staging may require the coordinator because index.lock has been blocked by the sandbox.

Syntax parsing and git diff --check passed. Git staging/commit failed at .git/worktrees/n-mech2/index.lock, so the coordinator must commit/merge externally. Commit message: Preserve normal mapping uncertainty and audit gold-point transitions.
