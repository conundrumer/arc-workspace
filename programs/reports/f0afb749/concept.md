# f0afb749

## Concept
- Blow the grid up by two, so each dot becomes a 2×2 block, then draw a blue diagonal through each block, top-left to bottom-right, out to the edges.

## Scene
- `background-field`: every cell that is not a mark is `background`.
- `single-cell-marks`: the marks are isolated single cells, no two touching, even at a corner.
- `one-mark-color`: all marks of an input share one color, which differs between inputs.
- `square-grid`: the input is square.
- `one-mark-per-diagonal`: no two marks lie on one line along `line_axis`.

## Rules
- `scale-up`: the output is the input scaled by `scale`: each input cell becomes a `scale`×`scale` block of its color.
- `diagonal-through-block`: for each mark's block, every background cell of the output on the line along `line_axis` that runs through the block's corner-to-corner diagonal takes `line_color`, on both sides of the block out to the grid edge.

## Parameters
- `scale`: 2
    - the scale factor on each axis
- `line_axis`: the main diagonal, top-left to bottom-right
    - the diagonal axis the lines follow
- `line_color`: 1
- `background`: 0

## Scene parameters
- none
