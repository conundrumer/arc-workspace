# b25e450b

## Departures
- `Extent` stands under `$AwayFromNearestEdge` (`AwayFromNearestEdge {e: Extent}`), not at the top level: the audit reported that `floating-block` is no witness of `$SweptOnly`, because `$SweptOnly` alone is equivalent to the concept (the Analyze report says so too). The track-extent property exists only with `$AwayFromNearestEdge`, so the point stands under that branch.
- `Paint` stands under `$OfBlockColor` (`OfBlockColor {t: Paint}`): `$RecolorTrack` & `$NonFieldColor` is equivalent to `$NonFieldColor`. Under `$NonFieldColor` every cell is of a field color or a block cell, and `$RecolorTrack` paints both.
- `impl_choice` holds 28 cases: the concept case; each `$Block(_, _, $Diagonal, $SpanStays)` case with `$AwayFromNearestEdge` (either `Extent`) and any `BlockCells`; and `$PerLine` with `$TouchedEdge` and any `BlockCells`. Each other `$Block` case fails Subsumption. `$TouchedEdge`, `$CornerUndefined` and `$SpanUndefined` only narrow where the model is defined, so each such case gives, wherever it is defined, the output of its copy that takes `$AwayFromNearestEdge($Band)`, `$Diagonal` and `$SpanStays` in their place. `witness --every-case` confirms this for each dropped case it runs. As a result, the single-branch models of `$Mirror`, `$EightConnected`, `$RecolorTrack`, `$NonFieldColor` and `$AwayFromNearestEdge` in the Analyze report are not cases. `record --all` rewrote the witness file's names to the cases that stand for them, and `witness --file work/task/b25e450b/witnesses.json` reports no difference.
- `$PerLine` with `$AwayFromNearestEdge` is not a case, because it fails Fit at train0. The column-0 run at rows 1–3 has the top end as its nearest end, so it moves to rows 0–2, and the output has 7 at row 0, col 0.
- Added branches `$Diagonal` (under `Corner`) and `$SpanStays` (under `Span`), both nested in `$Block`, from the Not formed item on blocks that touch two edges. They come with witnesses `corner-block` and `span-block`.
- A landed cell takes the color of the block cell that moved there. Under the concept this color is `block_color`, so the `block-on-top` text is kept.

## Judgments
- Reading of `$Diagonal`: a block whose heading is read from two adjacent edges moves away from both, to the opposite corner, with a track along each axis. Under `$Mirror` it flips on both axes. `corner-block` is `borderline` with verdict `$Diagonal`: a generator that places holes at an edge can place one at a corner. The axis such a hole moves along is not readable from the pairs, so the verdict rests on reading the block as headed away from both of its edges.
- Reading of `$SpanStays`: a block whose heading is read from two opposite edges stays in place with no track. `span-block` is `foreign`: the generator's blocks do not reach the opposite edge. On that witness `$PerLine` gives the same grid as `$SpanStays`.
- Another reading of the corner item, where a corner block moves along one axis, is not formed. With the axis as an open parameter, the two open values disagree on every corner block, so the model is undefined wherever the concept is undefined. That makes it equivalent to the concept, and it fails Equivalence.
- Not formed item on blocks that stop on a landed block: an order among the blocks as an open parameter fails Fit at train2. If the bottom block (col 2) slides first, it reaches rows 0–1, as the output shows. If the right block lands first at rows 6–7, cols 0–3, the bottom block stops at rows 8–9. So the open values give no common grid.
- Not formed items on other color proposers and on `field-colors`: `derive` lists no fitting derivation, so no `@derive` line is written.
- `store` lists only `landed[col]` and `landing[col]`, which equal the stored `block_color`. So no `@store` line is written.
- `$SweptOnly` track: the block's band, cut at the block's margin from its source edge (`edge_inset` of that margin). `$Mirror` flips each cell within the block's box on each axis of travel, then applies the move.
- `$PerLine`: a `Ray` cast from every block cell along each direction. A run moves where its source cell lies on the edge behind the direction and a blocked cell stops it. The move is the distance from the run's last cell to the far edge. The whole line of a moving run is its track.
- Determine: `field_color` is the colors that some cell of every train example keeps from input to output. A single example is not enough: train0 keeps 0 at (1,1) and (1,2), where a landing falls on the block's own cells.
- Hints:
    - `common-subexpr` on `out` was fixed by merging the two clauses into a disjunction.
    - `common-subexpr` on `shift` is kept with `@ignore`.
    - A `case section` hint on `settled` under `$SpanStays` was fixed: `shift` now takes its domain from `piece`, not from `settled`.
    - `case section` on the `heading_choice` enumerator is kept with `@ignore` (ticket filed).
- Deletions removed:
    - the `impl_choice` atoms in `four.node` and `eight.node`, because every `BlockCells` key is read under both connectivities
    - the edge test in `run.mark`, because `moving` tests the source edge
    - `axis_elem(A)` in the `$Mirror` clause, because `perp` binds `A`
- Deletions kept, because the pairs do not instantiate the structure they guard: the definedness relations (`pair`, `crowded`, `lone`, `corner`, `span`, `settled`, `stuck`, `undefined`, and the `$Diagonal` and `$SpanStays` clauses), the `$Mirror` flips and `piece(K, P)` there, `inside(P, Ahead)` in `$SweptOnly`, and the field-color test of `$RecolorTrack`. `dir_elem(D)` in `moving` stays, because it narrows the `Dir8` that `Ray` gives.
- Keywords: `objects lines move cast bbox d4`. `lines` is for `$PerLine`, and `d4` is for `$Mirror`.

## Open
- 18 of the 28 cases are not witnessed, so no check runs them, for example `$EightConnected & $Mirror` and `$SweptOnly & $NonFieldColor`. A witness on which such a case gives an output that no case taking part of its branches gives would settle it.
- The verdict of `corner-block`: a sibling task with a block in a corner would settle it.

## Lib
- Nearest edge of a box: `ArgExtremes<K, Dir>` with `cand(K, D, N) :- box(K, B), dir_elem(D), dist(B, D, N)`, read through `low`. Solver-local form: `nearest` in `programs/solvers/b25e450b.dl`. The grep finds the same shape in `programs/solvers/25d487eb.dl` (`margins`), `programs/solvers/8cb8642d.dl` (`nearest`) and `programs/solvers/9aec4887.dl` (`near`), all of them drafts.

## Fixes elsewhere
- none

## Tickets filed
- 10-276_task_b25e450b_create.md
