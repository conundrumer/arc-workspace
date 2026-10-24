# da515329

## Departures
- The `background=DominantColor` (@derive) and `wall_color=stored` (@store) branches have no directive line in the solver. The witness file still uses their Analyze names, and the run reports that those names "denote no case of the solver": I did not reach Develop step 5 (`derive`, `store`) before the coordinator's override stopped the pass.
- The other non-concept branches of `analyze.md` (`$OneArmAtATime`, `$Lane4`, `$SquareRings`, `$LengthTable`, `$EndAtEdge`, `$EdgeIsWall`) have no constructor: each fails Fit in `analyze.md`, and none has a witness.

## Judgments
- The parse finds the plus with lib relations. The center is the background cell with every side on the figure. Each arm is a `Ray` from the center, and its tip is the cell before the ray's `stop`. The plus color is the tip's color: the concept reads the color from the input.
- The unbounded plane is cut to a square around the center that reaches one cell past the grid's farthest edge (`Extremes` over the edge distances, then `Bbox`, then `Frame2D`). A lap that leaves this square lies past every grid edge, so the clip is exact. The square is a construction of the plane, not a task number.
- The lane of `hug-the-spiral` is the cells within `corridor_width` of the entered cell, apart from those behind it. For width 1 these are the 5 cells ahead and beside, the diagonals ahead included, as `analyze.md` gives for the concept's `lane neighborhood`.
- `$AtOnce`: the four arms' cells at one step are C4 rotations of one another about the center. So an arm grows against the rotations of its own trail, and one `Take` walk from all four tips encodes simultaneous growth. This relies on the plus being symmetric (`one-plus`). On an input that breaks `one-plus` (the `stray-cell-contest` witness), the reading may differ from a literal simultaneous growth. I did not check this, because the witness run never happened.
- `$TakeTurns`: one chain of moves in which the arm that moves next is the one that moved three states back, starting from `first_arm` = up in `sense` order. `first_arm` is a parameter of that branch alone.
- Hints from the last clean lint run (on the version before the final rewrite): `single-consumer` on `plus_color` (I would keep it with `@ignore`, since it is the color `clip` names), `head-repeat` on `cands` (D appears as both the head and the straight move's heading; I would keep it, since the straight move's heading is the head's), and `common-subexpr` across the `turns` clauses (the final rewrite removed those clauses). I did not apply any of these judgments in the file.

## Unsettled
- The solver does not pass. The file as it stands (the last rewrite: `Take` with a static `take`, each walk driven by `step`) has not been run through the runner. By hand, `souffle` on test0 was terminated at 200 s. The last runner result, `uv run python scripts/run_dl.py da515329` on the previous version (state = a `Window` record of four heads, a `take` with `excluded` tests): train1 and train2 PASS (2 witnessed cases), train0 and test0 FAIL ("the run exits with -9"). The `$AtOnce` walk alone (scratch variant /tmp/claude-0/-home-user-arc-workspace/95a9e697-9cd5-54be-be82-90365100c496/scratchpad/da515329_once.dl) passes all four pairs in 16 s. The `$TakeTurns` walk alone fails train0 and test0 the same way. What would settle it: a `$TakeTurns` encoding, or a lib walk component, whose state set does not cross every move with every state. Otherwise, a `@workaround` that bounds the walk.
- That previous version also had a lint finding: banned type `Window`. The final rewrite removes `Window`, but no lint has run on it.
- Develop steps 3 to 6 were not done: `derive`, `store` and `audit` were not run. Determine was not done: `sweep` and `determination-plan` were not run, and `.comp Determine {}` is empty. Witness, Simplify (`deletions`) and Prune were not done either. No witness has been recorded, and `uv run python scripts/run_dl.py witness da515329 --file programs/reports/da515329/witnesses.json` has not been run.
- Whether `$TakeTurns` fits every pair in this encoding: in the previous version it fit train1 and train2. It is unknown on train0 and test0.

## Concept faults
- none

## Fixes elsewhere
- `scripts/run_dl.py`, the "exits with -9" report: say whether a time limit or a memory limit ended the run, and give that limit.
- `scripts/run_dl.py run --help`, the profiling recipe: the PreToolUse hook blocks its `{ ... } > file` group, so the recipe needs a form an agent can run.

## Tickets filed
- none
