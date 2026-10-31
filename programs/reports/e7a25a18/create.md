# e7a25a18

## Departures
- `$UniformScale` has no constructor, and `oblong-frame` is gone from the witness file: no input shows `$UniformScale` defined and giving an output other than the concept's. Where both axes' ratios agree, the outputs are the same, so it fails Subsumption. `analyze.md` says the same.
- `$QuadrantFill` with the stored `parts` = 2 is not a case. Its point (`part count`) is collapsed, so the fill branch is one constructor, `$BlockGrid`, and the verdict of `quadrants-off-scale` is `$BlockGrid`. `nine-cell-pattern` is gone from the witness file: no run shows `$StoredParts` defined and differing from `$BlockGrid`, so it fails Subsumption, as `analyze.md` says. Once it left, `nine-cell-pattern` separated nothing. `parts` left Params and Determine, because no case reads it.
- `scale=stored` is an `@ignore: store` line, not a case. Its model in the solver keeps the program, which tiles the frame's inside by the stored scale. That model is undefined wherever the stored scale differs from the derived one, so it fails Subsumption. `analyze.md` gives it another model, which sizes the output from the scaled pattern. A `@store` branch does not change the program, so that model has no place in the solver. The witnesses `scale=stored` and `oblong-frame` left the witness file.
- Witness `field-of-seven` was added for `background=DominantColor`. Before it, no run showed the cases `$FrameByOutline & background=DominantColor` and `$BlockGrid & background=DominantColor` defined and differing. Under a 7 field, the commonest color is 7, so the whole inside is the pattern and the crop is unchanged. With the stored 0, the pattern is the top half, and the 7 ring is a second outline for `$FrameByOutline`.
- Concept-branch constructors: `Scaled`, `ByColor`, `InsideFrame`.

## Judgments
- `field-of-seven`: plausibility `borderline`, verdict `concept`. The field is 7, not 0, which breaks `one-frame` at the stored background. The lower half of the inside is 0, which a person could read as the pattern's empty half or as background. The concept's reading, with 0 as the background, gives the top half scaled 2 down and 1 across.
- The derivation `parts=TileCount` was dropped before `parts` left. It gave `$BlockGrid`'s output on every input tried, including a 9×9 grid, so the two cases were equivalent there. Of two cases with equal non-concept counts, the derivation left. `parts=TileDim` had no witness.
- Scale is per axis, from `tile_size` over the inside's and the pattern's extents. `Tile2D` maps each inside cell to its pattern cell. This uses no arithmetic.
- `$BlockGrid` counts blocks per axis by defect negation. A count is valid when, within each slab along the axis, every line is the same. Valid counts on both axes give single-color tiles. `Extremes.low` picks the fewest blocks.
- A pattern part with two colors, or two frames, gives conflicting `out` facts, so the case is undefined there. No uniqueness test is written.
- Deletions that change nothing: the outline's non-background test and `interior` test, `sub_extent`, `block_defect.a`, the divisibility atom in `block_count.cand`, and the determination's defect rules. Each states part of its claim, and the pairs do not instantiate that part. All are kept.
- Determination: `background` is the commonest color of every input (`Mode`). `frame_color` is the one color of every output's border cells. `determination-plan` reports no actions.
- Hints: the case-section hints on the shared clauses were resolved by moving those clauses above the first case marker. The single-consumer hint on `part_col` was resolved by inlining it.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
