# bf45cf4b

## Concept
- Fits every pair (`probe.py` reproduces train0–2 and test0). The concept's rules have a relational form and need no approximation. No witness has verdict `other`.

## Choice points
- `object-parse`
    - `concept`: the mask and the tile are the two connected components, under 8-adjacency, of the non-background cells.
    - `$Parse4Adj`: replaces `mask-shape`, with the components taken under 4-adjacency. It is undefined unless there are exactly two components. It fails Fit at train0, where the mask falls into three pieces (train1, train2 and test0 fail too).
    - `$MaskByColor`: replaces `mask-shape`. The tile is the one multicolor 8-connected component, and the mask is every other non-background cell, connected or not. It is undefined unless exactly one component is multicolor and the cells outside it share one color. It fits every pair. Witness `mask-in-two-pieces`: it breaks `mask-shape`, and its plausibility is `variant`, because the mask's cells are connected in every input, and a variant task's random mask can fall into pieces. Verdict `$MaskByColor`. At that witness, the concept finds three objects and is undefined.
- `tile-pick`
    - `concept`: the object with two or more colors is the tile, and the single-color object is the mask.
    - `$TileByCellCount`: replaces `pattern-tile`'s color test with "the object with more cells is the tile". It is undefined when the counts are equal. It fails Fit at train0, where both objects have 8 cells.
    - `$TileBySmallerBox`: replaces `pattern-tile`'s color test with "the object with the smaller bounding box is the tile". It fails Fit at train2 (4×4 tile, 3×3 mask) and at test0.
- `mask-cells`
    - `concept`: a block gets the tile when its cell belongs to the mask.
    - `$MaskBoxNonBg`: replaces `tile-on-mask-cell` and `background-elsewhere`, so that each non-background cell in the mask's bounding box gets the tile. It is defined wherever the concept is. It fits every pair. Witness `tile-inside-mask-box`: it breaks no scene claim. Its plausibility is `borderline`, because the two objects have disjoint bounding boxes in every input. Verdict `concept`.
- `tile-content`
    - `concept`: the tile is the tile component's cells, with background elsewhere in its bounding box.
    - `$TileBoxCrop`: replaces `tile-on-mask-cell`, so that the tile is the input cropped to the tile's bounding box, together with any mask cell that lies inside it. It is defined wherever the concept is. It fits every pair. Witness `mask-cell-in-tile-box`: it breaks `pattern-tile`, because the tile leaves a background corner at the edge of its box. Its plausibility is `borderline`: in every input the tile fills the edge of its bounding box, and the two objects have disjoint boxes. Verdict `concept`.
- `object-parse` & `tile-pick`, `object-parse` & `mask-cells`, `object-parse` & `tile-content`, `tile-pick` & `mask-cells`, `tile-pick` & `tile-content`, `mask-cells` & `tile-content`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Stored background color: the background is 4, 3, 1 and 8 in the four inputs, so one stored value fails Fit. Each reading derives it as the commonest color.
- Tile as the object with a square bounding box: in train2, the mask (3×3) and the tile (4×4) both have square boxes, so the reading is undefined there.
- Tile on the mask's empty cells (the complement): it contradicts every pair.
- Tile transformed by D4 or recolored per block: in every pair, every stamped block equals the tile.
- Block size other than the tile's size: no reading of the pairs gives another size, and the output's extent fixes it in every pair.

## Tickets filed
- none
