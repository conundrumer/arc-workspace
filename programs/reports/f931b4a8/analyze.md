# f931b4a8

## Concept
- Fits every train and test pair (`work/task/f931b4a8/check_concept.py`). Every rule has a relational form: the extents are counts of cells, and the tile and fill indices count tiles. No witness has verdict `other`. Three non-concept branches fit every pair: `$TileByBbox`, `$FillIndexWrap`, `$SeparateFillAnchor`. The pairs fix every parameter: `count_quad` by train 0 (16×4), `anchor` by train 3 (rows 1,6,1) and train 2 (cols 8–9 repeat cols 0–1), and `bg` = 0, the only color every input has.

## Choice points
- `tile`: what one tile of the output is
    - `concept`: the whole pattern quadrant
    - `$TileByBbox`: replaces `tile-pattern`. The tile is the bounding box of the pattern quadrant's non-`bg` cells. Same parameters. Undefined where the pattern quadrant has no non-`bg` cell, or where a hole's tile index passes the fill grid. Fits every pair: it parts from the concept only past row 2 of train 3, and that output has 3 rows. Witness `hole-row-at-pattern-edge`, at the stored assignment: train 3 with 8 cells in TL, so the output runs to 8 rows. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
    - `$TileByPeriod`: replaces `tile-pattern`. The tile is the pattern quadrant cut to its least period on each axis. Undefined where a hole's tile index passes the fill grid. Fails Fit at train 0: a period-2 tile gives 8 tile rows against a 4-row fill grid.
- `fill-source`: which color fills a hole
    - `concept`: the fill-grid cell at the tile's own place among the tiles, so the fill grid shows scaled by the tile size
    - `$FillSamePosition`: replaces `fill-holes-scaled`. A hole takes the fill-grid cell at the hole's own place within its tile. Fails Fit at train 1.
    - `$FillUniform`: replaces `fill-holes-scaled`. A hole takes the fill quadrant's one color. Undefined where the fill quadrant has more than one color. Fails Fit at train 1.
- `holes`: which tile cells take a fill color
    - `concept`: every `bg` cell of the tile
    - `$FillEnclosedOnly`: replaces `fill-holes-scaled`. Only the `bg` cells that no walk over `bg` reaches from the tile's edge take a fill color, and the rest stay `bg`. Fails Fit at train 0.
- `fill-past-grid`: a hole whose tile index passes the fill grid
    - `concept`: there is no fill cell for it, and the model is undefined
    - `$FillIndexWrap`: adds to `fill-holes-scaled` that the tile index wraps modulo the fill grid's extent on each axis. Same parameters. Defined wherever the concept is, and on inputs with non-square quadrants too. Fits every pair. Witness `fill-index-past-fill-grid`, at the stored assignment: a 4×8 input. It breaks `four-quadrants` and the invariant that every input is a square. Plausibility `foreign`, verdict `$FillIndexWrap`.
- `fill-corner`: the corner the fill grid's cells are counted from
    - `concept`: the tiling's `anchor`, one parameter for both
    - `$SeparateFillAnchor`: replaces `fill-holes-scaled` with a version that reads a parameter `fill_anchor` of its own, TL in this task, for the corner the fill grid is read from. Same at the stored assignment. Fits every pair. Witness `fill-read-from-other-corner`, at `fill_anchor` = `DIAG_BL` on train 1's input. It breaks no scene claim and no invariant of the inputs. What is unusual is the assignment: it pairs a tiling corner with a different fill corner, which no D4 image of the task does. Plausibility `borderline`, verdict `$SeparateFillAnchor`.
- `extent`: what gives the output's extent on each axis
    - `concept`: the count of non-`bg` cells in that axis's `count_quad` quadrant
    - `$SizeByBbox`: replaces `output-size`. The extent is the area of the bounding box of the quadrant's non-`bg` cells. Fails Fit at train 3 (9, not 3).
    - `$SizeByColorCount`: replaces `output-size`. The extent is the count of the quadrant's one non-`bg` color. Undefined where the quadrant has more than one. Fails Fit at test 0 (TL holds 2, 3 and 5).
    - `$SizeByComponents`: replaces `output-size`. The extent is the number of 4-connected non-`bg` components in the quadrant. Fails Fit at train 0 (1, not 16).
    - `$SizeInTiles`: replaces `output-size`. The count gives the extent in tiles. Fails Fit at train 0 (64 rows, not 16).
- `roles`: which quadrant plays which part
    - `concept`: stored in `pattern_quad`, `fill_quad`, `count_quad`
    - `$RolesByContent`: replaces the stored roles with roles derived from content: the fill quadrant is the one with no `bg` cell, the pattern quadrant is the one with both `bg` and non-`bg` cells, and the other two are the count quadrants. Undefined where content picks no single quadrant for a role. Fails Fit at train 1, where TL, TR and BL all have no `bg` cell.
- `bg`: the background color
    - `concept`: stored, 0
    - `bg=DominantColor`: fails Fit at train 1 (8 and 6)
    - `bg=RarestColor`: fails Fit at train 0 (3)
    - `bg=SharedColor`: fails Fit at train 0 (one input alone gives each of its colors)
- `tile` & `fill-past-grid`, `tile` & `fill-corner`, `fill-past-grid` & `fill-corner`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- The fill grid stretched over the whole output, each cell reading the fill cell at its position scaled by n/H and n/W: it has no relational form, because the ratio counts nothing the task has. It agrees with the concept wherever the output is n²×n².
- Tiling from a corner other than TL, or count axes swapped: these are values of `anchor` and `count_quad` that the pairs fix (trains 2 and 3, and train 0). They are not branches.
- A split located by content rather than at the halves: no input has a marker that places a split, and the halves are the only split every input shows. Train 1 and test 1 have multi-colored fill quadrants, so no single block bounds a quadrant there.

## Tickets filed
- none
