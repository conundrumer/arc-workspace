# b99e7126

## Departures
- `$CornerBase` reads the pattern that the lattice's four corner tiles share, through a `Unanimous` over every `DiagDir`, and is undefined where the corner tiles differ. The Analyze report reads the top-left tile alone: the task distinguishes no corner, and the relabelings audit found that turning or mirroring a stored `base_corner(DIAG_TL)` changed no output on any input of the task or of the witness file. So the program enumerates every corner, per [Orientation](docs/handbook/principles.md#orientation), and `Params` is empty.
- Witness `marked-outnumber-base` has a new input. On the Analyze input, the bottom-right corner tile is marked, so the corner tiles differ and `$CornerBase` is undefined there, where the Analyze file gives it a grid. The new input is a 3-by-3 lattice: four base corner tiles, five marked tiles in a plus, and a new color that draws the plus with its top-left cell. There the concept is undefined, and `$CornerBase` completes tile (0,0). `witness --file work/task/b99e7126/witnesses.json` lists the Analyze file's `$CornerBase` group on `marked-outnumber-base` as unchecked, since `$CornerBase` alone is no case. On the Analyze input, `grid --case '$CornerBase'` shows each case that takes `$CornerBase` emitting nothing.
- `$StoredLattice` is the `@store tile_of` branch on the `lattice` instance (`lattice.tile_of=stored`), because it stores a value that the program derives. Its witness `five-tile-lattice` now has the id `lattice.tile_of=stored`. The stored value is `tile_of` and not `divider`: stored divider lines, read as distances from both edges, give the concept's output on the 5-by-5 lattice, so they do not carry the stored tile count of 7 that the Analyze report describes.
- `lattice.tile_of=stored` stays, and the Analyze report says it fails Subsumption. The new witness `broken-divider` shows it defined and different from the concept. That witness is train0's input with cell (12,14) of a divider row in a base color: the concept reads no divider on that row and is undefined, and the stored lattice completes the shape.
- `$ComplementOfShared` is dropped under Subsumption. Where it is defined, the marked tile shares exactly one color with the base tile, so the cells off that color are the cells of the colors the base tile lacks, which is `$NewColor`'s shape. Witness `three-color-mark` then separated nothing and was removed.
- `impl_choice` holds the concept case and the cases `{$Commoner, $CornerBase} × {$NewColor, $MajorityColor} × {$InLattice, $ClippedPlacement} × {$UnionOfPlacements, $EachPlacement} × $MostMarked`. The cases outside that set fail Subsumption:
    - A `$OnePlacement & $MostMarked` case is defined only where one placement holds the most marked tiles, and there the `$UnionOfPlacements & $MostMarked` case gives the same grid.
    - A `$UnionOfPlacements` or `$EachPlacement` case with `$AllMarked` is defined only where some placement holds every marked tile. There the placements that hold the most marked tiles are those same placements, so the case with `$MostMarked` gives the same output.
    - Each non-concept `$OnePlacement & $AllMarked` case is subsumed by the `$UnionOfPlacements & $MostMarked` case with the same other branches. So the single-branch models of `$CornerBase`, `$MajorityColor`, `$ClippedPlacement`, `$UnionOfPlacements`, `$EachPlacement` and `$MostMarked` are not cases, and each of those branches is stood for by its nearest case.

## Judgments
- Lattice parse: `Unanimous<Line, Color>` finds the uniform lines, and those lines are the dividers of a `DividerTiles` instance. This follows the precedent of 135a2760. A `Bbox` per tile and `crop` give each cell its place in its tile.
- Tile patterns: a `Canon<Position>` class per pattern, with the equivalence read from the defect relation `differ` (two tiles differ at some cell).
- Placements: one `Occurrences<ShapeKey, Unit>` instance gives both bounds. `occurrence` gives the in-lattice placements (`$InLattice`), and `placement` gives every alignment of a shape cell with a tile (`$ClippedPlacement`). Each `$MostMarked` case reads `Mode<PlaceKey, Box, Position>` over the marked tiles a placement covers.
- `$EachPlacement` is a tiebreak among the qualifying placements, so `out` takes a `TiebreakResolution` column. Its values are `$Placed(B)`, one per placement, for `$EachPlacement`, and `$Every()` for the cases that draw every qualifying placement in one grid. When `$UnionOfPlacements` emitted its one grid at each placement's value, `record` wrote that grid once per value.
- Hint `head-repeat` on `drawn` is kept with `@ignore`: for `$EachPlacement`, the resolution `$Placed(B)` names the placement that its grid draws.
- Deletions that change no pair are all kept. Each guards a condition that the pairs never meet: the corner-tile tests, `majority_tie`, `rival`, the `pattern.id` test in `covers` (needed for clipped placements), `filled.res` (needed where `$EachPlacement` has ties), and `impl_choice` in `out` (it excludes the subsumed combinations).
- Witness `broken-divider`: `borderline`, because it breaks `tile-lattice` (divider lines of one color). Verdict `stored`: a person still sees the 7-by-7 lattice and completes the shape, and the odd cell stays.
- Witness `marked-outnumber-base` (rebuilt): `borderline $CornerBase`, `@relaxed tile-lattice` and `base-tile`. These are the Analyze judgment and grounds, on the new input.
- The other plausibilities and verdicts are the Analyze report's.
- `derive` found no built-in derivation. `store` printed no `@store` line. The sweep reported nothing, and the determination plan lists no actions, so the solver has no `Determine` comp.
- Keywords `decompose scale rank color-class`: the divider lattice, the shape read across the tile scale, the commoner pattern as base, and the new color's cells as one unit.

## Open
- The `uncovered-marked` and `several-placements` points are now coupled: `$AllMarked` occurs only with `$OnePlacement`, and `$MostMarked` only with the two other branches. A reviewer may judge whether one choice point of three branches states this better than the record and `impl_choice`. Settled by that review.

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
- 10-497_task_b99e7126_create.md
- 10-498_task_b99e7126_create.md
