# bf45cf4b

## Departures
- The `$MaskByColor` encoding checks that the non-background cells outside the tile share one color, using a `Unanimous` instance. Without that check, the branch would be defined on inputs where the Analyze report gives it as undefined.
- `$Parse4Adj`, `$TileByCellCount` and `$TileBySmallerBox` have no constructors. The Analyze report gives them no witness, and each one fails Fit. Because of that, the `tile-pick` choice point has no type in the solver.

## Judgments
- The concept branch constructors are named `$Connected`, `$MaskCells` and `$TileCells`. The witness file does not use the concept branch names, and `record --all` wrote those names into it.
- All eight combinations of the three branches are cases, and the run passes all four pairs. Each combination that takes two non-concept branches gives the output of a case that takes only one of them, so only four cases are witnessed. The audit reports nothing open.
- The background is derived as the commonest color with `Mode`, and it is not stored. The four inputs have four different backgrounds (4, 3, 1, 8), so a stored value fails Fit. `derive` and `store` report nothing.
- The tile and the mask are each the unique object of their kind (`rival_tile`, `rival_mask`). `deletions` reports that removing either test changes no pair. I kept both:
    - At `mask-in-two-pieces`, `rival_mask` makes the concept undefined, as the Analyze file requires. Without it, the concept would take the union of the two pieces and give the `$MaskByColor` output.
    - `rival_tile` states the scene claim that the tile is the other object of the two.
- `deletions` also reports two atoms in `tile_cell($TileCells(), …)`. Removing them makes `$TileCells` equal to `$TileBoxCrop`, and the witness `mask-cell-in-tile-box` separates those two cases. I kept the atoms. I also merged the shared `tile(Id)` atom out of the disjunction.
- I removed `tile(_)` from `mask($MaskByColor(), P)`. The output already reads the tile through `tile_cell`, so that atom was redundant.
- The `rest_hue.value` atom stays, although the pairs never exercise it. It is the definedness condition of `$MaskByColor`.
- Not formed: no item gives a case.
    - A stored background fails Fit.
    - A tile chosen by its square box is undefined at train2.
    - Stamping the tile on the mask's empty cells contradicts every pair.
    - A D4-transformed or recolored tile, and a block size other than the tile's size, give no model that differs from the concept on the pairs.
- Keywords: `objects scale stamp bbox crop tile-arrangement`.
- Lint gave no hints.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
