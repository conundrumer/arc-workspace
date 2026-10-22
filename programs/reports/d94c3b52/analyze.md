# d94c3b52

## Concept
- Fits every pair (`check_concept.py`). No witness with verdict `other` was found, and the rules have a relational form as written.
- The concept is undefined on an input where no tile, or more than one tile, holds `key_color`.
- The pairs never put three key-shape tiles on one lattice line, so which color a key-shape tile between two others takes is left open by the pairs (`match-link-precedence`).
- Every key shape in the evidence fills its tile's 3×3 box, so exact matching and matching up to a shift within the tile agree on every pair (`shape-identity`).

## Choice points
- `shape-identity`
    - `concept`: a tile matches when its non-background cells are the key tile's, cell for cell
    - `$CongruentMatch`: replaces `match-takes-key-color`, a tile matches when its cells are a D4 image of the key tile's; fails Fit at train2 (tile (1,0), rows 5–7, cols 1–3, holds the key arch turned over, and train2 output keeps it in 1)
    - `$TranslateMatch`: replaces `match-takes-key-color`, a tile matches when its cells are a translate of the key tile's within the tile; fits every pair
        - witness `shifted-copy`, at the stored assignment: the key holds a 2×2 square at its top-left, and tile (2,2) holds it at its bottom-right; breaks no scene claim; plausibility `ordinary`; verdict `concept`
- `span-lines`
    - `concept`: links run along lattice rows and lattice columns
    - `$DiagonalSpans`: replaces `between-takes-link-color`, links also run along lattice diagonals; fails Fit at train1 (tile (1,2) lies diagonally between copies (0,1) and (2,3), and train1 output keeps it in 1 at (6,10))
- `span-endpoints`
    - `concept`: any two key-shape tiles on a line, the key tile included, end a link
    - `$KeyEndpointSpan`: replaces `between-takes-link-color`, a link has the key tile as one end; fails Fit at train0 (tiles (2,2)–(2,4) lie between copies (2,1) and (2,5), and train0 output paints them 7, e.g. (10,9))
    - `$KeyNotEndpoint`: replaces `between-takes-link-color`, the key tile ends no link; fails Fit at train0 (tile (0,3) lies between the key (0,2) and copy (0,4), and train0 output paints it 7 at (1,13))
- `link-paint`
    - `concept`: a linked tile recolors its shape cells to `link_color`
    - `$FillLinkTile`: replaces `between-takes-link-color`, a linked tile fills whole with `link_color`; fails Fit at train0 (tile (0,3) keeps 0 at (1,14))
    - `$StampKeyShape`: replaces `between-takes-link-color`, a linked tile takes the key shape in `link_color`; fails Fit at train0 (tile (0,3) shows its own X in 7, 0 at (2,13))
- `match-link-precedence`
    - `concept`: a key-shape tile keeps `key_color` when it lies between two others
    - `$LinkOverMatch`: replaces `between-takes-link-color`, a key-shape tile between two others takes `link_color`; fits every pair
        - witness `collinear-copies`, at the stored assignment: train0 with a copy of the ring at tile (0,3), between the key (0,2) and copy (0,4); breaks no scene claim; plausibility `ordinary`; verdict `concept`
- `key_color`
    - `concept`: stored, 8
    - `key_color=RarestColor`: the rarest input color; fits every pair (it gives 8 on each)
        - witness `key_color=RarestColor`, at the stored assignment: train0 with the key drawn in 2; breaks `one-key-tile`; plausibility `variant`; breaks the invariant that the key is drawn in 8; verdict `key_color=RarestColor`
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: the commonest input color; fits every pair (it gives 0 on each)
        - witness `background=DominantColor`, at the stored assignment: train0 with 3 for 0; breaks `tile-lattice` and `shape-tiles`; plausibility `variant`; breaks the invariant that the background is 0; verdict `background=DominantColor`
- `gap`
    - `concept`: stored, 1
    - `gap=SepThickness`: the separator thickness of a witnessed lattice; fits every pair (on each it gives 1, from the fit of two 8-row and two 12-column segments around the middle line); undefined where no lattice fit is witnessed
        - witness `gap=SepThickness`, at the stored assignment: the left 4×4 tiles of train0 laid out with lines 2 wide, 22×22; breaks `tile-lattice`; plausibility `variant`; breaks the invariant that every input is 17×25 with lines 1 wide; verdict `gap=SepThickness`
- `tile_size`
    - `concept`: stored, 3
    - `tile_size=SepTileDim`: fails Fit at train0 (it gives 8 and 12)
    - `tile_size=TileDim`: fails Fit at train0 (it gives 1, 2, 4, 5, 7, 8, 11 and 12, and no 3)
- `link_color`
    - `concept`: stored, 7
    - `link_color=OutNewColor`: reads `ex_out`, which is empty in a run on one input, so it gives no value; undefined on every pair, and fails Fit at train0
- `shape-identity` & `span-lines`, `shape-identity` & `span-endpoints`, `shape-identity` & `link-paint`, `shape-identity` & `match-link-precedence`, `shape-identity` & `key_color`, `shape-identity` & `background`, `shape-identity` & `gap`, `shape-identity` & `tile_size`, `shape-identity` & `link_color`, `span-lines` & `span-endpoints`, `span-lines` & `link-paint`, `span-lines` & `match-link-precedence`, `span-lines` & `key_color`, `span-lines` & `background`, `span-lines` & `gap`, `span-lines` & `tile_size`, `span-lines` & `link_color`, `span-endpoints` & `link-paint`, `span-endpoints` & `match-link-precedence`, `span-endpoints` & `key_color`, `span-endpoints` & `background`, `span-endpoints` & `gap`, `span-endpoints` & `tile_size`, `span-endpoints` & `link_color`, `link-paint` & `match-link-precedence`, `link-paint` & `key_color`, `link-paint` & `background`, `link-paint` & `gap`, `link-paint` & `tile_size`, `link-paint` & `link_color`, `match-link-precedence` & `key_color`, `match-link-precedence` & `background`, `match-link-precedence` & `gap`, `match-link-precedence` & `tile_size`, `match-link-precedence` & `link_color`, `key_color` & `background`, `key_color` & `gap`, `key_color` & `tile_size`, `key_color` & `link_color`, `background` & `gap`, `background` & `tile_size`, `background` & `link_color`, `gap` & `tile_size`, `gap` & `link_color`, `tile_size` & `link_color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Links only between consecutive key-shape tiles on a line: the union of their spans, less the key-shape tiles, is the union of the spans of every two key-shape tiles, so the model is equivalent to the concept.
- Links along rows alone, or along columns alone: the program enumerates both axes, and no variant narrows the set; train0 links on both (row 0 at (0,3), column 4 at (1,4)).
- Shapes found as connected components in place of lattice tiles: the link rule reads lattice rows and columns, which a component parse does not give, and a shape such as train1's lone center cell matches by its place in the tile.
- `shape_color`, `lattice_rows`, `lattice_cols`: scene parameters; the program reads the shape as the non-background cells, and the lattice size as the grid size over `tile_size` and `gap`.

## Tickets filed
- none
