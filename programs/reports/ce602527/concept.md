# ce602527

## Concept
- A large shape at the edge of the grid is an enlarged close-up of one of the two small shapes, and the output is the small shape it shows.

## Scene
- `background`: one color fills the grid around the shapes.
- `color-shapes`: each other color is one shape: the cells of that color, which need not be connected.
- `three-shapes`: there are three shapes.
- `enlarged-copy`: one shape is a copy of one of the other two, each cell scaled to a `scale` × `scale` block, in the same orientation.
- `edge-cut`: the grid edge cuts the enlarged copy, so only part of it shows.
- `small-whole`: the two small shapes lie whole inside the grid.
- `one-match`: the visible part of the enlarged copy agrees with the enlarged form of one small shape only.

## Rules
- `pick-shown-shape`: the shown shape is the small shape whose enlarged form, at some placement, has the large shape's cells as the part of it inside the grid.
- `crop-shown-shape`: the output is the bounding box of the shown shape, its cells in its color and the other cells in the background color.

## Parameters
- `scale`: 2
    - the factor by which the enlarged copy scales each cell of the small shape

## Scene parameters
- none
