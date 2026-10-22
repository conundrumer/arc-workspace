# d931c21c

## Concept
- Each outline that closes around a hole gets a halo: the cells around it on the outside turn `outer_color`, and the cells of the hole that touch it turn `inner_color`. An outline with a gap is left as it is.

## Scene
- `outlines-on-background`: the input is a `background` field with a few separate one-cell-wide outlines of `wall_color` drawn on it, each outline a 4-connected set of `wall_color` cells.
- `some-closed-some-open`: some outlines are closed: the outline alone closes a region off, its hole, made of the cells not in it that no walk from the frame edge reaches, where a walk steps to any of the eight neighbors through cells not in the outline. The other outlines are broken by one or more one-cell gaps that let the inside reach the outside, and a piece between two gaps can be a single cell.
- `outlines-apart`: no cell is 8-adjacent both to a closed outline and to another outline.

## Rules
- `outer-halo`: each `background` cell that is 8-adjacent to a closed outline, and is not in that outline's hole, becomes `outer_color`.
- `inner-halo`: each `background` cell of a closed outline's hole that is 8-adjacent to that outline becomes `inner_color`, also where another outline's outer halo reaches it.
- `rest-unchanged`: every other cell keeps its input color, so the cells of a hole that touch no outline cell stay `background`, and open outlines and their surroundings do not change.

## Parameters
- `background`: 0
- `wall_color`: 1
- `outer_color`: 2
- `inner_color`: 3

## Scene parameters
none
