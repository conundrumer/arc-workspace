# cdecee7f

## Departures
- The `ten-dots` witness is a second witness of `$FitSquare` (borderline, verdict `$FitSquare`).
- The `raster-path` `assign` of `fill_order` is rewritten from rank/position facts into the Grid form `[[0,1,2],[3,4,5],[6,7,8]]`, because the solver stores `fill_order(p, r)` with a `GRID_3x3` call.

## Judgments
- The snake path is a walk over (cell, heading) states, a `GraphDistance` instance keyed by canvas. A state steps along the line while it is off the far edge (`!dist(P, D, 0)`). At the far edge it steps one line across and reverses. A cell's place on the path is its distance from the seed at the `fill_corner` cell. No parity arithmetic is needed, and the path follows `fill_corner` and `fill_axis` under D4.
- Ranks: `Order` with `before` set to "nearer the scan edge". Under `$LexTie`, a second `Order` breaks a tie by the distance from `tie_dir`. Under `$OneRank`, the explicit guard `tied` makes the concept undefined on a tie, including a tie between two dots of one color, which would otherwise give a defined grid.
- Under `$FitSquare`, the size has a relational form: a square frame for each side up to the input's extent, a `Tally` of each frame's cells, and `Extremes.low` of the sides whose cell count is at least the dot count. No square root is computed.
- `fill_order` is a lookup table: its keys are ranks from the input, and train2 shows all 9 of them. So it stays the `$StoredPath` constructor rather than a `@store` line.
- `store` printed `@store` lines for `least.low` and `least.cand`. I ignored both. A stored side gives the `$StoredSize` model at a square `out_size`, which subsumes it. A stored candidate set is read only through its least member, so it stores the same thing as `least.low`.
- In the sweep, `tie_dir` also admits L and R. They were not stored: a tie between two dots in one column cannot be broken by distance from the left or right edge, so no reader of the concept takes those values.
- Determine: the plan listed `bg` (DominantColor) and `out_size` (ConstOutDimAxis), and I wrote relations for both, as c8b7cc0f does. The plan also listed `fill_axis`, `fill_corner` and `scan_dir`, but their proposer is the enumerated domain and they need no clauses.
- Deletion report: `tied`, the `$LexTie` tie disjunct, `params.fill_axis(A)` in `walk.edge` and the `axis_dim` disjunct of `side` were kept. The pairs never tie, never reach a state on the other axis and never need a full-size square, but each of these states part of a claim. The two `Tally` `domain` rules and the `impl_choice` atom in `out` were removed. `impl_choice` stays declared, because the cases are not every combination of the fields.
- Keywords: `objects rank walk count`, with `count` coming from `$FitSquare`.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
