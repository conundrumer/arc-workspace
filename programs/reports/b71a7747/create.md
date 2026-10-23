# b71a7747

## Departures
- `$PackTiles` is not a case, and the witness `missing-tile` is gone from `programs/witnesses/b71a7747.wit.json`: the solver's `$PackTiles` fit every pair, but no input shows it defined and giving a grid that differs from the concept's. Where it is defined, its tiles are equal solid squares in a full array, and packing them by rank gives the grid that the concept's row and column removal gives. So it fails Subsumption, as the Analyze report says. After that, `missing-tile` separated no case. `witness --file work/task/b71a7747/witnesses.json` prints only that `$PackTiles` names no case, and prints no difference in output.
- The choice points are nested in a different way from the report. The report's Markdown indents `kept-lines` and `tile-colors` under the `$LineBreaks` bullet. Both properties exist only when the kept lines are read from the tiles, so `KeptLines` is the field of the concept constructor `FromTiles`. `tile-colors` is under `TileRows`, the concept branch of `kept-lines`, because `$TilingBands` reads no tile cell to choose its rows. So no `$TilingBands & $TileColorOnly` case exists: its model would be the `$TilingBands` model, and it would fail Equivalence. The report's `kept-lines & tile-colors` line gives no other case.
- The solver gives names of its own to the concept constructors: `FromTiles`, `TileRows` and `BothColors`. `record --all` rewrote the witness file's groups to `$TileRows`, `$FromTiles` and `concept`.

## Judgments
- How the program reads the color roles: the tile color and the path color are the one pair of colors whose cells, taken together, form 4-connected parts that are equal solid squares (`tile_pair`). This comes from the `tiles` and `path` claims. The Analyze probe reads the roles by eye, and the report gives no relational reading. On every pair and every Analyze witness, exactly that pair passes (I checked all 1- and 2-color sets in a scratch script). One noise color alone forms 1×1 squares, which is why the set must hold two colors.
- How `$TilingBands` and `$LineBreaks` read the tiling: the field colors are the non-tile colors that hold no cell on a row or column through a tile center. These are the background, and noise that is off the lines (4 and 6 in train0). The lines are the rows and columns that hold no field cell. The line color is the non-tile color that every line holds. With this reading, a noise cell on a line (`texture-on-line`) breaks the line for `$LineBreaks`, as the report requires.
- `$TileColorOnly` reads the tile color as the more common color of the tile pair (`Mode`). The path is a 1-wide line inside k×k squares.
- `$TilingBands` moves a tile's box so that its center lands on each line crossing, and keeps the moved box where `inside(B2, ZERO)` holds.
- Keywords `objects lines select noise cross`: `cross` is for `$TilingBands`, which keeps rows and columns around line crossings.
- The audit, derive and store found nothing. The determination plan lists no actions (`.comp Params {}`).
- Deletions that change nothing on the pairs, and that I kept: the extent check in `unsquare` and `part_extent` (this states "equal squares"), `gapped` (it matters on `texture-on-line`), and `perp` and `crop(C, B, _)` in `band_square` and `out` (each states which axis or which tile box is meant). I removed `!tile_color` from `crossed` because `field` already excludes the tile colors.

## Open
- The concept case is undefined where the tiles are not equal solid squares, for example tiles of two sizes. The by-eye reading of the concept would still give a grid there. A witness with tiles of unequal sizes would show the difference. That witness breaks `tiles`.
- Another pair of colors, such as noise and path cells that happen to form squares, could also pass the equal-solid-squares test. Then the concept would count extra colors as tile colors. No witness covers this. A grid built for this case would settle whether a case is needed.

## Lib
- Closing up kept lines: for each axis, an `OrderFrame` over the kept lines, then `split` of each input cell into its two lines, `pos` on each axis and `compose`. This solver: `layout` and its `out` clause. The grep found the same shape in 1190e5a7 (approved), 7039b2d7 and 458e3a53. Those three rank bands where this solver ranks single lines.
- The center cell of a box: `crop(P, B, P_rel), centered(P_rel)`. This solver: `tile_center`. The grep found the same shape in a3f84088.

## Fixes elsewhere
- none

## Tickets filed
- none
