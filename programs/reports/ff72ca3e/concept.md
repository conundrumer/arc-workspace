# ff72ca3e

## Concept
- Each yellow cell grows a red square centered on it, as large as it can be before it would reach a gray cell.

## Scene
- `lone-cells`: on a field of `background`, every other cell is a lone cell of `center_color` or of `blocker_color`.
- `blocker-near`: each `center_color` cell has at least one `blocker_color` cell somewhere in the grid.
- `square-fits`: the square each `center_color` cell grows lies wholly inside the grid.
- `squares-apart`: no two of the squares share a cell, and no square holds another `center_color` cell.

## Rules
- `square-radius`: a center's square has radius one less than the Chebyshev distance from the center to its nearest `blocker_color` cell.
- `paint-square`: every grid cell of a square that is not a `center_color` cell takes `fill_color`; every `center_color` cell keeps its color.
- `keep-rest`: every cell outside the squares keeps its input color.

## Parameters
- `center_color`: 4
- `blocker_color`: 5
- `fill_color`: 2

## Scene parameters
- `background`: 0
