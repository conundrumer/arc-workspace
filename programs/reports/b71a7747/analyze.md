# b71a7747

## Concept
- Fits every pair (`probe.py` in this directory runs each reading over the pairs and the witness inputs).
- Each pair uses its own colors for the background, lines, tiles and path, so no color is a parameter. The program reads the color roles from each input: the tile cells are the cells of the colors other than the background, line and texture colors.
- The `noise` of train0 is a texture of diagonal stripes of 6 on the cells where |col − row| is 5, 11 or 17. The lines and tiles cover it, for example at (0,11) and (7,18). No stripe cell sits on a line cell or in a tile.
- The rule as the generator applies it: a path is drawn on a field of the tile color and cut into k×k tiles, and the tiles are spread out onto the crossings of a lattice. The output is the uncut picture. The concept's rule, which removes each row and column with no tile cell, gives that picture on every input where each row and column of each tile band holds a tile cell.
- No witness has verdict `other`.

## Choice points
- `line-source`: where the kept rows and columns are read from
    - `concept`: from the tiles
    - `$LineBreaks`: replaces `pack-tiles`. A kept column is a column where a line row holds a cell that is not the line color, and a kept row is the same on the line columns. Undefined where no line is interrupted. Fits every pair. Witness `texture-on-line`: breaks no scene claim; stored assignment; plausibility `variant`; verdict `concept`; invariant broken: no texture cell sits on a line cell.
        - `kept-lines`: how the tiles give the output
            - `concept`: keep each row and column that holds a tile cell
            - `$LatticeBands`: replaces `pack-tiles`. Keep each row and column within the tiles' half-side of a line crossing where the whole square fits in the frame, whatever those cells hold. Undefined where the tiles are not equal squares. Fits every pair. Witness `missing-band`: breaks `tiles`; stored assignment; plausibility `borderline`; verdict `concept`; invariant broken: every crossing where a square fits holds a tile.
            - `$PackTiles`: replaces `pack-tiles`. Crop each tile (a 4-connected component of tile cells) and put it at its rank among the tile tops and among the tile lefts. Undefined where the tiles are not equal solid squares in a full array. Fits every pair. Fails Subsumption: where it is defined, it gives the concept's grid. Witness `missing-tile`, where it is undefined: breaks `tiles`; stored assignment; plausibility `borderline`; verdict `concept`; invariant broken: every crossing where a square fits holds a tile.
        - `tile-colors`: which colors make tile cells
            - `concept`: every color other than the background, line and texture colors, which is the tile color and the path color
            - `$TileColorOnly`: replaces the reading of a tile cell in `pack-tiles`. Only the tile color makes tile cells, and path cells do not. Fits every pair. Witness `path-edge-row`: breaks no scene claim; stored assignment; plausibility `borderline`; verdict `concept`; invariant broken: every row and every column of each tile band holds a tile-color cell.
            - `$TextureKept`: replaces `noise`. Only the background and line colors are lattice colors, so texture cells count as tile cells. Fails Fit at train0, where the stripe cells keep every row and column of the input, those between the tiles too.
            - `$BorderColors`: the lattice colors are the colors on the frame's border ring, and every other color makes tile cells. Fails Fit at train1, where the border is all line color, so the background color 1 is read as a tile color.
            - `$CommonColors`: the two commonest colors of the input are lattice colors. Fails Fit at train0, where 8 is the second commonest color, and at test0, where 2 is the commonest.
- `kept-lines` & `tile-colors`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- none

## Tickets filed
- none
