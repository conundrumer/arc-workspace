# b99e7126

## Concept
- The concept case fits every pair (`work/task/b99e7126/probe.py`). Each rule has a relational form, so no rule is approximated. No witness has the verdict `other`.
- The concept is undefined on each input where no placement in the tiling holds every marked tile, or where more than one does (`placement-past-edge`, `two-placements`, `stray-marked-tile`). Each such input breaks `partial-shape`.
- Invariants of the inputs that the concept does not claim:
    - every grid is 29 by 29, with 7 tiles of 3 by 3 to a side
    - the new color covers 6 or 7 of the 9 cells of the marked tile
    - the shape's placement keeps off the tiling's edge tiles

## Choice points
- `tiling-source`
    - `concept`: the tiling is read off the divider lines.
    - `$StoredTiling`: replaces `tiling` with a stored tile size of 3 and a stored tile count of 7; parameters `tile_size`, `tile_count`. Undefined where the divider lines do not fall at that stride. Fits every pair. Witness `five-tile-tiling` (5-by-5 tiling): the branch is undefined there. It breaks `tiling` at `tile_count` 7. Plausibility `variant`, because it breaks the invariant that every grid has 7 tiles to a side. Verdict `concept`. No witness exists on which the branch is defined, because wherever the stored stride matches the dividers, the branch gives the concept's output. So the concept subsumes this branch, and the branch fails Subsumption.
- `base-tile`
    - `concept`: the base tile is the commoner of the two tile patterns.
    - `$CornerBase`: replaces `base-tile` with the pattern of the tiling's top-left tile. Undefined where that tile is marked. Fits every pair. Witness `marked-outnumber-base`: a 3-by-3 tiling holds 5 marked tiles and 4 base tiles. There the branch is defined and the concept is undefined. It breaks `base-tile` and `tiling` at `tile_count` 7. Plausibility `borderline`, because it breaks the invariants that the tiling has 7 tiles to a side and that base tiles outnumber marked tiles. Verdict `$CornerBase`.
- `marked-tile-source`
    - `concept`: the marked tile is derived as the pattern that is not the base pattern.
    - `$StoredMarkedTile`: stores the marked tile, train0's `3 1 3 / 3 1 3 / 3 3 3`, and so replaces `marked-tile`. Fails Fit at train1, train2 and test0.
- `shape-source`
    - `concept`: the shape is the cells of the marked tile whose color the base tile does not have.
    - `$MajorityColor`: replaces `shape-of-new-color` with the cells of the marked tile's commoner color. Undefined where two colors tie for commonest. Fits every pair. Witness `minority-shape`: the new color draws a 4-cell L. There the branch is defined and differs from the concept. It breaks no scene claim. Plausibility `variant`, because it breaks the invariant that the new color covers 6 or 7 of the 9 cells. Verdict `concept`.
    - `$DiffersFromBase`: replaces `shape-of-new-color` with the cells where the marked tile differs from the base tile at the same cell. Fails Fit at train0, train2 and test0.
    - `$ComplementOfShared`: replaces `shape-of-new-color` with the cells of the marked tile that do not hold the one color it shares with the base tile. Undefined where the marked tile shares no color or more than one color with the base tile. Fits every pair. Witness `three-color-mark`: the marked tile holds both base colors and one new color. There the branch is undefined. It breaks `marked-tile`. Plausibility `borderline`, because it breaks the invariant that the marked tile has two colors. Verdict `concept`. No witness exists on which the branch is defined and differs, because wherever it is defined, its cells are those of the colors the base tile lacks. So the concept subsumes this branch, and the branch fails Subsumption.
    - `$OverlayShape`: replaces `complete-shape` and `shape-of-new-color` together: a completed tile keeps the base tile and takes the new color only on the shape's cells. Fails Fit at train0. For example, at train0 output (5,10) the pair gives `1` and the branch gives `4`.
- `placement-bounds`
    - `concept`: a placement lies wholly inside the tiling.
    - `$ClippedPlacement`: replaces the in-tiling condition of `partial-shape`. A placement may run past the tiling edge, and only its part inside the tiling is drawn. Undefined where more than one such placement holds every marked tile. Fits every pair. Witness `placement-past-edge`: there the branch is defined and the concept is undefined. It breaks `partial-shape`. Plausibility `foreign`, because it breaks the invariant that the shape's placement keeps off the tiling's edge tiles. Verdict `$ClippedPlacement`.
- `several-placements`
    - `concept`: undefined where more than one placement holds every marked tile.
    - `$UnionOfPlacements`: adds a rule to `complete-shape` that completes every such placement in one grid. Fits every pair. Witness `two-placements`: two adjacent marked tiles fit the bottom row of the U at two places. There the branch is defined and the concept is undefined. It breaks `partial-shape`. Plausibility `borderline`, because it breaks the invariant that the marked tiles fit one placement only. Verdict `$EachPlacement`.
    - `$EachPlacement`: adds a rule to `complete-shape` that gives one grid per such placement. Fits every pair. Witness `two-placements`, the same judgment as `$UnionOfPlacements`: the branch gives two grids. Verdict `$EachPlacement`.
- `uncovered-marked`
    - `concept`: undefined where no placement holds every marked tile.
    - `$MostMarked`: replaces `partial-shape` and `complete-shape` with the placement that holds the most marked tiles. Marked tiles outside that placement stay. Undefined where several placements tie for most and no `several-placements` branch resolves them. Fits every pair. Witness `stray-marked-tile`: a stray marked tile sits at tile (6,6). There the branch is defined and the concept is undefined. It breaks `partial-shape`. Plausibility `foreign`, because it breaks the invariant that every marked tile lies on the shape. Verdict `$MostMarked`.
- `tiling-source` & `base-tile`, `tiling-source` & `marked-tile-source`, `tiling-source` & `shape-source`, `tiling-source` & `placement-bounds`, `tiling-source` & `several-placements`, `tiling-source` & `uncovered-marked`, `base-tile` & `marked-tile-source`, `base-tile` & `shape-source`, `base-tile` & `placement-bounds`, `base-tile` & `several-placements`, `base-tile` & `uncovered-marked`, `marked-tile-source` & `shape-source`, `marked-tile-source` & `placement-bounds`, `marked-tile-source` & `several-placements`, `marked-tile-source` & `uncovered-marked`, `shape-source` & `placement-bounds`, `shape-source` & `several-placements`, `shape-source` & `uncovered-marked`, `placement-bounds` & `several-placements`, `placement-bounds` & `uncovered-marked`, `several-placements` & `uncovered-marked`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- none

## Tickets filed
- 10-433_task_b99e7126_analyze.md
- 10-434_task_b99e7126_analyze.md
- 10-435_task_b99e7126_analyze.md
