# e9bb6954

## Departures
- `$CrossOnlyPerpendicular` stays as a case. `analyze.md` says it fails Subsumption: it gives that verdict because the branch is undefined wherever two parallel lines meet. The branch is defined where two blocks of one color share a center row, and there it differs from the concept. Witness `same-color-shared-row` shows this: the concept clears the row, and the branch paints the row in that color. Plausibility `borderline`, verdict `concept`, relaxing `separate-lines` and `distinct-block-colors`.
- The `distinct-block-colors` scene line is in the header because `same-color-shared-row` relaxes it.
- `block_size=TileCount` is a held `@derive` branch, and `analyze.md` does not give it. `derive` lists it as fitting. `analyze.md` gives only TileDim and ConstInDim, and both fail Fit. Its cases with `$SquareOccurrence` fail Fit at train0, where the output is the input unchanged. An `@ignore: derive $SquareOccurrence` line records this.
- `cross_color=DominantColor` is a held `@derive` branch, and `analyze.md` does not give it. `derive` lists it as fitting on the `$CrossColorStored` parameter.
- Witnesses added beyond `witnesses.json`:
    - `odd-side-block` separates `$AnySideSquare` from `$Square & block_size=TileCount`: a 5x5 block on a 16x16 grid, whose sides admit no tile count of 5.
    - `zero-colored-block` separates `$CrossColorStored & cross_color=DominantColor` from `background=DominantColor`: a 0 block on a field of 6.
    - `largest-diagonal-run` shows `$LargestComponents & $Components8` defined and differing from `$LargestComponents`.
    - `same-color-shared-row` is described above.
- Two combinations are left out of `impl_choice`. `$AnySideSquare & $SquareOccurrence` would need placements of squares of every side. Inside each 3x3 block, the 2x2 placements overlap, so this combination is undefined on every pair and fails Fit. `$LargestComponents & $SquareOccurrence` takes all placements of one size as equally largest, so its model is `$SquareOccurrence`'s and it fails Equivalence.

## Judgments
- Witness `largest-diagonal-run`: plausibility `ordinary`, verdict `concept`. It is a short noise run of the block's color at the block's corner, the same scene as `diagonal-noise-at-block`.
- Witness `same-color-shared-row`: plausibility `borderline`, verdict `concept`. Same-color blocks that share a row break two scene claims. The concept's crossing rule (lines of two different blocks) then applies as written.
- Witness `odd-side-block`: plausibility `variant`, verdict `$AnySideSquare`, the same as `larger-block`.
- Witness `zero-colored-block`: plausibility `variant`, verdict `background=DominantColor`. With the field recolored to 6, the 0 block is a block.
- `background` and `cross_color` have no determination relation. DominantColor derives each from the field color, and the concept takes the background, and the cleared crossing color, from that same fact.
- `block_size` has a determination relation: the side of the solid square components that every train input holds. This replaces TileCount's tile-count fact.
- `store` hints on `size.tally` and `largest.cand` are dismissed with `@ignore ... store`. The count is 9 only because every block is 3x3, and a stored count adds no reading.
- `store` reports `line[a]` and `blob_cell[p]` with no case. Neither is an interpretation `analyze.md` gives, so neither is held as a branch.
- The 26 no-effect deletions are structure the pairs never instantiate, such as holes, undefined inputs, shielding and same-color lines. The witnesses exercise that structure, so nothing is deleted.
- The TwoBlocks crossing test keeps `Col1 != Col2 ; B1 != B2`. Under `$LargestComponents`, two components of different colors may share a bounding box.

## Unsettled
- The Determine comp repeats the program's component, bounding-box and hole derivation over `ex_in`. That derivation is not moved into `Parse`. Settling it would need the program's block finding keyed by example.

## Concept faults
- none

## Fixes elsewhere
- programs/reports/e9bb6954/analyze.md, the `$CrossOnlyPerpendicular` line ("No witness exists on which the branch is defined"): this is false where two blocks of one color share a line. See witness `same-color-shared-row`.

## Tickets filed
- none
