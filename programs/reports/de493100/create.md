# de493100

## Departures
- `hidden-picture-corner` is removed from the witness file, and the header has no `@approximated:` line: analyze.md calls this witness `foreign`, so `mask-recoverable` is a constraint of the generator. On every input the generator produces, `fill-from-mirror` therefore agrees with the generator's rule. Every case is undefined on the witness, so it separates no cases.
- The Params relation `picture_corner` (DIAG_TL) is added beside `picture_size`: the concept's "crop at the bottom and right" is an orientation, so the program cannot fix it. The same corner anchors the 2 × 2 `tile_groups` table to the quarter it describes.
- The Params relation `side_group` (SYM_BOX) is added: the program reads the group of the side mirrors for the tile keys and for `$DiagonalFallback`, and literals are banned.
- `$FoundAxes` looks for each center line only among the placements of a 32-line picture that holds the grid. It does not search every mirror line of the grid. It is not undefined where the row and col lines lie at different distances from the grid's corner: the picture frame stays square, so the diagonals are still defined there. No witness tests either difference.
- New witness `broken-side-mirror` (foreign, verdict `$DerivedTileGroups`, `@relaxed side-mirrors`): `witness` reported that no run showed `$DerivedTileGroups` defined and different from `$DiagonalFallback`. On this witness the mask's tile loses its vertical-line mirror, and the masked cell's side images disagree. `$DerivedTileGroups` gives the original content, which is what the generator's picture holds there. The other readings find two colors.
- New witness `stray-cell` (foreign, verdict `concept`, `@relaxed side-mirrors`, under `$MaskFromAsymmetry`): `witness` reported that no run separated `$MaskByShape` from `$MaskFromAsymmetry`. One recolored cell breaks a side mirror away from the mask. `$MaskFromAsymmetry` finds no color that every mismatch carries, and the concept and `$MaskByShape` give the hidden content.

## Judgments
- The concept case and all three branch points fit every pair. Of the 18 combinations, 6 cases are witnessed.
- The precedent is 0934a4d8: a stored per-tile group, a margin from the grid to the picture frame, and a determination that uses a one-sided mirror extension. The tile groups are keyed by the quarter's 2 × 2 tiles, as the concept file gives, and a tile's side-mirror image in the quarter at `picture_corner` maps to its key.
- `@derive TileDim` on `tile_size` is held as `@ignore: derive TileDim`. On a 30-wide input it gives several sizes at once. With the derived groups, the tiles conflict at train0, so that case fails Fit. With the stored groups, no input of the task or of the witness file showed an output other than the concept's, so that case fails Subsumption.
- `store` reported that `margin` has one value on every input with no witness. It gets `@ignore: store`, because `picture_size` and `picture_corner` already store it under `$StoredCorner`.
- The sweep reports that the train pairs do not pin `tile_groups` (52 single-row changes fit). analyze.md determines the groups from the inputs, so the parameter is not open. The determination derives them from the inputs.
- The 5 "determine prediction" hints were kept. Each one fires because a relation reads the determined `mask_color`, which tests the outputs (the color is in no output). The value that relation keeps comes from a fact of the inputs alone, with the mask's cells left out.
- The `comp-idiom` hints on `tile_broken` and Determine's `broken` (`D4Map.conflict`) were kept with `@ignore`: the tile groups need the broken cell, and D4Map gives only a per-key verdict.
- Case-section hints were resolved: the mask candidates, placements and picture cells are now keyed by the `Mask` branch, so each case reads only its own branch's facts.

## Unsettled
- `deletions` stopped at its 120 s timeout: rerun `uv run python scripts/run_dl.py deletions de493100` with a longer bound.
- Simplify was not done, because the pass was past its target. The `$FoundAxes`/`$MaskFromAsymmetry` placement search over every input color (`axis_pair`) is the largest relation and the likely cause of the slow `store` and `deletions` runs.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
