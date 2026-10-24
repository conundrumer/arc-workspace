# cdecee7f

## Departures
- Every non-concept case that takes `$OneRank` left under Subsumption, so `impl_choice` holds the concept case and every combination of `$LexTie` with a dot unit and a fill path, 10 cases in all: `witness` reported that no run shows `$FitSquare` (`$OneRank & $FitSquare`) or `$Objects` (`$Adj4 & $OneRank`) defined and differing from its `$LexTie` twin. No such input exists. Where `$OneRank` is defined, no two dots tie, so `$LexTie` ranks them the same way, and `$LexTie` is also defined on ties. Each later stand-in that takes `$OneRank` is subsumed in the same way, so I removed all of them at once. The concept case is exempt. So `$Objects`, `$Diag8`, `$FitSquare`, `$StoredPath` and `bg=DominantColor` are now each stood for by the case that also takes `$LexTie`.
- `// @ignore: derive $OneRank` stands under the `@derive DominantColor` line: the one case that takes `bg=DominantColor` together with `$OneRank` is subsumed by the same case with `$LexTie`.
- `$Overflow` was dropped, with its `Surplus` choice point: it fails Subsumption, as `analyze.md` states. Each case that takes it gives the output of its `$Drop` twin wherever it is defined. `witness` reported the `$Overflow` case, and every other case with `$Overflow` is subsumed the same way. The `ten-dots` witness stays, now as a second witness of `$FitSquare` (borderline, verdict `$FitSquare`), and its `separates` text no longer mentions `$Overflow`.
- `$MixedObjects` was dropped, with its `object-color` choice point: it fails Subsumption, as `analyze.md` states, and `witness` reported it. Its only witness, `touching-two-colors`, separated nothing else and was removed. `$Objects` now carries only the `adj` field.
- The `raster-path` `assign` of `fill_order` is rewritten from rank/position facts into the Grid form `[[0,1,2],[3,4,5],[6,7,8]]`, because the solver stores `fill_order(p, r)` with a `GRID_3x3` call.
- `witness --file programs/reports/cdecee7f/witnesses.json` can no longer compare branch outputs: after the departures above, the branch models other than the concept and `$LexTie` are not cases. It also reports the old `assign` form of `raster-path`. In the run before the cases were removed, every branch model's output matched `witnesses.json`, and the only mismatches were groups that `witnesses.json` cannot list (the `$LexTie` combination cases).

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
- The Subsumption cascade means no case gives the plain branch model of `$Objects`, `$Diag8`, `$FitSquare` or `$StoredPath`: each is paired with `$LexTie`. Settled by a confirmation that Subsumption against a twin that only adds a tiebreak is meant to remove a branch's own model.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
