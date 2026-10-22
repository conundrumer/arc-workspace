# c803e39c

## Concept
- Fits every train and test pair (`check_concept.py`, `probe.py`). No witness has the verdict `other`. The rules `tile-by-map` and `tile-colors` are relational: each output cell is the fill color where its block's map cell and its in-block tile cell are both set, and the ground color otherwise. No approximation is involved.

## Choice points
- `shape-role`: how the tile shape and the map shape are told apart
    - `concept`: by panel rank: panel 0 is the tile, panel 1 is the map (`panel_role`)
    - `$TileByColor`: replaces `tile-shape` and `map-shape` as read by the program: the tile is the shape of stored `tile_color` (1) and the map the shape of stored `map_color` (2), wherever they sit among panels 0 and 1; undefined where panel 0 or 1 holds more than one color or neither holds one of the two colors. Fits every pair. Witness `swapped-shape-colors` (train0 input with 1 and 2 swapped): breaks `tile-shape` and `map-shape`; stands at the stored assignment; plausibility `variant`; verdict `concept`; breaks the invariant that panel 0's shape is 1 and panel 1's shape is 2.
- `shape-frame`: the frame each shape is read in
    - `concept`: an n×n square one cell in from the panel's top and near side, where n is the side of the solid squares
    - `$ShapeBbox`: replaces `shapes-span-square` and the frame in `four-panels`: each shape's frame is its own bounding box, and the output is (map height × tile height) by (map width × tile width); undefined where a shape panel is empty. Fits every pair. Witness `shape-short-of-square` (train0 input, tile with its last column empty): breaks `shapes-span-square`; stands at the stored assignment; plausibility `variant`; verdict `concept`; breaks the invariant that each shape touches all four sides of its square.
    - `$HeightSide`: replaces how `four-panels` gives n: n is the grid height less 2, and the frames are n×n squares at the same place; undefined where a frame leaves the grid. Fits every pair. Witness `extra-bottom-row` (train0 input with one more row of background and dividers): breaks `four-panels` (the grid is n+2 high); stands at the stored assignment; plausibility `borderline`; verdict `concept`; breaks the invariant that the grid height is the solid squares' side plus 2.
- `divider`: the divider color
    - `concept`: stored `divider_color` = 5
    - `$DividerByLines`: derived by the program's clauses: the one non-background color that fills a full-height column; undefined where no such color or more than one exists. Fits every pair. Witness `recolored-dividers` (train0 input with 5 recolored to 6): breaks `four-panels` (`divider_color`); stands at the stored assignment, where the concept is undefined; plausibility `variant`; verdict `$DividerByLines`; breaks the invariant that the dividers are 5.
    - `divider_color=SharedColor`: derived as every color of the input, so the background columns of the panel margins also count as dividers and the input has more than four panels; fails Fit at train0 (and at every pair).
- `background`: the background color
    - `concept`: stored `background` = 0
    - `background=DominantColor`: derived as the input's commonest color. Fits every pair. Witness `background=DominantColor` (train0 input with 0 recolored to 6): breaks `four-panels` (`background`); stands at the stored assignment, where the concept is undefined; plausibility `variant`; verdict `background=DominantColor`; breaks the invariant that the background is 0.
    - `background=SharedColor`: derived as every color of the input, so no cell is ink and the solid squares have no color; fails Fit at train0 (and at every pair).
- `shape-role` & `shape-frame`, `shape-role` & `divider`, `shape-role` & `background`, `shape-frame` & `divider`, `shape-frame` & `background`, `divider` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Fill and ground told apart by color value (the lower color as fill holds in every pair): colors have identity and no other properties.
- Tile and map swapped, or the fill and ground panels swapped: another value of the stored `panel_role`, which fails Fit at train0, and not a different program.
- A map-unset block drawn as the tile's complement or in the fill color: every pair draws such a block all in the ground color, so the branch fails Fit at every pair and its rule `tile-by-map` has no other reading the pairs leave open.

## Tickets filed
- tickets/open/10-550_task_c803e39c_analyze.md
- tickets/open/10-551_task_c803e39c_analyze.md
