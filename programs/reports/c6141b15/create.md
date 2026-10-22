# c6141b15

## Departures
- The `stamps-at-line-ends` rule adds "drawn over any joining line": the concept file states no layer order, and the Analyze report's `layer-order` point gives its concept branch as stamps drawn over the lines. The `$LinesOverStamps` branch changes this claim.
- The concept branches take the constructor names `$OneObjectColor` (`line-parse`), `$JoinAll` (`joined-centers`) and `$StampsOverLines` (`layer-order`). `record --all` rewrote the witness file's `concept` groups to these names.
- `$Adjacency4`, `$LineIsLargest`, `$JoinChain` and `bg=SharedColor` have no constructor or `@derive` line: the Analyze report gives each one no witness, and each one fails Fit (train0, test0, train0, train0).

## Judgments
- The objects are `Components8<Color>`, one component set for each color: the concept reads the line and the copies by color. Ids stay separate because the node sets of the colors are disjoint.
- Line uniqueness and copy-color uniqueness are `Unanimous` instances keyed by `LineParse`. A clash leaves `parsed` empty, so the case is undefined. This gives the concept's undefined output on `one-copy` and on `bg=DominantColor`, where two colors each form one object.
- `$LineByStraightness` tests straightness through adjacency: an 8-connected object lies on one line of family A when no two of its cells touch along a direction off A. A pairwise `!same_line` fails to compile, because `same_line` is inline and brings in new variables under negation.
- The joins use one `Ray` cast from the centers: a cell is on a join when it lies on the cast of one center toward D and on the cast of another center toward the opposite of D. `$JoinAll` differs from `$JoinAligned` only by the guard that no two centers are off each other's rays.
- The stamp is the union of every copy translated from its center to each line end. The copies are identical by `shape-copies`, so this equals one copy.
- The `deletions` items that the run leaves as no-ops, other than those removed, are guards that the witness inputs need (`parsed`, `unaligned`, the `!stamp` and `!join` layer tests) or the universal of the determination (`uneven`). `in(T, _)` in `stamp` and `impl_choice` were removed: `out` ranges over `in(P, _)`, and `ready` grounds the case. The `impl_choice` enumerators of `JoinScope` and `LayerOrder` left with it.
- Not formed items give no branch. The hull-order polygon and the center of mass have no relational form, because each reads an angle or a mean about a centroid, which counts nothing the task has. The turned copy states no one model, because train fixes no turn. Stored colors, a stamp at every line cell, and one stamp per copy each fail Fit at train0.
- The determination keeps the color that is the commonest of every input (`Mode` over each example's input). The plan then gave "No actions".
- `derive` gave `bg=DominantColor`, written as `// @derive DominantColor: variant derived` with `@relaxed background`. Its witness is the Analyze file's `bg=DominantColor`. `store` gave no value to store.
- The cases are the 16 combinations of the three choice points and the `bg` derivation. Five are witnessed: the concept and one for each non-concept branch. `witness` reports no unseparated pair and no case left unshown.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-703_task_c6141b15_create.md
