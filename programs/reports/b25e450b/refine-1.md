# b25e450b

## Departures
- `Extent` stands under `$AwayFromNearestEdge` (`AwayFromNearestEdge {e: Extent}`), not at the top level (create): `$SweptOnly` alone is equivalent to the concept, so the track-extent property exists only with `$AwayFromNearestEdge`. Holds: under `$TouchedEdge` every block starts at one edge, under `$Diagonal` it crosses to the opposite corner, and under `$SpanStays` and `$PerLine` the band and the swept cells are the same.
- `Paint` stands under `$OfBlockColor` (`OfBlockColor {t: Paint}`) (create): `$RecolorTrack & $NonFieldColor` is equivalent to `$NonFieldColor`, because under `$NonFieldColor` every cell is of a field color or a block cell, and `$RecolorTrack` paints both. Holds.
- `impl_choice` holds 28 cases: the concept case; each `$Block(_, _, $Diagonal, $SpanStays)` case with `$AwayFromNearestEdge` (either `Extent`) and any `BlockCells`; and `$PerLine` with `$TouchedEdge` and any `BlockCells` (create). Each other `$Block` case fails Subsumption: `$TouchedEdge`, `$CornerUndefined` and `$SpanUndefined` only narrow where the model is defined. So the single-branch models of `$Mirror`, `$EightConnected`, `$RecolorTrack`, `$NonFieldColor`, `$AwayFromNearestEdge`, `$Diagonal` and `$SpanStays` are not cases. Holds: `witness b25e450b --every-case` prints "fails Subsumption" for each dropped case it runs, and `dropped cases: ok` in the audit.
- `$PerLine` with `$AwayFromNearestEdge` is not a case, because it fails Fit at train0 (create, with its fact corrected here). Under that reading, the column-0 run at rows 1–3 has the top end as its nearest end, so it moves to the bottom end, rows 7–9, where the output has 7 5 7. The solver's `$PerLine` clauses never read `Heading`, so `--every-case` on the solver does not show this. A scratch copy of the solver with clauses for the combination (each run moves away from its nearer end, undefined at a tie, and the track is the run's line, or the cells from the run onward under `$SweptOnly`) gives, under `--every-case`, "fails Fit: at `train 0` it gives no output the pair accepts" for each of the 6 `$PerLine & $AwayFromNearestEdge` cases. Holds.
- Added branches `$Diagonal` (under `Corner`) and `$SpanStays` (under `Span`), both nested in `$Block`, from the Not formed item on blocks that touch two edges, with witnesses `corner-block` and `span-block` (create). Holds: every case that takes them fits every pair.
- A landed cell takes the color of the block cell that moved there (create). Under the concept this color is `block_color`, so the `block-on-top` text is kept.

## Judgments
- Reading of `$Diagonal` (create): a block whose heading is read from two adjacent edges moves away from both, to the opposite corner, with a track along each axis. Under `$Mirror` it flips on both axes. `corner-block` is `borderline` with verdict `$Diagonal`: a generator that places holes at an edge can place one at a corner.
- Reading of `$SpanStays` (create): a block whose heading is read from two opposite edges stays in place with no track. `span-block` is `foreign`: the generator's blocks do not reach the opposite edge. On that witness `$PerLine` gives the same grid as `$SpanStays`.
- Another reading of the corner item, where a corner block moves along one axis, is not formed (create). With the axis as an open parameter, the two open values disagree on every corner block, so the model is undefined wherever the concept is undefined. It is equivalent to the concept, and it fails Equivalence.
- Not formed item on blocks that stop on a landed block (create): an order among the blocks as an open parameter fails Fit at train2. If the bottom block (col 2) slides first, it reaches rows 0–1, as the output shows. If the right block lands first at rows 6–7, cols 0–3, the bottom block stops at rows 8–9.
- Not formed items on other color proposers and on `field-colors` (create): `derive` lists no fitting derivation, so no `@derive` line is written. `store` and the audit's derive and store checks report nothing to add.
- New witnesses `floating-corner-touch`, `floating-corner-touch-3` and `floating-shape` in the witness file. They make 8 more cases witnessed, so 18 of the 28 cases now run in every check: `$EightConnected & $SweptOnly`, `$EightConnected & $NonFieldColor`, `$EightConnected & $SweptOnly & $NonFieldColor`, `$SweptOnly & $NonFieldColor`, `$Mirror & $SweptOnly`, `$Mirror & $NonFieldColor`, `$Mirror & $SweptOnly & $NonFieldColor` and `$SweptOnly & $RecolorTrack`. Each holds a block that touches no edge, so each breaks `edge-blocks` and is `borderline`, and the concept is undefined on it. Its verdict is `$AwayFromNearestEdge & $SweptOnly`, as for `floating-block`.
- The 10 cases that stay unwitnessed each take two branches whose verdicts are all `concept`, among `$EightConnected`, `$Mirror`, `$RecolorTrack` and `$PerLine`, for example `$EightConnected & $Mirror` and `$PerLine & $RecolorTrack`. The docs make such a case unwitnessed: "An output that no case taking only part of the case's non-concept branches gives witnesses no case that takes two branches on which every verdict is `concept`". This settles the create report's open item on the unwitnessed cases.
- The `case section` hint on the `heading_choice` enumerator (create) no longer fires, and the solver carries no `@ignore` for it.
- `$SweptOnly` track (create): the block's band, cut at the block's margin from its source edge (`edge_inset` of that margin). `$Mirror` flips each cell within the block's box on each axis of travel, then applies the move.
- `$PerLine` (create): a `Ray` cast from every block cell along each direction. A run moves where its source cell lies on the edge behind the direction and a blocked cell stops it. The move is the distance from the run's last cell to the far edge. The whole line of a moving run is its track.
- Determine (create): `field_color` is the colors that some cell of every train example keeps from input to output. A single example is not enough: train0 keeps 0 at (1,1) and (1,2), where a landing falls on the block's own cells.
- Hints (create): `common-subexpr` on `out` was fixed by merging the two clauses into a disjunction; `common-subexpr` on `shift` is kept with `@ignore`.
- Deletions: the run lists the same 30 deletions that change nothing as in create, and they are kept, because the pairs do not instantiate the structure they guard: the definedness relations (`pair`, `crowded`, `lone`, `corner`, `span`, `settled`, `stuck`, `undefined`, and the `$Diagonal` and `$SpanStays` clauses), the `$Mirror` flips and `piece(K, P)` there, `inside(P, Ahead)` in `$SweptOnly`, and the field-color test of `$RecolorTrack`. `dir_elem(D)` in `moving` stays, because it narrows the `Dir8` that `Ray` gives.
- Simplify and Prune changed nothing: no clause restates a lib relation, and the comments each state what a reader needs about a relation or a case.
- Keywords (create): `objects lines move cast bbox d4`. `lines` is for `$PerLine`, and `d4` is for `$Mirror`.

## Open
- The verdict of `corner-block` (create): a sibling task with a block in a corner would settle it.

## Lib
- Nearest edge of a box (create): `ArgExtremes<K, Dir>` with `cand(K, D, N) :- box(K, B), dir_elem(D), dist(B, D, N)`, read through `low`. Solver-local form: `nearest` in `programs/solvers/b25e450b.dl`. The grep finds the same shape in `programs/solvers/25d487eb.dl` (`margins`), `programs/solvers/8cb8642d.dl` (`nearest`) and `programs/solvers/9aec4887.dl` (`near`), all of them drafts.

## Fixes elsewhere
- none

## Tickets filed
- 10-280_task_b25e450b_refine.md
- 10-281_task_b25e450b_refine.md
