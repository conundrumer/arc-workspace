# b7f8a4d8

## Departures
- The `line-pairs` and `bridge-directions` choice points are fields of the `Bridges` constructor (`Bridges {pairs: LinePairs, dirs: Directions}`), not points at the concept as the Analyze report places them: the lint's unread-field hint showed that the `$BboxOutline` case never reads either field, and a point whose property exists only with one branch stands under that branch. The cases are the same as in the report's `join` & `line-pairs` and `join` & `bridge-directions` lines.
- `$BboxOutline & $CellBetween` is no case: it fails Fit on train1 and test0. Its reading paints the params.bg cells on the edge of the color's cell box, so the second row of each 2-row and 3-row band stays unpainted.
- The Not formed item "one color drawn over the other" is the `DrawOrder` choice point, with `$DrawnOver` its branch. Its order of colors is the `@open` relation `draw_rank`, whose open values are whole orders, each a dense ranking under its own `v`, the column the `DrawRankValue` field names. The stored open values are every order of the odd colors the inputs hold: 1, 3, 4 and 8.
- With `$DrawnOver` formed, each non-concept base that takes `$Unordered` fails Subsumption: it is undefined at each cell that two colors claim, and the same base with `$DrawnOver` gives its output wherever it is defined. So the concept case is the one case that takes `$Unordered`. `shared-line` and `missing-crossing` separate the `$BlockedByOdd` bases from their `$DrawnOver` cases.
- Where interior colors tie for the commonest, the solver reads each tied color as common and bridges the rest. The Analyze report has the concept undefined there. No witness has such a tie.
- The witness file adds `offset-blocked` and `offset-diagonal`. They witness `$BlockedByOdd & $CellBetween` and `$Dir8Bridges & $CellBetween`, which no Analyze witness separates from the cases that take only one of their branches.

## Judgments
- `shared-line`: plausibility `ordinary`, verdict `$DrawnOver`. It breaks no scene claim: each odd color's tiles fill the four corners of a rectangle of tiles, and two rectangles share a tile line. The generator draws each color's outline, so a color drawn later covers an earlier one where the two outlines overlap.
- `missing-crossing`: plausibility `borderline`, verdict `$DrawnOver`. It breaks `tiling` (the middle tile is missing), so the bridges of 1 and 3 cross on `params.bg` cells that no tile of another odd color blocks.
- `offset-blocked` and `offset-diagonal`: plausibility `foreign`, verdict `$CellBetween`. Both break `tiling` (a tile of 8 sits one row off the tiling) and `odd-rectangle`. On the offset tiles, the verdict follows `offset-tiles`. On the lone tile of 1 between tiles of 3, it follows `lone-odd-between` (the bridge crosses). On the tiles of 3 on one tile diagonal, it follows `square-rectangle` (no diagonal bridge). Under the concept's reading of each part, that gives the `$CellBetween` model's output.
- The parse takes the frame color as the non-params.bg color that meets params.bg (8-neighbors), and the interiors as components of the other non-params.bg colors, keyed by color. A cut-off tile with no interior cells (train2 row 25) is not a tile. This matches the Not formed note that no rule reads `frame-width`.
- `$Dir8Bridges` tile-level line test: two interiors are on one tile diagonal when they span the same diagonals, which the box corner distances to both corners across the diagonal test. This is the diagonal analog of the concept's "interiors span the same rows".
- `$BlockedByOdd` at both levels reads a cell of another odd color on the path between the two tiles as the block. At cell level it is the `blocked` input of the `Ray` instance, and both levels read `clear`, so `$AnyPair` keys have no blocked cells.
- `// @ignore dir: store` on `cell_ray`: `store` listed the cast directions as one value on every input. Each case's `Directions` branch gives that set, and the tool found no witnessed case that would take a stored branch.
- Hints during Develop: the marker hint on the diagonal `line_pair` clause was fixed by the constant head `$Dir8Bridges()`. Two pass-through hints (`outline_tile`, `outline_cell`) were fixed by writing `paint` directly. The second of those went away with the drop of `$BboxOutline & $CellBetween`.
- Deletions: removed `dir_elem(D)` from `frame_color` (8-neighbors give the same frame color), `odd_tile` from `tile_box.cell`, `span_tile` and the outline clause, where another atom already binds the same facts. Kept `!params.bg(Col)` in `frame_color`, `odd(Col)` in `color_box.cell`, and `same_dist(D, B, B_all)` in the outline clause. Each states part of a claim that the pairs do not exercise.
- Determine: the plan reports `bg` covered on the examples, so the solver has no Determine comp.
- Keywords `objects match span rank`: tiles are the pieces, tiles of one color pair off by color and line, the bridge spans between them, and the commonest color picks which tiles act.

## Open
- `$BlockedByOdd & $Dir8Bridges & $DrawnOver`, at both line-test levels, is not witnessed. Both branches have only `concept` verdicts, so no output can witness it. A witness with a non-`concept` verdict on one of the two branches would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-471_task_b7f8a4d8_create.md
