# eb5a1d5d

## Concept
- A stack of nested rectangles is redrawn as concentric squares, one ring per rectangle, outermost to innermost, with the innermost as the single center cell.

## Scene
- `background-field`: the outermost layer is one color that fills the grid border and everything outside the first rectangle.
- `nested-rectangles`: one or more solid filled rectangles, each strictly inside the one before it, touching none of its edges, so the layers form one chain by containment.
- `layer-differs-from-container`: each layer's color differs from the color of the layer that contains it; a color may recur at layers further apart.

## Rules
- `depth-chain`: the layers, from the background inward, are numbered by depth 0 to n-1.
- `concentric-output`: the output is a square of side `(2n-1)·ring_width`; a cell takes the color of the layer whose depth equals its ring, its Chebyshev distance from the output's border, divided by `ring_width`.
- `sizes-dropped`: the rectangles' sizes, margins and positions do not reach the output; only the order of their colors does.

## Parameters
- `ring_width`: 1
    - the width in cells of each ring in the output, the center square included.

## Scene parameters
- none
