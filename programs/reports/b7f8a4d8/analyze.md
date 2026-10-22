# b7f8a4d8

## Concept
- The concept fits every pair (`check_concept.py`, `probe.py`). It is defined where the non-`background` components parse as tiles with one interior color each and one interior color is the commonest. It is undefined where bridges of two colors claim one cell, which needs two odd colors in one tile line; no input shows that.
- No witness has the verdict `other`.
- The generator most likely picks two tile rows and two tile columns for each odd color and draws the outline of the rectangle that the four tiles at their crossings bound. The concept rule has a relational form and agrees with that outline wherever `odd-rectangle` holds, so it is not an approximation.

## Choice points
- `join`: which tiles of one odd color its bridges join
    - `concept`: each two tiles of the color in one tile row or one tile column, with the bridge crossing the tiles between them
    - `$BboxOutline`: replaces `bridge-odd-tiles` with the outline of the rectangle bounded by the color's outermost tile rows and tile columns, painted on the `background` cells in line with the interiors. It is defined where the concept is. It fits every pair. Witness `l-shape` breaks `odd-rectangle` (the tiles of 3 fill three corners), plausibility `variant`, verdict `concept`. The invariant it breaks is that each odd color's tiles fill all four corners of a rectangle of tiles.
- `line-pairs`: which two tiles in one tile line a bridge joins
    - `concept`: any two tiles of the color, whatever tiles lie between
    - `$AdjacentOnly`: replaces `bridge-odd-tiles` with bridges only between tiles with no tile between them. It fails train0, and every other pair as well (train0 row 7 bridges 1 across the tiles at cols 11–13 and 16–18).
    - `$BlockedByOdd`: replaces `bridge-odd-tiles` with bridges that no tile of another odd color lies between. It is defined where the concept is, and also where blocking leaves no cell to two colors. It fits every pair. Witness `lone-odd-between` breaks `odd-rectangle` (the tile of 1 has no partner), plausibility `variant`, verdict `concept`. The invariant it breaks is the one `l-shape` breaks.
- `bridge-directions`: the lines along which tiles join
    - `concept`: rows and columns of tiles, both axes
    - `$Dir8Bridges`: adds bridges between two tiles of the color on one tile diagonal, painted on the `background` cells on the diagonals through their interior cells. It is defined where the concept is. It fits every pair, because no two tiles of one odd color share a tile diagonal in any input. Witness `square-rectangle` breaks no scene claim, plausibility `ordinary`, verdict `concept`.
    - `$OneAxis`: replaces `bridge-odd-tiles` with bridges along one stored axis. It fails train0 at either axis, because train0 has bridges on both.
- `bridge-width`: the cells of a gap that a bridge paints
    - `concept`: the cells in line with the interiors
    - `$FrameWidth`: replaces `bridge-odd-tiles` with the cells in line with the whole tile, frame included. It fails train0 (train0 output row 1 cols 14–15 stay 0).
- `crossed-tiles`: what a bridge does to a tile it crosses
    - `concept`: the tile stays as it is
    - `$OverwriteCrossed`: replaces `bridge-odd-tiles` with a bridge that also paints the crossed tile in line with the interiors. It fails train0 (train0 output row 7 col 12 stays 4 inside the bridge of 1).
- `odd-colors`: which interior colors bridge
    - `concept`: each interior color other than the commonest (`common-interior`)
    - `common_interior=stored`: replaces `common-interior` with a stored common interior color. It fails Fit: train0's common interior is 4 and train1's is 2. At 4, train1 fails, and at 2, train0 fails.
    - `$CornerCommon`: replaces `common-interior` with the interior color of the top-left tile. It fails test0 (that tile holds 3, an odd color).
- `background`: the field color
    - `concept`: stored 0
    - `background=DominantColor`: derives `background` as the commonest color of the input. It fails train1, where the frame color 3 is the commonest.
    - `background=SharedColor`: derives `background` as each color of the input. It fails train0, which gives 0, 1, 2, 3 and 4, so a train output holds more than one grid.
- `line-test`: when two odd cells are in line
    - `concept`: tile-level: two tiles are in one tile row when their interiors span the same rows, and the same for columns
    - `$CellBetween`: replaces `bridge-odd-tiles` with cell-level bridges: a `background` cell with a cell of one odd color on each side along its row or column takes that color (lib `Between`). It is defined where the concept is. It fits every pair. Witness `offset-tiles` breaks `tile-lattice` (one tile of 8 sits a row lower), plausibility `foreign`, verdict `$CellBetween`. The invariant it breaks is that all tiles sit on one lattice.
- `join` & `line-pairs`, `join` & `bridge-directions`: the model is `$BboxOutline` alone. The properties of `line-pairs` and `bridge-directions` exist only with the concept branch of `join`, which the concept claims take, so both points stand at the concept.
- `join` & `bridge-width`, `join` & `crossed-tiles`, `join` & `odd-colors`, `join` & `background`, `join` & `line-test`, `line-pairs` & `bridge-directions`, `line-pairs` & `bridge-width`, `line-pairs` & `crossed-tiles`, `line-pairs` & `odd-colors`, `line-pairs` & `background`, `line-pairs` & `line-test`, `bridge-directions` & `bridge-width`, `bridge-directions` & `crossed-tiles`, `bridge-directions` & `odd-colors`, `bridge-directions` & `background`, `bridge-directions` & `line-test`, `bridge-width` & `crossed-tiles`, `bridge-width` & `odd-colors`, `bridge-width` & `background`, `bridge-width` & `line-test`, `crossed-tiles` & `odd-colors`, `crossed-tiles` & `background`, `crossed-tiles` & `line-test`, `odd-colors` & `background`, `odd-colors` & `line-test`, `background` & `line-test`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A rule for a cell that bridges of two colors both claim, such as one color drawn over the other: no input holds two odd colors in one tile line, and the pairs give no order of colors to draw by. `$BlockedByOdd` is the one reading formed that is defined there.
- A branch on `frame-width`: no rule reads it, because the interior is the tile's cells that are not its frame color.

## Tickets filed
- 10-407_task_b7f8a4d8_analyze.md
