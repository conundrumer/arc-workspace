# e74e1818

## Concept
- The picture is a stack of colored layers, and each layer is flipped upside down in its own place.

## Scene
- `layer-per-color`: each non-background color forms one layer, and the layer's cells are all the cells of that color.
- `stacked-layers`: along the stacking axis `axis`, the layers occupy disjoint, consecutive spans of lines, and each line that a layer covers holds a cell of that layer.
- `background`: every other cell has the background color `bg`.

## Rules
- `flip-in-span`: each layer is reflected across the center of its own span along `axis`: a cell at line k of a span from line a to line b moves to line a + b - k, and keeps its position across the axis.
- `background-fill`: every cell that no reflected layer covers has the background color.

## Parameters
- `axis`: V
    - the axis along which the layers stack and are flipped
- `bg`: 0

## Scene parameters
none
