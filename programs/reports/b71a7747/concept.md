# b71a7747

## Concept
- Square tiles sit on the crossings of a grid of lines, and a path is drawn across them in pieces; take the tiles out and push them together so the path joins up.

## Scene
- `tiling`: a background crossed by evenly spaced full rows and full columns of a line color.
- `tiles`: equal solid squares of a tile color, one centered on each line crossing where the whole square fits in the frame, so they form a full rectangular array with a gap of at least one cell between neighbors on each axis.
- `path`: a path of a path color is drawn inside the tiles, and only there; it runs across tile edges, so it is one 4-connected line once the gaps are closed.
- `noise`: some inputs also hold scattered cells of a noise color, only outside the tiles.

## Rules
- `pack-tiles`: the output is the tiles laid edge to edge, in their row and column order, with everything outside the tiles dropped: the input with each row and each column that holds no tile cell removed.

## Parameters
- none

## Scene parameters
- none
