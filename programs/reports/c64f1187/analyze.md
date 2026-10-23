# c64f1187

## Concept
- Fits every pair: train0, train1 and test0 (`check.py`, and the `concept` reading of `probe.py`).
- Every rule has a relational form, and no rule is approximated: the generator's rule is the concept file's rule.
- No witness has the verdict `other`.
- Every reading below that fits gives the concept's output on all three pairs, so the pairs separate none of them. The witnesses part them only on inputs that leave the inputs' invariants: legend shapes of two cells, a code off its corner, shapes or background in another color, a mirrored scene, 3 by 3 tiles, two-cell gaps, a tile grid of three tiles.

## Choice points
- `legend-source`: where a color's shape comes from
    - `concept`: the legend of the input
    - `$StoredLegend`: a stored table from code color to shape; replaces `legend` and `stamp-shape`; fails Fit at train1, whose shape for 2 is the full square, where train0's is `1 1` over `1 0`
- `legend-pairing`: which shape a marker names
    - `concept`: the `shape_color` cells in the tile-sized box whose `marker_corner` the marker touches diagonally from outside
    - `$ByOrder`: the markers and the pieces of `shape_color` outside the tiles, each ranked left to right, pair by rank, and a shape sits in a tile by its bounding box at the tile's `marker_corner` corner; replaces `legend`; parameters `shape_color`, `marker_corner`; undefined where the concept is; fits every pair
        - witness `diagonal-shape`: breaks no scene claim; plausibility `variant`; verdict `concept`; breaks the invariant that every legend shape is one 4-connected piece of three or four cells
    - `$TouchingShape`: the pieces of `shape_color` that touch the marker, diagonally included, placed by their bounding box; replaces `legend`; fails Fit at test0, where the marker of 4 at (1,13) touches no cell of its shape `0 1` over `1 1`
- `shape-place`: where a shape cell lands in a tile
    - `concept`: at its place in the legend box
    - `$BboxAnchor`: the shape's bounding box at the tile's `marker_corner` corner; replaces `stamp-shape`; parameters unchanged; undefined where the concept is; fits every pair
        - witness `bar-shape`: breaks no scene claim; plausibility `variant`; verdict `concept`; breaks the invariant that every legend shape holds three or four cells of its box, so its bounding box is the box
- `marker-corner`: the corner of a legend box the marker touches
    - `concept`: the stored `marker_corner`, top-left
    - `$DerivedCorner`: the one corner at which every marker's box holds a `shape_color` cell; replaces `legend` (`marker_corner`); undefined where no corner or more than one corner meets that; fits every pair
        - witness `mirrored-legend`: breaks `legend` (`marker_corner`) and `code` (`code_corner`); plausibility `variant`; verdict `$DerivedCorner`; breaks the invariant that every marker touches its box's top-left corner and every code sits at its tile's bottom-right cell
- `box-size`: the extent of a legend box
    - `concept`: the extent of the tiles, derived from the input
    - `tile_size=stored`: the stored `tile_size`, 2 by 2; replaces `tile-grid` (`tile_size` becomes a parameter); undefined where the concept is; fits every pair
        - witness `tile_size=stored`: breaks `tile-grid` (`tile_size`); plausibility `variant`; verdict `concept`; breaks the invariant that every tile and every legend box is 2 by 2
- `shape-ink`: which cells of a legend box are the shape
    - `concept`: the cells of the stored `shape_color`, 1
    - `$AnyInk`: every cell of the box that is not background and not a marker; replaces `legend` (`shape_color` is no longer read); undefined where the concept is; fits every pair
        - witness `shape-in-other-color`: breaks `legend` (`shape_color`); plausibility `variant`; verdict `$AnyInk`; breaks the invariant that every legend shape cell is 1
    - `shape_color=<Proposer>` for each color proposer: fails Fit at train0, since on one input with no output SharedColor and VanishedColor give every color of the input, DominantColor gives 0, RarestColor gives 4 and 8, and OutNewColor, AnyOutNewColor, ChangedColor and UnchangedColor give none
- `code-cell`: which cell of a tile is its code
    - `concept`: the one cell of the tile that is not `tile_color`; undefined on a tile with two such cells
    - `$CodeAtCorner`: the cell at the stored `code_corner`, bottom-right, when it is not `tile_color`; replaces `code` (`code_corner` becomes a parameter); defined on a tile with two such cells; fits every pair
        - witness `code-off-corner`: breaks `code` (`code_corner`); plausibility `borderline`; verdict `concept`; breaks the invariant that every code sits at its tile's bottom-right cell
- `tile-color`: the color of the tiles
    - `concept`: the stored `tile_color`, 5
    - `$TileColorByCount`: the commonest color other than background; replaces `tile-grid` (`tile_color` is no longer read); undefined on a tie; fits every pair
        - witness `few-tiles`: breaks no scene claim; plausibility `variant`; verdict `concept`; breaks the invariant that the tile grid holds at least 12 tiles and its cells outnumber the shape cells
    - `tile_color=<Proposer>` for each color proposer: fails Fit at train0, with the values `shape_color=<Proposer>` gives
- `background`: the background color
    - `concept`: the stored `background`, 0
    - `background=DominantColor`: the commonest color of the input; replaces `background`; undefined on a tie; fits every pair
        - witness `background=DominantColor`: breaks `background`; plausibility `variant`; verdict `background=DominantColor`; breaks the invariant that every input stands on a field of 0
    - `background=<Proposer>` for each other color proposer: fails Fit at train0, with the values `shape_color=<Proposer>` gives
- `tile-parse`: how the tiles are found
    - `concept`: each tile is a 4-connected piece of ink that holds `tile_color`
    - `gap=stored`: the tiles lie on a tiling from the top-left corner of the tile region, each of the extent of the piece there, at a stride of that extent plus the stored `gap`, 1; replaces `tile-grid` (`gap` becomes a parameter); undefined where the concept is, and where a part of a piece left off the tiling repeats a code color; fits every pair
        - witness `wide-gaps`: breaks `tile-grid` (`gap`); plausibility `variant`; verdict `concept`; breaks the invariant that neighboring tiles stand one cell apart
- `legend-source` & `code-cell`, `legend-source` & `tile-color`, `legend-source` & `background`, `legend-source` & `tile-parse`, `legend-pairing` & `marker-corner`, `legend-pairing` & `shape-ink`, `legend-pairing` & `code-cell`, `legend-pairing` & `tile-color`, `legend-pairing` & `background`, `legend-pairing` & `tile-parse`, `shape-place` & `marker-corner`, `shape-place` & `box-size`, `shape-place` & `shape-ink`, `shape-place` & `code-cell`, `shape-place` & `tile-color`, `shape-place` & `background`, `shape-place` & `tile-parse`, `marker-corner` & `box-size`, `marker-corner` & `shape-ink`, `marker-corner` & `code-cell`, `marker-corner` & `tile-color`, `marker-corner` & `background`, `marker-corner` & `tile-parse`, `box-size` & `shape-ink`, `box-size` & `code-cell`, `box-size` & `tile-color`, `box-size` & `background`, `box-size` & `tile-parse`, `shape-ink` & `code-cell`, `shape-ink` & `tile-color`, `shape-ink` & `background`, `shape-ink` & `tile-parse`, `code-cell` & `tile-color`, `code-cell` & `background`, `code-cell` & `tile-parse`, `tile-color` & `background`, `tile-color` & `tile-parse`, `background` & `tile-parse`: the two branches' changes applied together
- `legend-source` & `legend-pairing`, `legend-source` & `shape-place`, `legend-source` & `marker-corner`, `legend-source` & `box-size`, `legend-source` & `shape-ink`: the model of `$StoredLegend` alone, since a stored table reads no legend; these points stand at the concept, where their branches differ
- `legend-pairing` & `shape-place`, `legend-pairing` & `box-size`: the model of the `legend-pairing` branch alone, since its shape has no legend box and already sits by its bounding box; `shape-place` and `box-size` stand at the concept, where their branches differ

## Open parameters
- none

## Not formed
- A derivation of `tile_size` or `gap` by a proposer: the two are parameters only under `tile_size=stored` and `gap=stored`, and on one input TileDim gives several extents, while SepTileDim, SepThickness and Period read separator lines across the whole grid or a period, which no input has.
- A stamp in `shape_color` in place of the code's color, and a tile of `tile_color` left in place of a blank one: every output shows the code's color in the stamps and 0 in every uncoded tile, so no reading of the pairs takes them.
- A `marker_corner` other than top-left: under the concept, any other corner reads boxes that hold none of train0's shapes, so the pairs fix the value.

## Tickets filed
- none
