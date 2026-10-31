# f931b4a8

## Concept
- The grid is split into four quadrants. One holds a pattern with holes, one holds a grid of fill colors, and the other two give the output's height and width by how many marked cells each has. The output tiles the pattern over that size, starting from one corner, and fills the holes of each tile with the fill-grid cell at the same place as that tile, so the fill grid shows up scaled by the tile size.

## Scene
- `four-quadrants`: the input is a square of even side, cut into four equal square quadrants.
- `pattern-quadrant`: the `pattern_quad` quadrant holds a pattern of non-`bg` colors with at least one `bg` hole.
- `fill-quadrant`: the `fill_quad` quadrant has no `bg` cell; each of its cells is a fill color.
- `count-quadrants`: each quadrant in `count_quad` holds at least one non-`bg` cell on `bg`, and at most as many as the quadrant has cells.

## Rules
- `output-size`: the output's extent along each axis is the number of non-`bg` cells in that axis's `count_quad` quadrant.
- `tile-pattern`: the output is covered by copies of the pattern quadrant, laid edge to edge from the `anchor` corner of the output, and cut off at the far edges.
- `fill-holes-scaled`: in the tile i tiles down and j tiles across from the `anchor` corner, each `bg` cell takes the color of the fill quadrant's cell i rows down and j columns across from its own `anchor` corner. Every other cell keeps the pattern's color.

## Parameters
- `bg`: 0
- `pattern_quad`: BR
- `fill_quad`: BL
- `count_quad`: V → TL, H → TR
    - the quadrant whose non-`bg` count gives the output's extent along each axis
- `anchor`: TL
    - the corner the tiling starts from, and the corner the fill grid's cells are counted from

## Scene parameters
- none
