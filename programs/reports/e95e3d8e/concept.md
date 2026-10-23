# e95e3d8e

## Concept
- A wallpaper pattern has holes punched in it; fill each hole by continuing the repeating pattern.

## Scene
- `periodic-tiling`: the input is a tile repeated on both axes, with some cells covered by holes; on each axis the cells outside the holes repeat with one period, the least such period, and the period differs from input to input.
- `hole-patches`: the holes are solid rectangles of `hole_color`, and `hole_color` appears nowhere in the tile.
- `every-residue-visible`: each cell of the tile, by its row and column residue under the periods, shows outside the holes somewhere in the input.

## Rules
- `fill-from-period`: each hole cell takes the color of an uncovered cell in the same row residue and the same column residue under the periods; every other cell keeps its color.

## Parameters
- `hole_color`: 0

## Scene parameters
- none
