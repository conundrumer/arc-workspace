# fea12743

## Concept
- Fits every pair (`work/task/fea12743/check_concept2.py`, `work/task/fea12743/probe.py`). The concept needs a rule for picking a copy only in train0. There, the part shape `2222/0200/0200/2222` is drawn at tiles (0,1) and (2,0), and both are the union partner of (1,0) for (2,1). The output paints (0,1), which comes first in `copy_order`, and leaves (2,0) at 2. A first-draft concept without `copy_order` failed train0 for this reason.
- No witness has verdict `other`. As the generator applies it, the rule is: the tile it built as the overlay of two others becomes `union_color`, and the two tiles it drew as the pieces become `part_color`. The concept's `one-union` and `copy_order` approximate this by recovering those tiles from the grid.

## Choice points
- `union-tile`: how the union tile is found
    - `concept`: the one tile that is the cell-wise union of two other tiles, with one shape pair (`one-union`)
    - `$ProperUnion`: replaces `one-union`. A union whose shape equals one of its parts' shapes is ignored. No new parameters. Undefined where the remaining unions are not one tile with one shape pair. Fits every pair. Witness `$ProperUnion` breaks `one-union`: a bare frame lies inside a shape that is drawn twice, and a fuller tile is no union. Plausibility `borderline`, because it breaks the invariant that every input has exactly one union and that the union is the fullest tile. Verdict `$ProperUnion`: the union of a shape with a copy that contains it is trivial.
    - `$MaxCountUnion`: replaces `one-union`. The union tile is the unique fullest tile, and its parts are the one shape pair whose union it is. No new parameters. Undefined where the fullest count is tied, or where the fullest tile is not the union of exactly one shape pair. Fits every pair. Witness `two-proper-unions` breaks `one-union`. Plausibility `borderline`, because it breaks the invariant that every input has exactly one union. Verdict `$MaxCountUnion`: in every pair the union is the fullest tile.
- `combine-op`: how two tiles combine into the union tile
    - `concept`: cell-wise OR of the ink
    - `$XorCombine`: replaces `one-union` and `paint-parts`. The tile is the cell-wise XOR of two others. Undefined where no tile is. Fails Fit at train0, where no tile is such an XOR because the frames overlap. It is undefined on every pair.
    - `$IntersectCombine`: replaces `one-union` and `paint-parts`. The tile is the cell-wise AND of two others. Undefined where no tile is. Fails Fit at train0 (undefined on every pair).
- `painted-parts`: which tiles take `part_color`
    - `concept`: the two tiles of the shape pair whose union is the union tile (`paint-parts`)
    - `$SubsetParts`: replaces `paint-parts`. Every other tile whose ink lies inside the union tile is painted. Fails Fit at train0, where it also paints (2,0).
- `duplicate-copy`: which copy of a part shape drawn more than once gets painted
    - `concept`: the first copy in `copy_order`
    - `$FartherCopy`: replaces `paint-parts`. The painted copy is the one farthest from the union tile, by taxicab distance over tile positions. Does not read `copy_order`. Undefined where the farthest copies tie. Fits every pair. Witness `duplicate-part-nearer-first` breaks no scene claim. Plausibility `ordinary`. Verdict `any`: the pairs show only one duplicated part, and the copy is free.
    - `$AllCopies`: replaces `paint-parts`. Every copy of a part shape is painted. Fails Fit at train0, where (2,0) stays 2.
- `tile-frame`: where the tiles are
    - `concept`: the stored `tile_size` 4 and `gutter` 1
    - `$GutterLayout`: derives the layout in place of the stored `tile_size` and `gutter`, replacing `tile-layout`. The tiles are the maximal blocks between all-background rows and all-background columns. Undefined where those blocks differ in size. Fits every pair. Witness `$GutterLayout` (3×3 tiles in a 13×9 frame) breaks `tile-layout` at `tile_size` 4. Plausibility `variant`, because it breaks the invariant that every input is a 16×11 frame of 4×4 tiles. Verdict `$GutterLayout`.
- `union-tile` & `combine-op`, `union-tile` & `painted-parts`, `union-tile` & `duplicate-copy`, `union-tile` & `tile-frame`, `combine-op` & `painted-parts`, `combine-op` & `duplicate-copy`, `combine-op` & `tile-frame`, `painted-parts` & `tile-frame`, `duplicate-copy` & `tile-frame`: the two branches' changes applied together
- `painted-parts` & `duplicate-copy`: each case that takes `$SubsetParts` and a non-concept `duplicate-copy` branch has `$SubsetParts`'s model. No copy is chosen when every contained tile is painted. `duplicate-copy` exists with the concept branch of `painted-parts`, so it stays at the concept.
    - `$SubsetParts` & `$FartherCopy`: `$SubsetParts`'s model
    - `$SubsetParts` & `$AllCopies`: `$SubsetParts`'s model

## Open parameters
- none

## Not formed
- Other scan orders for `copy_order`: these are values of the stored orientation parameter, not branches. The pairs exclude top-left column-major and both bottom-left orders, but leave top-right row-major, top-right column-major and bottom-right column-major alongside reading order. A reader of "reading order" takes top-left row-major only, so these are not open values.
- `part_color` and `union_color` derived from the input: 8 and 3 appear in no input, and a `@derive` proposer reads one input and no output.
- `tile_size=TileDim` and `tile_size=SepTileDim`: I did not form these. I judged from the proposers' descriptions and did not read or run them. Their formula n·d + (n−1)·g has no outer margin, so on the 16×11 frame TileDim gives sizes besides 4 (16 = 3·4 + 2·2, 11 = 3·3 + 2·1), and a `@derive` branch reads every value it derives. `$GutterLayout` covers deriving the layout from the input.
- Tiles as connected pieces (`objects`): a tile can be more than one connected piece. Test (0,0) is two 8-connected pieces, and train2 (2,1) is two 4-connected pieces. A piece is then not a drawing, and the tile frame is the decomposition.
- Which copy of a duplicated union tile gets painted: `one-union` makes the union one tile. A second copy would give two union hits, and no input shows that.

## Tickets filed
- none
