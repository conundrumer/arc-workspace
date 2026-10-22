# b74ca5d1

## Concept
- Each corner marker calls in the shapes that carry its color as a key: every such shape swaps its own color with its key's color in place, and the overlay of all those shapes is stamped into that corner in the marker's color.

## Scene
- `background`: one color fills most of the grid, and differs from pair to pair.
- `corner-markers`: some of the four corner cells hold one non-background cell each, and the marked corners have distinct colors.
- `shapes`: each non-background color that no corner marker has draws one shape, whose cells need not be connected.
- `key-cell`: each shape has exactly one key, a cell of a corner marker's color that fits with the shape's cells in a `box-size` × `box-size` box, and each cell of a marker color off the corners is the key of exactly one shape.
- `shape-box`: a shape's cells with its key span `box-size` on both axes.
- `corner-clear`: the `box-size` × `box-size` box at each marked corner holds only background and the marker.

## Rules
- `swap-colors`: in each shape, every shape cell takes the key's color, and the key cell takes the shape's color.
- `stamp-corner`: each marked corner gets the overlay of the boxes of every shape keyed with its color, the shape cells and the key cell alike, painted in the marker's color, with each box flush against that corner.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `box-size`: 5
    - the extent on each axis of the box that holds a shape's cells and its key

## Scene parameters
- none
