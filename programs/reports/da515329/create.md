# da515329

## Departures
- The solver has the concept case alone. `$TakeTurns`, `background=DominantColor` and `wall_color=stored` have no case: Develop reached its budget before they were added. Their entries are under Unsettled.
- The witness file holds no witness. Each Analyze witness separates the concept from a branch that has no case, so it separates nothing in this solver.
- The walk grows one arm, and each cell it takes also takes the cell's three images under the quarter turns about the center (`walk.conflict`). The concept grows four arms in lockstep. The two agree wherever `one-plus` holds, because the plus and the lane rule both turn onto themselves under a quarter turn. On `stray-cell-contest` (foreign: it breaks `one-plus`), the solver gives rows 5–7 as `8 0 0 0 8 0 8 0`, `8 8 8 8 8 0 8 0` and `0 0 0 8 0 0 8 0`, which differ from the concept output of `witnesses.json`. This rests on the recursion ban: a `Take` state can only be a value that a static atom grounds, so the state cannot hold four arm tips.
- The walk runs in a square around the center with two extra rings, not on an unbounded plane. Its half-width is the center's distance to the farthest grid edge. Without the two rings, train0 (21,21) is lost, because there a spiral comes back into the grid from outside the square.
- `corridor_width` is no parameter: the lane is the five cells at one step from the new cell, through `neighbor`. A width read from a parameter would need a universal over a variable set of cells inside the walk's recursion, and that needs negation through the recursion.
- In the first version, the output on an input with no plus was an all-background grid. A `center(_)` atom now makes that output undefined, which agrees with the concept output of `witnesses.json` on `background=DominantColor`.

## Judgments
- The `domain-enumerator` hint on `walk.step`'s `dir_elem(H)` is ignored, with an `@ignore` line. `dir_elem(H)` grounds the state, and the recursion rule for `Take` needs that.
- The `take` clause leads with `walk.taken($U(), [P, H], P)`, because the tip of a state is always taken. With the static atoms first, each iteration enumerated the domain, and train0 and test0 reached the 20 s limit. With this atom first, the pairs run takes 7 s.
- A blocked lane is read as `walk.taken ; walk.excluded`. Taken, untaken and excluded together partition the cells, so this is the positive form of "not free" that the recursion allows.

## Unsettled
- `walk_arm` is a `@workaround`: the principled form starts a walk from every arm, and the relabelings audit reports that `walk_arm` changes no output. The four-walk form (`walk.start($U(), [P, D]) :- tip(D, P).`, with `walk_arm` removed) reaches the 20 s per-pair limit on train 0 and test 0, and passes train 1 and train 2. A run of the four-walk form inside the limit would settle it.
- `$TakeTurns` has no case. It cannot use the quarter-turn reduction, because its order breaks the symmetry. It would need a lib construction for a walk whose state holds several tips.
- `background=DominantColor`: the audit reports that `bg=DominantColor` fits and has no `@derive` line. A `// @derive DominantColor: variant derived` line on `bg`, with its witness recorded, would settle it.
- `wall_color=stored`: the audit's store check reports the plus color as 8 on every input. A `@store` line with verdict `concept` (plausibility `variant`) would settle it.
- `deletions` stopped at its timeout, so the Simplify check stays open. A `deletions` run that completes would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
