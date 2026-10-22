# ce8d95cc

## Concept
- Squeeze the grid: each run of identical adjacent rows becomes one row, and then each run of identical adjacent columns becomes one column.

## Scene
- `full-lines`: on a field of `background`, straight lines of one color each run the full width (rows) or the full height (columns) of the grid; where two lines cross, the cell takes one of the two colors.
- `lines-apart`: no two lines of one axis are adjacent; at least one row or column of `background` lies between them, and between each outermost line and the grid edge.

## Rules
- `dedupe-rows`: the output keeps the input's rows in order, with each run of identical adjacent rows kept once.
- `dedupe-columns`: in the result of `dedupe-rows`, each run of identical adjacent columns is kept once.

## Parameters
- none

## Scene parameters
- `background`: `0`
