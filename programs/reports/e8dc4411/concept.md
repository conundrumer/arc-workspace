# e8dc4411

## Concept
- A shape repeats in a line along a diagonal, toward a single marker cell next to it, in the color of that marker. Each copy meets the previous one corner to corner, and the copies go on until they leave the grid.

## Scene
- `background`: the most common color fills the grid.
- `template-shape`: the cells of color `shape_color` form one shape, the template.
- `single-marker`: one cell has a color that is neither the background nor `shape_color`. That cell is the marker.
- `marker-past-diagonal-tip`: the marker is diagonally adjacent to a template cell, and it lies past every template cell along that diagonal direction.

## Rules
- `direction`: the direction of the copies is the diagonal direction from the template to the marker.
- `step`: the step is the translation along the direction by the template's extent along that diagonal. Thus the first copy's cells nearest the template are one diagonal step past the template's cells nearest the marker, and the marker is a cell of the first copy.
- `repeat`: copies stand at one, two, three and more steps from the template, until a copy is fully outside the grid. Cells of a copy that fall outside the grid are dropped.
- `paint`: each copy paints its cells in the marker color. All other cells keep their input color.

## Parameters
- `shape_color`: 0
    - the color of the template's cells

## Scene parameters
none
