# e5062a87

## Concept
- A gray field has black holes and one red shape. Paint a red copy of that shape, in the same orientation, at every place where it fits completely on black cells.

## Scene
- `field-with-holes`: every cell that is not of the shape color is of the field color or of the hole color.
- `one-shape`: the cells of the shape color form one 4-connected shape.
- `placements-disjoint`: no two translates of the shape that lie completely on hole cells share a cell.

## Rules
- `stamp-every-fit`: each translate of the shape whose cells are all of the hole color in the input takes the shape color in the output.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `hole_color`: 0
- `shape_color`: 2

## Scene parameters
- `field_color`: 5
