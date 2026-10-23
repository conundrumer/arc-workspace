# c64f1187

## Departures
- The branch `gap=stored` is the constructor `$Tiling` of the `TileParse` point, and its name is rewritten in the witness file: the concept derives no gap, so no `@store` line can stand for it, and its tiling parse has clauses of its own.
- `$Tiling` reads the common extent of the tile pieces (`tile_size`) in place of the extent of the piece at the corner, and runs from `params.tiling_corner` (top-left) in place of a fixed top-left corner: the two extents differ only where the pieces differ in extent, where the concept is undefined, and a stored corner keeps the program free of a fixed orientation.
- `$ByOrder` ranks the markers and the pieces with `LexOrder` from `params.marker_corner` along a new parameter `params.order_axis` (H), and ranks a piece by the corner cell of its bounding box: the report's left-to-right order fixes an orientation that the program reads from Params.
- `$CodeAtCorner` takes no background cell as a code. The Analyze probe took any color other than the tile color, background included. They differ only on a tile of the tiling whose corner cell is background, which no single-branch witness shows.
- The concept is undefined on a tile with two code cells (`code_clash`), and `$DerivedCorner` is undefined where no single corner fits (the `corner_of(Ch, _)` guard on `out`). The first draft gave a blank grid on `background=DominantColor` and on `shape-in-other-color`, where the Analyze file gives undefined. With the fix, every branch gives the Analyze file's output on its 9 witnesses. That was checked against a copy of the Analyze file with `gap=stored` rewritten to `$Tiling`.
- Two witnesses are added beyond the Analyze file: `legend-mirrored` and `recolored-tiles` (see Judgments).

## Judgments
- The cases are the full product of the six `Choice` fields, with `shape-place` nested under the concept branch of `legend-pairing` (`InBox {place: Place}`): the report has `$ByOrder` & `$BboxAnchor` be the model of `$ByOrder` alone. `box-size` is the `@store` line on `tile_size`, and `$ByOrder` cases with `$StoredCorner` read no `tile_size`, so they take no branch there.
- Not formed: no item states a model to form. The proposer derivations of `tile_size` and `gap` fall under `derive`, which finds none that fits. The other two items are readings no pair takes.
- `derive`: only `DominantColor` fits `background`, and that is the `@derive` line.
- `store`: `corner_defect` and `corner_fit` under `$DerivedCorner` are constant on every input. A stored value of either gives the stored corner, so those cases are equivalent to `$StoredCorner`'s and carry `@ignore: store`. `corner_of`, `tile_color_of` and the `LexOrder` corners are stored already. The frame, offset and extent relations have no witness. `tile_size` keeps its `@store` line, whose witness is the Analyze file's `tile_size=stored`.
- Lint hints: the `pass-through` hint on `bbox_corner` was taken, and the relation was inlined into the two `shape_anchor` clauses. The `common-subexpr` hint on the two `LexOrder` axis clauses was taken through `rank_axis`. The `negated-use` findings were taken. The `dead` relation `tile` was removed.
- Subsumption, `witness` without `--file`. No run showed `$DerivedCorner` defined and differing from `$StoredCorner` among the cases that take `$CodeAtCorner`. `legend-mirrored` was built for it: train0's tiles under the mirrored legend, so the codes stay at bottom-right. I judge it `variant $DerivedCorner`, `@relaxed legend`: a mirrored legend is a routine variant, and the stamps mirror with the shapes.
- Subsumption, continued. No run showed `$TileColorByCount` defined and differing from `$StoredTileColor` among the cases that take `$DerivedCorner`. `recolored-tiles` was built for it: train0 with the tiles in 6. I judge it `variant $TileColorByCount`, `@relaxed tile-grid`: a color permutation is a variant task, and at the stored tile color the concept finds no tile.
- Determination. The plan asked for relations past its enumeration limit, then for the witness pairs, then for each value a proposer covers. The relations written are these:
    - `background`: the commonest color of every input.
    - `tile_color`: the color every piece of two colors holds. The commonest ink fails on `few-tiles`.
    - `code_corner`: a corner at which some code sits in every input. "Every code" fails on `code-off-corner`.
    - `gap`: the shortest background run between two tile cells. "Every run" fails on `wide-gaps`.
    - `marker_corner`: the corner away from which every marker has a shape cell on both axes.
    - `order_axis`: the axis of a line that holds every marker.
    - `shape_color`: the ink color outside the tiles and markers that no output shows.
- `tile_piece` moved into `Parse` (keyed by `TileColor` in the program and by `Example` in `Determine`), as did the ink `Mode` that `$TileColorByCount` and the determination share. `Determine`'s code and marker relations stay local, because the program keys them by the `Code` and `TileParse` branches.
- `order_axis` and `tiling_corner` keep one stored value each, though the sweep finds the pairs admit the others. The report states `$ByOrder` as ranked left to right and `$Tiling` as running from the top-left corner, and gives no open parameter.
- Deletions: the atoms whose removal changes nothing are guards of undefinedness, branch-only structure, or bounds the pairs do not reach, such as `inside(B, R)` and `box_corner(K, ZERO, D)`, and they stay. Two redundancies were removed: `impl_choice(Ch)` in `out`, which `corner_of(Ch, _)` already grounds, and the `mixed` filter in the `tile_color` candidates.
- Keywords `crop objects markers stamp decompose`: the output crops to the tile grid, the tiles and shapes are pieces, the legend markers fix which shape a color takes, each code stamps a footprint, and the gaps cut the grid into tiles.
- Performance: the solver has 96 bases and runs in 5 to 7 s. `sweep` and `deletions` took 49 s each. One run took 67 s (ticket below).

## Open
- Whether `tiling_corner` is an open parameter: any corner fits the pairs and the test, and only a misaligned region such as `wide-gaps` separates them. A reviewer's reading of `$Tiling` would settle it. `determination-plan` still lists it, because no fact of the evidence singles out the top-left corner.
- Whether `order_axis` is an open parameter: the pairs admit V as well. A legend whose piece corners stand on different rows would separate them, and so would a reviewer's reading of "ranked left to right".

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-743_task_c64f1187_create.md
- 10-744_task_c64f1187_create.md
