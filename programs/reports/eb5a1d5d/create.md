# eb5a1d5d

## Departures
- The witness file's group names are in the form `record --all` gives (`$LayersByContainment`, `$Layers4Connected`, `$Concentric` in place of `concept`), and its grids are unchanged from `witnesses.json`: the concept branches at the three points take constructor names of their own (`$Concentric`, `$Layers4Connected`, `$LayersByContainment`), per Write.

## Judgments
- Containment is bounding-box inclusion (`inside`, distinct boxes), not interior: `flush-inner` needs the concept to give 8/3/2 where the 2 rectangle touches its container's edge, and that holds only with non-strict inclusion. Depth is the `Order` rank over that strict partial order. Siblings share a rank, so two colors fall on one ring and the concept is undefined, as `sibling-rectangles` requires.
- The square of rings is built without arithmetic: its center is `uniform_inset(deepest depth)`, its cells are two `jump`s of a depth each from the center, and a cell's ring k is `inside` the box inset by k and not in its `interior`. `ring_width` scales that square through `Frame2D` and `concat_2d`.
- The score branches take depth as `rank_desc`, the count of layers with a larger score. A tie of two layers of one color still gives a defined output, where `analyze.md` says the branch is undefined on any tie. No witness depends on this.
- `$CompressRuns` collapses rows and columns at once, through runs of identical neighboring lines (`Canon`) laid out by `OrderFrame`. This is equal to the sequential collapse, because two columns are identical before rows collapse exactly when they are identical after.
- Determine: the sweep keeps `ring_width` at 1 alone, and `derive` finds no built-in derivation. The plan asks for a determination relation only for a value that a proposer derives from another fact, and no proposer derives one, so the solver has no Determine comp. `ring_width` 14 to 27 timed out in the sweep. Those values are far outside the pairs' outputs.
- 7 cases are enumerated and 5 are witnessed. `$Layers8Connected` combined with `$LayersByCellCount` or with `$LayersByBboxArea` takes two rejected branches, so the runner does not count those combinations as witnessed. `witness` and the audit report no unseparated pair and no unwitnessed case.
- Deletions kept: the `line_differs.a` column and `perp(A, A2)` in the `$CompressRuns` `out` clause. Both state the axis of a line, which the position alone implies only by its zeroed coordinates. I removed the redundant `impl_choice`, `domain`, `dir_elem` and `axis_of` atoms.
- Hint `single-consumer` on `layer_color`: I inlined the relation into `out`.
- Keywords: `objects rings rank count bbox lines`. `count` and `bbox` are for the score branches, and `lines` is for `$CompressRuns`.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
